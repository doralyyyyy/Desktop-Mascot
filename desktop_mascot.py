import base64
import ctypes
import io
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time
import shutil
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageGrab
from ui_widgets import ChatBubble, PillButton, RoundedPopupMenu, TogglePill


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR

ENV_FILE = APP_DIR / ".env"
APP_USER_MODEL_ID = "DesktopMascot.LocalApp.11"


def set_windows_app_id() -> None:
    if platform.system() != "Windows":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def show_in_windows_taskbar(window: tk.Tk | tk.Toplevel) -> None:
    if platform.system() != "Windows":
        return
    try:
        hwnd = window.winfo_id()
        gwl_exstyle = -20
        ws_ex_appwindow = 0x00040000
        ws_ex_toolwindow = 0x00000080
        get_style = ctypes.windll.user32.GetWindowLongPtrW
        set_style = ctypes.windll.user32.SetWindowLongPtrW
        style = get_style(hwnd, gwl_exstyle)
        style = (style | ws_ex_appwindow) & ~ws_ex_toolwindow
        set_style(hwnd, gwl_exstyle, style)
        window.withdraw()
        window.after(10, window.deiconify)
    except Exception:
        pass

def normalize_language(value: str) -> str:
    value = value.strip().lower()
    if value in {"ja", "jp", "japanese", "日本語", "日语"}:
        return "ja"
    return "zh"


def language_instruction(language: str) -> str:
    if language == "ja":
        return "重要：接下来的桌宠回复只能使用日语。每次只说一句自然的日语口语，不要 Markdown，少用标点。"
    return "重要：接下来的桌宠回复只能使用中文。每次只说一句自然的中文口语，不要 Markdown，少用标点。"


def observe_prompt(language: str) -> str:
    if language == "ja":
        return (
            "これは自動で見えたユーザーの現在の画面です。"
            "画面の内容に合わせて雑談か軽いツッコミを一言だけ言ってください。"
            "日本語だけを使い、スクリーンショットを見ていることは説明せず、Markdown は使わないでください。"
        )
    return (
        "这是你自动看到的用户当前屏幕。"
        "根据屏幕内容主动闲聊或吐槽一句。"
        "只说一句中文，不要解释你在截图，不要 Markdown，少用标点。"
    )


def welcome_message(language: str) -> str:
    if language == "ja":
        return "画面を見ながら雑談するね。自動観察はいつでも切れるよ。"
    return "我会看屏幕陪你闲聊，自动观察可以随时关。"


def context_cleared_message(language: str) -> str:
    if language == "ja":
        return "コンテキストをクリアしたよ。"
    return "上下文已清空。"


def load_env(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_text(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def normalize_tts_provider(value: str, model: str, base_url: str) -> str:
    value = value.strip().lower()
    if value in {"openai", "minimax"}:
        return value
    if model.startswith("speech-") or "/minimax/" in base_url.lower():
        return "minimax"
    return "openai"


def clean_model_reply(text: str) -> str:
    text = text.strip()
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_~]+", "", text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"^\s*\d+[.)]\s+", "", line)
        line = line.strip()
        if line:
            lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    first_sentence = re.split(r"(?<=[。.!！?？])\s*", text, maxsplit=1)[0].strip()
    text = first_sentence or text
    if len(text) > 60:
        text = text[:60].rstrip() + "..."
    return text


