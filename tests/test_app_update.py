import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from scripts.apply_update import apply


class UpdateTest(unittest.TestCase):
    def setup_fixture(self, root):
        target, source = root/"installed", root/"update"
        (target/"engine").mkdir(parents=True)
        (target/"engine/ace-server.exe").write_bytes(b"engine")
        (target/"engine-revision.txt").write_text("test")
        (target/"NoelMusicAI.cmd").write_bytes(b"old")
        (target/"runs").mkdir()
        (target/"runs/song.wav").write_bytes(b"private")
        (target/".runtime/models").mkdir(parents=True)
        (target/".runtime/models/music.gguf").write_bytes(b"weights")
        contents = {"noel/gui.py": b"new", "scripts/start.ps1": b"new", "NoelMusicAI.cmd": b"new", "requirements-ui.txt": b"new"}
        for name, data in contents.items():
            p = source/"app"/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        (source/"update-manifest.json").write_text(json.dumps({"engine": "test", "files": {k: hashlib.sha256(v).hexdigest() for k,v in contents.items()}}))
        return source, target

    def test_preserve_data(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = self.setup_fixture(Path(d))
            backup = apply(source, target)
            self.assertEqual((target/"noel/gui.py").read_bytes(), b"new")
            self.assertEqual((backup/"NoelMusicAI.cmd").read_bytes(), b"old")
            self.assertEqual((target/"engine/ace-server.exe").read_bytes(), b"engine")
            self.assertEqual((target/"runs/song.wav").read_bytes(), b"private")
            self.assertEqual((target/".runtime/models/music.gguf").read_bytes(), b"weights")

    def test_reject_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = self.setup_fixture(Path(d))
            (source/"app/noel/gui.py").write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "Hash"):
                apply(source, target)
            self.assertEqual((target/"NoelMusicAI.cmd").read_bytes(), b"old")
