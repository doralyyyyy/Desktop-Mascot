def normalize_language(value: str) -> str:
    value = value.strip().lower()
    if value in {"ja", "jp", "japanese", "日本語", "日语"}:
        return "ja"
    return "zh"


def language_instruction(language: str) -> str:
    if language == "ja":
        return (
            "重要：接下来的桌宠回复只能使用日语。"
            "每次只说一句自然的日语口语，六十文字以内，不要 Markdown。"
            "数字必须写成日语里容易朗读的汉字或假名，比如「百三十七」或「ひゃくさんじゅうなな」，不要输出阿拉伯数字。"
            "除非是必须保留的文件名或专有名词，否则不要输出英文缩写、代码符号或半角符号。"
            "使用自然口语标点，方便文字转语音在正确位置停顿。"
        )
    return "重要：接下来的桌宠回复只能使用中文。每次只说一句自然的中文口语，最多二十五个字，不要 Markdown，使用自然口语标点。"


def observe_prompt(language: str) -> str:
    if language == "ja":
        return (
            "これは自動で見えたユーザーの現在の画面です。"
            "画面にデスクトップ上の Live2D マスコットが写っていたら、それはあなた自身です。見た目や位置や動きを話題にせず、画面内の別キャラクターとして扱わないでください。"
            "画面全体をまとめるより、小さな文字、通知、ファイル名、隅の変化、カーソル付近など具体的な細部を一つ拾って、雑談か軽いツッコミを一言だけ言ってください。"
            "スクリーンショットを見ていることは説明せず、Markdown は使わないでください。"
        )
    return (
        "这是你自动看到的用户当前屏幕。"
        "如果屏幕里出现桌面上的 Live2D 桌宠角色，那就是你自己，不要围绕她的外观、位置或动作吐槽，也不要把她当成屏幕里的第三方角色来介绍。"
        "不要总是概括整个屏幕，优先留意一个具体细节，比如小字、通知、文件名、角落里的变化或当前光标附近的内容。"
        "根据这个细节主动闲聊或吐槽一句。"
        "只说一句中文，不要解释你在截图，不要 Markdown，使用自然口语标点。"
    )


def welcome_message(language: str) -> str:
    if language == "ja":
        return "画面を見ながら雑談するね。自動観察はいつでも切れるよ。"
    return "我会看屏幕陪你闲聊，自动观察可以随时关。"


def context_cleared_message(language: str) -> str:
    if language == "ja":
        return "コンテキストをクリアしたよ。"
    return "上下文已清空。"
