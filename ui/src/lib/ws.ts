import { useEffect, useRef, useState } from "react";

export type FluxVoiceState = "idle" | "processing" | "playing" | "error";

type FluxVoicePayload = {
  state?: string;
};

type FluxVoiceMessage = {
  type?: string;
  timestamp?: number;
  payload?: FluxVoicePayload;
};

const WS_URL = "ws://127.0.0.1:8765";
const BASE_RETRY_MS = 400;
const MAX_RETRY_MS = 8000;

function isFluxVoiceState(value: unknown): value is FluxVoiceState {
  return value === "idle" || value === "processing" || value === "playing" || value === "error";
}

export function useFluxVoiceState() {
  const [state, setState] = useState<FluxVoiceState>("idle");
  const [isConnected, setIsConnected] = useState(false);
  const retryAttemptRef = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    stoppedRef.current = false;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const closeSocket = () => {
      const socket = socketRef.current;
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
      }
      socketRef.current = null;
    };

    const scheduleReconnect = () => {
      if (stoppedRef.current) {
        return;
      }

      clearReconnectTimer();

      const attempt = retryAttemptRef.current;
      const delayMs = Math.min(BASE_RETRY_MS * 2 ** attempt, MAX_RETRY_MS);
      retryAttemptRef.current += 1;

      reconnectTimerRef.current = window.setTimeout(() => {
        connect();
      }, delayMs);
    };

    const connect = () => {
      if (stoppedRef.current) {
        return;
      }

      closeSocket();

      let socket: WebSocket;
      try {
        socket = new WebSocket(WS_URL);
      } catch {
        scheduleReconnect();
        return;
      }

      socketRef.current = socket;

      socket.onopen = () => {
        retryAttemptRef.current = 0;
        setIsConnected(true);
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        let parsed: FluxVoiceMessage;
        try {
          parsed = JSON.parse(event.data) as FluxVoiceMessage;
        } catch {
          return;
        }

        if (parsed.type !== "state_change") {
          return;
        }

        const next = parsed.payload?.state;
        if (isFluxVoiceState(next)) {
          setState(next);
        }
      };

      socket.onerror = () => {
        setIsConnected(false);
        closeSocket();
        scheduleReconnect();
      };

      socket.onclose = () => {
        setIsConnected(false);
        closeSocket();
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      stoppedRef.current = true;
      setIsConnected(false);
      clearReconnectTimer();
      closeSocket();
    };
  }, []);

  return { state, isConnected };
}

