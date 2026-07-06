"""Entity Sprite System for Blind Hunter 2D Horror Upgrade (Phase 6A).

Replaces flat colored dots with atmospheric, procedural horror silhouettes and animations:
1. **Player**: Pulsing blue core with an orientation indicator and breathing aura.
2. **Prey**: Distorted, twitching amber shapes that cower and tremble when alert.
3. **Predator**: Large, menacing crimson silhouettes with glowing red eyes and a dark shadow aura.
"""

from __future__ import annotations

import math
import random

from blind_hunter import config
from blind_hunter.game.state import AIState, EntityKind


class EntityRenderer:
    def __init__(self) -> None:
        self._rng = random.Random()

    def draw_player(self, surface, player, screen_pos: tuple[int, int], radius: int, now: float, dim: bool = False) -> None:
        import pygame

        px, py = screen_pos
        base_color = config.PLAYER_DOT_DIM if dim else config.COLOR_PLAYER

        # Breathing pulse oscillation
        pulse = math.sin(now * math.pi * 2.0 * config.PLAYER_PULSE_FREQUENCY) * 0.2
        current_rad = max(3, int(radius * (1.0 + pulse)))

        # 1. Outer faint aura (if not dimmed)
        if not dim:
            aura_surf = pygame.Surface((current_rad * 4, current_rad * 4), pygame.SRCALPHA)
            aura_color = (*base_color[:3], 40)
            pygame.draw.circle(aura_surf, aura_color, (current_rad * 2, current_rad * 2), current_rad * 2)
            surface.blit(aura_surf, (px - current_rad * 2, py - current_rad * 2), special_flags=pygame.BLEND_ADD)

        # 2. Core silhouette
        pygame.draw.circle(surface, base_color, (px, py), current_rad)
        pygame.draw.circle(surface, (255, 255, 255), (px, py), max(1, current_rad // 3))

        # 3. Facing indicator (sharp pointer/triangle)
        heading = math.radians(player.facing)
        ex = px + math.cos(heading) * (current_rad * 2.5)
        ey = py + math.sin(heading) * (current_rad * 2.5)
        
        # Draw line and tip
        pygame.draw.line(surface, base_color, (px, py), (int(ex), int(ey)), max(2, current_rad // 3))
        pygame.draw.circle(surface, (200, 240, 255), (int(ex), int(ey)), max(2, current_rad // 4))

    def draw_entity(self, surface, entity, screen_pos: tuple[int, int], radius: int, now: float, player_pos: tuple[float, float] = (0, 0)) -> None:
        import pygame

        px, py = screen_pos

        if entity.kind is EntityKind.PREY:
            self._draw_prey(surface, entity, px, py, radius, now)
        else:
            self._draw_predator(surface, entity, px, py, radius, now, player_pos)

    def _draw_prey(self, surface, entity, px: int, py: int, radius: int, now: float) -> None:
        import pygame

        color = config.COLOR_PREY
        
        # Twitching animation: random jitter when in ALERT or FLEE state
        jx, jy = 0, 0
        if entity.state in (AIState.ALERT, AIState.FLEE):
            freq = config.PREY_TWITCH_FREQUENCY * (2.0 if entity.state == AIState.FLEE else 1.0)
            if math.sin(now * math.pi * 2.0 * freq) > 0.5:
                jx = self._rng.randint(-2, 2)
                jy = self._rng.randint(-2, 2)

        center = (px + jx, py + jy)

        # Draw hunched organic polygon shape
        pts = [
            (center[0], center[1] - radius),
            (center[0] + radius, center[1] - radius // 3),
            (center[0] + radius // 2, center[1] + radius),
            (center[0] - radius // 2, center[1] + radius),
            (center[0] - radius, center[1] - radius // 3),
        ]
        pygame.draw.polygon(surface, color, pts)
        
        # Outer amber warning glow if alert
        if entity.state != AIState.IDLE:
            pygame.draw.polygon(surface, (255, 220, 100), pts, 2)

    def _draw_predator(self, surface, entity, px: int, py: int, radius: int, now: float, player_pos: tuple[float, float]) -> None:
        import pygame

        color = config.COLOR_PREDATOR
        pred_rad = int(radius * 1.4)  # Predators are larger and more imposing

        # 1. Dark shadow/crimson aura
        aura_surf = pygame.Surface((pred_rad * 4, pred_rad * 4), pygame.SRCALPHA)
        pygame.draw.circle(aura_surf, (150, 20, 20, 60), (pred_rad * 2, pred_rad * 2), pred_rad * 2)
        surface.blit(aura_surf, (px - pred_rad * 2, py - pred_rad * 2), special_flags=pygame.BLEND_ADD)

        # 2. Jagged spiky body silhouette
        num_spikes = 8
        pts = []
        for i in range(num_spikes * 2):
            ang = (i / (num_spikes * 2)) * math.pi * 2.0
            # Alternate between outer spike and inner body
            r = pred_rad if i % 2 == 0 else int(pred_rad * 0.65)
            # Add breathing throb
            r += int(math.sin(now * 5.0 + i) * 2)
            pts.append((px + math.cos(ang) * r, py + math.sin(ang) * r))
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (80, 10, 10), pts, 2)

        # 3. Glowing Red Eyes (oriented toward player or last heard noise)
        dx = player_pos[0] - entity.position[0]
        dy = player_pos[1] - entity.position[1]
        dist = math.hypot(dx, dy)
        if dist > 1e-4:
            ex_dir, ey_dir = dx / dist, dy / dist
        else:
            ex_dir, ey_dir = 1.0, 0.0

        # Two eye dots offset from center
        perp_x, perp_y = -ey_dir, ex_dir
        eye_offset_fwd = pred_rad * 0.4
        eye_offset_side = pred_rad * 0.35
        
        eye1 = (
            int(px + ex_dir * eye_offset_fwd + perp_x * eye_offset_side),
            int(py + ey_dir * eye_offset_fwd + perp_y * eye_offset_side),
        )
        eye2 = (
            int(px + ex_dir * eye_offset_fwd - perp_x * eye_offset_side),
            int(py + ey_dir * eye_offset_fwd - perp_y * eye_offset_side),
        )

        eye_rad = max(2, config.PREDATOR_EYE_GLOW_RADIUS)
        pygame.draw.circle(surface, (255, 30, 30), eye1, eye_rad)
        pygame.draw.circle(surface, (255, 200, 200), eye1, max(1, eye_rad // 2))
        pygame.draw.circle(surface, (255, 30, 30), eye2, eye_rad)
        pygame.draw.circle(surface, (255, 200, 200), eye2, max(1, eye_rad // 2))
