"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import { useOrganizationId } from "@/features/auth/session";
import { config } from "@/lib/config";
import type { ProcessingEventMessage } from "@/types/api";

export type ConnectionStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed";

export interface ProcessingEventsValue {
  readonly status: ConnectionStatus;
  readonly subscribe: (
    videoId: string,
    listener: (event: ProcessingEventMessage) => void,
  ) => () => void;
}

const ProcessingEventsContext = createContext<ProcessingEventsValue | null>(null);

const BASE_RETRY_MS = 1000;
const MAX_RETRY_MS = 30_000;

function backoffDelay(attempt: number): number {
  const exponential = Math.min(MAX_RETRY_MS, BASE_RETRY_MS * 2 ** attempt);
  // Jitter avoids a fleet of clients reconnecting in lockstep after a restart.
  return exponential * (0.5 + Math.random() / 2);
}

export function ProcessingEventsProvider({ children }: { children: ReactNode }) {
  const organizationId = useOrganizationId();
  const [status, setStatus] = useState<ConnectionStatus>("idle");

  // Listeners are held in a ref so subscribing does not re-open the socket.
  const listeners = useRef(new Map<string, Set<(event: ProcessingEventMessage) => void>>());
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<{ attempt: number; timer: number | null }>({
    attempt: 0,
    timer: null,
  });

  const subscribe = useCallback(
    (videoId: string, listener: (event: ProcessingEventMessage) => void) => {
      const set = listeners.current.get(videoId) ?? new Set();
      set.add(listener);
      listeners.current.set(videoId, set);
      return () => {
        const current = listeners.current.get(videoId);
        if (!current) return;
        current.delete(listener);
        if (current.size === 0) listeners.current.delete(videoId);
      };
    },
    [],
  );

  useEffect(() => {
    if (organizationId === null || config.wsUrl === "") return;

    // Captured so the cleanup closes over stable values rather than the mutable
    // ref objects React warns about.
    const reconnect = reconnectRef.current;
    let disposed = false;

    function open() {
      if (disposed) return;
      setStatus(reconnect.attempt === 0 ? "connecting" : "reconnecting");

      const url = `${config.wsUrl}/ws/processing?organization_id=${encodeURIComponent(
        organizationId ?? "",
      )}`;
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.addEventListener("open", () => {
        if (disposed) {
          socket.close();
          return;
        }
        reconnect.attempt = 0;
        setStatus("open");
      });

      socket.addEventListener("message", (message) => {
        let event: ProcessingEventMessage;
        try {
          event = JSON.parse(String(message.data)) as ProcessingEventMessage;
        } catch {
          // A malformed frame is dropped rather than thrown: it must not tear
          // down a working connection.
          return;
        }
        for (const listener of listeners.current.get(event.video_id) ?? []) {
          listener(event);
        }
      });

      socket.addEventListener("close", () => {
        if (disposed) return;
        scheduleReconnect();
      });

      socket.addEventListener("error", () => {
        // 'close' follows an 'error', so reconnection is handled there once.
        socket.close();
      });
    }

    function scheduleReconnect() {
      if (disposed) return;
      const attempt = reconnect.attempt;
      reconnect.attempt = attempt + 1;
      setStatus("reconnecting");
      reconnect.timer = window.setTimeout(open, backoffDelay(attempt));
    }

    open();

    return () => {
      disposed = true;
      if (reconnect.timer !== null) {
        window.clearTimeout(reconnect.timer);
        reconnect.timer = null;
      }
      reconnect.attempt = 0;
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [organizationId]);

  const value = useMemo<ProcessingEventsValue>(() => ({ status, subscribe }), [status, subscribe]);

  return (
    <ProcessingEventsContext.Provider value={value}>{children}</ProcessingEventsContext.Provider>
  );
}

/** Returns the realtime context, or 'null' when no provider is mounted. */
export function useProcessingEvents(): ProcessingEventsValue | null {
  return useContext(ProcessingEventsContext);
}