def tts_friendly_text(text: str) -> str:
    text = clean_model_reply(text)
    text = re.sub(r"[#*_`~>\[\](){}<>|\\/@$%^&=+:;；：，,。.!！?？、…·\"'“”‘’《》【】]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class AppConfig:
    api_key: str
    base_url: str
    model: str
    tts_enabled: bool
    tts_provider: str
    tts_api_key: str
    tts_base_url: str
    tts_model: str
    tts_voice_zh: str
    tts_voice_ja: str
    tts_response_format: str
    tts_sample_rate: int
    tts_bitrate: int
    tts_speed: float
    tts_volume: float
    tts_pitch: int
    include_screen_by_default: bool
    max_history_turns: int
    request_timeout: int
    screen_detail: str
    auto_observe_enabled: bool
    auto_observe_interval_seconds: int
    system_prompt: str
    language: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_env(ENV_FILE)
        default_prompt = (
            "你是一个住在用户 Windows 桌面上的桌宠，主要陪用户闲聊和吐槽。"
            "你能看到用户发来的屏幕截图。"
            "每次只回复一句当前指定输出语言的口语，最多二十五个字。"
            "不要使用 Markdown，不要列表，不要代码块，不要链接格式。"
            "尽量少用标点符号，适合被文字转语音直接念出来。"
        )
        tts_base_url = env_text(
            "TTS_BASE_URL",
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        ).rstrip("/")
        tts_model = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
        tts_provider = normalize_tts_provider(env_text("TTS_PROVIDER", "auto"), tts_model, tts_base_url)
        default_tts_voice_zh = "Chinese (Mandarin)_Crisp_Girl" if tts_provider == "minimax" else "nova"
        default_tts_voice_ja = "Japanese_GracefulMaiden" if tts_provider == "minimax" else "nova"
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=os.getenv("MASCOT_MODEL", "gpt-5.5"),
            tts_enabled=env_bool("TTS_ENABLED", True),
            tts_provider=tts_provider,
            tts_api_key=env_text("TTS_API_KEY", os.getenv("OPENAI_API_KEY", "")),
            tts_base_url=tts_base_url,
            tts_model=tts_model,
            tts_voice_zh=os.getenv("TTS_VOICE_ZH", default_tts_voice_zh),
            tts_voice_ja=os.getenv("TTS_VOICE_JA", default_tts_voice_ja),
            tts_response_format=env_text("TTS_RESPONSE_FORMAT", "mp3" if tts_provider == "minimax" else "wav"),
            tts_sample_rate=env_int("TTS_SAMPLE_RATE", 32000),
            tts_bitrate=env_int("TTS_BITRATE", 128000),
            tts_speed=env_float("TTS_SPEED", 1.0),
            tts_volume=env_float("TTS_VOLUME", 1.0),
            tts_pitch=env_int("TTS_PITCH", 0),
            include_screen_by_default=env_bool("INCLUDE_SCREEN_BY_DEFAULT", True),
            max_history_turns=int(os.getenv("MASCOT_MAX_HISTORY_TURNS", "8")),
            request_timeout=int(os.getenv("MASCOT_REQUEST_TIMEOUT", "60")),
            screen_detail=os.getenv("MASCOT_SCREEN_DETAIL", "low"),
            auto_observe_enabled=env_bool("AUTO_OBSERVE_ENABLED", True),
            auto_observe_interval_seconds=max(10, int(os.getenv("AUTO_OBSERVE_INTERVAL_SECONDS", "60"))),
            system_prompt=os.getenv("MASCOT_SYSTEM_PROMPT", default_prompt),
            language=normalize_language(os.getenv("MASCOT_LANGUAGE", "zh")),
        )


class ScreenCapture:
    @staticmethod
    def capture_jpeg_base64(max_side: int = 1280, quality: int = 78) -> str:
        image = ImageGrab.grab(all_screens=True)
        image = image.convert("RGB")
        width, height = image.size
        largest = max(width, height)
        if largest > max_side:
            scale = max_side / largest
            image = image.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(output.getvalue()).decode("ascii")


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
        on_error: Callable[[], None] | None = None,
    ) -> bool:
        text = tts_friendly_text(text)
        if not self.enabled or not self.api_key or not text:
            return False
        threading.Thread(
            target=self._speak_worker,
            args=(text, self.language, on_play_start, on_error),
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
        on_error: Callable[[], None] | None,
    ) -> None:
        audio_path: Path | None = None
        try:
            audio_path = self._request_audio(text, language)
            self._play_audio(audio_path, on_play_start)
        except Exception:
            if on_error:
                on_error()
            return
        finally:
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
                "若い成人女性の自然な声で、親しみやすく軽い会話のように読んでください。"
                if language == "ja"
                else "用年轻成年女性的自然口吻朗读，声音清亮、有亲近感，像日常聊天。"
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


class LLMClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.language = config.language
        self.history: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def set_language(self, language: str) -> None:
        self.language = language

    def ask(self, user_text: str, include_screen: bool) -> str:
        return self._request(user_text, include_screen, remember=True, temperature=0.7, max_tokens=120)

    def observe(self) -> str:
        prompt = observe_prompt(self.language)
        return self._request(prompt, include_screen=True, remember=True, temperature=0.9, max_tokens=80)

    def _request(
        self,
        user_text: str,
        include_screen: bool,
        remember: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        if not self.config.api_key:
            return (
                "还没有配置 OPENAI_API_KEY。请复制 .env.example 为 .env，"
                "填入你的 API key 和模型名后重新启动桌宠。"
            )

        with self._lock:
            try:
                messages = self._build_messages(user_text, include_screen)
            except Exception as exc:
                return f"读取当前屏幕失败：{exc}"

            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                f"{self.config.base_url}/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            try:
                with urlopen(request, timeout=self.config.request_timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                return f"API 请求失败：HTTP {exc.code}\n{body[:800]}"
            except URLError as exc:
                return f"API 连接失败：{exc.reason}"
            except TimeoutError:
                return "API 请求超时了。"
            except Exception as exc:
                return f"调用模型时出错：{exc}"

            try:
                reply = result["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                return f"API 返回格式无法识别：{json.dumps(result, ensure_ascii=False)[:800]}"

            reply = clean_model_reply(reply)
            if remember:
                self._remember(user_text, reply)
            return reply

    def _build_messages(self, user_text: str, include_screen: bool) -> list[dict]:
        prompt = self.config.system_prompt + "\n" + language_instruction(self.language)
        messages: list[dict] = [{"role": "system", "content": prompt}]
        for item in self.history[-self.config.max_history_turns * 2 :]:
            messages.append(item)

        if include_screen:
            screenshot = ScreenCapture.capture_jpeg_base64()
            content = [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{screenshot}",
                        "detail": self.config.screen_detail,
                    },
                },
            ]
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_text})
        return messages

    def _remember(self, user_text: str, reply: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})


class AutoObserver:
    def __init__(self, root: tk.Tk, llm: LLMClient, chat: "ChatWindow", tts: AITTS, config: AppConfig) -> None:
        self.root = root
        self.llm = llm
        self.chat = chat
        self.tts = tts
        self.config = config
        self._running = False
        self._inflight = False
        self._manual_cooldown_until = 0.0

    def start(self) -> None:
        self._running = True
        self.root.after(5000, self._tick)

    def stop(self) -> None:
        self._running = False

    def block_after_manual_reply(self, seconds: float = 5.0) -> None:
        self._manual_cooldown_until = max(self._manual_cooldown_until, time.time() + seconds)

    def _tick(self) -> None:
        if not self._running:
            return

        in_manual_cooldown = time.time() < self._manual_cooldown_until
        if self.chat.auto_var.get() and self.config.api_key and not self._inflight and not in_manual_cooldown:
            self._inflight = True
            self.chat.status_var.set("自动观察中...")
            threading.Thread(target=self._observe_worker, daemon=True).start()
        elif in_manual_cooldown:
            self.chat.status_var.set("刚聊完，跳过这次自动观察")

        self.root.after(self.config.auto_observe_interval_seconds * 1000, self._tick)

    def _observe_worker(self) -> None:
        started = time.time()
        reply = self.llm.observe()
        elapsed = time.time() - started
        self.root.after(0, lambda: self._finish(reply, elapsed))

    def _finish(self, reply: str, elapsed: float) -> None:
        self._inflight = False
        if reply:
            self.chat.receive_auto_reply(reply, elapsed)
        else:
            self.chat.status_var.set("自动观察完成")


