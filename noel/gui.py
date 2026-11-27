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
from .presets import (VOICES, MOODS, AMBIENCES, STRUCTURES, LANGUAGES, INSTRUMENTS, SECTIONS,
                      INTENTIONS, COMPLEXITIES, caption as build_caption, lyric_prompt)
from .audio_export import export_audio
from .creative_ui import ScrollFrame, tooltip, gradient
from .ui_theme import create_style
from .studio import render, write_json


class Studio:
    def __init__(self, window):
        self.player = Player()
        self.w = window
        window.title("Noel Music AI")
        window.geometry("1180x820")
        window.minsize(900, 650)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = self.closing = False
        self.proc = None
        self.playing_file = None
        self.verified = {}
        self.new_version = None
        self.song_data = []
        self.model_buttons = {}
        self.composing = False
        RUNTIME.mkdir(exist_ok=True)
        self.config = RUNTIME / "studio.json"
        self.paths = json.loads(self.config.read_text("utf-8")) if self.config.exists() else {}
        self.models = Path(self.paths.get("models", RUNTIME / "models"))
        self.runs = Path(self.paths.get("runs", ROOT / "runs"))
        self.status = tk.StringVar(value="Preparado")
        self.style, self.modern = create_style(window, ROOT, RUNTIME)
        self.theme("Oscuro")
        # Grid reserves the footer independently of the central content's requested size.
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1, minsize=0)
        window.rowconfigure(1, weight=0)
        window.rowconfigure(2, weight=0)
        body = ttk.Frame(window, padding=12)
        body.grid(row=0, column=0, sticky="nsew")
        body.pack_propagate(False)
        sidebar = ttk.Frame(body, padding=(8, 8, 16, 8), style="Nav.TFrame")
        sidebar.pack(side="left", fill="y")
        ttk.Label(sidebar, text="♫  Noel Music AI", font=("Segoe UI", 18, "bold"), style="Nav.TLabel").pack(pady=(10, 24))
        ttk.Label(sidebar, text="ESTUDIO LOCAL", font=("Segoe UI", 9), style="Nav.TLabel").pack(anchor="w", pady=(0, 10))
        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.panels = {name: ttk.Frame(content, padding=12) for name in ("Inicio", "Crear música", "Modelos", "Configuración")}
        self.nav_buttons = {}
        for name, panel in self.panels.items():
            panel.grid(row=0, column=0, sticky="nsew")
            b = ttk.Button(sidebar, text=name, style="Nav.TButton", command=lambda n=name: self.show_page(n))
            b.pack(fill="x", pady=4)
            self.nav_buttons[name] = b
        home, create, setup, settings = self.panels.values()
        hero = tk.Canvas(home, height=94, highlightthickness=0)
        hero.pack(fill="x", pady=(0, 8))
        hero.bind("<Configure>", lambda e: gradient(hero, e.width, e.height, "#d60980", "#136fa3",
                                                     "Tu música, tu imaginación", "Cada canción comienza con una idea."))
        self.home_notice = ttk.Button(home, text="Configurar componentes faltantes", command=lambda: self.show_page("Modelos"))
        self.home_notice.pack(anchor="w", pady=4)
        ttk.Label(home, text="Tus creaciones", font=("Segoe UI", 19, "bold")).pack(anchor="w", pady=8)
        self.home_filter = tk.BooleanVar(value=False)
        ttk.Checkbutton(home, text="Solo favoritas", variable=self.home_filter, command=self.draw_cards).pack(anchor="w")
        self.home_scroll = ScrollFrame(home)
        self.home_scroll.pack(fill="both", expand=True)
        self.home_cards = self.home_scroll.inner
        self.card_columns = 2
        self.home_scroll.canvas.bind("<Configure>", self.resize_cards, add="+")
        self.home_history = tk.Listbox(home, exportselection=False)  # internal selection, not a visible list

        ttk.Label(create, text="Crear música", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        split = ttk.Frame(create)
        split.pack(fill="both", expand=True, pady=8)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)
        form_scroll = self.form_scroll = ScrollFrame(split)
        form_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form = form_scroll.inner
        self.results_container = ttk.Frame(split, padding=(8, 0))
        self.results_container.grid(row=0, column=1, sticky="nsew")
        results = ttk.Frame(self.results_container)
        results.pack(fill="both", expand=True)
        self.results = results
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
        self.voice = self.combo(right, "Voz", [v for v in VOICES if v != "Instrumental"], "Preferencia vocal. El modelo puede no respetarla exactamente.")
        self.mood = self.combo(left, "Emoción", list(MOODS), "Carácter emocional de la interpretación.")
        self.setting = self.combo(right, "Ambiente", list(AMBIENCES), "Atmósfera y producción de la canción.")
        self.instrumental = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Instrumental · solo pista, sin voz", variable=self.instrumental, command=self.toggle_instrumental).pack(anchor="w", pady=4)
        self.language = self.combo(form, "Idioma de la canción", list(LANGUAGES), "Indica el idioma de las palabras cantadas. La IA puede desviarse.")
        instrument_row = ttk.Frame(form)
        instrument_row.pack(fill="x", pady=4)
        self.instrument_label = ttk.Label(instrument_row, text="Instrumentos: Automático", wraplength=310)
        self.instrument_label.pack(side="left", fill="x", expand=True)
        self.help(instrument_row, "Elige varios instrumentos o deja que la IA decida. Son preferencias, no pistas aisladas.")
        ttk.Button(instrument_row, text="Elegir", command=self.toggle_instruments).pack(side="right")
        self.instrument_panel = ttk.Frame(form, padding=6)
        self.instrument_vars = {}
        for i, name in enumerate(INSTRUMENTS):
            var = tk.BooleanVar(value=False)
            self.instrument_vars[name] = var
            ttk.Checkbutton(self.instrument_panel, text=name, variable=var, command=self.update_instrument_label).grid(row=i//3, column=i%3, sticky="w", padx=3)
        ttk.Button(self.instrument_panel, text="Automático", command=self.clear_instruments).grid(row=7, column=0, sticky="w")
        ttk.Button(self.instrument_panel, text="Listo", command=self.toggle_instruments).grid(row=7, column=1, sticky="w")
        self.field_label(form, "Estilo musical", "Detalles adicionales: instrumentos, ritmo, timbre o producción. Puedes dejarlo vacío.")
        self.prompt = ttk.Entry(form)
        self.prompt.pack(fill="x")
        lyricbar = ttk.Frame(form)
        lyricbar.pack(fill="x", pady=(10, 4))
        ttk.Label(lyricbar, text="Letra", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.help(lyricbar, "Escribe o pega la letra. Vacía = instrumental. Usa etiquetas [Verse], [Chorus].")
        self.compose_cta = ttk.Button(lyricbar, text="✦ ¿Aún no tienes letra? Créala con IA", style="Accent.TButton", command=self.lyric_dialog)
        self.compose_cta.pack(side="right")
        self.lyrics = tk.Text(form, height=7, wrap="word", font=("Segoe UI", 11), relief="flat")
        self.lyrics.pack(fill="x")
        self.duration = tk.IntVar(value=120)
        durations = ttk.Frame(form)
        durations.pack(fill="x", pady=(6, 0))
        self.field_label(durations, "Duración (segundos)", "De 15 a 300 segundos. Las canciones largas requieren más memoria; prueba primero 15 segundos.")
        ttk.Scale(durations, from_=15, to=300, variable=self.duration, command=lambda v: self.duration_label.configure(text=self.format_time(int(float(v))*1000))).pack(side="left", fill="x", expand=True)
        self.duration_label = ttk.Label(durations, text="2:00", width=6)
        self.duration_label.pack(side="right")
        self.model_choice = self.combo(form, "Modelo / calidad", ["Turbo Q8 · rápido (8 pasos)", "SFT Q8 · experimental (50 pasos)"], "Turbo conserva el perfil probado. SFT es opcional y puede tardar más; calidad y memoria aún sin benchmark.")
        self.generate_button = ttk.Button(form, text="✦ Generar canción", style="Accent.TButton", command=self.generate)
        self.generate_button.pack(fill="x", pady=8)
        ttk.Label(results, text="Tus generaciones", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.latest = ttk.Label(results, text="Aquí aparecerá la canción generada.", wraplength=270)
        self.latest.pack(anchor="w", pady=8)
        self.create_history = self.make_history(results)
        self.build_composer(self.results_container)
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
            btn = ttk.Button(row, text="Comprobando…", command=lambda k=key: self.install([k]))
            btn.pack(side="right")
            self.model_buttons[key] = btn
        ttk.Label(settings, text="Configuración", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(settings, text="Tema moderno ttkbootstrap" if self.modern else "Tema básico · ttkbootstrap no disponible").pack(anchor="w", pady=4)
        self.button(settings, "Alternar tema claro / oscuro", lambda: self.theme("Claro" if self.dark else "Oscuro"))
        self.button(settings, "Cambiar carpeta de modelos", lambda: self.folder("models"))
        self.button(settings, "Cambiar carpeta de canciones", lambda: self.folder("runs"))
        ttk.Label(settings, text="Mantenimiento · solo si hay un problema", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(16, 4))
        self.setting_action(settings, "Reparar motor musical", "Descarga el motor CUDA compatible si falta o está dañado. No es necesario si ya generas música.", self.find_release)
        self.setting_action(settings, "Revisar estado del equipo y modelos", "Comprueba GPU, RAM, espacio y archivos. No descarga nada.", self.force_inspect)
        self.setting_action(settings, "Exportar informe para soporte", "Guarda un JSON técnico para compartir si surge un error. No contiene letras ni audios.", self.report)
        self.observed = ttk.Label(settings, wraplength=680)
        self.observed.pack(anchor="w", pady=12)
        self.operation = ttk.Frame(window, padding=(16, 4))
        self.operation.grid(row=1, column=0, sticky="ew")
        ttk.Label(self.operation, textvariable=self.status, wraplength=800).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(self.operation, mode="indeterminate", length=180)
        self.cancel_button = ttk.Button(self.operation, text="Cancelar", command=self.cancel.set)
        player = ttk.Frame(window, padding=(16, 6))
        player.grid(row=2, column=0, sticky="ew")
        self.player_frame = player
        self.now_playing = ttk.Label(player, text="Selecciona una canción", font=("Segoe UI", 11, "bold"))
        self.now_playing.pack(anchor="w")
        visual = ttk.Frame(player)
        visual.pack(fill="x")
        self.waveform = tk.Canvas(visual, height=30, bg="#19212e", highlightthickness=0)
        self.waveform.pack(side="left", fill="x", expand=True)
        self.spectrum = tk.Canvas(visual, height=30, width=160, bg="#19212e", highlightthickness=0)
        self.spectrum.pack(side="right")
        self.position = ttk.Scale(player, from_=0, to=1, value=0)
        self.position.pack(fill="x")
        self.scrubbing = False
        self.position.bind("<ButtonPress-1>", lambda _: setattr(self, "scrubbing", True))
        self.position.bind("<ButtonRelease-1>", self.finish_seek)
        controls = ttk.Frame(player)
        controls.pack(fill="x")
        for text, fn, tip in [("⏮", lambda: self.next_song(-1), "Anterior"), ("−10 s", lambda: self.skip(-10000), "Retroceder"),
                         ("▶", self.resume_or_play, "Reproducir"), ("⏸", self.pause, "Pausa / continuar"), ("■", self.stop_player, "Detener"),
                         ("+10 s", lambda: self.skip(10000), "Adelantar"), ("⏭", lambda: self.next_song(1), "Siguiente")]:
            btn = ttk.Button(controls, text=text, width=5, command=fn, style="Accent.TButton" if text=="▶" else "TButton")
            btn.pack(side="left", padx=2)
            tooltip(btn, tip)
        self.clock = ttk.Label(controls, text="0:00 / 0:00")
        self.clock.pack(side="left", padx=8)
        self.volume = ttk.Scale(controls, from_=0, to=1000, command=self.volume_changed, length=100)
        self.volume.set(800)
        self.volume.pack(side="right")
        ttk.Label(controls, text="Volumen").pack(side="right")
        self.w.bind("<Escape>", lambda _: self.stop_player())
        self.show_page("Inicio")
        self.theme("Oscuro")
        self.library()
        window.protocol("WM_DELETE_WINDOW", self.close)
        self.inspect()
        window.after(150, self.poll)

    def help(self, parent, explanation):
        label = ttk.Label(parent, text="ⓘ", foreground="#e944a7", cursor="question_arrow", font=("Segoe UI", 11))
        label.pack(side="left", padx=4)
        tooltip(label, explanation, delay=3000)

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
        for name, fn in [("▶", self.play), ("⏸", self.pause), ("■", self.stop_player),
                         ("↓ MP3", lambda: self.export("mp3")), ("↓ WAV", self.export)]:
            ttk.Button(row, text=name, command=fn).pack(side="left", padx=2)
        row2 = ttk.Frame(parent)
        row2.pack(fill="x")
        self.favorite_button = ttk.Button(row2, text="♥", style="MutedHeart.TButton", command=lambda: self.edit_song(True))
        self.favorite_button.pack(side="left", padx=2)
        listing.bind("<<ListboxSelect>>", lambda _: self.update_heart())
        for name, fn in [("Renombrar", lambda: self.edit_song(False)), ("Abrir ubicación", self.open_folder), ("Letra", self.view_lyrics)]:
            ttk.Button(row2, text=name, command=fn).pack(side="left", padx=2)
        return listing

    def show_page(self, name):
        self.page = name
        self.panels[name].tkraise()
        for key, button in self.nav_buttons.items():
            button.configure(style="ActiveNav.TButton" if key==name else "Nav.TButton")
        if name == "Modelos" and not self.busy and hasattr(self, "generate_button"):
            self.inspect()
        if name in ("Inicio", "Crear música"):
            self.history = self.home_history if name == "Inicio" else self.create_history

    @staticmethod
    def format_time(ms):
        seconds = max(0, int(ms) // 1000)
        return f"{seconds//60}:{seconds%60:02d}"

    def stop_player(self):
        try:
            self.player.close()
        except OSError as exc:
            messagebox.showerror("Reproducción", str(exc))
        self.playing_file = None
        self.spectrum.delete("all")
        self.waveform.delete("all")
        self.position.set(0)
        self.clock.configure(text="0:00 / 0:00")
        self.now_playing.configure(text="Selecciona una canción")

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
        bg, fg = ("#13172b", "#f6f3ff") if self.dark else ("#f7eff8", "#251c3a")
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("Nav.TFrame", background="#25204b" if self.dark else "#e4d5f0")
        self.style.configure("Nav.TLabel", background="#25204b" if self.dark else "#e4d5f0", foreground=fg)
        self.style.configure("Nav.TButton", background="#392d66", foreground="#ffffff", padding=8)
        self.style.configure("ActiveNav.TButton", background="#cf137e", foreground="#ffffff", padding=8)
        self.style.configure("Accent.TButton", background="#c91382", foreground="#ffffff", padding=8)
        self.style.map("Accent.TButton", background=[("active", "#ee36a2"), ("disabled", "#675268")])
        self.style.map("ActiveNav.TButton", background=[("active", "#ee36a2")])
        self.style.configure("MutedHeart.TButton", foreground="#9692a7", font=("Segoe UI", 13))
        self.style.configure("FavoriteHeart.TButton", foreground="#ff3465", font=("Segoe UI", 13))
        self.style.configure("Good.TLabel", foreground="#43cfa3", background=bg)
        self.style.configure("Warn.TLabel", foreground="#f3b94c", background=bg)
        self.w.configure(background=bg)
        for widget in (getattr(self, "lyrics", None), getattr(self, "home_history", None), getattr(self, "create_history", None)):
            if widget is not None:
                widget.configure(background=bg, foreground=fg, selectbackground="#7761be", selectforeground="white")
        if hasattr(self, "lyrics"):
            self.lyrics.configure(insertbackground=fg)
        if hasattr(self, "topic"):
            self.topic.configure(background=bg, foreground=fg, insertbackground=fg)
        for scroll in (getattr(self, "home_scroll", None), getattr(self, "form_scroll", None), getattr(self, "composer", None)):
            if scroll:
                scroll.canvas.configure(background=bg)
        if hasattr(self, "song_data") and hasattr(self, "home_cards"):
            self.draw_cards()

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
        self.download_sample = None
        self.generate_button.state(["disabled"])
        self.compose_button.state(["disabled"])
        self.progress.configure(mode="determinate" if download else "indeterminate", value=0, maximum=100)
        self.progress.pack(side="right", padx=6)
        if not download:
            self.progress.start(12)
        self.cancel_button.configure(text="Cancelar descarga" if download else "Cancelar " + action.lower())
        self.cancel_button.pack(side="right")
        def work():
            try:
                self.events.put(("done", function() or "Finalizado"))
            except InterruptedError:
                self.events.put(("done", "Operación cancelada."))
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
                    self.set_model_state(key, state)
                if missing:
                    self.home_notice.configure(command=lambda: self.show_page("Configuración" if not self.binary().exists() else "Modelos"))
                    self.home_notice.pack(anchor="w", pady=8)
                else:
                    self.home_notice.pack_forget()
            elif kind == "model":
                key, state = text
                self.set_model_state(key, state)
            elif kind == "progress":
                label, n, total = text
                percent = 100*n/max(total, 1)
                self.stage = f"{label} · {percent:.1f}%"
                now = time.monotonic()
                if self.download_sample:
                    old_n, old_total, old_t = self.download_sample
                    if total == old_total and n > old_n and now > old_t:
                        speed = (n-old_n)/(now-old_t)
                        self.stage += f" · {speed/1e6:.1f} MB/s"
                self.download_sample = n, total, now
                self.progress.configure(mode="determinate", value=percent)
            elif kind == "lyrics":
                self.lyrics.delete("1.0", "end")
                self.lyrics.insert("1.0", text)
                self.lyric_notice.configure(text="Letra creada. Revísala y edítala antes de generar música.")
                self.hide_composer()
            elif kind == "song":
                label, version = text
                self.latest.configure(text=label)
                self.new_version = version
                self.hide_composer()
                self.show_page("Crear música")
            else:
                self.busy = False
                self.progress.stop()
                self.progress.pack_forget()
                self.cancel_button.pack_forget()
                self.generate_button.state(["!disabled"])
                self.compose_button.state(["!disabled"])
                self.status.set(text)
                if kind == "error" and not self.closing:
                    if self.action == "Composición":
                        self.lyric_notice.configure(text=text)
                    else:
                        messagebox.showerror("Noel Music AI", text)
                self.library()
                if kind == "done" and not self.closing and self.action in ("Instalación de modelos", "Instalación del motor"):
                    self.inspect()
        if self.player.opened:
            try:
                position = int(self.player.send("status noelplayer position"))
                duration = int(self.player.send("status noelplayer length"))
                self.position.configure(to=max(1, duration))
                if not self.scrubbing:
                    self.position.set(position)
                self.clock.configure(text=f"{self.format_time(position)} / {self.format_time(duration)}")
                self.spectrum.delete("all")
                if self.playing_file and self.player.send("status noelplayer mode") == "playing":
                    for i, level in enumerate(spectrum(self.playing_file, position)):
                        self.spectrum.create_rectangle(i*10+1, 30-28*level, i*10+8, 30, fill="#36d1cf", outline="")
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
        try:
            self.player.close()
        except OSError:
            pass
        self.closing = True
        self.cancel.set()

    def folder(self, key):
        if self.busy:
            return
        path = filedialog.askdirectory()
        if path:
            self.verified.clear()
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
        self.song_data = []
        for manifest in sorted(self.runs.glob("*/version.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(manifest.read_text("utf-8"))
                wav = manifest.with_name("song.wav")
                if wav.exists():
                    title_file = manifest.with_name("display.json")
                    display = json.loads(title_file.read_text("utf-8")) if title_file.exists() else {}
                    title = display.get("title") or data["request"]["caption"][:90]
                    favorite = bool(display.get("favorite"))
                    for listing in (self.home_history, self.create_history):
                        listing.insert("end", f"{'♥ ' if favorite else ''}{title} · {data['metrics']['actual_seconds']:.1f} s")
                    self.files.append(wav)
                    self.song_data.append(dict(title=title, favorite=favorite, seconds=data["metrics"]["actual_seconds"], lyrics=data["request"].get("lyrics", "")))
            except (OSError, ValueError, KeyError):
                continue
        if self.files:
            latest = self.runs/self.new_version/"song.wav" if self.new_version else None
            index = self.files.index(latest) if latest in self.files else self.files.index(selected) if selected in self.files else 0
            for listing in (self.home_history, self.create_history):
                listing.selection_set(index)
                listing.see(index)
            self.new_version = None
        self.update_heart()
        self.draw_cards()

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
                    self.waveform.create_line(i*width, 15-14*peak, i*width, 16+14*peak, fill="#ee61c0")
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
            try:
                mode = self.player.send("status noelplayer mode")
                if mode == "playing":
                    self.player.send("pause noelplayer")
                elif mode == "paused":
                    self.player.send("resume noelplayer")
            except OSError as exc:
                messagebox.showerror("Reproducción", str(exc))

    def volume_changed(self, value):
        if self.player.opened:
            self.player.send(f"setaudio noelplayer volume to {int(float(value))}")

    def export(self, format="wav"):
        if self.history.curselection() and not self.busy:
            index = self.history.curselection()[0]
            source = self.files[index]
            title = self.song_data[index]["title"]
            initial = "".join(c for c in title if c not in '<>:"/\\|?*')[:90] or "cancion"
            dest = filedialog.asksaveasfilename(defaultextension="."+format, initialfile=initial+"."+format,
                                               filetypes=[("Audio "+format.upper(), "*."+format)])
            if dest:
                self.run(lambda: export_audio(source, dest, format), "Exportación "+format.upper())

    def report(self):
        dest = filedialog.asksaveasfilename(defaultextension=".json")
        if dest:
            self.run(lambda: write_json(Path(dest), snapshot()))

    def binary(self):
        return binary_path(ROOT)

    def force_inspect(self):
        if not self.busy:
            self.verified.clear()
            self.inspect()

    def check_model(self, name, size, digest):
        path = self.models/name
        try:
            st = path.stat()
        except FileNotFoundError:
            return False
        key = (str(path), st.st_size, st.st_mtime_ns, st.st_ctime_ns, size, digest)
        if self.verified.get(str(path)) == key:
            return True
        ok = matches(path, size, digest)
        if ok:
            self.verified[str(path)] = key
        return ok

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
                ok = self.check_model(name, size, digest)
                path = self.models/name
                state = "✓ Instalado y verificado" if ok else "⚠ Requiere reparación" if path.exists() else "↓ Descarga pendiente" if path.with_suffix(".gguf.part").exists() else "○ No descargado"
                inventory[key] = f"{state} · {size/1e6:.0f} MB · {'Necesario' if key in MODELS else 'Opcional'}"
                missing = missing or (key in MODELS and not ok)
                rows.append(f"{name} · {state}")
            self.events.put(("inventory", ("\n".join(rows), inventory, missing)))
        self.run(work, "Diagnóstico")

    def install(self, keys):
        if self.busy or not keys:
            return
        total = sum(catalog()[k][1] for k in keys)
        if not messagebox.askyesno("Modelos seleccionados", f"Verificar y descargar desde Hugging Face los archivos faltantes o dañados (hasta {total/1e9:.2f} GB)?"):
            return
        def work():
            self.verified.clear()
            from .models import install
            install(self.models, True, keys, repair=True, cancel=self.cancel,
                    progress=lambda name, n, total: self.events.put(("progress", (f"{name} · {n/1e6:.1f} / {total/1e6:.1f} MB", n, total))))
            for key in keys:
                name, size, _ = catalog()[key]
                self.events.put(("model", (key, f"✓ Instalado y verificado · {size/1e6:.0f} MB · {'Necesario' if key in MODELS else 'Opcional'}")))
            return "Modelos verificados"
        self.run(work, "Instalación de modelos", download=True)

    def musical_caption(self):
        return build_caption(self.genres[self.genre.get()], self.mood.get(), self.setting.get(),
                             "Instrumental" if self.instrumental.get() else self.voice.get(), self.prompt.get(),
                             [name for name,var in self.instrument_vars.items() if var.get()])

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
            if not self.check_model(name, size, digest):
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

    def setting_action(self, parent, title, description, fn):
        row = ttk.Frame(parent, padding=5)
        row.pack(fill="x")
        ttk.Button(row, text=title, command=fn).pack(side="left", padx=(0,10))
        ttk.Label(row, text=description, wraplength=390).pack(side="left", fill="x", expand=True)

    def set_model_state(self, key, state):
        ok = state.startswith("✓")
        self.model_states[key].configure(text=state, style="Good.TLabel" if ok else "Warn.TLabel")
        button = self.model_buttons[key]
        button.configure(text="Verificar" if ok else "Reparar" if state.startswith("⚠") else "Reanudar" if state.startswith("↓") else "↓ Descargar")

    def toggle_instruments(self):
        if self.instrument_panel.winfo_manager():
            self.instrument_panel.pack_forget()
        else:
            self.instrument_panel.pack(fill="x", after=self.instrument_label.master)

    def update_instrument_label(self):
        names = [name for name, var in self.instrument_vars.items() if var.get()]
        self.instrument_label.configure(text="Instrumentos: " + (", ".join(names) if names else "Automático"))

    def clear_instruments(self):
        for var in self.instrument_vars.values():
            var.set(False)
        self.update_instrument_label()

    def toggle_instrumental(self):
        state = self.instrumental.get()
        self.voice.configure(state="disabled" if state else "readonly")
        self.language.configure(state="disabled" if state else "readonly")
        self.lyrics.configure(state="disabled" if state else "normal")
        self.compose_cta.configure(state="disabled" if state else "normal")
        if state:
            self.hide_composer()

    def build_composer(self, parent):
        self.composer = ScrollFrame(parent)
        frame = self.composer.inner
        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="✦ Compositor de letras IA", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(header, text="×", width=3, command=self.hide_composer).pack(side="right")
        self.field_label(frame, "Tema de tu canción", "Describe lo que quieres contar.")
        self.topic = tk.Text(frame, height=4, wrap="word", relief="flat")
        self.topic.pack(fill="x")
        self.structure = self.combo(frame, "Estructura", [*STRUCTURES, "Personalizada"], "Selecciona una estructura o define el orden de seis secciones.")
        self.sections_panel = ttk.Frame(frame)
        self.sections = []
        for i, val in enumerate(["Intro","Verso 1","Coro","Verso 2","Coro","Outro"]):
            slot = ttk.Frame(self.sections_panel)
            slot.grid(row=i//2, column=i%2, sticky="ew", padx=3, pady=3)
            ttk.Label(slot, text=str(i+1)).pack(anchor="w")
            combo = ttk.Combobox(slot, values=list(SECTIONS), state="readonly", width=12)
            combo.set(val)
            combo.pack(fill="x")
            self.sections.append(combo)
        self.sections_panel.columnconfigure(0, weight=1)
        self.sections_panel.columnconfigure(1, weight=1)
        self.structure.bind("<<ComboboxSelected>>", self.toggle_sections)
        self.intent = self.combo(frame, "Intención de la letra", list(INTENTIONS), "Tema o propósito: protesta, amor, patriotismo, desahogo, etc.")
        self.complexity = self.combo(frame, "Estilo de escritura", list(COMPLEXITIES), "El nivel de elaboración: poético, sencillo y pegadizo o narrativo.")
        self.lyric_language = self.combo(frame, "Idioma", list(LANGUAGES), "Idioma solicitado para la letra; se aplica también al canto.")
        self.field_label(frame, "Instrucción adicional", "Indicaciones que no estén cubiertas por los demás controles.")
        self.extra = ttk.Entry(frame)
        self.extra.pack(fill="x")
        self.lyric_notice = ttk.Label(frame, text="Modelo local opcional LM 0.6B · ~710 MB.", wraplength=280)
        self.lyric_notice.pack(anchor="w", pady=6)
        self.compose_button = ttk.Button(frame, text="✦ Generar letra", style="Accent.TButton", command=self.compose_lyrics)
        self.compose_button.pack(fill="x", pady=8)

    def toggle_sections(self, _=None):
        if self.structure.get() == "Personalizada":
            self.sections_panel.pack(fill="x", after=self.structure)
        else:
            self.sections_panel.pack_forget()

    def lyric_dialog(self):
        if self.instrumental.get() or self.busy:
            return
        self.lyric_language.set(self.language.get())
        self.results.pack_forget()
        self.composer.pack(fill="both", expand=True)
        self.composing = True

    def hide_composer(self):
        self.composer.pack_forget()
        if not self.results.winfo_manager():
            self.results.pack(fill="both", expand=True)
        self.composing = False

    def compose_lyrics(self):
        if self.busy or self.instrumental.get():
            return
        try:
            language = self.lyric_language.get()
            code = LANGUAGES[language][0]
            seconds = self.duration.get()
            prompt = lyric_prompt(self.topic.get("1.0", "end"), self.musical_caption(), self.structure.get(),
                                 self.complexity.get(), self.extra.get(), language, self.intent.get(),
                                 [x.get() for x in self.sections], seconds)
        except ValueError as exc:
            self.lyric_notice.configure(text=str(exc))
            return
        if self.lyrics.get("1.0", "end").strip() and not messagebox.askyesno("Compositor", "¿Reemplazar la letra actual si se genera correctamente?"):
            return
        self.lyric_notice.configure(text="Generando letra en " + language + "…")
        self.language.set(language)
        def work():
            with self.engine_session(("lm",)) as (engine, props):
                if OPTIONAL["lm"][0] not in props["models"].get("lm", []):
                    raise ValueError("El servidor no reconoció el modelo de letras.")
                self.events.put(("stage", "Componiendo letra"))
                lyrics = engine.compose(dict(caption=prompt, vocal_language=code, duration=seconds,
                                             lm_model=OPTIONAL["lm"][0], lm_mode="inspire", lm_batch_size=1))
                self.events.put(("lyrics", lyrics))
                return "Letra generada. Revísala antes de crear música."
        self.run(work, "Composición")

    def select_song(self, index):
        for listing in (self.home_history, self.create_history):
            listing.selection_clear(0, "end")
            listing.selection_set(index)
            listing.see(index)
        self.update_heart()

    def card_action(self, index, fn):
        self.select_song(index)
        fn()

    def resize_cards(self, event):
        cols = 3 if event.width >= 1140 else 2 if event.width >= 760 else 1
        if cols != self.card_columns:
            self.card_columns = cols
            self.draw_cards()

    def draw_cards(self):
        for widget in self.home_cards.winfo_children():
            widget.destroy()
        data = [(i, s) for i,s in enumerate(self.song_data) if not self.home_filter.get() or s["favorite"]]
        if not data:
            ttk.Label(self.home_cards, text="Todavía no hay canciones en esta vista.").pack(anchor="w")
            return
        palettes = [("#c80979","#5335af"),("#1551b8","#00a0aa"),("#e85324","#b71d6e"),("#5138ae","#087d97")]
        for pos, (i, song) in enumerate(data):
            card = ttk.Frame(self.home_cards, padding=7)
            card.grid(row=pos//self.card_columns, column=pos%self.card_columns, sticky="nsew", padx=4, pady=4)
            top = tk.Canvas(card, height=106, highlightthickness=0, cursor="hand2")
            top.pack(fill="x")
            left,right = palettes[i%len(palettes)]
            title = song["title"]
            sub = self.format_time(song["seconds"]*1000)
            top.bind("<Configure>", lambda e, w=top, a=left,b=right,t=title,s=sub: gradient(w,e.width,e.height,a,b,t,s,play=True))
            top.bind("<Button-1>", lambda _, n=i: self.card_action(n,self.play))
            row = ttk.Frame(card)
            row.pack(fill="x", pady=4)
            for text, fn in [("▶",self.play),("⏸",self.pause_selected),("■",self.stop_selected),("↓ MP3",lambda: self.export("mp3")),
                             ("↓ WAV",self.export),("Letra",self.view_lyrics)]:
                ttk.Button(row,text=text,command=lambda n=i,f=fn:self.card_action(n,f)).pack(side="left",padx=1)
            row2 = ttk.Frame(card)
            row2.pack(fill="x")
            ttk.Button(row2,text="♥",style="FavoriteHeart.TButton" if song["favorite"] else "MutedHeart.TButton",
                       command=lambda n=i:self.card_action(n,lambda:self.edit_song(True))).pack(side="left")
            for text, fn in [("Renombrar",lambda:self.edit_song(False)),("Ubicación",self.open_folder),
                             ("Compartir",self.share_song)]:
                ttk.Button(row2,text=text,command=lambda n=i,f=fn:self.card_action(n,f)).pack(side="left",padx=1)
        for col in range(3):
            self.home_cards.columnconfigure(col, weight=1 if col < self.card_columns else 0)

    def update_heart(self):
        if not hasattr(self, "favorite_button"):
            return
        selected = self.create_history.curselection()
        fav = bool(selected and selected[0] < len(self.song_data) and self.song_data[selected[0]]["favorite"])
        self.favorite_button.configure(style="FavoriteHeart.TButton" if fav else "MutedHeart.TButton")

    def view_lyrics(self):
        if not self.history.curselection():
            return
        song = self.song_data[self.history.curselection()[0]]
        w = tk.Toplevel(self.w)
        w.title(song["title"] + " · Letra")
        text = tk.Text(w, wrap="word", width=60, height=20)
        text.pack(fill="both", expand=True)
        text.insert("1.0", song["lyrics"] or "Sin letra.")
        text.configure(state="disabled")

    def share_song(self):
        if self.history.curselection():
            path = self.files[self.history.curselection()[0]]
            self.w.clipboard_clear()
            self.w.clipboard_append(str(path))
            os.startfile(path.parent)
            self.status.set("Ruta copiada. Adjunta el WAV o exporta MP3 para compartirlo.")

    def pause_selected(self):
        if self.history.curselection() and self.files[self.history.curselection()[0]] == self.playing_file:
            self.pause()

    def stop_selected(self):
        if self.history.curselection() and self.files[self.history.curselection()[0]] == self.playing_file:
            self.stop_player()

    def resume_or_play(self):
        if self.player.opened:
            try:
                mode = self.player.send("status noelplayer mode")
                if mode == "paused":
                    self.player.send("resume noelplayer")
                    return
                if mode == "playing":
                    return
            except OSError:
                pass
        self.play()

    def generate(self):
        if self.busy:
            return
        title = self.title.get().strip()
        caption = self.musical_caption()
        lyrics = self.lyrics.get("1.0", "end").strip()
        if self.instrumental.get():
            lyrics = ""
        if not self.instrumental.get() and not lyrics:
            messagebox.showinfo("Letra", "Escribe una letra o usa el compositor IA para generar una canción con voz.")
            return
        seconds = max(15, min(300, self.duration.get()))
        model = "sft" if self.model_choice.current() == 1 else "dit"
        if seconds > 120 or model == "sft":
            if not messagebox.askyesno("Configuración experimental", "Esta duración o modelo aún no tiene benchmark en tu GPU. ¿Continuar?"):
                return
        seed = secrets.randbelow(2**31)
        language = LANGUAGES[self.language.get()][0]
        def work():
            with self.engine_session(("sft",) if model == "sft" else ()) as (engine, props):
                self.events.put(("stage", "Generando música"))
                with PeakMonitor() as monitor:
                    result = render(engine, props, self.runs, caption, lyrics, seconds, seed, model, language)
                write_json(self.runs/result["version"]/"performance.json",
                           dict(peak_system_vram_mib=monitor.peak_gpu_mib, peak_system_ram_bytes=monitor.peak_ram_bytes,
                                total_seconds=result["total_s"], generated_seconds=result["actual_seconds"]))
                if title:
                    write_json(self.runs/result["version"]/"display.json", {"title": title})
                self.events.put(("song", (f"{title or 'Nueva canción'} · {result['actual_seconds']:.0f} s · lista para escuchar", result["version"])))
                return "Canción guardada · " + result["version"]
        self.run(work, "Generación")


if __name__ == "__main__":
    root = tk.Tk()
    Studio(root)
    root.mainloop()
