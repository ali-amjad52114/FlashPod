import { money } from "../lib";
import type { JobIndexEntry } from "../types";

export function JobsView(props: {
  jobs: JobIndexEntry[];
  onOpen: (e: JobIndexEntry) => void;
  onClose: () => void;
}) {
  return (
    <div
      onClick={props.onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(22,25,29,0.35)", zIndex: 50, display: "flex", justifyContent: "flex-end" }}
    >
      <aside
        onClick={(e) => e.stopPropagation()}
        style={{ width: "min(420px, 92vw)", background: "var(--panel)", height: "100%", padding: 20, overflowY: "auto", boxShadow: "var(--shadow)" }}
      >
        <div style={{ display: "flex", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>Jobs</h2>
          <button onClick={props.onClose} style={{ marginLeft: "auto" }} aria-label="Close jobs">Close</button>
        </div>

        {props.jobs.length === 0 ? (
          <div className="muted" style={{ fontSize: 13, padding: "24px 0" }}>
            No takeoffs yet. Run one and it'll appear here.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {props.jobs.map((j) => (
              <button
                key={j.takeoff_id}
                onClick={() => props.onOpen(j)}
                style={{ display: "grid", gap: 4, textAlign: "left", padding: 12 }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 600 }}>{j.project_name}</span>
                  <span className="badge" style={{ marginLeft: "auto" }}>done</span>
                </div>
                <div className="mono muted" style={{ fontSize: 11, display: "flex", gap: 12 }}>
                  <span>{new Date(j.date).toLocaleDateString()}</span>
                  <span>{j.symbol_count} symbols</span>
                  <span style={{ marginLeft: "auto" }}>${money(j.grand_total)}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