class ChatWindow(tk.Toplevel):
    def __init__(self, master: tk.Tk, llm: LLMClient, tts: AITTS, config: AppConfig) -> None:
        super().__init__(master)
        self.llm = llm
        self.tts = tts
        self.config = config
        self._busy = False
        self.auto_observer: AutoObserver | None = None
        self.language = config.language

        self.title("桌宠聊天")
        self.geometry("460x600")
        self.minsize(380, 480)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self._build_ui()
        self.withdraw()

    def _build_ui(self) -> None:
        self.configure(bg="#ece7dc")
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top = tk.Frame(self, bg="#ece7dc")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        top.grid_columnconfigure(2, weight=1)

        self.status_var = tk.StringVar(value="就绪")
        self.screen_var = tk.BooleanVar(value=self.config.include_screen_by_default)
        screen_check = TogglePill(top, "带当前屏幕", self.screen_var, lambda: None)
        screen_check.grid(row=0, column=0, sticky="w")

        self.auto_var = tk.BooleanVar(value=self.config.auto_observe_enabled)
        self.auto_toggle = TogglePill(top, "自动观察", self.auto_var, self._toggle_auto_observe)
        self.auto_toggle.grid(row=0, column=1, sticky="w", padx=(12, 0))

        clear_btn = PillButton(
            top,
            text="清空",
            command=self.clear_history,
            width=64,
            height=32,
            bg="#ffffff",
            hover_bg="#f5ead7",
            fg="#3b332b",
        )
        clear_btn.grid(row=0, column=3, sticky="e")

        status = tk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            bg="#ece7dc",
            fg="#6a6258",
            font=("Microsoft YaHei UI", 9),
        )
        status.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))

        chat_shell = tk.Frame(self, bg="#faf7f0")
        chat_shell.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        chat_shell.grid_rowconfigure(0, weight=1)
        chat_shell.grid_columnconfigure(0, weight=1)

        self.chat_canvas = tk.Canvas(chat_shell, bg="#faf7f0", highlightthickness=0, borderwidth=0)
        self.chat_canvas.grid(row=0, column=0, sticky="nsew")
        self.chat_scrollbar = tk.Scrollbar(chat_shell, orient="vertical", command=self.chat_canvas.yview)
        self.chat_scrollbar.grid(row=0, column=1, sticky="ns")
        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)

        self.messages_frame = tk.Frame(self.chat_canvas, bg="#faf7f0")
        self.messages_window = self.chat_canvas.create_window((0, 0), window=self.messages_frame, anchor="nw")
        self.messages_frame.bind("<Configure>", self._update_chat_scroll_region)
        self.chat_canvas.bind("<Configure>", self._resize_messages_frame)
        chat_shell.bind("<Enter>", self._bind_chat_mousewheel)
        chat_shell.bind("<Leave>", self._unbind_chat_mousewheel)
        self.chat_canvas.bind("<Enter>", self._bind_chat_mousewheel)
        self.messages_frame.bind("<Enter>", self._bind_chat_mousewheel)

        bottom = tk.Frame(self, bg="#ece7dc")
        bottom.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 12))
        bottom.grid_columnconfigure(0, weight=1)

        self.input_box = tk.Text(
            bottom,
            height=2,
            wrap="word",
            font=("Microsoft YaHei UI", 10),
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=4,
            bg="#fffdf8",
            fg="#241f1a",
            insertbackground="#241f1a",
        )
        self.input_box.grid(row=0, column=0, sticky="ew")
        self.input_box.bind("<Return>", self._handle_enter)
        self.input_box.bind("<Shift-Return>", self._handle_shift_enter)
        self.input_box.bind("<Control-Return>", self._handle_enter)

        self.send_btn = PillButton(
            bottom,
            text="发送",
            command=self.send_message,
            width=76,
            height=40,
            bg="#4f7a45",
            hover_bg="#416a38",
            fg="#ffffff",
            disabled_bg="#8c8a82",
        )
        self.send_btn.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._append("桌宠", welcome_message(self.language))

    def _update_chat_scroll_region(self, _event: tk.Event | None = None) -> None:
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

    def _resize_messages_frame(self, event: tk.Event) -> None:
        self.chat_canvas.itemconfigure(self.messages_window, width=event.width)

    def _on_chat_mousewheel(self, event: tk.Event) -> None:
        delta = -1 if event.delta > 0 else 1
        self.chat_canvas.yview_scroll(delta * 3, "units")
        return "break"

    def _bind_chat_mousewheel(self, _event: tk.Event) -> None:
        self.chat_canvas.bind_all("<MouseWheel>", self._on_chat_mousewheel)

    def _unbind_chat_mousewheel(self, _event: tk.Event) -> None:
        self.chat_canvas.unbind_all("<MouseWheel>")

    def show(self) -> None:
        self.deiconify()
        show_in_windows_taskbar(self)
        self.lift()
        self.input_box.focus_set()

    def clear_history(self) -> None:
        self.llm.history.clear()
        for child in self.messages_frame.winfo_children():
            child.destroy()
        self._append("系统", context_cleared_message(self.language))

    def _toggle_auto_observe(self) -> None:
        enabled = self.auto_var.get()
        self.master.event_generate("<<AutoObserveChanged>>", when="tail")
        self.status_var.set("自动观察已开启" if enabled else "自动观察已关闭")
        self.auto_toggle._draw()

    def _handle_enter(self, _event: tk.Event) -> str:
        self.send_message()
        return "break"

    def _handle_shift_enter(self, _event: tk.Event) -> str:
        self.input_box.insert("insert", "\n")
        return "break"

    def send_message(self) -> None:
        if self._busy:
            return
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            return

        self.input_box.delete("1.0", "end")
        include_screen = self.screen_var.get()
        self._append("你", text)
        self.status_var.set("正在截图并调用模型..." if include_screen else "正在调用模型...")
        self._set_busy(True)
        threading.Thread(target=self._ask_worker, args=(text, include_screen), daemon=True).start()

    def _ask_worker(self, text: str, include_screen: bool) -> None:
        started = time.time()
        reply = self.llm.ask(text, include_screen)
        elapsed = time.time() - started
        self.after(0, lambda: self._receive_reply(reply, elapsed))

    def _receive_reply(self, reply: str, elapsed: float) -> None:
        self._set_busy(False)
        self.status_var.set(f"语音生成中，上次请求 {elapsed:.1f}s")
        if self.auto_observer:
            self.auto_observer.block_after_manual_reply(5.0)
        self._speak_then_append(reply, lambda: self.status_var.set(f"就绪，上次请求 {elapsed:.1f}s"))

    def receive_auto_reply(self, reply: str, elapsed: float) -> None:
        self.status_var.set(f"自动观察语音生成中 {elapsed:.1f}s")
        self._speak_then_append(reply, lambda: self.status_var.set(f"自动观察完成 {elapsed:.1f}s"))

    def _speak_then_append(self, reply: str, on_visible: Callable[[], None] | None = None) -> None:
        shown = threading.Event()

        def show_reply() -> None:
            if shown.is_set():
                return
            shown.set()
            self.after(0, lambda: self._append_reply_and_update(reply, on_visible))

        if not self.tts.speak(reply, on_play_start=show_reply, on_error=show_reply):
            show_reply()

    def _append_reply_and_update(self, reply: str, on_visible: Callable[[], None] | None) -> None:
        self._append("桌宠", reply)
        if on_visible:
            on_visible()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.send_btn.set_text("思考中" if busy else "发送")
        self.send_btn.set_enabled(not busy)

    def _append(self, speaker: str, text: str) -> None:
        if speaker == "你":
            align = "right"
            bubble_bg = "#fff0cf"
            fg = "#2b251c"
        elif speaker == "系统":
            align = "left"
            bubble_bg = "#eee7dc"
            fg = "#4e463c"
        else:
            align = "left"
            bubble_bg = "#ffffff"
            fg = "#1f2a1d"

        row = tk.Frame(self.messages_frame, bg="#faf7f0")
        row.pack(fill="x", padx=6, pady=(2, 5))
        row.grid_columnconfigure(0, weight=1)
        bubble = ChatBubble(row, speaker, text, align, bubble_bg, fg, self._on_chat_mousewheel)
        bubble.grid(row=0, column=0, sticky="e" if align == "right" else "w")
        self.after_idle(self._update_chat_scroll_region)


