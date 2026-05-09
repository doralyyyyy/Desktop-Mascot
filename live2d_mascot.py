import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import tkinter as tk

from config import APP_DIR, RESOURCE_DIR
from tts import AITTS
from ui_widgets import RoundedPopupMenu


LIVE2D_WIDTH = 360
LIVE2D_HEIGHT = 430
ELECTRON_WIDTH = 520
ELECTRON_HEIGHT = 640
LIVE2D_MODEL_RELATIVE_PATH = "live2d/model/model.model3.json"


def live2d_runtime_available() -> bool:
    assets_dir = RESOURCE_DIR / "assets"
    runtime_index = assets_dir / "live2d_runtime" / "index.html"
    model_file = assets_dir / LIVE2D_MODEL_RELATIVE_PATH
    return runtime_index.exists() and model_file.exists() and (
        electron_runtime_available()
        or (
            importlib.util.find_spec("PySide6") is not None
            and importlib.util.find_spec("PySide6.QtWebEngineWidgets") is not None
        )
    )


def electron_runtime_available() -> bool:
    return _electron_command() is not None and (RESOURCE_DIR / "assets" / "live2d_electron" / "main.js").exists()


class Live2DMascotWindow:
    def __init__(self, root: tk.Tk, chat: object, tts: AITTS) -> None:
        self.root = root
        self.chat = chat
        self.tts = tts
        self.menu: RoundedPopupMenu | None = None
        self._control_url: str | None = None
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._process: subprocess.Popen[str] | None = None

        if not live2d_runtime_available():
            raise RuntimeError("Live2D runtime is not available")

        self._start_callback_server()
        try:
            self._start_child_process()
        except Exception:
            self.destroy()
            raise

    def destroy(self) -> None:
        if self.menu is not None:
            self.menu.close()
            self.menu = None

        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._server_thread = None

    def _start_callback_server(self) -> None:
        owner = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path != "/event":
                    self.send_error(404)
                    return

                query = parse_qs(parsed.query)
                event_type = query.get("type", [""])[0]
                x = _safe_int(query.get("x", ["0"])[0])
                y = _safe_int(query.get("y", ["0"])[0])
                owner.root.after(0, lambda: owner._handle_event(event_type, x, y))
                self.send_response(204)
                self.end_headers()

            def log_message(self, _format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

    def _start_child_process(self) -> None:
        if self._server is None:
            raise RuntimeError("Live2D callback server is not running")

        callback_url = f"http://127.0.0.1:{self._server.server_port}/event"
        assets_dir = RESOURCE_DIR / "assets"
        self._control_url = f"http://127.0.0.1:{_find_free_port()}/control"
        command = _electron_child_command(callback_url, self._control_url, assets_dir)
        if command is None:
            command = _child_command(callback_url, self._control_url, assets_dir)
        output_dir = APP_DIR / "output"
        output_dir.mkdir(exist_ok=True)
        log_file = open(output_dir / "live2d_child.log", "a", encoding="utf-8")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = os.environ.copy()
        if command and Path(command[0]).name.lower() == "electron.exe":
            control = urlparse(self._control_url)
            env.update(
                {
                    "LIVE2D_CALLBACK_URL": callback_url,
                    "LIVE2D_CONTROL_PORT": str(control.port or ""),
                    "LIVE2D_ASSETS_DIR": str(assets_dir),
                    "LIVE2D_WIDTH": str(ELECTRON_WIDTH),
                    "LIVE2D_HEIGHT": str(ELECTRON_HEIGHT),
                    "LIVE2D_LOG_PATH": str(output_dir / "live2d_electron.log"),
                }
            )
        try:
            self._process = subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creation_flags,
                env=env,
            )
        finally:
            log_file.close()

        try:
            exit_code = self._process.wait(timeout=0.8)
        except subprocess.TimeoutExpired:
            return
        raise RuntimeError(f"Live2D child process exited early with code {exit_code}")

    def _handle_event(self, event_type: str, x: int, y: int) -> None:
        if event_type == "click":
            return
        elif event_type == "contextmenu":
            self._show_menu(x, y)
        elif event_type == "quit":
            self.root.destroy()

    def play_tap_motion(self) -> None:
        self._send_control("tap")

    def play_idle_motion(self) -> None:
        self._send_control("idle")

    def _send_control(self, action: str) -> None:
        if not self._control_url:
            return

        def worker() -> None:
            query = urlencode({"action": action})
            deadline = time.time() + 2.0
            while time.time() < deadline:
                try:
                    urlopen(Request(f"{self._control_url}?{query}"), timeout=0.5).close()
                    return
                except OSError:
                    time.sleep(0.1)

        threading.Thread(target=worker, daemon=True).start()

    def _show_menu(self, x: int, y: int) -> None:
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
        self.menu.show(x, y)

    def _toggle_auto_observe(self) -> None:
        self.chat.auto_var.set(not self.chat.auto_var.get())
        self.chat._toggle_auto_observe()

    def _auto_menu_label(self) -> str:
        return "关闭自动观察" if self.chat.auto_var.get() else "开启自动观察"


