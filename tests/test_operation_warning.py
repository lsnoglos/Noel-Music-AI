import unittest
from noel.hardware import operation_warning

class WarningTests(unittest.TestCase):
    def test_cpu_operations_independent(self):
        info={"gpu":None,"ram_available":9*2**30}
        self.assertEqual(operation_warning(info,"cpu","lyrics","qwen17"),"")
        self.assertIn("Turbo Q4",operation_warning(info,"cpu","music","turbo4"))
        self.assertNotIn("Qwen",operation_warning(info,"cpu","music","turbo4"))
    def test_gpu(self):
        self.assertEqual(operation_warning({"gpu":{"free_mib":8000},"ram_available":9*2**30},"gpu","music","dit"),"")
    def test_missing_gpu(self):
        self.assertIn("CPU",operation_warning({"gpu":None},"gpu","lyrics","qwen"))
