import { FormEvent, useState } from "react";
import { DriverPreferences, savePreferences } from "../api";

export default function PreferencesPanel({
  prefs,
  onSaved,
}: {
  prefs: DriverPreferences | null;
  onSaved: (next: DriverPreferences) => void;
}) {
  const [open, setOpen] = useState(false);
  const [home, setHome] = useState("");
  const [work, setWork] = useState("");
  const [temp, setTemp] = useState("21");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openPanel = () => {
    if (prefs) {
      setHome(prefs.home.query);
      setWork(prefs.work.query);
      setTemp(String(prefs.default_temp_c));
    }
    setError(null);
    setOpen(true);
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const celsius = Number(temp);
    if (Number.isNaN(celsius)) {
      setError("Default temperature must be a number");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const next = await savePreferences({
        home_query: home.trim() || "home",
        home_label: "Home",
        work_query: work.trim() || "office",
        work_label: "Work",
        default_temp_c: celsius,
      });
      onSaved(next);
      setOpen(false);
    } catch {
      setError("Couldn't save preferences");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <button type="button" className="prefs-btn" onClick={openPanel}>
        Preferences
      </button>
      {open && (
        <div className="prefs-backdrop" onClick={() => setOpen(false)}>
          <form
            className="prefs-card"
            onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => void onSubmit(e)}
          >
            <h2>Driver preferences</h2>
            <p className="prefs-help">
              Home and Work are used by “take me home” and the map chips. Default
              temperature is applied at start and when you ask for your usual climate.
            </p>
            <label>
              Home
              <input
                value={home}
                onChange={(e) => setHome(e.target.value)}
                placeholder="Address or place name"
              />
            </label>
            <label>
              Work
              <input
                value={work}
                onChange={(e) => setWork(e.target.value)}
                placeholder="Address or place name"
              />
            </label>
            <label>
              Default cabin temp (°C)
              <input
                type="number"
                min={16}
                max={30}
                step={0.5}
                value={temp}
                onChange={(e) => setTemp(e.target.value)}
              />
            </label>
            {error && <div className="prefs-error">{error}</div>}
            <div className="prefs-actions">
              <button type="button" className="prefs-cancel" onClick={() => setOpen(false)}>
                Close
              </button>
              <button type="submit" className="prefs-save" disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
