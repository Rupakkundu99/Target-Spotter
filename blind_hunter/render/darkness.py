"""Living darkness rendering system (Phase 6A).

Instead of a flat black screen, darkness in Blind Hunter is an active, unsettling
presence. This module provides:

1. **Film Grain**: Pre-generated noise frames cycled each tick to give the dark
   areas texture and movement without per-frame CPU penalties.
2. **Dynamic Vignette**: A dark radial gradient border whose opacity and pulsation
   sync with predator proximity / heartbeat tension.
3. **Micro-Flickers**: Random subtle brightness flashes or shadow dips when danger
   is near, simulating sensory hallucinations or failing light.
4. **Corruption Borders**: Dark creeping shadow vignettes that encroach on the screen
   edges during high-threat moments.
"""

from __future__ import annotations

import math
import random
import numpy as np

from blind_hunter import config


class DarknessSystem:
    def __init__(self) -> None:
        self._width = 0
        self._height = 0
        self._grain_frames: list = []
        self._grain_idx = 0
        self._vignette_base = None
        self._corruption_base = None
        self._flicker_timer = 0.0
        self._flicker_alpha = 0.0
        self._rng = random.Random()

    def init(self, width: int, height: int) -> None:
        import pygame

        self._width = width
        self._height = height

        # 1. Pre-render 16 noise frames for film grain
        self._grain_frames = []
        for _ in range(16):
            noise = np.random.uniform(0, 255 * config.FILM_GRAIN_INTENSITY, (width, height)).astype(np.uint8)
            # Make it 3-channel grayscale
            rgb = np.dstack([noise, noise, noise])
            rgb = np.ascontiguousarray(rgb)
            surf = pygame.Surface((width, height))
            pygame.surfarray.blit_array(surf, rgb)
            self._grain_frames.append(surf)

        # 2. Build radial vignette base
        self._vignette_base = self._build_radial_vignette(width, height)
        
        # 3. Build corruption border base (jagged/organic edge darkening)
        self._corruption_base = self._build_corruption_border(width, height)

    def _build_radial_vignette(self, width: int, height: int):
        import pygame

        xx, yy = np.ogrid[:width, :height]
        cx, cy = width / 2.0, height / 2.0
        max_dist = math.hypot(cx, cy)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        
        # Smoothstep falloff from center to edges
        norm_dist = np.clip(dist / (max_dist * 0.85), 0.0, 1.0)
        alpha = (norm_dist ** 2.0) * 255.0 * config.VIGNETTE_STRENGTH
        alpha = np.clip(alpha, 0, 255).astype(np.uint8)

        # Create black SRCALPHA surface and write alpha channel directly
        # (blit_array only supports RGB, not RGBA)
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        alpha_px = pygame.surfarray.pixels_alpha(surf)
        alpha_px[:] = alpha
        del alpha_px  # release pixel lock
        return surf

    def _build_corruption_border(self, width: int, height: int):
        import pygame

        xx, yy = np.ogrid[:width, :height]
        cx, cy = width / 2.0, height / 2.0
        max_dist = math.hypot(cx, cy)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

        # Add sinusoidal/noise-like ripple to the distance for jagged tendril edges
        angle = np.arctan2(yy - cy, xx - cx)
        ripple = np.sin(angle * 8.0) * 0.08 + np.cos(angle * 13.0) * 0.05
        norm_dist = np.clip((dist / (max_dist * 0.75)) + ripple, 0.0, 1.0)
        
        alpha = (np.maximum(0.0, norm_dist - 0.4) / 0.6) ** 1.5 * 255.0
        alpha = np.clip(alpha, 0, 255).astype(np.uint8)

        # Create black SRCALPHA surface and write alpha channel directly
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        alpha_px = pygame.surfarray.pixels_alpha(surf)
        alpha_px[:] = alpha
        del alpha_px  # release pixel lock
        return surf

    def update(self, dt: float, danger_level: float) -> None:
        """Update grain animation and micro-flicker states.
        
        Args:
            dt: time delta in seconds.
            danger_level: 0.0 (safe) to 1.0 (predator adjacent/attacking).
        """
        # Cycle grain frame
        if self._grain_frames:
            self._grain_idx = (self._grain_idx + 1) % len(self._grain_frames)

        # Micro-flicker logic: more frequent when danger is high
        self._flicker_timer -= dt
        if self._flicker_timer <= 0.0:
            if danger_level > 0.2 and self._rng.random() < (danger_level * 0.4):
                # Trigger a brief flicker
                self._flicker_alpha = self._rng.uniform(0.1, 0.35) * danger_level
                self._flicker_timer = self._rng.uniform(0.05, 0.15)
            else:
                self._flicker_alpha = 0.0
                self._flicker_timer = self._rng.uniform(0.2, 0.8)
        else:
            # Decay flicker
            self._flicker_alpha = max(0.0, self._flicker_alpha - dt * 3.0)

    def apply(self, surface, danger_level: float, now: float) -> None:
        """Composite darkness layers onto the target screen surface."""
        import pygame

        if not self._grain_frames:
            return

        # 1. Add film grain (BLEND_ADD adds subtle texture to both dark and lit areas)
        grain_surf = self._grain_frames[self._grain_idx]
        surface.blit(grain_surf, (0, 0), special_flags=pygame.BLEND_ADD)

        # 2. Add Vignette (pulsing slightly with heart rate/danger)
        if self._vignette_base:
            pulse = math.sin(now * (2.0 + danger_level * 6.0)) * 0.15 * danger_level
            scale_alpha = max(0.2, min(1.0, 0.8 + pulse))
            
            # If danger is high or pulsing, we can adjust opacity via set_alpha
            self._vignette_base.set_alpha(int(255 * scale_alpha))
            surface.blit(self._vignette_base, (0, 0))

        # 3. Add Corruption tendrils when under high threat (> 0.4 danger)
        if self._corruption_base and danger_level > 0.3:
            corr_alpha = int(min(1.0, (danger_level - 0.3) / 0.7) * 220)
            self._corruption_base.set_alpha(corr_alpha)
            surface.blit(self._corruption_base, (0, 0))

        # 4. Micro-flickers (darkening or brightening pulse)
        if self._flicker_alpha > 0.01:
            flicker_val = int(self._flicker_alpha * 255)
            flicker_surf = pygame.Surface((self._width, self._height))
            flicker_surf.fill((flicker_val, flicker_val, flicker_val))
            # Randomly subtract or add light for unsettling sensory glitch
            mode = pygame.BLEND_SUB if int(now * 100) % 2 == 0 else pygame.BLEND_ADD
            surface.blit(flicker_surf, (0, 0), special_flags=mode)
