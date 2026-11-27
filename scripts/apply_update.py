"""Apply an extracted, verified app update without replacing engine or user data."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ALLOWED = {"noel", "scripts", "docs", "ui-wheels", "README.md", "NoelMusicAI.cmd",
           "THIRD_PARTY_NOTICES.md", "LICENSE", "requirements-ui.txt", "PROJECT_STATUS.md", "CHANGELOG.md"}


def apply(source, target):
    source, target = source.resolve(), target.resolve()
    if source == target or source.is_relative_to(target):
        raise ValueError("Extrae la actualización en otra carpeta, fuera de la instalación.")
    if not (target/"NoelMusicAI.cmd").is_file() or not (target/"engine/ace-server.exe").is_file():
        raise ValueError("Selecciona la carpeta de la instalación portable completa.")
    manifest = json.loads((source/"update-manifest.json").read_text("utf-8"))
    if (target/"engine-revision.txt").read_text(encoding="utf-8-sig").strip() != manifest["engine"]:
        raise ValueError("Motor incompatible. Descarga el paquete completo.")
    paths = manifest["files"]
    groups = set()
    for name, digest in paths.items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or path.parts[0] not in ALLOWED:
            raise ValueError("Ruta de actualización inválida.")
        file = source/"app"/path
        if file.is_symlink() or not file.is_file():
            raise ValueError("Archivo de actualización ausente.")
        with file.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != digest:
                raise ValueError("Hash incorrecto: "+name)
        groups.add(path.parts[0])
    if not {"noel", "scripts", "NoelMusicAI.cmd", "requirements-ui.txt"}.issubset(groups):
        raise ValueError("Paquete de actualización incompleto.")
    lock = target/".update-lock"
    lock.touch(exist_ok=False)
    backup = Path(tempfile.mkdtemp(prefix=".noel-update-backup-", dir=target))
    stage = Path(tempfile.mkdtemp(prefix=".noel-update-stage-", dir=target))
    moved, installed = [], []
    try:
        for name in paths:
            dest = stage/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source/"app"/name, dest)
        for name in sorted(groups):
            original = target/name
            if original.exists():
                os.replace(original, backup/name)
                moved.append(name)
            os.replace(stage/name, original)
            installed.append(name)
    except Exception:
        for name in reversed(installed):
            os.replace(target/name, stage/name)
        for name in reversed(moved):
            os.replace(backup/name, target/name)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        lock.unlink(missing_ok=True)
    print("Actualización instalada. Copia anterior:", backup)
    return backup


if __name__ == "__main__":
    try:
        apply(Path(__file__).resolve().parent, Path(sys.argv[1]))
    except Exception as exc:
        sys.exit("Actualización no aplicada: " + str(exc))
