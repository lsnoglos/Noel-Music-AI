import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock
from noel.presets import caption, lyric_prompt
from noel.studio import render
from noel.audio_export import export_audio


class Creative(unittest.TestCase):
    def test_language_structure_instruments(self):
        text = lyric_prompt("mar", "bachata", "Personalizada", "Poética", "", "Francés",
                            "Protesta", ["Intro","Verso 1","Coro","Coro","Omitir","Outro"])
        self.assertIn("French", text)
        self.assertIn("[Intro], [Verse 1], [Chorus], [Chorus], [Outro]", text)
        self.assertIn("social protest", text)
        self.assertIn("piano, violin", caption("pop", "Natural", "Libre", "Tenor", "", ["Piano","Violín"]))

    def test_vocal_language_reaches_render(self):
        engine = Mock()
        engine.generate.return_value = (b"wav", b"latent", 15)
        with tempfile.TemporaryDirectory() as d:
            render(engine, {}, Path(d), "pop", "hello", 15, 42, "dit", "en")
        self.assertEqual(engine.generate.call_args.args[0]["vocal_language"], "en")

    def test_export(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            wav = root/"song.wav"
            with wave.open(str(wav), "wb") as f:
                f.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
                f.writeframes(b"\x01\x02\x03\x04"*48000)
            export_audio(wav, root/"copy.wav")
            self.assertEqual(wav.read_bytes(), (root/"copy.wav").read_bytes())
            try:
                import lameenc
            except ImportError:
                self.skipTest("optional encoder not installed")
            export_audio(wav, root/"copy.mp3", "mp3")
            self.assertGreater((root/"copy.mp3").stat().st_size, 1000)
