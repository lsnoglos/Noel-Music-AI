"""Open the real desktop with an empty private configuration on a Windows runner."""
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from noel.gui import Studio


def main():
    with tempfile.TemporaryDirectory() as tmp, patch("noel.gui.ROOT", Path(tmp)), patch("noel.gui.RUNTIME", Path(tmp)/".runtime"):
        window = tk.Tk()
        studio = Studio(window)
        def check():
            if studio.busy:
                window.after(100, check)
            else:
                studio.close()
        window.after(300, check)
        window.after(30000, window.quit)
        window.mainloop()
        if not studio.closing:
            raise TimeoutError("La ventana no respondió al diagnóstico.")


if __name__ == "__main__":
    main()
