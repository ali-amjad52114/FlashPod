// Client-side proposal PDF (the backend's /proposal/export is a 501 stub today).
// Driven by the real TakeoffOut priced_items + the UI's labeled totals.
import { jsPDF } from "jspdf";
import { colorForType, computeTotals, money, sourceLabel } from "./lib";
import type { PricedItem } from "./types";

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
  pricedItems: PricedItem[];
  laborPct: number;
}): void {
  const { projectName, proposalNumber, pricedItems, laborPct } = opts;
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const W = doc.internal.pageSize.getWidth();
  const M = 54; // margin
  let y = 56;
  const date = new Date().toISOString().slice(0, 10);

  // --- Letterhead ---
  doc.setFont("helvetica", "bold").setFontSize(18).setTextColor(...INK);
  doc.text("FlashPod", M, y);
  doc.setFont("helvetica", "normal").setFontSize(9).setTextColor(...SECONDARY);
  doc.text("ELECTRICAL ESTIMATING", M, y + 14);

  doc.setFont("helvetica", "bold").setFontSize(13).setTextColor(...INK);
  doc.text("PROPOSAL", W - M, y, { align: "right" });
  doc.setFont("helvetica", "normal").setFontSize(9).setTextColor(...SECONDARY);
  doc.text(`No. ${proposalNumber}`, W - M, y + 14, { align: "right" });
  doc.text(date, W - M, y + 26, { align: "right" });

  y += 38;
  doc.setDrawColor(...ACCENT).setLineWidth(1.4).line(M, y, W - M, y);
  y += 22;

  // --- Meta grid ---
  doc.setFontSize(9);
  const metaRow = (label: string, value: string, col: number) => {
    const x = col === 0 ? M : W / 2;
    doc.setTextColor(...SECONDARY).text(label.toUpperCase(), x, y);
    doc.setTextColor(...INK).setFont("helvetica", "bold").text(value, x, y + 12);
    doc.setFont("helvetica", "normal");
  };
  metaRow("Project", projectName, 0);
  metaRow("Date", date, 1);
  y += 28;
  metaRow("Prepared for", "—", 0);
  metaRow("Sheet", "E-1", 1);
  y += 26;
  doc.setTextColor(...SECONDARY).setFontSize(8.5);
  doc.text("Budgetary electrical material takeoff generated from the marked-up drawing.", M, y);
  y += 22;

  // --- Takeoff table ---
  const cols = { item: M + 16, qty: W - M - 200, unit: W - M - 110, amt: W - M };
  doc.setFillColor(...INK).rect(M, y - 12, W - 2 * M, 18, "F");
  doc.setTextColor(255, 255, 255).setFont("helvetica", "bold").setFontSize(8.5);
  doc.text("ITEM", cols.item, y);
  doc.text("QTY", cols.qty, y, { align: "right" });
  doc.text("UNIT PRICE", cols.unit, y, { align: "right" });
  doc.text("AMOUNT", cols.amt, y, { align: "right" });
  y += 16;

  doc.setFont("helvetica", "normal");
  pricedItems.forEach((it, i) => {
    if (i % 2 === 1) {
      doc.setFillColor(248, 250, 252).rect(M, y - 11, W - 2 * M, 16, "F");
    }
    const [r, g, b] = hexToRgb(colorForType(it.type));
    doc.setFillColor(r, g, b).rect(M + 4, y - 8, 7, 7, "F"); // swatch
    doc.setTextColor(...INK).setFontSize(9);
    doc.text(it.label, cols.item, y);
    doc.text(String(it.quantity), cols.qty, y, { align: "right" });
    const live = sourceLabel(it.price_source).live ? "*" : "";
    doc.text(`${money(it.unit_price)}${live}`, cols.unit, y, { align: "right" });
    doc.text(money(it.total), cols.amt, y, { align: "right" });
    y += 16;
  });

  // --- Totals ---
  const { material, labor, grand } = computeTotals(pricedItems, laborPct);
  y += 6;
  doc.setDrawColor(...HAIRLINE).setLineWidth(0.6).line(W / 2, y, W - M, y);
  y += 16;
  const totalRow = (label: string, val: string, bold = false, accent = false) => {
    doc.setFont("helvetica", bold ? "bold" : "normal").setFontSize(bold ? 11 : 9);
    doc.setTextColor(...(accent ? ACCENT : INK));
    doc.text(label, W / 2, y);
    doc.text(`$${val}`, W - M, y, { align: "right" });
    y += bold ? 18 : 14;
  };
  totalRow("Material subtotal", money(material));
  totalRow(`Labor (est. ${laborPct}%)`, money(labor));
  doc.setDrawColor(...INK).setLineWidth(1).line(W / 2, y - 4, W - M, y - 4);
  y += 6;
  totalRow("TOTAL (USD)", money(grand), true, true);

  // --- Notes & terms ---
  y += 12;
  doc.setFont("helvetica", "bold").setFontSize(9).setTextColor(...INK).text("Notes & Terms", M, y);
  y += 14;
  doc.setFont("helvetica", "normal").setFontSize(8).setTextColor(...SECONDARY);
  const notes = [
    "1. Budgetary basis — quantities derived from automated symbol detection; verify before bid.",
    "2. Labor is an estimate applied as a percentage of material; adjust to local rates.",
    "3. Excludes permits, taxes, and items not shown on the provided drawing.",
    "4. Proposal valid for 30 days from the date above.",
  ];
  notes.forEach((n) => {
    doc.text(n, M, y, { maxWidth: W - 2 * M });
    y += 12;
  });

  // --- Signature + footer ---
  y += 18;
  doc.setDrawColor(...HAIRLINE).setLineWidth(0.6);
  doc.line(M, y, M + 200, y);
  doc.line(W - M - 200, y, W - M, y);
  doc.setFontSize(8).setTextColor(...SECONDARY);
  doc.text("Prepared by", M, y + 11);
  doc.text("Accepted by / Date", W - M - 200, y + 11);

  const footY = doc.internal.pageSize.getHeight() - 40;
  doc.setDrawColor(...HAIRLINE).line(M, footY, W - M, footY);
  doc.setFontSize(7.5).setTextColor(...SECONDARY);
  doc.text("FlashPod · electrical estimating", M, footY + 12);
  doc.text(
    "Counts via template matching — verify before issuing for bid.   * live market price via Bright Data",
    W - M,
    footY + 12,
    { align: "right" },
  );

  doc.save(`${projectName.replace(/[^a-z0-9]+/gi, "_") || "proposal"}.pdf`);
}
