"""Generate placeholder audio assets into assets/audio/.

Run once (or after tweaking `blind_hunter.audio.synth`):

    python -m tools.gen_assets

Writes mono 16-bit WAVs that the game loads at runtime. Replace any of these
files with real recordings later — same filenames, no code changes needed.
"""

from __future__ import annotations

import wave
from pathlib import Path

from blind_hunter import config
from blind_hunter.audio import synth

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"


def write_wav(path: Path, samples) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(config.SAMPLE_RATE)
        w.writeframes(samples.tobytes())


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for filename, generator in synth.GENERATORS.items():
        samples = generator()
        write_wav(ASSET_DIR / filename, samples)
        print(f"wrote {filename}  ({samples.size} samples)")
    print(f"done -> {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
