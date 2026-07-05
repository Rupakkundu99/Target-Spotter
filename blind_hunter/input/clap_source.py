"""ClapSource — the assembled Option A input pipeline.

Runs a worker thread that: pulls audio blocks from `AudioCapture`, feeds them to
`OnsetDetector`, resolves a `Direction`, tags double-claps, and emits a
`ClapEvent` on the queue that `InputSource` exposes to the game loop.

This is the concrete Phase 1 input source. Swapping to Option B later means
handing in a `WebcamHandResolver` instead of the default — nothing else changes.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from pathlib import Path
import numpy as np

from blind_hunter import config
from blind_hunter.events import ClapEvent
from blind_hunter.input.audio_capture import AudioCapture
from blind_hunter.input.base import InputSource
from blind_hunter.input.direction_resolver import DirectionResolver, ForwardResolver
from blind_hunter.input.onset_detection import OnsetDetector


class ClapSource(InputSource):
    def __init__(
        self,
        capture: Optional[AudioCapture] = None,
        detector: Optional[OnsetDetector] = None,
        resolver: Optional[DirectionResolver] = None,
        device: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.capture = capture or AudioCapture(device=device)
        self.detector = detector or OnsetDetector()
        self.resolver = resolver or ForwardResolver()

        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._last_clap_time: float = -1.0

        # Maintain 1.0 second of rolling audio history
        self._history = np.zeros(config.SAMPLE_RATE, dtype=np.float32)

        # Load PyTorch model if trained weights exist
        self._model = None
        model_path = Path(__file__).resolve().parent.parent.parent / config.MODEL_PATH
        if model_path.exists():

            try:
                import torch
                from blind_hunter.audio.synth_model import get_torch_model
                self._model = get_torch_model()
                self._model.load_state_dict(torch.load(str(model_path), map_location="cpu"))
                self._model.eval()
                print(f"[clap_source] Sound classifier loaded from {model_path}")
            except Exception as exc:
                print(f"[clap_source] Failed to load classifier model: {exc}")
        else:
            print("[clap_source] Classifier model not found. Running in standard clap mode.")

    # -- lifecycle ------------------------------------------------------------
    def start(self) -> None:
        self.capture.start()
        self._calibrate()
        self._running.set()
        self._thread = threading.Thread(target=self._run, name="clap-source", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self.capture.stop()

    # -- internals ------------------------------------------------------------
    def _calibrate(self) -> None:
        """Sample ambient audio to seed the noise floor before we start firing."""
        deadline = time.monotonic() + config.CALIBRATION_SECONDS
        ambient = []
        while time.monotonic() < deadline:
            block = self.capture.read(timeout=0.5)
            if block is not None:
                ambient.append(block)
        self.detector.calibrate(ambient)

    def _run(self) -> None:
        while self._running.is_set():
            block = self.capture.read(timeout=0.25)
            if block is None:
                continue

            # Update rolling audio history buffer
            self._history = np.roll(self._history, -len(block))
            self._history[-len(block):] = block

            now = time.monotonic()
            onset = self.detector.process(block, now)
            if onset is None:
                continue

            # Collect the remaining tail blocks (450ms tail = 19 additional blocks)
            tail_blocks = []
            for _ in range(19):
                tb = self.capture.read(timeout=0.25)
                if tb is not None:
                    tail_blocks.append(tb)
                    self._history = np.roll(self._history, -len(tb))
                    self._history[-len(tb):] = tb

            # Reconstruct 0.5s segment centered at onset block
            # Since we added 19 tail blocks, the onset block is 20 blocks from the end
            onset_idx = len(self._history) - 20 * config.BLOCK_SIZE
            pre_samples = int(config.SAMPLE_RATE * 0.05)  # 50ms pre-onset
            start_idx = max(0, onset_idx - pre_samples)
            segment = self._history[start_idx:start_idx + int(config.SAMPLE_RATE * 0.5)]

            # Classify sound type
            sound_type = "clap"
            if self._model is not None:
                try:
                    import torch
                    from blind_hunter.audio.synth_model import compute_spectrogram
                    spectrogram = compute_spectrogram(segment)  # Shape (129, 56)
                    inp = torch.tensor(spectrogram, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
                    with torch.no_grad():
                        out = self._model(inp)
                        pred = out.argmax(dim=1).item()
                        
                        # Classes: ["background", "clap", "snap", "ping"]
                        if pred == 1:
                            sound_type = "clap"
                        elif pred == 2:
                            sound_type = "snap"
                        elif pred == 3:
                            sound_type = "ping"
                        else:
                            sound_type = "background"
                except Exception as exc:
                    print(f"[clap_source] Classification error: {exc}")

            # Ignore false triggers (background noise)
            if sound_type == "background":
                print("[clap_source] Filtered background noise false-trigger.")
                continue

            print(f"[clap_source] Classified: {sound_type} (intensity={onset.intensity:.2f})")

            is_double = (
                self._last_clap_time >= 0
                and (now - self._last_clap_time) <= config.DOUBLE_CLAP_WINDOW
            )
            self._last_clap_time = now

            self.emit(
                ClapEvent(
                    intensity=onset.intensity,
                    direction=self.resolver.resolve(),
                    timestamp=now,
                    is_double=is_double,
                    sound_type=sound_type,
                )
            )

