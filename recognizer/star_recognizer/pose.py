"""Bounded asynchronous MediaPipe adapter; no UE or transport objects on native callbacks."""
import threading
from pathlib import Path
from .capture import clock_ms
from .types import Landmark, PoseSample

class PoseEngine:
    def __init__(self, model_path, on_sample):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        if not Path(model_path).is_file():
            raise FileNotFoundError(f"missing model: {model_path}; run scripts/fetch_model.py")
        self._mp, self._on_sample = mp, on_sample
        self._lock = threading.Lock()
        self._pending = None
        self._preview = None
        self._closed = False
        self.error = ""
        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path, delegate=python.BaseOptions.Delegate.CPU),
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_poses=2,
            min_pose_detection_confidence=0.6,
            min_pose_presence_confidence=0.6,
            min_tracking_confidence=0.6,
            output_segmentation_masks=False,
            result_callback=self._result,
        )
        self._task = vision.PoseLandmarker.create_from_options(options)

    def submit(self, frame):
        import cv2
        with self._lock:
            if self._closed or self._pending is not None:
                return False
            self._pending = frame
        try:
            rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
            image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            self._task.detect_async(image, frame.timestamp_ms)
            return True
        except Exception:
            with self._lock:
                self._pending = None
            raise

    def _result(self, result, image, timestamp_ms):
        with self._lock:
            frame = self._pending
            closed = self._closed
        if closed or frame is None or timestamp_ms != frame.timestamp_ms:
            return
        try:
            poses = tuple(tuple(Landmark(p.x, p.y, p.z, p.visibility, p.presence) for p in pose)
                          for pose in result.pose_landmarks)
            sample = PoseSample(frame.generation, timestamp_ms, poses, frame.image.shape[1]/frame.image.shape[0], frame.reset_epoch)
            self._on_sample(sample)
            with self._lock:
                self._preview = (frame, sample)
        except Exception as exc:
            self.error = f"pose callback: {exc}"
        finally:
            with self._lock:
                self._pending = None

    def preview(self):
        with self._lock:
            return self._preview

    def pending_age_ms(self):
        with self._lock:
            return 0 if self._pending is None else max(0, clock_ms() - self._pending.timestamp_ms)

    def close(self):
        with self._lock:
            self._closed = True
        errors = []
        def shutdown():
            try:
                self._task.close()
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=shutdown, name="mediapipe-close", daemon=True)
        thread.start()
        thread.join(timeout=2)
        if thread.is_alive():
            raise RuntimeError("MediaPipe native shutdown timed out; transport is disconnected")
        if errors:
            raise RuntimeError(f"MediaPipe shutdown failed: {errors[0]}")
