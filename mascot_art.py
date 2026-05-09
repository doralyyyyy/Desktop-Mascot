import tkinter as tk


def draw_mascot(canvas: tk.Canvas, mood: int) -> None:
    canvas.delete("all")
    bob = 4 if mood % 2 else 0

    canvas.create_oval(33, 36 + bob, 117, 126 + bob, fill="#ffd66b", outline="#6f4b16", width=3)
    canvas.create_oval(24, 72 + bob, 48, 102 + bob, fill="#ffbf55", outline="#6f4b16", width=2)
    canvas.create_oval(102, 72 + bob, 126, 102 + bob, fill="#ffbf55", outline="#6f4b16", width=2)
    canvas.create_oval(47, 65 + bob, 67, 85 + bob, fill="#ffffff", outline="#6f4b16", width=2)
    canvas.create_oval(83, 65 + bob, 103, 85 + bob, fill="#ffffff", outline="#6f4b16", width=2)
    canvas.create_oval(56, 72 + bob, 63, 80 + bob, fill="#222222", outline="")
    canvas.create_oval(92, 72 + bob, 99, 80 + bob, fill="#222222", outline="")
    canvas.create_arc(58, 83 + bob, 94, 108 + bob, start=200, extent=140, style="arc", outline="#6f4b16", width=3)
    canvas.create_oval(43, 90 + bob, 57, 101 + bob, fill="#ff9c8a", outline="")
    canvas.create_oval(93, 90 + bob, 107, 101 + bob, fill="#ff9c8a", outline="")

    canvas.create_line(51, 45 + bob, 43, 22 + bob, fill="#6f4b16", width=3)
    canvas.create_oval(35, 13 + bob, 50, 28 + bob, fill="#7dd3fc", outline="#25637a", width=2)
    canvas.create_line(99, 45 + bob, 107, 22 + bob, fill="#6f4b16", width=3)
    canvas.create_oval(100, 13 + bob, 115, 28 + bob, fill="#7dd3fc", outline="#25637a", width=2)
    canvas.create_oval(52, 124 + bob, 98, 154 + bob, fill="#8bd17c", outline="#356326", width=3)
    canvas.create_text(75, 143 + bob, text="AI", fill="#1f3b19", font=("Segoe UI", 12, "bold"))
