"""Master Horror Renderer for Blind Hunter 2D Horror Upgrade (Phase 6A).

Orchestrates all atmospheric rendering layers and post-processing effects:
1. **Darkness Layer**: Film grain, dynamic vignette, micro-flickers, corruption borders.
2. **Scene Layer**: Procedural tilemap (walls, floor, extraction rune).
3. **Entity Layer**: Animated horror silhouettes for player, prey, and predators.
4. **Particle Layer**: Footprint traces, blood bursts, predator shadow trails, floating dust motes.
5. **Light Mask**: Jagged organic echolocation reveals with color temperature and ghost afterimages.
6. **Post-Processing**: Screen-shake, chromatic aberration, CRT scanlines.
"""

from __future__ import annotations

import math
import random
import time
from typing import Optional

from blind_hunter import config
from blind_hunter.game.state import EntityKind, World, distance
from blind_hunter.render.camera import Camera
from blind_hunter.render.darkness import DarknessSystem
from blind_hunter.render.entities import EntityRenderer
from blind_hunter.render.particles import ParticleSystem
from blind_hunter.render.postfx import PostFX
from blind_hunter.render.reveal import Reveal, _build_gradient_sprite, radius_for_intensity


class HorrorRenderer:
    def __init__(self) -> None:
        self._reveals: list[Reveal] = []
        self._screen = None
        self._scene = None
        self._mask = None
        self._gradient = None
        self.camera: Camera | None = None
        self._font = None

        # Subsystems
        self.darkness = DarknessSystem()
        self.tiles = __import__("blind_hunter.render.tiles", fromlist=["TileRenderer"]).TileRenderer()
        self.entities = EntityRenderer()
        self.particles = ParticleSystem()
        self.postfx = PostFX()

        self._last_time = time.monotonic()
        self._last_prey_count = 0

    def init(self, width: int, height: int, camera: Camera) -> None:
        import pygame

        pygame.init()
        self._screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Blind Hunter — Horror Edition")
        self._scene = pygame.Surface((width, height))
        self._mask = pygame.Surface((width, height))
        self._gradient = _build_gradient_sprite(int(config.REVEAL_RADIUS_MAX))
        self.camera = camera
        self._font = pygame.font.SysFont("consolas", 16)

        # Initialize subsystems
        self.darkness.init(width, height)
        self.postfx.init(width, height)

    def add_reveal(self, world_center: tuple[float, float], intensity: float, now: float, sound_type: str = "clap", facing_deg: float = 0.0) -> None:
        assert self.camera is not None

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

        # Trigger atmospheric reactions on clap
        shake_amt = config.SCREEN_SHAKE_CLAP * (0.5 if sound_type == "snap" else 1.0)
        self.postfx.trigger_shake(shake_amt)
        self.postfx.trigger_aberration(0.15)

    def _compute_danger_level(self, world: World) -> float:
        player_pos = world.player.position
        min_dist = 999.0
        for ent in world.entities:
            if ent.kind is EntityKind.PREDATOR:
                d = distance(player_pos, ent.position)
                if d < min_dist:
                    min_dist = d
        
        # Danger ramps up from 15 world units down to 0
        if min_dist >= 15.0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - (min_dist / 15.0)))

    def _draw_scene_layer(self, world: World, now: float) -> None:
        import pygame

        cam = self.camera
        assert cam is not None and self._scene is not None
        scene = self._scene
        scene.fill(config.COLOR_BACKGROUND)

        cell = cam.cell_size()
        wall_tile, floor_tile, floor_vars, extraction_tile = self.tiles.get_tiles(cell, now)

        gm = world.game_map
        
        # Draw Floor and Walls in visible camera bounds
        # Calculate grid range visible on screen
        min_gx = max(0, int(cam.curr_x - (cam.width / 2.0) / cam.scale) - 2)
        max_gx = min(gm.width, int(cam.curr_x + (cam.width / 2.0) / cam.scale) + 2)
        min_gy = max(0, int(cam.curr_y - (cam.height / 2.0) / cam.scale) - 2)
        max_gy = min(gm.height, int(cam.curr_y + (cam.height / 2.0) / cam.scale) + 2)

        for gx in range(min_gx, max_gx):
            for gy in range(min_gy, max_gy):
                sx, sy = cam.to_screen((gx, gy))
                if gm.is_blocked((gx, gy)):
                    scene.blit(wall_tile, (sx, sy))
                elif (gx, gy) == gm.extraction:
                    scene.blit(extraction_tile, (sx, sy))
                else:
                    # Pick floor variant deterministically based on coordinates
                    var_idx = (gx * 7 + gy * 13) % (len(floor_vars) + 1)
                    if var_idx == 0:
                        scene.blit(floor_tile, (sx, sy))
                    else:
                        scene.blit(floor_vars[var_idx - 1], (sx, sy))

        # Draw World Particles (footprints, blood, shadow trails)
        self.particles.draw(scene, cam)

        # Draw Entities
        for ent in world.entities:
            # Emit shadow trails for predators
            if ent.kind is EntityKind.PREDATOR and random.random() < 0.3:
                self.particles.emit_predator_trail(ent.position)
            
            screen_pos = cam.to_screen(ent.position)
            rad = max(4, cell // 3)
            self.entities.draw_entity(scene, ent, screen_pos, rad, now, player_pos=world.player.position)

        # Draw Player
        px, py = cam.to_screen(world.player.position)
        self.entities.draw_player(scene, world.player, (px, py), max(5, cell // 3), now, dim=False)

    def _build_light_mask(self, now: float) -> None:
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

    def draw(self, world: World, now: float, hud: str = "") -> None:
        import pygame

        assert self._screen is not None and self._scene is not None and self.camera is not None

        dt = now - self._last_time
        self._last_time = now
        if dt > 0.5:
            dt = 1.0 / 60.0

        # Check for prey capture blood burst
        if world.player.prey_captured > self._last_prey_count:
            self.particles.emit_blood_burst(world.player.position, count=35)
            self.postfx.trigger_shake(8.0)
            self._last_prey_count = world.player.prey_captured

        # Check game over / attack
        if world.lost:
            self.postfx.trigger_shake(config.SCREEN_SHAKE_ATTACK)
            self.postfx.trigger_aberration(0.5, shift_px=8)

        # 1. Update Subsystems
        danger_level = self._compute_danger_level(world)
        self.camera.update(world.player.position, dt, self.postfx.shake_offset)
        self.darkness.update(dt, danger_level)
        self.postfx.update(dt, danger_level)
        self.particles.update(dt, self.camera.width, self.camera.height)
        self.particles.check_emit_footprint(world.player.position, world.player.facing)

        # 2. Render Scene & Mask
        self._draw_scene_layer(world, now)
        self._build_light_mask(now)

        # 3. Composite Scene * Mask
        frame = self._scene.copy()
        frame.blit(self._mask, (0, 0), special_flags=pygame.BLEND_MULT)

        # 4. Always draw dimmed player marker if enabled
        if config.PLAYER_DOT_ALWAYS_ON:
            px, py = self.camera.to_screen(world.player.position)
            self.entities.draw_player(frame, world.player, (px, py), max(5, self.camera.cell_size() // 3), now, dim=True)

        # 5. Apply Living Darkness & Post-FX
        self.darkness.apply(frame, danger_level, now)
        self.postfx.apply(frame)

        # 6. Present to Screen
        self._screen.blit(frame, (0, 0))
        if hud and self._font is not None:
            hud_surf = self._font.render(hud, True, (140, 30, 40) if danger_level > 0.5 else (110, 120, 140))
            self._screen.blit(hud_surf, (10, 10))
        pygame.display.flip()

    def shutdown(self) -> None:
        import pygame

        pygame.quit()
