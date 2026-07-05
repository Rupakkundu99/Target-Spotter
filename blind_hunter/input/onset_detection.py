"""Clap / onset detection from raw audio blocks.

Algorithm (deliberately ML-free, per the design doc):

1. Compute RMS energy of each incoming block.
2. Maintain an adaptive noise floor as an exponential moving average of *quiet*
   blocks (blocks that didn't trigger), so the detector self-tunes to the room.
3. Fire an onset when a block's RMS exceeds `max(floor * TRIGGER_FACTOR,
   MIN_TRIGGER_RMS)` — i.e. a sharp spike above ambient.
4. Enforce a refractory window so one clap's decay tail doesn't retrigger.
5. Normalize the peak RMS into a 0..1 intensity.

The `calibrate()` helper samples ambient audio at startup to seed the floor,
which noticeably cuts false positives in echoey rooms.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from blind_hunter import config


def rms(block: np.ndarray) -> float:
    """Root-mean-square energy of an audio block."""
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))


@dataclass
class Onset:
    """A detected clap onset."""

    intensity: float   # normalized 0..1
    peak_rms: float    # raw RMS that triggered it
    monotonic_time: float


class OnsetDetector:
    """Stateful, streaming clap detector. Feed it blocks; it returns Onsets."""

    def __init__(self) -> None:
        self.noise_floor: float = config.MIN_TRIGGER_RMS
        self._refractory_until: float = 0.0

    def calibrate(self, ambient_blocks) -> float:
        """Seed the noise floor from a sequence of ambient (quiet) blocks."""
        energies = [rms(b) for b in ambient_blocks if b is not None]
        if energies:
            # Use the mean ambient energy as the initial floor.
            self.noise_floor = max(float(np.mean(energies)), 1e-6)
        return self.noise_floor

    def _intensity(self, peak_rms: float) -> float:
        """Map raw RMS to 0..1, softened with a sqrt curve for perceptual feel."""
        norm = peak_rms / config.INTENSITY_REFERENCE_RMS
        return float(min(1.0, math.sqrt(max(0.0, norm))))

    def process(self, block: np.ndarray, now: float):
        """Process one block. Returns an Onset if a clap fired, else None."""
        energy = rms(block)
        trigger_level = max(
            self.noise_floor * config.TRIGGER_FACTOR, config.MIN_TRIGGER_RMS
        )

        if now < self._refractory_until:
            # Still inside a previous clap's debounce window — don't retrigger,
            # and don't let the loud tail poison the noise floor.
            return None

        if energy >= trigger_level:
            self._refractory_until = now + config.REFRACTORY_SECONDS
            return Onset(
                intensity=self._intensity(energy),
                peak_rms=energy,
                monotonic_time=now,
            )

        # Quiet block — fold it into the adaptive floor.
        a = config.NOISE_FLOOR_ALPHA
        self.noise_floor = a * self.noise_floor + (1.0 - a) * energy
        return None
