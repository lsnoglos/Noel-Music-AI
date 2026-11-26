"""Windows desktop studio. Network and engine operations run outside Tk's event loop."""
import json
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
from tkinter import filedialog, messagebox, ttk

from .__main__ import ROOT, RUNTIME
from .diagnostics import snapshot
from .engine import Engine
from .distribution import available, binary_path, install_engine
from .models import MODELS, matches
from .studio import render, write_json


class Studio:
    def __init__(self, window):
        self.w = window
        window.title("Noel Music AI")
        window.geometry("800x620")
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = self.closing = False
        self.proc = None
        RUNTIME.mkdir(exist_ok=True)
        self.config = RUNTIME / "studio.json"
        self.paths = json.loads(self.config.read_text("utf-8")) if self.config.exists() else {}
        self.models = Path(self.paths.get("models", RUNTIME / "models"))
        self.runs = Path(self.paths.get("runs", ROOT / "runs"))
        self.status = tk.StringVar(value="Preparado")
        self.style = ttk.Style(window)
        self.style.theme_use("clam")
        self.theme("Oscuro")
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=16, pady=16)
        create, library, setup, settings, diag = [ttk.Frame(notebook, padding=18) for _ in range(5)]
        for panel, name in zip((create, library, setup, settings, diag), ("Crear música", "Biblioteca", "Modelos y descargas", "Configuración", "Diagnóstico")):
            notebook.add(panel, text=name)
        ttk.Label(create, text="Nueva canción", font=("Segoe UI", 22)).pack(anchor="w")
        self.title = ttk.Entry(create)
        ttk.Label(create, text="Título").pack(anchor="w")
        self.title.pack(fill="x")
        self.genre = self.combo(create, "Género", ["Balada acústica", "Pop latino", "Rock", "Salsa", "Salsa romántica", "Bachata", "Bachata romántica", "Merengue", "Cumbia", "Bolero", "Vallenato", "Reguetón", "Jazz", "Regional mexicano"])
        ttk.Label(create, text="Describe cómo quieres que suene").pack(anchor="w")
        self.mood = self.combo(create, "Emoción", ["Natural", "Romántica", "Alegre", "Melancólica", "Enérgica"])
        self.prompt = ttk.Entry(create)
        self.prompt.pack(fill="x")
        ttk.Label(create, text="Letra · déjala vacía para una instrumental").pack(anchor="w", pady=(10, 0))
        self.lyrics = tk.Text(create, height=7, wrap="word")
        self.lyrics.pack(fill="x")
        self.seconds = self.combo(create, "Duración en segundos", [15, 30, 60, 120])
        self.button(create, "Generar canción", self.generate)
        self.history = tk.Listbox(library, height=14)
        self.history.pack(fill="both", expand=True)
        self.button(library, "Reproducir", self.play)
        self.button(library, "Guardar copia WAV", self.export)
        self.observed = ttk.Label(diag, wraplength=700)
        self.observed.pack(anchor="w")
        self.button(setup, "Buscar e instalar el motor Windows", self.find_release)
        self.button(settings, "Alternar tema claro / oscuro", lambda: self.theme("Claro" if self.dark else "Oscuro"))
        self.selected = {}
        for key, (name, size, _) in MODELS.items():
            var = tk.BooleanVar(value=True)
            self.selected[key] = var
            ttk.Checkbutton(setup, variable=var, text=f"{name}   {size/1e6:.0f} MB").pack(anchor="w")
        self.button(setup, "Verificar e instalar los modelos seleccionados", self.install)
        self.button(settings, "Cambiar carpeta de modelos", lambda: self.folder("models"))
        self.button(settings, "Cambiar carpeta de canciones", lambda: self.folder("runs"))
        self.button(diag, "Guardar diagnóstico", self.report)
        self.button(diag, "Comprobar componentes", self.inspect)
        ttk.Label(window, textvariable=self.status, wraplength=750).pack(anchor="w", padx=20)
        self.button(window, "Cancelar operación", self.cancel.set)
        self.library()
        window.protocol("WM_DELETE_WINDOW", self.close)
        self.inspect()
        window.after(150, self.poll)

    def theme(self, name):
        self.dark = name == "Oscuro"
        bg, fg = ("#19212e", "#eef2ff") if self.dark else ("#f3f5fa", "#182233")
        self.style.configure(".", background=bg, foreground=fg, fieldbackground=bg, font=("Segoe UI", 10))
        self.style.map("TButton", background=[("active", "#485a79")])
        self.w.configure(background=bg)

    def find_release(self):
        def lookup():
            self.events.put(("release", available()))
        self.run(lookup)

    def combo(self, parent, label, values):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 0))
        field = ttk.Combobox(parent, values=values, state="readonly")
        field.current(0)
        field.pack(anchor="w")
        return field

    def button(self, parent, label, action):
        ttk.Button(parent, text=label, command=action).pack(anchor="w", pady=3, padx=3)

    def run(self, function):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.start_time = time.monotonic()
        self.stage = "Preparando"
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
                self.observed.configure(text=text)
            else:
                self.busy = False
                self.status.set(text)
                if kind == "error" and not self.closing:
                    messagebox.showerror("Noel Music AI", text)
                self.library()
        if self.closing and not self.busy:
            self.w.destroy()
            return
        if self.busy:
            self.status.set(f"{self.stage} · {int(time.monotonic()-self.start_time)} s")
        self.w.after(200, self.poll)

    def confirm_install(self, asset):
        if not self.closing and messagebox.askyesno("Instalar motor", f"Descargar {asset['name']} desde GitHub ({asset['size']/1e6:.1f} MB) e instalar el motor?"):
            self.run(lambda: install_engine(ROOT, asset, self.cancel, lambda n,total: self.events.put(("stage", f"Motor · {n/1e6:.1f}/{total/1e6:.1f} MB"))))

    def close(self):
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
        self.history.delete(0, "end")
        self.files = []
        for manifest in sorted(self.runs.glob("*/version.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(manifest.read_text("utf-8"))
                wav = manifest.with_name("song.wav")
                if wav.exists():
                    title_file = manifest.with_name("display.json")
                    if title_file.exists():
                        data["request"]["caption"] = json.loads(title_file.read_text("utf-8"))["title"]
                    self.history.insert("end", f"{data['request']['caption']} · {data['metrics']['actual_seconds']:.1f} s")
                    self.files.append(wav)
            except (OSError, ValueError, KeyError):
                continue
        if self.files:
            self.history.selection_set(0)

    def play(self):
        if self.history.curselection():
            os.startfile(self.files[self.history.curselection()[0]])

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
                    f"Motor musical: {'presente' if self.binary().exists() else 'falta · descargue el paquete Windows de GitHub Actions'}"]
            for name, size, digest in MODELS.values():
                state = "verificado" if matches(self.models/name, size, digest) else "falta o requiere reparación"
                rows.append(f"{name} · {state}")
            self.events.put(("inventory", "\n".join(rows)))
        self.run(work)

    def install(self):
        keys = [k for k, v in self.selected.items() if v.get()]
        if self.busy or not keys:
            return
        total = sum(MODELS[k][1] for k in keys)
        if not messagebox.askyesno("Modelos seleccionados", f"Verificar y descargar desde Hugging Face los archivos faltantes o dañados (hasta {total/1e9:.2f} GB)?"):
            return
        def work():
            from .models import install
            install(self.models, True, keys, repair=True, cancel=self.cancel,
                    progress=lambda name, n, total: self.events.put(("stage", f"{name} · {n/1e6:.1f} / {total/1e6:.1f} MB")))
            return "Modelos verificados"
        self.run(work)

    def generate(self):
        title = self.title.get().strip()
        caption = " · ".join(filter(None, (self.genre.get(), self.mood.get(), self.prompt.get().strip())))
        lyrics = self.lyrics.get("1.0", "end").strip()
        seconds = int(self.seconds.get())
        def work():
            binary = self.binary()
            if not binary.is_file():
                raise ValueError("Abra la distribución Windows con la carpeta engine incluida. Consulte Instalación.")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            from .runtime import verify_engine
            verify_engine(binary)
            gpu = snapshot()["gpu"]
            if not gpu:
                raise ValueError("No se detectó GPU NVIDIA. Revise el diagnóstico.")
            for name, size, digest in MODELS.values():
                if self.cancel.is_set():
                    raise InterruptedError("Cancelado")
                if not matches(self.models/name, size, digest):
                    raise ValueError("Verifique los modelos en Instalación.")
            args = [str(binary), "--device", "CUDA0", "--host", "127.0.0.1", "--port", str(port),
                    "--models", str(self.models), "--max-batch", "1", "--vae-chunk",
                    "128" if gpu["free_mib"] < 6000 else "256", "--vae-overlap", "32"]
            with (RUNTIME / "engine.log").open("w") as log:
                proc = subprocess.Popen(args, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    engine = Engine(port, self.cancel)
                    for _ in range(200):
                        if proc.poll() is not None:
                            raise ValueError("El motor se cerró. Consulte .runtime/engine.log.")
                        if self.cancel.is_set():
                            raise InterruptedError("Cancelado")
                        try:
                            props = engine.ready()
                            break
                        except ConnectionError:
                            time.sleep(.2)
                    else:
                        raise TimeoutError("El motor no respondió.")
                    self.events.put(("stage", "Generando música"))
                    result = render(engine, props, self.runs, caption, lyrics, seconds, 42)
                    if title:
                        write_json(self.runs/result["version"]/"display.json", {"title": title})
                    return "Canción guardada · " + result["version"]
                finally:
                    proc.terminate()
                    proc.wait(timeout=10)
        self.run(work)


if __name__ == "__main__":
    root = tk.Tk()
    Studio(root)
    root.mainloop()
