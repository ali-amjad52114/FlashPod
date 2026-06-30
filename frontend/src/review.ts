// Local "reviewed" model. Detections + priced_items from the backend are the
// source of truth, but the estimator can correct them before the proposal:
// exclude false positives, retype, add missed items, and adjust unit prices.
// Edits live here (local); unit-price confirms also call correctItem() for
// persistence. Line items + totals are DERIVED from this model.
import { round2 } from "./lib";
import type { Detection, PriceSource, PricedItem, Takeoff } from "./types";

export const LOW_CONF = 0.6;

export interface RDetection {
  id: string;
  type: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  confidence: number;
  excluded: boolean;
  manual: boolean;
}

export interface ReviewModel {
  detections: RDetection[];
  unitPriceByType: Record<string, number>;
  labelByType: Record<string, string>;
  sourceByType: Record<string, PriceSource>;
}

export interface ReviewLineItem extends PricedItem {
  lowConf: number;
  reviewed: boolean;
}

export function buildReviewModel(t: Takeoff): ReviewModel {
  const detections: RDetection[] = (t.detections ?? []).map((d: Detection, i) => ({
    ...d,
    id: `d${i}`,
    excluded: false,
    manual: false,
  }));
  const unitPriceByType: Record<string, number> = {};
  const labelByType: Record<string, string> = {};
  const sourceByType: Record<string, PriceSource> = {};
  for (const it of t.priced_items ?? []) {
    unitPriceByType[it.type] = it.unit_price;
    labelByType[it.type] = it.label;
    sourceByType[it.type] = it.price_source ?? "static";
  }
  for (const d of detections) {
    if (!(d.type in unitPriceByType)) unitPriceByType[d.type] = 5;
    if (!(d.type in labelByType)) labelByType[d.type] = d.label;
    if (!(d.type in sourceByType)) sourceByType[d.type] = "static";
  }
  return { detections, unitPriceByType, labelByType, sourceByType };
}

export function activeDetections(m: ReviewModel): RDetection[] {
  return m.detections.filter((d) => !d.excluded);
}

export function typesInOrder(dets: RDetection[]): string[] {
  const out: string[] = [];
  for (const d of dets) if (!out.includes(d.type)) out.push(d.type);
  return out;
}

export function deriveLineItems(m: ReviewModel): ReviewLineItem[] {
  const active = activeDetections(m);
  return typesInOrder(active).map((type) => {
    const group = active.filter((d) => d.type === type);
    const unit = m.unitPriceByType[type] ?? 5;
    const qty = group.length;
    const src = m.sourceByType[type] ?? "static";
    return {
      type,
      label: m.labelByType[type] ?? type,
      quantity: qty,
      unit_price: unit,
      total: round2(unit * qty),
      boxes: group.map((d) => [d.x, d.y, d.w, d.h]),
      price_source: src,
      lowConf: group.filter((d) => d.confidence < LOW_CONF).length,
      reviewed: group.some((d) => d.manual) || src === "manual",
    };
  });
}

export function lowConfidenceCount(m: ReviewModel): number {
  return activeDetections(m).filter((d) => d.confidence < LOW_CONF).length;
}

export function computeTotals(items: ReviewLineItem[], contingencyPct: number) {
  const material = round2(items.reduce((s, it) => s + it.total, 0));
  const contingency = round2((material * contingencyPct) / 100);
  return { material, contingency, total: round2(material + contingency) };
}
