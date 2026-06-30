export type Step = "upload" | "symbols" | "run" | "results";

const STEPS: { key: Step; label: string }[] = [
  { key: "upload", label: "Upload" },
  { key: "symbols", label: "Symbols" },
  { key: "run", label: "Run" },
  { key: "results", label: "Results" },
];

export function TopBar(props: { step: Step; jobsCount: number; onJobs: () => void; onHome: () => void }) {
  const order = STEPS.findIndex((s) => s.key === props.step);
  return (
    <header
      className="hairline"
      style={{
        background: "var(--panel)",
        display: "flex",
        alignItems: "center",
        gap: 20,
        padding: "10px clamp(12px, 4vw, 40px)",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      <button
        onClick={props.onHome}
        style={{ border: "none", background: "none", padding: 0, fontWeight: 700, fontSize: 16, letterSpacing: -0.2 }}
        aria-label="FlashPod home"
      >
        Flash<span style={{ color: "var(--accent)" }}>Pod</span>
      </button>

      <nav aria-label="Steps" style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        {STEPS.map((s, i) => {
          const active = s.key === props.step;
          const done = i < order;
          return (
            <span key={s.key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {i > 0 && <span className="muted" aria-hidden>·</span>}
              <span
                style={{
                  fontSize: 12,
                  fontWeight: active ? 700 : 500,
                  color: active ? "var(--accent)" : done ? "var(--ink)" : "var(--secondary)",
                }}
              >
                {s.label}
              </span>
            </span>
          );
        })}
      </nav>

      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
        <span className="badge" title="Honest scope">
          Runpod CPU endpoint · template-match MVP
        </span>
        <button onClick={props.onJobs} aria-label="Open jobs history">
          Jobs{props.jobsCount > 0 ? ` · ${props.jobsCount}` : ""}
        </button>
      </div>
    </header>
  );
}
