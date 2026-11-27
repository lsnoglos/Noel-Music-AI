import hashlib
import tempfile
import unittest
from pathlib import Path
from noel.models import catalog, model_path, required_music, device_warning, transfer_model
from noel.text_engine import kind, ASSETS


class ModelCenter(unittest.TestCase):
    def test_transfer(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source=root/"renamed.gguf"
            source.write_bytes(b"model")
            dest=root/"copy.gguf"
            sha=hashlib.sha256(b"model").hexdigest()
            transfer_model(source,dest,5,sha)
            self.assertEqual(dest.read_bytes(),b"model")
            self.assertEqual(source.read_bytes(),b"model")
            with self.assertRaises(ValueError):
                transfer_model(source,dest,5,"0"*64)
            self.assertEqual(dest.read_bytes(),b"model")
    def test_catalog_and_device(self):
        self.assertIn("turbo4",required_music("turbo4"))
        self.assertNotIn("dit",required_music("turbo4"))
        self.assertEqual(model_path(Path("models"),"qwen").parent.name,"text-models")
        self.assertEqual(kind("hybrid"),"gpu")
        self.assertIn("Solo CPU",device_warning("cpu","sft","qwen",{}))
        self.assertEqual(catalog()["qwen"][1],2497280448)
