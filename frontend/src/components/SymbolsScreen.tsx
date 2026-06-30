import { useRef, useState } from "react";
import { uploadTemplate } from "../api";
import { colorForType, slugify } from "../lib";
import type { Project, Template } from "../types";

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function SymbolsScreen(props: {
  project: Project;
  imageUrl: string;
  templates: Template[];
  onTemplatesChange: (t: Template[]) => void;
  onRun: () => void;
  onBack: () => void;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [rect, setRect] = useState<Rect | null>(null);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const [label, setLabel] = useState("");
  const [threshold, setThreshold] = useState(0.7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function relPoint(e: React.MouseEvent) {
    const img = imgRef.current!;
    const r = img.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(e.clientX - r.left, r.width)),
      y: Math.max(0, Math.min(e.clientY - r.top, r.height)),
    };
  }

  function onDown(e: React.MouseEvent) {
    const p = relPoint(e);
    setDrag(p);
    setRect({ x: p.x, y: p.y, w: 0, h: 0 });
  }
  function onMove(e: React.MouseEvent) {
    if (!drag) return;
    const p = relPoint(e);
    setRect({ x: Math.min(drag.x, p.x), y: Math.min(drag.y, p.y), w: Math.abs(p.x - drag.x), h: Math.abs(p.y - drag.y) });
  }
  function onUp() {
    setDrag(null);
  }

  async function addSymbol() {
    const img = imgRef.current;
    if (!img || !rect || rect.w < 6 || rect.h < 6) {
      setError("Draw a box around one symbol first.");
      return;
    }
    if (!label.trim()) {
      setError("Give the symbol a label (e.g. “Duplex Outlet”).");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const sx = (rect.x * img.naturalWidth) / img.clientWidth;
      const sy = (rect.y * img.naturalHeight) / img.clientHeight;
      const sw = (rect.w * img.naturalWidth) / img.clientWidth;
      const sh = (rect.h * img.naturalHeight) / img.clientHeight;
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(sw);
      canvas.height = Math.round(sh);
      canvas.getContext("2d")!.drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
      const blob: Blob = await new Promise((res, rej) =>
        canvas.toBlob((b) => (b ? res(b) : rej(new Error("crop failed"))), "image/png"),
      );
      const file = new File([blob], `${slugify(label)}.png`, { type: "image/png" });
      const tpl = await uploadTemplate(props.project.id, {
        sym_type: slugify(label),
        label: label.trim(),
        threshold,
        file,
      });
      props.onTemplatesChange([...props.templates, tpl]);
      setRect(null);
      setLabel("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 20, alignItems: "start" }}>
      <div className="panel" style={{ padding: 12, background: "var(--sheet)" }}>
        <div
          style={{ position: "relative", display: "inline-block", cursor: "crosshair", userSelect: "none", maxWidth: "100%" }}
          onMouseDown={onDown}
          onMouseMove={onMove}
          onMouseUp={onUp}
          onMouseLeave={onUp}
        >
          <img ref={imgRef} src={props.imageUrl} alt="Drawing" draggable={false} style={{ maxWidth: "100%", display: "block" }} />
          {rect && (
            <div
              style={{
                position: "absolute",
                left: rect.x,
                top: rect.y,
                width: rect.w,
                height: rect.h,
                border: "2px solid var(--accent)",
                background: "rgba(45,91,255,0.12)",
                pointerEvents: "none",
              }}
            />
          )}
        </div>
      </div>

      <div style={{ display: "grid", gap: 16 }}>
        <div>
          <h2 style={{ fontSize: 18, margin: "4px 0" }}>Mark your symbols</h2>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            Draw a box around one instance of each symbol (use the legend if there is one). Each crop is sent to the
            backend as a match template.
          </p>
        </div>

        <div className="panel" style={{ padding: 14, display: "grid", gap: 12 }}>
          <label style={{ display: "grid", gap: 5 }}>
            <span style={{ fontSize: 12, color: "var(--secondary)" }}>Symbol label</span>
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Duplex Outlet" />
          </label>
          <label style={{ display: "grid", gap: 5 }}>
            <span style={{ fontSize: 12, color: "var(--secondary)" }}>
              Match threshold <span className="mono">{threshold.toFixed(2)}</span>
            </span>
            <input
              type="range"
              min={0.3}
              max={0.95}
              step={0.05}
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
            />
          </label>
          {error && <div style={{ color: "var(--danger)", fontSize: 12 }}>{error}</div>}
          <button className="primary" disabled={busy} onClick={addSymbol}>
            {busy ? "Adding…" : "Add symbol"}
          </button>
        </div>

        <div className="panel" style={{ padding: 14, display: "grid", gap: 8 }}>
          <span style={{ fontSize: 12, color: "var(--secondary)" }}>
            Symbols to count ({props.templates.length})
          </span>
          {props.templates.length === 0 ? (
            <span className="muted" style={{ fontSize: 13 }}>None yet — draw a box and add one.</span>
          ) : (
            props.templates.map((t) => (
              <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                <span style={{ width: 12, height: 12, borderRadius: 3, background: colorForType(t.sym_type) }} />
                <span>{t.label}</span>
                <span className="mono muted" style={{ marginLeft: "auto", fontSize: 12 }}>≥ {t.threshold.toFixed(2)}</span>
              </div>
            ))
          )}
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={props.onBack}>Back</button>
          <button className="primary" style={{ marginLeft: "auto" }} disabled={props.templates.length === 0} onClick={props.onRun}>
            Run takeoff
          </button>
        </div>
      </div>
    </div>
  );
}
