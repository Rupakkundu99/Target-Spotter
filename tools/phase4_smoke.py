"""Headless Phase 4 smoke test — no pygame/mixer, pure game logic.

Exercises: noise decay, prey idle->alert->flee + flee movement, predator
patrol->investigate->chase->attack, double-clap capture, and the extraction win.
Run: python tools/phase4_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blind_hunter import config
from blind_hunter.events import ClapEvent, Direction
from blind_hunter.game import loop as game_loop
from blind_hunter.game import noise as noise_mod
from blind_hunter.game.ai import movement
from blind_hunter.game.state import (
    AIState,
    AudioProfile,
    Entity,
    EntityKind,
    GameMap,
    Player,
    World,
    distance,
)

failures: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        failures.append(name)


def make_world(walls=None, prey=None, predator=None, player=(16.0, 16.0)):
    gm = GameMap(
        width=32,
        height=32,
        walls=[tuple(w) for w in (walls or [])],
        player_start=player,
        extraction=(2.0, 2.0),
    )
    ents = []
    for i, p in enumerate(prey or []):
        ents.append(
            Entity(f"prey-{i}", EntityKind.PREY, p, AIState.IDLE, hearing_radius=8.0, speed=1.2)
        )
    for i, p in enumerate(predator or []):
        ents.append(
            Entity(
                f"pred-{i}", EntityKind.PREDATOR, p, AIState.PATROL,
                hearing_radius=12.0, speed=3.0,
            )
        )
    return World(player=Player(position=player), entities=ents, game_map=gm, required_prey=1)


# ---------------------------------------------------------------------------
print("noise decay:")
w = make_world()
noise_mod.register_clap(w, 1.0, now=0.0)
check("full intensity at t=0", abs(noise_mod.decayed_intensity(w.player.noise_history[0], 0.0) - 1.0) < 1e-9)
mid = noise_mod.decayed_intensity(w.player.noise_history[0], noise_mod.NOISE_DECAY_SECONDS / 2)
check("~half intensity at half life", 0.4 < mid < 0.6)
check("still active before decay window", len(noise_mod.active_noises(w, noise_mod.NOISE_DECAY_SECONDS - 0.1)) == 1)
check("pruned after decay window", len(noise_mod.active_noises(w, noise_mod.NOISE_DECAY_SECONDS + 0.1)) == 0)

# ---------------------------------------------------------------------------
print("prey idle -> alert -> flee + movement:")
w = make_world(prey=[(16.0, 20.0)])
prey = w.entities[0]
# Player claps right next to prey (well inside 8u hearing radius).
noise_mod.register_clap(w, 0.9, now=0.0)
t = 0.0
seen = set()
start_pos = prey.position
for _ in range(120):  # ~2s at 60fps
    t += 1 / 60
    # keep the noise fresh so the prey commits to fleeing
    if not w.player.noise_history:
        noise_mod.register_clap(w, 0.9, now=t)
    game_loop.update_world(w, now=t, dt=1 / 60)
    seen.add(prey.state)
check("entered ALERT at some point", AIState.ALERT in seen)
check("entered FLEE", AIState.FLEE in seen)
moved = distance(prey.position, start_pos)
check("prey moved while fleeing", moved > 1.0)
check("prey fled AWAY from noise (dist to player grew)",
      distance(prey.position, w.player.position) > distance(start_pos, w.player.position))

print("prey calms to IDLE once noise decays:")
w2 = make_world(prey=[(16.0, 20.0)])
prey2 = w2.entities[0]
noise_mod.register_clap(w2, 0.9, now=0.0)
game_loop.update_world(w2, now=0.5, dt=1 / 60)  # hears it
# Let all noise decay, then tick again.
game_loop.update_world(w2, now=noise_mod.NOISE_DECAY_SECONDS + 1.0, dt=1 / 60)
check("prey back to IDLE after silence", prey2.state == AIState.IDLE)

# ---------------------------------------------------------------------------
print("predator patrol -> chase -> attack:")
# Predator two cells from the player -> inside CHASE_RANGE.
w = make_world(predator=[(20.0, 16.0)])
pred = w.entities[0]
attacked = False
t = 0.0
for _ in range(600):  # up to 10s
    t += 1 / 60
    game_loop.update_world(w, now=t, dt=1 / 60)
    if w.lost:
        attacked = True
        break
check("predator entered CHASE and closed in", pred.state in (AIState.CHASE, AIState.ATTACK))
check("attack triggered game-over (world.lost)", attacked and w.lost)
check("player marked not alive", not w.player.alive)

print("predator investigates a distant noise:")
# Predator far from player but a noise is planted within hearing range.
w = make_world(predator=[(28.0, 28.0)], player=(4.0, 4.0))
pred = w.entities[0]
# Plant a noise ~10u away from predator (within 12u hearing, beyond 5u chase),
# low intensity so it's investigate-not-chase.
w.player.noise_history.append(
    __import__("blind_hunter.game.state", fromlist=["NoiseEvent"]).NoiseEvent(
        position=(22.0, 22.0), intensity=0.3, timestamp=0.0
    )
)
start = pred.position
saw_investigate = False
t = 0.0
for _ in range(60):
    t += 1 / 60
    if not w.player.noise_history:
        w.player.noise_history.append(
            __import__("blind_hunter.game.state", fromlist=["NoiseEvent"]).NoiseEvent(
                position=(22.0, 22.0), intensity=0.3, timestamp=t
            )
        )
    game_loop.update_world(w, now=t, dt=1 / 60)
    if pred.state == AIState.INVESTIGATE:
        saw_investigate = True
check("predator entered INVESTIGATE", saw_investigate)
check("predator moved toward the noise", distance(pred.position, (22.0, 22.0)) < distance(start, (22.0, 22.0)))

print("predator patrols when nothing to react to:")
w = make_world(predator=[(28.0, 28.0)], player=(2.0, 2.0))
pred = w.entities[0]
start = pred.position
t = 0.0
for _ in range(120):
    t += 1 / 60
    game_loop.update_world(w, now=t, dt=1 / 60)
check("predator is PATROLLING", pred.state == AIState.PATROL)
check("predator wandered from spawn", distance(pred.position, start) > 0.5)

# ---------------------------------------------------------------------------
print("double-clap capture + extraction win:")
w = make_world(prey=[(16.5, 16.0)])  # prey within capture range of player
dbl = ClapEvent(intensity=0.9, direction=Direction.FORWARD, is_double=True)
game_loop.apply_clap(w, dbl, now=0.0)
check("prey removed from world", all(e.kind is not EntityKind.PREY for e in w.entities))
check("prey_captured incremented", w.player.prey_captured == 1)
game_loop.update_world(w, now=0.1, dt=1 / 60)
check("not won before reaching extraction", not w.won)
# Teleport player onto extraction and tick end-conditions.
w.player.position = w.game_map.extraction
game_loop.update_world(w, now=0.2, dt=1 / 60)
check("won after reaching extraction with quota met", w.won)

print("capture requires proximity:")
w = make_world(prey=[(25.0, 25.0)])  # far away
game_loop.apply_clap(w, dbl, now=0.0)
check("far prey NOT captured", w.player.prey_captured == 0)

# ---------------------------------------------------------------------------
print("pathfinding routes around a wall:")
# Vertical wall segment between start (1,5) and goal (9,5), with a gap at y!=5.
wall = [(5, y) for y in range(0, 5)]  # blocks y=0..4 at x=5; gap at y>=5
gm = GameMap(width=10, height=10, walls=[tuple(c) for c in wall])
path = movement.find_path(gm, (1, 2), (9, 2))
check("path found around wall", len(path) > 0 and path[0] == (1, 2) and path[-1] == (9, 2))
check("path avoids blocked cells", all(not gm.is_blocked(c) for c in path))

# ---------------------------------------------------------------------------
print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: all checks passed")
