import { useEffect, useState } from "react";
import { autoDetectSymbols, confirmSymbols, type SymbolCandidate } from "../api";
import { slugify } from "../lib";
import type { Drawing, Project } from "../types";

interface Row {
  cand: SymbolCandidate;
  selected: boolean;
  name: string;
}

// "Select symbol examples" — FlashPod auto-detects the legend glyphs; the user
// just unchecks false positives, names each symbol, and confirms.
export function SymbolSetupModal(props: {
  project: Project;
  drawing: Drawing;
  onContinue: () => void;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    autoDetectSymbols(props.project.id, props.drawing.id)
      .then((res) => {
        if (!alive) return;
        setRows(res.candidates.map((c) => ({ cand: c, selected: true, name: "" })));
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

  function update(i: number, patch: Partial<Row>) {
    setRows((rs) => (rs ? rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)) : rs));
  }

  const selected = rows?.filter((r) => r.selected) ?? [];
  const allNamed = selected.every((r) => r.name.trim());

  async function confirm() {
    if (!rows) return;
    const chosen = rows.filter((r) => r.selected);
    if (chosen.length === 0) return setError("Select at least one symbol.");
    if (!chosen.every((r) => r.name.trim())) return setError("Give every selected symbol a name.");
    setError(null);
    setBusy(true);
    try {
      await confirmSymbols(
        props.project.id,
        props.drawing.id,
        chosen.map((r) => ({
          bbox: r.cand.bbox,
          sym_type: slugify(r.name),
          label: r.name.trim(),
          threshold: 0.7,
        })),
      );
      props.onContinue();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={props.onClose}>
      <div
        className="panel"
        onClick={(e) => e.stopPropagation()}
        style={{ padding: 18, width: "min(760px, 96vw)", maxHeight: "92vh", overflow: "auto" }}
      >
        <h2 style={{ margin: "0 0 2px", fontSize: 18 }}>Confirm detected symbols</h2>
        <p className="muted" style={{ margin: "0 0 14px", fontSize: 13 }}>
          FlashPod auto-detected these symbols from the drawing's legend. Uncheck any that
          aren't symbols, name each one, then confirm — FlashPod counts every instance across
          the drawing.
        </p>

        {loading && (
          <div className="muted" style={{ padding: 28, textAlign: "center" }}>
            Detecting symbols from the legend…
          </div>
        )}
        {error && (
          <div style={{ color: "var(--danger)", fontSize: 13, marginBottom: 10 }}>{error}</div>
        )}

        {rows && rows.length === 0 && !loading && (
          <div className="muted" style={{ padding: 16 }}>
            No legend symbols were detected automatically on this drawing.
          </div>
        )}

        {rows && rows.length > 0 && (
          <div style={{ display: "grid", gap: 8 }}>
            {rows.map((r, i) => (
              <div
                key={r.cand.index}
                className="panel"
                style={{
                  padding: 10,
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  opacity: r.selected ? 1 : 0.5,
                }}
              >
                <input
                  type="checkbox"
                  checked={r.selected}
                  onChange={(e) => update(i, { selected: e.target.checked })}
                  aria-label="Use this symbol"
                />
                <img
                  src={`data:image/png;base64,${r.cand.glyph_base64}`}
                  alt="symbol glyph"
                  style={{
                    width: 40,
                    height: 40,
                    objectFit: "contain",
                    background: "var(--sheet)",
                    border: "1px solid var(--hairline)",
                    borderRadius: 4,
                    flexShrink: 0,
                  }}
                />
                <img
                  src={`data:image/png;base64,${r.cand.label_base64}`}
                  alt="legend label"
                  title="Legend label from the drawing"
                  style={{ height: 26, objectFit: "contain", maxWidth: 170 }}
                />
                <input
                  value={r.name}
                  disabled={!r.selected}
                  onChange={(e) => update(i, { name: e.target.value })}
                  placeholder="Name this symbol"
                  style={{ marginLeft: "auto", width: 200 }}
                />
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <button onClick={props.onClose}>Cancel</button>
          <button
            className="primary"
            style={{ marginLeft: "auto" }}
            disabled={busy || loading || selected.length === 0 || !allNamed}
            onClick={confirm}
          >
            {busy
              ? "Saving…"
              : `Confirm ${selected.length} symbol${selected.length === 1 ? "" : "s"} → Review`}
          </button>
        </div>
      </div>
    </div>
  );
}