def _child_command(callback_url: str, control_url: str, assets_dir: Path) -> list[str]:
    command = [sys.executable, str(APP_DIR / "desktop_mascot.py")]
    command.extend(
        [
            "--live2d-child",
            "--callback-url",
            callback_url,
            "--control-url",
            control_url,
            "--assets-dir",
            str(assets_dir),
            "--width",
            str(LIVE2D_WIDTH),
            "--height",
            str(LIVE2D_HEIGHT),
        ]
    )
    return command


def _electron_command() -> str | None:
    candidates = [
        APP_DIR / "node_modules" / "electron" / "dist" / "electron.exe",
        APP_DIR / "node_modules" / ".bin" / "electron.cmd",
        APP_DIR / "node_modules" / ".bin" / "electron",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("electron")


def _electron_child_command(callback_url: str, control_url: str, assets_dir: Path) -> list[str] | None:
    electron = _electron_command()
    if electron is None:
        return None

    control = urlparse(control_url)
    if control.port is None:
        return None

    return [
        electron,
        str(APP_DIR),
    ]


def _safe_int(value: str) -> int:
    try:
        return int(float(value))
    except ValueError:
        return 0


def _find_free_port() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    try:
        return server.server_port
    finally:
        server.server_close()


def run_live2d_child(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live2d-child", action="store_true")
    parser.add_argument("--callback-url", required=True)
    parser.add_argument("--control-url", required=True)
    parser.add_argument("--assets-dir", required=True)
    parser.add_argument("--width", type=int, default=LIVE2D_WIDTH)
    parser.add_argument("--height", type=int, default=LIVE2D_HEIGHT)
    args = parser.parse_args(argv)

    return _run_qt_live2d_window(
        callback_url=args.callback_url,
        control_url=args.control_url,
        assets_dir=Path(args.assets_dir),
        width=args.width,
        height=args.height,
    )


def _run_qt_live2d_window(
    callback_url: str,
    control_url: str,
    assets_dir: Path,
    width: int,
    height: int,
) -> int:
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl, Signal
    from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    static_server = _StaticAssetServer(assets_dir)
    static_server.start()
    control_server: _QtControlServer | None = None

    def send_event(event_type: str, x: int = 0, y: int = 0) -> None:
        def worker() -> None:
            query = urlencode({"type": event_type, "x": x, "y": y})
            try:
                urlopen(Request(f"{callback_url}?{query}"), timeout=1).close()
            except OSError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def global_pos(event: QMouseEvent) -> QPoint:
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()

    class MascotWebView(QWebEngineView):
        def __init__(self, owner: "Live2DQtWindow") -> None:
            super().__init__(owner)
            self.owner = owner
            self._press_global: QPoint | None = None
            self._press_window_pos: QPoint | None = None
            self._dragging = False

        def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            pos = event.globalPos()
            send_event("contextmenu", pos.x(), pos.y())
            event.accept()

        def mousePressEvent(self, event: QMouseEvent) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self._press_global = global_pos(event)
                self._press_window_pos = self.owner.pos()
                self._dragging = False
                event.accept()
                return
            if event.button() == Qt.MouseButton.RightButton:
                pos = global_pos(event)
                send_event("contextmenu", pos.x(), pos.y())
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event: QMouseEvent) -> None:
            if event.buttons() & Qt.MouseButton.LeftButton and self._press_global and self._press_window_pos:
                current = global_pos(event)
                delta = current - self._press_global
                if abs(delta.x()) + abs(delta.y()) >= 4:
                    self._dragging = True
                    self.owner.move(self._press_window_pos + delta)
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event: QMouseEvent) -> None:
            if event.button() == Qt.MouseButton.LeftButton and self._press_global:
                pos = global_pos(event)
                if not self._dragging:
                    self.owner.play_tap_motion()
                    send_event("click", pos.x(), pos.y())
                self._press_global = None
                self._press_window_pos = None
                self._dragging = False
                event.accept()
                return
            super().mouseReleaseEvent(event)

    class ControlBridge(QObject):
        tap_requested = Signal()
        idle_requested = Signal()

    class ConsolePage(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message: str, line_number: int, source_id: str) -> None:  # type: ignore[no-untyped-def]
            log_line = f"Live2D JS[{level}] {source_id}:{line_number}: {message}"
            encoding = sys.stdout.encoding or "utf-8"
            safe_line = log_line.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
            print(safe_line, flush=True)

    class Live2DQtWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Desktop Live2D Mascot")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
                | Qt.WindowType.NoDropShadowWindowHint
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setStyleSheet("background: transparent;")
            self.resize(width, height)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            self.view = MascotWebView(self)
            self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.view.setStyleSheet("background: transparent;")
            self.view.setPage(ConsolePage(self.view))
            self.view.page().setBackgroundColor(QColor(0, 0, 0, 0))
            settings = self.view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            self.view.loadFinished.connect(self._on_load_finished)
            layout.addWidget(self.view)

            self._position_near_bottom_right()
            model_url = f"/{LIVE2D_MODEL_RELATIVE_PATH}"
            url = f"{static_server.base_url}/live2d_runtime/index.html?model={model_url}"
            self.view.load(QUrl(url))

        def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            send_event("quit")
            event.accept()

        def play_tap_motion(self) -> None:
            self.view.page().runJavaScript("window.desktopMascot && window.desktopMascot.tap();")

        def play_idle_motion(self) -> None:
            self.view.page().runJavaScript("window.desktopMascot && window.desktopMascot.idle();")

        def _on_load_finished(self, ok: bool) -> None:
            if ok:
                send_event("ready")

        def _position_near_bottom_right(self) -> None:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                return
            rect = screen.availableGeometry()
            x = max(rect.x(), rect.x() + rect.width() - self.width() - 140)
            y = max(rect.y(), rect.y() + rect.height() - self.height() - 60)
            self.move(x, y)

    app = QApplication(sys.argv[:1])
    window = Live2DQtWindow()
    bridge = ControlBridge()
    bridge.tap_requested.connect(window.play_tap_motion)
    bridge.idle_requested.connect(window.play_idle_motion)
    control_server = _QtControlServer(control_url, bridge.tap_requested.emit, bridge.idle_requested.emit)
    control_server.start()
    window.show()
    try:
        return app.exec()
    finally:
        if control_server is not None:
            control_server.stop()
        static_server.stop()


