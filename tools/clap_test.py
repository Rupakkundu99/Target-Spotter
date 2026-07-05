"""Phase 1 milestone: prove the mic -> onset -> ClapEvent pipeline works.

Run this, clap near your laptop, and watch it print detections:

    python -m tools.clap_test

    [calibrating ambient noise for 1.0s... done, floor=0.0021]
    listening — clap near the mic (Ctrl+C to quit)
    Clap detected: intensity=0.82  (double=False)
    Clap detected: intensity=0.44  (double=False)

This is the reliability foundation for everything else, so it exercises the real
ClapSource — the same code path the game will use.
"""

from __future__ import annotations

import sys
import time

from blind_hunter.input.clap_source import ClapSource


def main() -> int:
    try:
        source = ClapSource()
    except Exception as exc:  # pragma: no cover - construction is trivial
        print(f"Failed to build clap source: {exc}", file=sys.stderr)
        return 1

    print("[calibrating ambient noise... speak/clap NOT during this second]")
    try:
        source.start()
    except Exception as exc:
        print(
            f"Could not open the microphone: {exc}\n"
            "Is `sounddevice` installed and a mic available?",
            file=sys.stderr,
        )
        return 1

    print(f"[done, noise floor ~ {source.detector.noise_floor:.4f}]")
    print("listening — clap near the mic (Ctrl+C to quit)")

    try:
        while True:
            for event in source.poll():
                print(
                    f"Clap detected: intensity={event.intensity:.2f}  "
                    f"(double={event.is_double})"
                )
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        source.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
