"""Dependency-free domain types. Enum numbers match proto/star/v1/star.proto."""
from dataclasses import dataclass
from enum import IntEnum


class Action(IntEnum):
    SQUAT = 1
    LEFT_LEG = 2
    RIGHT_LEG = 3
    JUMP_LEFT = 4
    JUMP_RIGHT = 5
    JUMPING_JACK = 6


class Phase(IntEnum):
    BEGIN = 1
    COMPLETE = 2
    CANCEL = 3


class TrackingState(IntEnum):
    LOST = 1
    NOT_READY = 2
    READY = 3


@dataclass(frozen=True)
class InputEvent:
    generation: int
    action: Action | None = None
    phase: Phase | None = None
    state: TrackingState | None = None

    def __post_init__(self):
        if type(self.generation) is not int or not 0 < self.generation < 2**64:
            raise ValueError("event generation must be a nonzero uint64")
        if self.state is not None:
            if self.action is not None or self.phase is not None:
                raise ValueError("event must contain tracking OR action")
        elif self.action is None or self.phase is None:
            raise ValueError("action event requires action and phase")


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0
    presence: float = 1.0


@dataclass(frozen=True)
class PoseSample:
    generation: int
    timestamp_ms: int
    poses: tuple[tuple[Landmark, ...], ...]
    aspect_ratio: float = 4 / 3
    reset_epoch: int = 0
