import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock

from noel.editor import edit_song, exact_outside
from noel.engine import multipart_request
from noel.models import MODELS


def wav(value, seconds=2):
    out=io.BytesIO()
    with wave.open(out,"wb") as f:
        f.setparams((2,2,48000,0,"NONE","not compressed"))
        f.writeframes(value*48000*seconds)
    return out.getvalue()


class EditorTests(unittest.TestCase):
    def test_multipart(self):
        boundary,body=multipart_request({"task_type":"cover-nofsq"},{"audio":b"source","ref_audio":b"ref"})
        self.assertIn(b'name="request"',body)
        self.assertIn(b'name="audio"',body)
        self.assertIn(b'name="ref_audio"',body)
        self.assertTrue(body.endswith(("--"+boundary+"--\r\n").encode()))

    def test_cover_preserves_original_and_saves_new_version(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src=root/"source.wav"
            src.write_bytes(wav(b"\x01\x02\x03\x04"))
            original=src.read_bytes()
            engine=Mock()
            engine.edit.return_value=(wav(b"\x04\x03\x02\x01"),b"latent",2)
            props={"models":{"dit":[MODELS["dit"][0]]}}
            result=edit_song(engine,props,root/"runs",src,"cover","pop","Hola","es","dit",42,consent=True)
            payload,parts=engine.edit.call_args.args
            self.assertEqual(payload["task_type"],"cover-nofsq")
            self.assertEqual(parts["audio"],original)
            self.assertEqual(parts["ref_audio"],original)
            self.assertEqual(src.read_bytes(),original)
            self.assertTrue((root/"runs"/result["version"]/"song.wav").exists())

    def test_repaint_exact_pcm(self):
        original=wav(b"\x01\x02\x03\x04")
        changed=wav(b"\x04\x03\x02\x01")
        result=exact_outside(original,changed,.5,1.5)
        with wave.open(io.BytesIO(result)) as f:
            pcm=f.readframes(f.getnframes())
        self.assertEqual(pcm[:24000*4],b"\x01\x02\x03\x04"*24000)
        self.assertEqual(pcm[24000*4:72000*4],b"\x04\x03\x02\x01"*48000)
        self.assertEqual(pcm[72000*4:],b"\x01\x02\x03\x04"*24000)

    def test_no_consent(self):
        with self.assertRaisesRegex(ValueError,"autorización"):
            edit_song(Mock(),{},Path("."),Path("missing"),"voice","pop","Hola","es","dit",42)
