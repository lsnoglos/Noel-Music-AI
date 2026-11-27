"""Optional isolated llama.cpp runtime; pinned ZIPs, local HTTP only."""
import hashlib
import http.client
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

TAG = "b12635"
BASE = f"https://github.com/ggml-org/llama.cpp/releases/download/{TAG}/"
ASSETS = {
    "cpu": [("llama-b12635-bin-win-cpu-x64.zip", 25046284, "c0fcd7ef0412f2a02b76713c6228d68717973a61f0cc17b9299eb98e3bf048dc")],
    "gpu": [("llama-b12635-bin-win-cuda-12.4-x64.zip", 357980275, "5e2998c6524562a388d34f23bd223901c21140a9bd959746c09cfb13e1fc259f"),
            ("cudart-llama-bin-win-cuda-12.4-x64.zip", 391443627, "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6")],
}

def kind(mode):
    if mode not in ("cpu", "gpu", "hybrid"):
        raise ValueError("Dispositivo no admitido.")
    return "cpu" if mode == "cpu" else "gpu"

def runtime_dir(root, mode):
    return root / "text-engines" / (TAG+"-"+kind(mode))

def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def runtime_ready(root, mode):
    folder = runtime_dir(root, mode)
    try:
        manifest = json.loads((folder/"manifest.json").read_text("utf-8"))
        return ("llama-server.exe" in manifest and all(
            re.fullmatch(r"[A-Za-z0-9_.-]+", n) and n not in (".","..")
            and (folder/n).is_file() and digest(folder/n) == h for n,h in manifest.items()))
    except (OSError, ValueError, TypeError, AttributeError):
        return False

def install_runtime(root, mode, cancel, progress):
    if runtime_ready(root, mode):
        return
    folder = runtime_dir(root, mode)
    folder.parent.mkdir(parents=True, exist_ok=True)
    assets = ASSETS[kind(mode)]
    if shutil.disk_usage(folder.parent).free < sum(x[1] for x in assets)*4:
        raise ValueError("Espacio insuficiente para el motor de letras.")
    with tempfile.TemporaryDirectory(dir=folder.parent) as d:
        temp = Path(d)
        stage = temp/"engine"
        stage.mkdir()
        for name,size,expected in assets:
            archive = temp/name
            h = hashlib.sha256()
            count = 0
            with urllib.request.urlopen(BASE+name, timeout=30) as response, archive.open("wb") as out:
                while chunk := response.read(1024*1024):
                    if cancel.is_set():
                        raise InterruptedError("Descarga cancelada.")
                    count += len(chunk)
                    if count > size:
                        raise ValueError("Tamaño incorrecto del motor de letras.")
                    h.update(chunk)
                    out.write(chunk)
                    progress(name,count,size)
            if count != size or h.hexdigest() != expected:
                raise ValueError("Hash incorrecto del motor de letras.")
            with zipfile.ZipFile(archive) as z:
                for item in z.infolist():
                    name = item.filename.replace("\\","/").rsplit("/",1)[-1]
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.(exe|dll|txt|md)", name, re.I):
                        continue
                    target = stage/name
                    if target.exists():
                        # Archives can share identical notices; never replace a DLL or executable.
                        if target.suffix.lower() in (".txt",".md"):
                            continue
                        with z.open(item) as src:
                            if hashlib.file_digest(src,"sha256").hexdigest() != digest(target):
                                raise ValueError("Biblioteca duplicada e incompatible: "+name)
                        continue
                    with z.open(item) as src,target.open("xb") as dst:
                        shutil.copyfileobj(src,dst)
        if not (stage/"llama-server.exe").is_file():
            raise ValueError("El paquete no incluye llama-server.exe.")
        (stage/"manifest.json").write_text(json.dumps({p.name:digest(p) for p in stage.iterdir()}), encoding="utf-8")
        backup = temp/"previous"
        if folder.exists():
            folder.rename(backup)
        try:
            stage.rename(folder)
        except Exception:
            if backup.exists():
                backup.rename(folder)
            raise

def request(port, path, payload=None, timeout=5):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("POST" if payload is not None else "GET", path,
                     json.dumps(payload).encode("utf-8") if payload is not None else None,
                     {"Content-Type":"application/json"})
        r = conn.getresponse()
        data = r.read(2*1024*1024+1)
        if len(data)>2*1024*1024 or r.status != 200:
            raise RuntimeError(f"Motor de letras HTTP {r.status}: {data[:300]!r}")
        return json.loads(data)
    finally:
        conn.close()

def compose(root, model, mode, prompt, cancel, stage):
    if not runtime_ready(root, mode):
        raise ValueError("Instala el motor de letras desde Modelos.")
    binary = runtime_dir(root,mode)/"llama-server.exe"
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        port=s.getsockname()[1]
    layers = "0" if mode=="cpu" else "18" if mode=="hybrid" else "99"
    args = [str(binary), "-m", str(model), "--host","127.0.0.1","--port",str(port),
            "-c","4096","-ngl",layers,"--parallel","1","--no-webui"]
    root.mkdir(parents=True,exist_ok=True)
    with (root/"text-engine.log").open("w",encoding="utf-8") as log:
        stage("Cargando Qwen3")
        proc = subprocess.Popen(args, stdout=log, stderr=log, cwd=binary.parent,
                                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        try:
            end=time.monotonic()+180
            while time.monotonic()<end:
                if cancel.is_set():
                    raise InterruptedError("Composición cancelada.")
                if proc.poll() is not None:
                    raise RuntimeError("Qwen no pudo iniciar. Consulta text-engine.log.")
                try:
                    if request(port,"/health").get("status")=="ok":
                        break
                except (OSError, RuntimeError, ValueError):
                    pass
                time.sleep(.3)
            else:
                raise TimeoutError("Qwen no terminó de cargar.")
            stage("Escribiendo letra con Qwen3")
            results=queue.Queue()
            def run():
                try:
                    data=request(port,"/v1/chat/completions",{
                        "messages":[{"role":"system","content":"Eres un compositor profesional. Sigue el tema, idioma, estructura y requisitos del usuario. Escribe únicamente una letra original cantable con etiquetas de sección. Evita relleno y repeticiones innecesarias. No inventes datos geográficos. No incluyas explicaciones."},
                                    {"role":"user","content":prompt}],
                        "temperature":.7,"top_p":.9,"max_tokens":2048,"stream":False,
                        **({"chat_template_kwargs":{"enable_thinking":False}} if model.name.startswith(("Qwen3-0.6B","Qwen3-1.7B")) else {})},timeout=900)
                    results.put((True,data))
                except Exception as exc:
                    results.put((False,exc))
            threading.Thread(target=run,daemon=True).start()
            end=time.monotonic()+900
            while time.monotonic()<end:
                if cancel.is_set():
                    raise InterruptedError("Composición cancelada.")
                if proc.poll() is not None:
                    raise RuntimeError("El motor de letras se cerró.")
                try:
                    ok,data=results.get(timeout=.25)
                except queue.Empty:
                    continue
                if not ok:
                    raise data
                choice=data["choices"][0]
                text=choice["message"].get("content","").strip()
                if choice.get("finish_reason")=="length":
                    raise ValueError("Qwen agotó su límite de texto; reduce la extensión solicitada.")
                if not text or len(text)>16000:
                    raise ValueError("Qwen devolvió una letra vacía o demasiado extensa.")
                return text
            raise TimeoutError("Tiempo agotado al componer.")
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
