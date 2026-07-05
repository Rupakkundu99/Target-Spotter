"""Noise-event propagation (Phase 4).

Each clap registers a ``NoiseEvent`` at the player's position. Predators are
drawn toward recent noise; prey flee from it. Events decay over time so the world
"forgets" old sounds and the AI doesn't stay alert indefinitely.

Decay is two-fold:
- An event's *effective* intensity ramps down linearly across
  ``NOISE_DECAY_SECONDS`` (``decayed_intensity``), so a sound that just happened
  matters more than one from three seconds ago.
- Once fully decayed, the event is pruned from the player's history.

Entities "hear" the loudest *decayed* noise inside their hearing radius, so as a
noise ages it both quiets down and, eventually, drops out entirely.
"""

from __future__ import annotations

from blind_hunter.game.state import NoiseEvent, World, distance

# How long (seconds) until a noise event has fully decayed and is forgotten.
NOISE_DECAY_SECONDS = 4.0


def register_clap(world: World, intensity: float, now: float) -> None:
    """Record a noise event at the player's current position."""
    world.player.noise_history.append(
        NoiseEvent(position=world.player.position, intensity=intensity, timestamp=now)
    )


def decayed_intensity(noise: NoiseEvent, now: float) -> float:
    """Effective loudness of a noise right now (0 once fully decayed)."""
    age = now - noise.timestamp
    if age <= 0.0:
        return noise.intensity
    if age >= NOISE_DECAY_SECONDS:
        return 0.0
    return noise.intensity * (1.0 - age / NOISE_DECAY_SECONDS)


def active_noises(world: World, now: float) -> list[NoiseEvent]:
    """Return non-decayed noise events (and prune the rest)."""
    fresh = [
        n for n in world.player.noise_history
        if (now - n.timestamp) < NOISE_DECAY_SECONDS
    ]
    world.player.noise_history = fresh
    return fresh


class _HeardNoise:
    """A noise as perceived by an entity: source position + decayed loudness.

    Kept API-compatible with ``NoiseEvent`` (``.position`` / ``.intensity``) so
    the AI can treat it the same, but ``intensity`` here is the *decayed* value.
    """

    __slots__ = ("position", "intensity")

    def __init__(self, position, intensity: float) -> None:
        self.position = position
        self.intensity = intensity


def loudest_heard(entity_pos, world: World, now: float, hearing_radius: float):
    """Loudest currently-audible noise within an entity's hearing radius, or None.

    Loudness is the time-decayed intensity, so aging noises fade out of hearing
    before they're pruned entirely.
    """
    best: _HeardNoise | None = None
    for n in active_noises(world, now):
        if distance(entity_pos, n.position) > hearing_radius:
            continue
        loud = decayed_intensity(n, now)
        if loud <= 0.0:
            continue
        if best is None or loud > best.intensity:
            best = _HeardNoise(n.position, loud)
    return best
