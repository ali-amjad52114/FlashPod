export type Step = "project" | "review" | "proposal";

const STEPS: { key: Step; n: number; label: string }[] = [
  { key: "project", n: 1, label: "Project" },
  { key: "review", n: 2, label: "Review" },
  { key: "proposal", n: 3, label: "Proposal" },
];

export function TopBar(props: { step: Step; jobsCount: number; onJobs: () => void; onHome: () => void }) {
  const order = STEPS.findIndex((s) => s.key === props.step);
  return (
    <header
      className="hairline"
      style={{ background: "var(--panel)", position: "sticky", top: 0, zIndex: 10 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "10px clamp(12px, 4vw, 40px)", flexWrap: "wrap" }}>
        <button
          onClick={props.onHome}
          style={{ border: "none", background: "none", padding: 0, fontWeight: 700, fontSize: 16, letterSpacing: -0.2 }}
          aria-label="FlashPod home"
        >
          Flash<span style={{ color: "var(--accent)" }}>Pod</span>
        </button>

        <nav aria-label="Steps" style={{ display: "flex", gap: 4, alignItems: "center" }}>
          {STEPS.map((s, i) => {
            const active = s.key === props.step;
            const done = i < order;
            return (
              <span key={s.key} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                {i > 0 && <span className="muted" aria-hidden style={{ margin: "0 2px" }}>›</span>}
                <span
                  style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    width: 18, height: 18, borderRadius: "50%", fontSize: 11, fontWeight: 700,
                    background: active ? "var(--accent)" : done ? "var(--ok)" : "var(--hairline)",
                    color: active || done ? "#fff" : "var(--secondary)",
                  }}
                >
                  {s.n}
                </span>
                <span style={{ fontSize: 12, fontWeight: active ? 700 : 500, color: active ? "var(--accent)" : "var(--secondary)" }}>
                  {s.label}
                </span>
              </span>
            );
          })}
        </nav>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          <button onClick={props.onJobs} aria-label="Open proposals">
            Proposals{props.jobsCount > 0 ? ` · ${props.jobsCount}` : ""}
          </button>
        </div>
      </div>

      {/* Honesty badge — its own quiet row so it never crowds the bar on mobile */}
      <div style={{ padding: "0 clamp(12px, 4vw, 40px) 8px" }}>
        <span className="chip">
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--ok)" }} />
          <span className="hide-mobile">Runpod CPU endpoint · OpenCV template-matching MVP · no trained model</span>
          <span className="show-mobile">CPU template-match MVP · no trained model</span>
        </span>
      </div>
    </header>
  );
}
