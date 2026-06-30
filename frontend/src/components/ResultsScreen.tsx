import { useState } from "react";
import { exportProposalPdf } from "../pdf";
import { DrawingCanvas } from "./DrawingCanvas";
import { LineItemTable } from "./LineItemTable";
import { ProposalPanel } from "./ProposalPanel";
import type { Takeoff } from "../types";

export function ResultsScreen(props: {
  takeoff: Takeoff;
  projectName: string;
  imageUrl: string;
  laborPct: number;
  onLaborPct: (n: number) => void;
  onTakeoffUpdate: (t: Takeoff) => void;
  onNew: () => void;
  onAdjust: () => void;
}) {
  const { takeoff } = props;
  const [tab, setTab] = useState<"table" | "proposal">("table");
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const detections = takeoff.detections ?? [];
  const total = detections.length;
  const shown = selectedType ? detections.filter((d) => d.type === selectedType).length : total;
  const selLabel = selectedType ? detections.find((d) => d.type === selectedType)?.label ?? selectedType : "";

  if (takeoff.status === "error") {
    return (
      <div className="panel" style={{ padding: 24, maxWidth: 560, margin: "40px auto" }}>
        <h2 style={{ marginTop: 0 }}>This takeoff errored</h2>
        <div style={{ color: "var(--danger)", fontFamily: "var(--mono)", fontSize: 13 }}>{takeoff.error}</div>
        <button className="primary" style={{ marginTop: 16 }} onClick={props.onNew}>New takeoff</button>
      </div>
    );
  }

  if (!takeoff.image_size) {
    return <div className="muted" style={{ padding: 24 }}>No image metadata — cannot render overlays.</div>;
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(340px, 1fr)", gap: 20, alignItems: "start" }}>
      {/* Drawing — the hero */}
      <div className="panel" style={{ padding: 12, position: "relative" }}>
        {selectedType && (
          <div
            className="badge"
            style={{ position: "absolute", top: 18, left: 18, zIndex: 2, background: "var(--ink)", color: "#fff", border: "none" }}
          >
            showing <span className="mono">{shown}</span> of <span className="mono">{total}</span> · {selLabel}
            <button
              onClick={() => setSelectedType(null)}
              style={{ background: "none", border: "none", color: "#fff", padding: "0 2px", marginLeft: 4 }}
              aria-label="Clear selection"
            >
              ×
            </button>
          </div>
        )}
        <DrawingCanvas
          imageUrl={props.imageUrl}
          imageSize={takeoff.image_size}
          detections={detections}
          selectedType={selectedType}
          onSelectType={setSelectedType}
        />
      </div>

      {/* Right panel */}
      <div style={{ display: "grid", gap: 14 }}>
        <div style={{ display: "flex", gap: 6 }}>
          <button className={tab === "table" ? "primary" : ""} onClick={() => setTab("table")}>Takeoff</button>
          <button className={tab === "proposal" ? "primary" : ""} onClick={() => setTab("proposal")}>Proposal</button>
        </div>

        {tab === "table" ? (
          <LineItemTable
            takeoff={takeoff}
            selectedType={selectedType}
            onSelectType={setSelectedType}
            laborPct={props.laborPct}
            onLaborPct={props.onLaborPct}
            onTakeoffUpdate={props.onTakeoffUpdate}
          />
        ) : (
          <ProposalPanel proposal={takeoff.proposal} />
        )}

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button onClick={props.onAdjust}>Adjust symbols</button>
          <button onClick={props.onNew}>New</button>
          <button
            className="primary"
            style={{ marginLeft: "auto" }}
            onClick={() =>
              exportProposalPdf({
                projectName: props.projectName,
                proposalNumber: `FP-${String(takeoff.id).padStart(5, "0")}`,
                pricedItems: takeoff.priced_items ?? [],
                laborPct: props.laborPct,
              })
            }
          >
            Create PDF
          </button>
        </div>
      </div>
    </div>
  );
}
