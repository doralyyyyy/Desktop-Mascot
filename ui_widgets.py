import tkinter as tk
import tkinter.font as tkfont
from typing import Callable


class PillButton(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
        width: int,
        height: int = 32,
        bg: str = "#ffffff",
        hover_bg: str = "#f5ead7",
        fg: str = "#2f2a24",
        disabled_bg: str = "#b8b3aa",
    ) -> None:
        super().__init__(master, width=width, height=height, bg=master["bg"], highlightthickness=0)
        self.text = text
        self.command = command
        self.width = width
        self.height = height
        self.normal_bg = bg
        self.hover_bg = hover_bg
        self.disabled_bg = disabled_bg
        self.fg = fg
        self.enabled = True
        self.hover = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<Configure>", self._resize)
        self._draw()

    def set_text(self, text: str) -> None:
        self.text = text
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        fill = self.disabled_bg if not self.enabled else self.hover_bg if self.hover else self.normal_bg
        text_fill = "#ffffff" if fill in {"#4f7a45", "#416a38", "#8c8a82", "#b8b3aa"} else self.fg
        self._rounded_rect(1, 1, self.width - 1, self.height - 1, self.height // 2, fill=fill, outline="")
        self.create_text(
            self.width // 2,
            self.height // 2,
            text=self.text,
            fill=text_fill,
            font=("Microsoft YaHei UI", 10, "bold"),
        )

    def _enter(self, _event: tk.Event) -> None:
        self.hover = True
        self._draw()

    def _leave(self, _event: tk.Event) -> None:
        self.hover = False
        self._draw()

    def _click(self, _event: tk.Event) -> None:
        if self.enabled:
            self.command()

    def _resize(self, event: tk.Event) -> None:
        if event.width != self.width or event.height != self.height:
            self.width = max(1, event.width)
            self.height = max(1, event.height)
            self._draw()

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: object) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class TogglePill(tk.Canvas):
    def __init__(self, master: tk.Misc, text: str, variable: tk.BooleanVar, command: Callable[[], None]) -> None:
        super().__init__(master, width=118, height=32, bg=master["bg"], highlightthickness=0)
        self.text = text
        self.variable = variable
        self.command = command
        self.hover = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._click)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        active = self.variable.get()
        fill = "#e7f3df" if active else "#fffdf8"
        if self.hover:
            fill = "#dcefd2" if active else "#f5ead7"
        outline = "#9bc28d" if active else "#d7cfc1"
        self._rounded_rect(1, 1, 117, 31, 16, fill=fill, outline=outline)
        self.create_oval(10, 10, 22, 22, fill="#4f7a45" if active else "#b8b0a5", outline="")
        self.create_text(32, 16, text=self.text, anchor="w", fill="#2f2a24", font=("Microsoft YaHei UI", 9, "bold"))

    def _enter(self, _event: tk.Event) -> None:
        self.hover = True
        self._draw()

    def _leave(self, _event: tk.Event) -> None:
        self.hover = False
        self._draw()

    def _click(self, _event: tk.Event) -> None:
        self.variable.set(not self.variable.get())
        self.command()
        self._draw()

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: object) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class ChatBubble(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        speaker: str,
        text: str,
        align: str,
        bubble_bg: str,
        fg: str,
        wheel_handler: Callable[[tk.Event], str],
    ) -> None:
        super().__init__(master, bg=master["bg"])
        self.align = align
        self.bubble_bg = bubble_bg
        self.fg = fg
        self.wheel_handler = wheel_handler
        self.speaker = speaker
        self.text = text.strip()
        self.max_text_width = 360
        self.min_text_width = 110 if speaker == "系统" else 56
        self.font = tkfont.Font(family="Microsoft YaHei UI", size=10)
        self.line_px = self.font.metrics("linespace") + 6
        self.text_pad_x = 10
        self.text_pad_y = 6

        self.grid_columnconfigure(0, weight=1)
        side = "e" if align == "right" else "w"

        if speaker:
            label = tk.Label(
                self,
                text=speaker,
                bg=master["bg"],
                fg="#6a6258",
                font=("Microsoft YaHei UI", 9),
            )
            label.grid(row=0, column=0, sticky=side, padx=10, pady=(0, 2))

        self.canvas = tk.Canvas(self, bg=master["bg"], highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=1, column=0, sticky=side, padx=8)

        self.text_widget = tk.Text(
            self.canvas,
            wrap="word",
            font=self.font,
            bg=bubble_bg,
            fg=fg,
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=4,
            cursor="xterm",
            exportselection=True,
            insertwidth=0,
        )
        self.text_widget.insert("1.0", self.text)
        self.text_widget.configure(state="disabled")
        self.text_widget.bind("<Button-3>", self._copy_text)
        self.text_widget.bind("<MouseWheel>", self.wheel_handler)
        self.canvas.bind("<MouseWheel>", self.wheel_handler)
        self.bind("<MouseWheel>", self.wheel_handler)
        self.text_window = self.canvas.create_window(1, 1, anchor="nw", window=self.text_widget)
        self.after_idle(self._layout)

    def _layout(self) -> None:
        text_width, fallback_lines = self._measure_text()
        inner_width = max(1, text_width + self.text_pad_x * 2)

        # Lock pixel width first, then query actual wrapped display lines.
        self.text_widget.configure(width=1, height=max(1, fallback_lines))
        self.canvas.itemconfigure(self.text_window, width=inner_width)
        self.text_widget.update_idletasks()

        count_result = self.text_widget.count("1.0", "end-1c", "displaylines")
        display_lines = max(1, int(count_result[0])) if count_result else max(1, fallback_lines)
        self.text_widget.configure(height=display_lines)
        self.text_widget.update_idletasks()

        inner_height = max(1, self.text_widget.winfo_reqheight())
        bubble_width = inner_width + 2
        bubble_height = inner_height + 2
        self.canvas.configure(width=bubble_width, height=bubble_height, bg=self.master["bg"])
        self.canvas.itemconfigure(self.text_window, width=inner_width, height=inner_height)
        self.canvas.delete("bubble")
        self._rounded_rect(1, 1, bubble_width - 1, bubble_height - 1, 12, fill=self.bubble_bg, outline="")
        self.canvas.tag_lower("bubble")
        self.canvas.coords(self.text_window, 1, 1)

    def _measure_text(self) -> tuple[int, int]:
        logical_lines = self.text.splitlines() or [self.text]
        longest_px = max((self.font.measure(line) for line in logical_lines), default=1)
        text_width = min(max(longest_px + 2, self.min_text_width), self.max_text_width)
        display_lines = 0
        for line in logical_lines:
            display_lines += self._wrapped_line_count(line, text_width)
        return text_width, max(1, display_lines)

    def _wrapped_line_count(self, line: str, max_width: int) -> int:
        if not line:
            return 1
        lines = 1
        current = 0
        for char in line:
            char_width = max(1, self.font.measure(char))
            if current > 0 and current + char_width > max_width:
                lines += 1
                current = char_width
            else:
                current += char_width
        return lines

    def _copy_text(self, _event: tk.Event) -> str:
        self.clipboard_clear()
        self.clipboard_append(self.text)
        return "break"

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: object) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.canvas.create_polygon(points, smooth=True, splinesteps=24, tags="bubble", **kwargs)


