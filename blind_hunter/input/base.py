"""Input-source abstraction.

Any input scheme (mic-only, mic+webcam, or a future hardware mic array) is an
`InputSource` that pushes `ClapEvent`s onto a thread-safe queue. The game loop
drains that queue each tick and never cares how the events were produced.
"""

from __future__ import annotations

import abc
import queue

from blind_hunter.events import ClapEvent


class InputSource(abc.ABC):
    """Base class for anything that produces ClapEvents on a background thread."""

    def __init__(self) -> None:
        # Unbounded is fine — claps are low-frequency and the loop drains fast.
        self.events: "queue.Queue[ClapEvent]" = queue.Queue()

    @abc.abstractmethod
    def start(self) -> None:
        """Begin capturing / processing on a background thread."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop capture and release resources."""

    def emit(self, event: ClapEvent) -> None:
        """Push an event for the game loop to consume."""
        self.events.put(event)

    def poll(self) -> list[ClapEvent]:
        """Non-blocking drain of all pending events (called from the game loop)."""
        drained: list[ClapEvent] = []
        while True:
            try:
                drained.append(self.events.get_nowait())
            except queue.Empty:
                break
        return drained

    def __enter__(self) -> "InputSource":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
