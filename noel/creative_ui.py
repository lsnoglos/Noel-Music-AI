"""Small Tk widgets: scrollable panels, gradient artwork and delayed help."""
import tkinter as tk
from tkinter import ttk


class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#13172b")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas, padding=3)
        self.item = self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.item, width=e.width))
        self.canvas.bind("<MouseWheel>", self.wheel)
        self.inner.bind("<MouseWheel>", self.wheel)

    def wheel(self, event):
        self.canvas.yview_scroll(-int(event.delta/120), "units")


def tooltip(widget, text, delay=3000):
    state = {"timer": None, "window": None}
    def hide(_=None):
        if state["timer"] is not None:
            widget.after_cancel(state["timer"])
            state["timer"] = None
        if state["window"] is not None:
            state["window"].destroy()
            state["window"] = None
    def show():
        state["timer"] = None
        if not widget.winfo_exists():
            return
        tip = tk.Toplevel(widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        label = tk.Label(tip, text=text, bg="#38265d", fg="white", padx=12, pady=9,
                         wraplength=300, justify="left", font=("Segoe UI",10))
        label.pack()
        tip.update_idletasks()
        x = min(widget.winfo_rootx(), widget.winfo_screenwidth()-tip.winfo_reqwidth()-8)
        y = widget.winfo_rooty()+widget.winfo_height()+5
        if y+tip.winfo_reqheight() > widget.winfo_screenheight():
            y = widget.winfo_rooty()-tip.winfo_reqheight()-5
        tip.geometry(f"+{max(0,x)}+{max(0,y)}")
        state["window"] = tip
    def enter(_):
        hide()
        state["timer"] = widget.after(delay, show)
    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<Destroy>", hide, add="+")
    widget.bind("<ButtonPress>", hide, add="+")


def gradient(canvas, width, height, start, end, title, subtitle, play=False):
    canvas.delete("all")
    a = tuple(int(start[i:i+2],16) for i in (1,3,5))
    b = tuple(int(end[i:i+2],16) for i in (1,3,5))
    for x in range(0,width,4):
        t = x/max(1,width-1)
        color = "#"+"".join(f"{round(v+(w-v)*t):02x}" for v,w in zip(a,b))
        canvas.create_rectangle(x,0,x+4,height,fill=color,outline="")
    if play:
        canvas.create_oval(width-55, height/2-19, width-17, height/2+19, fill="#ffffff", outline="")
        canvas.create_polygon(width-41,height/2-9,width-41,height/2+9,width-26,height/2,fill=start,outline="")
    canvas.create_text(12, height/2-12, anchor="w", text=title, fill="white", width=max(60,width-(72 if play else 24)),
                       font=("Segoe UI",14 if play else 20,"bold"))
    canvas.create_text(12, height-13, anchor="w", text=subtitle, fill="#fff1fb", font=("Segoe UI",10))
