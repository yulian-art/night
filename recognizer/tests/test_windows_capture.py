from dataclasses import replace
import io
import unittest
from unittest.mock import patch
from star_recognizer.config import CameraConfig
from star_recognizer.windows_capture import capture_command,read_exact

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

if __name__=="__main__":
    unittest.main()
