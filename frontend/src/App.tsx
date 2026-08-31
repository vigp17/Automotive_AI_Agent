import { useEffect, useRef, useState } from "react";
import { openStateSocket, VehicleState } from "./api";
import AlertBanner from "./components/AlertBanner";
import ChatPanel from "./components/ChatPanel";
import MapPanel from "./components/MapPanel";
import VehicleWidgets from "./components/VehicleWidgets";

const SESSION_ID = `cabin-${Math.random().toString(36).slice(2, 10)}`;

export default function App() {
  const [state, setState] = useState<VehicleState | null>(null);
  const [queuedPrompt, setQueuedPrompt] = useState<string | null>(null);
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
      {state?.alerts && (
        <AlertBanner alerts={state.alerts} onAction={setQueuedPrompt} />
      )}
      <main className="layout">
        <VehicleWidgets state={state} />
        <MapPanel state={state} />
        <ChatPanel
          sessionId={SESSION_ID}
          queuedPrompt={queuedPrompt}
          onQueuedPromptHandled={() => setQueuedPrompt(null)}
        />
      </main>
    </div>
  );
}
