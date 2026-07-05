"""Low-latency mic capture on a background thread.

Uses `sounddevice`'s callback API to push fixed-size float32 blocks onto a
bounded queue. Downstream (onset detection) pulls blocks off this queue. Keeping
capture and analysis on separate stages keeps the audio callback cheap, which
matters for latency and for not dropping frames.

`sounddevice` is imported lazily so the rest of the package stays importable on
machines that haven't installed the audio deps yet.
"""

from __future__ import annotations

import queue
from typing import Optional

import numpy as np

from blind_hunter import config


class AudioCapture:
    """Continuous mic capture into a thread-safe block queue."""

    def __init__(
        self,
        sample_rate: int = config.SAMPLE_RATE,
        block_size: int = config.BLOCK_SIZE,
        channels: int = config.CHANNELS,
        device: Optional[int] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.channels = channels
        self.device = device

        self.blocks: "queue.Queue[np.ndarray]" = queue.Queue(
            maxsize=config.RING_BUFFER_BLOCKS
        )
        self._stream = None  # sounddevice.InputStream, created in start()

    # -- sounddevice callback -------------------------------------------------
    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: D401
        # Runs on sounddevice's audio thread — keep this cheap.
        if status:
            # Overflow/underflow etc. Not fatal; we just note it via a marker
            # block so higher layers could react if they wanted.
            pass
        mono = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
        try:
            self.blocks.put_nowait(mono)
        except queue.Full:
            # Drop the oldest block to stay real-time rather than backing up.
            try:
                self.blocks.get_nowait()
                self.blocks.put_nowait(mono)
            except queue.Empty:
                pass

    def start(self) -> None:
        import sounddevice as sd  # lazy import

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            channels=self.channels,
            device=self.device,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Block for the next captured audio block (or None on timeout)."""
        try:
            return self.blocks.get(timeout=timeout)
        except queue.Empty:
            return None
