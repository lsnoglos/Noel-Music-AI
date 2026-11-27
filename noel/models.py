"""Pinned model inventory and explicit, resumable installation."""
import hashlib
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
}


def catalog():
    return {**MODELS, **OPTIONAL}


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
            dest = directory / name
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
                                "--output", str(part), f"{BASE}/{name}"]
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
