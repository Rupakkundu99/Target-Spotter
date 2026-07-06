"""Post-processing effects for Blind Hunter 2D Horror Upgrade (Phase 6A).

Provides screen-space distortion and camera polish effects:
1. **Screen-Shake**: Random decaying displacement vector triggered by claps,
   snaps, pings, or predator attacks.
2. **Chromatic Aberration**: Fast in-place RGB channel shifting via NumPy slicing
   during intense audio onset events or high danger.
3. **Scanlines**: Pre-rendered CRT/found-footage horizontal scanline overlay.
"""

from __future__ import annotations

import math
import random
import numpy as np

from blind_hunter import config


class PostFX:
    def __init__(self) -> None:
        self._width = 0
        self._height = 0
        self._shake_intensity = 0.0
        self._shake_offset = (0, 0)
        self._aberration_timer = 0.0
        self._aberration_px = 0
        self._scanlines = None
        self._rng = random.Random()

    def init(self, width: int, height: int) -> None:
        import pygame

        self._width = width
        self._height = height

        # Pre-render horizontal scanline overlay
        self._scanlines = pygame.Surface((width, height), pygame.SRCALPHA)
        self._scanlines.fill((0, 0, 0, 0))
        
        # Every 3rd row is darkened
        alpha_val = int(255 * config.SCANLINE_OPACITY)
        for y in range(0, height, 3):
            pygame.draw.line(self._scanlines, (0, 0, 0, alpha_val), (0, y), (width, y))

    def trigger_shake(self, amount: float) -> None:
        """Add screen shake intensity."""
        self._shake_intensity = max(self._shake_intensity, amount)

    def trigger_aberration(self, duration: float, shift_px: int = 0) -> None:
        """Trigger brief chromatic aberration pulse."""
        self._aberration_timer = max(self._aberration_timer, duration)
        self._aberration_px = shift_px or config.CHROMATIC_ABERRATION_PX

    def update(self, dt: float, danger_level: float) -> None:
        """Update screen shake and aberration timers."""
        # Update shake decay
        if self._shake_intensity > 0.1:
            angle = self._rng.uniform(0, math.pi * 2)
            dist = self._shake_intensity
            self._shake_offset = (int(math.cos(angle) * dist), int(math.sin(angle) * dist))
            self._shake_intensity *= config.SCREEN_SHAKE_DECAY
            if self._shake_intensity < 0.1:
                self._shake_intensity = 0.0
                self._shake_offset = (0, 0)
        else:
            self._shake_offset = (0, 0)

        # Update chromatic aberration timer
        if self._aberration_timer > 0.0:
            self._aberration_timer -= dt
            if self._aberration_timer <= 0.0:
                self._aberration_px = 0
        elif danger_level > 0.6:
            # Persistent slight aberration when predator is right on top of you
            self._aberration_px = max(1, int(config.CHROMATIC_ABERRATION_PX * ((danger_level - 0.6) / 0.4)))
        else:
            self._aberration_px = 0

    @property
    def shake_offset(self) -> tuple[int, int]:
        return self._shake_offset

    def apply(self, surface) -> None:
        """Apply scanlines and chromatic aberration in-place on the final screen surface."""
        import pygame

        # 1. Apply Chromatic Aberration via fast numpy array slicing
        if self._aberration_px > 0:
            try:
                arr = pygame.surfarray.pixels3d(surface)
                shift = min(self._aberration_px, arr.shape[0] - 1)
                if shift > 0:
                    # Shift Red channel left/up
                    arr[:-shift, :, 0] = arr[shift:, :, 0]
                    # Shift Blue channel right/down
                    arr[shift:, :, 2] = arr[:-shift, :, 2]
                del arr  # Release pixel lock immediately
            except Exception:
                pass  # Fallback if locking fails

        # 2. Overlay Scanlines
        if self._scanlines:
            surface.blit(self._scanlines, (0, 0))
