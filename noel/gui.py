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
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .__main__ import ROOT, RUNTIME
from .diagnostics import PeakMonitor, snapshot
from .player import Player, envelope, spectrum
from .engine import Engine
from .distribution import available, binary_path, install_engine
from .models import (MODELS, OPTIONAL, catalog, matches, MUSIC, LYRIC_MODELS, DEVICES,
                     model_path, required_music, device_warning, transfer_model, TEXT_BASES)
from . import text_engine
from .presets import (VOICES, MOODS, AMBIENCES, STRUCTURES, LANGUAGES, INSTRUMENTS, SECTIONS,
                      INTENTIONS, COMPLEXITIES, caption as build_caption, lyric_prompt)
from .audio_export import export_audio
from .creative_ui import ScrollFrame, tooltip, gradient, PianoLoader, instrument_icon
from .hardware import recommend, operation_warning
from .creative_ui import center_dialog, draw_play_state
from .ui_theme import create_style
from .studio import render, write_json
from . import editor, voice_profiles, voice_engine


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
        self.voice_root=RUNTIME/"voices"
        self.voice_profiles={}
        self.recording=voice_profiles.Recorder()
        self.voice_record_timer=None
        self.voice_temp=None
        self.verified = {}
        self.new_version = None
        self.song_data = []
        self.card_views = {}
        self.card_playing = None
        self.model_buttons = {}
        self.model_save_buttons = {}
        self.composing = False
        self.hardware = None
        self.advice_seen = set()
        self.pending_hardware_action = None
        RUNTIME.mkdir(exist_ok=True)
        self.config = RUNTIME / "studio.json"
        self.paths = json.loads(self.config.read_text("utf-8")) if self.config.exists() else {}
        self.device_mode = self.paths.get("device", "gpu")
        if self.device_mode not in DEVICES:
            self.device_mode = "gpu"
        self.music_default = self.paths.get("music_model", "dit")
        if self.music_default not in MUSIC:
            self.music_default = "dit"
        self.lyrics_default = self.paths.get("lyrics_model", "lm")
        if self.lyrics_default not in LYRIC_MODELS:
            self.lyrics_default = "lm"
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
        self.panels = {name: ttk.Frame(content, padding=12) for name in ("Inicio", "Crear música", "Editor musical", "Mis voces", "Modelos", "Configuración")}
        self.nav_buttons = {}
        for name, panel in self.panels.items():
            panel.grid(row=0, column=0, sticky="nsew")
            b = ttk.Button(sidebar, text=name, style="Nav.TButton", command=lambda n=name: self.show_page(n))
            b.pack(fill="x", pady=4)
            self.nav_buttons[name] = b
        home, create, edit_panel, voices_panel, setup, settings = self.panels.values()
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
        split.columnconfigure(0, weight=1, uniform="studio")
        split.columnconfigure(1, weight=1, uniform="studio")
        split.rowconfigure(0, weight=1)
        form_scroll = self.form_scroll = ScrollFrame(split)
        form_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form = form_scroll.inner
        workspace = self.workspace = ttk.Frame(split, padding=(8, 0))
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.pack_propagate(False)
        self.generate_button = ttk.Button(workspace, text="✦ Generar canción", style="Accent.TButton", command=lambda:self.refresh_then(self.generate))
        self.generate_button.pack(fill="x", pady=(0, 5))
        instrument_row = ttk.Frame(workspace)
        instrument_row.pack(fill="x")
        self.instrument_label = ttk.Label(instrument_row, text="Instrumentos",style="Field.TLabel",font=("Segoe UI",11,"bold"))
        self.instrument_label.pack(side="left")
        self.help(instrument_row, "Automático deja elegir al motor; Manual usa tus preferencias de instrumentos. La IA puede desviarse.")
        mode_row=ttk.Frame(workspace)
        mode_row.pack(fill="x",pady=(2,2))
        self.instrument_mode=tk.StringVar(value="auto")
        for value,label in (("auto","Automático"),("manual","Manual")):
            ttk.Radiobutton(mode_row,text=label,value=value,variable=self.instrument_mode,command=self.update_instrument_mode).pack(side="left",padx=3)
        self.instrument_panel = ttk.Frame(workspace)
        self.instrument_panel.pack(fill="x")
        self.instrument_vars={}
        self.instrument_checks={}
        self.instrument_icons=[]
        # Short labels fit the right-hand studio; tooltip keeps the complete instrument name.
        aliases={"Guitarra acústica":"G. acúst.","Guitarra eléctrica":"G. eléct.","Violonchelo":"Chelo",
                 "Sintetizador":"Sintetiz.","Acordeón":"Acordeón"}
        for i,name in enumerate(INSTRUMENTS):
            var=tk.BooleanVar(value=False)
            self.instrument_vars[name]=var
            pic=instrument_icon(name,self.w)
            self.instrument_icons.append(pic)
            kwargs={"image":pic,"compound":"left"} if pic else {}
            check=ttk.Checkbutton(self.instrument_panel,text=aliases.get(name,name),variable=var,
                                  command=self.update_instrument_label,style="Instrument.TCheckbutton",**kwargs)
            check.grid(row=i//3,column=i%3,sticky="w",padx=1,pady=0)
            self.instrument_checks[name]=check
            tooltip(check,name,delay=800)
        self.update_instrument_mode()
        self.duration=tk.IntVar(value=60)
        self.field_label(workspace,"Duración de la canción","15 a 300 segundos. Comienza con un minuto; en CPU conviene probar 15 segundos.")
        durations=ttk.Frame(workspace)
        durations.pack(fill="x",pady=(0,5))
        ttk.Scale(durations,from_=15,to=300,variable=self.duration).pack(side="left",fill="x",expand=True)
        self.duration_label=ttk.Label(durations,text="1:00",width=6,style="Field.TLabel")
        self.duration_label.pack(side="right")
        self.duration.trace_add("write",lambda *_:self.duration_label.configure(text=self.format_time(self.duration.get()*1000)))
        self.results_container = ttk.Frame(workspace)
        self.results_container.pack(fill="both",expand=True)
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
        voice_row = ttk.Frame(form)
        voice_row.pack(fill="x",pady=3)
        voice_row.columnconfigure(0,weight=1,uniform="language")
        voice_row.columnconfigure(1,weight=1,uniform="language")
        instrumental_cell=ttk.Frame(voice_row)
        instrumental_cell.grid(row=0,column=0,sticky="sw",padx=(0,4))
        ttk.Checkbutton(instrumental_cell,text="Instrumental, sin voz",variable=self.instrumental,command=self.toggle_instrumental).pack(anchor="w")
        language_cell=ttk.Frame(voice_row)
        language_cell.grid(row=0,column=1,sticky="ew",padx=(4,0))
        self.language = self.combo(language_cell, "Idioma", list(LANGUAGES), "Idioma de las palabras cantadas.")
        self.field_label(form, "Estilo musical", "Detalles adicionales: instrumentos, ritmo, timbre o producción. Puedes dejarlo vacío.")
        self.prompt = ttk.Entry(form)
        self.prompt.pack(fill="x")
        lyricbar = ttk.Frame(form)
        lyricbar.pack(fill="x", pady=(10, 4))
        ttk.Label(lyricbar, text="Letra", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.help(lyricbar, "Escribe o pega la letra. Vacía = instrumental. Usa etiquetas [Verse], [Chorus].")
        self.compose_cta = ttk.Button(lyricbar, text="✦ Crear letra con IA", style="Accent.TButton", command=self.lyric_dialog)
        self.compose_cta.pack(side="right")
        self.copy_button = copy_button = ttk.Button(lyricbar, text="▣ Copiar", command=self.copy_lyrics, state="disabled")
        copy_button.pack(side="right", padx=4)
        tooltip(copy_button, "Copiar letra al portapapeles")
        self.lyrics = tk.Text(form, height=6, wrap="word", font=("Segoe UI", 11), relief="flat")
        self.lyrics.pack(fill="x")
        self.lyrics.bind("<<Modified>>",self.lyrics_changed)
        self.lyrics.edit_modified(False)
        ttk.Label(results, text="Tus generaciones", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.latest = ttk.Label(results, text="Aquí aparecerá la canción generada.", wraplength=270)
        self.latest.pack(anchor="w", pady=8)
        result_scroll = ScrollFrame(results)
        result_scroll.pack(fill="both",expand=True)
        self.create_history = self.make_history(result_scroll.inner)
        self.build_composer(self.results_container)
        self.build_editor(edit_panel)
        self.build_voices(voices_panel)
        self.refresh_voices()
        model_scroll = ScrollFrame(setup)
        model_scroll.pack(fill="both", expand=True)
        setup = model_scroll.inner
        ttk.Label(setup, text="Centro de modelos", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(setup, text="Descarga, carga un GGUF existente o guarda una copia. Cada archivo se verifica por tamaño y SHA-256.", wraplength=650).pack(anchor="w", pady=8)
        ttk.Button(setup, text="Instalar paquete musical predeterminado", command=lambda: self.install(required_music(self.music_default))).pack(anchor="w", pady=6)
        ttk.Button(setup, text="↓ Descargar todo · motores y modelos", style="Accent.TButton", command=self.download_all).pack(anchor="w", pady=6)
        ttk.Button(setup,text="Conversión vocal · HTDemucs y Seed-VC",command=lambda:self.show_page("Mis voces")).pack(anchor="w",pady=4)
        self.model_states = {}
        descriptions = {"embedding":"Interpreta las instrucciones musicales", "dit":"Generación rápida · perfil probado",
                        "vae":"Decodificación de audio", "lm":"Compositor musical rápido · seguimiento de instrucciones limitado",
                        "sft":"Generación alternativa · 50 pasos", "turbo4":"Cuantización ligera · CPU experimental",
                        "qwen":"Compositor generalista · requiere llama.cpp opcional",
                        "qwen06":"Texto ligero · recomendado para CPU modesta · experimental",
                        "qwen17":"Texto equilibrado · alternativa para CPU/GPU · experimental"}
        for heading, keys in [("Generación musical", MUSIC), ("Composición de letras", LYRIC_MODELS),
                              ("Componentes auxiliares de música", ("embedding","vae"))]:
            ttk.Label(setup, text=heading, font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(16,4))
            for key in keys:
                name,size,_ = catalog()[key]
                row = ttk.Frame(setup, padding=8)
                row.pack(fill="x", pady=3)
                detail = ttk.Frame(row)
                detail.pack(fill="x")
                ttk.Label(detail, text=name, font=("Segoe UI", 10, "bold"), wraplength=600).pack(anchor="w")
                ttk.Label(detail, text=descriptions[key], wraplength=600).pack(anchor="w")
                state = ttk.Label(detail, text="Comprobando…")
                state.pack(anchor="w")
                self.model_states[key] = state
                controls = ttk.Frame(row)
                controls.pack(fill="x", pady=3)
                btn = ttk.Button(controls, text="Comprobando…", command=lambda k=key: self.install([k]))
                btn.pack(side="left", padx=2)
                self.model_buttons[key] = btn
                ttk.Button(controls, text="↑ Cargar modelo", command=lambda k=key: self.import_model(k)).pack(side="left", padx=2)
                save = ttk.Button(controls, text="↓ Guardar copia", command=lambda k=key: self.save_model(k), state="disabled")
                save.pack(side="left", padx=2)
                self.model_save_buttons[key] = save
        ttk.Button(setup, text="Instalar motor Qwen (llama.cpp)", command=self.install_text_runtime).pack(anchor="w", pady=8)
        self.text_runtime_status = ttk.Label(setup, text="Motor de letras independiente · instalación opcional", wraplength=600)
        self.text_runtime_status.pack(anchor="w")
        settings_scroll = ScrollFrame(settings)
        settings_scroll.pack(fill="both", expand=True)
        settings = settings_scroll.inner
        ttk.Label(settings, text="Configuración", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(settings, text="Tema moderno ttkbootstrap" if self.modern else "Tema básico · ttkbootstrap no disponible").pack(anchor="w", pady=4)
        ttk.Label(settings, text="Procesamiento y modelos predeterminados", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(10,4))
        self.device_setting = self.combo(settings, "Procesador", list(DEVICES.values()), "CPU: procesamiento local lento. GPU: CUDA. CPU + GPU: ACE-Step usa GPU y Qwen reparte capas.")
        self.device_setting.set(DEVICES[self.device_mode])
        hardware_box=ttk.Frame(settings,padding=8,style="Nav.TFrame")
        hardware_box.pack(fill="x",pady=5)
        self.hardware_label=ttk.Label(hardware_box,text="Detectando recursos…",wraplength=650,style="Nav.TLabel")
        self.hardware_label.pack(anchor="w")
        self.recommend_label=ttk.Label(settings,text="",wraplength=650,style="Field.TLabel")
        self.recommend_label.pack(anchor="w",pady=3)
        ttk.Button(settings,text="Usar recomendación del equipo",command=self.recommend_settings).pack(anchor="w",pady=3)
        self.music_setting = self.combo(settings, "Modelo de música", list(MUSIC.values()), "Se carga al generar música, no al iniciar.")
        self.music_setting.set(MUSIC[self.music_default])
        self.lyrics_setting = self.combo(settings, "Modelo de letras", list(LYRIC_MODELS.values()), "Se carga al componer letras, y se libera después.")
        self.lyrics_setting.set(LYRIC_MODELS[self.lyrics_default])
        ttk.Button(settings, text="Guardar cambios", style="Accent.TButton", command=self.save_preferences).pack(anchor="w", pady=6)
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
        self.piano = PianoLoader(self.operation)
        self.progress = ttk.Progressbar(self.operation, mode="indeterminate", length=140)
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
        ttk.Label(row, text=text,style="Field.TLabel").pack(side="left")
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
        if name == "Mis voces" and hasattr(self,"voice_list"):
            self.refresh_voices()
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
        self.sync_card_playback(None)
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
        self.style.configure("Field.TLabel",background=bg,foreground="#71dfe4" if self.dark else "#126b78",font=("Segoe UI",10,"bold"))
        self.style.configure("TEntry",fieldbackground="#ffffff",foreground="#22243a",insertcolor="#22243a")
        self.style.configure("TCombobox",fieldbackground="#ffffff",foreground="#22243a",background="#ffffff",arrowcolor="#25233d")
        self.style.map("TCombobox",fieldbackground=[("disabled","#e8e8ef"),("readonly","#ffffff"),("!disabled","#ffffff")],foreground=[("disabled","#777785"),("readonly","#22243a")],selectbackground=[("readonly","#ffffff")],selectforeground=[("readonly","#22243a")])
        self.style.map("TEntry",fieldbackground=[("disabled","#e8e8ef"),("!disabled","#ffffff")],foreground=[("disabled","#777785"),("!disabled","#22243a")])
        self.w.option_add("*TCombobox*Listbox.background","#ffffff")
        self.w.option_add("*TCombobox*Listbox.foreground","#22243a")
        self.w.option_add("*TCombobox*Listbox.selectBackground","#e9d7f3")
        self.w.option_add("*TCombobox*Listbox.selectForeground","#22243a")
        self.style.configure("Nav.TFrame", background="#25204b" if self.dark else "#e4d5f0")
        self.style.configure("Nav.TLabel", background="#25204b" if self.dark else "#e4d5f0", foreground=fg)
        self.style.configure("Nav.TButton", background="#392d66", foreground="#ffffff", padding=8)
        self.style.configure("ActiveNav.TButton", background="#cf137e", foreground="#ffffff", padding=8)
        self.style.configure("Accent.TButton", background="#c91382", foreground="#ffffff", padding=8)
        self.style.configure("Instrument.TCheckbutton", font=("Segoe UI",9), padding=0, background=bg, foreground=fg)
        self.style.map("Accent.TButton", background=[("active", "#ee36a2"), ("disabled", "#675268")])
        self.style.map("ActiveNav.TButton", background=[("active", "#ee36a2")])
        self.style.configure("MutedHeart.TButton", foreground="#9692a7", font=("Segoe UI", 13))
        self.style.configure("FavoriteHeart.TButton", foreground="#ff3465", font=("Segoe UI", 13))
        self.style.configure("Good.TLabel", foreground="#43cfa3", background=bg)
        self.style.configure("Warn.TLabel", foreground="#f3b94c", background=bg)
        self.w.configure(background=bg)
        for widget in (getattr(self, "lyrics", None), getattr(self, "home_history", None), getattr(self, "create_history", None)):
            if widget is not None:
                widget.configure(background="#ffffff", foreground="#22243a", selectbackground="#dbc5f1", selectforeground="#22243a")
        if hasattr(self, "lyrics"):
            self.lyrics.configure(insertbackground="#22243a")
        if hasattr(self, "topic"):
            self.topic.configure(background="#ffffff", foreground="#22243a", insertbackground="#22243a")
        if hasattr(self,"edit_lyrics"):
            self.edit_lyrics.configure(background="#ffffff",foreground="#22243a",insertbackground="#22243a")
        for scroll in (getattr(self, "home_scroll", None), getattr(self, "form_scroll", None),getattr(self,"composer_scroll",None)):
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
        field = ttk.Combobox(parent, values=values, state="readonly",width=8)
        field.current(0)
        field.pack(fill="x", anchor="w")
        return field

    def button(self, parent, label, action):
        ttk.Button(parent, text=label, command=action).pack(anchor="w", pady=3, padx=3)

    def run(self, function, action="Operación", download=False):
        if self.busy or self.recording.active:
            return
        self.busy = True
        self.cancel.clear()
        self.start_time = time.monotonic()
        self.stage = action
        self.action = action
        self.download_sample = None
        self.piano.pack(side="right",padx=5)
        self.piano.start()
        self.generate_button.state(["disabled"])
        self.compose_button.state(["disabled"])
        self.edit_button.state(["disabled"])
        self.voice_apply_button.state(["disabled"])
        self.replace_voice_button.state(["disabled"])
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
            elif kind == "hardware":
                self.hardware = text
                self.update_hardware_summary(text)
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
            elif kind == "text_runtime":
                self.text_runtime_status.configure(text=text)
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
            elif kind == "voice_profile":
                self.refresh_voices()
                self.voice_status.configure(text="Perfil guardado localmente.")
            elif kind == "voice_components":
                self.voice_status.configure(text=text)
            elif kind == "lyrics":
                self.lyrics.delete("1.0", "end")
                self.lyrics.insert("1.0", text)
                self.update_copy_button()
                self.lyric_notice.configure(text="Letra creada. Revísala y edítala antes de generar música.")
                self.hide_composer()
            elif kind == "edited":
                self.edit_result_path = self.runs/text/"song.wav"
                self.new_version = text
                self.edit_status.configure(text="Nueva versión guardada. El original no se modificó.")
            elif kind == "song":
                label, version = text
                self.latest.configure(text=label)
                self.new_version = version
                self.hide_composer()
                # Do not interrupt navigation or playback when a new song arrives.
            else:
                self.busy = False
                self.progress.stop()
                self.piano.stop()
                self.piano.pack_forget()
                self.progress.pack_forget()
                self.cancel_button.pack_forget()
                self.generate_button.state(["!disabled"])
                self.compose_button.state(["!disabled"])
                self.edit_button.state(["!disabled"])
                self.voice_apply_button.state(["!disabled"])
                self.replace_voice_button.state(["!disabled"])
                self.status.set(text)
                if self.action=="Detectando recursos":
                    callback=self.pending_hardware_action
                    self.pending_hardware_action=None
                    if kind=="done" and text=="Recursos actualizados" and callback and not self.closing:
                        self.w.after_idle(callback)
                if kind == "error" and not self.closing:
                    if self.action == "Edición musical":
                        self.edit_status.configure(text=text)
                    elif self.action == "Composición":
                        self.lyric_notice.configure(text=text)
                    else:
                        messagebox.showerror("Noel Music AI", text)
                self.library()
                if kind == "done" and not self.closing and self.action in ("Instalación de modelos", "Instalación del motor", "Importar modelo", "Instalar motor Qwen", "Instalación completa"):
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
                playing=self.player.send("status noelplayer mode")=="playing" and position<duration
                self.sync_card_playback(self.playing_file if playing else None)
                if self.playing_file and playing:
                    for i, level in enumerate(spectrum(self.playing_file, position)):
                        self.spectrum.create_rectangle(i*10+1, 30-28*level, i*10+8, 30, fill="#36d1cf", outline="")
            except (OSError, ValueError):
                pass
        else:
            self.sync_card_playback(None)
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
        self.discard_recording()
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
        key = next((k for k, v in catalog().items() if v[0] == name), None)
        path = model_path(self.models, key) if key else self.models/name
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
            self.events.put(("hardware",info))
            gpu = info["gpu"] or {}
            rows = [f"{info['os']} {info['architecture']} · Python {sys.version.split()[0]}",
                    f"{gpu.get('name', 'GPU no detectada')} · controlador {gpu.get('driver','—')} · VRAM libre {gpu.get('free_mib','—')} MiB",
                    f"RAM libre: {(info['ram_available'] or 0)/2**30:.2f} GiB · Disco libre: {info['disk_free']/2**30:.1f} GiB",
                    f"Motor musical: {'presente' if self.binary().exists() else 'falta · descargue el paquete Windows de GitHub Actions'}"]
            inventory = {}
            missing = not self.binary().exists()
            for key, (name, size, digest) in catalog().items():
                ok = self.check_model(name, size, digest)
                path = model_path(self.models,key)
                state = "✓ Instalado y verificado" if ok else "⚠ Requiere reparación" if path.exists() else "↓ Descarga pendiente" if path.with_suffix(".gguf.part").exists() else "○ No descargado"
                inventory[key] = f"{state} · {size/1e6:.0f} MB · {'Requerido por modelo predeterminado' if key in required_music(self.music_default) else 'Opcional'}"
                missing = missing or (key in required_music(self.music_default) and not ok)
                rows.append(f"{name} · {state}")
            self.events.put(("inventory", ("\n".join(rows), inventory, missing)))
            self.events.put(("text_runtime", "✓ Motor Qwen instalado y verificado" if text_engine.runtime_ready(RUNTIME,self.device_mode) else "Motor Qwen no instalado para "+DEVICES[self.device_mode]))
        self.run(work, "Diagnóstico")

    def install(self, keys):
        if self.busy or not keys:
            return
        mode = self.device_mode
        text_runtime_needed = any(k in TEXT_BASES for k in keys) and not (text_engine.runtime_dir(RUNTIME,mode)/"llama-server.exe").is_file()
        total = sum(catalog()[k][1] for k in keys)
        extra = sum(x[1] for x in text_engine.ASSETS[text_engine.kind(mode)]) if text_runtime_needed else 0
        note = f" Incluye motor llama.cpp para {DEVICES[mode]} (hasta {extra/1e6:.0f} MB)." if text_runtime_needed else ""
        if not messagebox.askyesno("Modelos seleccionados", f"Verificar y descargar archivos faltantes o dañados (hasta {(total+extra)/1e9:.2f} GB) desde Hugging Face y GitHub?"+note):
            return
        def work():
            self.verified.clear()
            from .models import install
            install(self.models, True, keys, repair=True, cancel=self.cancel,
                    progress=lambda name, n, total: self.events.put(("progress", (f"{name} · {n/1e6:.1f} / {total/1e6:.1f} MB", n, total))))
            for key in keys:
                name, size, _ = catalog()[key]
                self.events.put(("model", (key, f"✓ Instalado y verificado · {size/1e6:.0f} MB · {'Requerido por modelo predeterminado' if key in required_music(self.music_default) else 'Opcional'}")))
            if text_runtime_needed:
                text_engine.install_runtime(RUNTIME,mode,self.cancel,
                                            lambda n,b,t:self.events.put(("progress",(n,b,t))))
            return "Modelos verificados"
        self.run(work, "Instalación de modelos", download=True)

    def musical_caption(self):
        return build_caption(self.genres[self.genre.get()], self.mood.get(), self.setting.get(),
                             "Instrumental" if self.instrumental.get() else "Automática" if self.voice.get() in self.voice_profiles else self.voice.get(), self.prompt.get(),
                             [name for name,var in self.instrument_vars.items() if var.get()] if self.instrument_mode.get()=="manual" else [])

    @contextmanager
    def engine_session(self, optional=(), music=None):
        music = music or self.music_default
        binary = self.binary()
        if not binary.is_file():
            raise ValueError("Falta el motor. Instálalo en Configuración.")
        from .runtime import verify_engine
        self.events.put(("stage", "Verificando componentes"))
        verify_engine(binary)
        gpu = snapshot()["gpu"]
        if self.device_mode != "cpu" and not gpu:
            raise ValueError("No se detectó GPU NVIDIA. Selecciona CPU o consulta Diagnóstico.")
        device = "CPU" if self.device_mode == "cpu" else "CUDA0"
        for key in [*required_music(music), *optional]:
            name, size, digest = catalog()[key]
            if self.cancel.is_set():
                raise InterruptedError("Cancelado")
            if not self.check_model(name, size, digest):
                raise ValueError(f"Instala o verifica {name} en Modelos.")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        args = [str(binary), "--device", device, "--host", "127.0.0.1", "--port", str(port),
                "--models", str(self.models), "--max-batch", "1", "--vae-chunk",
                "128" if not gpu or gpu["free_mib"] < 6000 else "256", "--vae-overlap", "32"]
        self.events.put(("stage", "Iniciando motor "+device))
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
                        props = engine.ready(music)
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

    def build_voices(self,parent):
        scroll=ScrollFrame(parent)
        scroll.pack(fill="both",expand=True)
        form=scroll.inner
        ttk.Label(form,text="Mis voces",font=("Segoe UI",22,"bold")).pack(anchor="w")
        ttk.Label(form,text="Registra tu voz o una voz autorizada. El perfil es local y reutilizable; no entrena un modelo individual.",wraplength=620).pack(anchor="w",pady=6)
        self.field_label(form,"Nombre del perfil","Nombre para reconocer la voz en Crear música y Editor musical.")
        self.voice_name=ttk.Entry(form)
        self.voice_name.pack(fill="x")
        self.voice_kind=self.combo(form,"Tipo de muestra",["Hablada","Cantada"],"Una muestra cantada limpia puede mejorar el resultado.")
        ttk.Label(form,text="Lee o canta con naturalidad: Cada día es una nueva oportunidad para imaginar, soñar y crear. La música expresa lo que sentimos.",wraplength=620,style="Field.TLabel").pack(anchor="w",pady=6)
        row=ttk.Frame(form)
        row.pack(fill="x")
        self.record_button=ttk.Button(row,text="● Grabar (hasta 30 s)",command=self.start_voice_recording,style="Accent.TButton")
        self.record_button.pack(side="left",padx=2)
        ttk.Button(row,text="■ Detener",command=self.finish_voice_recording).pack(side="left",padx=2)
        ttk.Button(row,text="Importar WAV",command=self.import_voice_sample).pack(side="left",padx=2)
        ttk.Button(row,text="▶ Escuchar muestra",command=lambda:self.play_editor_file(self.voice_sample)).pack(side="left",padx=2)
        self.voice_sample=None
        self.voice_sample_label=ttk.Label(form,text="Sin muestra. Recomendamos 15–30 s sin música.")
        self.voice_sample_label.pack(anchor="w",pady=5)
        self.voice_consent=tk.BooleanVar(value=False)
        ttk.Checkbutton(form,text="Es mi voz o tengo autorización para utilizarla.",variable=self.voice_consent).pack(anchor="w")
        ttk.Button(form,text="Guardar perfil",command=self.save_voice_profile,style="Accent.TButton").pack(fill="x",pady=6)
        ttk.Label(form,text="Biblioteca de voces",style="Field.TLabel",font=("Segoe UI",14,"bold")).pack(anchor="w")
        self.voice_list=tk.Listbox(form,height=4,background="white",foreground="#22243a",exportselection=False)
        self.voice_list.pack(fill="x")
        row=ttk.Frame(form)
        row.pack(fill="x",pady=4)
        ttk.Button(row,text="▶ Escuchar perfil",command=self.play_voice_profile).pack(side="left",padx=2)
        ttk.Button(row,text="Guardar WAV",command=self.export_voice_profile).pack(side="left",padx=2)
        ttk.Button(row,text="Eliminar perfil",command=self.delete_voice_profile).pack(side="left",padx=2)
        ttk.Label(form,text="Aplicar voz a una canción existente",style="Field.TLabel",font=("Segoe UI",14,"bold")).pack(anchor="w",pady=(8,3))
        ttk.Label(form,text="Selecciona el perfil arriba y un WAV propio/autorizado. Se conserva una copia del instrumental extraído; la separación y el timbre son aproximados.",wraplength=620).pack(anchor="w")
        self.voice_apply_button=ttk.Button(form,text="Sustituir cantante de un WAV",command=lambda:self.refresh_then(lambda:self.apply_existing_voice(False)))
        self.voice_apply_button.pack(fill="x",pady=3)
        ttk.Button(form,text="Aplicar a canción seleccionada en biblioteca",command=lambda:self.refresh_then(lambda:self.apply_existing_voice(True))).pack(fill="x",pady=3)
        ttk.Button(form,text="Instalar componentes de clonación",command=self.install_voice_components).pack(fill="x",pady=5)
        self.voice_status=ttk.Label(form,text="HTDemucs Q8 + Seed-VC Q8 + audio.cpp · experimentales, instalación opcional.",wraplength=620)
        self.voice_status.pack(anchor="w")

    def refresh_voices(self):
        items=voice_profiles.profiles(self.voice_root)
        old=self.voice.get()
        previous=self.edit_target_voice.get()
        self.voice_profiles={"Perfil · "+p["name"]:p for p in items}
        self.voice.configure(values=[v for v in VOICES if v!="Instrumental"]+list(self.voice_profiles))
        self.voice.set(old if old in self.voice["values"] else "Automática")
        self.edit_target_voice.configure(values=["Original / automática",*self.voice_profiles])
        self.edit_target_voice.set(previous if previous in self.edit_target_voice["values"] else "Original / automática")
        selected=self.voice_list.curselection()
        self.voice_list.delete(0,"end")
        for label,p in self.voice_profiles.items():
            self.voice_list.insert("end",f"{label} · {p['kind']} · {p['seconds']:.1f} s")
        if items:
            self.voice_list.selection_set(min(selected[0],len(items)-1) if selected else 0)

    def selected_profile(self):
        selected=self.voice_list.curselection()
        if not selected:
            messagebox.showinfo("Mis voces","Selecciona un perfil.")
            return None
        return list(self.voice_profiles.values())[selected[0]]

    def discard_recording(self):
        if self.voice_record_timer:
            self.w.after_cancel(self.voice_record_timer)
            self.voice_record_timer=None
        try:
            self.recording.close()
        except OSError:
            pass
        if self.voice_temp:
            self.voice_temp.cleanup()
            self.voice_temp=None

    def start_voice_recording(self):
        if self.busy or self.recording.active:
            return
        if not self.voice_consent.get():
            messagebox.showinfo("Mis voces","Confirma que autorizas la grabación.")
            return
        self.stop_player()
        self.discard_recording()
        self.voice_sample=None
        self.voice_temp=tempfile.TemporaryDirectory(prefix="noel-voice-")
        try:
            self.recording.start()
            self.record_start=time.monotonic()
            self.record_button.configure(state="disabled")
            self.record_tick()
        except (OSError,ValueError) as exc:
            self.discard_recording()
            self.record_button.configure(state="normal")
            messagebox.showerror("Micrófono",str(exc))

    def record_tick(self):
        self.voice_record_timer=None
        elapsed=time.monotonic()-self.record_start
        self.voice_sample_label.configure(text=f"Grabando… {int(elapsed)} / 30 s")
        if elapsed>=30:
            self.finish_voice_recording()
        elif self.recording.active:
            self.voice_record_timer=self.w.after(200,self.record_tick)

    def finish_voice_recording(self):
        if not self.recording.active:
            return
        if self.voice_record_timer:
            self.w.after_cancel(self.voice_record_timer)
            self.voice_record_timer=None
        try:
            path=Path(self.voice_temp.name)/"sample.wav"
            self.recording.stop(path)
            self.voice_sample=path
            self.voice_sample_label.configure(text="Grabación lista. Escucha y guarda el perfil.")
        except OSError as exc:
            messagebox.showerror("Micrófono",str(exc))
        finally:
            self.record_button.configure(state="normal")

    def import_voice_sample(self):
        if self.busy or self.recording.active:
            return
        path=filedialog.askopenfilename(filetypes=[("WAV PCM 16 bits","*.wav")])
        if path:
            self.stop_player()
            self.discard_recording()
            self.voice_sample=Path(path)
            self.voice_consent.set(False)
            self.voice_sample_label.configure(text=self.voice_sample.name)

    def save_voice_profile(self):
        if self.busy or self.recording.active or not self.voice_sample:
            return
        name=self.voice_name.get()
        consent=self.voice_consent.get()
        kind=self.voice_kind.get()
        source=self.voice_sample
        def work():
            data=voice_profiles.create_profile(self.voice_root,source,name,consent,kind)
            self.events.put(("voice_profile",data))
            return "Perfil vocal guardado."
        self.run(work,"Guardando voz")

    def play_voice_profile(self):
        profile=self.selected_profile()
        if profile:
            try:
                self.play_editor_file(voice_profiles.reference(self.voice_root,profile))
            except (OSError,ValueError) as exc:
                messagebox.showerror("Mis voces",str(exc))

    def export_voice_profile(self):
        profile=self.selected_profile()
        if not profile:
            return
        path=filedialog.asksaveasfilename(defaultextension=".wav",filetypes=[("Audio WAV","*.wav")])
        if path:
            try:
                export_audio(voice_profiles.reference(self.voice_root,profile),path,"wav")
            except (OSError,ValueError) as exc:
                messagebox.showerror("Mis voces",str(exc))

    def delete_voice_profile(self):
        if self.busy or self.recording.active:
            return
        profile=self.selected_profile()
        if profile and messagebox.askyesno("Mis voces","¿Eliminar este perfil local? Las canciones ya generadas se conservan."):
            try:
                self.stop_player()
                voice_profiles.remove_profile(self.voice_root,profile)
                self.refresh_voices()
            except (OSError,ValueError) as exc:
                messagebox.showerror("Mis voces",str(exc))

    def install_voice_components(self):
        if self.busy or self.recording.active:
            return
        mode=self.device_mode
        total=sum(x[1] for x in voice_engine.MODELS.values())+sum(x[1] for x in voice_engine.ASSETS[voice_engine.kind(mode)])
        if not messagebox.askyesno("Componentes vocales",f"Descargar desde Hugging Face y GitHub hasta {total/1e9:.2f} GB para {DEVICES[mode]}? Se verifican los archivos. Modelos de terceros sujetos a sus licencias."):
            return
        def work():
            voice_engine.install(RUNTIME,self.models,mode,self.cancel,lambda n,b,t:self.events.put(("progress",(n,b,t))))
            self.events.put(("voice_components","Componentes descargados y verificados. Inferencia experimental."))
            return "Componentes vocales instalados."
        self.run(work,"Instalación vocal",download=True)

    def voice_precheck(self):
        mode=self.device_mode
        if not voice_engine.binary(RUNTIME,mode,verify=False) or not all(voice_engine.model_path(self.models,k).is_file() for k in voice_engine.MODELS):
            messagebox.showinfo("Mis voces","Instala primero HTDemucs, Seed-VC y audio.cpp desde Mis voces.")
            self.show_page("Mis voces")
            return False
        info=self.hardware or {}
        gpu=info.get("gpu") or {}
        if mode!="cpu" and not gpu:
            messagebox.showinfo("Mis voces","No se detectó NVIDIA. Ajusta el procesador en Configuración.")
            self.show_page("Configuración")
            return False
        if mode=="cpu" or (gpu.get("free_mib") or 0)<6000 or (info.get("ram_available") or 0)<6*2**30:
            return messagebox.askyesno("Recursos de conversión vocal","La conversión puede tardar mucho o agotar memoria. Recomendamos una prueba de 15–30 segundos. ¿Continuar?")
        return True

    def apply_voice_result(self,result,profile,title=None):
        source=self.runs/result["version"]/"song.wav"
        request=json.loads(source.with_name("version.json").read_text("utf-8"))["request"]
        return voice_engine.convert(RUNTIME,self.models,self.runs,source,voice_profiles.reference(self.voice_root,profile),
                                    profile,self.device_mode,self.cancel,lambda s:self.events.put(("stage",s)),request,title)

    def replace_editor_voice(self):
        if self.busy or not self.edit_source or not self.edit_consent.get():
            messagebox.showinfo("Editor musical","Selecciona un WAV y confirma la autorización.")
            return
        profile=self.voice_profiles.get(self.edit_target_voice.get())
        if not profile:
            messagebox.showinfo("Editor musical","Selecciona un perfil vocal guardado; cambia de Repaint a otro modo si es necesario.")
            return
        if not self.voice_precheck():
            return
        source=self.edit_source
        # Preserve original metadata only if it belongs to the selected source; never substitute edited lyrics.
        request=None
        manifest=source.with_name("version.json")
        if source.parent.parent==self.runs and manifest.is_file():
            request=json.loads(manifest.read_text("utf-8"))["request"]
        def work():
            result=voice_engine.convert(RUNTIME,self.models,self.runs,source,voice_profiles.reference(self.voice_root,profile),
                                        profile,self.device_mode,self.cancel,lambda s:self.events.put(("stage",s)),request)
            self.events.put(("edited",result["version"]))
            return "Nueva versión vocal guardada sin regenerar la música."
        self.run(work,"Edición musical")

    def apply_existing_voice(self,library=False):
        if self.busy or self.recording.active:
            return
        profile=self.selected_profile()
        if not profile:
            return
        request=None
        title=None
        if library:
            selection=self.history.curselection()
            if not selection:
                messagebox.showinfo("Mis voces","Selecciona una canción en la biblioteca primero.")
                return
            index=selection[0]
            source=self.files[index]
            request=json.loads(source.with_name("version.json").read_text("utf-8"))["request"]
            title=self.song_data[index]["title"]
        else:
            path=filedialog.askopenfilename(filetypes=[("WAV PCM","*.wav")])
            if not path:
                return
            source=Path(path)
        if not messagebox.askyesno("Mis voces","¿Confirmas que tienes autorización sobre la grabación de origen y la voz elegida?"):
            return
        if not self.voice_precheck():
            return
        def work():
            result=voice_engine.convert(RUNTIME,self.models,self.runs,source,voice_profiles.reference(self.voice_root,profile),
                                        profile,self.device_mode,self.cancel,lambda s:self.events.put(("stage",s)),request,title)
            self.events.put(("song",("Conversión vocal lista",result["version"])))
            return "Nueva versión vocal guardada."
        self.run(work,"Conversión vocal")

    def build_editor(self, parent):
        scroll = ScrollFrame(parent)
        scroll.pack(fill="both", expand=True)
        form=scroll.inner
        ttk.Label(form,text="Editor musical",font=("Segoe UI",22,"bold")).pack(anchor="w")
        ttk.Label(form,text="Experimenta con audio propio o autorizado. Todas las ediciones crean una nueva versión.",wraplength=650).pack(anchor="w",pady=6)
        self.edit_mode=self.combo(form,"Operación",list(editor.MODES.values()),"Cover conserva referencias aproximadas; Repaint modifica un intervalo; referencia vocal orienta el timbre, no clona una identidad exacta.")
        self.edit_mode.bind("<<ComboboxSelected>>",self.update_editor)
        self.edit_source=None
        self.edit_result_path=None
        row=ttk.Frame(form)
        row.pack(fill="x",pady=5)
        ttk.Button(row,text="Abrir WAV",command=self.pick_edit_source).pack(side="left",padx=2)
        ttk.Button(row,text="Usar canción seleccionada",command=self.pick_library_source).pack(side="left",padx=2)
        ttk.Button(row,text="▶ Original",command=lambda:self.play_editor_file(self.edit_source)).pack(side="left",padx=2)
        self.edit_source_label=ttk.Label(form,text="Sin audio de referencia",wraplength=650)
        self.edit_source_label.pack(anchor="w")
        self.edit_explanation=ttk.Label(form,wraplength=650)
        self.edit_explanation.pack(anchor="w",pady=6)
        self.field_label(form,"Descripción musical","Describe el estilo a conservar o el nuevo arreglo.")
        self.edit_caption=ttk.Entry(form)
        self.edit_caption.insert(0,"Preserve the musical arrangement, rhythm, melody and vocal character of the reference")
        self.edit_caption.pack(fill="x")
        self.field_label(form,"Letra nueva","Para editar un fragmento introduce la letra completa actualizada, incluyendo las partes no editadas.")
        self.edit_lyrics=tk.Text(form,height=8,wrap="word")
        self.edit_lyrics.pack(fill="x")
        self.edit_language=self.combo(form,"Idioma",list(LANGUAGES),"Idioma del canto.")
        self.edit_model=self.combo(form,"Modelo",list(MUSIC.values()),"Turbo Q8 recomendado inicialmente; otras variantes experimentales.")
        self.edit_model.set(MUSIC[self.music_default])
        self.edit_target_voice=self.combo(form,"Voz guardada (opcional)",["Original / automática"],"Aplicar un perfil después de la edición. No se aplica a Repaint con PCM exacto.")
        self.cover_box=ttk.Frame(form)
        self.edit_fidelity=self.combo(self.cover_box,"Fidelidad a la referencia",list(editor.FIDELITY),"Alta favorece conservar la fuente, pero puede dificultar cambios de letra.")
        self.edit_fidelity.set("Equilibrada")
        self.repaint_box=ttk.Frame(form)
        ttk.Label(self.repaint_box,text="Intervalo de edición (segundos)").pack(anchor="w")
        times=ttk.Frame(self.repaint_box)
        times.pack(fill="x")
        self.edit_start=ttk.Entry(times,width=10)
        self.edit_start.insert(0,"0")
        self.edit_start.pack(side="left")
        ttk.Label(times,text=" a ").pack(side="left")
        self.edit_end=ttk.Entry(times,width=10)
        self.edit_end.insert(0,"10")
        self.edit_end.pack(side="left")
        self.exact_pcm=tk.BooleanVar(value=True)
        ttk.Checkbutton(self.repaint_box,text="Conservar PCM exacto fuera del fragmento (48 kHz estéreo)",variable=self.exact_pcm).pack(anchor="w")
        self.voice_box=ttk.Frame(form)
        ttk.Label(self.voice_box,text="Duración de nueva canción (segundos)").pack(anchor="w")
        self.edit_duration=ttk.Entry(self.voice_box,width=12)
        self.edit_duration.insert(0,"30")
        self.edit_duration.pack(anchor="w")
        self.edit_consent=tk.BooleanVar(value=False)
        self.edit_consent_widget=ttk.Checkbutton(form,text="Tengo autorización para editar el audio y utilizar las voces de referencia.",variable=self.edit_consent)
        self.edit_consent_widget.pack(anchor="w",pady=6)
        self.edit_button=ttk.Button(form,text="✦ Generar versión editada",style="Accent.TButton",command=lambda:self.refresh_then(self.run_editor))
        self.edit_button.pack(fill="x",pady=5)
        self.replace_voice_button=ttk.Button(form,text="Sustituir cantante sin regenerar música",command=lambda:self.refresh_then(self.replace_editor_voice))
        self.replace_voice_button.pack(fill="x",pady=3)
        self.edit_status=ttk.Label(form,text="Pista instrumental idéntica + letra nueva: módulo de separación y síntesis vocal pendiente.",wraplength=650)
        self.edit_status.pack(anchor="w",pady=6)
        result=ttk.Frame(form)
        result.pack(fill="x")
        ttk.Button(result,text="▶ Escuchar resultado",command=lambda:self.play_editor_file(self.edit_result_path)).pack(side="left",padx=2)
        ttk.Button(result,text="Ver resultado en biblioteca",command=lambda:self.show_page("Crear música")).pack(side="left",padx=2)
        self.update_editor()

    def update_editor(self,_=None):
        mode=next(k for k,v in editor.MODES.items() if v==self.edit_mode.get())
        for box in (self.cover_box,self.repaint_box,self.voice_box):
            box.pack_forget()
        box={"cover":self.cover_box,"repaint":self.repaint_box,"voice":self.voice_box}[mode]
        box.pack(fill="x",before=self.edit_consent_widget,pady=5)
        self.edit_explanation.configure(text={
            "cover":"Regenera toda la mezcla guiándose por el original. No conserva exactamente la pista ni la identidad vocal.",
            "repaint":"Regenera únicamente el intervalo solicitado. Con PCM exacto activo, los datos fuera del intervalo se copian del WAV original; puede haber una unión audible.",
            "voice":"Crea música nueva usando un fragmento vocal autorizado de 1–30 segundos como referencia tímbrica. No garantiza la misma voz."
        }[mode])
        self.edit_target_voice.configure(state="disabled" if mode=="repaint" else "readonly")
        if mode=="repaint":
            self.edit_target_voice.current(0)
        self.edit_consent.set(False)

    def set_edit_source(self,path,lyrics=None,caption=None):
        try:
            _,duration,_=editor.read_wav(path)
        except Exception as exc:
            messagebox.showerror("Editor musical",str(exc))
            return
        self.edit_source=Path(path)
        self.edit_consent.set(False)
        self.edit_source_label.configure(text=f"{self.edit_source.name} · {duration:.2f} s")
        if lyrics is not None:
            self.edit_lyrics.delete("1.0","end")
            self.edit_lyrics.insert("1.0",lyrics)
        if caption:
            self.edit_caption.delete(0,"end")
            self.edit_caption.insert(0,caption)
        self.edit_end.delete(0,"end")
        self.edit_end.insert(0,str(min(10, duration)))

    def pick_edit_source(self):
        if self.busy:
            return
        path=filedialog.askopenfilename(filetypes=[("WAV PCM","*.wav")])
        if path:
            self.set_edit_source(path)

    def pick_library_source(self):
        if self.busy:
            return
        if not self.history.curselection():
            messagebox.showinfo("Editor musical","Selecciona primero una canción en Inicio o Crear música.")
            return
        index=self.history.curselection()[0]
        path=self.files[index]
        manifest=json.loads(path.with_name("version.json").read_text("utf-8"))
        request=manifest["request"]
        self.set_edit_source(path,request.get("lyrics",""),request.get("caption",""))

    def play_editor_file(self,path):
        if path is None or not path.is_file():
            messagebox.showinfo("Editor musical","Selecciona un audio o genera una versión.")
            return
        try:
            self.player.open(path)
            self.playing_file=path
            self.now_playing.configure(text=path.name)
            self.volume_changed(self.volume.get())
            peaks=envelope(path)
            self.waveform.delete("all")
            width=self.waveform.winfo_width()/len(peaks)
            for i,peak in enumerate(peaks):
                self.waveform.create_line(i*width,15-14*peak,i*width,16+14*peak,fill="#ee61c0")
        except (OSError,ValueError) as exc:
            messagebox.showerror("Reproducción",str(exc))

    def run_editor(self):
        if self.busy:
            return
        if self.edit_source is None or not self.edit_consent.get():
            messagebox.showinfo("Editor musical","Selecciona audio y confirma la autorización.")
            return
        mode=next(k for k,v in editor.MODES.items() if v==self.edit_mode.get())
        model=next(k for k,v in MUSIC.items() if v==self.edit_model.get())
        source=self.edit_source
        caption=self.edit_caption.get().strip()
        lyrics=self.edit_lyrics.get("1.0","end").strip()
        language=LANGUAGES[self.edit_language.get()][0]
        try:
            start=float(self.edit_start.get()) if mode=="repaint" else 0.
            end=float(self.edit_end.get()) if mode=="repaint" else 10.
            seconds=int(self.edit_duration.get()) if mode=="voice" else 30
        except ValueError:
            messagebox.showerror("Editor musical","Revisa los tiempos.")
            return
        if not self.preflight("editor",model):
            return
        fidelity=self.edit_fidelity.get()
        preserve=self.exact_pcm.get()
        profile=self.voice_profiles.get(self.edit_target_voice.get()) if mode!="repaint" else None
        if profile and not self.voice_precheck():
            return
        self.edit_status.configure(text="Preparando edición experimental…")
        def work():
            with self.engine_session(music=model) as (engine,props):
                self.events.put(("stage","Editando audio con ACE-Step"))
                result=editor.edit_song(engine,props,self.runs,source,mode,caption,lyrics,language,model,
                                        secrets.randbelow(2**31),fidelity,start,end,seconds,True,preserve)
            if profile:
                try:
                    result=self.apply_voice_result(result,profile)
                except (InterruptedError, OSError, ValueError, RuntimeError) as exc:
                    raise type(exc)("La edición original se guardó; no se completó la conversión vocal: "+str(exc)) from exc
            self.events.put(("edited",result["version"]))
            return "Versión editada guardada."
        self.run(work,"Edición musical")

    def update_copy_button(self):
        enabled=bool(self.lyrics.get("1.0","end").strip()) and not self.instrumental.get()
        self.copy_button.configure(state="normal" if enabled else "disabled")

    def lyrics_changed(self,_=None):
        self.lyrics.edit_modified(False)
        self.update_copy_button()

    def copy_lyrics(self):
        lyrics=self.lyrics.get("1.0","end").strip()
        if not lyrics or self.instrumental.get():
            return
        self.w.clipboard_clear()
        self.w.clipboard_append(lyrics)
        self.status.set("Letra copiada al portapapeles.")

    def download_all(self):
        if self.busy:
            return
        modes=["cpu","gpu"] if self.hardware and self.hardware.get("gpu") else ["cpu"]
        total=sum(x[1] for x in catalog().values())
        extra=sum(x[1] for device in modes for x in text_engine.ASSETS[text_engine.kind(device)])
        voice_total=sum(x[1] for x in voice_engine.MODELS.values())+sum(x[1] for mode in modes for x in voice_engine.ASSETS[voice_engine.kind(mode)])
        note=f"Todos los modelos del catálogo: hasta {total/1e9:.2f} GB. Motores de letras: hasta {extra/1e9:.2f} GB. Componentes vocales opcionales (incluidos en esta descarga): hasta {voice_total/1e9:.2f} GB, sujetos a licencias de terceros. Si el motor musical falta o está dañado, también se descargará el portable compatible. Los archivos válidos se conservan. Se requiere espacio adicional para extraer los motores. ¿Comenzar?"
        if not messagebox.askyesno("Descargar todo",note):
            return
        directory=self.models
        def work():
            from .runtime import verify_engine
            from .models import install
            try:
                binary=self.binary()
                if not binary.is_file():
                    raise FileNotFoundError(binary)
                verify_engine(binary)
            except (OSError,ValueError):
                asset=available()
                self.events.put(("stage","Instalando motor musical"))
                install_engine(ROOT,asset,self.cancel,lambda n,t:self.events.put(("progress",("Motor musical",n,t))))
            self.verified.clear()
            install(directory,True,list(catalog()),repair=True,cancel=self.cancel,
                    progress=lambda name,n,t:self.events.put(("progress",(name,n,t))))
            for device in modes:
                if self.cancel.is_set():
                    raise InterruptedError("Cancelado")
                text_engine.install_runtime(RUNTIME,device,self.cancel,lambda name,n,t:self.events.put(("progress",(name,n,t))))
                voice_engine.install(RUNTIME,directory,device,self.cancel,lambda name,n,t:self.events.put(("progress",(name,n,t))))
            return "Todos los modelos del catálogo y motores seleccionados están instalados."
        self.run(work,"Instalación completa",download=True)

    def apply_recommendation(self,rec):
        self.device_setting.set(DEVICES[rec["device"]])
        self.music_setting.set(MUSIC[rec["music"]])
        self.lyrics_setting.set(LYRIC_MODELS[rec["lyrics"]])

    def update_hardware_summary(self,info):
        gpu=info.get("gpu") or {}
        ram=(info.get("ram_available") or 0)/2**30
        self.hardware_label.configure(text=f"{gpu.get('name','CPU · sin NVIDIA detectada')}  |  RAM libre: {ram:.1f} GiB  |  Hilos: {info.get('cpu_threads') or '—'}")
        rec=recommend(info)
        self.recommend_label.configure(text="Sugeridos: "+MUSIC[rec["music"]]+" / "+LYRIC_MODELS[rec["lyrics"]])

    def recommend_settings(self):
        if self.busy:
            return
        if self.hardware is None:
            self.inspect()
            return
        self.apply_recommendation(recommend(self.hardware))
        self.status.set("Recomendación seleccionada. Pulsa Guardar cambios para aplicarla.")

    def refresh_then(self, callback):
        if self.busy or self.recording.active:
            return
        self.pending_hardware_action=callback
        def work():
            info=snapshot()
            if self.cancel.is_set():
                raise InterruptedError("Cancelado")
            self.events.put(("hardware",info))
            return "Recursos actualizados"
        self.run(work,"Detectando recursos")

    def preflight(self,purpose,selected):
        if self.hardware is None:
            self.status.set("Completa el diagnóstico antes de continuar.")
            self.inspect()
            return False
        warning=operation_warning(self.hardware,self.device_mode,purpose,selected)
        if not warning:
            return True
        signature=(purpose,self.device_mode,selected,warning)
        if signature in self.advice_seen:
            return True
        dialog=tk.Toplevel(self.w)
        dialog.withdraw()
        dialog.title("Recursos del equipo")
        dialog.transient(self.w)
        frame=ttk.Frame(dialog,padding=16)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text={"lyrics":"Generación de letras","music":"Generación musical","editor":"Edición musical"}[purpose],
                  style="Field.TLabel",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,8))
        ttk.Label(frame,text=warning,wraplength=420,justify="left").pack(anchor="w")
        answer=tk.StringVar(value="cancel")
        def choose(value):
            answer.set(value)
            dialog.destroy()
        ttk.Button(frame,text="Continuar",style="Accent.TButton",command=lambda:choose("keep")).pack(fill="x",pady=(12,3))
        ttk.Button(frame,text="Ajustar modelos",command=lambda:choose("settings")).pack(fill="x",pady=3)
        dialog.protocol("WM_DELETE_WINDOW",lambda:choose("cancel"))
        center_dialog(dialog,self.w)
        dialog.grab_set()
        self.w.wait_window(dialog)
        if answer.get()=="settings":
            self.show_page("Configuración")
            return False
        if answer.get()=="keep":
            self.advice_seen.add(signature)
            return True
        return False

    def save_preferences(self):
        if self.busy:
            return
        device = next(k for k,v in DEVICES.items() if v==self.device_setting.get())
        music = next(k for k,v in MUSIC.items() if v==self.music_setting.get())
        lyrics = next(k for k,v in LYRIC_MODELS.items() if v==self.lyrics_setting.get())
        warning = device_warning(device,music,lyrics,snapshot())
        missing = [catalog()[key][0] for key in [*required_music(music),lyrics] if not model_path(self.models,key).is_file()]
        if missing:
            warning += "\nModelos pendientes de descargar o cargar: " + ", ".join(missing)
        if lyrics in TEXT_BASES and not (text_engine.runtime_dir(RUNTIME,device)/"llama-server.exe").is_file():
            warning += "\nEl motor de letras Qwen para el procesador elegido todavía debe instalarse desde Modelos."
        if warning.strip() and not messagebox.askyesno("Guardar configuración", warning.strip()+"\n\n¿Guardar de todos modos?"):
            return
        self.advice_seen.clear()
        self.device_mode,self.music_default,self.lyrics_default = device,music,lyrics
        self.paths.update(device=device,music_model=music,lyrics_model=lyrics)
        write_json(self.config,self.paths)
        self.edit_model.set(MUSIC[music])
        self.status.set("Preferencias guardadas. Los modelos se cargan cuando se necesitan.")
        self.inspect()

    def import_model(self,key):
        if self.busy:
            return
        name,size,sha=catalog()[key]
        selected=filedialog.askopenfilename(title="Cargar "+name,filetypes=[("Modelos GGUF","*.gguf")])
        if not selected:
            return
        destination=model_path(self.models,key)
        def work():
            transfer_model(Path(selected),destination,size,sha,self.cancel,
                           lambda n,t:self.events.put(("progress",("Importando "+name,n,t))))
            self.verified.clear()
            return "Modelo cargado y verificado."
        self.run(work,"Importar modelo",download=True)

    def save_model(self,key):
        if self.busy:
            return
        name,size,sha=catalog()[key]
        folder=filedialog.askdirectory(title="Guardar copia del modelo")
        if not folder:
            return
        source=model_path(self.models,key)
        dest=Path(folder)/name
        if dest.exists() and not messagebox.askyesno("Guardar copia","Ya existe un archivo con este nombre. ¿Reemplazarlo si la copia es válida?"):
            return
        def work():
            transfer_model(source,dest,size,sha,self.cancel,
                           lambda n,t:self.events.put(("progress",("Guardando "+name,n,t))))
            return "Copia del modelo guardada."
        self.run(work,"Guardar modelo",download=True)

    def install_text_runtime(self):
        if self.busy:
            return
        mode=self.device_mode
        size=sum(x[1] for x in text_engine.ASSETS[text_engine.kind(mode)])
        if not messagebox.askyesno("Motor de letras",f"Instalar llama.cpp {text_engine.TAG} para {DEVICES[mode]} desde GitHub oficial (hasta {size/1e6:.0f} MB)?"):
            return
        def work():
            text_engine.install_runtime(RUNTIME,mode,self.cancel,
                                        lambda n,b,t:self.events.put(("progress",(n,b,t))))
            return "Motor Qwen instalado."
        self.run(work,"Instalar motor Qwen",download=True)

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
        self.model_save_buttons[key].configure(state="normal" if ok else "disabled")

    def update_instrument_mode(self):
        manual=self.instrument_mode.get()=="manual"
        for check in self.instrument_checks.values():
            check.configure(state="normal" if manual else "disabled")
        self.update_instrument_label()

    def toggle_instruments(self):
        # Compatibility with older tests and shortcuts; the list never hides.
        self.instrument_mode.set("manual")
        self.update_instrument_mode()

    def update_instrument_label(self):
        count = sum(var.get() for var in self.instrument_vars.values())
        self.instrument_label.configure(text="Instrumentos" + (f" · {count}" if self.instrument_mode.get()=="manual" else ""))

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
        self.update_copy_button()
        if state:
            self.hide_composer()

    def build_composer(self, parent):
        self.composer=ttk.Frame(parent,padding=(0,2))
        header=ttk.Frame(self.composer)
        header.pack(side="top",fill="x")
        footer=ttk.Frame(self.composer)
        footer.pack(side="bottom",fill="x")
        self.composer_scroll=ScrollFrame(self.composer,auto_hide=True)
        self.composer_scroll.pack(fill="both",expand=True)
        frame=self.composer_scroll.inner
        ttk.Label(header,text="✦ Compositor IA",style="Field.TLabel",font=("Segoe UI",13,"bold")).pack(side="left")
        ttk.Button(header,text="×",width=2,command=self.hide_composer).pack(side="right")
        self.field_label(frame,"Tema de la canción","Describe lo que quieres contar.")
        self.topic=tk.Text(frame,height=2,width=12,wrap="word",relief="flat",font=("Segoe UI",10),background="white",foreground="#22243a")
        self.topic.pack(fill="x")
        row=ttk.Frame(frame)
        row.pack(fill="x")
        row.columnconfigure(0,weight=1,uniform="composer")
        row.columnconfigure(1,weight=1,uniform="composer")
        left,right=ttk.Frame(row),ttk.Frame(row)
        left.grid(row=0,column=0,sticky="ew",padx=(0,3))
        right.grid(row=0,column=1,sticky="ew",padx=(3,0))
        self.structure=self.combo(left,"Estructura",[*STRUCTURES,"Personalizada"],"Selecciona una estructura o personaliza seis secciones.")
        self.intent=self.combo(right,"Intención",list(INTENTIONS),"Propósito de la letra: amor, protesta, patriotismo, etc.")
        self.sections_panel=ttk.Frame(frame)
        self.sections=[]
        for i,val in enumerate(["Intro","Verso 1","Coro","Verso 2","Coro","Outro"]):
            combo=ttk.Combobox(self.sections_panel,values=list(SECTIONS),state="readonly",width=6)
            combo.set(val)
            combo.grid(row=i//3,column=i%3,sticky="ew",padx=2,pady=1)
            self.sections.append(combo)
        for i in range(3):
            self.sections_panel.columnconfigure(i,weight=1)
        self.structure_row=row
        self.structure.bind("<<ComboboxSelected>>",self.toggle_sections)
        row2=ttk.Frame(frame)
        row2.pack(fill="x")
        row2.columnconfigure(0,weight=1,uniform="composer")
        row2.columnconfigure(1,weight=1,uniform="composer")
        left,right=ttk.Frame(row2),ttk.Frame(row2)
        left.grid(row=0,column=0,sticky="ew",padx=(0,3))
        right.grid(row=0,column=1,sticky="ew",padx=(3,0))
        self.complexity=self.combo(left,"Estilo de escritura",list(COMPLEXITIES),"Poético, sencillo, narrativo, etc.")
        self.lyric_language=self.combo(right,"Idioma",list(LANGUAGES),"Idioma de la letra y el canto.")
        self.field_label(frame,"Instrucción adicional","Indicaciones complementarias.")
        self.extra=ttk.Entry(frame)
        self.extra.pack(fill="x")
        self.compose_button=ttk.Button(footer,text="✦ Generar letra",style="Accent.TButton",command=lambda:self.refresh_then(self.compose_lyrics))
        self.compose_button.pack(fill="x",pady=(3,1))
        self.lyric_notice=ttk.Label(footer,text="",wraplength=280)
        self.lyric_notice.pack(anchor="w")

    def toggle_sections(self, _=None):
        if self.structure.get() == "Personalizada":
            self.sections_panel.pack(fill="x", after=self.structure_row)
        else:
            self.sections_panel.pack_forget()

    def lyric_dialog(self):
        if self.instrumental.get() or self.busy:
            return
        self.lyric_language.set(self.language.get())
        self.results.pack_forget()
        self.composer.pack(fill="both", expand=True)
        self.composer_scroll.canvas.yview_moveto(0)
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
        selected = self.lyrics_default
        if not self.preflight("lyrics", selected):
            return
        self.language.set(language)
        mode = self.device_mode
        if selected in TEXT_BASES:
            if not model_path(self.models,selected).is_file():
                self.lyric_notice.configure(text="Descarga o carga el Qwen3 seleccionado desde Modelos.")
                return
            if not text_engine.runtime_dir(RUNTIME,mode).joinpath("llama-server.exe").is_file():
                self.lyric_notice.configure(text="Instala el motor Qwen desde Modelos para este procesador.")
                return
        def work():
            if selected in TEXT_BASES:
                if not self.check_model(*catalog()[selected]):
                    raise ValueError("El archivo Qwen no pasó la verificación SHA-256.")
                if mode != "cpu" and not snapshot().get("gpu"):
                    raise ValueError("No hay GPU NVIDIA. Selecciona CPU en Configuración.")
                lyrics = text_engine.compose(RUNTIME,model_path(self.models,selected),mode,prompt,self.cancel,
                                            lambda s:self.events.put(("stage",s)))
                self.events.put(("lyrics",lyrics))
                return "Letra generada con Qwen3. Revísala antes de crear música."
            with self.engine_session(("lm",)) as (engine, props):
                if OPTIONAL["lm"][0] not in props["models"].get("lm", []):
                    raise ValueError("El servidor no reconoció el modelo de letras.")
                self.events.put(("stage", "Componiendo letra"))
                lyrics = engine.compose(dict(caption=prompt, vocal_language=code, duration=seconds,
                                             lm_model=OPTIONAL["lm"][0], lm_mode="inspire", lm_batch_size=1))
                self.events.put(("lyrics", lyrics))
                return "Letra generada. Revísala antes de crear música."
        self.lyric_notice.configure(text="Generando letra en " + language + "…")
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
        self.card_views={}
        data=[(i,s) for i,s in enumerate(self.song_data) if not self.home_filter.get() or s["favorite"]]
        if not data:
            ttk.Label(self.home_cards,text="Todavía no hay canciones en esta vista.").pack(anchor="w")
            return
        palettes=[("#c80979","#5335af"),("#1551b8","#00a0aa"),("#e85324","#b71d6e"),("#5138ae","#087d97")]
        for pos,(i,song) in enumerate(data):
            card=ttk.Frame(self.home_cards,padding=7)
            card.grid(row=pos//self.card_columns,column=pos%self.card_columns,sticky="nsew",padx=4,pady=4)
            top=tk.Canvas(card,height=106,highlightthickness=0,cursor="hand2")
            top.pack(fill="x")
            left,right=palettes[i%len(palettes)]
            title=song["title"]
            sub=self.format_time(song["seconds"]*1000)
            path=self.files[i]
            self.card_views[path]=(top,left)
            def paint(e,w=top,a=left,b=right,t=title,s=sub,p=path):
                gradient(w,e.width,e.height,a,b,t,s,play=True)
                draw_play_state(w,a,self.card_playing==p)
            top.bind("<Configure>",paint)
            top.bind("<Button-1>",lambda _,n=i:self.toggle_card(n))
            row=ttk.Frame(card)
            row.pack(fill="x",pady=4)
            ttk.Button(row,text="♥",style="FavoriteHeart.TButton" if song["favorite"] else "MutedHeart.TButton",
                       command=lambda n=i:self.card_action(n,lambda:self.edit_song(True))).pack(side="left",padx=1)
            for label,fn in [("↓ MP3",lambda:self.export("mp3")),("↓ WAV",self.export),("Letra",self.view_lyrics)]:
                ttk.Button(row,text=label,command=lambda n=i,f=fn:self.card_action(n,f)).pack(side="left",padx=1)
            more=ttk.Button(row,text="⋯",width=3)
            more.pack(side="right",padx=1)
            more.configure(command=lambda n=i,w=more:self.card_menu(n,w))
        for col in range(3):
            self.home_cards.columnconfigure(col,weight=1 if col<self.card_columns else 0)

    def card_menu(self,index,anchor):
        menu=tk.Menu(anchor,tearoff=False,background="white",foreground="#22243a")
        for label,fn in [("Renombrar",lambda:self.edit_song(False)),("Ubicación",self.open_folder),("Compartir",self.share_song)]:
            menu.add_command(label=label,command=lambda f=fn:self.card_action(index,f))
        try:
            menu.tk_popup(anchor.winfo_rootx(),anchor.winfo_rooty()+anchor.winfo_height())
        finally:
            menu.grab_release()

    def sync_card_playback(self,path):
        if path==self.card_playing:
            return
        self.card_playing=path
        for file,(canvas,color) in self.card_views.items():
            draw_play_state(canvas,color,file==path)

    def toggle_card(self,index):
        path=self.files[index]
        if self.player.opened and self.playing_file==path:
            try:
                mode=self.player.send("status noelplayer mode")
                if mode=="playing":
                    self.player.send("pause noelplayer")
                    self.sync_card_playback(None)
                    return
                if mode=="paused":
                    self.player.send("resume noelplayer")
                    self.sync_card_playback(path)
                    return
            except OSError:
                pass
        self.card_action(index,self.play)
        if self.playing_file==path and self.player.opened:
            self.sync_card_playback(path)

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
        model = self.music_default
        if not self.preflight("music",model):
            return
        if seconds > 120 or model == "sft":
            if not messagebox.askyesno("Configuración experimental", "Esta duración o modelo aún no tiene benchmark suficiente en tu equipo. ¿Continuar?"):
                return
        profile=None if self.instrumental.get() else self.voice_profiles.get(self.voice.get())
        if profile and not self.voice_precheck():
            return
        seed = secrets.randbelow(2**31)
        language = LANGUAGES[self.language.get()][0]
        def work():
            with self.engine_session(music=model) as (engine, props):
                self.events.put(("stage", "Generando música"))
                with PeakMonitor() as monitor:
                    result = render(engine, props, self.runs, caption, lyrics, seconds, seed, model, language)
                write_json(self.runs/result["version"]/"performance.json",
                           dict(peak_system_vram_mib=monitor.peak_gpu_mib, peak_system_ram_bytes=monitor.peak_ram_bytes,
                                total_seconds=result["total_s"], generated_seconds=result["actual_seconds"]))
                if title:
                    write_json(self.runs/result["version"]/"display.json", {"title": title})
            if profile:
                try:
                    result=self.apply_voice_result(result,profile,title)
                except (InterruptedError, OSError, ValueError, RuntimeError) as exc:
                    raise type(exc)("La canción original se guardó; no se completó la conversión vocal: "+str(exc)) from exc
            self.events.put(("song", (f"{title or 'Nueva canción'} · {result['actual_seconds']:.0f} s · lista para escuchar", result["version"])))
            return "Canción guardada · " + result["version"]
        self.run(work, "Generación")


if __name__ == "__main__":
    root = tk.Tk()
    Studio(root)
    root.mainloop()
