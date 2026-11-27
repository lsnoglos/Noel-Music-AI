"""Load a modern theme from an isolated offline wheelhouse; keep Tk fallback."""
import subprocess
import sys
from tkinter import ttk


def create_style(window, root, runtime):
    target = runtime / ("ui-" + str(sys.version_info.major) + "." + str(sys.version_info.minor))
    sys.path.insert(0, str(target))
    try:
        import ttkbootstrap
    except ImportError:
        wheels = root / "ui-wheels"
        if wheels.is_dir():
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--no-index",
                                "--find-links", str(wheels), "--target", str(target),
                                "-r", str(root / "requirements-ui.txt")],
                               check=True, timeout=120, capture_output=True)
                import importlib
                importlib.invalidate_caches()
                import ttkbootstrap
            except (ImportError, OSError, subprocess.SubprocessError):
                return ttk.Style(window), False
        else:
            return ttk.Style(window), False
    try:
        return ttkbootstrap.Style(theme="darkly"), True
    except Exception:
        return ttk.Style(window), False
