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
    parser.add_argument("--no-audio", action="store_true", help="Disable spatial audio and synth.")
    args = parser.parse_args()

    if args.mode == "claptest":
        from tools.clap_test import main as claptest_main

        return claptest_main()

    # mode == play  (Phase 2+: horror graphics, clap-to-move, radial reveal)
    from blind_hunter.app import GameApp
    from blind_hunter.loader import load_level

    # Try to attach the mic so real claps move the player. If it's unavailable
    # (no sounddevice / no mic), fall back to keyboard-only play — SPACE claps.
    source = None
    webcam_tracker = None
    try:
        # Try Option B (webcam + mic) for directional input
        resolver = None
        try:
            from blind_hunter import config as cfg
            if cfg.WEBCAM_ENABLED:
                from blind_hunter.input.webcam_tracker import WebcamTracker
                from blind_hunter.input.direction_resolver import WebcamHandResolver
                webcam_tracker = WebcamTracker()
                resolver = WebcamHandResolver(webcam_tracker)
                print("Webcam attached — point to aim, clap to move.")
        except Exception as exc:
            print(f"Webcam unavailable ({exc}). Arrow-key turning only.")

        from blind_hunter.input.clap_source import ClapSource

        source = ClapSource(resolver=resolver)
        print("Microphone attached — clap to move.")
    except Exception as exc:
        print(f"Mic unavailable ({exc}). Keyboard-only: SPACE = clap.")

    if webcam_tracker is not None:
        print("Controls: POINT to aim, CLAP to move, S snap, P ping, C capture, ESC quit.")
    else:
        print("Controls: arrows turn, SPACE clap, S snap, P ping, C capture, ESC quit.")

    levels = ["level1", "level2", "level3"] if args.level == "level1" else [args.level]
    for idx, lvl_name in enumerate(levels):
        world = load_level(lvl_name)
        print(f"\n==================================================")
        print(f"Loaded '{lvl_name}': {len(world.entities)} entities.")
        print(f"Mission: Extract {world.required_prey} prey and reach extraction point.")
        print(f"==================================================")
        
        app = GameApp(world, source=source, webcam_tracker=webcam_tracker, enable_audio=not args.no_audio, show_title=(idx == 0))
        app.run()
        
        if not world.won:
            print("\n[RUN FAILED] You were consumed by the darkness.")
            break
        
        print(f"\n[LEVEL COMPLETED] {lvl_name} cleared!")
        if idx < len(levels) - 1:
            print(f"Descending deeper into {levels[idx + 1]}...")
            
    return 0


if __name__ == "__main__":
    sys.exit(main())
