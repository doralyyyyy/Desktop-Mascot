# Desktop Mascot

Windows desktop mascot prototype. It can chat, screenshot your current screen for a multimodal model, speak replies with AI TTS, and automatically observe your desktop on a loop.

## Run

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python desktop_mascot.py
```

In `.env`, set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and a model that supports image input.

## Build EXE

Install PyInstaller:

```powershell
python -m pip install pyinstaller
```

Build with the checked-in spec file:

```powershell
python -m PyInstaller --clean --noconfirm desktop_mascot.spec
```

Run the packaged app:

```powershell
dist\desktop_mascot.exe
```

Use the spec file instead of only running a long `pyinstaller` command. The current build intentionally does not set a custom icon, so Tk/PyInstaller use their default window icon.

For MiniMax TTS, set:

```text
TTS_PROVIDER=minimax
TTS_BASE_URL=https://api.minimax.io/v1
TTS_MODEL=speech-2.8-turbo
TTS_VOICE_ZH=Chinese (Mandarin)_Crisp_Girl
TTS_VOICE_JA=Japanese_GracefulMaiden
```

If you use a relay service, point `TTS_BASE_URL` at its MiniMax-compatible base path. For example, Yunwu's MiniMax route is `https://yunwu.ai/minimax/v1`.

## Controls

- Left click the mascot: open chat.
- Drag the mascot: move it.
- Right click the mascot: open menu.
- `Enter`: send.
- `Shift+Enter`: new line.
- The chat window checkbox `自动观察` enables or disables the screenshot loop.

## Auto Observe

`AUTO_OBSERVE_ENABLED=true` starts the loop when the mascot starts.

`AUTO_OBSERVE_INTERVAL_SECONDS=60` controls the interval. Lower it if you want the mascot to comment more often.

The mascot only replies with one short spoken sentence by default. You can adjust the style with `MASCOT_SYSTEM_PROMPT`.
