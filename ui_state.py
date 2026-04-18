from enum import Enum
import itertools
import threading
from typing import Callable, Dict, Optional


class UIState(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    PLAYING = "playing"
    ERROR = "error"


class UIStateBus(object):
    def __init__(self):
        self._state_lock = threading.Lock()
        self._current_state = UIState.IDLE
        self._subscribers: Dict[int, Callable[[UIState], None]] = {}
        self._subscriber_id_counter = itertools.count(1)

    @property
    def current_state(self) -> UIState:
        with self._state_lock:
            return self._current_state

    def publish(self, state: UIState) -> None:
        with self._state_lock:
            self._current_state = state
            subscribers = list(self._subscribers.values())

        for callback in subscribers:
            try:
                callback(state)
            except Exception:
                # Keep bus delivery resilient if one subscriber fails.
                continue

    def subscribe(self, callback: Callable[[UIState], None], emit_current: bool = True) -> Callable[[], None]:
        subscriber_id = next(self._subscriber_id_counter)

        with self._state_lock:
            self._subscribers[subscriber_id] = callback
            current = self._current_state

        if emit_current:
            try:
                callback(current)
            except Exception:
                pass

        def unsubscribe() -> None:
            with self._state_lock:
                self._subscribers.pop(subscriber_id, None)

        return unsubscribe

    def drain_latest(self) -> Optional[UIState]:
        # Legacy compatibility path for existing consumers.
        return self.current_state

