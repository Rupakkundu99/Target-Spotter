"""Blind Hunter entry point.

Phase 1 is wired: `--mode claptest` runs the mic -> onset -> ClapEvent console
loop (same as `python -m tools.clap_test`). `--mode play` is the placeholder for
the full game loop, which comes online in Phase 2 once rendering exists.
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Blind Hunter")
    parser.add_argument(
        "--mode",
        choices=["claptest", "play"],
        default="claptest",
        help="claptest: Phase 1 clap-detection console. play: full game (Phase 2+).",
    )
    parser.add_argument("--level", default="level1", help="Level name to load.")
    args = parser.parse_args()

    if args.mode == "claptest":
        from tools.clap_test import main as claptest_main

        return claptest_main()

    # mode == play  (Phase 2: black screen, clap-to-move, radial reveal)
    from blind_hunter.app import GameApp
    from blind_hunter.loader import load_level

    world = load_level(args.level)
    print(f"Loaded '{args.level}': {len(world.entities)} entities.")

    # Try to attach the mic so real claps move the player. If it's unavailable
    # (no sounddevice / no mic), fall back to keyboard-only play — SPACE claps.
    source = None
    try:
        from blind_hunter.input.clap_source import ClapSource

        source = ClapSource()
        print("Microphone attached — clap to move.")
    except Exception as exc:
        print(f"Mic unavailable ({exc}). Keyboard-only: SPACE = clap.")

    print("Controls: arrows turn, SPACE clap, ESC quit.")
    GameApp(world, source).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
