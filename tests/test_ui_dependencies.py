import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from noel.ui_theme import install_private

class PrivateDependencyTests(unittest.TestCase):
    def test_existing_cache_requires_successful_probe(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"requirements-ui.txt").write_text("miniaudio==1.73\n")
            (root/"ui-wheels").mkdir()
            calls=[]
            def pip(args,**kwargs):
                calls.append(args)
                return Mock(returncode=0,stdout="",stderr="")
            with patch("noel.ui_theme.subprocess.run",side_effect=pip):
                target=install_private(root,root/"runtime")
                self.assertTrue(target.is_dir())
                self.assertIn("--ignore-installed",calls[0])
                self.assertIn("--no-index",calls[0])
                self.assertIn("-I",calls[1])
                self.assertEqual(install_private(root,root/"runtime"),target)
                self.assertEqual(len(calls),3)
    def test_failed_install_reports_log(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"requirements-ui.txt").write_text("miniaudio==1.73\n")
            (root/"ui-wheels").mkdir()
            with patch("noel.ui_theme.subprocess.run",return_value=Mock(returncode=1,stdout="",stderr="test pip failure")):
                with self.assertRaisesRegex(RuntimeError,"ui-dependencies.log"):
                    install_private(root,root/"runtime")
            self.assertIn("test pip failure",(root/"runtime/ui-dependencies.log").read_text())
