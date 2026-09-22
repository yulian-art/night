import json
import math
from pathlib import Path
import tempfile
import threading
import unittest
from star_recognizer.capture import Frame, LatestFrame, view_direction
from star_recognizer.config import CameraConfig, load_config
from star_recognizer.types import InputEvent, Action, Phase, TrackingState

class CaptureTests(unittest.TestCase):
    def test_latest_only_and_generation_is_not_relabelled(self):
        buffer=LatestFrame()
        buffer.put(Frame(41,100,"old"))
        buffer.put(Frame(42,120,"new"))
        frame=buffer.take(0)
        self.assertEqual((frame.generation,frame.image),(42,"new"))
        self.assertEqual(buffer.overwritten,1)
        self.assertIsNone(buffer.take(0))

    def test_close_wakes_reader(self):
        buffer=LatestFrame()
        done=threading.Event()
        thread=threading.Thread(target=lambda:(buffer.take(5),done.set()))
        thread.start()
        buffer.close()
        self.assertTrue(done.wait(0.5))
        thread.join()
        buffer.put(Frame(1,10,"ignored"))
        self.assertIsNone(buffer.take(0))

    def test_panorama_center_rotation_and_horizon(self):
        lon,lat=view_direction(49.5,49.5,100,100,90)
        self.assertAlmostEqual(lon,0)
        self.assertAlmostEqual(lat,0)
        lon,lat=view_direction(49.5,49.5,100,100,90,90,30)
        self.assertAlmostEqual(lon,math.pi/2)
        self.assertAlmostEqual(lat,math.pi/6)

    def test_ray_edges_cover_specified_field_of_view(self):
        left,_=view_direction(-0.5,49.5,100,100,90)
        right,_=view_direction(99.5,49.5,100,100,90)
        self.assertAlmostEqual(right-left,math.pi/2)

class ConfigTests(unittest.TestCase):
    def test_paths_resolve_relative_to_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"config.json"
            path.write_text(json.dumps({"camera":{"device":"/dev/video2"},"model":"models/pose.task"}))
            config=load_config(path)
            self.assertEqual(config.model,str(Path(directory)/"models/pose.task"))
            self.assertEqual(config.camera.device,"/dev/video2")

    def test_typo_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"bad.json"
            path.write_text('{"adress":"x"}')
            with self.assertRaises(ValueError):
                load_config(path)

    def test_invalid_projection_or_file_device_fails(self):
        with self.assertRaises(ValueError):
            CameraConfig(projection="fish-eye")
        with self.assertRaises(ValueError):
            CameraConfig(device="recording.mp4")

    def test_uint64_generation_never_uses_float(self):
        g=2**63+12345
        event=InputEvent(g,action=Action.SQUAT,phase=Phase.BEGIN)
        self.assertEqual(event.generation,g)
        with self.assertRaises(ValueError):
            InputEvent(0,state=TrackingState.READY)
        with self.assertRaises(ValueError):
            InputEvent(g,action=Action.SQUAT,phase=Phase.BEGIN,state=TrackingState.READY)

if __name__=="__main__":
    unittest.main()
