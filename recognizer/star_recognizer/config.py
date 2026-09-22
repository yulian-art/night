"""Runtime configuration; relative model/video paths are relative to the config file."""
from dataclasses import dataclass, field, fields
import json
import math
from pathlib import Path

@dataclass(frozen=True)
class CameraConfig:
    device: int | str = 0
    backend: str = "auto"
    width: int = 1280
    height: int = 720
    fps: float = 30.0
    projection: str = "perspective"
    output_width: int = 960
    output_height: int = 720
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    horizontal_fov_deg: float = 90.0
    mirror_preview: bool = True
    windows_ffmpeg: str = "ffmpeg.exe"
    windows_device: str = "Insta360 X5"
    windows_video_codec: str = ""

    def __post_init__(self):
        if self.backend not in {"auto", "v4l2", "dshow", "msmf", "windows-ffmpeg"}:
            raise ValueError("camera.backend must be auto/v4l2/dshow/msmf/windows-ffmpeg")
        if self.projection not in {"perspective", "equirectangular"}:
            raise ValueError("camera.projection must be perspective/equirectangular")
        for name in ("width", "height", "output_width", "output_height"):
            value = getattr(self, name)
            if type(value) is not int or not 64 <= value <= 8192:
                raise ValueError(f"camera.{name} must be an integer in [64,8192]")
        if not math.isfinite(self.fps) or not 1 <= self.fps <= 120:
            raise ValueError("camera.fps must be in [1,120]")
        if not 20 <= self.horizontal_fov_deg <= 140:
            raise ValueError("horizontal_fov_deg must be in [20,140]")
        if not -180 <= self.yaw_deg <= 180 or not -80 <= self.pitch_deg <= 80:
            raise ValueError("invalid camera yaw/pitch")
        if type(self.device) not in (int, str) or isinstance(self.device, int) and self.device < 0:
            raise ValueError("camera.device must be a nonnegative index or /dev/video path")
        if isinstance(self.device, str) and not self.device.startswith("/dev/video"):
            raise ValueError("use --video for a file; camera.device strings must be /dev/video paths")
        for name in ("windows_ffmpeg", "windows_device"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or "\0" in value:
                raise ValueError(f"camera.{name} must be a nonempty string without NUL")
        if not isinstance(self.windows_video_codec, str) or (
            self.windows_video_codec and not self.windows_video_codec.replace("_", "").isalnum()
        ):
            raise ValueError("camera.windows_video_codec must be a codec name such as mjpeg, or empty for driver default")

@dataclass(frozen=True)
class RuntimeConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    model: str = "models/pose_landmarker_lite.task"
    address: str = "127.0.0.1:50051"
    max_frame_age_ms: int = 500
    lost_after_ms: int = 750
    inference_timeout_ms: int = 5000
    gestures: dict = field(default_factory=dict)

    def __post_init__(self):
        if not 100 <= self.max_frame_age_ms <= 2000:
            raise ValueError("max_frame_age_ms must be in [100,2000]")
        if not self.max_frame_age_ms <= self.lost_after_ms < self.inference_timeout_ms:
            raise ValueError("require max_frame_age_ms <= lost_after_ms < inference_timeout_ms")
        if not isinstance(self.gestures, dict):
            raise ValueError("gestures must be a JSON object")

def load_config(path: str | Path) -> RuntimeConfig:
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    unknown = set(data) - {f.name for f in fields(RuntimeConfig)}
    if unknown:
        raise ValueError(f"unknown config fields: {sorted(unknown)}")
    camera_data = data.pop("camera", {})
    ffmpeg = camera_data.get("windows_ffmpeg", "ffmpeg.exe")
    if "/" in ffmpeg and not Path(ffmpeg).is_absolute():
        camera_data["windows_ffmpeg"] = str(path.parent / ffmpeg)
    camera = CameraConfig(**camera_data)
    model = Path(data.pop("model", "models/pose_landmarker_lite.task"))
    if not model.is_absolute():
        model = path.parent / model
    return RuntimeConfig(camera=camera, model=str(model), **data)
