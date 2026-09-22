"""Command-line entry points. No camera, network, or native imports at module import."""
import argparse
from dataclasses import replace
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import signal
import sys
import threading
import time

from .config import load_config
ROOT = Path(__file__).resolve().parents[1]

def parser():
    p = argparse.ArgumentParser(prog="star-recognizer", description="X5 / MediaPipe local pose runtime")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="capture and recognize; use --standalone until UE/watch is connected")
    run.add_argument("--config", default=str(ROOT / "config.example.json"))
    run.add_argument("--camera", help="Windows device name for windows-ffmpeg; otherwise numeric index or /dev/video path")
    run.add_argument("--video", help="local recording for standalone testing, played at source FPS")
    run.add_argument("--model")
    run.add_argument("--address")
    run.add_argument("--standalone", action="store_true", help="local events only; no Go producer connection")
    run.add_argument("--headless", action="store_true")
    run.add_argument("--seconds", type=float, default=0, help="0 runs until stopped")
    doc = sub.add_parser("doctor", help="check existing environment without installing anything")
    doc.add_argument("--config", default=str(ROOT / "config.example.json"))
    doc.add_argument("--go", action="store_true", help="also call GetProgress (no save writes)")
    dev = sub.add_parser("devices", help="list capture devices")
    dev.add_argument("--config", default=str(ROOT / "config.example.json"))
    dev.add_argument("--modes", action="store_true", help="list the configured Windows camera's input modes")
    probe = sub.add_parser("probe", help="verify Windows camera -> WSL by reading a complete frame; no inference or Go")
    probe.add_argument("--config", default=str(ROOT / "config.example.json"))
    probe.add_argument("--timeout", type=float, default=10, help="first-frame timeout in seconds")
    watch = sub.add_parser("watch", help="temporary UE input consumer, no camera and no SaveRun")
    watch.add_argument("--address", default="127.0.0.1:50051")
    watch.add_argument("--seconds", type=float, default=60)
    return p

def devices(config=None, modes=False):
    if config is not None and config.camera.backend == "windows-ffmpeg":
        from .windows_capture import list_windows_devices, list_windows_options, windows_device_names
        listing = list_windows_devices(config.camera)
        print(listing)
        if config.camera.windows_device not in windows_device_names(listing):
            raise RuntimeError(f"Configured Windows video device {config.camera.windows_device!r} is absent; "
                               "set camera.windows_device to a listed video name or alternative name")
        if modes:
            print(list_windows_options(config.camera))
        else:
            print("Device found; video capture is not verified. Use 'probe' to check an actual frame.")
        return 0
    if modes:
        raise ValueError("devices --modes requires camera.backend=windows-ffmpeg")
    nodes = sorted(Path("/dev").glob("video*"))
    for node in nodes:
        name_file = Path("/sys/class/video4linux") / node.name / "name"
        name = name_file.read_text().strip() if name_file.exists() else "unknown"
        print(json.dumps({"device": str(node), "name": name, "readable": os.access(node, os.R_OK),
                          "writable": os.access(node, os.W_OK)}, ensure_ascii=False))
    if not nodes:
        print("No /dev/video* devices. X5 must be in Webcam mode and attached to WSL via USB/IP.")
    return 0 if nodes else 2

def probe(args):
    from .windows_capture import WindowsFFmpegCapture
    config = load_config(args.config)
    if config.camera.backend != "windows-ffmpeg":
        raise ValueError("probe requires camera.backend=windows-ffmpeg")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("--timeout must be a finite positive number")
    capture = WindowsFFmpegCapture(config.camera, lambda: (0, 0))
    try:
        capture.start(timeout=args.timeout)
        frame = capture.frames.take(0)
        if frame is None:
            raise RuntimeError("Windows camera did not deliver a complete frame")
        print(json.dumps({"capture": "ok", **capture.actual,
                          "frame_shape": list(frame.image.shape)}, ensure_ascii=False))
    finally:
        capture.close()
    return 0

def doctor(args):
    config = load_config(args.config)
    missing = []
    print(f"Python: {sys.executable}\nVersion: {sys.version.split()[0]}\nPlatform: {platform.platform()}")
    for name in ("mediapipe", "opencv-contrib-python", "numpy", "grpcio", "protobuf"):
        try:
            print(f"{name}: {importlib.metadata.version(name)}")
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
            print(f"{name}: MISSING")
    print(f"Model: {config.model} ({'found' if Path(config.model).is_file() else 'MISSING'})")
    print(f"Preview: DISPLAY={os.environ.get('DISPLAY', '')} WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '')}")
    print("Inference delegate: CPU. CUDA installation alone does not select a MediaPipe GPU delegate.")
    camera_result = devices(config)
    if args.go:
        import grpc
        from .generated.star.v1 import star_pb2 as pb
        with grpc.insecure_channel(config.address) as channel:
            get = channel.unary_unary("/star.v1.StarService/GetProgress",
                                      request_serializer=pb.GetProgressRequest.SerializeToString,
                                      response_deserializer=pb.GetProgressResponse.FromString)
            print("Go GetProgress:", get(pb.GetProgressRequest(), timeout=3))
    return 2 if missing or not Path(config.model).is_file() or camera_result else 0

