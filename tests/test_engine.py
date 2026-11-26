"""Synthetic transport fixtures; no model inference."""
import io
import json
import tempfile
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from noel.engine import ENGINE, Engine, unpack
from noel.models import MODELS, matches
from noel.studio import render


def multipart():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setparams((2, 2, 48000, 0, "NONE", ""))
        f.writeframes(b"\x01\x00" * 96000)
    mark = b"--ace-batch-boundary"
    return (mark + b"\r\nContent-Type: audio/wav\r\n\r\n" + buf.getvalue() + b"\r\n" + mark
            + b'\r\nContent-Type: application/octet-stream\r\nContent-Disposition: form-data; name="latent"\r\n\r\n'
            + bytes(25 * 256) + b"\r\n" + mark + b"--\r\n")


MIME = "multipart/mixed; boundary=ace-batch-boundary"
JOB = "1234567890abcdef"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, data, mime="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode() if mime == "application/json" else data)

    def do_GET(self):
        if self.path == "/health":
            self.send({"status": "ok"})
        elif self.path == "/props":
            self.send({"version": ENGINE[:7], "models": {k: [v[0]] for k, v in MODELS.items()}})
        elif self.path == f"/job?id={JOB}&result=1":
            self.send(multipart(), MIME)
        elif self.path == f"/job?id={JOB}":
            self.send({"status": self.server.status})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/synth":
            self.server.payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send({"id": JOB})
        elif self.path == f"/job?id={JOB}&cancel=1":
            self.server.cancelled = True
            self.send({"status": "cancelled"})
        else:
            self.send_error(404)


class Contract(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.status = "done"
        Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.engine = Engine(self.server.server_port)

    def test_complete_version(self):
        with tempfile.TemporaryDirectory() as d:
            props = self.engine.ready()
            result = render(self.engine, props, Path(d), "guitarra", "", 1, 42)
            version = Path(d) / result["version"]
            manifest = json.loads((version / "version.json").read_text())
            self.assertEqual(manifest["request"], self.server.payload)
            self.assertTrue(matches(version / "song.vae", 6400, manifest["latent_sha256"]))
            self.assertEqual(result["actual_seconds"], 1)

    def test_failed_job_preserves_existing_versions(self):
        self.server.status = "failed"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                render(self.engine, {}, Path(d), "guitarra", "", 1, 42)
            self.assertFalse(list(Path(d).iterdir()))

    def test_timeout_cancels(self):
        with self.assertRaises(TimeoutError):
            self.engine.generate({"duration": 1}, timeout=0)
        self.assertTrue(self.server.cancelled)

    def test_keyboard_cancels(self):
        self.server.status = "running"
        with patch("noel.engine.time.sleep", side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            self.engine.generate({"duration": 1})
        self.assertTrue(self.server.cancelled)


class Audio(unittest.TestCase):
    def test_missing_latent(self):
        with self.assertRaises(ValueError):
            unpack(MIME, multipart().replace(bytes(6400) + b"\r\n--", b"\r\n--"), 1)

    def test_wrong_duration(self):
        with self.assertRaises(ValueError):
            unpack(MIME, multipart(), 15)

    def test_truncated(self):
        with self.assertRaises(ValueError):
            unpack(MIME, multipart()[:-20], 1)

    def test_silence(self):
        with self.assertRaises(ValueError):
            unpack(MIME, multipart().replace(b"\x01\x00" * 96000, bytes(192000)), 1)
