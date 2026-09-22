"""Serializes resets, inference callbacks, and the missing-frame watchdog."""
import json
import threading
from .capture import clock_ms
from .gestures import GestureConfig, GestureRecognizer

class Controller:
    def __init__(self, config, send=None, emit_log=True):
        self.config = config
        self.recognizer = GestureRecognizer(GestureConfig(**config.gestures))
        self._lock = threading.RLock()
        self._send = send
        self._emit_log = emit_log
        self._last_result_at = clock_ms()
        self._invalid_through = -1
        self._watchdog_lost = False
        self._reset_epoch = 0

    def capture_token(self):
        with self._lock:
            return self.recognizer.generation, self._reset_epoch

    def set_sender(self, send):
        with self._lock:
            self._send = send

    def generation(self):
        with self._lock:
            return self.recognizer.generation

    def reset(self, generation):
        with self._lock:
            self._reset_epoch += 1
            self.recognizer.reset(generation)
            self._last_result_at = clock_ms()
            self._invalid_through = -1
            self._watchdog_lost = False

    def _publish(self, events):
        for event in events:
            if self._emit_log:
                data = {"generation": str(event.generation)}
                if event.state is not None:
                    data["state"] = event.state.name
                else:
                    data.update(action=event.action.name, phase=event.phase.name)
                print(json.dumps(data), flush=True)
            if self._send:
                self._send(event)

    def observe(self, sample):
        with self._lock:
            now = clock_ms()
            if sample.reset_epoch != self._reset_epoch or sample.generation != self.recognizer.generation or sample.timestamp_ms <= self._invalid_through:
                return
            if now - sample.timestamp_ms > self.config.max_frame_age_ms:
                return
            self._last_result_at = now
            self._watchdog_lost = False
            self._publish(self.recognizer.observe(sample))

    def watchdog(self, now=None):
        with self._lock:
            now = clock_ms() if now is None else now
            if now - self._last_result_at >= self.config.lost_after_ms and not self._watchdog_lost:
                self._watchdog_lost = True
                self._invalid_through = now
                self._publish(self.recognizer.lost(self.recognizer.generation, now))

    def status(self):
        with self._lock:
            r = self.recognizer
            return {"generation": r.generation, "state": r.tracking_state.name,
                    "action": r.active_action.name if r.active_action else "-",
                    "reason": r.reason}
