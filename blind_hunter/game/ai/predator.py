"""Predator AI state machine (Phase 4): patrol -> investigate -> chase -> attack.

Priority each tick, highest first:

- **ATTACK**  — within ``ATTACK_RANGE`` of the player: the run ends.
- **CHASE**   — player within ``CHASE_RANGE``, or a loud noise erupts close by
                (``PREDATOR_CHASE_NOISE_*``): home straight in on the player.
- **INVESTIGATE** — a fainter/further noise is audible: move to its source.
- **PATROL**  — nothing to react to: wander the map. If it was mid-hunt, it
                first walks out its last known lead, then resumes wandering.

Movement is grid-pathfound (see ``ai/movement.py``) so the predator routes around
walls toward the player, a noise, or its patrol waypoint.
"""

from __future__ import annotations

import random

from blind_hunter import config
from blind_hunter.game import noise as noise_mod
from blind_hunter.game.ai import movement
from blind_hunter.game.state import AIState, Entity, World, distance

ATTACK_RANGE = 1.0
CHASE_RANGE = 5.0

# Wander destinations don't need to be reproducible run-to-run.
_rng = random.Random()


def update(entity: Entity, world: World, now: float, dt: float) -> None:
    player_pos = world.player.position
    to_player = distance(entity.position, player_pos)
    heard = noise_mod.loudest_heard(
        entity.position, world, now, entity.hearing_radius
    )

    # --- ATTACK: contact ends the run immediately. ---
    if to_player <= ATTACK_RANGE:
        entity.state = AIState.ATTACK
        world.lost = True
        world.player.alive = False
        return

    loud_and_close = (
        heard is not None
        and heard.intensity >= config.PREDATOR_CHASE_NOISE_INTENSITY
        and distance(entity.position, heard.position)
        <= config.PREDATOR_CHASE_NOISE_RANGE
    )

    # --- Decide state (transitions). ---
    if to_player <= CHASE_RANGE or loud_and_close:
        entity.state = AIState.CHASE
        entity.last_heard = player_pos  # keep pursuing where the player was
    elif heard is not None:
        entity.state = AIState.INVESTIGATE
        entity.last_heard = heard.position
    else:
        # No player nearby and the world's gone quiet. Finish walking out the
        # last lead, then drop back to patrol.
        if entity.state in (AIState.CHASE, AIState.INVESTIGATE) and (
            entity.last_heard is not None
        ):
            if distance(entity.position, entity.last_heard) <= config.AI_ARRIVE_DISTANCE:
                entity.last_heard = None
                entity.state = AIState.PATROL
            else:
                entity.state = AIState.INVESTIGATE
        else:
            entity.state = AIState.PATROL

    # --- Act (movement). ---
    game_map = world.game_map
    if entity.state == AIState.CHASE:
        movement.move_toward_cell(
            entity, game_map, movement.cell_of(player_pos), dt, entity.speed
        )
    elif entity.state == AIState.INVESTIGATE and entity.last_heard is not None:
        movement.move_toward_cell(
            entity, game_map, movement.cell_of(entity.last_heard), dt, entity.speed
        )
    else:
        _patrol(entity, world, dt)


def _patrol(entity: Entity, world: World, dt: float) -> None:
    """Wander toward a random waypoint, picking a fresh one on arrival."""
    game_map = world.game_map
    if entity.patrol_target is None or (
        distance(entity.position, entity.patrol_target) <= config.AI_ARRIVE_DISTANCE
    ):
        entity.patrol_target = movement.cell_center(
            movement.random_walkable_cell(game_map, _rng)
        )

    movement.move_toward_cell(
        entity,
        game_map,
        movement.cell_of(entity.patrol_target),
        dt,
        entity.speed * config.PREDATOR_PATROL_SPEED_FACTOR,
    )
