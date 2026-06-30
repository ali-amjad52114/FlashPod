// Client-side proposal PDF (the backend's /proposal/export is a 501 stub).
// Driven by the reviewed line items + contingency.
import { jsPDF } from "jspdf";
import { colorForType, money, sourceLabel } from "./lib";
import { computeTotals, type ReviewLineItem } from "./review";

const ACCENT: [number, number, number] = [45, 91, 255];
const INK: [number, number, number] = [22, 25, 29];
const SECONDARY: [number, number, number] = [90, 99, 110];
const HAIRLINE: [number, number, number] = [216, 222, 230];

function hexToRgb(hex: string): [number, number, number] {
  const m = hex.replace("#", "");
  return [parseInt(m.slice(0, 2), 16), parseInt(m.slice(2, 4), 16), parseInt(m.slice(4, 6), 16)];
}

export function exportProposalPdf(opts: {
  projectName: string;
  proposalNumber: string;
  items: ReviewLineItem[];
  contingencyPct: number;
}): void {
  const { projectName, proposalNumber, items, contingencyPct } = opts;
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const W = doc.internal.pageSize.getWidth();
  const M = 54;
  let y = 56;
  const date = new Date().toISOString().slice(0, 10);

  doc.setFont("helvetica", "bold").setFontSize(18).setTextColor(...INK).text("FlashPod", M, y);
  doc.setFont("helvetica", "normal").setFontSize(9).setTextColor(...SECONDARY).text("ELECTRICAL ESTIMATING", M, y + 14);
  doc.setFont("helvetica", "bold").setFontSize(13).setTextColor(...INK).text("PROPOSAL", W - M, y, { align: "right" });
  doc.setFont("helvetica", "normal").setFontSize(9).setTextColor(...SECONDARY);
  doc.text(`No. ${proposalNumber}`, W - M, y + 14, { align: "right" });
  doc.text(date, W - M, y + 26, { align: "right" });

  y += 38;
  doc.setDrawColor(...ACCENT).setLineWidth(1.4).line(M, y, W - M, y);
  y += 20;

  doc.setFontSize(9).setTextColor(...SECONDARY).text("PROJECT", M, y);
  doc.setTextColor(...INK).setFont("helvetica", "bold").text(projectName, M, y + 12);
  doc.setFont("helvetica", "normal").setTextColor(...SECONDARY).text("Sheet E-1 · budgetary", W - M, y + 12, { align: "right" });
  y += 30;
  doc.setFontSize(8.5).setTextColor(...SECONDARY).text("First-pass electrical material takeoff from the marked-up drawing; reviewed by the estimator.", M, y);
  y += 20;

  // table header
  const cols = { item: M + 16, qty: W - M - 200, unit: W - M - 110, amt: W - M };
  doc.setFillColor(...INK).rect(M, y - 12, W - 2 * M, 18, "F");
  doc.setTextColor(255, 255, 255).setFont("helvetica", "bold").setFontSize(8.5);
  doc.text("ITEM", cols.item, y);
  doc.text("QTY", cols.qty, y, { align: "right" });
  doc.text("UNIT", cols.unit, y, { align: "right" });
  doc.text("MATERIAL", cols.amt, y, { align: "right" });
  y += 16;

  doc.setFont("helvetica", "normal");
  items.forEach((it, i) => {
    if (i % 2 === 1) doc.setFillColor(248, 250, 252).rect(M, y - 11, W - 2 * M, 16, "F");
    const [r, g, b] = hexToRgb(colorForType(it.type));
    doc.setFillColor(r, g, b).rect(M + 4, y - 8, 7, 7, "F");
    doc.setTextColor(...INK).setFontSize(9).text(it.label, cols.item, y);
    doc.text(String(it.quantity), cols.qty, y, { align: "right" });
    doc.text(`${money(it.unit_price)}${sourceLabel(it.price_source).live ? "*" : ""}`, cols.unit, y, { align: "right" });
    doc.text(money(it.total), cols.amt, y, { align: "right" });
    y += 16;
  });

  // totals
  const { material, contingency, total } = computeTotals(items, contingencyPct);
  y += 6;
  doc.setDrawColor(...HAIRLINE).setLineWidth(0.6).line(W / 2, y, W - M, y);
  y += 16;
  const row = (label: string, val: string, bold = false, accent = false) => {
    doc.setFont("helvetica", bold ? "bold" : "normal").setFontSize(bold ? 11 : 9).setTextColor(...(accent ? ACCENT : INK));
    doc.text(label, W / 2, y);
    doc.text(`$${val}`, W - M, y, { align: "right" });
    y += bold ? 18 : 14;
  };
  row("Material subtotal", money(material));
  row(`Contingency (${contingencyPct}%)`, money(contingency));
  doc.setDrawColor(...INK).setLineWidth(1).line(W / 2, y - 4, W - M, y - 4);
  y += 6;
  row("Estimated Total (USD)", money(total), true, true);

  // notes
  y += 12;
  doc.setFont("helvetica", "bold").setFontSize(9).setTextColor(...INK).text("Assumptions & Exclusions", M, y);
  y += 14;
  doc.setFont("helvetica", "normal").setFontSize(8).setTextColor(...SECONDARY);
  [
    "1. Budgetary basis — quantities from OpenCV template matching, reviewed before issue; verify before bid.",
    "2. Contingency is an estimator input applied to material subtotal.",
    "3. Excludes labor, permits, taxes, and devices not shown on the drawing.",
    "4. Proposal valid for 30 days.",
  ].forEach((n) => { doc.text(n, M, y, { maxWidth: W - 2 * M }); y += 12; });

  const footY = doc.internal.pageSize.getHeight() - 38;
  doc.setDrawColor(...HAIRLINE).line(M, footY, W - M, footY);
  doc.setFontSize(7.5).setTextColor(...SECONDARY);
  doc.text("FlashPod · first-pass takeoff · estimator-in-the-loop", M, footY + 12);
  doc.text("Counts via template matching — verify before issuing for bid.   * live price", W - M, footY + 12, { align: "right" });

  doc.save(`${projectName.replace(/[^a-z0-9]+/gi, "_") || "proposal"}.pdf`);
}
