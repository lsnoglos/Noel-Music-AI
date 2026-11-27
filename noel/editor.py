"""First local editing increment: native ACE-Step, never overwrite the source."""
import hashlib
import io
import math
import shutil
import tempfile
import time
import uuid
import wave
from pathlib import Path

from .models import catalog, MODELS, MUSIC, REVISION
from .studio import write_json

MODES = {
    "cover": "Cambiar letra · conservar referencia (experimental)",
    "repaint": "Editar un fragmento · Repaint",
    "voice": "Nueva canción · referencia de voz autorizada (experimental)",
}
FIDELITY = {
    "Libre": (.45, .0),
    "Equilibrada": (.8, .15),
    "Alta": (1., .25),
}


def read_wav(path):
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".wav" or path.stat().st_size > 64*1024*1024:
        raise ValueError("Selecciona un WAV PCM de hasta 64 MiB.")
    data = path.read_bytes()
    with wave.open(io.BytesIO(data)) as f:
        channels, rate, width, frames = f.getnchannels(), f.getframerate(), f.getsampwidth(), f.getnframes()
        if width != 2 or channels not in (1,2) or rate not in (44100,48000) or not 1 <= frames/rate <= 300:
            raise ValueError("Usa WAV PCM 16 bits, mono/estéreo, 44.1 o 48 kHz, de 1 a 300 s.")
        pcm = f.readframes(frames)
        if len(pcm) != frames*channels*width:
            raise ValueError("WAV incompleto.")
    return data, frames/rate, (channels,rate,width,frames)


def exact_outside(source, generated, start, end):
    """Keep source PCM byte-for-byte outside an edit range; requires native format."""
    with wave.open(io.BytesIO(source)) as orig, wave.open(io.BytesIO(generated)) as edited:
        fmt = (orig.getnchannels(),orig.getframerate(),orig.getsampwidth())
        if fmt != (2,48000,2) or fmt != (edited.getnchannels(),edited.getframerate(),edited.getsampwidth()):
            raise ValueError("Preservación PCM exacta requiere WAV estéreo 48 kHz 16 bits.")
        frames=orig.getnframes()
        a,b=round(start*48000),round(end*48000)
        if not 0<=a<b<=frames or edited.getnframes()<b:
            raise ValueError("El resultado no cubre todo el fragmento.")
        raw=orig.readframes(frames)
        edited.setpos(a)
        middle=edited.readframes(b-a)
        if len(middle)!=(b-a)*4:
            raise ValueError("Fragmento incompleto.")
        buf=io.BytesIO()
        with wave.open(buf,"wb") as output:
            output.setparams((2,2,48000,0,"NONE","not compressed"))
            output.writeframes(raw[:a*4]+middle+raw[b*4:])
        return buf.getvalue()


def edit_song(engine, props, root, source_path, mode, caption, lyrics, language, model, seed,
              fidelity="Equilibrada", start=0., end=10., duration=30, consent=False, preserve_pcm=True):
    if not consent:
        raise ValueError("Confirma autorización sobre la grabación y las voces.")
    if mode not in MODES or model not in MUSIC or fidelity not in FIDELITY:
        raise ValueError("Modo o modelo no admitido.")
    if not caption.strip() or not lyrics.strip() or len(caption)>8000 or len(lyrics)>16000:
        raise ValueError("Escribe una descripción musical y la nueva letra.")
    if not 0<=seed<2**31:
        raise ValueError("Semilla fuera de rango.")
    data, source_seconds, fmt=read_wav(source_path)
    if mode=="voice" and source_seconds>30:
        raise ValueError("Para referencia de voz utiliza un fragmento autorizado de 1 a 30 s, preferiblemente aislado.")
    if mode=="voice" and not 1<=duration<=300:
        raise ValueError("Duración nueva fuera de rango.")
    if mode=="repaint" and not (math.isfinite(start) and math.isfinite(end) and 0<=start<end<=source_seconds):
        raise ValueError("El intervalo debe estar dentro de la canción original.")
    if mode=="repaint" and preserve_pcm and fmt[:3]!=(2,48000,2):
        raise ValueError("Para conservar exactamente el audio fuera del intervalo, usa WAV estéreo 48 kHz 16 bits o desactiva esa opción.")
    name=catalog()[model][0]
    if name not in props.get("models",{}).get("dit",[]):
        raise ValueError("El motor no reconoce el modelo seleccionado.")
    steps=50 if model=="sft" else 8
    seconds=duration if mode=="voice" else source_seconds
    payload=dict(caption=caption,lyrics=lyrics,vocal_language=language,duration=seconds,seed=seed,
                 task_type="text2music" if mode=="voice" else "repaint" if mode=="repaint" else "cover-nofsq",
                 output_format="wav16",inference_steps=steps,synth_batch_size=1,synth_model=name,vae=MODELS["vae"][0])
    parts={"ref_audio":data} if mode=="voice" else {"audio":data}
    if mode=="cover":
        strength,noise=FIDELITY[fidelity]
        payload.update(audio_cover_strength=strength,cover_noise_strength=noise)
        parts["ref_audio"]=data
    if mode=="repaint":
        payload.update(repainting_start=start,repainting_end=end)
    started=time.perf_counter()
    wav,latent,actual=engine.edit(payload,parts)
    spliced=mode=="repaint" and preserve_pcm
    if spliced:
        wav=exact_outside(data,wav,start,end)
        actual=source_seconds
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix=".pending-",dir=root))
    final=root/uuid.uuid4().hex
    try:
        (folder/"song.wav").write_bytes(wav)
        latent_file="engine-before-splice.vae" if spliced else "song.vae"
        (folder/latent_file).write_bytes(latent)
        metrics=dict(version=final.name,seconds=seconds,actual_seconds=actual,
                     total_s=time.perf_counter()-started,model=name,steps=steps,seed=seed)
        write_json(folder/"version.json",dict(request=payload,metrics=metrics,props=props,
            models_revision=REVISION,ai_generated=True,wav_sha256=hashlib.sha256(wav).hexdigest(),
            latent_sha256=hashlib.sha256(latent).hexdigest(),latent_file=latent_file,
            editing=dict(mode=mode,source_sha256=hashlib.sha256(data).hexdigest(),source_name=Path(source_path).name,
                         fidelity=fidelity,pcm_outside_exact=spliced,reference_authorized=True,
                         latent_corresponds_to_final_audio=not spliced)))
        write_json(folder/"display.json",{"title":Path(source_path).stem+" · "+{"cover":"Nueva letra","repaint":"Fragmento editado","voice":"Nueva canción"}[mode]})
        folder.rename(final)
        return metrics
    finally:
        if folder.exists():
            shutil.rmtree(folder)
