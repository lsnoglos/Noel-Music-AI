"""Local system-wide measurements. Missing counters stay null."""
import ctypes
import os
import platform
import shutil
import subprocess
import threading
from pathlib import Path


def ram():
    if platform.system() == "Windows":
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
                (name, ctypes.c_uint64) for name in
                ("total", "free", "page", "free_page", "virtual", "free_virtual", "extended")]
        info = Memory()
        info.length = ctypes.sizeof(info)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):
            return info.total, info.free
    elif Path("/proc/meminfo").exists():
        fields = dict(line.split(":") for line in Path("/proc/meminfo").read_text().splitlines())
        return tuple(int(fields[key].split()[0]) * 1024 for key in ("MemTotal", "MemAvailable"))
    return None, None


def snapshot():
    gpu = None
    error = None
    try:
        result = subprocess.run(["nvidia-smi", "-i", "0",
                                 "--query-gpu=name,driver_version,memory.total,memory.free,memory.used",
                                 "--format=csv,noheader,nounits"], capture_output=True,
                                text=True, check=True, timeout=5)
        name, driver, total, free, used = result.stdout.strip().split(", ")
        gpu = dict(name=name, driver=driver, total_mib=int(total), free_mib=int(free), used_mib=int(used))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        error = str(exc)
    total, free = ram()
    return dict(os=platform.system(), architecture=platform.machine(), cpu=platform.processor(), cpu_threads=os.cpu_count(), gpu=gpu, gpu_error=error,
                ram_total=total, ram_available=free, disk_free=shutil.disk_usage(".").free)


class PeakMonitor:
    def __init__(self):
        self.stop = threading.Event()
        self.peak_gpu_mib = self.peak_ram_bytes = None
        self.worker = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        while True:
            data = snapshot()
            if data["gpu"]:
                self.peak_gpu_mib = max(self.peak_gpu_mib or 0, data["gpu"]["used_mib"])
            if data["ram_available"] is not None:
                self.peak_ram_bytes = max(self.peak_ram_bytes or 0, data["ram_total"] - data["ram_available"])
            if self.stop.wait(1):
                return

    def __enter__(self):
        self.worker.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.worker.join()
