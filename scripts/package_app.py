"""Create an application-only update and assemble a portable from a pinned verified engine."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noel.engine import ENGINE
from noel.runtime import verify_engine

APP = ("noel", "scripts", "docs", "README.md", "NoelMusicAI.cmd", "THIRD_PARTY_NOTICES.md",
       "LICENSE", "requirements-ui.txt", "PROJECT_STATUS.md", "CHANGELOG.md")
UPDATE = "NoelMusicAI-Update.zip"
FULL = "NoelMusicAI-Windows.zip"


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def entries(root):
    return sorted(p for p in root.rglob("*") if p.is_file())


def archive(root, dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for p in entries(root):
            z.write(p, p.relative_to(root).as_posix())
    dest.with_name(dest.name + ".sha256").write_text(sha(dest) + "\n", encoding="ascii")


def app_payload(dest, wheels=True):
    dest.mkdir(parents=True, exist_ok=True)
    for name in APP:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest/name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
        else:
            shutil.copy2(src, dest/name)
    if wheels:
        (dest/"ui-wheels").mkdir()
        for py in ("311", "312", "313", "314"):
            subprocess.run([sys.executable, "-m", "pip", "download", "--only-binary=:all:",
                            "--platform", "win_amd64", "--implementation", "cp", "--python-version", py,
                            "--dest", str(dest/"ui-wheels"), "-r", str(ROOT/"requirements-ui.txt")], check=True)


def make_update(output):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        app_payload(root/"app")
        shutil.copy2(ROOT/"scripts/apply-update.ps1", root/"apply-update.ps1")
        shutil.copy2(ROOT/"scripts/apply_update.py", root/"apply_update.py")
        (root/"Actualizar.cmd").write_text('@echo off\r\npowershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0apply-update.ps1"\r\nif errorlevel 1 pause\r\n', encoding="ascii")
        manifest = {p.relative_to(root/"app").as_posix(): sha(p) for p in entries(root/"app")}
        (root/"update-manifest.json").write_text(json.dumps({"engine": ENGINE, "files": manifest}, indent=2), encoding="utf-8")
        archive(root, output/UPDATE)


def fetch_base(dest, base):
    if base["revision"] != ENGINE:
        raise ValueError("El manifiesto no coincide con el motor fijado; compila un motor nuevo y actualiza engine-base.json.")
    with urllib.request.urlopen(base["url"], timeout=60) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f, length=1024*1024)
    if dest.stat().st_size != base["size"] or sha(dest) != base["sha256"]:
        raise ValueError("SHA-256 o tamaño del motor base incorrecto.")


def extract_engine(source, dest):
    (dest/"engine").mkdir()
    with zipfile.ZipFile(source) as z:
        for item in z.infolist():
            name = item.filename.replace("\\", "/")
            if name not in ("engine-manifest.json", "engine-revision.txt") and not re.fullmatch(r"engine/[A-Za-z0-9_.-]+\.(dll|exe|txt)", name, re.I):
                continue
            with z.open(item) as src, (dest/name).open("xb") as out:
                shutil.copyfileobj(src, out)
    if (dest/"engine-revision.txt").read_text(encoding="utf-8-sig").strip() != ENGINE:
        raise ValueError("Revisión de motor incorrecta.")
    manifest = json.loads((dest/"engine-manifest.json").read_text(encoding="utf-8-sig"))
    if {p.name for p in (dest/"engine").iterdir()} != {entry["name"] for entry in manifest}:
        raise ValueError("Inventario de DLL diferente del manifiesto.")
    verify_engine(dest/"engine/ace-server.exe")


def make_full(output, update):
    base = json.loads((ROOT/"scripts/engine-base.json").read_text("utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root/"engine-base.zip"
        fetch_base(source, base)
        stage = root/"portable"
        stage.mkdir()
        extract_engine(source, stage)
        # Reuse the exact already-tested application payload from the update job.
        with zipfile.ZipFile(update) as z:
            manifest = json.loads(z.read("update-manifest.json"))
            if manifest["engine"] != ENGINE:
                raise ValueError("Actualización incompatible.")
            for name, digest in manifest["files"].items():
                path = Path(name)
                if path.is_absolute() or ".." in path.parts or path.parts[0] not in (*APP, "ui-wheels"):
                    raise ValueError("Ruta de aplicación inválida.")
                dst = stage/path
                dst.parent.mkdir(parents=True, exist_ok=True)
                with z.open("app/"+name) as src, dst.open("xb") as out:
                    shutil.copyfileobj(src, out)
                if sha(dst) != digest:
                    raise ValueError("Integridad de aplicación incorrecta.")
        subprocess.run([sys.executable, "-m", "tests.server_contract", str(stage/"engine/ace-server.exe")], cwd=ROOT, check=True)
        archive(stage, output/FULL)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=("update", "full"))
    p.add_argument("--output", type=Path, default=ROOT)
    p.add_argument("--update", type=Path, default=ROOT/UPDATE)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.kind == "update":
        make_update(args.output)
    else:
        make_full(args.output, args.update)


if __name__ == "__main__":
    main()
