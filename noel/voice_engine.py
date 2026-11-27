"""Optional audio.cpp v0.9.6: verified downloads and sequential local SVC pipeline."""
import array
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path
from .voice_profiles import read_pcm,resample,save_pcm,hash_file
from .studio import write_json

TAG="v0.9.6"
RELEASE="https://github.com/0xShug0/audio.cpp/releases/download/"+TAG+"/"
HF="https://huggingface.co/audio-cpp/audio.cpp-gguf/resolve/"
MODELS={
    "demucs":("HTDemucs-GGUF/htdemucs-q8_0.gguf",61940768,"b0f532ac6e5f373aeb11fa0df73253251e133832d9c8b9942dc58f50bc5b4388","4c9a3098d552a0f3d9b2adc11638a11022c07d7e"),
    "seed":("SeedVC-MLX-GGUF/seed-vc-mlx-q8_0.gguf",3120809440,"17aaccb16e230a5b105187b7bccf3a67ec9899047cddac255c335c73091a88c8","6f45df32f8fb283e4cfce3d3e1cb7688986fcbe6"),
}
ASSETS={
    "cpu":[("audio-v0.9.6-bin-windows-x64-cpu-portable.zip",35202438,"5d2e7fe24dbec0f8267db00ab2c6ccdd24799d916cb7beef3168eb66a53a4077")],
    "gpu":[("audio-v0.9.6-bin-windows-x64-cuda12.4.zip",471249296,"ff7783e29b02e9006fa4304b9cdeffa030cd5a184998090f769f0a1d221b2698"),
           ("audio-v0.9.6-cudart-windows-x64-cuda12.4.zip",607273675,"283fbf6927021b8e73cd22e6c3c300c2d12adb66361bc1d392401e1ca2759297")],
}
def kind(mode):
    return "cpu" if mode=="cpu" else "gpu"
def model_path(root,key):
    return Path(root)/"voice-models"/MODELS[key][0]
def runtime_dir(root,mode):
    return Path(root)/"voice-engines"/(TAG+"-"+kind(mode))
def model_ready(root,key):
    path=model_path(root,key)
    _,size,digest,_=MODELS[key]
    return path.is_file() and path.stat().st_size==size and hash_file(path)==digest
def binary(root,mode,verify=True):
    folder=runtime_dir(root,mode)
    try:
        meta=json.loads((folder/"manifest.json").read_text("utf-8"))
        cli=folder/"audiocpp_cli.exe"
        if not cli.is_file() or "audiocpp_cli.exe" not in meta:
            return None
        if verify and any(Path(n).name!=n or not (folder/n).is_file() or hash_file(folder/n)!=h for n,h in meta.items()):
            return None
        return cli
    except (OSError,ValueError,TypeError,AttributeError):
        return None
def download(url,path,size,digest,cancel,progress):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file() and path.stat().st_size==size and hash_file(path)==digest:
        return
    if shutil.disk_usage(path.parent).free<size:
        raise ValueError("Espacio insuficiente para "+path.name)
    part=path.with_suffix(path.suffix+".part")
    h=hashlib.sha256()
    n=0
    try:
        with urllib.request.urlopen(url,timeout=45) as response,part.open("wb") as out:
            while data:=response.read(1024*1024):
                if cancel.is_set():
                    raise InterruptedError("Descarga cancelada")
                n+=len(data)
                if n>size:
                    raise ValueError("Tamaño incorrecto: "+path.name)
                h.update(data)
                out.write(data)
                progress(path.name,n,size)
        if n!=size or h.hexdigest()!=digest:
            raise ValueError("SHA-256 incorrecto: "+path.name)
        os.replace(part,path)
    finally:
        part.unlink(missing_ok=True)
def install(root,models,mode,cancel,progress):
    for key,(name,size,digest,rev) in MODELS.items():
        download(HF+rev+"/"+name,model_path(models,key),size,digest,cancel,progress)
    if binary(root,mode):
        return
    folder=runtime_dir(root,mode)
    folder.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder.parent) as tmp:
        tmp=Path(tmp)
        stage=tmp/"stage"
        stage.mkdir()
        for name,size,digest in ASSETS[kind(mode)]:
            zip_path=tmp/name
            download(RELEASE+name,zip_path,size,digest,cancel,progress)
            with zipfile.ZipFile(zip_path) as z:
                for item in z.infolist():
                    if cancel.is_set():
                        raise InterruptedError("Instalación cancelada")
                    name=Path(item.filename.replace("\\","/")).name
                    if Path(name).suffix.lower() not in (".dll",".exe",".txt",".md"):
                        continue
                    if not name or ":" in name or item.file_size>2*1024**3:
                        raise ValueError("Archivo de motor inválido")
                    dest=stage/name
                    with z.open(item) as src:
                        if dest.exists():
                            if dest.suffix.lower() in (".txt",".md"):
                                continue
                            if hashlib.file_digest(src,"sha256").hexdigest()!=hash_file(dest):
                                raise ValueError("DLL duplicada incompatible: "+name)
                        else:
                            with dest.open("xb") as out:
                                shutil.copyfileobj(src,out)
        if not (stage/"audiocpp_cli.exe").is_file():
            raise ValueError("El paquete no contiene audiocpp_cli.exe")
        write_json(stage/"manifest.json",{p.name:hash_file(p) for p in stage.iterdir()})
        backup=tmp/"previous"
        if folder.exists():
            folder.rename(backup)
        try:
            stage.rename(folder)
        except Exception:
            if backup.exists():
                backup.rename(folder)
            raise
