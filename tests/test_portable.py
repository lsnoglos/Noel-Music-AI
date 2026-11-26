import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from noel.runtime import verify_engine
from noel.distribution import binary_path


class Portable(unittest.TestCase):
    def test_dll_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root / "engine"
            folder.mkdir()
            entries = []
            for name in ["ace-server.exe", "test.dll"]:
                (folder/name).write_bytes(b"fixture")
                entries.append(dict(name=name, bytes=7, sha256=hashlib.sha256(b"fixture").hexdigest()))
            (root/"engine-manifest.json").write_text(json.dumps(entries))
            verify_engine(binary_path(root))
            (folder/"test.dll").unlink()
            with self.assertRaises(ValueError):
                verify_engine(binary_path(root))

    def test_reject_external_pointer(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/".runtime").mkdir()
            (root/".runtime/current-engine").write_text("../elsewhere")
            with self.assertRaises(ValueError):
                binary_path(root)
