import { useEffect, useRef, useState } from "react";
import { openStateSocket, VehicleState } from "./api";
import ChatPanel from "./components/ChatPanel";
import VehicleWidgets from "./components/VehicleWidgets";

const SESSION_ID = `cabin-${Math.random().toString(36).slice(2, 10)}`;

export default function App() {
  const [state, setState] = useState<VehicleState | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;

    const connect = () => {
      const ws = openStateSocket(setState);
      ws.onclose = () => {
        if (!closed) setTimeout(connect, 2000);
      };
      wsRef.current = ws;
    };
    connect();

    return () => {
      closed = true;
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="logo">AI Cabin Copilot</div>
        <div className="status">
          <span className={`dot ${state ? "online" : "offline"}`} />
          {state ? "vehicle online" : "connecting"}
        </div>
      </header>
      <main className="layout">
        <VehicleWidgets state={state} />
        <ChatPanel sessionId={SESSION_ID} />
      </main>
    </div>
  );
}
