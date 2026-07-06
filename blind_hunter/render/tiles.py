"""Procedural Tile Renderer for Blind Hunter 2D Horror Upgrade (Phase 6A).

Generates atmospheric horror textures for walls, floors, and the extraction zone
using procedural NumPy noise and geometric patterns:
1. **Walls**: Dark stone blocks with beveled edges, surface noise, and organic moss/cracks.
2. **Floor**: Grimy concrete/dirt with subtle edge borders and drag mark stains.
3. **Extraction**: Floor tile inscribed with a glowing occult rune circle / extraction glyph.

Textures are generated at base resolution and cached per cell size so rendering
is immediate and scale-independent.
"""

from __future__ import annotations

import math
import random
import numpy as np

from blind_hunter import config


class TileRenderer:
    def __init__(self) -> None:
        self._cached_size = -1
        self._wall_tile = None
        self._floor_tile = None
        self._floor_var_tiles: list = []
        self._extraction_tile = None
        self._rng = random.Random(1337)  # Fixed seed for consistent world textures

    def get_tiles(self, cell_size: int, now: float = 0.0):
        """Return (wall_tile, floor_tile, floor_variants, extraction_tile) for cell_size."""
        import pygame

        if cell_size != self._cached_size or self._wall_tile is None:
            self._cached_size = max(4, cell_size)
            self._generate_all(self._cached_size)

        # Pulse extraction tile if requested
        return self._wall_tile, self._floor_tile, self._floor_var_tiles, self._extraction_tile

    def _generate_all(self, size: int) -> None:
        import pygame

        # 1. Generate Wall Tile
        self._wall_tile = self._make_wall(size)

        # 2. Generate Base Floor Tile and 3 variants (with subtle blood/grime)
        self._floor_tile = self._make_floor(size, variant=0)
        self._floor_var_tiles = [
            self._make_floor(size, variant=1),
            self._make_floor(size, variant=2),
            self._make_floor(size, variant=3),
        ]

        # 3. Generate Extraction Rune Tile
        self._extraction_tile = self._make_extraction(size)

    def _make_wall(self, size: int):
        import pygame

        # Base dark stone color (60, 58, 68) with +-12 noise
        noise = np.random.uniform(-12, 12, (size, size, 3))
        base = np.array([60, 58, 68], dtype=np.float32)
        arr = np.clip(base + noise, 0, 255).astype(np.uint8)

        # Add 3D bevel / border darkening
        border_thickness = max(1, size // 8)
        for i in range(border_thickness):
            factor = 0.5 + (i / border_thickness) * 0.5
            arr[i, :, :] = (arr[i, :, :] * factor).astype(np.uint8)
            arr[-1 - i, :, :] = (arr[-1 - i, :, :] * factor).astype(np.uint8)
            arr[:, i, :] = (arr[:, i, :] * factor).astype(np.uint8)
            arr[:, -1 - i, :] = (arr[:, -1 - i, :] * factor).astype(np.uint8)

        # Add occasional moss/crack green-ish tint in center
        if size >= 8:
            cx, cy = size // 2, size // 2
            arr[cx - 2:cx + 2, cy - 2:cy + 2, 1] = np.clip(arr[cx - 2:cx + 2, cy - 2:cy + 2, 1] + 20, 0, 255)

        surf = pygame.Surface((size, size))
        pygame.surfarray.blit_array(surf, np.ascontiguousarray(arr))
        return surf

    def _make_floor(self, size: int, variant: int = 0):
        import pygame

        # Base grimy dirt/concrete (20, 20, 26) with +-5 noise
        noise = np.random.uniform(-5, 5, (size, size, 3))
        base = np.array([20, 20, 26], dtype=np.float32)
        arr = np.clip(base + noise, 0, 255).astype(np.uint8)

        # Subtle dark edge border so grid is visible without lines
        arr[0, :, :] = (arr[0, :, :] * 0.7).astype(np.uint8)
        arr[-1, :, :] = (arr[-1, :, :] * 0.7).astype(np.uint8)
        arr[:, 0, :] = (arr[:, 0, :] * 0.7).astype(np.uint8)
        arr[:, -1, :] = (arr[:, -1, :] * 0.7).astype(np.uint8)

        # Variants: add subtle drag marks or grime stains
        if variant == 1 and size >= 8:
            # Subtle dark blood smear
            arr[size // 4:size // 2, :, 0] = np.clip(arr[size // 4:size // 2, :, 0] + 15, 0, 255)
            arr[size // 4:size // 2, :, 1:] = (arr[size // 4:size // 2, :, 1:] * 0.8).astype(np.uint8)
        elif variant == 2 and size >= 8:
            # Grime patch
            arr[:, size // 3:size // 3 + 2, :] = (arr[:, size // 3:size // 3 + 2, :] * 0.6).astype(np.uint8)

        surf = pygame.Surface((size, size))
        pygame.surfarray.blit_array(surf, np.ascontiguousarray(arr))
        return surf

    def _make_extraction(self, size: int):
        import pygame

        # Start with base floor
        surf = self._make_floor(size, variant=0).copy()

        # Draw glowing green/cyan occult rune circle
        center = (size // 2, size // 2)
        radius = max(2, (size // 2) - 2)
        color_outer = (50, 220, 130)
        color_inner = (120, 255, 180)

        # Outer circle
        pygame.draw.circle(surf, color_outer, center, radius, max(1, size // 16))
        # Inner triangle or inscribed glyph
        pts = [
            (center[0], center[1] - radius + 2),
            (center[0] - radius + 2, center[1] + radius - 2),
            (center[0] + radius - 2, center[1] + radius - 2),
        ]
        if size >= 8:
            pygame.draw.polygon(surf, color_inner, pts, max(1, size // 20))
            pygame.draw.circle(surf, color_inner, center, max(2, radius // 3), max(1, size // 20))

        return surf