def run_cli(cli,args,cancel,log_path):
    with log_path.open("w",encoding="utf-8") as log:
        proc=subprocess.Popen([str(cli),*map(str,args)],cwd=cli.parent,stdout=log,stderr=log,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        try:
            deadline=time.monotonic()+3600
            while proc.poll() is None:
                if cancel.wait(.2):
                    raise InterruptedError("Conversión cancelada")
                if time.monotonic()>deadline:
                    raise TimeoutError("El motor vocal superó el límite de ejecución")
            if proc.returncode:
                raise RuntimeError("Falló audio.cpp. Consulta "+str(log_path))
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
def load_stereo(path):
    samples,rate,channels=read_pcm(path)
    return resample(samples,rate,channels,44100,2)
def mix_stems(instrumental,vocal):
    # Match length with at most 250 ms of codec padding; do not time-stretch.
    if abs(len(instrumental)-len(vocal))>22050:
        raise ValueError("La voz convertida no conserva la duración. No se mezclará automáticamente.")
    n=len(instrumental)
    peak=max((abs(int(instrumental[i])+(int(vocal[i]) if i<len(vocal) else 0)) for i in range(n)),default=1)
    gain=min(1.,32767/max(1,peak))
    return array.array("h",(round((int(instrumental[i])+(int(vocal[i]) if i<len(vocal) else 0))*gain) for i in range(n)))
def convert(root,models,runs,source,reference,profile,mode,cancel,stage,request=None,title=None):
    cli=binary(root,mode)
    if cancel.is_set():
        raise InterruptedError("Conversión cancelada")
    if not cli or not all(model_ready(models,key) for key in MODELS):
        raise ValueError("Instala los componentes de conversión vocal en Mis voces.")
    started=time.perf_counter()
    runs=Path(runs)
    runs.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix=".voice-pending-",dir=runs))
    final=runs/uuid.uuid4().hex
    backend="cpu" if mode=="cpu" else "cuda"
    try:
        stage("Preparando audio")
        source_pcm=load_stereo(source)
        seconds=len(source_pcm)/88200
        if seconds>300:
            raise ValueError("Máximo 5 minutos por canción.")
        mixture=folder/"input.wav"
        save_pcm(mixture,source_pcm,44100,2)
        del source_pcm
        stems=folder/"stems"
        stems.mkdir()
        stage("Separando voz e instrumental")
        run_cli(cli,["--task","sep","--family","htdemucs","--model",model_path(models,"demucs"),"--backend",backend,"--audio",mixture,"--out-dir",stems,"--out-format","pcm16"],cancel,Path(root)/"voice-separation.log")
        if cancel.is_set():
            raise InterruptedError("Conversión cancelada")
        def stem(name):
            found=[p for p in stems.rglob("*.wav") if p.stem.lower()==name]
            if len(found)!=1:
                raise ValueError("No se encontró una pista "+name+" única en la salida del separador.")
            return found[0]
        vocal=stem("vocals")
        vocal_pcm,_,_=read_pcm(vocal)
        if max(abs(min(vocal_pcm)),abs(max(vocal_pcm)))<100:
            raise ValueError("No se detectó una pista vocal con nivel suficiente para convertir.")
        del vocal_pcm
        backing=load_stereo(stem("drums"))
        # Accumulate at 32 bits; retain instrumental as separate artifact.
        accum=array.array("i",backing)
        del backing
        for name in ("bass","other"):
            data=load_stereo(stem(name))
            if len(data)!=len(accum):
                raise ValueError("Duración de pistas inconsistente.")
            for i,x in enumerate(data):
                accum[i]+=x
        del data
        peak=max(1,max(abs(min(accum)),abs(max(accum))))
        gain=min(1.,32767/peak)
        instrumental=array.array("h",(round(x*gain) for x in accum))
        del accum
        save_pcm(folder/"instrumental.wav",instrumental,44100,2)
        if cancel.is_set():
            raise InterruptedError("Conversión cancelada")
        stage("Convirtiendo canto con Seed-VC")
        converted=folder/"converted.wav"
        run_cli(cli,["--task","svc","--family","seed_vc","--model",model_path(models,"seed"),"--backend",backend,"--task-route","v1_svc","--audio",vocal,"--voice-ref",reference,"--out",converted,"--out-format","pcm16","--num-inference-steps","30","--request-option","auto_f0_adjust=false"],cancel,Path(root)/"voice-conversion.log")
        stage("Mezclando pistas")
        new_voice=load_stereo(converted)
        result=mix_stems(instrumental,new_voice)
        save_pcm(folder/"song.wav",result,44100,2)
        if cancel.is_set():
            raise InterruptedError("Conversión cancelada")
        metrics=dict(version=final.name,actual_seconds=len(result)/88200,seconds=seconds,total_s=time.perf_counter()-started)
        write_json(folder/"version.json",dict(request=request or {"caption":"Conversión vocal","lyrics":""},metrics=metrics,
                  ai_generated=True,wav_sha256=hash_file(folder/"song.wav"),
                  editing=dict(mode="voice_conversion",source_sha256=hash_file(source),voice_profile_id=profile["id"],
                               voice_reference_sha256=profile["sha256"],reference_authorized=True,engine=TAG,
                               instrumental_sha256=hash_file(folder/"instrumental.wav"),separated_instrumental=True)))
        write_json(folder/"display.json",{"title":(title or Path(source).stem)+" · "+profile["name"]})
        mixture.unlink()
        folder.rename(final)
        return metrics
    finally:
        if folder.exists():
            shutil.rmtree(folder)
