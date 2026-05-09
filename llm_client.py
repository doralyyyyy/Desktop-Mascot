import json
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import AppConfig
from prompts import language_instruction, observe_prompt
from screen_capture import ScreenCapture
from text_utils import clean_model_reply


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
