"""Windows DirectShow capture through ffmpeg.exe; frames flow over its binary stdout into WSL."""
from collections import deque
import shutil
import subprocess
import threading
from pathlib import Path
from .capture import Frame, LatestFrame, Projector, clock_ms

def resolve_ffmpeg(path):
    resolved = shutil.which(path)
    if resolved:
        return resolved
    candidate = Path(path).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    raise FileNotFoundError(f"Windows FFmpeg not found: {path}; set camera.windows_ffmpeg to /mnt/c/.../ffmpeg.exe or run scripts/fetch_windows_ffmpeg.py")

def capture_command(config):
    # argv list, never a shell string: device names are not executable shell code.
    return [resolve_ffmpeg(config.windows_ffmpeg), "-hide_banner", "-loglevel", "warning",
            "-f", "dshow", "-rtbufsize", "16M",
            "-video_size", f"{config.width}x{config.height}", "-framerate", str(config.fps),
            "-i", f"video={config.windows_device}", "-an", "-sn", "-dn",
            "-vf", f"scale={config.width}:{config.height}", "-pix_fmt", "bgr24",
            "-f", "rawvideo", "pipe:1"]

def read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            if data:
                raise EOFError(f"truncated raw video frame: {len(data)}/{size} bytes")
            return None
        data.extend(chunk)
    return bytes(data)

def list_windows_devices(config):
    result = subprocess.run([resolve_ffmpeg(config.windows_ffmpeg), "-hide_banner", "-list_devices", "true",
                             "-f", "dshow", "-i", "dummy"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=15)
    # FFmpeg deliberately exits nonzero after enumerating DirectShow devices.
    return result.stderr.decode("utf-8", errors="replace")

class WindowsFFmpegCapture:
    def __init__(self, config, get_generation):
        self.config, self.get_generation = config, get_generation
        self.frames = LatestFrame()
        self.stop_event = threading.Event()
        self.finished = threading.Event()
        self.error = ""
        self.actual = {"width": config.width, "height": config.height, "fps": config.fps,
                       "backend": "Windows DirectShow / FFmpeg stdout -> WSL"}
        self._process = None
        self._thread = None
        self._stderr_thread = None
        self._stderr = deque(maxlen=16)
        self._stderr_lock = threading.Lock()
        self.last_frame_at = 0

    def start(self):
        self._process = subprocess.Popen(capture_command(self.config), stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self._stderr_thread = threading.Thread(target=self._read_stderr, name="ffmpeg-stderr", daemon=True)
        self._thread = threading.Thread(target=self._loop, name="windows-camera", daemon=True)
        self._stderr_thread.start()
        self._thread.start()

    def _read_stderr(self):
        for line in iter(self._process.stderr.readline, b""):
            with self._stderr_lock:
                self._stderr.append(line.decode("utf-8", errors="replace").strip())

    def diagnostics(self):
        with self._stderr_lock:
            return " | ".join(self._stderr)

    def _loop(self):
        import numpy as np
        projector = Projector(self.config)
        size = self.config.width * self.config.height * 3
        previous = -1
        try:
            while not self.stop_event.is_set():
                token = self.get_generation()
                generation, epoch = token if isinstance(token, tuple) else (token, 0)
                data = read_exact(self._process.stdout, size)
                if data is None:
                    if not self.stop_event.is_set():
                        self.error = "Windows FFmpeg ended: " + self.diagnostics()
                    break
                now = max(clock_ms(), previous + 1)
                previous = self.last_frame_at = now
                image = np.frombuffer(data, dtype=np.uint8).reshape(self.config.height, self.config.width, 3)
                self.frames.put(Frame(generation, now, projector.apply(image), epoch))
        except Exception as exc:
            if not self.stop_event.is_set():
                self.error = str(exc) + " " + self.diagnostics()
        finally:
            self.finished.set()

    def close(self):
        self.stop_event.set()
        self.frames.close()
        process = self._process
        if process:
            if process.poll() is None:
                try:
                    process.stdin.write(b"q\n")
                    process.stdin.flush()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
            for thread in (self._thread, self._stderr_thread):
                if thread:
                    thread.join(timeout=1)
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe:
                    pipe.close()
