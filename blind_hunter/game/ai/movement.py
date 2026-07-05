"""Grid movement & pathfinding shared by prey and predator AI (Phase 4).

Entity positions are continuous ``(x, y)`` world coordinates; the map's collision
data is a set of blocked integer grid cells (``GameMap.walls``). This module
bridges the two:

- Cell helpers convert between continuous positions and grid cells.
- ``find_path`` runs a 4-connected breadth-first search over walkable cells,
  giving the shortest cell path between two points (empty if unreachable).
- ``move_toward_cell`` steers an entity one tick's worth of movement along that
  path, and ``move_toward_point`` handles the low-level step with wall sliding so
  an entity brushing a wall slides along it instead of sticking.

BFS is cheap on the small grids this game uses (a 32x32 map is ~1k cells) and is
recomputed each tick, so entities react immediately as the player and noises
move — no stale cached paths.
"""

from __future__ import annotations

import math
import random
from collections import deque

from blind_hunter.game.state import GameMap, Vec2

_EPS = 1e-6


def cell_of(pos: Vec2) -> tuple[int, int]:
    """Grid cell containing a continuous world position."""
    return (int(math.floor(pos[0])), int(math.floor(pos[1])))


def cell_center(cell: tuple[int, int]) -> Vec2:
    """Center point of a grid cell — entities aim for cell centers."""
    return (cell[0] + 0.5, cell[1] + 0.5)


def in_bounds(game_map: GameMap, cell: tuple[int, int]) -> bool:
    x, y = cell
    return 0 <= x < game_map.width and 0 <= y < game_map.height


def is_walkable(game_map: GameMap, cell: tuple[int, int]) -> bool:
    return in_bounds(game_map, cell) and not game_map.is_blocked(cell)


def _neighbors(game_map: GameMap, cell: tuple[int, int]):
    x, y = cell
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (x + dx, y + dy)
        if is_walkable(game_map, n):
            yield n


def find_path(
    game_map: GameMap, start: tuple[int, int], goal: tuple[int, int]
) -> list[tuple[int, int]]:
    """Shortest 4-connected walkable cell path from ``start`` to ``goal``.

    Returns a list beginning at ``start`` and ending at ``goal`` (inclusive), or
    an empty list if ``goal`` is unreachable. If ``start == goal`` the path is
    just ``[start]``.
    """
    if start == goal:
        return [start]
    if not is_walkable(game_map, goal):
        return []

    frontier: deque[tuple[int, int]] = deque([start])
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}

    while frontier:
        current = frontier.popleft()
        if current == goal:
            break
        for nxt in _neighbors(game_map, current):
            if nxt not in came_from:
                came_from[nxt] = current
                frontier.append(nxt)

    if goal not in came_from:
        return []

    path: list[tuple[int, int]] = []
    node: tuple[int, int] | None = goal
    while node is not None:
        path.append(node)
        node = came_from[node]
    path.reverse()
    return path


def _try_step(game_map: GameMap, pos: Vec2, dx: float, dy: float) -> Vec2:
    """Move by (dx, dy), sliding along a wall if the diagonal is blocked."""
    direct = (pos[0] + dx, pos[1] + dy)
    if is_walkable(game_map, cell_of(direct)):
        return direct
    # Slide: keep whichever single axis stays walkable.
    slide_x = (pos[0] + dx, pos[1])
    if dx and is_walkable(game_map, cell_of(slide_x)):
        return slide_x
    slide_y = (pos[0], pos[1] + dy)
    if dy and is_walkable(game_map, cell_of(slide_y)):
        return slide_y
    return pos  # boxed in — hold position


def move_toward_point(
    entity, game_map: GameMap, target: Vec2, dt: float, speed: float
) -> None:
    """Advance ``entity`` up to ``speed * dt`` units toward ``target``."""
    px, py = entity.position
    dx, dy = target[0] - px, target[1] - py
    dist = math.hypot(dx, dy)
    if dist < _EPS:
        return
    step = min(speed * dt, dist)
    entity.position = _try_step(game_map, entity.position, dx / dist * step, dy / dist * step)


def move_toward_cell(
    entity, game_map: GameMap, goal_cell: tuple[int, int], dt: float, speed: float
) -> None:
    """Pathfind toward ``goal_cell`` and take one tick's step along the route."""
    start = cell_of(entity.position)
    if start == goal_cell:
        move_toward_point(entity, game_map, cell_center(goal_cell), dt, speed)
        return

    path = find_path(game_map, start, goal_cell)
    if len(path) >= 2:
        # Head for the next waypoint's center; BFS guarantees it's walkable.
        move_toward_point(entity, game_map, cell_center(path[1]), dt, speed)
    else:
        # Unreachable (e.g. walled-off) — steer directly and let sliding cope.
        move_toward_point(entity, game_map, cell_center(goal_cell), dt, speed)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def flee_from(
    entity, game_map: GameMap, danger: Vec2, dt: float, speed: float, lookahead: float
) -> None:
    """Pathfind away from ``danger``, respecting walls.

    Projects an escape target ``lookahead`` units directly away from the danger,
    clamps it inside the map, then pathfinds to that cell — so a fleeing entity
    routes around obstacles rather than backing into a corner.
    """
    px, py = entity.position
    dx, dy = px - danger[0], py - danger[1]
    dist = math.hypot(dx, dy)
    if dist < _EPS:
        dx, dy, dist = 1.0, 0.0, 1.0  # danger is on top of us — pick a direction

    tx = _clamp(px + dx / dist * lookahead, 0.5, game_map.width - 0.5)
    ty = _clamp(py + dy / dist * lookahead, 0.5, game_map.height - 0.5)
    move_toward_cell(entity, game_map, cell_of((tx, ty)), dt, speed)


def random_walkable_cell(game_map: GameMap, rng: random.Random) -> tuple[int, int]:
    """A random unblocked cell — used to pick patrol destinations."""
    for _ in range(32):
        cell = (rng.randrange(game_map.width), rng.randrange(game_map.height))
        if is_walkable(game_map, cell):
            return cell
    # Degenerate fallback: scan for any walkable cell.
    for x in range(game_map.width):
        for y in range(game_map.height):
            if is_walkable(game_map, (x, y)):
                return (x, y)
    return (0, 0)
