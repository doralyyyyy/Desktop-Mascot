import json
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from config import AppConfig
from text_utils import tts_friendly_text


class AITTS:
    def __init__(self, config: AppConfig, language: str) -> None:
        self.enabled = config.tts_enabled
        self.provider = config.tts_provider
        self.api_key = config.tts_api_key
        self.base_url = config.tts_base_url
        self.model = config.tts_model
        self.voice_zh = config.tts_voice_zh
        self.voice_ja = config.tts_voice_ja
        self.response_format = config.tts_response_format
        self.sample_rate = config.tts_sample_rate
        self.bitrate = config.tts_bitrate
        self.speed = config.tts_speed
        self.volume = config.tts_volume
        self.pitch = config.tts_pitch
        self.language = language
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._current_file: Path | None = None
        self._ffplay = shutil.which("ffplay")

    def set_language(self, language: str) -> None:
        self.language = language

    def speak(
        self,
        text: str,
        on_play_start: Callable[[], None] | None = None,
        on_play_end: Callable[[], None] | None = None,
        on_error: Callable[[], None] | None = None,
    ) -> bool:
        text = tts_friendly_text(text)
        if not self.enabled or not self.api_key or not text:
            return False
        threading.Thread(
            target=self._speak_worker,
            args=(text, self.language, on_play_start, on_play_end, on_error),
            daemon=True,
        ).start()
        return True

    def stop(self) -> None:
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
            self._process = None
            self._cleanup_current_file()

    def _speak_worker(
        self,
        text: str,
        language: str,
        on_play_start: Callable[[], None] | None,
        on_play_end: Callable[[], None] | None,
        on_error: Callable[[], None] | None,
    ) -> None:
        audio_path: Path | None = None
        play_started = False

        def handle_play_start() -> None:
            nonlocal play_started
            play_started = True
            if on_play_start:
                on_play_start()

        try:
            audio_path = self._request_audio(text, language)
            self._play_audio(audio_path, handle_play_start)
        except Exception:
            if on_error:
                on_error()
            return
        finally:
            if play_started and on_play_end:
                on_play_end()
            if audio_path is not None:
                try:
                    audio_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _request_audio(self, text: str, language: str) -> Path:
        if self.provider == "minimax":
            audio = self._request_minimax_audio(text, language)
        else:
            with urlopen(self._open_speech_response(text, language), timeout=60) as response:
                audio = response.read()

        suffix = f".{self.response_format}" if self.response_format in {"mp3", "wav", "flac"} else ".audio"
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        path = Path(handle.name)
        with handle:
            handle.write(audio)
        return path

    def _speech_request(self, text: str, language: str, include_format: bool = True) -> Request:
        payload = {
            "model": self.model,
            "voice": self.voice_ja if language == "ja" else self.voice_zh,
            "input": text,
            "instructions": (
                "若い女性の自然な声で、親しみやすく軽い会話のように読んでください。"
                if language == "ja"
                else "用年轻女性的自然口吻朗读，声音清亮、有亲近感，像日常聊天。"
            ),
        }
        if include_format and self.response_format:
            payload["response_format"] = self.response_format
        return Request(
            f"{self.base_url}/audio/speech",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

    def _open_speech_response(self, text: str, language: str):
        try:
            return urlopen(self._speech_request(text, language), timeout=60)
        except HTTPError:
            if not self.response_format:
                raise
            return urlopen(self._speech_request(text, language, include_format=False), timeout=60)

    def _minimax_payload(self, text: str, language: str) -> dict:
        return {
            "model": self.model,
            "text": text,
            "stream": False,
            "language_boost": "Japanese" if language == "ja" else "Chinese",
            "output_format": "hex",
            "voice_setting": {
                "voice_id": self.voice_ja if language == "ja" else self.voice_zh,
                "speed": self.speed,
                "vol": self.volume,
                "pitch": self.pitch,
            },
            "audio_setting": {
                "sample_rate": self.sample_rate,
                "bitrate": self.bitrate,
                "format": self.response_format or "mp3",
                "channel": 1,
            },
        }

    def _minimax_request(self, text: str, language: str) -> Request:
        payload = self._minimax_payload(text, language)
        return Request(
            f"{self.base_url}/t2a_v2",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

    @staticmethod
    def _audio_from_minimax_json(result: dict) -> bytes:
        audio_hex = ""
        if isinstance(result.get("data"), dict):
            audio_hex = str(result["data"].get("audio") or "")
        if not audio_hex:
            audio_hex = str(result.get("audio_file") or result.get("audio") or "")
        if not audio_hex:
            raise ValueError("MiniMax TTS response did not include audio")
        return bytes.fromhex(audio_hex)

    def _request_minimax_audio(self, text: str, language: str) -> bytes:
        with urlopen(self._minimax_request(text, language), timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        return self._audio_from_minimax_json(result)

    def _play_audio(self, audio_path: Path, on_play_start: Callable[[], None] | None = None) -> None:
        if self._ffplay:
            self._play_audio_ffplay(audio_path, on_play_start)
            return

        script = (
            "Add-Type -AssemblyName PresentationCore;"
            "$path=[Console]::In.ReadToEnd().Trim();"
            "$player=New-Object System.Windows.Media.MediaPlayer;"
            "$player.Open([Uri]$path);"
            "$player.Volume=1.0;"
            "$player.Play();"
            "while ($player.NaturalDuration.HasTimeSpan -eq $false) { Start-Sleep -Milliseconds 50; }"
            "$duration=$player.NaturalDuration.TimeSpan.TotalMilliseconds;"
            "Start-Sleep -Milliseconds ([int]($duration + 250));"
            "$player.Close();"
        )
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
            self._cleanup_current_file()
            self._current_file = audio_path
            self._process = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=creation_flags,
            )
            process = self._process
        try:
            if on_play_start:
                on_play_start()
            process.communicate(input=str(audio_path), timeout=120)
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
                    self._current_file = None

    def _play_audio_ffplay(
        self,
        audio_path: Path,
        on_play_start: Callable[[], None] | None = None,
    ) -> None:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
            self._cleanup_current_file()
            self._current_file = audio_path
            self._process = subprocess.Popen(
                [
                    self._ffplay,
                    "-nodisp",
                    "-autoexit",
                    "-loglevel",
                    "quiet",
                    str(audio_path),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            process = self._process
        try:
            if on_play_start:
                on_play_start()
            process.wait(timeout=120)
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
                    self._current_file = None

    def _cleanup_current_file(self) -> None:
        if self._current_file:
            try:
                self._current_file.unlink(missing_ok=True)
            except OSError:
                pass
            self._current_file = None
