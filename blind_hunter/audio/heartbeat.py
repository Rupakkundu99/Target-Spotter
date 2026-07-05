"""Heartbeat tension loop (Phase 3).

A 'lub-dub' pulse retriggered on a reserved channel, whose tempo and volume rise
as the nearest predator closes in. This is the passive tension channel — it
gives the player proximity information without needing to ping.

Runs on mixer channel 0 (SpatialMixer allocates entity voices from channel 1),
so the two never fight over a channel.
"""

from __future__ import annotations

from blind_hunter import config
from blind_hunter.game.state import EntityKind, World, distance


def nearest_predator_distance(world: World) -> float:
    dists = [
        distance(world.player.position, e.position)
        for e in world.entities
        if e.kind is EntityKind.PREDATOR
    ]
    return min(dists) if dists else float("inf")


def closeness(dist: float) -> float:
    """0 at/after max audible range, 1 when adjacent."""
    if dist >= config.MAX_AUDIBLE_DISTANCE:
        return 0.0
    return 1.0 - (dist / config.MAX_AUDIBLE_DISTANCE)


def tempo_for_distance(dist: float) -> float:
    """Beats-per-second: fast when close, slow (or silent) when far."""
    c = closeness(dist)
    if c <= 0.0:
        return 0.0
    return config.HEARTBEAT_TEMPO_MIN + (
        config.HEARTBEAT_TEMPO_MAX - config.HEARTBEAT_TEMPO_MIN
    ) * c


class Heartbeat:
    """Retriggers a heartbeat sample at a distance-driven tempo."""

    CHANNEL_INDEX = 0

    def __init__(self) -> None:
        self._sound = None
        self._channel = None
        self._last_beat: float = -1.0

    def init(self) -> None:
        import pygame

        from blind_hunter.audio.spatial_mixer import load_sound

        if not pygame.mixer.get_init():
            return
        self._sound = load_sound("assets/audio/heartbeat.wav")
        self._channel = pygame.mixer.Channel(self.CHANNEL_INDEX)

    def update(self, world: World, now: float) -> None:
        if self._sound is None or self._channel is None:
            return
        dist = nearest_predator_distance(world)
        tempo = tempo_for_distance(dist)
        if tempo <= 0.0:
            return

        interval = 1.0 / tempo
        if self._last_beat < 0 or (now - self._last_beat) >= interval:
            volume = config.HEARTBEAT_VOLUME * closeness(dist)
            self._channel.set_volume(volume)
            self._channel.play(self._sound)
            self._last_beat = now

    def shutdown(self) -> None:
        if self._channel is not None:
            self._channel.stop()
