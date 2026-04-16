from enum import Enum
import queue
from typing import Optional


class UIState(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    PLAYING = "playing"


class UIStateBus(object):
    def __init__(self):
        self._events: "queue.Queue[UIState]" = queue.Queue()

    def publish(self, state: UIState) -> None:
        self._events.put(state)

    def drain_latest(self) -> Optional[UIState]:
        latest = None
        while True:
            try:
                latest = self._events.get_nowait()
            except queue.Empty:
                break
        return latest

