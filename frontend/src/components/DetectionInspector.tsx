import { correctItem } from "../api";
import { colorForType } from "../lib";
import { LOW_CONF, activeDetections, deriveLineItems, lowConfidenceCount, type ReviewModel } from "../review";

export function DetectionInspector(props: {
  takeoffId: number;
  model: ReviewModel;
  selectedId: string | null;
  selectedType: string | null;
  addType: string | null;
  onAddType: (t: string | null) => void;
  onPickType: (t: string | null) => void;
  onChange: (m: ReviewModel) => void;
}) {
  const { model } = props;
  const items = deriveLineItems(model);
  const active = activeDetections(model);
  const excluded = model.detections.filter((d) => d.excluded);
  const allTypes = Array.from(new Set([...model.detections.map((d) => d.type), ...Object.keys(model.labelByType)]));
  const sel = props.selectedId ? model.detections.find((d) => d.id === props.selectedId) : null;

  function update(detections = model.detections, extra: Partial<ReviewModel> = {}) {
    props.onChange({ ...model, detections, ...extra });
  }
  function exclude(id: string) { update(model.detections.map((d) => (d.id === id ? { ...d, excluded: true } : d))); }
  function restore(id: string) { update(model.detections.map((d) => (d.id === id ? { ...d, excluded: false } : d))); }
  function retype(id: string, t: string) {
    update(model.detections.map((d) => (d.id === id ? { ...d, type: t, label: model.labelByType[t] ?? t } : d)));
  }
  function setPrice(type: string, price: number) {
    props.onChange({ ...model, unitPriceByType: { ...model.unitPriceByType, [type]: price }, sourceByType: { ...model.sourceByType, [type]: "manual" } });
  }
  async function persistPrice(type: string, price: number) {
    if (props.takeoffId > 0) { try { await correctItem(props.takeoffId, type, { unit_price: price }); } catch { /* best-effort */ } }
  }

  return (
    <div style={{ display: "grid", gap: 14 }}>
      {/* summary chips */}
      <div className="chips">
        <span className="chip"><b className="mono">{active.length}</b> devices found</span>
        <span className="chip"><b className="mono">{items.length}</b> item types</span>
        <span className={`chip${lowConfidenceCount(model) ? " warn" : ""}`}><b className="mono">{lowConfidenceCount(model)}</b> low-confidence</span>
      </div>

      {/* add missing item */}
      <div className="panel" style={{ padding: 12, display: "grid", gap: 8 }}>
        <span style={{ fontSize: 12, color: "var(--secondary)" }}>Add a missed device</span>
        <div style={{ display: "flex", gap: 8 }}>
          <select value={props.addType ?? ""} onChange={(e) => props.onAddType(e.target.value || null)} style={{ flex: 1 }}>
            <option value="">Choose type…</option>
            {allTypes.map((t) => <option key={t} value={t}>{model.labelByType[t] ?? t}</option>)}
          </select>
          {props.addType ? <button onClick={() => props.onAddType(null)}>Stop</button> : <span className="muted" style={{ fontSize: 11, alignSelf: "center" }}>then drag on drawing</span>}
        </div>
      </div>

      {/* selected detection */}
      {sel && (
        <div className="panel" style={{ padding: 12, display: "grid", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 11, height: 11, borderRadius: 3, background: colorForType(sel.type) }} />
            <b>{sel.label}</b>
            <span className="mono muted" style={{ marginLeft: "auto", fontSize: 12 }}>{(sel.confidence * 100).toFixed(0)}%{sel.manual ? " · manual" : ""}</span>
          </div>
          <div className="mono muted" style={{ fontSize: 11 }}>x {sel.x} · y {sel.y} · {sel.w}×{sel.h}px</div>
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ fontSize: 11, color: "var(--secondary)" }}>Change type</span>
            <select value={sel.type} onChange={(e) => retype(sel.id, e.target.value)}>
              {allTypes.map((t) => <option key={t} value={t}>{model.labelByType[t] ?? t}</option>)}
            </select>
          </label>
          <button onClick={() => exclude(sel.id)} style={{ color: "var(--danger)" }}>Exclude false positive</button>
        </div>
      )}

      {/* item types list */}
      <div className="panel" style={{ padding: 12, display: "grid", gap: 6 }}>
        <span style={{ fontSize: 12, color: "var(--secondary)" }}>Item types — click to trace on drawing</span>
        {items.map((it) => {
          const selRow = props.selectedType === it.type;
          return (
            <div key={it.type} onClick={() => props.onPickType(selRow ? null : it.type)}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 4px", borderRadius: 6, cursor: "pointer", background: selRow ? "rgba(45,91,255,0.08)" : undefined }}>
              <span style={{ width: 11, height: 11, borderRadius: 3, background: colorForType(it.type) }} />
              <span style={{ fontSize: 13 }}>{it.label}</span>
              {it.lowConf > 0 && <span className="chip warn" style={{ fontSize: 10, padding: "1px 6px" }}>{it.lowConf} low</span>}
              <span className="mono" style={{ marginLeft: "auto", fontSize: 13 }}>×{it.quantity}</span>
              <span onClick={(e) => e.stopPropagation()} style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
                <span className="muted">$</span>
                <input type="number" min={0} step={0.01} value={model.unitPriceByType[it.type] ?? 0}
                  onChange={(e) => setPrice(it.type, parseFloat(e.target.value) || 0)}
                  onBlur={(e) => persistPrice(it.type, parseFloat(e.target.value) || 0)}
                  style={{ width: 70, textAlign: "right", padding: "3px 6px" }} />
              </span>
            </div>
          );
        })}
      </div>

      {/* excluded */}
      {excluded.length > 0 && (
        <div className="panel" style={{ padding: 12, display: "grid", gap: 6 }}>
          <span style={{ fontSize: 12, color: "var(--secondary)" }}>Excluded ({excluded.length})</span>
          {excluded.map((d) => (
            <div key={d.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
              <span style={{ width: 10, height: 10, borderRadius: 3, background: colorForType(d.type), opacity: 0.5 }} />
              <span className="muted">{d.label}</span>
              <span className="mono muted" style={{ fontSize: 11 }}>{(d.confidence * 100).toFixed(0)}%</span>
              <button onClick={() => restore(d.id)} style={{ marginLeft: "auto", padding: "2px 8px", fontSize: 12 }}>Restore</button>
            </div>
          ))}
        </div>
      )}

      <p className="muted" style={{ fontSize: 11, margin: 0 }}>Low-confidence = below {Math.round(LOW_CONF * 100)}%. Estimator-in-the-loop: corrections here flow into the takeoff &amp; proposal.</p>
    </div>
  );
}
