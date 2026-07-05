"""Resolve a clap's direction — the swappable Option A / Option B seam.

Both resolvers answer one question: "at the moment of this clap, which way was
it aimed?" and return a `Direction`. The clap source calls a resolver right when
an onset fires, so the game never learns which scheme is active.

- Option A (`VoiceCommandResolver`): direction is driven by voice keywords that
  rotate the player's facing; a plain clap is always FORWARD relative to that.
  This is the MVP path and needs no extra hardware or ML beyond keyword spotting
  (wired in later — for now it defaults to FORWARD).
- Option B (`WebcamHandResolver`): direction comes from where the player's hand
  is in the webcam frame (left / center / right) at clap time. Stubbed for
  Phase 5.
"""

from __future__ import annotations

import abc

from blind_hunter.events import Direction


class DirectionResolver(abc.ABC):
    @abc.abstractmethod
    def resolve(self) -> Direction:
        """Return the direction for a clap happening *now*."""


class ForwardResolver(DirectionResolver):
    """Phase 1 default: every clap steps forward. Dead simple, always reliable."""

    def resolve(self) -> Direction:
        return Direction.FORWARD


class VoiceCommandResolver(DirectionResolver):
    """Option A: facing is mutated by voice commands; claps go FORWARD.

    Turning is applied to the Player's facing in the game loop when a VoiceEvent
    arrives, so at clap time the aim is simply FORWARD. This class exists as the
    named seam for that scheme. (Keyword spotting integration: Phase 4/Option A.)
    """

    def resolve(self) -> Direction:
        return Direction.FORWARD


class WebcamHandResolver(DirectionResolver):
    """Option B stub: map latest webcam hand position to a Direction.

    Phase 5 wires a MediaPipe Hands thread that updates `self.latest_zone` with
    'left' / 'center' / 'right'. Until then it behaves like ForwardResolver.
    """

    def __init__(self) -> None:
        self.latest_zone: str = "center"

    def resolve(self) -> Direction:
        return {
            "left": Direction.LEFT,
            "right": Direction.RIGHT,
            "center": Direction.FORWARD,
        }.get(self.latest_zone, Direction.FORWARD)
