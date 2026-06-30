import { useState } from "react";
import { DrawingCanvas } from "./DrawingCanvas";
import { activeDetections, computeTotals, deriveLineItems, type ReviewModel } from "../review";
import { colorForType, money } from "../lib";
import { exportCsv, exportJson } from "../exports";
import { exportProposalPdf } from "../pdf";
import type { Takeoff } from "../types";

export function ProposalPage(props: {
  projectName: string;
  imageUrl: string;
  takeoff: Takeoff;
  model: ReviewModel;
  contingencyPct: number;
  onContingency: (n: number) => void;
  onBack: () => void;
}) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const items = deriveLineItems(props.model);
  const totals = computeTotals(items, props.contingencyPct);
  const active = activeDetections(props.model);
  const proposalNo = `FP-${String(props.takeoff.id || Date.now() % 100000).padStart(5, "0")}`;

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 22, margin: "0 0 2px" }}>Quantity Takeoff &amp; Proposal</h1>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>Every quantity links back to the drawing evidence.</p>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button onClick={props.onBack}>← Back to Review</button>
          <button onClick={() => exportCsv(props.projectName, items)}>Export CSV</button>
          <button onClick={() => exportJson(props.projectName, items, totals)}>Export JSON</button>
          <button className="primary" onClick={() => exportProposalPdf({ projectName: props.projectName, proposalNumber: proposalNo, items, contingencyPct: props.contingencyPct })}>Download PDF</button>
        </div>
      </div>

      <div className="two-col">
        {/* drawing evidence */}
        <div className="panel" style={{ padding: 12 }}>
          <DrawingCanvas imageUrl={props.imageUrl} imageSize={props.takeoff.image_size!} detections={active} selectedType={selectedType} onPickType={setSelectedType} />
        </div>

        {/* takeoff table + proposal */}
        <div style={{ display: "grid", gap: 14 }}>
          <div className="panel" style={{ padding: 12, overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--secondary)", fontSize: 11 }}>
                  <th style={{ padding: "6px 8px" }}>ITEM</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>QTY</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>UNIT</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>MATERIAL</th>
                  <th style={{ padding: "6px 8px" }}>STATUS</th>
                  <th style={{ padding: "6px 8px" }}></th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => {
                  const sel = selectedType === it.type;
                  return (
                    <tr key={it.type} onClick={() => setSelectedType(sel ? null : it.type)} style={{ cursor: "pointer", borderTop: "1px solid var(--hairline)", background: sel ? "rgba(45,91,255,0.07)" : undefined }}>
                      <td style={{ padding: "8px" }}>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                          <span style={{ width: 11, height: 11, borderRadius: 3, background: colorForType(it.type) }} />
                          {it.label}
                        </span>
                      </td>
                      <td className="mono" style={{ padding: "8px", textAlign: "right" }}>{it.quantity}</td>
                      <td className="mono" style={{ padding: "8px", textAlign: "right" }}>${money(it.unit_price)}</td>
                      <td className="mono" style={{ padding: "8px", textAlign: "right" }}>${money(it.total)}</td>
                      <td style={{ padding: "8px" }}>
                        {it.reviewed ? <span className="chip" style={{ fontSize: 10, padding: "1px 6px" }}>reviewed</span>
                          : it.lowConf > 0 ? <span className="chip warn" style={{ fontSize: 10, padding: "1px 6px" }}>{it.lowConf} low-conf</span>
                          : <span className="muted" style={{ fontSize: 11 }}>ok</span>}
                      </td>
                      <td style={{ padding: "8px", textAlign: "right" }}>
                        <button onClick={(e) => { e.stopPropagation(); setSelectedType(it.type); }} style={{ padding: "3px 10px", fontSize: 12 }}>Trace</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* proposal document */}
          <div className="panel" style={{ padding: 16, display: "grid", gap: 12 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>FlashPod Electrical Proposal</div>
              <div className="mono muted" style={{ fontSize: 11 }}>{proposalNo} · {props.projectName} · {new Date().toLocaleDateString()}</div>
            </div>

            <Section title="Scope of Work">
              First-pass electrical material takeoff generated from the marked-up drawing and reviewed by the estimator.
              Quantities reflect detected device counts after review.
            </Section>

            <Section title="Quantity Takeoff">
              {items.length} item type{items.length === 1 ? "" : "s"}, {active.length} devices total. See the table above; every line traces to the drawing.
            </Section>

            <Section title="Material Pricing">
              <div style={{ display: "grid", gap: 4 }}>
                <Line label="Material subtotal" value={`$${money(totals.material)}`} />
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="muted" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    Contingency (
                    <input type="number" min={0} max={100} value={props.contingencyPct} onChange={(e) => props.onContingency(parseFloat(e.target.value) || 0)} style={{ width: 52, padding: "3px 6px" }} aria-label="Contingency percent" />
                    %)
                  </span>
                  <span className="mono" style={{ marginLeft: "auto" }}>${money(totals.contingency)}</span>
                </div>
                <div style={{ borderTop: "1px solid var(--ink)", paddingTop: 6, display: "flex", fontWeight: 700 }}>
                  <span style={{ color: "var(--accent)" }}>Estimated Total (USD)</span>
                  <span className="mono" style={{ marginLeft: "auto", color: "var(--accent)" }}>${money(totals.total)}</span>
                </div>
              </div>
            </Section>

            <Section title="Assumptions">
              Budgetary estimate. Material prices are list/fallback unless marked from a live source. Contingency is an estimator input.
            </Section>
            <Section title="Exclusions">
              Labor, permits, taxes, and any devices not shown on the provided drawing. Counts via OpenCV template matching — verify before issuing for bid.
            </Section>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section(props: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--secondary)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 3 }}>{props.title}</div>
      <div style={{ fontSize: 13 }}>{props.children}</div>
    </div>
  );
}

function Line(props: { label: string; value: string }) {
  return (
    <div style={{ display: "flex" }}>
      <span className="muted">{props.label}</span>
      <span className="mono" style={{ marginLeft: "auto" }}>{props.value}</span>
    </div>
  );
}
