"""Windows DirectShow capture through ffmpeg.exe; frames flow over its binary stdout into WSL."""
from collections import deque
import re
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

def pipe_dimensions(config):
    # Keep the sphere intact for WSL projection; ordinary views can shrink before IPC.
    if config.projection == "equirectangular":
        return config.width, config.height
    scale = min(config.output_width / config.width, config.output_height / config.height, 1.0)
    return round(config.width * scale), round(config.height * scale)

def capture_command(config):
    # argv list, never a shell string: device names are not executable shell code.
    width, height = pipe_dimensions(config)
    command = [resolve_ffmpeg(config.windows_ffmpeg), "-hide_banner", "-loglevel", "warning",
            "-f", "dshow", "-rtbufsize", "16M",
            "-video_size", f"{config.width}x{config.height}", "-framerate", str(config.fps)]
    if config.windows_video_codec:
        command += ["-vcodec", config.windows_video_codec]
    return command + ["-i", f"video={config.windows_device}", "-an", "-sn", "-dn",
            "-vf", f"scale={width}:{height}", "-pix_fmt", "bgr24",
            "-fps_mode", "passthrough", "-flush_packets", "1", "-f", "rawvideo", "pipe:1"]

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

def failure_hint(details):
    if "WSL" in details or "Exec format error" in details:
        return "Check WSL Windows interop and execution permissions (cmd.exe /c ver)."
    return ("Check X5 Webcam mode, USB connection, and close other Windows camera apps. "
            "Run 'devices --modes' with the same --config; width/height/fps/windows_video_codec "
            "must match a listed input mode. Device enumeration alone does not verify capture.")

def windows_device_names(listing):
    names = set()
    video = False
    for line in listing.splitlines():
        match = re.search(r'"([^"]+)" \((video|audio|none)\)', line)
        if match:
            video = match[2] == "video"
            if video:
                names.add(match[1])
        elif video:
            alias = re.search(r'Alternative name "([^"]+)"', line)
            if alias:
                names.add(alias[1])
    return names

def _enumerate(config, options, marker):
    command = [resolve_ffmpeg(config.windows_ffmpeg), "-hide_banner"] + options
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=15)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Windows FFmpeg enumeration timed out. " + failure_hint("")) from exc
    details = result.stderr.decode("utf-8", errors="replace")
    # Listing may exit either zero or nonzero. Require real results, not an exit code.
    if not marker(details):
        raise RuntimeError(f"Windows FFmpeg enumeration failed (exit {result.returncode}): "
                           f"{details.strip()}\n{failure_hint(details)}")
    return details

def list_windows_devices(config):
    return _enumerate(config, ["-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                      windows_device_names)

def list_windows_options(config):
    return _enumerate(config, ["-list_options", "true", "-f", "dshow", "-i", f"video={config.windows_device}"],
                      lambda text: re.search(r"(?:vcodec|pixel_format)=\S+\s+min s=\d+x\d+", text))

class WindowsFFmpegCapture:
    def __init__(self, config, get_generation):
        self.config, self.get_generation = config, get_generation
        self.frames = LatestFrame()
        self.stop_event = threading.Event()
        self.finished = threading.Event()
        self._ready = threading.Event()
        self.error = ""
        width, height = pipe_dimensions(config)
        self.actual = {"width": width, "height": height,
                       "requested_input": {"device": config.windows_device, "width": config.width,
                                           "height": config.height, "fps": config.fps,
                                           "codec": config.windows_video_codec or "driver default"},
                       "backend": "Windows DirectShow / FFmpeg stdout -> WSL"}
        self._process = None
        self._thread = None
        self._stderr_thread = None
        self._stderr = deque(maxlen=16)
        self._stderr_lock = threading.Lock()
        self.last_frame_at = 0

    def start(self, timeout=10):
        if self._process is not None or self.stop_event.is_set():
            raise RuntimeError("capture already started or closed; create a new capture to reconnect")
        try:
            self._process = subprocess.Popen(capture_command(self.config), stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            self._stderr_thread = threading.Thread(target=self._read_stderr, name="ffmpeg-stderr", daemon=True)
            self._thread = threading.Thread(target=self._loop, name="windows-camera", daemon=True)
            self._stderr_thread.start()
            self._thread.start()
            if not self._ready.wait(timeout):
                details = self.diagnostics()
                raise RuntimeError(f"No complete X5 frame within {timeout:g}s: {details}\n{failure_hint(details)}")
            if self.error:
                raise RuntimeError(self.error)
        except Exception:
            self.close()
            raise

    def _read_stderr(self):
        for line in iter(self._process.stderr.readline, b""):
            with self._stderr_lock:
                self._stderr.append(line.decode("utf-8", errors="replace").strip())

    def diagnostics(self):
        with self._stderr_lock:
            return " | ".join(self._stderr)

    def _loop(self):
        try:
            import numpy as np
            projector = Projector(self.config)
            width, height = pipe_dimensions(self.config)
            size = width * height * 3
            previous = -1
            while not self.stop_event.is_set():
                token = self.get_generation()
                generation, epoch = token if isinstance(token, tuple) else (token, 0)
                data = read_exact(self._process.stdout, size)
                if data is None:
                    if not self.stop_event.is_set():
                        raise EOFError("Windows FFmpeg ended before the next complete frame")
                    break
                now = max(clock_ms(), previous + 1)
                previous = now
                image = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)
                self.frames.put(Frame(generation, now, projector.apply(image), epoch))
                self.last_frame_at = now
                self._ready.set()
        except Exception as exc:
            if not self.stop_event.is_set():
                if self._stderr_thread:
                    self._stderr_thread.join(timeout=0.5)
                details = self.diagnostics()
                self.error = f"{exc}: {details}\n{failure_hint(details)}"
        finally:
            self.finished.set()
            self._ready.set()

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
