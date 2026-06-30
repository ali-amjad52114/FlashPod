import { useState } from "react";
import { correctItem } from "../api";
import { colorForType, computeTotals, money, sourceLabel } from "../lib";
import type { PricedItem, Takeoff } from "../types";

export function LineItemTable(props: {
  takeoff: Takeoff;
  selectedType: string | null;
  onSelectType: (t: string | null) => void;
  laborPct: number;
  onLaborPct: (n: number) => void;
  onTakeoffUpdate: (t: Takeoff) => void;
}) {
  const items = props.takeoff.priced_items ?? [];
  const [editing, setEditing] = useState<string | null>(null);
  const [qty, setQty] = useState(0);
  const [unit, setUnit] = useState(0);
  const [busy, setBusy] = useState(false);
  const { material, labor, grand } = computeTotals(items, props.laborPct);

  function startEdit(it: PricedItem) {
    setEditing(it.type);
    setQty(it.quantity);
    setUnit(it.unit_price);
  }

  async function save(symType: string) {
    setBusy(true);
    try {
      const updated = await correctItem(props.takeoff.id, symType, { quantity: qty, unit_price: unit });
      props.onTakeoffUpdate(updated);
      setEditing(null);
    } catch (e) {
      alert(`Correction failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--secondary)", fontSize: 11 }}>
            <th style={{ padding: "6px 8px" }}>ITEM</th>
            <th style={{ padding: "6px 8px", textAlign: "right" }}>QTY</th>
            <th style={{ padding: "6px 8px", textAlign: "right" }}>UNIT</th>
            <th style={{ padding: "6px 8px", textAlign: "right" }}>TOTAL</th>
            <th style={{ padding: "6px 8px" }}></th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => {
            const sel = props.selectedType === it.type;
            const src = sourceLabel(it.price_source);
            const isEditing = editing === it.type;
            return (
              <tr
                key={it.type}
                onClick={() => props.onSelectType(sel ? null : it.type)}
                style={{ cursor: "pointer", background: sel ? "rgba(45,91,255,0.07)" : undefined, borderTop: "1px solid var(--hairline)" }}
              >
                <td style={{ padding: "8px" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 11, height: 11, borderRadius: 3, background: colorForType(it.type) }} />
                    <span>{it.label}</span>
                  </span>
                  <div style={{ marginTop: 2 }}>
                    {it.source_url ? (
                      <a href={it.source_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} style={{ fontSize: 10 }}>
                        {src.text}{it.vendor ? ` · ${it.vendor}` : ""}
                      </a>
                    ) : (
                      <span className="muted" style={{ fontSize: 10 }}>{src.text}</span>
                    )}
                  </div>
                </td>
                <td className="mono" style={{ padding: "8px", textAlign: "right" }}>
                  {isEditing ? (
                    <input type="number" min={0} value={qty} onClick={(e) => e.stopPropagation()} onChange={(e) => setQty(parseInt(e.target.value) || 0)} style={{ width: 64, textAlign: "right" }} />
                  ) : (
                    it.quantity
                  )}
                </td>
                <td className="mono" style={{ padding: "8px", textAlign: "right" }}>
                  {isEditing ? (
                    <input type="number" min={0} step={0.01} value={unit} onClick={(e) => e.stopPropagation()} onChange={(e) => setUnit(parseFloat(e.target.value) || 0)} style={{ width: 72, textAlign: "right" }} />
                  ) : (
                    <>${money(it.unit_price)}{src.live ? "*" : ""}</>
                  )}
                </td>
                <td className="mono" style={{ padding: "8px", textAlign: "right" }}>${money(it.total)}</td>
                <td style={{ padding: "8px", textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                  {isEditing ? (
                    <span style={{ display: "inline-flex", gap: 4 }}>
                      <button disabled={busy} onClick={() => save(it.type)} style={{ padding: "3px 8px" }}>Save</button>
                      <button disabled={busy} onClick={() => setEditing(null)} style={{ padding: "3px 8px" }}>×</button>
                    </span>
                  ) : (
                    <button onClick={() => startEdit(it)} style={{ padding: "3px 8px", fontSize: 12 }}>Edit</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="panel" style={{ padding: 12, display: "grid", gap: 6, fontSize: 13 }}>
        <Row label="Material subtotal" value={`$${money(material)}`} />
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="muted" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            Labor (est.
            <input
              type="number"
              min={0}
              max={200}
              value={props.laborPct}
              onChange={(e) => props.onLaborPct(parseFloat(e.target.value) || 0)}
              style={{ width: 54, padding: "3px 6px" }}
              aria-label="Labor percent"
            />
            %)
          </span>
          <span className="mono" style={{ marginLeft: "auto" }}>${money(labor)}</span>
        </div>
        <div style={{ borderTop: "1px solid var(--ink)", paddingTop: 6, display: "flex", fontWeight: 700 }}>
          <span style={{ color: "var(--accent)" }}>TOTAL (USD)</span>
          <span className="mono" style={{ marginLeft: "auto", color: "var(--accent)" }}>${money(grand)}</span>
        </div>
        <span className="muted" style={{ fontSize: 10 }}>Labor is a UI estimate (% of material) — the backend prices materials only.</span>
      </div>
    </div>
  );
}

function Row(props: { label: string; value: string }) {
  return (
    <div style={{ display: "flex" }}>
      <span className="muted">{props.label}</span>
      <span className="mono" style={{ marginLeft: "auto" }}>{props.value}</span>
    </div>
  );
}
