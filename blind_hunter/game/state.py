"""Core data model — Player, entities, and the map.

Mirrors section 6.2 of the design doc. These are plain dataclasses with no game
logic beyond trivial helpers; behavior lives in the AI modules and game loop.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field


Vec2 = tuple[float, float]


class EntityKind(enum.Enum):
    PREY = "prey"
    PREDATOR = "predator"


class AIState(enum.Enum):
    # Prey
    IDLE = "idle"
    ALERT = "alert"
    FLEE = "flee"
    # Predator
    PATROL = "patrol"
    INVESTIGATE = "investigate"
    CHASE = "chase"
    ATTACK = "attack"


@dataclass
class NoiseEvent:
    """A noise the player made — predators/prey are drawn to or spooked by it."""

    position: Vec2
    intensity: float
    timestamp: float


@dataclass
class Player:
    position: Vec2 = (0.0, 0.0)
    facing: float = 0.0  # degrees; 0 = +x, grows counter-clockwise
    noise_history: list[NoiseEvent] = field(default_factory=list)
    prey_captured: int = 0
    alive: bool = True


@dataclass
class AudioProfile:
    idle_sound: str = ""
    alert_sound: str = ""
    move_sound: str = ""


@dataclass
class Entity:
    id: str
    kind: EntityKind
    position: Vec2
    state: AIState
    hearing_radius: float = 8.0
    speed: float = 1.0
    audio: AudioProfile = field(default_factory=AudioProfile)

    # --- Phase 4 AI bookkeeping (mutated by the AI modules each tick) ---
    # Last noise/target position the entity is reacting to (prey flees from it,
    # predators investigate toward it). None when the entity has nothing to chase.
    last_heard: Vec2 | None = None
    # Current wander destination while patrolling (predator only).
    patrol_target: Vec2 | None = None
    # Monotonic time the entity entered its current state — drives dwell timers
    # (e.g. how long prey sits in ALERT before fleeing).
    state_since: float = 0.0


@dataclass
class GameMap:
    width: int
    height: int
    walls: list[Vec2] = field(default_factory=list)  # blocked grid cells
    player_start: Vec2 = (0.0, 0.0)
    extraction: Vec2 = (0.0, 0.0)
    prey_spawns: list[Vec2] = field(default_factory=list)
    predator_spawns: list[Vec2] = field(default_factory=list)

    def is_blocked(self, cell: Vec2) -> bool:
        return cell in self.walls


@dataclass
class World:
    """Everything the game loop mutates each tick."""

    player: Player
    entities: list[Entity]
    game_map: GameMap
    required_prey: int = 1
    won: bool = False
    lost: bool = False


def distance(a: Vec2, b: Vec2) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
