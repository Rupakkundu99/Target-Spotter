"""Main game loop (Phase 2+ stub).

Fixed-tick loop that: drains ClapEvents from the InputSource, applies them to the
player (move / turn / capture), ticks prey and predator AI, then asks the
renderer and audio mixer to update. Phase 1 doesn't need this — the clap console
tool exercises the input pipeline directly — but the wiring is laid out so
Phase 2 slots straight in.
"""

from __future__ import annotations

import time

from blind_hunter import config
from blind_hunter.events import ClapEvent, Direction
from blind_hunter.game import noise as noise_mod
from blind_hunter.game.ai import predator as predator_ai
from blind_hunter.game.ai import prey as prey_ai
from blind_hunter.game.state import AIState, EntityKind, World, distance
from blind_hunter.input.base import InputSource


def _step_size(intensity: float) -> float:
    return config.STEP_MIN + (config.STEP_MAX - config.STEP_MIN) * intensity


def apply_clap(world: World, event: ClapEvent, now: float) -> None:
    """Move the player and register the noise the clap made."""
    player = world.player
    import math

    sound_type = getattr(event, "sound_type", "clap")

    # Determine movement step size and noise intensity based on sound type
    step_scale = 1.0
    noise_scale = 1.0
    should_move = True

    if sound_type == "ping":
        should_move = False
        noise_scale = config.PING_NOISE_SCALE
    elif sound_type == "snap":
        step_scale = config.SNAP_STEP_SCALE
        noise_scale = config.SNAP_NOISE_SCALE
    # "clap" uses step_scale=1.0 and noise_scale=1.0

    if should_move:
        heading = math.radians(player.facing)
        step = _step_size(event.intensity) * step_scale
        dx, dy = math.cos(heading) * step, math.sin(heading) * step
        player.position = (player.position[0] + dx, player.position[1] + dy)

    # Register the sound event for AI detection
    noise_mod.register_clap(world, event.intensity * noise_scale, now)

    # Double-clap near prey = capture attempt.
    if event.is_double:
        _attempt_capture(world)



def _attempt_capture(world: World) -> None:
    """Capture the nearest prey within CAPTURE_RANGE of the player, if any.

    A double-clap grabs at most one prey (the closest), removing it from the
    world and bumping the player's tally. Reaching the extraction point with the
    quota met is what actually wins — that's checked in `_check_end_conditions`.
    """
    player_pos = world.player.position
    in_range = [
        ent
        for ent in world.entities
        if ent.kind is EntityKind.PREY
        and distance(ent.position, player_pos) <= config.CAPTURE_RANGE
    ]
    if not in_range:
        return

    target = min(in_range, key=lambda e: distance(e.position, player_pos))
    world.entities.remove(target)
    world.player.prey_captured += 1


def update_world(world: World, now: float, dt: float) -> None:
    """Advance AI and end-conditions for one tick (input already applied)."""
    for ent in world.entities:
        if ent.kind is EntityKind.PREY:
            prey_ai.update(ent, world, now, dt)
        else:
            predator_ai.update(ent, world, now, dt)

    _check_end_conditions(world)


def tick(world: World, source: InputSource, now: float, dt: float) -> None:
    """Headless tick: drain input, then advance the world.

    The Pygame frontend (`blind_hunter.app`) drives input itself so it can fire
    a reveal per clap, and calls `update_world` directly.
    """
    for event in source.poll():
        apply_clap(world, event, now)
    update_world(world, now, dt)


def _check_end_conditions(world: World) -> None:
    if world.lost:
        return
    if world.player.prey_captured >= world.required_prey:
        if (
            distance(world.player.position, world.game_map.extraction)
            <= config.EXTRACTION_RANGE
        ):
            world.won = True


def run(world: World, source: InputSource) -> None:
    """Blocking fixed-tick loop. Renderer/mixer hookups land in Phase 2/3."""
    dt = 1.0 / config.TICK_RATE
    last = time.monotonic()
    while not (world.won or world.lost):
        now = time.monotonic()
        tick(world, source, now, now - last)
        last = now
        time.sleep(max(0.0, dt - (time.monotonic() - now)))
