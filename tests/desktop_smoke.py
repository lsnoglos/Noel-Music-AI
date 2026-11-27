"""Open and exercise the actual Windows desktop without model downloads."""
import json
import tempfile
import tkinter as tk
import wave
from pathlib import Path
from unittest.mock import patch

from noel.gui import Studio


def main():
    with tempfile.TemporaryDirectory() as tmp, patch("noel.gui.ROOT", Path(tmp)), patch("noel.gui.RUNTIME", Path(tmp)/".runtime"):
        run = Path(tmp)/"runs"/"example"
        run.mkdir(parents=True)
        (run/"version.json").write_text(json.dumps({"request":{"caption":"Demo","lyrics":"Hola"},"metrics":{"actual_seconds":1}}))
        with wave.open(str(run/"song.wav"), "wb") as f:
            f.setparams((2,2,48000,0,"NONE","not compressed"))
            f.writeframes(b"\x01\x02\x03\x04"*48000)
        window = tk.Tk()
        studio = Studio(window)
        assert set(studio.panels) == {"Inicio", "Crear música", "Editor musical", "Modelos", "Configuración"}
        assert studio.modern, "ttkbootstrap no se activó"
        assert "Niño" in studio.voice["values"]
        assert studio.model_choice.current() == 0
        assert studio.duration.get() == 60
        assert studio.instrument_mode.get()=="auto"
        failures = []
        def check():
            if studio.busy:
                window.after(100, check)
                return
            try:
                studio.show_page("Crear música")
                window.update_idletasks()
                assert studio.player_frame.winfo_ismapped()
                bottom = studio.player_frame.winfo_rooty()+studio.player_frame.winfo_height()
                limit = window.winfo_rooty()+window.winfo_height()
                assert bottom <= limit+1, f"reproductor recortado: footer={bottom}, window={limit}"
                studio.duration.set(300)
                assert studio.duration.get() == 300
                studio.instrumental.set(True)
                studio.toggle_instrumental()
                assert str(studio.voice["state"]) == "disabled"
                studio.instrumental.set(False)
                studio.toggle_instrumental()
                studio.lyric_dialog()
                window.update_idletasks()
                assert studio.composing and studio.composer.winfo_ismapped()
                assert studio.generate_button.winfo_ismapped()
                assert studio.instrument_panel.winfo_ismapped()
                assert studio.duration_label.winfo_ismapped()
                studio.structure.set("Personalizada")
                studio.toggle_sections()
                assert len(studio.sections) == 6
                assert "Inglés" in studio.lyric_language["values"]
                studio.hide_composer()
                studio.toggle_instruments()
                assert studio.instrument_panel.winfo_manager() == "pack"
                studio.instrument_vars["Piano"].set(True)
                assert "piano" in studio.musical_caption()
                studio.instrument_mode.set("auto")
                studio.update_instrument_mode()
                assert "featured instruments:" not in studio.musical_caption()
                studio.piano.start()
                assert studio.piano.timer is not None
                studio.piano.stop()
                assert studio.piano.timer is None
                studio.show_page("Inicio")
                window.update_idletasks()
                assert len(studio.song_data) == 1 and studio.home_cards.winfo_children()
                assert all("No descargado" in x.cget("text") for x in studio.model_states.values())
                assert "qwen" in studio.model_states and "turbo4" in studio.model_states
                assert "CPU + GPU" in studio.device_setting["values"]
                studio.lyrics.delete("1.0","end")
                studio.lyrics.insert("1.0","Hola mundo")
                studio.copy_lyrics()
                assert window.clipboard_get()=="Hola mundo"
                studio.show_page("Editor musical")
                studio.set_edit_source(run/"song.wav","Hola","Demo")
                assert studio.edit_source == run/"song.wav"
                studio.edit_mode.current(1)
                studio.update_editor()
                assert studio.repaint_box.winfo_manager()=="pack"
            except Exception as exc:
                failures.append(exc)
            finally:
                studio.close()
        window.geometry("900x650")
        window.after(700, check)
        window.after(30000, window.quit)
        window.mainloop()
        if failures:
            raise failures[0]
        if not studio.closing:
            raise TimeoutError("La ventana no respondió al diagnóstico.")


if __name__ == "__main__":
    main()
