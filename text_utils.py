import re


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
    first_sentence = re.split(r"(?<=[。.])\s*", text, maxsplit=1)[0].strip()
    text = first_sentence or text
    if len(text) > 60:
        text = text[:60].rstrip() + "..."
    return text


def tts_friendly_text(text: str) -> str:
    text = clean_model_reply(text)
    text = re.sub(r"[#*_`~>\[\](){}<>|\\/@$%^&=+:;；：·\"'“”‘’《》【】]", " ", text)
    text = re.sub(r"\s*([，,、。.!！?？])\s*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def minimax_tts_text(text: str) -> str:
    text = tts_friendly_text(text)
    pauses = {
        "\u0001": "<#0.18#>",
        "\u0002": "<#0.35#>",
        "\u0003": "<#0.45#>",
    }
    pause_tokens = "".join(pauses)
    text = text.replace("……", "\u0003").replace("...", "\u0003")
    text = re.sub(r"[，,、]+", "\u0001", text)
    text = re.sub(r"[。.!！?？]+", "\u0002", text)
    text = re.sub(f"[{pause_tokens}]{{2,}}", "\u0002", text)
    text = re.sub(rf"^\s*[{pause_tokens}]+", "", text)
    text = re.sub(rf"[{pause_tokens}]+\s*$", "", text)
    for marker, pause in pauses.items():
        text = text.replace(marker, pause)
    return re.sub(r"\s+", " ", text).strip()
