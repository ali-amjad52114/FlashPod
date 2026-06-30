import { useRef, useState } from "react";
import { uploadTemplate } from "../api";
import { colorForType, slugify } from "../lib";
import type { Project, Template } from "../types";

interface Rect { x: number; y: number; w: number; h: number; }

// Compact "setup" step (modal) — select symbol examples before detection runs.
export function SymbolSetupModal(props: {
  project: Project;
  imageUrl: string;
  onContinue: () => void;
  onClose: () => void;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [rect, setRect] = useState<Rect | null>(null);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const [label, setLabel] = useState("");
  const [threshold, setThreshold] = useState(0.7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<Template[]>([]);

  function rel(e: React.MouseEvent) {
    const r = imgRef.current!.getBoundingClientRect();
    return { x: Math.max(0, Math.min(e.clientX - r.left, r.width)), y: Math.max(0, Math.min(e.clientY - r.top, r.height)) };
  }
  function down(e: React.MouseEvent) { const p = rel(e); setDrag(p); setRect({ ...p, w: 0, h: 0 }); }
  function move(e: React.MouseEvent) {
    if (!drag) return;
    const p = rel(e);
    setRect({ x: Math.min(drag.x, p.x), y: Math.min(drag.y, p.y), w: Math.abs(p.x - drag.x), h: Math.abs(p.y - drag.y) });
  }

  async function add() {
    const img = imgRef.current;
    if (!img || !rect || rect.w < 6 || rect.h < 6) return setError("Draw a box around one symbol.");
    if (!label.trim()) return setError("Name the symbol (e.g. “Duplex Receptacle”).");
    setError(null); setBusy(true);
    try {
      const k = { sx: (rect.x * img.naturalWidth) / img.clientWidth, sy: (rect.y * img.naturalHeight) / img.clientHeight, sw: (rect.w * img.naturalWidth) / img.clientWidth, sh: (rect.h * img.naturalHeight) / img.clientHeight };
      const c = document.createElement("canvas");
      c.width = Math.round(k.sw); c.height = Math.round(k.sh);
      c.getContext("2d")!.drawImage(img, k.sx, k.sy, k.sw, k.sh, 0, 0, c.width, c.height);
      const blob: Blob = await new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error("crop failed"))), "image/png"));
      const tpl = await uploadTemplate(props.project.id, { sym_type: slugify(label), label: label.trim(), threshold, file: new File([blob], `${slugify(label)}.png`, { type: "image/png" }) });
      setAdded((a) => [...a, tpl]); setRect(null); setLabel("");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" onClick={props.onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()} style={{ padding: 18, width: "min(920px, 96vw)", maxHeight: "92vh", overflow: "auto" }}>
        <h2 style={{ margin: "0 0 2px", fontSize: 18 }}>Select symbol examples</h2>
        <p className="muted" style={{ margin: "0 0 14px", fontSize: 13 }}>
          Draw a box around one of each symbol on the drawing. FlashPod matches these examples to count every instance.
        </p>

        <div className="two-col">
          <div style={{ background: "var(--sheet)", border: "1px solid var(--hairline)", borderRadius: 6, padding: 8, overflow: "auto" }}>
            <div style={{ position: "relative", display: "inline-block", cursor: "crosshair", userSelect: "none", maxWidth: "100%" }}
              onMouseDown={down} onMouseMove={move} onMouseUp={() => setDrag(null)} onMouseLeave={() => setDrag(null)}>
              <img ref={imgRef} src={props.imageUrl} alt="Drawing" draggable={false} style={{ maxWidth: "100%", display: "block" }} />
              {rect && <div style={{ position: "absolute", left: rect.x, top: rect.y, width: rect.w, height: rect.h, border: "2px solid var(--accent)", background: "rgba(45,91,255,0.12)", pointerEvents: "none" }} />}
            </div>
          </div>

          <div style={{ display: "grid", gap: 12 }}>
            <label style={{ display: "grid", gap: 5 }}>
              <span style={{ fontSize: 12, color: "var(--secondary)" }}>Symbol name</span>
              <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Duplex Receptacle" />
            </label>
            <label style={{ display: "grid", gap: 5 }}>
              <span style={{ fontSize: 12, color: "var(--secondary)" }}>Match threshold <span className="mono">{threshold.toFixed(2)}</span></span>
              <input type="range" min={0.3} max={0.95} step={0.05} value={threshold} onChange={(e) => setThreshold(parseFloat(e.target.value))} />
            </label>
            {error && <div style={{ color: "var(--danger)", fontSize: 12 }}>{error}</div>}
            <button className="primary" disabled={busy} onClick={add}>{busy ? "Adding…" : "Add example"}</button>

            <div className="panel" style={{ padding: 10, display: "grid", gap: 6 }}>
              <span style={{ fontSize: 12, color: "var(--secondary)" }}>Examples ({added.length})</span>
              {added.length === 0 ? <span className="muted" style={{ fontSize: 12 }}>None yet.</span> :
                added.map((t) => (
                  <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                    <span style={{ width: 11, height: 11, borderRadius: 3, background: colorForType(t.sym_type) }} />
                    {t.label}
                    <span className="mono muted" style={{ marginLeft: "auto", fontSize: 12 }}>≥ {t.threshold.toFixed(2)}</span>
                  </div>
                ))}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <button onClick={props.onClose}>Cancel</button>
          <button className="primary" style={{ marginLeft: "auto" }} disabled={added.length === 0} onClick={props.onContinue}>
            Continue to Review
          </button>
        </div>
      </div>
    </div>
  );
}
