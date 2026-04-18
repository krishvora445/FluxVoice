import asyncio
import json
import time

import websockets

from state_bridge import UIStateBridge
from ui_state import UIState, UIStateBus


async def main():
    state_bus = UIStateBus()
    bridge = UIStateBridge(state_bus=state_bus)
    bridge.start()

    try:
        uri = "ws://127.0.0.1:8765"
        async with websockets.connect(uri) as ws:
            initial = json.loads(await ws.recv())
            print("initial:", initial)

            state_bus.publish(UIState.PROCESSING)
            processing = json.loads(await ws.recv())
            print("processing:", processing)

            state_bus.publish(UIState.PLAYING)
            playing = json.loads(await ws.recv())
            print("playing:", playing)

            state_bus.publish(UIState.IDLE)
            idle = json.loads(await ws.recv())
            print("idle:", idle)

            assert initial["type"] == "state_change"
            assert processing["payload"]["state"] == "processing"
            assert playing["payload"]["state"] == "playing"
            assert idle["payload"]["state"] == "idle"

            # quick sanity check that timestamp is populated
            now = time.time()
            assert abs(now - float(idle["timestamp"])) < 60
            print("bridge smoke test passed")
    finally:
        bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())

