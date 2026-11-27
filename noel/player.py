"""Windows MCI playback and a peak envelope from the saved stereo PCM16 WAV."""
import array
import ctypes
import math
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

    def seek(self, milliseconds):
        if self.opened:
            duration = int(self.send("status noelplayer length"))
            playing = self.send("status noelplayer mode") == "playing"
            self.send(f"seek noelplayer to {max(0, min(duration, milliseconds))}")
            if playing:
                self.send("play noelplayer")


def spectrum(path, milliseconds, bands=16):
    """Log-spaced Goertzel magnitudes from a PCM window at playback position."""
    with wave.open(str(path)) as f:
        rate = f.getframerate()
        if f.getsampwidth() != 2:
            return [0.0] * bands
        channels = f.getnchannels()
        start = min(f.getnframes(), max(0, milliseconds * rate // 1000))
        f.setpos(start)
        samples = array.array("h", f.readframes(2048))
    n = len(samples) // channels
    if n < 2:
        return [0.0] * bands
    mono = [sum(samples[i*channels:(i+1)*channels]) / (channels*32768) *
            (0.5 - 0.5*math.cos(2*math.pi*i/(n-1))) for i in range(n)]
    levels = []
    for b in range(bands):
        freq = 60 * (12000/60)**(b/max(1,bands-1))
        coefficient = 2*math.cos(2*math.pi*freq/rate)
        q1 = q2 = 0.0
        for x in mono:
            q0 = x + coefficient*q1 - q2
            q2, q1 = q1, q0
        magnitude = math.sqrt(max(0, q1*q1+q2*q2-coefficient*q1*q2))/n
        levels.append(max(0.0, min(1.0, (20*math.log10(max(magnitude, 1e-8))+65)/55)))
    return levels
