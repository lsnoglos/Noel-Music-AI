"""Obtain the compatible engine from a verified repository release."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .engine import ENGINE
from .runtime import verify_engine

REPO = "lsnoglos/Noel-Music-AI"
PREFIX = f"https://github.com/{REPO}/releases/download/"


def available():
    with urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases?per_page=30", timeout=15) as r:
        releases = json.load(r)
    for release in releases:
        for asset in release["assets"]:
            if (not release["draft"] and asset["name"] == "NoelMusicAI-Windows.zip"
                    and asset["browser_download_url"].startswith(PREFIX)
                    and re.fullmatch("sha256:[a-f0-9]{64}", asset.get("digest") or "")):
                return asset
    raise ValueError("GitHub aún no ofrece un paquete Windows con digest verificable.")


def install_engine(root, asset, cancel, progress):
    cache = root / ".runtime"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as folder:
        temp = Path(folder)
        archive = temp / "portable.zip"
        size = asset["size"]
        if shutil.disk_usage(temp).free < size * 4:
            raise ValueError("Espacio insuficiente para descargar y extraer el motor.")
        digest = hashlib.sha256()
        with urllib.request.urlopen(asset["browser_download_url"], timeout=30) as r, archive.open("wb") as f:
            while chunk := r.read(1024*1024):
                if cancel.is_set():
                    raise InterruptedError("Cancelado")
                if f.tell()+len(chunk) > size:
                    raise ValueError("Tamaño de descarga incorrecto.")
                digest.update(chunk)
                f.write(chunk)
                progress(f.tell(), size)
        if archive.stat().st_size != size or "sha256:"+digest.hexdigest() != asset["digest"]:
            raise ValueError("El paquete no coincide con el digest publicado.")
        engine = temp / "engine"
        engine.mkdir()
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                name = item.filename.replace("\\", "/")
                if name in ("engine-manifest.json", "engine-revision.txt"):
                    dest = temp / name
                elif re.fullmatch(r"engine/[A-Za-z0-9_.-]+\.(dll|exe|txt)", name, re.I):
                    dest = temp / name
                else:
                    continue
                with z.open(item) as src, dest.open("xb") as out:
                    shutil.copyfileobj(src, out)
        if (temp/"engine-revision.txt").read_text(encoding="utf-8-sig").strip() != ENGINE:
            raise ValueError("La revisión del motor no corresponde a esta aplicación.")
        verify_engine(engine / "ace-server.exe")
        # Publish an immutable generation; only switch the pointer after verification.
        versions = cache / "engines"
        versions.mkdir(exist_ok=True)
        version = Path(tempfile.mkdtemp(dir=versions))
        engine.rename(version/"engine")
        (temp/"engine-manifest.json").rename(version/"engine-manifest.json")
        pointer = temp / "current"
        pointer.write_text(version.name, encoding="ascii")
        os.replace(pointer, cache / "current-engine")


def binary_path(root):
    runtime = root / ".runtime"
    pointer = runtime / "current-engine"
    if pointer.exists():
        name = pointer.read_text(encoding="ascii")
        if not re.fullmatch("[a-zA-Z0-9_-]+", name):
            raise ValueError("Selección de motor incorrecta.")
        return runtime / "engines" / name / "engine/ace-server.exe"
    packaged = root / "engine/ace-server.exe"
    return packaged if packaged.exists() else runtime / "build/Release/ace-server.exe"
