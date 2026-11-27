import unittest
from pathlib import Path
from noel.hardware import recommend
from noel.models import catalog, model_path, TEXT_BASES

class HardwareTests(unittest.TestCase):
    def test_cpu(self):
        r=recommend({"gpu":None,"ram_total":8*2**30,"ram_available":5*2**30,"cpu_threads":4})
        self.assertEqual((r["device"],r["music"],r["lyrics"]),("cpu","turbo4","qwen06"))
    def test_cpu_mid(self):
        r=recommend({"gpu":None,"ram_total":16*2**30,"ram_available":8*2**30,"cpu_threads":8})
        self.assertEqual(r["lyrics"],"qwen17")
    def test_gpu(self):
        r=recommend({"gpu":{"total_mib":8192,"free_mib":7900}})
        self.assertEqual((r["device"],r["music"],r["lyrics"]),("gpu","dit","qwen"))
        r=recommend({"gpu":{"total_mib":6144,"free_mib":4000}})
        self.assertEqual(r["music"],"turbo4")
    def test_catalog(self):
        for key,size in (("qwen06",484219808),("qwen17",1282439328)):
            self.assertIn(key,TEXT_BASES)
            self.assertEqual(catalog()[key][1],size)
            self.assertEqual(model_path(Path("models"),key).parent.name,"text-models")
