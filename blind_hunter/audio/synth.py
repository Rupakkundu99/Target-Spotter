"""Procedural placeholder sounds (numpy → int16 mono).

These stand in for real audio assets so the game is audible immediately. They're
intentionally simple and *loop-seamless* where it matters: the looping ambient
uses a sin² envelope over one full cycle, so its amplitude is zero at both ends
and repeats without a click.

Both the asset generator (`tools/gen_assets.py`) and the runtime fallback in
`SpatialMixer` use these, so a missing .wav never crashes the game — you just get
the placeholder tone until a real asset is dropped in.
"""

from __future__ import annotations

import numpy as np

from blind_hunter import config

SR = config.SAMPLE_RATE


def _t(duration: float) -> np.ndarray:
    return np.linspace(0.0, duration, int(SR * duration), endpoint=False)


def to_int16(mono: np.ndarray, peak: float = 0.9) -> np.ndarray:
    """Normalize a float waveform to a peak and convert to int16."""
    m = np.max(np.abs(mono)) or 1.0
    return np.ascontiguousarray((mono / m * peak * 32767).astype(np.int16))


def _noise(n: int, seed: int) -> np.ndarray:
    # Deterministic noise (no global RNG — the workflow/runtime forbids it and
    # deterministic assets are nicer anyway).
    rng = np.random.RandomState(seed)
    return rng.uniform(-1.0, 1.0, n)


def prey_breath(duration: float = 2.4) -> np.ndarray:
    """Slow breathing swell with wheezing texture — loop-seamless."""
    t = _t(duration)
    env = np.sin(np.pi * t / duration) ** 2
    # Airy content: low sine + slightly raspy frequency modulation
    tone = 0.5 * np.sin(2 * np.pi * 190 * t + 0.3 * np.sin(2 * np.pi * 5 * t))
    wheeze = 0.2 * np.sin(2 * np.pi * 380 * t)
    breath = 0.4 * _smooth(_noise(t.size, 11), 220)
    return to_int16(env * (tone + wheeze + breath), peak=0.7)


def prey_startle(duration: float = 0.35) -> np.ndarray:
    """Short upward chirp for the alert state."""
    t = _t(duration)
    freq = np.linspace(400, 900, t.size)
    env = np.exp(-t * 9)
    return to_int16(env * np.sin(2 * np.pi * freq * t), peak=0.8)


def steps(duration: float = 0.5, thump_hz: float = 130.0) -> np.ndarray:
    """A couple of soft footfall thumps."""
    t = _t(duration)
    sig = np.zeros(t.size)
    for onset in (0.02, 0.28):
        idx = t >= onset
        local = t - onset
        sig += np.where(idx, np.exp(-local * 30) * np.sin(2 * np.pi * thump_hz * local), 0.0)
    return to_int16(sig, peak=0.7)


def predator_growl(duration: float = 2.0) -> np.ndarray:
    """Low, guttural menacing rumble with tremolo — loop-seamless."""
    t = _t(duration)
    env = np.sin(np.pi * t / duration) ** 2
    # Sub-bass + dissonant rumble with 5 Hz amplitude modulation (tremolo)
    tremolo = 0.7 + 0.3 * np.sin(2 * np.pi * 5.0 * t)
    rumble = np.sin(2 * np.pi * 55 * t) + 0.6 * np.sin(2 * np.pi * 83 * t) + 0.4 * np.sin(2 * np.pi * 110 * t)
    grit = 0.6 * _smooth(_noise(t.size, 7), 120)
    return to_int16(env * tremolo * (rumble + grit), peak=0.85)


def predator_alert(duration: float = 0.5) -> np.ndarray:
    """A menacing downward snarl."""
    t = _t(duration)
    freq = np.linspace(300, 90, t.size)
    env = np.exp(-t * 4)
    return to_int16(env * (np.sin(2 * np.pi * freq * t) + 0.3 * _noise(t.size, 3)), peak=0.9)


def heartbeat(duration: float = 0.5) -> np.ndarray:
    """A single 'lub-dub' pulse, retriggered per beat by the Heartbeat module."""
    t = _t(duration)
    sig = np.zeros(t.size)
    for onset, gain, hz in ((0.0, 1.0, 62.0), (0.16, 0.75, 55.0)):
        local = t - onset
        idx = t >= onset
        sig += np.where(idx, gain * np.exp(-local * 22) * np.sin(2 * np.pi * hz * local), 0.0)
    return to_int16(sig, peak=0.95)


def ambient_drone(duration: float = 6.0) -> np.ndarray:
    """Continuous low-volume dark atmospheric drone — loop-seamless."""
    t = _t(duration)
    env = np.sin(np.pi * t / duration) ** 2
    # Deep sub-bass rumble + eerie dissonant harmonics
    drone = 0.5 * np.sin(2 * np.pi * 55 * t) + 0.3 * np.sin(2 * np.pi * 82.5 * t) + 0.2 * np.sin(2 * np.pi * 110 * t)
    wind = 0.4 * _smooth(_noise(t.size, 42), 300)
    return to_int16(env * (drone + wind), peak=0.45)


def _smooth(x: np.ndarray, window: int) -> np.ndarray:
    """Cheap moving-average low-pass to take the edge off white noise."""
    if window <= 1:
        return x
    kernel = np.ones(window) / window
    return np.convolve(x, kernel, mode="same")


# Maps the AudioProfile filenames used in level JSON to a generator.
GENERATORS = {
    "prey_breath.wav": prey_breath,
    "prey_startle.wav": prey_startle,
    "prey_steps.wav": steps,
    "predator_growl.wav": predator_growl,
    "predator_alert.wav": predator_alert,
    "predator_steps.wav": lambda: steps(thump_hz=95.0),
    "heartbeat.wav": heartbeat,
    "ambient_drone.wav": ambient_drone,
}

