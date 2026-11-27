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

    def test_conversion_pipeline(self):
        import json
        import threading
        from unittest.mock import patch
        from noel.voice_engine import convert
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source=root/"song.wav"
            sample=array.array("h",[1000,-1000]*44100*2)
            save_pcm(source,sample,44100,2)
            original=source.read_bytes()
            profile=create_profile(root/"voices", self.make_sample(root), "Mi voz",True)
            ref=reference(root/"voices",profile)
            calls=[]
            def simulate(cli,args,cancel,log):
                task=args[args.index("--task")+1]
                calls.append(task)
                if task=="sep":
                    target=args[args.index("--out-dir")+1]
                    for name in ("vocals","drums","bass","other"):
                        save_pcm(target/(name+".wav"),sample,44100,2)
                else:
                    save_pcm(args[args.index("--out")+1],sample,44100,2)
            with patch("noel.voice_engine.binary",return_value=root/"dummy.exe"), patch("noel.voice_engine.model_ready",return_value=True),patch("noel.voice_engine.run_cli",side_effect=simulate):
                result=convert(root,root/"models",root/"runs",source,ref,profile,"cpu",threading.Event(),lambda _:None)
            self.assertEqual(calls,["sep","svc"])
            self.assertEqual(source.read_bytes(),original)
            path=root/"runs"/result["version"]
            self.assertTrue((path/"instrumental.wav").is_file())
            self.assertEqual(json.loads((path/"version.json").read_text("utf-8"))["editing"]["voice_profile_id"],profile["id"])
    def make_sample(self,root):
        wav=root/"ref.wav"
        save_pcm(wav,array.array("h",[1200,-1200]*44100*3))
        return wav

    def test_speech_adapter(self):
        import threading
        from unittest.mock import patch
        from noel.voice_engine import speak
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            p=create_profile(root/"voices",self.make_sample(root),"Mi voz",True,transcript="Texto real")
            ref=reference(root/"voices",p)
            calls=[]
            def simulate(cli,args,cancel,log):
                calls.extend(args)
                save_pcm(args[args.index("--out")+1],array.array("h",[1000]*24000),24000)
            with patch("noel.voice_engine.binary",return_value=root/"dummy.exe"),patch("noel.voice_engine.model_ready",return_value=True),patch("noel.voice_engine.run_cli",side_effect=simulate):
                result=speak(root,root/"models",ref,p,"cpu","Hola mundo","es",threading.Event())
            self.assertTrue(result.is_file())
            self.assertIn("Texto real",calls)
            self.assertIn("Hola mundo",calls)
            self.assertIn("qwen3_tts",calls)

    def test_history_and_commit(self):
        from noel.voice_profiles import save_phrase,phrase_history,commit_draft,clip_reference
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            sample=self.make_sample(root)
            draft=root/"draft"
            p=create_profile(draft,sample,"Borrador",True)
            folder=draft/p["id"]
            save_phrase(folder,sample,"Primera","es")
            save_phrase(folder,sample,"Segunda","en")
            self.assertEqual(len(phrase_history(folder)),2)
            saved=commit_draft(root/"voices",draft,p,"Mi voz")
            self.assertEqual(saved["name"],"Mi voz")
            self.assertEqual({x["text"] for x in phrase_history(root/"voices"/p["id"])},{"Primera","Segunda"})
            self.assertTrue((folder/"reference.wav").is_file())
            clip_reference(sample,root/"clip.wav",100)
            self.assertTrue((root/"clip.wav").is_file())
