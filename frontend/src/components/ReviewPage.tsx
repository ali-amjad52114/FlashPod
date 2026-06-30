import { useEffect, useRef, useState } from "react";
import { runTakeoff } from "../api";
import { DrawingCanvas, type Box } from "./DrawingCanvas";
import { DetectionInspector } from "./DetectionInspector";
import { activeDetections, type ReviewModel, type RDetection } from "../review";
import type { Drawing, Project, Takeoff } from "../types";

export function ReviewPage(props: {
  project: Project | null;
  drawing: Drawing | null;
  imageUrl: string;
  takeoff: Takeoff | null;
  review: ReviewModel | null;
  onRan: (t: Takeoff) => void;
  onReviewChange: (m: ReviewModel) => void;
  onGenerate: () => void;
  onBack: () => void;
}) {
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [addType, setAddType] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  async function runNow() {
    if (!props.project || !props.drawing) return;
    setError(null);
    setRunning(true);
    setElapsed(0);
    const t0 = Date.now();
    timer.current = window.setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
    try {
      const t = await runTakeoff(props.project.id, props.drawing.id);
      if (t.status === "error") setError(t.error || "Detection failed.");
      else props.onRan(t);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      if (timer.current) window.clearInterval(timer.current);
      setRunning(false);
    }
  }

  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);

  const ready = props.review && props.takeoff?.status === "done" && props.takeoff.image_size;

  // ---- not-yet-detected: run card with honest status ----
  if (!ready) {
    return (
      <div style={{ maxWidth: 620, margin: "30px auto 0", display: "grid", gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 22, margin: "0 0 4px" }}>Detect &amp; Review</h1>
          <p className="muted" style={{ margin: 0 }}>FlashPod will scan the drawing for your symbol examples. Run a first-pass detection, then review and correct.</p>
        </div>
        <div className="panel" style={{ padding: 22, display: "grid", gap: 16 }}>
          {running ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span className="spinner" aria-hidden />
                <div>
                  <div style={{ fontWeight: 600 }}>{elapsed < 60 ? "Warming up Runpod worker" : "Processing drawing"}</div>
                  <div className="muted mono" style={{ fontSize: 12 }}>{elapsed}s · cold start can take 30–120s</div>
                </div>
              </div>
              <p className="muted" style={{ margin: 0, fontSize: 12 }}>
                The backend runs one synchronous job, so detect / count / price / proposal complete together — these labels are informational, not live per-stage progress.
              </p>
            </>
          ) : error ? (
            <>
              <div style={{ color: "var(--danger)", fontFamily: "var(--mono)", fontSize: 13, whiteSpace: "pre-wrap" }}>{error}</div>
              <div style={{ display: "flex", gap: 10 }}>
                <button onClick={props.onBack}>Back to project</button>
                <button className="primary" style={{ marginLeft: "auto" }} onClick={runNow}>Retry</button>
              </div>
            </>
          ) : (
            <>
              <p style={{ margin: 0, fontSize: 14 }}>Ready to run a first-pass takeoff on this drawing.</p>
              <div style={{ display: "flex", gap: 10 }}>
                <button onClick={props.onBack}>Back</button>
                <button className="primary" style={{ marginLeft: "auto" }} onClick={runNow}>Run takeoff</button>
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  // ---- detected: review UI ----
  const model = props.review!;
  const active = activeDetections(model);

  function pickDetection(id: string | null) {
    setSelectedId(id);
    setSelectedType(id ? model.detections.find((d) => d.id === id)?.type ?? null : null);
  }
  function pickType(t: string | null) {
    setSelectedType(t);
    setSelectedId(null);
  }
  function addBox(b: Box) {
    if (!addType) return;
    const label = model.labelByType[addType] ?? addType;
    const det: RDetection = { id: `man-${Date.now()}-${model.detections.length}`, type: addType, label, x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.w), h: Math.round(b.h), confidence: 1, excluded: false, manual: true };
    props.onReviewChange({ ...model, detections: [...model.detections, det] });
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 22, margin: "0 0 2px" }}>Detect &amp; Review</h1>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>FlashPod found electrical devices. Review and correct these reviewable detections before creating the proposal.</p>
        </div>
        <button className="primary" style={{ marginLeft: "auto" }} onClick={props.onGenerate}>Generate Quantity Takeoff →</button>
      </div>

      <div className="two-col">
        <div className="panel" style={{ padding: 12 }}>
          <DrawingCanvas
            imageUrl={props.imageUrl}
            imageSize={props.takeoff!.image_size!}
            detections={active}
            selectedType={selectedType}
            selectedId={selectedId}
            onPickType={pickType}
            onPickDetection={pickDetection}
            addMode={!!addType}
            onAddBox={addBox}
          />
          {addType && <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>Drawing mode — drag a box to add a <b>{model.labelByType[addType] ?? addType}</b>. <button onClick={() => setAddType(null)} style={{ padding: "2px 8px", marginLeft: 6 }}>Done</button></div>}
        </div>

        <DetectionInspector
          takeoffId={props.takeoff!.id}
          model={model}
          selectedId={selectedId}
          selectedType={selectedType}
          addType={addType}
          onAddType={setAddType}
          onPickType={pickType}
          onChange={props.onReviewChange}
        />
      </div>
    </div>
  );
}
