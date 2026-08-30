import { useEffect, useState } from "react";
import { CabinAlert } from "../api";

export default function AlertBanner({
  alerts,
  onAction,
}: {
  alerts: CabinAlert[];
  onAction: (prompt: string) => void;
}) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    const live = new Set(alerts.map((a) => a.id));
    setDismissed((prev) => new Set([...prev].filter((id) => live.has(id))));
  }, [alerts]);

  const visible = alerts.filter((a) => !dismissed.has(a.id));
  if (visible.length === 0) return null;

  return (
    <div className="alert-stack" role="status">
      {visible.map((alert) => (
        <div key={alert.id} className={`alert-card ${alert.severity}`}>
          <div className="alert-body">
            <div className="alert-title">{alert.title}</div>
            <div className="alert-message">{alert.message}</div>
          </div>
          <div className="alert-actions">
            {alert.action && (
              <button className="alert-action" onClick={() => onAction(alert.action!)}>
                {alert.action}
              </button>
            )}
            <button
              className="alert-dismiss"
              aria-label={`Dismiss ${alert.title}`}
              onClick={() => setDismissed((prev) => new Set(prev).add(alert.id))}
            >
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
