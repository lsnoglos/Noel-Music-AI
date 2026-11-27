"""Adapter for the asynchronous ace-server contract at the pinned revision."""
import http.client
import io
import json
import re
import sys
import time
import wave
from email.message import Message

from .models import MODELS

ENGINE = "973517be024ff8b6bbd50e0adc9e308ab2ed71b3"
MAX_BODY = 80 * 1024 * 1024  # 300 s stereo PCM16 + latent + multipart overhead


def unpack(content_type, data, seconds):
    header = Message()
    header["Content-Type"] = content_type
    boundary = header.get_boundary()
    if header.get_content_type() != "multipart/mixed" or not boundary:
        raise ValueError("Respuesta sin pistas multipart.")
    marker = b"--" + boundary.encode("ascii")
    blocks = data.split(b"\r\n" + marker)
    if len(blocks) != 3 or not blocks[0].startswith(marker + b"\r\n") or blocks[-1].strip() != b"--":
        raise ValueError("Se esperaba exactamente una pareja WAV/latente.")
    audio_hdr, wav = blocks[0][len(marker):].split(b"\r\n\r\n", 1)
    latent_hdr, latent = blocks[1].split(b"\r\n\r\n", 1)
    if b"content-type: audio/wav" not in audio_hdr.lower() or b'name="latent"' not in latent_hdr.lower() or b"application/octet-stream" not in latent_hdr.lower():
        raise ValueError("Tipos de pista incorrectos.")
    if not latent or len(latent) % 256:
        raise ValueError("Latente incompleto.")
    with wave.open(io.BytesIO(wav)) as audio:
        frames, rate = audio.getnframes(), audio.getframerate()
        if rate != 48000 or audio.getnchannels() != 2 or audio.getsampwidth() != 2:
            raise ValueError("El motor devolvió un formato PCM inesperado.")
        actual = frames / rate
        if abs(actual - seconds) > 1 or abs(actual - len(latent) / 256 / 25) > 1:
            raise ValueError("Duración de audio o latente inesperada.")
        pcm = audio.readframes(frames)
        if len(pcm) != frames * 4 or not pcm.strip(b"\x00"):
            raise ValueError("WAV truncado o silencioso.")
    return wav, latent, actual


class Engine:
    def __init__(self, port=8085, cancelled=None):
        self.cancelled = cancelled
        self.port = port

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            conn.request(method, path, body, {"Content-Type": "application/json"})
            response = conn.getresponse()
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise ValueError("Respuesta demasiado grande.")
            if response.status != 200:
                raise RuntimeError(f"Motor HTTP {response.status}: {data[:500]!r}")
            return response.getheader("Content-Type", ""), data
        finally:
            conn.close()

    def metadata(self, method, path, body=None):
        return json.loads(self.request(method, path, body)[1])

    def ready(self):
        if self.metadata("GET", "/health").get("status") != "ok":
            raise RuntimeError("El motor aún no está disponible.")
        props = self.metadata("GET", "/props")
        version = props.get("version", "").split(" ")[0]
        if len(version) < 7 or not ENGINE.startswith(version):
            raise ValueError("Versión del motor incompatible. Ejecute el instalador de esta revisión.")
        for bucket, (name, _, _) in MODELS.items():
            if name not in props["models"].get(bucket, []):
                raise ValueError(f"El motor necesita {name}.")
        if props["models"]["embedding"][0] != MODELS["embedding"][0]:
            raise ValueError("Use una carpeta dedicada: el motor selecciona el primer embedding.")
        return props


    def generate(self, payload, timeout=900):
        return unpack(*self.job("/synth", payload, timeout), payload["duration"])

    def compose(self, payload, timeout=300):
        _, data = self.job("/lm", payload, timeout)
        result = json.loads(data)
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise ValueError("Respuesta inesperada del compositor.")
        lyrics = result[0].get("lyrics")
        if not isinstance(lyrics, str) or not lyrics.strip() or lyrics.strip() == "[Instrumental]":
            raise ValueError("El compositor no devolvió una letra utilizable.")
        if len(lyrics) > 16000:
            raise ValueError("La letra generada supera el límite del editor.")
        return lyrics

    def job(self, endpoint, payload, timeout):
        job = self.metadata("POST", endpoint, json.dumps(payload).encode())["id"]
        if not isinstance(job, str) or not re.fullmatch(r"[0-9a-f]{16}", job):
            raise ValueError("Identificador de trabajo incorrecto.")
        print(f"Trabajo {job} recibido por el motor.", flush=True)
        path = f"/job?id={job}"
        end = time.monotonic() + timeout
        try:
            while time.monotonic() < end:
                if self.cancelled and self.cancelled.is_set():
                    raise InterruptedError("Cancelación solicitada.")
                status = self.metadata("GET", path)["status"]
                if status == "done":
                    return self.request("GET", path + "&result=1")
                if status != "running":
                    raise RuntimeError(f"Estado del trabajo {job}: {status}. Consulte la consola del motor.")
                time.sleep(0.5)
            raise TimeoutError(f"Tiempo agotado para el trabajo {job}.")
        except (KeyboardInterrupt, OSError, TimeoutError):
            try:
                self.metadata("POST", path + "&cancel=1", b"")
            except Exception as error:
                print(f"No se pudo confirmar la cancelación: {error}", file=sys.stderr)
            raise
