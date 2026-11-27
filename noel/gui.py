"""Windows desktop studio. Network and engine operations run outside Tk's event loop."""
import json
import secrets
from contextlib import contextmanager
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .__main__ import ROOT, RUNTIME
from .diagnostics import PeakMonitor, snapshot
from .player import Player, envelope, spectrum
from .engine import Engine
from .distribution import available, binary_path, install_engine
from .models import MODELS, OPTIONAL, catalog, matches
from .presets import VOICES, MOODS, AMBIENCES, STRUCTURES, caption as build_caption, lyric_prompt
from .ui_theme import create_style
from .studio import render, write_json


class Studio:
    def __init__(self, window):
        self.player = Player()
        self.w = window
        window.title("Noel Music AI")
        window.geometry("1180x820")
        window.minsize(820, 650)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = self.closing = False
        self.proc = None
        self.playing_file = None
        RUNTIME.mkdir(exist_ok=True)
        self.config = RUNTIME / "studio.json"
        self.paths = json.loads(self.config.read_text("utf-8")) if self.config.exists() else {}
        self.models = Path(self.paths.get("models", RUNTIME / "models"))
        self.runs = Path(self.paths.get("runs", ROOT / "runs"))
        self.status = tk.StringVar(value="Preparado")
        self.style, self.modern = create_style(window, ROOT, RUNTIME)
        self.theme("Oscuro")
        body = ttk.Frame(window, padding=12)
        body.pack(fill="both", expand=True)
        sidebar = ttk.Frame(body, padding=(8, 8, 16, 8))
        sidebar.pack(side="left", fill="y")
        ttk.Label(sidebar, text="♫  Noel Music AI", font=("Segoe UI", 18, "bold")).pack(pady=(10, 24))
        ttk.Label(sidebar, text="ESTUDIO LOCAL", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))
        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.panels = {name: ttk.Frame(content, padding=12) for name in ("Inicio", "Crear música", "Modelos", "Configuración")}
        for name, panel in self.panels.items():
            panel.grid(row=0, column=0, sticky="nsew")
            ttk.Button(sidebar, text=name, command=lambda n=name: self.show_page(n)).pack(fill="x", pady=4)
        home, create, setup, settings = self.panels.values()
        ttk.Label(home, text="Tu estudio musical", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(home, text="Últimas canciones · selecciona una para escucharla o exportarla.").pack(anchor="w", pady=8)
        self.home_history = self.make_history(home)
        self.home_notice = ttk.Button(home, text="Configurar componentes faltantes", command=lambda: self.show_page("Modelos"))
        self.home_notice.pack(anchor="w", pady=8)
        ttk.Label(create, text="Crear música", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        split = ttk.Frame(create)
        split.pack(fill="both", expand=True, pady=8)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)
        form = ttk.Frame(split, padding=(0, 0, 12, 0))
        form.grid(row=0, column=0, sticky="nsew")
        results = ttk.Frame(split, padding=(12, 0))
        results.grid(row=0, column=1, sticky="nsew")
        self.title = ttk.Entry(form)
        self.field_label(form, "Título", "Nombre visible en tu biblioteca.")
        self.title.pack(fill="x")
        self.genres = json.loads(Path(__file__).with_name("genres.json").read_text("utf-8"))
        options = ttk.Frame(form)
        options.pack(fill="x", pady=6)
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        left, right = ttk.Frame(options), ttk.Frame(options)
        left.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        right.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.genre = self.combo(left, "Género", list(self.genres), "Instrumentos y patrón musical.")
        self.voice = self.combo(right, "Voz", list(VOICES), "Preferencia vocal. El motor generativo puede desviarse; instrumental elimina la letra.")
        self.mood = self.combo(left, "Emoción", list(MOODS), "Carácter emocional de la interpretación.")
        self.setting = self.combo(right, "Ambiente", list(AMBIENCES), "Atmósfera y producción de la canción.")
        self.field_label(form, "Estilo musical", "Detalles adicionales: instrumentos, ritmo, timbre o producción. Puedes dejarlo vacío.")
        self.prompt = ttk.Entry(form)
        self.prompt.pack(fill="x")
        lyricbar = ttk.Frame(form)
        lyricbar.pack(fill="x", pady=(10, 4))
        ttk.Label(lyricbar, text="Letra", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.help(lyricbar, "Escribe o pega la letra. Vacía = instrumental. Usa etiquetas [Verse], [Chorus].")
        ttk.Button(lyricbar, text="✦ Crear letra con IA", command=self.lyric_dialog).pack(side="right")
        self.lyrics = tk.Text(form, height=7, wrap="word", font=("Segoe UI", 11), relief="flat")
        self.lyrics.pack(fill="both", expand=True)
        self.duration = tk.IntVar(value=120)
        durations = ttk.Frame(form)
        durations.pack(fill="x", pady=(6, 0))
        self.field_label(durations, "Duración (segundos)", "De 15 a 300 segundos. Las canciones largas requieren más memoria; prueba primero 15 segundos.")
        ttk.Scale(durations, from_=15, to=300, variable=self.duration, command=lambda v: self.duration_label.configure(text=self.format_time(int(float(v))*1000))).pack(side="left", fill="x", expand=True)
        self.duration_label = ttk.Label(durations, text="2:00", width=6)
        self.duration_label.pack(side="right")
        self.model_choice = self.combo(form, "Modelo / calidad", ["Turbo Q8 · rápido (8 pasos)", "SFT Q8 · experimental (50 pasos)"], "Turbo conserva el perfil probado. SFT es opcional y puede tardar más; calidad y memoria aún sin benchmark.")
        self.generate_button = ttk.Button(form, text="Generar canción", command=self.generate)
        self.generate_button.pack(fill="x", pady=8)
        ttk.Label(results, text="Tus generaciones", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.latest = ttk.Label(results, text="Aquí aparecerá la canción generada.", wraplength=270)
        self.latest.pack(anchor="w", pady=8)
        self.create_history = self.make_history(results)
        ttk.Label(setup, text="Modelos musicales", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(setup, text="Los tres componentes básicos son necesarios. Los demás son opcionales.", wraplength=650).pack(anchor="w", pady=8)
        ttk.Button(setup, text="Instalar / verificar paquete básico", command=lambda: self.install(list(MODELS))).pack(anchor="w", pady=8)
        self.model_states = {}
        descriptions = {"embedding":"Interpreta las instrucciones · necesario", "dit":"Generación rápida · necesario",
                        "vae":"Decodificación de audio · necesario", "lm":"Compositor de letras local · opcional",
                        "sft":"Generación alternativa · opcional / experimental"}
        for key, (name, size, _) in catalog().items():
            row = ttk.Frame(setup, padding=8)
            row.pack(fill="x", pady=3)
            detail = ttk.Frame(row)
            detail.pack(side="left", fill="x", expand=True)
            ttk.Label(detail, text=name, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            state = ttk.Label(detail, text="Comprobando…")
            state.pack(anchor="w")
            self.model_states[key] = state
            self.help(row, descriptions[key])
            ttk.Button(row, text="Descargar / verificar", command=lambda k=key: self.install([k])).pack(side="right")
        ttk.Label(settings, text="Configuración", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        self.button(settings, "Alternar tema claro / oscuro", lambda: self.theme("Claro" if self.dark else "Oscuro"))
        self.button(settings, "Cambiar carpeta de modelos", lambda: self.folder("models"))
        self.button(settings, "Cambiar carpeta de canciones", lambda: self.folder("runs"))
        self.button(settings, "Instalar / reparar motor Windows", self.find_release)
        self.button(settings, "Comprobar componentes (diagnóstico)", self.inspect)
        self.button(settings, "Guardar informe de diagnóstico", self.report)
        self.observed = ttk.Label(settings, wraplength=680)
        self.observed.pack(anchor="w", pady=12)
        self.operation = ttk.Frame(window, padding=(16, 4))
        self.operation.pack(fill="x")
        ttk.Label(self.operation, textvariable=self.status, wraplength=800).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(self.operation, mode="indeterminate", length=180)
        self.cancel_button = ttk.Button(self.operation, text="Cancelar", command=self.cancel.set)
        player = ttk.Frame(window, padding=(16, 6))
        player.pack(fill="x")
        self.now_playing = ttk.Label(player, text="Selecciona una canción", font=("Segoe UI", 11, "bold"))
        self.now_playing.pack(anchor="w")
        visual = ttk.Frame(player)
        visual.pack(fill="x")
        self.waveform = tk.Canvas(visual, height=38, bg="#19212e", highlightthickness=0)
        self.waveform.pack(side="left", fill="x", expand=True)
        self.spectrum = tk.Canvas(visual, height=38, width=160, bg="#19212e", highlightthickness=0)
        self.spectrum.pack(side="right")
        self.position = ttk.Scale(player, from_=0, to=1, value=0)
        self.position.pack(fill="x")
        self.scrubbing = False
        self.position.bind("<ButtonPress-1>", lambda _: setattr(self, "scrubbing", True))
        self.position.bind("<ButtonRelease-1>", self.finish_seek)
        controls = ttk.Frame(player)
        controls.pack(fill="x")
        for text, fn in [("◀◀", lambda: self.next_song(-1)), ("−10 s", lambda: self.skip(-10000)),
                         ("▶", self.play), ("Ⅱ", self.pause), ("■", self.player.close),
                         ("+10 s", lambda: self.skip(10000)), ("▶▶", lambda: self.next_song(1))]:
            ttk.Button(controls, text=text, command=fn).pack(side="left", padx=2)
        self.clock = ttk.Label(controls, text="0:00 / 0:00")
        self.clock.pack(side="left", padx=8)
        self.volume = ttk.Scale(controls, from_=0, to=1000, command=self.volume_changed, length=100)
        self.volume.set(800)
        self.volume.pack(side="right")
        ttk.Label(controls, text="Volumen").pack(side="right")
        self.show_page("Inicio")
        self.theme("Oscuro")
        self.library()
        window.protocol("WM_DELETE_WINDOW", self.close)
        self.inspect()
        window.after(150, self.poll)

    def help(self, parent, explanation):
        ttk.Button(parent, text="ⓘ", width=3, command=lambda: messagebox.showinfo("Ayuda", explanation)).pack(side="left", padx=3)

    def field_label(self, parent, text, explanation):
        row = ttk.Frame(parent)
        row.pack(fill="x", anchor="w", pady=(4, 0))
        ttk.Label(row, text=text).pack(side="left")
        self.help(row, explanation)

    def make_history(self, parent):
        box = ttk.Frame(parent)
        box.pack(fill="both", expand=True)
        listing = tk.Listbox(box, height=6, font=("Segoe UI", 11), relief="flat", exportselection=False)
        scroll = ttk.Scrollbar(box, command=listing.yview)
        listing.configure(yscrollcommand=scroll.set)
        listing.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        listing.bind("<Double-Button-1>", lambda _: self.play())
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=6)
        for name, fn in [("Reproducir", self.play), ("Descargar WAV", self.export), ("Favorita", lambda: self.edit_song(True))]:
            ttk.Button(row, text=name, command=fn).pack(side="left", padx=2)
        row2 = ttk.Frame(parent)
        row2.pack(fill="x")
        for name, fn in [("Renombrar", lambda: self.edit_song(False)), ("Abrir carpeta", self.open_folder)]:
            ttk.Button(row2, text=name, command=fn).pack(side="left", padx=2)
        return listing

    def show_page(self, name):
        self.page = name
        self.panels[name].tkraise()
        if name in ("Inicio", "Crear música"):
            self.history = self.home_history if name == "Inicio" else self.create_history

    @staticmethod
    def format_time(ms):
        seconds = max(0, int(ms) // 1000)
        return f"{seconds//60}:{seconds%60:02d}"

    def finish_seek(self, _):
        self.scrubbing = False
        self.seek(int(self.position.get()))

    def seek(self, ms):
        if self.player.opened:
            try:
                self.player.seek(ms)
            except OSError as exc:
                messagebox.showerror("Reproducción", str(exc))

    def skip(self, delta):
        if self.player.opened:
            self.seek(int(self.player.send("status noelplayer position")) + delta)

    def next_song(self, delta):
        if self.files:
            index = self.files.index(self.playing_file) if self.playing_file in self.files else 0
            index = (index + delta) % len(self.files)
            self.history.selection_clear(0, "end")
            self.history.selection_set(index)
            self.history.see(index)
            self.play()

    def theme(self, name):
        self.dark = name == "Oscuro"
        bg, fg = ("#19212e", "#eef2ff") if self.dark else ("#f3f5fa", "#182233")
        if self.modern:
            self.style.theme_use("darkly" if self.dark else "flatly")
        else:
            self.style.theme_use("clam")
            self.style.configure(".", background=bg, foreground=fg, fieldbackground=bg, font=("Segoe UI", 10))
            self.style.map("TCombobox", fieldbackground=[("readonly", bg)], foreground=[("readonly", fg)])
            self.style.map("TButton", background=[("active", "#485a79")])
        self.w.configure(background=bg)
        for widget in (getattr(self, "lyrics", None), getattr(self, "home_history", None), getattr(self, "create_history", None)):
            if widget is not None:
                widget.configure(background=bg, foreground=fg, selectbackground="#7761be", selectforeground="white")
        if hasattr(self, "lyrics"):
            self.lyrics.configure(insertbackground=fg)

    def find_release(self):
        def lookup():
            self.events.put(("release", available()))
        self.run(lookup)

    def combo(self, parent, label, values, explanation=""):
        self.field_label(parent, label, explanation)
        field = ttk.Combobox(parent, values=values, state="readonly")
        field.current(0)
        field.pack(fill="x", anchor="w")
        return field

    def button(self, parent, label, action):
        ttk.Button(parent, text=label, command=action).pack(anchor="w", pady=3, padx=3)

    def run(self, function, action="Operación", download=False):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.start_time = time.monotonic()
        self.stage = action
        self.action = action
        self.progress.configure(mode="determinate" if download else "indeterminate", value=0, maximum=100)
        self.progress.pack(side="right", padx=6)
        if not download:
            self.progress.start(12)
        self.cancel_button.configure(text="Cancelar descarga" if download else "Cancelar " + action.lower())
        self.cancel_button.pack(side="right")
        def work():
            try:
                self.events.put(("done", function() or "Finalizado"))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind, text = self.events.get()
            if kind == "release":
                asset = text
                self.w.after(200, lambda: self.confirm_install(asset))
            elif kind == "stage":
                self.stage = text
            elif kind == "inventory":
                report, inventory, missing = text
                self.observed.configure(text=report)
                for key, state in inventory.items():
                    self.model_states[key].configure(text=state)
                if missing:
                    self.home_notice.pack(anchor="w", pady=8)
                else:
                    self.home_notice.pack_forget()
            elif kind == "model":
                key, state = text
                self.model_states[key].configure(text=state)
            elif kind == "progress":
                label, n, total = text
                self.stage = label
                self.progress.configure(mode="determinate", value=100*n/max(total, 1))
            elif kind == "lyrics":
                self.lyrics.delete("1.0", "end")
                self.lyrics.insert("1.0", text)
            elif kind == "song":
                self.latest.configure(text=text)
                self.show_page("Crear música")
            else:
                self.busy = False
                self.progress.stop()
                self.progress.pack_forget()
                self.cancel_button.pack_forget()
                self.status.set(text)
                if kind == "error" and not self.closing:
                    messagebox.showerror("Noel Music AI", text)
                self.library()
        if self.player.opened:
            try:
                position = int(self.player.send("status noelplayer position"))
                duration = int(self.player.send("status noelplayer length"))
                self.position.configure(to=max(1, duration))
                if not self.scrubbing:
                    self.position.set(position)
                self.clock.configure(text=f"{self.format_time(position)} / {self.format_time(duration)}")
                self.spectrum.delete("all")
                if self.playing_file:
                    for i, level in enumerate(spectrum(self.playing_file, position)):
                        self.spectrum.create_rectangle(i*10+1, 38-36*level, i*10+8, 38, fill="#53d4c0", outline="")
            except (OSError, ValueError):
                pass
        if self.closing and not self.busy:
            self.w.destroy()
            return
        if self.busy:
            self.status.set(f"{self.stage} · {int(time.monotonic()-self.start_time)} s")
        self.w.after(200, self.poll)

    def confirm_install(self, asset):
        if not self.closing and messagebox.askyesno("Instalar motor", f"Descargar {asset['name']} desde GitHub ({asset['size']/1e6:.1f} MB) e instalar el motor?"):
            self.run(lambda: install_engine(ROOT, asset, self.cancel, lambda n,total: self.events.put(("progress", (f"Motor · {n/1e6:.1f}/{total/1e6:.1f} MB", n, total)))), "Instalación del motor", download=True)

    def close(self):
        self.player.close()
        self.closing = True
        self.cancel.set()

    def folder(self, key):
        if self.busy:
            return
        path = filedialog.askdirectory()
        if path:
            self.paths[key] = path
            setattr(self, key, Path(path))
            write_json(self.config, self.paths)
            self.library()
            self.inspect()

    def library(self):
        selected = self.files[self.history.curselection()[0]] if getattr(self, "files", None) and self.history.curselection() else None
        for listing in (self.home_history, self.create_history):
            listing.delete(0, "end")
        self.files = []
        for manifest in sorted(self.runs.glob("*/version.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(manifest.read_text("utf-8"))
                wav = manifest.with_name("song.wav")
                if wav.exists():
                    title_file = manifest.with_name("display.json")
                    if title_file.exists():
                        display = json.loads(title_file.read_text("utf-8"))
                        data["request"]["caption"] = ("★ " if display.get("favorite") else "") + display.get("title", data["request"]["caption"])
                    for listing in (self.home_history, self.create_history):
                        listing.insert("end", f"{data['request']['caption']} · {data['metrics']['actual_seconds']:.1f} s")
                    self.files.append(wav)
            except (OSError, ValueError, KeyError):
                continue
        if self.files:
            index = self.files.index(selected) if selected in self.files else 0
            for listing in (self.home_history, self.create_history):
                listing.selection_set(index)

    def play(self):
        if self.history.curselection():
            wav = self.files[self.history.curselection()[0]]
            try:
                self.player.open(wav)
                self.playing_file = wav
                self.now_playing.configure(text=self.history.get(self.history.curselection()[0]))
                self.volume_changed(self.volume.get())
                peaks = envelope(wav)
                self.waveform.delete("all")
                width = self.waveform.winfo_width() / len(peaks)
                for i, peak in enumerate(peaks):
                    self.waveform.create_line(i*width, 27-25*peak, i*width, 28+25*peak, fill="#53d4c0")
            except OSError as error:
                messagebox.showerror("Reproducción", str(error))

    def edit_song(self, favorite):
        if self.history.curselection():
            f = self.files[self.history.curselection()[0]].with_name("display.json")
            data = json.loads(f.read_text("utf-8")) if f.exists() else {}
            if favorite:
                data["favorite"] = not data.get("favorite", False)
            else:
                title = simpledialog.askstring("Renombrar", "Título de la canción")
                if not title:
                    return
                data["title"] = title
            write_json(f, data)
            self.library()

    def open_folder(self):
        if self.history.curselection():
            os.startfile(self.files[self.history.curselection()[0]].parent)

    def pause(self):
        if self.player.opened:
            mode = self.player.send("status noelplayer mode")
            self.player.send(("pause" if mode == "playing" else "resume") + " noelplayer")

    def volume_changed(self, value):
        if self.player.opened:
            self.player.send(f"setaudio noelplayer volume to {int(float(value))}")

    def export(self):
        if self.history.curselection():
            dest = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("Audio WAV", "*.wav")])
            if dest:
                shutil.copyfile(self.files[self.history.curselection()[0]], dest)

    def report(self):
        dest = filedialog.asksaveasfilename(defaultextension=".json")
        if dest:
            self.run(lambda: write_json(Path(dest), snapshot()))

    def binary(self):
        return binary_path(ROOT)

    def inspect(self):
        def work():
            info = snapshot()
            gpu = info["gpu"] or {}
            rows = [f"{info['os']} {info['architecture']} · Python {sys.version.split()[0]}",
                    f"{gpu.get('name', 'GPU no detectada')} · controlador {gpu.get('driver','—')} · VRAM libre {gpu.get('free_mib','—')} MiB",
                    f"RAM libre: {(info['ram_available'] or 0)/2**30:.2f} GiB · Disco libre: {info['disk_free']/2**30:.1f} GiB",
                    f"Motor musical: {'presente' if self.binary().exists() else 'falta · descargue el paquete Windows de GitHub Actions'}"]
            inventory = {}
            missing = not self.binary().exists()
            for key, (name, size, digest) in catalog().items():
                ok = matches(self.models/name, size, digest)
                state = "Verificado" if ok else "No instalado / requiere reparación"
                inventory[key] = f"{state} · {size/1e6:.0f} MB · {'Necesario' if key in MODELS else 'Opcional'}"
                missing = missing or (key in MODELS and not ok)
                rows.append(f"{name} · {state}")
            self.events.put(("inventory", ("\n".join(rows), inventory, missing)))
        self.run(work)

    def install(self, keys):
        if self.busy or not keys:
            return
        total = sum(catalog()[k][1] for k in keys)
        if not messagebox.askyesno("Modelos seleccionados", f"Verificar y descargar desde Hugging Face los archivos faltantes o dañados (hasta {total/1e9:.2f} GB)?"):
            return
        def work():
            from .models import install
            install(self.models, True, keys, repair=True, cancel=self.cancel,
                    progress=lambda name, n, total: self.events.put(("progress", (f"{name} · {n/1e6:.1f} / {total/1e6:.1f} MB", n, total))))
            for key in keys:
                name, size, _ = catalog()[key]
                self.events.put(("model", (key, f"Verificado · {size/1e6:.0f} MB · {'Necesario' if key in MODELS else 'Opcional'}")))
            return "Modelos verificados"
        self.run(work, "Instalación de modelos", download=True)

    def musical_caption(self):
        return build_caption(self.genres[self.genre.get()], self.mood.get(), self.setting.get(),
                             self.voice.get(), self.prompt.get())

    @contextmanager
    def engine_session(self, optional=()):
        binary = self.binary()
        if not binary.is_file():
            raise ValueError("Falta el motor. Instálalo en Configuración.")
        from .runtime import verify_engine
        self.events.put(("stage", "Verificando componentes"))
        verify_engine(binary)
        gpu = snapshot()["gpu"]
        if not gpu:
            raise ValueError("No se detectó GPU NVIDIA. Consulta Configuración > Diagnóstico.")
        for key in [*MODELS, *optional]:
            name, size, digest = catalog()[key]
            if self.cancel.is_set():
                raise InterruptedError("Cancelado")
            if not matches(self.models/name, size, digest):
                raise ValueError(f"Instala o verifica {name} en Modelos.")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        args = [str(binary), "--device", "CUDA0", "--host", "127.0.0.1", "--port", str(port),
                "--models", str(self.models), "--max-batch", "1", "--vae-chunk",
                "128" if gpu["free_mib"] < 6000 else "256", "--vae-overlap", "32"]
        self.events.put(("stage", "Iniciando motor CUDA"))
        with (RUNTIME / "engine.log").open("w") as log:
            proc = subprocess.Popen(args, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                engine = Engine(port, self.cancel)
                for _ in range(200):
                    if proc.poll() is not None:
                        raise ValueError("El motor se cerró. Consulta .runtime/engine.log.")
                    if self.cancel.is_set():
                        raise InterruptedError("Cancelado")
                    try:
                        props = engine.ready()
                        break
                    except ConnectionError:
                        time.sleep(.2)
                else:
                    raise TimeoutError("El motor no respondió.")
                yield engine, props
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()

    def lyric_dialog(self):
        if self.busy:
            return
        if self.voice.get() == "Instrumental":
            messagebox.showinfo("Compositor", "Selecciona una voz para componer una letra.")
            return
        dialog = tk.Toplevel(self.w)
        dialog.title("Compositor de letras IA")
        dialog.transient(self.w)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        self.field_label(frame, "Tema de la canción", "Describe la historia, personas, lugares y sentimiento.")
        topic = tk.Text(frame, height=4, width=55, wrap="word")
        topic.pack(fill="x")
        structure = self.combo(frame, "Estructura", list(STRUCTURES), "Organización de versos y coros.")
        complexity = self.combo(frame, "Complejidad", ["Poética", "Sencilla y pegadiza", "Narrativa y profunda", "Divertida", "Romántica"], "Preferencia de escritura; el modelo puede desviarse.")
        self.field_label(frame, "Instrucciones adicionales", "Ejemplo: coro pegadizo y metáforas del mar.")
        extra = ttk.Entry(frame)
        extra.pack(fill="x")
        ttk.Label(frame, text="Requiere el modelo opcional ACE-Step LM 0.6B (~710 MB).").pack(anchor="w", pady=8)
        def submit():
            try:
                prompt = lyric_prompt(topic.get("1.0", "end"), self.musical_caption(), structure.get(), complexity.get(), extra.get())
            except ValueError as exc:
                messagebox.showerror("Compositor", str(exc), parent=dialog)
                return
            if self.lyrics.get("1.0", "end").strip() and not messagebox.askyesno("Compositor", "¿Reemplazar la letra actual si se genera correctamente?", parent=dialog):
                return
            seconds = self.duration.get()
            dialog.destroy()
            def work():
                with self.engine_session(("lm",)) as (engine, props):
                    if OPTIONAL["lm"][0] not in props["models"].get("lm", []):
                        raise ValueError("El servidor no reconoció el modelo de letras.")
                    self.events.put(("stage", "Componiendo letra"))
                    lyrics = engine.compose(dict(caption=prompt, vocal_language="es", duration=seconds,
                                                 lm_model=OPTIONAL["lm"][0], lm_mode="inspire", lm_batch_size=1))
                    self.events.put(("lyrics", lyrics))
                    return "Letra generada. Revísala antes de crear música."
            self.run(work, "Composición")
        ttk.Button(frame, text="Generar letra", command=submit).pack(fill="x", pady=8)

    def generate(self):
        if self.busy:
            return
        title = self.title.get().strip()
        caption = self.musical_caption()
        lyrics = self.lyrics.get("1.0", "end").strip()
        if self.voice.get() == "Instrumental" and lyrics:
            if not messagebox.askyesno("Instrumental", "La letra no se cantará. ¿Continuar?"):
                return
            lyrics = ""
        if self.voice.get() not in ("Automática", "Instrumental") and not lyrics:
            messagebox.showinfo("Letra", "Escribe una letra o usa el compositor IA para generar una canción con voz.")
            return
        seconds = max(15, min(300, self.duration.get()))
        model = "sft" if self.model_choice.current() == 1 else "dit"
        if seconds > 120 or model == "sft":
            if not messagebox.askyesno("Configuración experimental", "Esta duración o modelo aún no tiene benchmark en tu GPU. ¿Continuar?"):
                return
        seed = secrets.randbelow(2**31)
        def work():
            with self.engine_session(("sft",) if model == "sft" else ()) as (engine, props):
                self.events.put(("stage", "Generando música"))
                with PeakMonitor() as monitor:
                    result = render(engine, props, self.runs, caption, lyrics, seconds, seed, model)
                write_json(self.runs/result["version"]/"performance.json",
                           dict(peak_system_vram_mib=monitor.peak_gpu_mib, peak_system_ram_bytes=monitor.peak_ram_bytes,
                                total_seconds=result["total_s"], generated_seconds=result["actual_seconds"]))
                if title:
                    write_json(self.runs/result["version"]/"display.json", {"title": title})
                self.events.put(("song", f"{title or 'Nueva canción'} · {result['actual_seconds']:.0f} s · lista para escuchar"))
                return "Canción guardada · " + result["version"]
        self.run(work, "Generación")


if __name__ == "__main__":
    root = tk.Tk()
    Studio(root)
    root.mainloop()
