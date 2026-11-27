"""Install private UI/audio dependencies from the portable wheelhouse."""
import hashlib
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from tkinter import ttk

MODULES=("ttkbootstrap","PIL","lameenc","miniaudio")
last_error=""

def interpreter():
    exe=Path(sys.executable)
    console=exe.with_name("python.exe")
    return str(console if exe.name.lower()=="pythonw.exe" and console.is_file() else exe)

def probe(target):
    code="import sys; sys.path.insert(0,sys.argv[1]); import ttkbootstrap, PIL.Image, lameenc, miniaudio"
    return subprocess.run([interpreter(),"-I","-S","-c",code,str(target)],capture_output=True,text=True,
                          timeout=30,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))

def install_private(root,runtime):
    """Version dependency directories by requirements, not just Python version.
    Validate actual imports in a fresh interpreter before using the directory."""
    root,runtime=Path(root),Path(runtime)
    req=root/"requirements-ui.txt"
    stamp=hashlib.sha256(req.read_bytes()).hexdigest()[:16]
    version=f"{sys.version_info.major}.{sys.version_info.minor}"
    target=runtime/f"ui-{version}-{stamp}"
    log=runtime/"ui-dependencies.log"
    runtime.mkdir(parents=True,exist_ok=True)
    def record(text):
        log.write_text(text,encoding="utf-8",errors="replace")
    if target.is_dir():
        check=probe(target)
        if check.returncode==0:
            return target
        record(check.stdout+"\n"+check.stderr)
    wheels=root/"ui-wheels"
    if not wheels.is_dir():
        raise RuntimeError("Falta la carpeta ui-wheels. Usa el paquete oficial NoelMusicAI-Update.zip o NoelMusicAI-Windows.zip, no el ZIP del código fuente.")
    stage=Path(tempfile.mkdtemp(prefix=".ui-install-",dir=runtime))
    try:
        result=subprocess.run([interpreter(),"-m","pip","--disable-pip-version-check","install",
                               "--no-index","--find-links",str(wheels),"--target",str(stage),
                               "--ignore-installed","-r",str(req)],capture_output=True,text=True,
                              timeout=180,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        record(result.stdout+"\n"+result.stderr)
        if result.returncode:
            raise RuntimeError("No se pudieron instalar las bibliotecas incluidas. Consulta "+str(log))
        result=probe(stage)
        if result.returncode:
            record(result.stdout+"\n"+result.stderr)
            raise RuntimeError("Las bibliotecas instaladas no superaron la comprobación. Consulta "+str(log))
        if target.exists():
            # This directory is only an isolated dependency cache, not user data.
            shutil.rmtree(target)
        stage.rename(target)
        record("Dependencias verificadas: "+str(target))
        return target
    finally:
        if stage.exists():
            shutil.rmtree(stage,ignore_errors=True)

def create_style(window,root,runtime):
    global last_error
    last_error=""
    root,runtime=Path(root),Path(runtime)
    legacy=runtime/f"ui-{sys.version_info.major}.{sys.version_info.minor}"
    if legacy.is_dir():
        sys.path.insert(0,str(legacy))
    try:
        if (root/"ui-wheels").is_dir():
            target=install_private(root,runtime)
            sys.path.insert(0,str(target))
            importlib.invalidate_caches()
        else:
            # Source/development installations may already have all dependencies.
            for module in MODULES:
                importlib.import_module(module)
    except (ImportError,OSError,RuntimeError,subprocess.SubprocessError) as exc:
        last_error=str(exc)
        try:
            (runtime/"ui-dependencies.log").open("a",encoding="utf-8").write("\n"+last_error+"\n")
        except OSError:
            pass
    # A missing audio codec must not disable an otherwise healthy theme.
    try:
        import ttkbootstrap
        return ttkbootstrap.Style(theme="darkly"),True
    except Exception as exc:
        if not last_error:
            last_error=str(exc)
        return ttk.Style(window),False
