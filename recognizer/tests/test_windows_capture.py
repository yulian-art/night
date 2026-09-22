from dataclasses import replace
import io
import importlib.util
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from star_recognizer.config import CameraConfig
from star_recognizer.windows_capture import (WindowsFFmpegCapture, capture_command, read_exact,
    list_windows_devices, list_windows_options, pipe_dimensions, windows_device_names)

DEVICES = '''[dshow] "Insta360 X5" (video)
[dshow]   Alternative name "@device_pnp_x5"
[dshow] "Mic" (audio)
[dshow]   Alternative name "@device_audio"
'''

class FragmentedStream:
    def __init__(self,data):
        self.data=io.BytesIO(data)
    def read(self,n):
        return self.data.read(min(2,n))

class WindowsCaptureTests(unittest.TestCase):
    def test_partial_pipe_reads_preserve_frame_boundary(self):
        stream=FragmentedStream(b"abcdef123456")
        self.assertEqual(read_exact(stream,6),b"abcdef")
        self.assertEqual(read_exact(stream,6),b"123456")
        self.assertIsNone(read_exact(stream,6))

    def test_truncated_frame_is_error_not_reshaped_garbage(self):
        with self.assertRaises(EOFError):
            read_exact(io.BytesIO(b"abc"),6)

    def test_command_is_argv_with_exact_device_name(self):
        config=replace(CameraConfig(),backend="windows-ffmpeg",windows_device="X5 & echo should-not-run")
        with patch("star_recognizer.windows_capture.resolve_ffmpeg",return_value="/mnt/c/tools/ffmpeg.exe"):
            command=capture_command(config)
        self.assertIn("video=X5 & echo should-not-run",command)
        self.assertEqual(command[-1],"pipe:1")
        self.assertIn("dshow",command)
        self.assertIn("bgr24",command)

    def test_input_mode_and_pipe_shape_are_separate(self):
        config = CameraConfig(width=1920, height=1080, windows_video_codec="mjpeg")
        with patch("star_recognizer.windows_capture.resolve_ffmpeg", return_value="ffmpeg.exe"):
            command = capture_command(config)
        before, after = command[:command.index("-i")], command[command.index("-i"):]
        self.assertEqual(before[before.index("-video_size") + 1], "1920x1080")
        self.assertEqual(before[before.index("-vcodec") + 1], "mjpeg")
        self.assertEqual(after[after.index("-vf") + 1], "scale=960:540")
        self.assertEqual(after[after.index("-fps_mode") + 1], "passthrough")
        self.assertEqual(pipe_dimensions(config), (960, 540))

    def test_panorama_is_not_distorted_to_preview_aspect(self):
        config = CameraConfig(width=2880, height=1440, projection="equirectangular")
        self.assertEqual(pipe_dimensions(config), (2880, 1440))

    def test_device_names_include_only_video_aliases(self):
        self.assertEqual(windows_device_names(DEVICES), {"Insta360 X5", "@device_pnp_x5"})

    @patch("star_recognizer.windows_capture.resolve_ffmpeg", return_value="ffmpeg.exe")
    @patch("star_recognizer.windows_capture.subprocess.run")
    def test_enumeration_accepts_real_devices_despite_nonzero_exit(self, run, resolve):
        run.return_value = subprocess.CompletedProcess([], 1, b"", DEVICES.encode())
        self.assertEqual(list_windows_devices(CameraConfig()), DEVICES)

    @patch("star_recognizer.windows_capture.resolve_ffmpeg", return_value="ffmpeg.exe")
    @patch("star_recognizer.windows_capture.subprocess.run")
    def test_interop_failure_cannot_pass_doctor_even_with_exit_zero(self, run, resolve):
        run.return_value = subprocess.CompletedProcess([], 0, b"", b"WSL ERROR: socket failed 1")
        with self.assertRaisesRegex(RuntimeError, "Windows interop"):
            list_windows_devices(CameraConfig())

    @patch("star_recognizer.windows_capture.resolve_ffmpeg", return_value="ffmpeg.exe")
    @patch("star_recognizer.windows_capture.subprocess.run")
    def test_modes_require_actual_capabilities_not_just_header(self, run, resolve):
        run.return_value = subprocess.CompletedProcess([], 1, b"", b"DirectShow video device options\nCould not open device")
        with self.assertRaisesRegex(RuntimeError, "enumeration failed"):
            list_windows_options(CameraConfig())
        run.return_value.stderr = b"vcodec=mjpeg  min s=1920x1080 fps=30 max s=1920x1080 fps=30"
        self.assertIn("1920x1080", list_windows_options(CameraConfig()))

    @patch("star_recognizer.windows_capture.resolve_ffmpeg", return_value="ffmpeg.exe")
    @patch("star_recognizer.windows_capture.subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 15))
    def test_enumeration_timeout_is_actionable(self, run, resolve):
        with self.assertRaisesRegex(RuntimeError, "enumeration timed out"):
            list_windows_devices(CameraConfig())

    def test_cli_rejects_missing_configured_camera(self):
        from star_recognizer.cli import devices
        from star_recognizer.config import RuntimeConfig
        config = RuntimeConfig(camera=CameraConfig(backend="windows-ffmpeg", windows_device="Missing X5"))
        with patch("star_recognizer.windows_capture.list_windows_devices", return_value=DEVICES), patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaisesRegex(RuntimeError, "Missing X5.*absent"):
                devices(config)

    def test_cli_returns_failure_for_broken_interop(self):
        from star_recognizer.cli import main
        with patch("star_recognizer.windows_capture.list_windows_devices", side_effect=RuntimeError("WSL interop failed")), patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(main(["devices"]), 1)
            self.assertIn("WSL interop failed", err.getvalue())


@unittest.skipUnless(all(importlib.util.find_spec(name) for name in ("numpy", "cv2")), "requires NumPy/OpenCV")
class WindowsPipeTests(unittest.TestCase):
    def setUp(self):
        self.config = CameraConfig(width=64, height=64, output_width=64, output_height=64)

    def test_real_binary_subprocess_pipe_and_cleanup(self):
        code = "import sys; sys.stdout.buffer.write(bytes([17, 29, 43])*64*64); sys.stdout.buffer.flush(); sys.stdin.buffer.readline()"
        capture = WindowsFFmpegCapture(self.config, lambda: (7, 12))
        with patch("star_recognizer.windows_capture.capture_command", return_value=[sys.executable, "-u", "-c", code]):
            try:
                capture.start(timeout=2)
                frame = capture.frames.take(0)
                self.assertEqual((frame.generation, frame.reset_epoch), (7, 12))
                self.assertEqual(frame.image.shape, (64, 64, 3))
                self.assertEqual(frame.image[0, 0].tolist(), [17, 29, 43])
            finally:
                capture.close()
        self.assertIsNotNone(capture._process.poll())
        self.assertFalse(capture._thread.is_alive())
        self.assertFalse(capture._stderr_thread.is_alive())
        capture.close()  # CLI cleanup also runs after startup failure.

    def test_no_first_frame_times_out_and_reaps_child(self):
        code = "import sys; sys.stdin.buffer.readline()"
        capture = WindowsFFmpegCapture(self.config, lambda: 0)
        with patch("star_recognizer.windows_capture.capture_command", return_value=[sys.executable, "-u", "-c", code]):
            with self.assertRaisesRegex(RuntimeError, "No complete X5 frame"):
                capture.start(timeout=0.1)
        self.assertIsNotNone(capture._process.poll())
        self.assertTrue(capture.finished.is_set())

    def test_open_failure_keeps_ffmpeg_diagnostics(self):
        code = "import sys; sys.stderr.write('Could not set video options: unsupported 1280x720\\n'); sys.exit(1)"
        capture = WindowsFFmpegCapture(self.config, lambda: 0)
        with patch("star_recognizer.windows_capture.capture_command", return_value=[sys.executable, "-u", "-c", code]):
            with self.assertRaisesRegex(RuntimeError, "unsupported 1280x720"):
                capture.start(timeout=2)
        self.assertIsNotNone(capture._process.poll())

    def test_reset_during_blocking_read_cannot_relabel_old_frame(self):
        token = [5, 8]
        capture = WindowsFFmpegCapture(self.config, lambda: tuple(token))
        capture._process = Mock(stdout=object())
        def read(stream, size):
            token[:] = [5, 9]  # Same generation, new reset epoch while read was blocked.
            capture.stop_event.set()
            return bytes(size)
        with patch("star_recognizer.windows_capture.read_exact", side_effect=read):
            capture._loop()
        frame = capture.frames.take(0)
        self.assertEqual((frame.generation, frame.reset_epoch), (5, 8))

    def test_slow_consumer_keeps_only_latest_complete_frame(self):
        capture = WindowsFFmpegCapture(self.config, lambda: (5, 8))
        capture._process = Mock(stdout=object())
        frames = iter([bytes([1])*64*64*3, bytes([2])*64*64*3])
        def read(stream, size):
            data = next(frames)
            if data[0] == 2:
                capture.stop_event.set()
            return data
        with patch("star_recognizer.windows_capture.read_exact", side_effect=read):
            capture._loop()
        self.assertEqual(capture.frames.overwritten, 1)
        self.assertEqual(int(capture.frames.take(0).image[0, 0, 0]), 2)
        self.assertIsNone(capture.frames.take(0))

if __name__=="__main__":
    unittest.main()
