"""Radial echolocation reveal renderer (Phase 2).

The screen sits near-black. Each clap adds a `Reveal`: a radial "flashlight"
centered on the player whose radius scales with clap intensity and whose
brightness fades to nothing over REVEAL_FADE_SECONDS.

Compositing works in two layers:

1. **Scene** — the world (floor grid, walls, extraction, entities) drawn at full
   brightness onto an off-screen surface.
2. **Light mask** — a black surface onto which each active reveal adds a white
   radial gradient (dimmed by its current fade alpha).

`scene * mask` (BLEND_MULT) leaves the world visible only where light exists and
black everywhere else — so you only ever see flashes of terrain around you.

A single max-radius gradient sprite is precomputed with numpy and scaled per
reveal, which keeps per-frame cost low even with several overlapping flashes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from blind_hunter import config
from blind_hunter.game.state import EntityKind
from blind_hunter.render.camera import Camera


@dataclass
class Reveal:
    """A single active reveal flash."""

    world_center: tuple[float, float] # world-space center
    radius: float                     # base pixels at zoom=1.0
    started_at: float
    sound_type: str = "clap"
    facing_deg: float = 0.0

    def alpha(self, now: float) -> float:
        """0..1 brightness; fades linearly to 0 over the primary fade window."""
        elapsed = now - self.started_at
        if elapsed >= config.REVEAL_FADE_SECONDS:
            return 0.0
        return 1.0 - (elapsed / config.REVEAL_FADE_SECONDS)

    def ghost_alpha(self, now: float) -> float:
        """0..1 brightness for the lingering afterimage ghost."""
        elapsed = now - self.started_at
        max_dur = config.REVEAL_FADE_SECONDS * getattr(config, "AFTERIMAGE_DURATION_MULT", 2.5)
        if elapsed >= max_dur:
            return 0.0
        return (1.0 - (elapsed / max_dur)) * 0.28


def radius_for_intensity(intensity: float) -> float:
    return config.REVEAL_RADIUS_MIN + (
        config.REVEAL_RADIUS_MAX - config.REVEAL_RADIUS_MIN
    ) * intensity


def _build_gradient_sprite(radius: int):
    """White-center → black-edge radial gradient with jagged organic edges."""
    import pygame

    d = radius * 2
    xx, yy = np.ogrid[:d, :d]
    cx, cy = radius, radius
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    
    # Add angular noise / ripple to distance for organic jagged edges
    angle = np.arctan2(yy - cy, xx - cx)
    ripple = np.sin(angle * 11.0) * (radius * 0.06) + np.cos(angle * 17.0) * (radius * 0.04)
    dist_rippled = np.maximum(0.0, dist + ripple)
    
    val = np.clip(1.0 - dist_rippled / radius, 0.0, 1.0) ** config.REVEAL_FALLOFF_POWER
    arr = (val * 255).astype(np.uint8)
    rgb = np.ascontiguousarray(np.dstack([arr, arr, arr]))
    surf = pygame.Surface((d, d))
    pygame.surfarray.blit_array(surf, rgb)
    return surf


class RevealRenderer:
    """Owns the window and composites scene + light mask each frame."""

    def __init__(self) -> None:
        self._reveals: list[Reveal] = []
        self._screen = None
        self._scene = None
        self._mask = None
        self._gradient = None
        self.camera: Camera | None = None
        self._font = None

    def init(self, width: int, height: int, camera: Camera) -> None:
        import pygame

        pygame.init()
        self._screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Blind Hunter")
        self._scene = pygame.Surface((width, height))
        self._mask = pygame.Surface((width, height))
        self._gradient = _build_gradient_sprite(int(config.REVEAL_RADIUS_MAX))
        self.camera = camera
        self._font = pygame.font.SysFont("consolas", 16)

    # -- reveals --------------------------------------------------------------
    def add_reveal(self, world_center, intensity: float, now: float, sound_type: str = "clap", facing_deg: float = 0.0) -> None:
        assert self.camera is not None
        
        # Scale reveal radius based on the type of sound
        radius = radius_for_intensity(intensity)
        if sound_type == "snap":
            radius *= config.SNAP_REVEAL_RADIUS_SCALE
        elif sound_type == "ping":
            radius *= config.PING_REVEAL_RADIUS_SCALE

        self._reveals.append(
            Reveal(
                world_center=world_center,
                radius=radius,
                started_at=now,
                sound_type=sound_type,
                facing_deg=facing_deg,
            )
        )

    # -- scene ----------------------------------------------------------------
    def _draw_scene(self, world) -> None:
        import pygame

        cam = self.camera
        assert cam is not None and self._scene is not None
        scene = self._scene
        scene.fill(config.COLOR_BACKGROUND)

        cell = cam.cell_size()

        if config.DRAW_FLOOR_GRID:
            gm = world.game_map
            for gx in range(gm.width + 1):
                x0, y0 = cam.to_screen((gx, 0))
                _, y1 = cam.to_screen((gx, gm.height))
                pygame.draw.line(scene, config.COLOR_FLOOR_GRID, (x0, y0), (x0, y1))
            for gy in range(gm.height + 1):
                x0, y0 = cam.to_screen((0, gy))
                x1, _ = cam.to_screen((gm.width, gy))
                pygame.draw.line(scene, config.COLOR_FLOOR_GRID, (x0, y0), (x1, y0))

        for wall in world.game_map.walls:
            sx, sy = cam.to_screen(wall)
            pygame.draw.rect(scene, config.COLOR_WALL, (sx, sy, cell, cell))

        ex, ey = cam.to_screen(world.game_map.extraction)
        pygame.draw.rect(
            scene, config.COLOR_EXTRACTION, (ex - cell // 2, ey - cell // 2, cell, cell)
        )

        for ent in world.entities:
            color = (
                config.COLOR_PREY
                if ent.kind is EntityKind.PREY
                else config.COLOR_PREDATOR
            )
            pygame.draw.circle(scene, color, cam.to_screen(ent.position), max(4, cell // 3))

        self._draw_player(scene, world, dim=False)

    def _draw_player(self, surface, world, dim: bool) -> None:
        import pygame

        cam = self.camera
        assert cam is not None
        px, py = cam.to_screen(world.player.position)
        color = config.PLAYER_DOT_DIM if dim else config.COLOR_PLAYER
        pygame.draw.circle(surface, color, (px, py), config.PLAYER_RADIUS_PX)
        # Facing indicator.
        heading = math.radians(world.player.facing)
        ex = px + math.cos(heading) * config.FACING_INDICATOR_PX
        ey = py + math.sin(heading) * config.FACING_INDICATOR_PX
        pygame.draw.line(surface, color, (px, py), (int(ex), int(ey)), 2)

    # -- light mask -----------------------------------------------------------
    def _build_mask(self, now: float) -> None:
        import pygame

        mask = self._mask
        assert mask is not None and self.camera is not None
        mask.fill((config.AMBIENT_LIGHT,) * 3)

        alive: list[Reveal] = []
        zoom_mult = getattr(self.camera, "zoom", 1.0)

        for r in self._reveals:
            ghost_a = r.ghost_alpha(now)
            if ghost_a <= 0.0:
                continue
            alive.append(r)
            
            screen_center = self.camera.to_screen(r.world_center)
            rad = max(1, int(r.radius * zoom_mult))
            sprite = pygame.transform.smoothscale(self._gradient, (rad * 2, rad * 2))
            
            # Apply directional cone if this is a "ping" (whistle / tongue click)
            if r.sound_type == "ping":
                cone_mask = pygame.Surface((rad * 2, rad * 2))
                half_angle = config.PING_CONE_ANGLE / 2.0
                heading_rad = math.radians(r.facing_deg)
                
                num_pts = 12
                pts = [(rad, rad)]
                for i in range(num_pts + 1):
                    ang = heading_rad + math.radians(-half_angle + i * (2.0 * half_angle / num_pts))
                    dist = rad * 1.5
                    px = rad + math.cos(ang) * dist
                    py = rad + math.sin(ang) * dist
                    pts.append((px, py))
                
                pygame.draw.polygon(cone_mask, (255, 255, 255), pts)
                sprite.blit(cone_mask, (0, 0), special_flags=pygame.BLEND_MULT)

            primary_a = r.alpha(now)
            if primary_a > 0.0:
                # Primary reveal: cold white-blue warming to amber/orange as it fades
                dim_r = int(255 * primary_a)
                dim_g = int((180 * primary_a + 75) * primary_a)
                dim_b = int((100 * primary_a + 30) * primary_a)
                primary_sprite = sprite.copy()
                primary_sprite.fill((dim_r, dim_g, dim_b), special_flags=pygame.BLEND_MULT)
                mask.blit(
                    primary_sprite,
                    (screen_center[0] - rad, screen_center[1] - rad),
                    special_flags=pygame.BLEND_ADD,
                )
            elif ghost_a > 0.0:
                # Afterimage ghost: faint eerie greenish/cyan tint
                dim_r = int(80 * ghost_a)
                dim_g = int(150 * ghost_a)
                dim_b = int(130 * ghost_a)
                sprite.fill((dim_r, dim_g, dim_b), special_flags=pygame.BLEND_MULT)
                mask.blit(
                    sprite,
                    (screen_center[0] - rad, screen_center[1] - rad),
                    special_flags=pygame.BLEND_ADD,
                )

        self._reveals = alive

    # -- frame ----------------------------------------------------------------
    def draw(self, world, now: float, hud: str = "") -> None:
        import pygame

        assert self._screen is not None and self._scene is not None
        self._draw_scene(world)
        self._build_mask(now)

        frame = self._scene.copy()
        frame.blit(self._mask, (0, 0), special_flags=pygame.BLEND_MULT)

        # Keep the player locatable even in full darkness (orientation aid).
        if config.PLAYER_DOT_ALWAYS_ON:
            self._draw_player(frame, world, dim=True)

        self._screen.blit(frame, (0, 0))
        if hud and self._font is not None:
            self._screen.blit(self._font.render(hud, True, (110, 120, 140)), (10, 10))
        pygame.display.flip()

    def shutdown(self) -> None:
        import pygame

        pygame.quit()
