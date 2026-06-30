import { useEffect, useRef, useState } from "react";
import { apiBase, autoDetectSymbols, confirmSymbols } from "../api";
import { slugify } from "../lib";
import type { Drawing, Project } from "../types";

interface Row {
  key: string;
  bbox: [number, number, number, number]; // original-image px [x,y,w,h]
  preview: string; // data URL for the glyph thumbnail
  selected: boolean;
  name: string;
  manual: boolean;
}
interface Rect { x: number; y: number; w: number; h: number; }

// "Select symbol examples" — auto-detects the legend glyphs (and OCR-names them);
// falls back to drawing a box by hand when a drawing has no legend.
export function SymbolSetupModal(props: {
  project: Project;
  drawing: Drawing;
  onContinue: () => void;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // manual draw-a-box state
  const imgRef = useRef<HTMLImageElement>(null);
  const [rect, setRect] = useState<Rect | null>(null);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const [manualName, setManualName] = useState("");
  const imageUrl = `${apiBase}/drawings/${props.drawing.id}`;

  useEffect(() => {
    let alive = true;
    autoDetectSymbols(props.project.id, props.drawing.id)
      .then((res) => {
        if (!alive) return;
        setRows(
          res.candidates.map((c) => ({
            key: `auto-${c.index}`,
            bbox: c.bbox,
            preview: `data:image/png;base64,${c.glyph_base64}`,
            selected: true,
            name: c.suggested_label || "",
            manual: false,
          })),
        );
        setLoading(false);
      })
      .catch((e) => {
        if (!alive) return;
        setError((e as Error).message);
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [props.project.id, props.drawing.id]);

  function update(key: string, patch: Partial<Row>) {
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }
  function remove(key: string) {
    setRows((rs) => rs.filter((r) => r.key !== key));
  }

  // --- manual box on the drawing ---
  function rel(e: React.MouseEvent) {
    const r = imgRef.current!.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(e.clientX - r.left, r.width)),
      y: Math.max(0, Math.min(e.clientY - r.top, r.height)),
    };
  }
  function down(e: React.MouseEvent) { const p = rel(e); setDrag(p); setRect({ ...p, w: 0, h: 0 }); }
  function move(e: React.MouseEvent) {
    if (!drag) return;
    const p = rel(e);
    setRect({ x: Math.min(drag.x, p.x), y: Math.min(drag.y, p.y), w: Math.abs(p.x - drag.x), h: Math.abs(p.y - drag.y) });
  }

  function addManual() {
    const img = imgRef.current;
    if (!img || !rect || rect.w < 5 || rect.h < 5) return setError("Draw a box around one symbol first.");
    if (!manualName.trim()) return setError("Name the symbol you boxed.");
    setError(null);
    // display px -> original image px
    const sx = (rect.x * img.naturalWidth) / img.clientWidth;
    const sy = (rect.y * img.naturalHeight) / img.clientHeight;
    const sw = (rect.w * img.naturalWidth) / img.clientWidth;
    const sh = (rect.h * img.naturalHeight) / img.clientHeight;
    let preview = "";
    try {
      const c = document.createElement("canvas");
      c.width = Math.round(sw); c.height = Math.round(sh);
      c.getContext("2d")!.drawImage(img, sx, sy, sw, sh, 0, 0, c.width, c.height);
      preview = c.toDataURL("image/png");
    } catch { /* cross-origin: skip the thumbnail, the box still works */ }
    setRows((rs) => [
      ...rs,
      {
        key: `manual-${Date.now()}`,
        bbox: [Math.round(sx), Math.round(sy), Math.round(sw), Math.round(sh)],
        preview,
        selected: true,
        name: manualName.trim(),
        manual: true,
      },
    ]);
    setRect(null); setManualName("");
  }

  const selected = rows.filter((r) => r.selected);
  const allNamed = selected.every((r) => r.name.trim());

  async function confirm() {
    const chosen = rows.filter((r) => r.selected);
    if (chosen.length === 0) return setError("Add or select at least one symbol.");
    if (!chosen.every((r) => r.name.trim())) return setError("Give every selected symbol a name.");
    setError(null);
    setBusy(true);
    try {
      await confirmSymbols(
        props.project.id,
        props.drawing.id,
        chosen.map((r) => ({ bbox: r.bbox, sym_type: slugify(r.name), label: r.name.trim(), threshold: 0.7 })),
      );
      props.onContinue();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const noAuto = !loading && rows.every((r) => r.manual);

  return (
    <div className="modal-overlay" onClick={props.onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()} style={{ padding: 18, width: "min(820px, 96vw)", maxHeight: "92vh", overflow: "auto" }}>
        <h2 style={{ margin: "0 0 2px", fontSize: 18 }}>Confirm detected symbols</h2>
        <p className="muted" style={{ margin: "0 0 14px", fontSize: 13 }}>
          FlashPod auto-detects symbols from the drawing's legend and names them. If a drawing has
          no legend, draw a box around one of each symbol below. Uncheck any you don't want, then
          confirm — FlashPod counts every instance across the drawing.
        </p>

        {loading && <div className="muted" style={{ padding: 24, textAlign: "center" }}>Detecting symbols from the legend…</div>}
        {error && <div style={{ color: "var(--danger)", fontSize: 13, marginBottom: 10 }}>{error}</div>}

        {!loading && noAuto && (
          <div className="chip warn" style={{ fontSize: 12, marginBottom: 12 }}>
            No legend found on this drawing — draw a box around one example of each symbol below.
          </div>
        )}

        {/* symbol rows (auto + manual) */}
        {rows.length > 0 && (
          <div style={{ display: "grid", gap: 8, marginBottom: 14 }}>
            {rows.map((r) => (
              <div key={r.key} className="panel" style={{ padding: 10, display: "flex", alignItems: "center", gap: 12, opacity: r.selected ? 1 : 0.5 }}>
                <input type="checkbox" checked={r.selected} onChange={(e) => update(r.key, { selected: e.target.checked })} aria-label="Use this symbol" />
                {r.preview ? (
                  <img src={r.preview} alt="symbol" style={{ width: 40, height: 40, objectFit: "contain", background: "var(--sheet)", border: "1px solid var(--hairline)", borderRadius: 4, flexShrink: 0 }} />
                ) : (
                  <span style={{ width: 40, height: 40, display: "grid", placeItems: "center", background: "var(--sheet)", border: "1px solid var(--hairline)", borderRadius: 4, fontSize: 10 }} className="muted">box</span>
                )}
                <input value={r.name} disabled={!r.selected} onChange={(e) => update(r.key, { name: e.target.value })} placeholder="Name this symbol" style={{ marginLeft: "auto", width: 220 }} />
                {r.manual && <button onClick={() => remove(r.key)} title="Remove" style={{ padding: "2px 8px", fontSize: 12 }}>✕</button>}
              </div>
            ))}
          </div>
        )}

        {/* manual draw area */}
        <details open={noAuto} style={{ marginBottom: 8 }}>
          <summary style={{ cursor: "pointer", fontSize: 13, color: "var(--secondary)" }}>Add a symbol by hand</summary>
          <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
            <div style={{ background: "var(--sheet)", border: "1px solid var(--hairline)", borderRadius: 6, padding: 8, maxHeight: 360, overflow: "auto" }}>
              <div style={{ position: "relative", display: "inline-block", cursor: "crosshair", userSelect: "none", maxWidth: "100%" }}
                onMouseDown={down} onMouseMove={move} onMouseUp={() => setDrag(null)} onMouseLeave={() => setDrag(null)}>
                <img ref={imgRef} src={imageUrl} crossOrigin="anonymous" alt="Drawing" draggable={false} style={{ maxWidth: "100%", display: "block" }} />
                {rect && <div style={{ position: "absolute", left: rect.x, top: rect.y, width: rect.w, height: rect.h, border: "2px solid var(--accent)", background: "rgba(45,91,255,0.12)", pointerEvents: "none" }} />}
              </div>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <input value={manualName} onChange={(e) => setManualName(e.target.value)} placeholder="Name the boxed symbol (e.g. Duplex Receptacle)" style={{ flex: 1 }} />
              <button className="primary" onClick={addManual}>Add example</button>
            </div>
          </div>
        </details>

        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <button onClick={props.onClose}>Cancel</button>
          <button className="primary" style={{ marginLeft: "auto" }} disabled={busy || loading || selected.length === 0 || !allNamed} onClick={confirm}>
            {busy ? "Saving…" : `Confirm ${selected.length} symbol${selected.length === 1 ? "" : "s"} → Review`}
          </button>
        </div>
      </div>
    </div>
  );
}
