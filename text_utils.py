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
    first_sentence = re.split(r"(?<=[。.!！?？])\s*", text, maxsplit=1)[0].strip()
    text = first_sentence or text
    if len(text) > 60:
        text = text[:60].rstrip() + "..."
    return text


def tts_friendly_text(text: str) -> str:
    text = clean_model_reply(text)
    text = re.sub(r"[#*_`~>\[\](){}<>|\\/@$%^&=+:;；：，,。.!！?？、…·\"'“”‘’《》【】]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
