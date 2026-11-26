"""Exercise report persistence and model installer with small local fixtures."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noel.models import install
from noel.studio import benchmark


class Benchmark(unittest.TestCase):
    def test_partial_report_after_failure(self):
        with tempfile.TemporaryDirectory() as d, patch("noel.studio.render") as render:
            render.side_effect = [{"actual_seconds": 15}, RuntimeError("simulated failure")]
            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                benchmark(None, {}, Path(d), 1)
            folder, = Path(d).iterdir()
            rows = json.loads((folder / "benchmark.json").read_text())
            self.assertEqual([(r["seconds"], r["status"]) for r in rows], [(15, "ok"), (30, "error")])
            with (folder / "benchmark.csv").open(newline="") as stream:
                self.assertEqual(list(csv.DictReader(stream))[1]["error"], "simulated failure")

    def test_required_durations_and_repetitions(self):
        with tempfile.TemporaryDirectory() as d, patch("noel.studio.render", return_value={}):
            benchmark(None, {}, Path(d), 2)
            report, = Path(d).glob("*/benchmark.json")
            self.assertEqual([row["seconds"] for row in json.loads(report.read_text())], [15, 30, 60, 120]*2)


class Installer(unittest.TestCase):
    def test_no_download_without_approval(self):
        with tempfile.TemporaryDirectory() as d, patch("noel.models.subprocess.run") as curl:
            dest = Path(d) / "models"
            install(dest, False)
            self.assertFalse(dest.exists())
            curl.assert_not_called()

    def test_hash_verification_keeps_existing_file(self):
        digest = hashlib.sha256(b"good").hexdigest()
        with tempfile.TemporaryDirectory() as d, patch.dict("noel.models.MODELS", {"dit": ("test.gguf", 4, digest)}, clear=True):
            dest = Path(d) / "test.gguf"
            dest.write_bytes(b"oops")
            with self.assertRaises(ValueError):
                install(Path(d), True)
            self.assertEqual(dest.read_bytes(), b"oops")
            self.assertFalse((Path(d) / ".installing").exists())
            dest.write_bytes(b"good")
            with patch("noel.models.subprocess.run") as curl:
                install(Path(d), True)
                curl.assert_not_called()
