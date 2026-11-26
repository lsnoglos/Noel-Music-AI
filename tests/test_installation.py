"""Offline fixtures for per-model recovery and transactional engine installation."""
import hashlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from noel.distribution import binary_path, install_engine
from noel.engine import ENGINE
from noel.models import install


class Components(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = b"fixture"
        digest = hashlib.sha256(self.payload).hexdigest()
        patcher = patch.dict("noel.models.MODELS", {"dit": ("music.gguf", 7, digest)}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_completed_partial_repairs_only_selected_model_offline(self):
        target = self.root/"music.gguf"
        target.write_bytes(b"damaged")
        (self.root/"music.gguf.part").write_bytes(self.payload)
        with patch("noel.models.subprocess.run", side_effect=AssertionError("network")):
            install(self.root, True, ["dit"], repair=True)
            install(self.root, True, ["dit"])
        self.assertEqual(target.read_bytes(), self.payload)

    def test_corrupt_partial_preserves_previous_model(self):
        target = self.root/"music.gguf"
        target.write_bytes(b"previous")
        (self.root/"music.gguf.part").write_bytes(b"invalid")
        with self.assertRaisesRegex(ValueError, "Integridad"):
            install(self.root, True, ["dit"], repair=True)
        self.assertEqual(target.read_bytes(), b"previous")

    def test_insufficient_disk_keeps_partial(self):
        partial = self.root/"music.gguf.part"
        partial.write_bytes(b"fix")
        with patch("noel.models.shutil.disk_usage") as disk:
            disk.return_value.free = 2
            with self.assertRaisesRegex(ValueError, "Espacio"):
                install(self.root, True)
        self.assertEqual(partial.read_bytes(), b"fix")

    def package(self, revision):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr("engine/ace-server.exe", self.payload)
            z.writestr("engine-revision.txt", revision)
            z.writestr("../escape", b"fixture")
            z.writestr("engine-manifest.json", json.dumps([dict(name="ace-server.exe", bytes=7,
                       sha256=hashlib.sha256(self.payload).hexdigest())]))
        return stream.getvalue()

    def deploy(self, package, cancel=False):
        event = threading.Event()
        if cancel:
            event.set()
        asset = dict(size=len(package), digest="sha256:"+hashlib.sha256(package).hexdigest(),
                     browser_download_url="https://example.invalid/fixture")
        with patch("noel.distribution.urllib.request.urlopen", return_value=io.BytesIO(package)):
            install_engine(self.root, asset, event, lambda *_: None)

    def test_engine_repair_switches_only_after_validation(self):
        self.deploy(self.package(ENGINE))
        active = binary_path(self.root)
        self.assertEqual(active.read_bytes(), self.payload)
        with self.assertRaisesRegex(ValueError, "revisión"):
            self.deploy(self.package("wrong"))
        self.assertEqual(binary_path(self.root), active)
        self.assertFalse(list(self.root.rglob("escape")))

    def test_cancel_preserves_installed_engine(self):
        self.deploy(self.package(ENGINE))
        active = binary_path(self.root)
        with self.assertRaises(InterruptedError):
            self.deploy(self.package(ENGINE), cancel=True)
        self.assertEqual(binary_path(self.root), active)
