"""Export existing PCM to MP3 without regenerating music."""
import os
import shutil
import tempfile
import wave
from pathlib import Path


def export_audio(source, destination, format="wav"):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Elige otra ubicación para exportar.")
    if format not in ("wav", "mp3"):
        raise ValueError("Formato no admitido.")
    fd, path = tempfile.mkstemp(prefix=".noel-export-", dir=destination.parent)
    os.close(fd)
    temp = Path(path)
    try:
        if format == "wav":
            shutil.copyfile(source, temp)
        else:
            try:
                import lameenc
            except ImportError as exc:
                raise RuntimeError("Falta el codificador MP3. Instala las dependencias de la versión portable.") from exc
            with wave.open(str(source)) as wav, temp.open("wb") as out:
                if wav.getsampwidth() != 2:
                    raise ValueError("Se requiere WAV PCM de 16 bits.")
                encoder = lameenc.Encoder()
                encoder.set_bit_rate(320)
                encoder.set_in_sample_rate(wav.getframerate())
                encoder.set_channels(wav.getnchannels())
                encoder.set_quality(2)
                while data := wav.readframes(65536):
                    out.write(encoder.encode(data))
                out.write(encoder.flush())
        if not temp.stat().st_size:
            raise ValueError("La exportación está vacía.")
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
