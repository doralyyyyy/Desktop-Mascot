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
