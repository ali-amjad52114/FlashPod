// CSV / JSON export of the reviewed takeoff.
import type { ReviewLineItem } from "./review";

function download(name: string, mime: string, data: string) {
  const url = URL.createObjectURL(new Blob([data], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function slug(s: string): string {
  return s.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "takeoff";
}

function csvCell(s: string): string {
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function exportCsv(projectName: string, items: ReviewLineItem[]) {
  const rows = [["Item", "Type", "Quantity", "Unit Price", "Material Total", "Reviewed"]];
  for (const it of items) {
    rows.push([
      it.label,
      it.type,
      String(it.quantity),
      it.unit_price.toFixed(2),
      it.total.toFixed(2),
      it.reviewed ? "yes" : "no",
    ]);
  }
  download(`${slug(projectName)}.csv`, "text/csv", rows.map((r) => r.map(csvCell).join(",")).join("\n"));
}

export function exportJson(
  projectName: string,
  items: ReviewLineItem[],
  totals: { material: number; contingency: number; total: number },
) {
  const payload = {
    project_name: projectName,
    generated_at: new Date().toISOString(),
    line_items: items.map((it) => ({
      type: it.type,
      label: it.label,
      quantity: it.quantity,
      unit_price: it.unit_price,
      material_total: it.total,
      price_source: it.price_source,
      reviewed: it.reviewed,
      boxes: it.boxes,
    })),
    totals,
  };
  download(`${slug(projectName)}.json`, "application/json", JSON.stringify(payload, null, 2));
}
