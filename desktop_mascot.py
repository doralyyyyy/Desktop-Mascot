import ctypes
import platform
import signal
import sys
import threading
import time
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

from config import AppConfig, RESOURCE_DIR
from live2d_mascot import Live2DMascotWindow, live2d_runtime_available, run_live2d_child
from llm_client import LLMClient
from mascot_art import draw_mascot
from prompts import context_cleared_message, welcome_message
from tts import AITTS
from ui_widgets import ChatBubble, PillButton, RoundedPopupMenu, TogglePill


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
        self.root.after(10000, self._tick)

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

        def start_talking() -> None:
            self.after(0, self._notify_talk_start)
            show_reply()

        if not self.tts.speak(
            reply,
            on_play_start=start_talking,
            on_play_end=lambda: self.after(0, self._notify_talk_stop),
            on_error=show_reply,
        ):
            show_reply()

    def _notify_talk_start(self) -> None:
        self.master.event_generate("<<MascotTalkStart>>", when="tail")

    def _notify_talk_stop(self) -> None:
        self.master.event_generate("<<MascotTalkStop>>", when="tail")

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
        self.gif_frames: list[tk.PhotoImage] = []
        self.gif_frame_index = 0
        self.gif_frame_delay_ms = 120

        self.transparent = "#00ff01"
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", self.transparent)
        root.configure(bg=self.transparent)

        self.canvas = tk.Canvas(root, width=150, height=170, bg=self.transparent, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", self._show_menu)

        self.menu: RoundedPopupMenu | None = None

        self._position_near_bottom_right()
        self._load_gif_frames()
        self._draw()
        self._animate()

    def _position_near_bottom_right(self) -> None:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, screen_width - 150 - 120)
        y = max(0, screen_height - 170 - 80)
        self.root.geometry(f"150x170+{x}+{y}")

    def _load_gif_frames(self) -> None:
        path = RESOURCE_DIR / "assets" / "mascot.gif"
        frames: list[tk.PhotoImage] = []
        index = 0
        while True:
            try:
                frames.append(tk.PhotoImage(file=str(path), format=f"gif -index {index}"))
            except tk.TclError:
                break
            index += 1
        self.gif_frames = frames

    def _draw(self) -> None:
        if not self.gif_frames:
            draw_mascot(self.canvas, self.mood)
            return

        self.canvas.delete("all")
        frame = self.gif_frames[self.gif_frame_index]
        self.canvas.create_image(75, 85, image=frame, anchor="center")

    def _animate(self) -> None:
        self.mood += 1
        if self.gif_frames:
            self.gif_frame_index = (self.gif_frame_index + 1) % len(self.gif_frames)
        self._draw()
        delay = self.gif_frame_delay_ms if self.gif_frames else 650
        self.root.after(delay, self._animate)

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
    if "--live2d-child" in sys.argv:
        return run_live2d_child(sys.argv[1:])

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
    use_live2d = live2d_runtime_available()
    if use_live2d:
        root.withdraw()

    tts = AITTS(config, config.language)
    llm = LLMClient(config)
    chat = ChatWindow(root, llm, tts, config)
    mascot: MascotWindow | Live2DMascotWindow
    if use_live2d:
        try:
            mascot = Live2DMascotWindow(root, chat, tts)
        except Exception as exc:
            print(f"Live2D mascot unavailable, falling back to canvas mascot: {exc}", flush=True)
            root.deiconify()
            mascot = MascotWindow(root, chat, tts)
    else:
        mascot = MascotWindow(root, chat, tts)
    observer = AutoObserver(root, llm, chat, tts, config)
    chat.auto_observer = observer
    observer.start()
    if "--open-chat" in sys.argv:
        root.after(500, chat.show)

    def handle_error(exc: Exception) -> None:
        messagebox.showerror("桌宠错误", str(exc))

    def request_shutdown(_signum: int, _frame: object) -> None:
        try:
            root.after(0, root.quit)
        except tk.TclError:
            pass

    previous_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, request_shutdown)

    root.report_callback_exception = lambda _t, exc, _tb: handle_error(exc)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.quit()
    finally:
        signal.signal(signal.SIGINT, previous_sigint_handler)
        observer.stop()
        tts.stop()
        if isinstance(mascot, Live2DMascotWindow):
            mascot.destroy()
    _ = mascot
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