class _StaticAssetServer:
    def __init__(self, assets_dir: Path) -> None:
        self.assets_dir = assets_dir
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url = ""

    def start(self) -> None:
        handler = partial(_NoCacheFileHandler, directory=str(self.assets_dir))
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._thread = None


class _NoCacheFileHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, _format: str, *args: object) -> None:
        return


def _disable_windows_rounded_corners(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        dwmwa_window_corner_preference = 33
        dwmwa_border_color = 34
        dwmwa_caption_color = 35
        dwmwa_text_color = 36
        dwmwcp_donotround = 1
        color_none = 0xFFFFFFFE
        value = ctypes.c_int(dwmwcp_donotround)
        color = ctypes.c_uint(color_none)
        dwmapi = ctypes.windll.dwmapi
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            dwmwa_window_corner_preference,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
        for attribute in (dwmwa_border_color, dwmwa_caption_color, dwmwa_text_color):
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(color),
                ctypes.sizeof(color),
            )
    except Exception as exc:
        print(f"Live2D DWM setup failed: {exc}", flush=True)


class _QtControlServer:
    def __init__(self, control_url: str, tap: Callable[[], None], idle: Callable[[], None]) -> None:
        self.control_url = urlparse(control_url)
        self.tap = tap
        self.idle = idle
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        host = self.control_url.hostname or "127.0.0.1"
        port = self.control_url.port
        if port is None:
            raise RuntimeError("Live2D control URL needs a port")
        owner = self

        class ControlHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path != owner.control_url.path:
                    self.send_error(404)
                    return
                action = parse_qs(parsed.query).get("action", [""])[0]
                if action == "tap":
                    owner.tap()
                elif action == "idle":
                    owner.idle()
                self.send_response(204)
                self.end_headers()

            def log_message(self, _format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer((host, port), ControlHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._thread = None
