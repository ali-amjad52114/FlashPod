import { useEffect, useRef, useState } from "react";
import { runTakeoff } from "../api";
import type { Drawing, Project, Takeoff } from "../types";

const STAGES = ["Detect symbols", "Price materials", "Generate proposal"];

export function RunScreen(props: {
  project: Project;
  drawing: Drawing;
  onDone: (t: Takeoff) => void;
  onBack: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const started = useRef(false);

  async function run() {
    setError(null);
    setElapsed(0);
    const t0 = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
    try {
      // Blocks until the backend's worker finishes + Bright Data overlay (cold start ~30-120s).
      const t = await runTakeoff(props.project.id, props.drawing.id);
      clearInterval(timer);
      if (t.status === "error") setError(t.error || "The takeoff failed.");
      else props.onDone(t);
    } catch (e) {
      clearInterval(timer);
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    if (started.current) return; // guard StrictMode double-invoke -> avoid double POST
    started.current = true;
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const coldStart = !error && elapsed < 60;

  return (
    <div style={{ maxWidth: 560, margin: "40px auto 0", display: "grid", gap: 20 }}>
      <div className="panel" style={{ padding: 24, display: "grid", gap: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {!error && <span className="spinner" aria-hidden />}
          <div>
            <div style={{ fontWeight: 600 }}>
              {error ? "Takeoff failed" : coldStart ? "Warming up — cold start" : "Running takeoff"}
            </div>
            <div className="muted mono" style={{ fontSize: 12 }}>
              {error ? "" : `${elapsed}s elapsed`}
            </div>
          </div>
        </div>

        {!error && (
          <>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>
              One Runpod job runs the whole pipeline. The stages below resolve together when the job returns — the
              backend doesn't report per-stage progress, so we don't fake it.
            </p>
            <div style={{ display: "grid", gap: 8 }}>
              {STAGES.map((s) => (
                <div key={s} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", animation: "pulse 1.4s ease-in-out infinite" }} />
                  <span>{s}</span>
                  <span className="muted" style={{ marginLeft: "auto", fontSize: 12 }}>working…</span>
                </div>
              ))}
            </div>
          </>
        )}

        {error && (
          <div style={{ display: "grid", gap: 14 }}>
            <div style={{ color: "var(--danger)", fontSize: 13, fontFamily: "var(--mono)", whiteSpace: "pre-wrap" }}>{error}</div>
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={props.onBack}>Back to symbols</button>
              <button className="primary" style={{ marginLeft: "auto" }} onClick={run}>
                Retry
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
