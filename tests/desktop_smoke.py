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
        assert set(studio.panels) == {"Inicio", "Crear música", "Modelos", "Configuración"}
        assert studio.modern, "ttkbootstrap no se activó"
        assert "Niño" in studio.voice["values"]
        studio.instrumental.set(True)
        studio.toggle_instrumental()
        assert str(studio.voice["state"]) == "disabled"
        studio.instrumental.set(False)
        studio.toggle_instrumental()
        studio.lyric_dialog()
        # Startup inspection may still be active; verify the panel directly.
        studio.structure.set("Personalizada")
        studio.toggle_sections()
        assert len(studio.sections) == 6
        assert "Inglés" in studio.lyric_language["values"]
        assert studio.model_choice.current() == 0
        studio.show_page("Crear música")
        studio.duration.set(300)
        assert studio.duration.get() == 300
        studio.show_page("Inicio")
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
