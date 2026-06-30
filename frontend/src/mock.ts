// Client-side mock drawing + takeoff so the app is demoable WITHOUT a live
// Runpod worker (e.g. zero credits). Clearly a sample — never presented as real.
// Produces a synthetic SVG "drawing" with glyphs and detections aligned to them.
import { colorForType } from "./lib";
import type { Detection, PricedItem, Takeoff } from "./types";

const W = 1000;
const H = 700;
const BOX = 22;

type Shape = "circle" | "square" | "triangle" | "rect";

const PLAN: { type: string; label: string; n: number; shape: Shape; price: number }[] = [
  { type: "duplex_outlet", label: "Duplex Receptacle", n: 24, shape: "circle", price: 4.25 },
  { type: "light", label: "Light Fixture", n: 14, shape: "square", price: 45 },
  { type: "switch", label: "Switch", n: 9, shape: "triangle", price: 3.25 },
  { type: "data_drop", label: "Data Drop", n: 7, shape: "triangle", price: 12 },
  { type: "panel", label: "Panel", n: 3, shape: "rect", price: 320 },
];

export function buildMockTakeoff(): { takeoff: Takeoff; imageUrl: string } {
  const dets: Detection[] = [];
  const glyphs: string[] = [];
  const cols = 12;
  let k = 0;

  PLAN.forEach((p, ti) => {
    for (let i = 0; i < p.n; i++) {
      const col = k % cols;
      const row = Math.floor(k / cols);
      const x = 60 + col * 74 + ti * 6;
      const y = 96 + row * 78 + ((k * 13) % 18);
      const conf = Math.min(0.97, Math.round((0.55 + ((k * 37) % 42) / 100) * 100) / 100);
      dets.push({ type: p.type, label: p.label, x, y, w: BOX, h: BOX, confidence: conf });
      glyphs.push(glyph(p.shape, x + BOX / 2, y + BOX / 2, colorForType(p.type)));
      k++;
    }
  });

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">` +
    `<rect width="${W}" height="${H}" fill="#FBFCFD"/>${grid()}` +
    `<rect x="8" y="8" width="${W - 16}" height="${H - 16}" fill="none" stroke="#C9D2DC" stroke-width="2"/>` +
    `<rect x="${W - 250}" y="${H - 90}" width="234" height="74" fill="#fff" stroke="#C9D2DC"/>` +
    `<text x="${W - 238}" y="${H - 62}" font-family="monospace" font-size="13" fill="#5A636E">FlashPod — Mock Drawing E-1</text>` +
    `<text x="${W - 238}" y="${H - 42}" font-family="monospace" font-size="11" fill="#8A94A0">Sample electrical plan (demo)</text>` +
    glyphs.join("") +
    `</svg>`;
  const imageUrl = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;

  const priced_items: PricedItem[] = PLAN.map((p) => {
    const group = dets.filter((d) => d.type === p.type);
    return {
      type: p.type,
      label: p.label,
      quantity: group.length,
      unit_price: p.price,
      total: Math.round(p.price * group.length * 100) / 100,
      boxes: group.map((d) => [d.x, d.y, d.w, d.h]),
      price_source: "static",
    };
  });

  const takeoff: Takeoff = {
    id: 0,
    project_id: 0,
    drawing_id: 0,
    status: "done",
    detections: dets,
    priced_items,
    proposal: null,
    image_size: { width: W, height: H },
    error: null,
    created_at: new Date().toISOString(),
  };
  return { takeoff, imageUrl };
}

function grid(): string {
  let s = "";
  for (let x = 60; x < W - 40; x += 74) s += `<line x1="${x}" y1="40" x2="${x}" y2="${H - 100}" stroke="#EEF2F6"/>`;
  for (let y = 90; y < H - 90; y += 78) s += `<line x1="40" y1="${y}" x2="${W - 40}" y2="${y}" stroke="#EEF2F6"/>`;
  return s;
}

function glyph(shape: Shape, cx: number, cy: number, color: string): string {
  const r = 9;
  if (shape === "circle")
    return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="2.4"/><line x1="${cx - 4}" y1="${cy}" x2="${cx + 4}" y2="${cy}" stroke="${color}" stroke-width="2"/>`;
  if (shape === "square")
    return `<rect x="${cx - r}" y="${cy - r}" width="${2 * r}" height="${2 * r}" fill="none" stroke="${color}" stroke-width="2.4"/><line x1="${cx - r}" y1="${cy - r}" x2="${cx + r}" y2="${cy + r}" stroke="${color}" stroke-width="1.6"/>`;
  if (shape === "triangle")
    return `<polygon points="${cx},${cy - r} ${cx - r},${cy + r} ${cx + r},${cy + r}" fill="none" stroke="${color}" stroke-width="2.4"/>`;
  return `<rect x="${cx - r}" y="${cy - r * 0.7}" width="${2 * r}" height="${1.4 * r}" fill="${color}" opacity="0.85"/>`;
}
