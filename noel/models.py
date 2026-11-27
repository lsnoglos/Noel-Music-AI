"""Pinned model inventory and explicit, resumable installation."""
import hashlib
import os
import tempfile
import shutil
import subprocess
import time
from pathlib import Path

REVISION = "83f32e465c3abd605271d0c1c935ad2faf28c197"
BASE = f"https://huggingface.co/Serveurperso/ACE-Step-1.5-GGUF/resolve/{REVISION}"
MODELS = {
    "embedding": ("Qwen3-Embedding-0.6B-Q8_0.gguf", 784144960, "972f23255e46adfe744a0eb9a0039f3c63988f65753b0968d776e8b27168c321"),
    "dit": ("acestep-v15-turbo-Q8_0.gguf", 2549528000, "288f708a61cfc241013a98a62f98ba331f83fe34d0d3559acdd9b0f6a2f7cd6b"),
    "vae": ("vae-BF16.gguf", 337420928, "0599862ac5d15cd308e1d2e368373aea6c02e25ebd1737ad4a4562a0901b0ef8"),
}

# Optional weights from the same pinned Hugging Face revision. No automatic downloads.
OPTIONAL = {
    "lm": ("acestep-5Hz-lm-0.6B-Q8_0.gguf", 709846656, "bdaf9e292d4470f31c19cafeaca1b74936a114667e3a85e5d33b65247e9908ec"),
    "sft": ("acestep-v15-sft-Q8_0.gguf", 2549527936, "17f1984e48aaab27b3eb8ccbf0b754a6656e677884c60ea7003845cfc0059b70"),
    "turbo4": ("acestep-v15-turbo-Q4_K_M.gguf", 1445710272, "55b4d8514850f3d0f82536f37e99673aaf48df802b5ae5b153eea32a2e2daa5e"),
    "qwen": ("Qwen3-4B-Instruct-2507-Q4_K_M.gguf", 2497280448, "8cdb57cbb880d313736a9bc4e3d3d2485f145b5e19cf33783746e753e82641fc"),
    "qwen06": ("Qwen3-0.6B-Q4_K_M.gguf", 484219808, "cd47557a67d7e8f2891d98b5e1dbf2988544569fdf4f1bdb30e92b71aa61b548"),
    "qwen17": ("Qwen3-1.7B-Q4_K_M.gguf", 1282439328, "e0801cbda7e2f3fd00bea4d73b53b422b14b13aa130e778f6414b6b641920b7e"),
}


def catalog():
    return {**MODELS, **OPTIONAL}

QWEN_BASE = "https://huggingface.co/lmstudio-community/Qwen3-4B-Instruct-2507-GGUF/resolve/dc2e72201d372af11b32615149baa50eb2588a2f"
MUSIC = {"dit": "Turbo Q8 · rápido (8 pasos)", "turbo4": "Turbo Q4 · ligero (8 pasos)", "sft": "SFT Q8 · experimental (50 pasos)"}
LYRIC_MODELS = {"lm": "ACE-Step LM 0.6B · rápido", "qwen": "Qwen3 4B Instruct Q4 · creativo",
                "qwen06": "Qwen3 0.6B Q4 · ligero", "qwen17": "Qwen3 1.7B Q4 · equilibrado"}
TEXT_BASES = {
    "qwen": QWEN_BASE,
    "qwen06": "https://huggingface.co/lmstudio-community/Qwen3-0.6B-GGUF/resolve/3334d820ab76652cf6e242d7c6302b10f0951f23",
    "qwen17": "https://huggingface.co/lmstudio-community/Qwen3-1.7B-GGUF/resolve/97628ceb7c121b629a2a9392eb9b97bd4c2a8f66",
}
DEVICES = {"gpu": "GPU", "cpu": "CPU", "hybrid": "CPU + GPU"}

def model_path(directory, key):
    # Keep general-purpose GGUF outside the ACE-Step registry.
    return directory / ("text-models" if key in TEXT_BASES else "") / catalog()[key][0]

def required_music(key):
    if key not in MUSIC:
        raise ValueError("Modelo musical no admitido.")
    return ["embedding", key, "vae"]

