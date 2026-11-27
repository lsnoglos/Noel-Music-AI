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
        self.winfo_toplevel().bind("<MouseWheel>", self.wheel, add="+")

    def wheel(self, event):
        widget = event.widget
        # Only scroll the pane containing the pointer; preserve editable text/listbox scrolling.
        if isinstance(widget, (tk.Text, tk.Listbox, ttk.Combobox)):
            return
        while widget is not None:
            if widget is self:
                self.canvas.yview_scroll(-int(event.delta/120), "units")
                return "break"
            widget = getattr(widget, "master", None)


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


class PianoLoader(tk.Canvas):
    """Silent five-key activity animation. The sweep is not an inference percentage."""
    def __init__(self,parent):
        super().__init__(parent,width=116,height=35,highlightthickness=0,bg="#13172b")
        self.timer=None
        self.phase=0
        self.white=[]
        self.black=[]
        for i in range(5):
            x=2+23*i
            self.white.append(self.create_rectangle(x,2,x+21,33,fill="#f1edf9",outline="#706489"))
        for i in (0,1,3):
            x=17+23*i
            self.black.append((i+.7,self.create_rectangle(x,2,x+12,21,fill="#28223c",outline="#7762ab")))
    def tick(self):
        self.timer=None
        position=self.phase if self.phase<=4 else 8-self.phase
        for i,key in enumerate(self.white):
            self.itemconfigure(key,fill="#f05ab6" if abs(i-position)<.6 else "#cbb9ee" if abs(i-position)<1.5 else "#f1edf9")
        for i,key in self.black:
            self.itemconfigure(key,fill="#8f408e" if abs(i-position)<.8 else "#28223c")
        self.phase=(self.phase+.5)%8
        self.timer=self.after(100,self.tick)
    def start(self):
        if self.timer is None:
            self.phase=0
            self.tick()
    def stop(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer=None
        self.phase=0


def instrument_icon(name, master):
    """Original tiny instrument-family drawings, no icon files or emoji fonts required."""
    try:
        from PIL import Image, ImageDraw, ImageTk
    except ImportError:
        return None
    im=Image.new("RGBA",(40,40))
    d=ImageDraw.Draw(im)
    pink="#ec50b3"; purple="#8670dd"; blue="#2dc8cf"; gold="#eab14f"; white="#f7edff"
    if name in ("Guitarra acústica","Guitarra eléctrica","Requinto","Bajo","Violín","Violonchelo"):
        d.ellipse((4,17,25,37),fill=pink)
        d.ellipse((13,13,29,29),fill=pink)
        d.line((19,23,34,6),fill=gold,width=5)
        d.line((17,23,35,4),fill=white,width=1)
        d.ellipse((14,22,20,28),fill="#32244a")
    elif name in ("Piano","Órgano","Sintetizador","Marimba","Acordeón"):
        d.rounded_rectangle((3,9,37,32),radius=3,fill=purple)
        for i in range(5):
            x=5+i*6
            d.rectangle((x,12,x+4,29),fill=white)
        for i in (0,1,3):
            x=8+i*6
            d.rectangle((x,12,x+3,22),fill="#32244a")
    elif name in ("Batería","Bongó","Congas","Güira","Maracas"):
        d.rounded_rectangle((7,13,33,35),radius=3,fill=blue)
        d.ellipse((7,7,33,20),fill=gold,outline=white,width=2)
        d.line((12,19,26,34),fill=white,width=2)
        d.line((26,19,13,34),fill=white,width=2)
    elif name=="Arpa":
        d.line((9,33,18,5,32,33,9,33),fill=gold,width=4,joint="curve")
        for x in (15,19,23,27):
            d.line((x,32,x,10+abs(19-x)),fill=white,width=2)
    else:
        d.line((7,10,25,10,25,28,12,28),fill=gold,width=5,joint="curve")
        d.polygon(((5,4),(17,10),(5,16)),fill=gold)
        for x in (18,23,28):
            d.ellipse((x,7,x+3,10),fill=white)
    return ImageTk.PhotoImage(im.resize((15,15),Image.Resampling.LANCZOS),master=master)