def watch(args):
    import grpc
    from .generated.star.v1 import star_pb2 as pb
    if args.seconds <= 0:
        raise ValueError("--seconds must be positive for watch")
    generation = time.time_ns()
    print(f"Temporary UE consumer generation={generation}; do not run alongside real UE.", flush=True)
    with grpc.insecure_channel(args.address) as channel:
        call = channel.unary_stream("/star.v1.StarService/WatchInput",
                                    request_serializer=pb.WatchInputRequest.SerializeToString,
                                    response_deserializer=pb.InputEvent.FromString)
        stream = call(pb.WatchInputRequest(generation=generation), timeout=args.seconds)
        try:
            for event in stream:
                if event.HasField("tracking"):
                    print(json.dumps({"generation": str(event.tracking.generation),
                                      "state": pb.TrackingState.Name(event.tracking.state)}), flush=True)
                else:
                    print(json.dumps({"generation": str(event.action.generation),
                                      "action": pb.Action.Name(event.action.action),
                                      "phase": pb.Phase.Name(event.action.phase)}), flush=True)
        except grpc.RpcError as exc:
            if exc.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                raise
        finally:
            stream.cancel()
    return 0

def run(args):
    from .capture import CameraCapture, clock_ms
    from .controller import Controller
    from .pose import PoseEngine
    config = load_config(args.config)
    if not math.isfinite(args.seconds) or args.seconds < 0:
        raise ValueError("--seconds must be finite and nonnegative")
    if args.video and not args.standalone:
        raise ValueError("--video requires --standalone so recorded actions cannot enter a real game")
    if args.video and not Path(args.video).is_file():
        raise FileNotFoundError(args.video)
    if args.camera:
        if config.camera.backend == "windows-ffmpeg":
            config = replace(config, camera=replace(config.camera, windows_device=args.camera))
        else:
            device = int(args.camera) if args.camera.isdecimal() else args.camera
            config = replace(config, camera=replace(config.camera, device=device))
    if args.model:
        config = replace(config, model=str(Path(args.model).resolve()))
    if args.address:
        config = replace(config, address=args.address)
    controller = Controller(config)
    stop = threading.Event()
    prior = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        prior[sig] = signal.signal(sig, lambda *_: stop.set())
    bridge = engine = capture = None
    started = time.monotonic()
    try:
        # Load the model before opening the camera, so configuration errors are actionable.
        engine = PoseEngine(config.model, controller.observe)
        if args.standalone:
            controller.reset(time.time_ns())
        else:
            from .transport import GrpcBridge
            def disconnected(reason):
                controller.reset(0)
                print(f"Go connection: {reason}", file=sys.stderr, flush=True)
            bridge = GrpcBridge(config.address, controller.reset, disconnected)
            controller.set_sender(bridge.send)
            bridge.start()
        if config.camera.backend == "windows-ffmpeg" and not args.video:
            from .windows_capture import WindowsFFmpegCapture
            capture = WindowsFFmpegCapture(config.camera, controller.capture_token)
        else:
            capture = CameraCapture(config.camera, controller.capture_token, args.video)
        capture.start()
        print("Capture ready: " + json.dumps(capture.actual), file=sys.stderr, flush=True)
        if not args.standalone:
            print("Waiting for UE or 'watch' to open a generation. No UE means no action output.", file=sys.stderr)
        while not stop.is_set():
            if args.seconds and time.monotonic() - started >= args.seconds:
                break
            frame = capture.frames.take(0.02)
            if frame is not None and clock_ms() - frame.timestamp_ms <= config.max_frame_age_ms:
                engine.submit(frame)
            controller.watchdog()
            if engine.error:
                raise RuntimeError(engine.error)
            if engine.pending_age_ms() > config.inference_timeout_ms:
                raise RuntimeError("MediaPipe inference timed out; restart runtime and re-confirm readiness")
            if capture.error:
                controller.watchdog(clock_ms() + config.lost_after_ms)
                raise RuntimeError(capture.error)
            if getattr(capture, "last_frame_at", 0) and clock_ms() - capture.last_frame_at > config.inference_timeout_ms:
                raise RuntimeError("Windows camera stopped delivering frames; check USB connection and restart capture")
            if not args.headless:
                from .preview import show
                preview = engine.preview()
                if preview:
                    current = controller.status()
                    view_frame, sample = preview
                    from .types import PoseSample
                    if (sample.generation, sample.reset_epoch) != controller.capture_token():
                        sample = PoseSample(sample.generation, sample.timestamp_ms, (), sample.aspect_ratio, sample.reset_epoch)
                    age = clock_ms() - view_frame.timestamp_ms
                    connection = "standalone" if bridge is None else ("Go connected" if bridge.connected else bridge.last_error)
                    if not show(view_frame, sample, current, config.camera.mirror_preview, f"{connection}; frame age {age}ms"):
                        break
            if capture.finished.is_set() and frame is None and engine.pending_age_ms() == 0:
                break
    finally:
        active_exception = sys.exc_info()[0] is not None
        errors = []
        try:
            # Disconnect Go first; native camera/inference cleanup must not keep gameplay alive.
            for resource in (bridge, capture, engine):
                if resource:
                    try:
                        resource.close()
                    except Exception as exc:
                        errors.append(str(exc))
            if not args.headless:
                try:
                    import cv2
                    cv2.destroyAllWindows()
                except Exception as exc:
                    errors.append(str(exc))
        finally:
            for sig, handler in prior.items():
                signal.signal(sig, handler)
        if errors:
            message = "Cleanup: " + "; ".join(errors)
            if active_exception:
                print(message, file=sys.stderr)
            else:
                raise RuntimeError(message)

    return 0

def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return {"run": run, "doctor": doctor, "devices": lambda a: devices(load_config(a.config), a.modes),
                "probe": probe, "watch": watch}[args.command](args)
    except KeyboardInterrupt:
        return 0
    except (ValueError, TypeError, OSError, RuntimeError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if isinstance(exc, ImportError):
            print("Install recognizer/requirements.txt into your selected WSL Python environment.", file=sys.stderr)
        return 1
    except Exception as exc:
        # gRPC exceptions and native-library startup errors remain actionable without a traceback flood.
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
