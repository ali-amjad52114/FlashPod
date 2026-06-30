// Small shared helpers: stable per-type colors, totals, formatting, slugs.
import type { PriceSource, PricedItem } from "./types";

// Functional symbol-type colors — reused everywhere a type appears
// (legend, table chip, box overlay, PDF swatch). Stable per `type`.
const KNOWN_COLORS: Record<string, string> = {
  duplex_outlet: "#E8833A",
  light: "#7C5CFF",
  light_fixture: "#7C5CFF",
  switch: "#159C8C",
  panel: "#E0475B",
  junction_box: "#3B82C4",
  data_drop: "#3B82C4",
  gfci_outlet: "#C2410C",
};

const PALETTE = ["#E8833A", "#7C5CFF", "#159C8C", "#E0475B", "#3B82C4", "#B45309", "#0E7490", "#9333EA"];

export function colorForType(type: string): string {
  if (KNOWN_COLORS[type]) return KNOWN_COLORS[type];
  let h = 0;
  for (let i = 0; i < type.length; i++) h = (h * 31 + type.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

// slugify a human label into a sym_type key, e.g. "Duplex Outlet" -> "duplex_outlet"
export function slugify(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "symbol";
}

export function money(n: number): string {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function materialSubtotal(items: PricedItem[]): number {
  return round2(items.reduce((s, it) => s + (it.total || 0), 0));
}

export function round2(n: number): number {
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

// Labor is a UI-side, clearly-labeled estimate (the backend doesn't return it).
// It's a simple policy % of the material subtotal — NOT a material price lookup.
export function computeTotals(items: PricedItem[], laborPct: number) {
  const material = materialSubtotal(items);
  const labor = round2((material * laborPct) / 100);
  return { material, labor, grand: round2(material + labor) };
}

export function sourceLabel(src?: PriceSource): { text: string; live: boolean } {
  switch (src) {
    case "brightdata":
      return { text: "Live · Bright Data", live: true };
    case "manual":
      return { text: "Manual override", live: false };
    case "static":
    case "fallback":
    default:
      return { text: "List price", live: false };
  }
}

export function symbolCount(items: PricedItem[] | null | undefined): number {
  return (items ?? []).reduce((s, it) => s + (it.quantity || 0), 0);
}
