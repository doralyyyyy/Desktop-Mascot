# Desktop Mascot

Windows desktop mascot prototype. It can chat, screenshot your current screen for a multimodal model, speak replies with AI TTS, and automatically observe your desktop on a loop.

The mascot display uses an Electron transparent window for Live2D, and falls back to the built-in Tk canvas drawing if Live2D cannot start. This repository does not include a Live2D model; put your own model files under `assets/live2d/model/` to enable the Live2D mascot.

## Run

```powershell
python -m pip install -r requirements.txt
npm install --registry=https://registry.npmmirror.com
Copy-Item .env.example .env
notepad .env
```

In `.env`, set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and a model that supports image input.

For TTS, set `TTS_PROVIDER`, `TTS_API_KEY`, `TTS_BASE_URL`, `TTS_MODEL`, `TTS_VOICE_ZH`, `TTS_VOICE_JA`.

```powershell
python desktop_mascot.py
```

## Live2D Model

The Live2D model directory is intentionally ignored by git because model files may have their own licenses and can be large. To use Live2D, place a Cubism 4 model here:

```text
assets/live2d/model/model.model3.json
```

The folder should also contain the files referenced by that `model3.json`, such as `.moc3`, textures, motions, expressions, physics, and pose files.

If the model is missing or Live2D fails to start, the app falls back to the built-in Tk canvas mascot.

## Controls

- Drag the mascot with left mouse: move it.
- Right click the mascot: open menu.
- Open chat from the mascot's right-click menu.
- `Enter`: send.
- `Shift+Enter`: new line.
- The chat window checkbox `自动观察` enables or disables the screenshot loop.

## Auto Observe

`AUTO_OBSERVE_ENABLED=true` starts the loop when the mascot starts.

`AUTO_OBSERVE_INTERVAL_SECONDS=30` controls the interval.

The mascot only replies with one short spoken sentence by default. You can adjust the style with `MASCOT_SYSTEM_PROMPT`.
