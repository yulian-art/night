"""One camera owner and a one-slot buffer. Never build up a video backlog."""
from dataclasses import dataclass
import math
import platform
import threading
import time

def clock_ms():
    return time.monotonic_ns() // 1_000_000

@dataclass(frozen=True)
class Frame:
    generation: int
    timestamp_ms: int
    image: object
    reset_epoch: int = 0

class LatestFrame:
    def __init__(self):
        self._condition = threading.Condition()
        self._frame = None
        self._closed = False
        self.overwritten = 0

    def put(self, frame):
        with self._condition:
            if self._closed:
                return
            if self._frame is not None:
                self.overwritten += 1
            self._frame = frame
            self._condition.notify()

    def take(self, timeout=0.05):
        with self._condition:
            self._condition.wait_for(lambda: self._frame is not None or self._closed, timeout)
            frame, self._frame = self._frame, None
            return frame

    def close(self):
        with self._condition:
            self._closed = True
            self._frame = None
            self._condition.notify_all()

def view_direction(x, y, width, height, fov_deg, yaw_deg=0, pitch_deg=0):
    """Pure scalar reference for the fixed perspective-to-sphere mapping."""
    scale = math.tan(math.radians(fov_deg) / 2)
    dx = (2 * (x + 0.5) / width - 1) * scale
    dy = (1 - 2 * (y + 0.5) / height) * scale * height / width
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    py, pz = dy * math.cos(pitch) + math.sin(pitch), -dy * math.sin(pitch) + math.cos(pitch)
    px, pz = dx * math.cos(yaw) + pz * math.sin(yaw), -dx * math.sin(yaw) + pz * math.cos(yaw)
    length = math.sqrt(px*px + py*py + pz*pz)
    return math.atan2(px, pz), math.asin(py / length)

class Projector:
    def __init__(self, config):
        self.config = config
        self._shape = None
        self._maps = None

    def apply(self, image):
        import cv2
        import numpy as np
        c = self.config
        if c.projection == "perspective":
            # Preserve aspect ratio; nonuniform resizing corrupts joint angles.
            scale = min(c.output_width / image.shape[1], c.output_height / image.shape[0], 1.0)
            return cv2.resize(image, (round(image.shape[1]*scale), round(image.shape[0]*scale))) if scale < 1 else image
        h, w = image.shape[:2]
        if abs(w / h - 2.0) > 0.05:
            raise ValueError("equirectangular input must be a stitched 2:1 panorama (not dual fisheye)")
        if self._shape != (h, w):
            x, y = np.meshgrid(np.arange(c.output_width), np.arange(c.output_height))
            scale = math.tan(math.radians(c.horizontal_fov_deg) / 2)
            dx = (2*(x + 0.5)/c.output_width - 1)*scale
            dy = (1 - 2*(y + 0.5)/c.output_height)*scale*c.output_height/c.output_width
            yaw, pitch = math.radians(c.yaw_deg), math.radians(c.pitch_deg)
            py, pz = dy*math.cos(pitch) + math.sin(pitch), -dy*math.sin(pitch) + math.cos(pitch)
            px, pz = dx*math.cos(yaw) + pz*math.sin(yaw), -dx*math.sin(yaw) + pz*math.cos(yaw)
            longitude = np.arctan2(px, pz)
            latitude = np.arcsin(py / np.sqrt(px*px + py*py + pz*pz))
            mx = ((longitude/(2*math.pi) + 0.5)*w - 0.5).astype(np.float32)
            my = np.clip((0.5 - latitude/math.pi)*h - 0.5, 0, h-1).astype(np.float32)
            self._maps, self._shape = (mx, my), (h, w)
        return cv2.remap(image, *self._maps, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

class CameraCapture:
    def __init__(self, config, get_generation, video=None):
        self.config, self.get_generation, self.video = config, get_generation, video
        self.frames = LatestFrame()
        self.stop_event = threading.Event()
        self.finished = threading.Event()
        self.error = ""
        self.actual = {}
        self._thread = None
        self._capture = None

    def start(self):
        import cv2
        backend = "auto" if self.video else self.config.backend
        if backend == "auto":
            backend = "dshow" if platform.system() == "Windows" else "v4l2"
        api = {"dshow": cv2.CAP_DSHOW, "v4l2": cv2.CAP_V4L2, "msmf": cv2.CAP_MSMF}[backend]
        source = self.video if self.video else self.config.device
        cap = cv2.VideoCapture(source, cv2.CAP_ANY if self.video else api)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"cannot open {source!r}; check Webcam mode and WSL /dev/video* mapping")
        try:
            self._capture = cap
            if not self.video:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
                cap.set(cv2.CAP_PROP_FPS, self.config.fps)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.actual = {"width": cap.get(cv2.CAP_PROP_FRAME_WIDTH), "height": cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                           "fps": cap.get(cv2.CAP_PROP_FPS), "backend": cap.getBackendName()}
            self._thread = threading.Thread(target=self._loop, name="camera-capture", daemon=True)
            self._thread.start()
        except Exception:
            cap.release()
            self._capture = None
            raise

    def _loop(self):
        projector = Projector(self.config)
        last_timestamp = -1
        try:
            fps = self.actual["fps"]
            period = 1 / fps if self.video and math.isfinite(fps) and fps > 0 else 0
            due = time.monotonic()
            while not self.stop_event.is_set():
                if period:
                    self.stop_event.wait(max(0, due - time.monotonic()))
                    due += period
                    if self.stop_event.is_set():
                        break
                # Bind generation BEFORE read: a reset while read blocks must not relabel that frame.
                token = self.get_generation()
                generation, epoch = token if isinstance(token, tuple) else (token, 0)
                ok, image = self._capture.read()
                if not ok:
                    if not self.video:
                        self.error = "camera stopped returning frames"
                    break
                timestamp = max(clock_ms(), last_timestamp + 1)
                last_timestamp = timestamp
                self.frames.put(Frame(generation, timestamp, projector.apply(image), epoch))
        except Exception as exc:
            self.error = str(exc)
        finally:
            self._capture.release()
            self.finished.set()

    def close(self):
        self.stop_event.set()
        self.frames.close()
        if self._thread:
            self._thread.join(timeout=2)
        # The capture thread owns release(); do not race a blocked VideoCapture.read().
