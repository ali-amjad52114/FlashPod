// Mirrors backend/app/models.py (the FastAPI contract — the source of truth for the UI).

export interface Project {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Drawing {
  id: number;
  project_id: number;
  filename: string;
  url: string; // backend-served image URL (GET /drawings/{id})
  created_at: string;
}

export interface Template {
  id: number;
  project_id: number;
  sym_type: string;
  label: string;
  threshold: number;
  created_at: string;
}

export interface ImageSize {
  width: number;
  height: number;
}

export interface Detection {
  type: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  confidence: number;
}

// price_source: "static" (worker fallback) | "fallback" (backend, no live price)
//             | "brightdata" (live) | "manual" (user-corrected)
export type PriceSource = "static" | "fallback" | "brightdata" | "manual";

export interface PricedItem {
  type: string;
  label: string;
  quantity: number;
  unit_price: number;
  total: number;
  boxes: number[][]; // [[x, y, w, h], ...] in original image pixels
  price_source?: PriceSource;
  vendor?: string;
  source_url?: string;
  matched_title?: string;
}

export type TakeoffStatus = "pending" | "running" | "done" | "error";

export interface Takeoff {
  id: number;
  project_id: number;
  drawing_id: number;
  status: TakeoffStatus;
  detections: Detection[] | null;
  priced_items: PricedItem[] | null;
  proposal: string | null;
  image_size: ImageSize | null;
  error: string | null;
  created_at: string;
}

// Lightweight client-side index for the Jobs view. The backend has no
// "list takeoffs" endpoint, so we store only IDs + a little metadata
// (NO base64) and hydrate full data from GET /takeoffs/{id} on open.
export interface JobIndexEntry {
  takeoff_id: number;
  project_id: number;
  project_name: string;
  drawing_id: number;
  symbol_count: number;
  grand_total: number;
  date: string;
}
