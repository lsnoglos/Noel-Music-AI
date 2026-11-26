"""Run against the real ace-server executable with metadata-only GGUF fixtures."""
import json
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from noel.engine import Engine
from noel.models import MODELS


def string(value):
    return struct.pack("<Q", len(value)) + value.encode()


def check(binary):
    with tempfile.TemporaryDirectory() as d:
        for bucket, arch in [("dit", "dit"), ("embedding", "text-enc"), ("vae", "vae")]:
            header = b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + string("general.architecture")
            header += struct.pack("<I", 8) + string("acestep-" + arch)
            (Path(d) / MODELS[bucket][0]).write_bytes(header + bytes(-len(header) % 32))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        proc = subprocess.Popen([binary, "--models", d, "--device", "CPU", "--port", str(port)])
        try:
            client = Engine(port)
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError(f"ace-server cerró durante el inicio: 0x{proc.returncode & 0xffffffff:08X}")
                try:
                    props = client.ready()
                    break
                except ConnectionError:
                    time.sleep(.1)
            else:
                raise TimeoutError("ace-server no respondió")
            case = unittest.TestCase()
            case.assertEqual(props["models"]["lm"], [])
            with case.assertRaisesRegex(RuntimeError, "400"):
                client.metadata("POST", "/synth", b"{}")
            # Unknown model fails upstream before any tensors are accessed.
            with case.assertRaisesRegex(RuntimeError, "failed"):
                client.generate({"caption": "test", "duration": 1, "synth_model": "missing"})
            print(json.dumps({"real_server": props["version"], "health": "ok", "invalid_request": 400,
                              "async_failure": "verified", "inference": False}))
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    check(sys.argv[1])
