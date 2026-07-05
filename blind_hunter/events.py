"""Event types that flow from the input layer into the game core.

The whole architecture pivots on `ClapEvent`: Option A (mic-only) and Option B
(mic + webcam) both ultimately emit one of these, so the game loop never needs
to know which input scheme produced it.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field


class Direction(enum.Enum):
    """Coarse direction a clap is aimed at.

    Option A resolves this from the last voice-command facing (usually FORWARD
    relative to the player). Option B resolves it from webcam hand position.
    """

    FORWARD = "forward"
    LEFT = "left"
    RIGHT = "right"
    BACK = "back"


@dataclass(frozen=True)
class ClapEvent:
    """A discrete sound event detected from the mic.

    Attributes:
        intensity: normalized 0..1 loudness of the clap.
        direction: coarse aim of the clap (see Direction).
        timestamp: monotonic seconds when the onset was detected.
        is_double: True if this is the second clap of a quick double-clap.
    """

    intensity: float
    direction: Direction = Direction.FORWARD
    timestamp: float = field(default_factory=time.monotonic)
    is_double: bool = False
    sound_type: str = "clap"



class VoiceCommand(enum.Enum):
    """Recognized keyword-spotting commands (Option A turning)."""

    LEFT = "left"
    RIGHT = "right"
    TURN = "turn"


@dataclass(frozen=True)
class VoiceEvent:
    command: VoiceCommand
    timestamp: float = field(default_factory=time.monotonic)
