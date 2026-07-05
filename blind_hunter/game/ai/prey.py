"""Prey AI state machine (Phase 4): idle -> alert -> flee.

Prey stand still and quiet until the player's noise reaches them. On first
hearing a noise they snap to ALERT; if the noise persists past a short dwell they
break into a FLEE, pathfinding *away* from the noise source while respecting
walls. When the world falls quiet again (noise events decay — see
``game/noise.py``) they settle back to IDLE so they don't flee forever.
"""

from __future__ import annotations

from blind_hunter import config
from blind_hunter.game import noise as noise_mod
from blind_hunter.game.ai import movement
from blind_hunter.game.state import AIState, Entity, World


def update(entity: Entity, world: World, now: float, dt: float) -> None:
    heard = noise_mod.loudest_heard(
        entity.position, world, now, entity.hearing_radius
    )

    if heard is not None:
        # Remember where the scare came from so we can flee directly away.
        entity.last_heard = heard.position
        if entity.state == AIState.IDLE:
            entity.state = AIState.ALERT
            entity.state_since = now
        elif entity.state == AIState.ALERT:
            # Linger in ALERT briefly, then bolt.
            if (now - entity.state_since) >= config.PREY_ALERT_TO_FLEE_SECONDS:
                entity.state = AIState.FLEE
                entity.state_since = now
        # Already FLEEing: stay fleeing while the noise is still audible.
    else:
        # Nothing heard for a while — calm down and stop running.
        if entity.state in (AIState.ALERT, AIState.FLEE):
            entity.state = AIState.IDLE
            entity.state_since = now
        entity.last_heard = None

    if entity.state == AIState.FLEE and entity.last_heard is not None:
        movement.flee_from(
            entity,
            world.game_map,
            entity.last_heard,
            dt,
            entity.speed,
            config.PREY_FLEE_LOOKAHEAD,
        )
