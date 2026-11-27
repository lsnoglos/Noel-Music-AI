"""Private reusable, authorized voice references; no training or network access."""
import array
import os
import datetime
import hashlib
import json
import math
import shutil
import tempfile
import uuid
import wave
from pathlib import Path
from .studio import write_json
from .player import Player

def read_pcm(path, limit=300):
    with wave.open(str(path),"rb") as f:
        rate,channels,n=f.getframerate(),f.getnchannels(),f.getnframes()
        if f.getsampwidth()!=2 or channels not in (1,2) or not 8000<=rate<=96000 or not 1<=n/rate<=limit:
            raise ValueError("Usa WAV PCM de 16 bits, mono o estéreo, de duración compatible.")
        raw=f.readframes(n)
        if len(raw)!=n*channels*2:
            raise ValueError("WAV incompleto.")
    return array.array("h",raw),rate,channels

def resample(samples,rate,channels,target=44100,out_channels=None):
    out_channels=out_channels or channels
    if rate==target and channels==out_channels:
        return samples
    n=len(samples)//channels
    result=array.array("h")
    for i in range(round(n*target/rate)):
        a=min(n-1,i*rate//target)
        b=min(n-1,a+1)
        fraction=(i*rate%target)/target
        for c in range(out_channels):
            if channels==2 and out_channels==1:
                x=(samples[2*a]+samples[2*a+1])/2
                y=(samples[2*b]+samples[2*b+1])/2
            else:
                k=min(c,channels-1)
                x=samples[a*channels+k]
                y=samples[b*channels+k]
            result.append(round(x+(y-x)*fraction))
    return result

def save_pcm(path,samples,rate=44100,channels=1):
    with wave.open(str(path),"wb") as f:
        f.setparams((channels,2,rate,0,"NONE","not compressed"))
        f.writeframes(samples.tobytes())

def hash_file(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def create_profile(root,source,name,consent,kind="Hablada",transcript=""):
    if not consent:
        raise ValueError("Confirma que es tu voz o tienes autorización.")
    transcript=transcript.strip()
    if len(transcript)>2000:
        raise ValueError("La transcripción supera 2000 caracteres.")
    name=name.strip()
    if not name or len(name)>80 or any(ord(c)<32 for c in name):
        raise ValueError("Escribe un nombre de perfil válido.")
    if kind not in ("Hablada","Cantada"):
        raise ValueError("Tipo de referencia desconocido.")
    samples,rate,channels=read_pcm(source,30.5)
    mono=resample(samples,rate,channels,44100,1)
    seconds=len(mono)/44100
    if seconds<5:
        raise ValueError("Graba al menos 5 segundos; recomendamos 15–30.")
    peak=max(abs(min(mono)),abs(max(mono)))
    rms=math.sqrt(sum(x*x for x in mono)/len(mono))
    if peak<150 or rms<50:
        raise ValueError("La grabación está demasiado silenciosa.")
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    if any(p["name"].casefold()==name.casefold() for p in profiles(root)):
        raise ValueError("Ya existe un perfil con ese nombre.")
    folder=Path(tempfile.mkdtemp(prefix=".pending-",dir=root))
    ident=uuid.uuid4().hex
    try:
        path=folder/"reference.wav"
        save_pcm(path,mono)
        data=dict(id=ident,name=name,kind=kind,seconds=seconds,authorized=True,
                  sha256=hash_file(path),peak=peak/32768,rms=rms/32768,transcript=transcript)
        write_json(folder/"profile.json",data)
        folder.rename(root/ident)
        return data
    finally:
        if folder.exists():
            shutil.rmtree(folder)

def profiles(root):
    result=[]
    for path in Path(root).glob("*/profile.json"):
        try:
            data=json.loads(path.read_text("utf-8"))
            if (path.parent.name!=data["id"] or len(data["id"])!=32 or
                    any(c not in "0123456789abcdef" for c in data["id"]) or
                    not data["authorized"] or not isinstance(data["name"],str) or
                    not (path.parent/"reference.wav").is_file()):
                continue
            result.append(data)
        except (OSError,ValueError,KeyError,TypeError):
            pass
    return sorted(result,key=lambda p:p["name"].casefold())

def reference(root,profile):
    path=Path(root)/profile["id"]/"reference.wav"
    if not profile["authorized"] or hash_file(path)!=profile["sha256"]:
        raise ValueError("La referencia vocal fue modificada o no es válida.")
    return path

def remove_profile(root,profile):
    reference(root,profile)
    shutil.rmtree(Path(root)/profile["id"])

class Recorder:
    """Windows MCI waveaudio uses the default recording device."""
    def __init__(self):
        self.api=Player()
        self.active=False
    def start(self):
        if self.active:
            raise ValueError("Ya hay una grabación.")
        self.api.send("open new type waveaudio alias noelrecorder")
        self.active=True
        try:
            self.api.send("set noelrecorder time format milliseconds")
            self.api.send("set noelrecorder format tag pcm channels 1 samplespersec 44100 bitspersample 16 alignment 2 bytespersec 88200")
            self.api.send("record noelrecorder")
        except Exception:
            self.close()
            raise
    def stop(self,path):
        if not self.active:
            raise ValueError("No hay grabación activa.")
        try:
            self.api.send("stop noelrecorder")
            self.api.send(f'save noelrecorder "{path}"')
        finally:
            self.close()
    def close(self):
        if self.active:
            try:
                self.api.send("close noelrecorder")
            finally:
                self.active=False


def import_audio(source,destination):
    """Bound decoding to five minutes; the source is never changed."""
    try:
        import miniaudio
    except ImportError as exc:
        raise RuntimeError("Falta el decodificador MP3/WAV. Aplica la actualización oficial con ui-wheels y vuelve a abrir Noel Music AI.") from exc
    source=Path(source)
    if source.suffix.lower() not in (".mp3",".wav") or source.stat().st_size>128*1024**2:
        raise ValueError("Selecciona MP3 o WAV de hasta 128 MiB.")
    stream=miniaudio.stream_file(str(source),output_format=miniaudio.SampleFormat.SIGNED16,nchannels=2,sample_rate=44100)
    frames=0
    try:
        with wave.open(str(destination),"wb") as f:
            f.setparams((2,2,44100,0,"NONE","not compressed"))
            for block in stream:
                frames+=len(block)//2
                if frames>300*44100:
                    raise ValueError("El audio supera cinco minutos.")
                f.writeframesraw(block.tobytes())
        if frames<5*44100:
            raise ValueError("La muestra debe durar al menos cinco segundos.")
        return frames/44100
    except Exception:
        Path(destination).unlink(missing_ok=True)
        raise
    finally:
        stream.close()

def clip_reference(source,destination,start):
    with wave.open(str(source),"rb") as f:
        rate=f.getframerate()
        total=f.getnframes()
        pos=max(0,min(round(start*rate),max(0,total-5*rate)))
        f.setpos(pos)
        data=f.readframes(min(30*rate,total-pos))
        with wave.open(str(destination),"wb") as out:
            out.setparams(f.getparams())
            out.writeframes(data)

def phrase_history(folder):
    folder=Path(folder)
    items=[]
    for path in (folder/"phrases").glob("*/phrase.json"):
        try:
            item=json.loads(path.read_text("utf-8"))
            if item["id"]!=path.parent.name or not (path.parent/"audio.wav").is_file():
                continue
            items.append(dict(item,path=path.parent/"audio.wav"))
        except (OSError,ValueError,KeyError,TypeError):
            continue
    items.sort(key=lambda x:x.get("created",""),reverse=True)
    if (folder/"preview.wav").is_file():
        items.append(dict(id="legacy",text="Prueba anterior (texto no registrado)",language="",path=folder/"preview.wav"))
    return items

def save_phrase(folder,audio,text,language):
    root=Path(folder)/"phrases"
    root.mkdir(exist_ok=True)
    ident=uuid.uuid4().hex
    stage=Path(tempfile.mkdtemp(prefix=".pending-",dir=root))
    try:
        shutil.copyfile(audio,stage/"audio.wav")
        write_json(stage/"phrase.json",dict(id=ident,text=text,language=language,created=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        stage.rename(root/ident)
        return root/ident/"audio.wav"
    finally:
        if stage.exists():
            shutil.rmtree(stage)

def commit_draft(root,draft,profile,name):
    name=name.strip()
    if not name or len(name)>80 or any(ord(c)<32 for c in name):
        raise ValueError("Escribe un nombre de perfil válido.")
    if not phrase_history(Path(draft)/profile["id"]):
        raise ValueError("Genera una frase de prueba antes de guardar el perfil.")
    if any(p["name"].casefold()==name.casefold() for p in profiles(root)):
        raise ValueError("Ya existe un perfil con ese nombre.")
    reference(draft,profile)
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".pending-",dir=root))
    try:
        shutil.copytree(Path(draft)/profile["id"],stage,dirs_exist_ok=True)
        saved=dict(profile,name=name)
        write_json(stage/"profile.json",saved)
        stage.rename(root/profile["id"])
        return saved
    finally:
        if stage.exists():
            shutil.rmtree(stage)
