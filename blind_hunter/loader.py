"""Load a level JSON into the runtime `World` data model."""

from __future__ import annotations

import json
from pathlib import Path

from blind_hunter.game.state import (
    AIState,
    AudioProfile,
    Entity,
    EntityKind,
    GameMap,
    Player,
    World,
)

DATA_DIR = Path(__file__).parent / "data" / "maps"


def _audio_profile(cfg: dict) -> AudioProfile:
    a = cfg.get("audio", {})
    return AudioProfile(
        idle_sound=a.get("idle_sound", ""),
        alert_sound=a.get("alert_sound", ""),
        move_sound=a.get("move_sound", ""),
    )


def load_level(name: str = "level1") -> World:
    path = DATA_DIR / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    game_map = GameMap(
        width=data["width"],
        height=data["height"],
        walls=[tuple(w) for w in data.get("walls", [])],
        player_start=tuple(data["player_start"]),
        extraction=tuple(data["extraction"]),
        prey_spawns=[tuple(p) for p in data.get("prey_spawns", [])],
        predator_spawns=[tuple(p) for p in data.get("predator_spawns", [])],
    )

    ent_cfg = data.get("entities", {})
    prey_cfg = ent_cfg.get("prey", {})
    pred_cfg = ent_cfg.get("predator", {})

    entities: list[Entity] = []
    for i, pos in enumerate(game_map.prey_spawns):
        entities.append(
            Entity(
                id=f"prey-{i}",
                kind=EntityKind.PREY,
                position=pos,
                state=AIState.IDLE,
                hearing_radius=prey_cfg.get("hearing_radius", 8.0),
                speed=prey_cfg.get("speed", 1.0),
                audio=_audio_profile(prey_cfg),
            )
        )
    for i, pos in enumerate(game_map.predator_spawns):
        entities.append(
            Entity(
                id=f"predator-{i}",
                kind=EntityKind.PREDATOR,
                position=pos,
                state=AIState.PATROL,
                hearing_radius=pred_cfg.get("hearing_radius", 12.0),
                speed=pred_cfg.get("speed", 1.0),
                audio=_audio_profile(pred_cfg),
            )
        )

    return World(
        player=Player(position=game_map.player_start),
        entities=entities,
        game_map=game_map,
        required_prey=data.get("required_prey", 1),
    )
