import csv
import hashlib
import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from .diagnostics import PeakMonitor
from .models import MODELS, OPTIONAL, REVISION


def write_json(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def render(engine, props, root, caption, lyrics, seconds, seed, model="dit"):
    if not caption.strip() or len(caption) > 8000 or len(lyrics) > 16000:
        raise ValueError("Revise la descripción y la extensión de la letra.")
    if not 1 <= seconds <= 300 or not 0 <= seed < 2**31:
        raise ValueError("Use de 1 a 300 segundos y una semilla entre 0 y 2147483647.")
    if model not in ("dit", "sft"):
        raise ValueError("Modelo musical no admitido.")
    name = MODELS["dit"][0] if model == "dit" else OPTIONAL["sft"][0]
    steps = 8 if model == "dit" else 50
    if model != "dit" and name not in props.get("models", {}).get("dit", []):
        raise ValueError("Instale el modelo SFT antes de seleccionarlo.")
    payload = dict(caption=caption, lyrics=lyrics or "[Instrumental]", vocal_language="es" if lyrics else "unknown",
                   duration=seconds, seed=seed, task_type="text2music", output_format="wav16",
                   inference_steps=steps, synth_batch_size=1, synth_model=name, vae=MODELS["vae"][0])
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    wav, latent, duration = engine.generate(payload)
    received = time.perf_counter()
    folder = Path(tempfile.mkdtemp(prefix=".pending-", dir=root))
    final = root / uuid.uuid4().hex
    try:
        (folder / "song.wav").write_bytes(wav)
        (folder / "song.vae").write_bytes(latent)
        elapsed = time.perf_counter() - started
        result = dict(version=final.name, seconds=seconds, actual_seconds=duration, total_s=elapsed,
                      request_and_transfer_s=received-started, write_audio_s=elapsed-(received-started),
                      rtf=elapsed/duration, model=payload["synth_model"], steps=steps, seed=seed)
        write_json(folder / "version.json", dict(metrics=result, request=payload, props=props,
                   models_revision=REVISION, ai_generated=True, wav_sha256=hashlib.sha256(wav).hexdigest(),
                   latent_sha256=hashlib.sha256(latent).hexdigest()))
        folder.rename(final)
        return result
    finally:
        if folder.exists():
            shutil.rmtree(folder)


def benchmark(engine, props, root, repeats):
    root.mkdir(parents=True, exist_ok=True)
    folder = root / ("benchmark-" + uuid.uuid4().hex)
    folder.mkdir()
    rows = []
    print(folder, flush=True)
    for iteration in range(1, repeats + 1):
        for duration in (15, 30, 60, 120):
            row = dict(iteration=iteration, seconds=duration, model=MODELS["dit"][0], steps=8, seed=42)
            try:
                with PeakMonitor() as monitor:
                    row.update(render(engine, props, folder, "Instrumental acoustic guitar, piano and light percussion",
                                      "", duration, 42))
                row["status"] = "ok"
            except (Exception, KeyboardInterrupt) as exc:
                row.update(status="error", error=str(exc) or type(exc).__name__)
                raise
            finally:
                row.update(peak_system_gpu_mib=monitor.peak_gpu_mib, peak_system_ram_bytes=monitor.peak_ram_bytes)
                rows.append(row)
                write_json(folder / "benchmark.json", rows)
                fields = list(dict.fromkeys(key for item in rows for key in item))
                with (folder / "benchmark.csv.tmp").open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fields)
                    writer.writeheader()
                    writer.writerows(rows)
                (folder / "benchmark.csv.tmp").replace(folder / "benchmark.csv")
                print(f"{duration} s: {row['status']}", flush=True)