class MascotWindow:
    def __init__(self, root: tk.Tk, chat: ChatWindow, tts: AITTS) -> None:
        self.root = root
        self.chat = chat
        self.tts = tts
        self.drag_start: tuple[int, int] | None = None
        self.click_start: tuple[int, int] | None = None
        self.mood = 0

        self.transparent = "#00ff01"
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", self.transparent)
        root.configure(bg=self.transparent)
        root.geometry("150x170+80+300")

        self.canvas = tk.Canvas(root, width=150, height=170, bg=self.transparent, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", self._show_menu)

        self.menu: RoundedPopupMenu | None = None

        self._draw()
        self._animate()

    def _draw(self) -> None:
        self.canvas.delete("all")
        bob = 4 if self.mood % 2 else 0

        self.canvas.create_oval(33, 36 + bob, 117, 126 + bob, fill="#ffd66b", outline="#6f4b16", width=3)
        self.canvas.create_oval(24, 72 + bob, 48, 102 + bob, fill="#ffbf55", outline="#6f4b16", width=2)
        self.canvas.create_oval(102, 72 + bob, 126, 102 + bob, fill="#ffbf55", outline="#6f4b16", width=2)
        self.canvas.create_oval(47, 65 + bob, 67, 85 + bob, fill="#ffffff", outline="#6f4b16", width=2)
        self.canvas.create_oval(83, 65 + bob, 103, 85 + bob, fill="#ffffff", outline="#6f4b16", width=2)
        self.canvas.create_oval(56, 72 + bob, 63, 80 + bob, fill="#222222", outline="")
        self.canvas.create_oval(92, 72 + bob, 99, 80 + bob, fill="#222222", outline="")
        self.canvas.create_arc(58, 83 + bob, 94, 108 + bob, start=200, extent=140, style="arc", outline="#6f4b16", width=3)
        self.canvas.create_oval(43, 90 + bob, 57, 101 + bob, fill="#ff9c8a", outline="")
        self.canvas.create_oval(93, 90 + bob, 107, 101 + bob, fill="#ff9c8a", outline="")

        self.canvas.create_line(51, 45 + bob, 43, 22 + bob, fill="#6f4b16", width=3)
        self.canvas.create_oval(35, 13 + bob, 50, 28 + bob, fill="#7dd3fc", outline="#25637a", width=2)
        self.canvas.create_line(99, 45 + bob, 107, 22 + bob, fill="#6f4b16", width=3)
        self.canvas.create_oval(100, 13 + bob, 115, 28 + bob, fill="#7dd3fc", outline="#25637a", width=2)
        self.canvas.create_oval(52, 124 + bob, 98, 154 + bob, fill="#8bd17c", outline="#356326", width=3)
        self.canvas.create_text(75, 143 + bob, text="AI", fill="#1f3b19", font=("Segoe UI", 12, "bold"))

    def _animate(self) -> None:
        self.mood += 1
        self._draw()
        self.root.after(650, self._animate)

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root, event.y_root)
        self.click_start = (event.x_root, event.y_root)

    def _drag(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        old_x, old_y = self.drag_start
        dx = event.x_root - old_x
        dy = event.y_root - old_y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self.drag_start = (event.x_root, event.y_root)

    def _release(self, event: tk.Event) -> None:
        if not self.click_start:
            return
        dx = abs(event.x_root - self.click_start[0])
        dy = abs(event.y_root - self.click_start[1])
        if dx < 5 and dy < 5:
            self.chat.show()
        self.drag_start = None
        self.click_start = None

    def _show_menu(self, event: tk.Event) -> None:
        self.menu = RoundedPopupMenu(
            self.root,
            [
                ("打开聊天", self.chat.show),
                (self._auto_menu_label(), self._toggle_auto_observe),
                ("停止朗读", self.tts.stop),
                (None, None),
                ("退出桌宠", self.root.destroy),
            ],
        )
        self.menu.show(event.x_root, event.y_root)

    def _toggle_auto_observe(self) -> None:
        self.chat.auto_var.set(not self.chat.auto_var.get())
        self.chat._toggle_auto_observe()

    def _auto_menu_label(self) -> str:
        return "关闭自动观察" if self.chat.auto_var.get() else "开启自动观察"


def main() -> int:
    set_windows_app_id()
    config = AppConfig.from_env()
    print(
        "DesktopMascot config: "
        f"chat_model={config.model}, "
        f"tts_provider={config.tts_provider}, "
        f"tts_model={config.tts_model}, "
        f"tts_voice={config.tts_voice_ja if config.language == 'ja' else config.tts_voice_zh}",
        flush=True,
    )
    root = tk.Tk()
    root.title("Desktop Mascot")

    tts = AITTS(config, config.language)
    llm = LLMClient(config)
    chat = ChatWindow(root, llm, tts, config)
    mascot = MascotWindow(root, chat, tts)
    observer = AutoObserver(root, llm, chat, tts, config)
    chat.auto_observer = observer
    observer.start()
    if "--open-chat" in sys.argv:
        root.after(500, chat.show)

    def handle_error(exc: Exception) -> None:
        messagebox.showerror("桌宠错误", str(exc))

    root.report_callback_exception = lambda _t, exc, _tb: handle_error(exc)
    root.mainloop()
    observer.stop()
    tts.stop()
    _ = mascot
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
