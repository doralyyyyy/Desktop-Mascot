import os
from dataclasses import dataclass
from pathlib import Path

from prompts import normalize_language


APP_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = APP_DIR

ENV_FILE = APP_DIR / ".env"


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
            "如果截图里出现桌面上的 Live2D 桌宠角色，那就是你自己，不要围绕她的外观、位置或动作吐槽，也不要把她当成屏幕里的第三方角色来介绍。"
            "回复时优先抓住屏幕里的一个具体细节，而不是只总结整体画面。"
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