def device_warning(mode, music, lyrics, info):
    warnings = []
    if mode == "cpu":
        warnings.append("Solo CPU: incluso Turbo Q4 puede ser muy lento. Empieza con 15 segundos.")
        if music != "turbo4":
            warnings.append("El modelo musical seleccionado es más pesado que Turbo Q4.")
        if lyrics == "qwen":
            warnings.append("Qwen 4B puede requerir más RAM y tiempo que los modelos pequeños.")
    elif not info.get("gpu"):
        warnings.append("No se detectó GPU NVIDIA. Este modo no podrá generar música hasta disponer de una GPU compatible.")
    if mode == "hybrid":
        warnings.append("CPU + GPU: ACE-Step usa GPU; Qwen reparte capas entre CPU y GPU. No equivale a sumar sus memorias.")
    if music == "sft":
        warnings.append("SFT utiliza 50 pasos y todavía no tiene benchmark en este equipo.")
    if info.get("ram_available") is not None and info["ram_available"] < 4*2**30:
        warnings.append("Hay menos de 4 GiB de RAM disponible; pueden producirse fallos.")
    return "\n".join(warnings)

def transfer_model(source, dest, size, digest, cancel=None, progress=None):
    """Verify exact bytes and atomically copy, leaving the original untouched."""
    source, dest = Path(source), Path(dest)
    if not source.is_file() or source.stat().st_size != size:
        raise ValueError("El archivo no tiene el tamaño exacto del modelo seleccionado.")
    if source.resolve() == dest.resolve():
        if not matches(source, size, digest):
            raise ValueError("SHA-256 incorrecto.")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(dest.parent).free < size:
        raise ValueError("Espacio insuficiente para la copia.")
    fd, temp = tempfile.mkstemp(prefix=".model-", dir=dest.parent)
    h = hashlib.sha256()
    count = 0
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            while data := inp.read(4*1024*1024):
                if cancel and cancel.is_set():
                    raise InterruptedError("Copia cancelada.")
                count += len(data)
                if count > size:
                    raise ValueError("El archivo cambió durante la copia.")
                h.update(data)
                out.write(data)
                if progress:
                    progress(count, size)
        if count != size or h.hexdigest() != digest:
            raise ValueError("SHA-256 incorrecto: no corresponde a esta versión del modelo.")
        os.replace(temp, dest)
    finally:
        Path(temp).unlink(missing_ok=True)


def matches(path, size, digest):
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == digest


def install(directory: Path, approved: bool, selected=None, repair=False, cancel=None, progress=None):
    print("Modelos de Serveurperso/ACE-Step-1.5-GGUF:")
    for name, size, _ in catalog().values():
        print(f"  {name}   {size:,} bytes")
    if not approved:
        print("Use models --download para autorizar la descarga.")
        return
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".installing"
    lock.touch(exist_ok=False)
    try:
        for key in (MODELS if selected is None else selected):
            name, size, digest = catalog()[key]
            dest = model_path(directory, key)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                if matches(dest, size, digest):
                    continue
                if not repair:
                    raise ValueError(f"Modelo existente incorrecto. Mueva {dest} y reintente.")
            part = dest.with_suffix(".gguf.part")
            offset = part.stat().st_size if part.exists() else 0
            if shutil.disk_usage(directory).free < size - offset:
                raise ValueError("Espacio insuficiente para " + name)
            if offset < size:
                args = ["curl", "--fail", "--location", "--proto", "=https",
                                "--proto-redir", "=https", "--retry", "2", "--continue-at", "-",
                                "--output", str(part), f"{TEXT_BASES.get(key, BASE)}/{name}"]
                if cancel is None:
                    subprocess.run(args, check=True)
                else:
                    with subprocess.Popen(args) as proc:
                        while proc.poll() is None:
                            if cancel.is_set():
                                proc.terminate()
                                raise InterruptedError("Descarga cancelada. Puede reanudarla.")
                            if progress:
                                progress(name, part.stat().st_size if part.exists() else 0, size)
                            time.sleep(.3)
                        if proc.returncode:
                            raise ValueError(f"Descarga fallida: {name}")
            if not matches(part, size, digest):
                part.unlink()
                raise ValueError(f"Integridad incorrecta para {name}. Repita la descarga.")
            part.replace(dest)
    finally:
        lock.unlink()
