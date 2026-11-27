import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from noel.engine import Engine, MAX_BODY
from noel.models import MODELS, OPTIONAL, catalog
from noel.presets import caption, lyric_prompt
from noel.studio import render


class StudioUpgrade(unittest.TestCase):
    def test_voice_and_style(self):
        self.assertIn("solo female lead singer", caption("bachata", "Romántica", "Verano", "Femenina", "guitar"))
        self.assertIn("male and female vocal duet", caption("pop", "Natural", "Libre", "Dúo", ""))
        self.assertIn("no singing", caption("pop", "Natural", "Libre", "Instrumental", ""))

    def test_lyrics_contract(self):
        engine = Engine()
        engine.job = Mock(return_value=("application/json", b'[{"lyrics":"[Verse] Hola"}]'))
        self.assertEqual(engine.compose({"lm_mode": "inspire"}), "[Verse] Hola")
        engine.job.assert_called_once_with("/lm", {"lm_mode": "inspire"}, 300)
        self.assertIn("Spanish", lyric_prompt("mar", "bachata", "Comercial", "Poetic", ""))

    def test_long_render_and_alternative(self):
        engine = Mock()
        engine.generate.return_value = (b"wav-fixture", b"latent-fixture", 300)
        props = {"models": {"dit": [OPTIONAL["sft"][0]]}}
        with tempfile.TemporaryDirectory() as d:
            result = render(engine, props, Path(d), "ballad", "letra", 300, 7, "sft")
        self.assertEqual(result["steps"], 50)
        self.assertEqual(engine.generate.call_args.args[0]["duration"], 300)
        self.assertGreater(MAX_BODY, 300 * (48000*4 + 25*256))
        self.assertEqual(set(MODELS), {"embedding", "dit", "vae"})
        self.assertIn("lm", catalog())

    def test_turbo_unchanged(self):
        engine = Mock()
        engine.generate.return_value = (b"wav", b"latent", 15)
        with tempfile.TemporaryDirectory() as d:
            render(engine, {}, Path(d), "test", "", 15, 42)
        payload = engine.generate.call_args.args[0]
        self.assertEqual(payload["inference_steps"], 8)
        self.assertEqual(payload["synth_model"], MODELS["dit"][0])
        self.assertEqual(payload["lyrics"], "[Instrumental]")
