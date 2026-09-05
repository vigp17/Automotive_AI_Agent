import { useEffect, useState } from "react";
import {
  CalendarStatus,
  addDemoMeeting,
  connectOutlook,
  fetchCalendarStatus,
  logoutOutlook,
} from "../api";

export default function OutlookConnect() {
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => fetchCalendarStatus().then(setStatus).catch(() => undefined);

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    if (!status?.pending) return;
    const id = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(id);
  }, [status?.pending]);

  if (!status || status.backend !== "graph") return null;

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      await connectOutlook();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start Outlook login");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {status.connected ? (
        <>
          <button
            type="button"
            className="prefs-btn"
            onClick={() => void logoutOutlook().then(() => refresh())}
          >
            Outlook connected
          </button>
          {status.meeting_count === 0 && (
            <button
              type="button"
              className="prefs-btn"
              onClick={() =>
                void addDemoMeeting()
                  .then(() => refresh())
                  .catch((err) =>
                    setError(err instanceof Error ? err.message : "Could not add sample meeting"),
                  )
              }
              disabled={busy}
            >
              Add sample meeting
            </button>
          )}
        </>
      ) : (
        <button type="button" className="prefs-btn" onClick={() => void start()} disabled={busy || !status.configured}>
          {busy ? "Starting..." : "Connect Outlook"}
        </button>
      )}
      {status.pending && (
        <div className="prefs-backdrop">
          <div className="prefs-card">
            <h2>Connect Outlook</h2>
            <p className="prefs-help">
              Open{" "}
              <a href={status.pending.verification_uri} target="_blank" rel="noreferrer">
                {status.pending.verification_uri}
              </a>{" "}
              and enter this code:
            </p>
            <div className="device-code">{status.pending.user_code}</div>
            <p className="prefs-help">This window updates when Microsoft confirms the login.</p>
            {status.error && <div className="prefs-error">{status.error}</div>}
          </div>
        </div>
      )}
      {error && !status.pending && <span className="prefs-inline-error">{error}</span>}
    </>
  );
}