class RoundedPopupMenu:
    def __init__(self, root: tk.Tk, items: list[tuple[str | None, Callable[[], None] | None]]) -> None:
        self.root = root
        self.items = items
        self.window: tk.Toplevel | None = None
        self.canvas: tk.Canvas | None = None
        self.hover_index: int | None = None
        self.width = 172
        self.item_height = 38
        self.separator_height = 10
        self.padding = 8
        self.radius = 14
        self.transparent = "#ff00fe"

    def show(self, x: int, y: int) -> None:
        self.close()
        height = self._menu_height()

        self.window = tk.Toplevel(self.root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-transparentcolor", self.transparent)
        self.window.configure(bg=self.transparent)
        self.window.geometry(f"{self.width}x{height}+{x}+{y}")
        self.window.bind("<FocusOut>", lambda _event: self.close())
        self.window.bind("<Escape>", lambda _event: self.close())

        self.canvas = tk.Canvas(
            self.window,
            width=self.width,
            height=height,
            bg=self.transparent,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<ButtonRelease-1>", self._on_click)

        self._draw()
        self.window.focus_force()

    def close(self) -> None:
        if self.window is not None:
            self.window.destroy()
        self.window = None
        self.canvas = None
        self.hover_index = None

    def _draw(self) -> None:
        if not self.canvas:
            return
        height = self._menu_height()
        self.canvas.delete("all")
        self._rounded_rect(1, 1, self.width - 1, height - 1, self.radius, fill="#fffdf8", outline="#d7cfc1")

        y = self.padding
        for index, (label, _command) in enumerate(self.items):
            if label is None:
                self.canvas.create_line(14, y + self.separator_height // 2, self.width - 14, y + self.separator_height // 2, fill="#e5dccf")
                y += self.separator_height
                continue
            y1 = y
            y2 = y1 + self.item_height
            if self.hover_index == index:
                self._rounded_rect(8, y1 + 3, self.width - 8, y2 - 3, 9, fill="#e7f3df", outline="")
            self.canvas.create_text(
                20,
                y1 + self.item_height // 2,
                text=label,
                anchor="w",
                fill="#2f2a24",
                font=("Microsoft YaHei UI", 10),
            )
            y += self.item_height

    def _on_motion(self, event: tk.Event) -> None:
        index = self._index_at(event.y)
        label = self.items[index][0] if index is not None else None
        next_hover = index if label is not None else None
        if next_hover != self.hover_index:
            self.hover_index = next_hover
            self._draw()

    def _on_leave(self, _event: tk.Event) -> None:
        if self.hover_index is not None:
            self.hover_index = None
            self._draw()

    def _on_click(self, event: tk.Event) -> None:
        index = self._index_at(event.y)
        if index is None:
            self.close()
            return
        label, command = self.items[index]
        self.close()
        if label is not None and command is not None:
            command()

    def _index_at(self, y: int) -> int | None:
        cursor = self.padding
        for index, (label, _command) in enumerate(self.items):
            row_height = self.separator_height if label is None else self.item_height
            if cursor <= y < cursor + row_height:
                return index
            cursor += row_height
        return None

    def _menu_height(self) -> int:
        content_height = 0
        for label, _command in self.items:
            content_height += self.separator_height if label is None else self.item_height
        return self.padding * 2 + content_height

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: object) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)



