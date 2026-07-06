"""Ambient drone audio layer (Phase 6C).

Plays a continuous low-volume atmospheric drone on a dedicated mixer channel
(channel MIXER_CHANNELS - 1) so the game world never feels completely silent or sterile.
"""

from __future__ import annotations

from blind_hunter import config


class AmbientDrone:
    """Plays a looping atmospheric background drone."""

    CHANNEL_INDEX = config.MIXER_CHANNELS - 1

    def __init__(self) -> None:
        self._sound = None
        self._channel = None

    def init(self) -> None:
        import pygame
        from blind_hunter.audio.spatial_mixer import load_sound

        if not pygame.mixer.get_init():
            return
        self._sound = load_sound("assets/audio/ambient_drone.wav")
        self._channel = pygame.mixer.Channel(self.CHANNEL_INDEX)
        self._channel.set_volume(config.MASTER_VOLUME * 0.35)
        if self._sound:
            self._channel.play(self._sound, loops=-1)

    def shutdown(self) -> None:
        if self._channel is not None:
            self._channel.stop()
