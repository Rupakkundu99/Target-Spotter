"""Webcam hand-tracking thread for directional input (Phase 5 / Option B).

Runs a background thread that captures frames from the webcam, detects
hand landmarks via MediaPipe Hands, and computes a pointing direction
from the index finger vector.  The game loop reads ``latest_direction``
at clap time through the ``WebcamHandResolver``.

Direction mapping (relative):
  - Pointing UP in the frame   → FORWARD (keep current facing)
  - Pointing LEFT in the frame → LEFT   (turn left relative to facing)
  - Pointing RIGHT in frame    → RIGHT  (turn right relative to facing)
  - Pointing DOWN in frame     → BACK   (turn 180° from facing)

The frame is **mirrored** (selfie view) so that pointing your real left
hand to YOUR left registers as LEFT in-game.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Optional

from blind_hunter import config
from blind_hunter.events import Direction


class WebcamTracker:
    """Background thread that tracks the player's pointing direction via webcam.

    Attributes:
        latest_direction: The most recently detected pointing direction.
                          Thread-safe — written by the capture thread,
                          read by the game thread at clap time.
        running: Whether the capture loop is active.
    """

    def __init__(self, device: Optional[int] = None) -> None:
        self._device = device if device is not None else config.WEBCAM_DEVICE_INDEX
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._direction = Direction.FORWARD
        self._hand_detected = False
        self._last_detect_time = 0.0

    # -- public API -----------------------------------------------------------

    @property
    def latest_direction(self) -> Direction:
        """Return the last detected pointing direction (thread-safe read)."""
        with self._lock:
            # Fall back to FORWARD if hand was lost for more than 0.8 seconds.
            # This prevents holding the last-pointing direction forever (e.g. BACK).
            if not self._hand_detected and (time.monotonic() - self._last_detect_time > 0.8):
                return Direction.FORWARD
            return self._direction

    @property
    def hand_detected(self) -> bool:
        """True if a hand is currently being tracked."""
        with self._lock:
            return self._hand_detected

    def start(self) -> None:
        """Launch the webcam capture + hand-tracking thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="webcam-tracker", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    # -- internals ------------------------------------------------------------

    def _run(self) -> None:
        """Main capture loop — runs on the background thread."""
        import cv2
        import mediapipe.python.solutions.hands as mp_hands
        import mediapipe.python.solutions.drawing_utils as mp_drawing

        cap = cv2.VideoCapture(self._device)
        if not cap.isOpened():
            print(f"[webcam-tracker] Could not open camera device {self._device}.")
            return

        # Lower resolution for speed — we only need hand landmarks, not HD frames.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        target_interval = 1.0 / max(1, config.WEBCAM_FPS)

        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=config.WEBCAM_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.WEBCAM_MIN_TRACKING_CONFIDENCE,
        )

        print("[webcam-tracker] Started — point your index finger to aim.")

        had_hand = False
        last_local_dir = Direction.FORWARD

        try:
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                # Mirror horizontally so pointing left = game-left.
                frame = cv2.flip(frame, 1)

                # MediaPipe expects RGB.
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb)

                if results.multi_hand_landmarks:
                    hand = results.multi_hand_landmarks[0]
                    direction = self._compute_direction(hand)
                    with self._lock:
                        self._direction = direction
                        self._hand_detected = True
                        self._last_detect_time = time.monotonic()

                    if not had_hand:
                        print(f"[webcam-tracker] Hand detected — aiming: {direction.value.upper()}")
                        had_hand = True
                        last_local_dir = direction
                    elif direction != last_local_dir:
                        print(f"[webcam-tracker] Aim changed to: {direction.value.upper()}")
                        last_local_dir = direction

                    if config.WEBCAM_DEBUG_WINDOW:
                        mp_drawing.draw_landmarks(
                            frame, hand, mp_hands.HAND_CONNECTIONS
                        )
                        # Draw direction label
                        cv2.putText(
                            frame,
                            f"Direction: {direction.value}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            (0, 255, 0),
                            2,
                        )
                else:
                    with self._lock:
                        self._hand_detected = False
                        # Keep last direction when hand disappears — the player
                        # may lift their hand to clap and we want the *last*
                        # pointed direction to persist briefly.
                    if had_hand:
                        print("[webcam-tracker] Hand lost")
                        had_hand = False

                if config.WEBCAM_DEBUG_WINDOW:
                    cv2.imshow("Blind Hunter — Webcam Debug", frame)
                    if cv2.waitKey(1) & 0xFF == 27:  # ESC in debug window
                        break

                # Throttle to target FPS.
                elapsed = time.monotonic() - loop_start
                sleep_time = target_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            hands.close()
            cap.release()
            if config.WEBCAM_DEBUG_WINDOW:
                cv2.destroyAllWindows()
            print("[webcam-tracker] Stopped.")

    def _compute_direction(self, hand_landmarks) -> Direction:
        """Derive a pointing direction from the index finger vector.

        Uses the vector from the index finger MCP knuckle (landmark 5) to the tip
        (landmark 8). The frame is already mirrored, so frame-left = real-left.

        Coordinate system in the mirrored frame:
          - x: 0 (left edge) → 1 (right edge)
          - y: 0 (top edge)  → 1 (bottom edge)

        The pointing vector (tip - knuckle):
          - Pointing UP in frame   → dy < 0 (dominant)
          - Pointing DOWN in frame → dy > 0 (dominant)
          - Pointing LEFT in frame → dx < 0 (dominant)
          - Pointing RIGHT in frame→ dx > 0 (dominant)

        We compute the angle of the vector and map it to 4 quadrants.
        """
        mcp = hand_landmarks.landmark[5]
        tip = hand_landmarks.landmark[8]

        dx = tip.x - mcp.x
        dy = tip.y - mcp.y

        # Check deadzone — if the finger vector is too short, default to FORWARD.
        magnitude = math.hypot(dx, dy)
        if magnitude < config.WEBCAM_DIRECTION_DEADZONE:
            return Direction.FORWARD

        # atan2 with negated dy because y grows downward in the frame but we
        # want "up" to map to the conventional positive-y / 0-degree direction.
        # Result: angle in [-π, π] where:
        #   0     = pointing right in frame
        #   π/2   = pointing up in frame
        #   -π/2  = pointing down in frame
        #   ±π    = pointing left in frame
        angle = math.atan2(-dy, dx)
        angle_deg = math.degrees(angle)

        # Map to 4 zones (centered on each cardinal direction):
        #   UP    (FORWARD):  45° to 135°
        #   RIGHT:           -45° to 45°
        #   DOWN  (BACK):   -135° to -45°
        #   LEFT:            135° to 180° or -180° to -135°
        if 45 <= angle_deg <= 135:
            return Direction.FORWARD   # pointing up = move forward
        elif -45 <= angle_deg < 45:
            return Direction.RIGHT     # pointing right
        elif -135 <= angle_deg < -45:
            return Direction.BACK      # pointing down = turn around
        else:
            return Direction.LEFT      # pointing left

    def __enter__(self) -> "WebcamTracker":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
