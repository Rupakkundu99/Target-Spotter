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
        # Uniform scale so the map isn't distorted; fit the tighter axis.
        self.scale = min(usable_w / game_map.width, usable_h / game_map.height)
        # Center the map in the window.
        self.offset_x = (width - game_map.width * self.scale) / 2
        self.offset_y = (height - game_map.height * self.scale) / 2

    def to_screen(self, world_pos) -> tuple[int, int]:
        x, y = world_pos
        return (
            int(self.offset_x + x * self.scale),
            int(self.offset_y + y * self.scale),
        )

    def cell_size(self) -> int:
        """Pixel size of one world grid cell (for drawing walls/floor)."""
        return max(1, int(round(self.scale)))
