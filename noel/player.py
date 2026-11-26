"""Windows MCI playback and a peak envelope from the saved stereo PCM16 WAV."""
import array
import ctypes
import wave


def envelope(path, bars=160):
    with wave.open(str(path)) as wav:
        stride = max(1, (wav.getnframes()+bars-1)//bars)
        peaks = []
        while data := wav.readframes(stride):
            samples = array.array("h", data)
            peaks.append(max(abs(min(samples)), abs(max(samples))) / 32768)
        return peaks


class Player:
    def __init__(self):
        self.opened = False

    def send(self, command):
        buffer = ctypes.create_unicode_buffer(256)
        code = ctypes.windll.winmm.mciSendStringW(command, buffer, len(buffer), None)
        if code:
            ctypes.windll.winmm.mciGetErrorStringW(code, buffer, len(buffer))
            raise OSError(buffer.value)
        return buffer.value

    def open(self, path):
        self.close()
        self.send(f'open "{path}" type mpegvideo alias noelplayer')
        self.opened = True
        self.send("set noelplayer time format milliseconds")
        self.send("play noelplayer")

    def close(self):
        if self.opened:
            self.send("close noelplayer")
            self.opened = False
