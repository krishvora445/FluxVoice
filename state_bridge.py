import asyncio
import json
import logging
import threading
import time
from typing import Optional, Set

import websockets

from ui_state import UIState, UIStateBus


class UIStateBridge(object):
    def __init__(self, state_bus: UIStateBus, host: str = "127.0.0.1", port: int = 8765):
        self._state_bus = state_bus
        self._host = host
        self._port = port

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._state_queue: Optional[asyncio.Queue[Optional[UIState]]] = None
        self._clients: Set[websockets.WebSocketServerProtocol] = set()
        self._shutdown_event = threading.Event()
        self._started_event = threading.Event()
        self._serving_event = threading.Event()
        self._startup_error: Optional[Exception] = None
        self._unsubscribe = None
        # Suppress expected invalid-handshake noise from port probes and half-open sockets.
        self._ws_logger = logging.getLogger("fluxvoice.state_bridge.ws")
        self._ws_logger.propagate = False
        self._ws_logger.setLevel(logging.CRITICAL)
        if not self._ws_logger.handlers:
            self._ws_logger.addHandler(logging.NullHandler())

    def start(self) -> None:
        if self._thread is not None:
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ui-state-bridge")
        self._thread.start()
        self._started_event.wait(timeout=2.0)

        # Wait for successful bind or early thread failure.
        self._serving_event.wait(timeout=2.0)
        if self._startup_error is not None:
            raise RuntimeError("UI state bridge startup failed: {0}".format(self._startup_error))
        if not self._serving_event.is_set():
            raise RuntimeError("UI state bridge startup timed out before server bind.")

        self._unsubscribe = self._state_bus.subscribe(self._on_state_change, emit_current=False)

    def stop(self) -> None:
        self._shutdown_event.set()

        if self._unsubscribe is not None:
            try:
                self._unsubscribe()
            except Exception:
                pass
            self._unsubscribe = None

        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self._enqueue_shutdown_signal)
            except RuntimeError:
                pass

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _enqueue_shutdown_signal(self) -> None:
        if self._state_queue is not None:
            self._state_queue.put_nowait(None)

    def _on_state_change(self, state: UIState) -> None:
        if self._loop is None or self._state_queue is None:
            return

        try:
            self._loop.call_soon_threadsafe(self._state_queue.put_nowait, state)
        except RuntimeError:
            return

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._state_queue = asyncio.Queue()
        self._started_event.set()

        try:
            self._loop.run_until_complete(self._serve())
        except Exception as exc:
            self._startup_error = exc
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            finally:
                self._loop.close()

    async def _serve(self) -> None:
        async with websockets.serve(
            self._handle_client,
            self._host,
            self._port,
            logger=self._ws_logger,
        ):
            self._serving_event.set()
            await self._broadcast_loop()

    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol) -> None:
        self._clients.add(websocket)
        try:
            await websocket.send(self._state_payload(self._state_bus.current_state))
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)

    async def _broadcast_loop(self) -> None:
        while not self._shutdown_event.is_set():
            state = await self._state_queue.get()
            if state is None:
                break
            await self._broadcast_state(state)

        await self._close_all_clients()

    async def _broadcast_state(self, state: UIState) -> None:
        if not self._clients:
            return

        payload = self._state_payload(state)
        dead_clients = []
        for client in list(self._clients):
            try:
                await client.send(payload)
            except Exception:
                dead_clients.append(client)

        for client in dead_clients:
            self._clients.discard(client)
            try:
                await client.close()
            except Exception:
                pass

    async def _close_all_clients(self) -> None:
        for client in list(self._clients):
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()

    def _state_payload(self, state: UIState) -> str:
        return json.dumps(
            {
                "type": "state_change",
                "timestamp": time.time(),
                "payload": {"state": state.value},
            }
        )

