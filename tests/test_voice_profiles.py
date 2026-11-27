import array
import tempfile
import unittest
from pathlib import Path
from noel.voice_profiles import create_profile,profiles,reference,remove_profile,save_pcm
from noel.voice_engine import mix_stems

class VoiceTests(unittest.TestCase):
    def test_profile(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            wav=root/"sample.wav"
            save_pcm(wav,array.array("h",[1200,-1200]*44100*3))
            with self.assertRaises(ValueError):
                create_profile(root/"voices",wav,"Demo",False)
            p=create_profile(root/"voices",wav,"Demo",True)
            self.assertEqual(profiles(root/"voices")[0]["name"],"Demo")
            self.assertTrue(reference(root/"voices",p).is_file())
            remove_profile(root/"voices",p)
            self.assertEqual(profiles(root/"voices"),[])
            self.assertTrue(wav.is_file())
    def test_mix(self):
        a=array.array("h",[1000,-1000])
        b=array.array("h",[2000,-2000])
        self.assertEqual(list(mix_stems(a,b)),[3000,-3000])
        self.assertEqual(list(a),[1000,-1000])
