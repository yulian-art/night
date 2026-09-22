import importlib.util
from pathlib import Path
import threading
import unittest

AVAILABLE = all(importlib.util.find_spec(name) for name in ("mediapipe", "numpy", "cv2"))
MODEL = Path(__file__).resolve().parents[1]/"models/pose_landmarker_lite.task"

@unittest.skipUnless(AVAILABLE and MODEL.is_file(), "requires installed MediaPipe/OpenCV and local model")
class RealPoseTests(unittest.TestCase):
    def test_real_cpu_model_blank_frame_callback_preserves_token(self):
        import numpy as np
        from star_recognizer.pose import PoseEngine
        from star_recognizer.capture import Frame,clock_ms
        ready=threading.Event()
        samples=[]
        def callback(sample):
            samples.append(sample)
            ready.set()
        engine=PoseEngine(str(MODEL),callback)
        try:
            self.assertTrue(engine.submit(Frame(7,clock_ms(),np.zeros((480,640,3),dtype=np.uint8),12)))
            self.assertTrue(ready.wait(10),"MediaPipe callback timeout")
            self.assertEqual((samples[0].generation,samples[0].reset_epoch),(7,12))
            self.assertEqual(samples[0].poses,())
            self.assertAlmostEqual(samples[0].aspect_ratio,640/480)
        finally:
            engine.close()

class ControllerTests(unittest.TestCase):
    def test_old_callback_after_same_generation_reset_is_ignored(self):
        from star_recognizer.controller import Controller
        from star_recognizer.config import RuntimeConfig
        from star_recognizer.types import PoseSample
        from star_recognizer.capture import clock_ms
        from unittest.mock import patch
        controller=Controller(RuntimeConfig(),emit_log=False)
        controller.reset(5)
        _,old_epoch=controller.capture_token()
        controller.reset(5)
        with patch.object(controller.recognizer,"observe") as observe:
            controller.observe(PoseSample(5,clock_ms(),(),reset_epoch=old_epoch))
            observe.assert_not_called()
            _,epoch=controller.capture_token()
            controller.observe(PoseSample(5,clock_ms(),(),reset_epoch=epoch))
            observe.assert_called_once()

    def test_watchdog_invalidates_delayed_result(self):
        from star_recognizer.controller import Controller
        from star_recognizer.config import RuntimeConfig
        from star_recognizer.types import PoseSample
        from star_recognizer.capture import clock_ms
        from unittest.mock import patch
        controller=Controller(RuntimeConfig(),emit_log=False)
        controller.reset(6)
        _,epoch=controller.capture_token()
        now=clock_ms()
        controller.watchdog(now+1000)
        with patch.object(controller.recognizer,"observe") as observe:
            controller.observe(PoseSample(6,now,(),reset_epoch=epoch))
            observe.assert_not_called()

if __name__=="__main__":
    unittest.main()
