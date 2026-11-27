import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

from .diagnostics import snapshot
from .engine import Engine
from .distribution import binary_path
from .models import MODELS, catalog, install, matches
from .studio import benchmark, render

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"


def main():
    parser = argparse.ArgumentParser(prog="noel", description="Estudio musical local · primera integración")
    parser.add_argument("--port", type=int, default=8085)
    parser.add_argument("--models-dir", type=Path, default=RUNTIME / "models")
    parser.add_argument("--output", type=Path, default=ROOT / "runs")
    cmds = parser.add_subparsers(dest="cmd", required=True)
    models = cmds.add_parser("models")
    models.add_argument("--select", choices=list(catalog()), action="append")
    models.add_argument("--repair", action="store_true")
    models.add_argument("--download", action="store_true")
    cmds.add_parser("diagnose")
    cmds.add_parser("health")
    cmds.add_parser("start").add_argument("--binary", type=Path, default=binary_path(ROOT))
    gen = cmds.add_parser("generate")
    gen.add_argument("caption")
    gen.add_argument("--lyrics", default="")
    gen.add_argument("--seconds", type=int, default=15)
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--model", choices=("dit", "sft"), default="dit")
    gen.add_argument("--language", choices=("es", "en", "pt", "fr", "it", "de", "ja"), default="es")
    cmds.add_parser("benchmark").add_argument("--repeat", type=int, choices=range(1, 11), default=1)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Puerto fuera de rango")
    if args.cmd == "models":
        return install(args.models_dir, args.download, args.select, args.repair)
    if args.cmd == "diagnose":
        print(json.dumps(snapshot(), indent=2))
        return
    if args.cmd == "start":
        info = snapshot()
        if not info["gpu"]:
            raise ValueError("No se detecta NVIDIA GPU 0. Revise nvidia-smi y el controlador.")
        for name, size, sha in MODELS.values():
            if not matches(args.models_dir / name, size, sha):
                raise ValueError(f"Falta un modelo verificado: {name}. Ejecute models --download.")
        chunk = 128 if info["gpu"]["free_mib"] < 6000 else 256
        subprocess.run([str(args.binary.resolve()), "--models", str(args.models_dir.resolve()),
                        "--device", "CUDA0", "--host", "127.0.0.1", "--port", str(args.port),
                        "--max-batch", "1", "--vae-chunk", str(chunk), "--vae-overlap", "32"], check=True)
        return
    engine = Engine(args.port)
    props = engine.ready()
    if args.cmd == "health":
        print(json.dumps(props, indent=2))
    elif args.cmd == "benchmark":
        benchmark(engine, props, args.output, args.repeat)
    else:
        result = render(engine, props, args.output, args.caption, args.lyrics, args.seconds, args.seed, args.model, args.language)
        print(args.output / result["version"] / "song.wav")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Operación interrumpida.")
    except (OSError, RuntimeError, ValueError, EOFError, KeyError, wave.Error, subprocess.SubprocessError) as error:
        sys.exit(f"NOEL-01 · {error}\nConsulte el diagnóstico y la consola de ace-server.")
