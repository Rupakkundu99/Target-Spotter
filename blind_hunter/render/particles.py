"""Particle System for Blind Hunter 2D Horror Upgrade (Phase 6A).

Provides lightweight atmospheric and environmental particle effects:
1. **Dust Motes**: Slow-drifting particles in world/screen space that catch the light during reveals.
2. **Blood Bursts**: Crimson particle explosions triggered on prey capture or predator attacks.
3. **Predator Trails**: Dark shadow motes that shed from moving predators.
4. **Footprint Traces**: Fading marks left behind by the player's movement, anchoring exploration.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from blind_hunter import config


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    lifetime: float
    max_lifetime: float
    color: tuple[int, int, int]
    size: float
    kind: str  # "dust", "blood", "trail", "footprint"
    facing_deg: float = 0.0


class ParticleSystem:
    def __init__(self) -> None:
        self._particles: list[Particle] = []
        self._rng = random.Random()
        self._last_footprint_pos = (0.0, 0.0)

    def update(self, dt: float, width: int, height: int) -> None:
        """Update particle physics and cull expired particles."""
        alive: list[Particle] = []
        for p in self._particles:
            p.lifetime -= dt
            if p.lifetime <= 0.0:
                continue
            
            # Apply velocity
            p.x += p.vx * dt
            p.y += p.vy * dt
            
            # Add slight drag/buoyancy to dust
            if p.kind == "dust":
                p.vx += self._rng.uniform(-2.0, 2.0) * dt
                p.vy += self._rng.uniform(-2.0, 2.0) * dt
            elif p.kind == "blood":
                p.vx *= 0.92
                p.vy *= 0.92
            
            alive.append(p)

        # Spawn ambient dust motes randomly
        if len(alive) < config.MAX_PARTICLES and self._rng.random() < config.DUST_SPAWN_RATE:
            # Spawn in a generous area around the screen or world
            alive.append(
                Particle(
                    x=self._rng.uniform(0, 32),  # Map coords roughly 0..32
                    y=self._rng.uniform(0, 32),
                    vx=self._rng.uniform(-0.3, 0.3),
                    vy=self._rng.uniform(-0.3, 0.3),
                    lifetime=self._rng.uniform(4.0, 10.0),
                    max_lifetime=10.0,
                    color=(180, 190, 210),
                    size=self._rng.uniform(1.0, 2.5),
                    kind="dust",
                )
            )

        self._particles = alive

    def emit_blood_burst(self, world_pos: tuple[float, float], count: int = 25) -> None:
        """Spawn a burst of blood particles at world_pos."""
        wx, wy = world_pos
        for _ in range(count):
            ang = self._rng.uniform(0, math.pi * 2.0)
            spd = self._rng.uniform(1.5, 6.0)
            self._particles.append(
                Particle(
                    x=wx,
                    y=wy,
                    vx=math.cos(ang) * spd,
                    vy=math.sin(ang) * spd,
                    lifetime=self._rng.uniform(0.5, 2.5),
                    max_lifetime=2.5,
                    color=(200, 20, 30) if self._rng.random() > 0.3 else (120, 10, 15),
                    size=self._rng.uniform(2.0, 4.5),
                    kind="blood",
                )
            )

    def emit_predator_trail(self, world_pos: tuple[float, float]) -> None:
        """Spawn dark shadow trail particles behind a predator."""
        wx, wy = world_pos
        for _ in range(self._rng.randint(1, 3)):
            self._particles.append(
                Particle(
                    x=wx + self._rng.uniform(-0.3, 0.3),
                    y=wy + self._rng.uniform(-0.3, 0.3),
                    vx=self._rng.uniform(-0.2, 0.2),
                    vy=self._rng.uniform(-0.2, 0.2),
                    lifetime=self._rng.uniform(0.4, 1.2),
                    max_lifetime=1.2,
                    color=(30, 5, 10),
                    size=self._rng.uniform(3.0, 6.0),
                    kind="trail",
                )
            )

    def check_emit_footprint(self, world_pos: tuple[float, float], facing_deg: float) -> None:
        """Spawn a footprint trace if the player has moved enough distance."""
        dist = math.hypot(world_pos[0] - self._last_footprint_pos[0], world_pos[1] - self._last_footprint_pos[1])
        if dist >= 0.7:
            self._last_footprint_pos = world_pos
            self._particles.append(
                Particle(
                    x=world_pos[0],
                    y=world_pos[1],
                    vx=0.0,
                    vy=0.0,
                    lifetime=config.FOOTPRINT_FADE_SECONDS,
                    max_lifetime=config.FOOTPRINT_FADE_SECONDS,
                    color=(50, 80, 110),
                    size=2.5,
                    kind="footprint",
                    facing_deg=facing_deg,
                )
            )

    def draw(self, surface, camera) -> None:
        """Draw all active particles onto the scene surface."""
        import pygame

        for p in self._particles:
            alpha_ratio = max(0.0, min(1.0, p.lifetime / p.max_lifetime))
            sx, sy = camera.to_screen((p.x, p.y))

            if p.kind == "footprint":
                # Draw oriented footprint mark
                color = (*p.color, int(150 * alpha_ratio))
                rad = max(2, int(p.size * (camera.scale / 25.0)))
                pygame.draw.circle(surface, p.color, (sx, sy), rad)
            elif p.kind == "trail":
                # Dark shadow puff
                rad = max(3, int(p.size * (camera.scale / 20.0) * alpha_ratio))
                pygame.draw.circle(surface, p.color, (sx, sy), rad)
            elif p.kind == "blood":
                rad = max(1, int(p.size * (camera.scale / 25.0)))
                pygame.draw.circle(surface, p.color, (sx, sy), rad)
            elif p.kind == "dust":
                # Faint floating mote
                rad = max(1, int(p.size))
                pygame.draw.circle(surface, p.color, (sx, sy), rad)
