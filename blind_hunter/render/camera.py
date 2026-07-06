"""World <-> screen coordinate transform.

The world is measured in grid units (e.g. a 32x32 map); the window is in pixels.
The camera fits the whole map inside the window with a uniform scale and centers
it, so movement and reveals line up regardless of window size.

Note on axes: screen y grows downward while world y grows "up" in the data
model. We keep the mapping direct (world y -> screen y) for MVP simplicity —
top-down navigation reads fine either way, and facing angles stay internally
consistent because both the facing indicator and movement use the same frame.
"""

from __future__ import annotations

from blind_hunter import config
from blind_hunter.game.state import GameMap


class Camera:
    def __init__(self, game_map: GameMap, width: int, height: int) -> None:
        self.width = width
        self.height = height
        margin = config.VIEWPORT_MARGIN
        usable_w = max(1, width - 2 * margin)
        usable_h = max(1, height - 2 * margin)
        # Base scale to fit the whole map; apply horror zoom multiplier
        self.base_scale = min(usable_w / game_map.width, usable_h / game_map.height)
        self.zoom = getattr(config, "CAMERA_ZOOM", 1.8)
        self.scale = self.base_scale * self.zoom
        
        # Smooth tracking state
        self.curr_x, self.curr_y = game_map.player_start
        self.shake_offset = (0, 0)

    def update(self, player_pos: tuple[float, float], dt: float, shake_offset: tuple[int, int] = (0, 0)) -> None:
        """Smoothly track player position and apply screen-shake offset."""
        target_x, target_y = player_pos
        lerp = getattr(config, "CAMERA_LERP_SPEED", 0.12)
        # Frame-rate independent exponential lerp approximation
        factor = 1.0 - (1.0 - lerp) ** (dt * 60.0)
        self.curr_x += (target_x - self.curr_x) * factor
        self.curr_y += (target_y - self.curr_y) * factor
        self.shake_offset = shake_offset

    def to_screen(self, world_pos: tuple[float, float]) -> tuple[int, int]:
        x, y = world_pos
        # Center curr_x, curr_y in the window and apply shake
        sx = self.width / 2.0 + (x - self.curr_x) * self.scale + self.shake_offset[0]
        sy = self.height / 2.0 + (y - self.curr_y) * self.scale + self.shake_offset[1]
        return int(sx), int(sy)

    def cell_size(self) -> int:
        """Pixel size of one world grid cell (for drawing walls/floor)."""
        return max(1, int(round(self.scale)))

