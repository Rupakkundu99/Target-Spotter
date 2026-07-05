"""Spatial audio mixer (Phase 3).

Each audio-emitting entity owns a `pygame` Channel playing its looping sound.
Every tick we recompute a stereo (left, right) gain from the entity's position
relative to the player's position + facing, and push it with
`Channel.set_volume(left, right)` — pygame's per-channel stereo panning.

- **Pan** comes from the angle between player facing and the source.
- **Volume** falls off with distance (silent past MAX_AUDIBLE_DISTANCE) and is
  muffled when the source is behind the player (a cheap front/back cue, since
  stereo panning alone can't tell front from back).

Sounds load from the entity's AudioProfile .wav paths; if a file is missing we
synthesize a placeholder so the game never goes silent or crashes.

`pygame` and `numpy` are imported lazily so the package stays importable without
the audio stack.
"""

from __future__ import annotations

import math
import os
from typing import Optional

from blind_hunter import config
from blind_hunter.game.state import EntityKind, World, distance


def pan_and_volume(listener_pos, listener_facing_deg, source_pos):
    """Return (left_gain, right_gain) in 0..1 for a source relative to listener."""
    dist = distance(listener_pos, source_pos)
    if dist >= config.MAX_AUDIBLE_DISTANCE:
        return 0.0, 0.0

    volume = max(0.0, 1.0 - (dist / config.MAX_AUDIBLE_DISTANCE)) ** (
        1.0 + config.DISTANCE_FALLOFF
    )

    dx = source_pos[0] - listener_pos[0]
    dy = source_pos[1] - listener_pos[1]
    angle_to = math.degrees(math.atan2(dy, dx))
    rel = math.radians((angle_to - listener_facing_deg + 180) % 360 - 180)

    # Behind the listener → muffle for a front/back distinction.
    if math.cos(rel) < 0:
        volume *= config.BACK_MUFFLE

    # rel = 0 → dead ahead (centered); +/- pi/2 → hard right/left.
    pan = math.sin(rel)  # -1 (left) .. +1 (right)
    left = volume * (1.0 - max(0.0, pan))
    right = volume * (1.0 - max(0.0, -pan))
    return left, right


def _sound_from_synth(filename: str):
    """Build a pygame Sound from the procedural synth fallback."""
    import numpy as np
    import pygame

    from blind_hunter.audio import synth

    gen = synth.GENERATORS.get(os.path.basename(filename), synth.prey_breath)
    mono = gen()  # int16 mono
    # Match the mixer's channel count (usually stereo) for make_sound.
    channels = pygame.mixer.get_init()[2] if pygame.mixer.get_init() else 1
    if channels >= 2:
        data = np.ascontiguousarray(np.column_stack([mono, mono]))
    else:
        data = mono
    return pygame.sndarray.make_sound(data)


def load_sound(path: str):
    """Load a Sound from disk, or synthesize a placeholder if the file is absent."""
    import pygame

    if path and os.path.exists(path):
        try:
            return pygame.mixer.Sound(path)
        except Exception:
            pass  # fall through to synth
    return _sound_from_synth(path or "prey_breath.wav")


class _Voice:
    """One looping entity sound bound to a channel."""

    def __init__(self, channel, sound) -> None:
        self.channel = channel
        self.sound = sound
        self.channel.play(sound, loops=-1)


class SpatialMixer:
    def __init__(self) -> None:
        self._initialized = False
        self._voices: dict[str, _Voice] = {}
        self._next_channel = 1  # channel 0 is reserved for the heartbeat

    def init(self) -> None:
        import pygame

        pygame.mixer.pre_init(config.SAMPLE_RATE, -16, 2, config.AUDIO_BUFFER)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(config.MIXER_CHANNELS)
        self._initialized = True

    def load_world(self, world: World) -> None:
        """Give every audio-emitting entity a looping voice on its own channel."""
        import pygame

        if not self._initialized:
            return
        for ent in world.entities:
            path = ent.audio.idle_sound
            sound = load_sound(path)
            channel = pygame.mixer.Channel(self._next_channel)
            self._next_channel += 1
            self._voices[ent.id] = _Voice(channel, sound)

    def update(self, world: World) -> None:
        """Reposition every entity's sound relative to the player."""
        if not self._initialized:
            return
        player = world.player
        live_ids = {e.id for e in world.entities}

        # Silence + drop voices for entities that no longer exist (captured prey).
        for ent_id in list(self._voices):
            if ent_id not in live_ids:
                self._voices[ent_id].channel.stop()
                del self._voices[ent_id]

        for ent in world.entities:
            voice = self._voices.get(ent.id)
            if voice is None:
                continue
            left, right = pan_and_volume(player.position, player.facing, ent.position)
            m = config.MASTER_VOLUME
            voice.channel.set_volume(left * m, right * m)

    def shutdown(self) -> None:
        if self._initialized:
            import pygame

            pygame.mixer.stop()
            pygame.mixer.quit()
            self._initialized = False
            self._voices.clear()
