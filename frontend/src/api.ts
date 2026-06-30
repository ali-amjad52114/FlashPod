// Typed client for the FastAPI backend (backend/). The React app calls this
// directly — the backend holds RUNPOD_API_KEY + Bright Data config and calls
// Runpod itself, so the frontend never touches Runpod or the API key.
import type { Drawing, Project, Takeoff, Template } from "./types";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export const apiBase = BASE;

async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

// --- Projects ---
export function createProject(name: string): Promise<Project> {
  return fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then((r) => jsonOrThrow<Project>(r));
}

export function listProjects(): Promise<Project[]> {
  return fetch(`${BASE}/projects`).then((r) => jsonOrThrow<Project[]>(r));
}

// --- Drawings (multipart upload; no base64 in the UI) ---
export function uploadDrawing(projectId: number, file: File): Promise<Drawing> {
  const fd = new FormData();
  fd.append("file", file);
  return fetch(`${BASE}/projects/${projectId}/drawings`, { method: "POST", body: fd }).then((r) =>
    jsonOrThrow<Drawing>(r),
  );
}

// --- Templates (multipart upload of the cropped symbol) ---
export function uploadTemplate(
  projectId: number,
  args: { sym_type: string; label: string; threshold: number; file: File },
): Promise<Template> {
  const fd = new FormData();
  fd.append("sym_type", args.sym_type);
  fd.append("label", args.label);
  fd.append("threshold", String(args.threshold));
  fd.append("file", args.file);
  return fetch(`${BASE}/projects/${projectId}/templates`, { method: "POST", body: fd }).then((r) =>
    jsonOrThrow<Template>(r),
  );
}

export function listTemplates(projectId: number): Promise<Template[]> {
  return fetch(`${BASE}/projects/${projectId}/templates`).then((r) => jsonOrThrow<Template[]>(r));
}

// --- Takeoff ---
// NOTE: this POST BLOCKS until the worker finishes (cold start ~30-120s) and
// the backend has overlaid Bright Data prices. It returns the final TakeoffOut
// with status "done" or "error". There is no job-status polling at this layer.
export function runTakeoff(projectId: number, drawingId: number): Promise<Takeoff> {
  return fetch(`${BASE}/projects/${projectId}/takeoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drawing_id: drawingId }),
  }).then((r) => jsonOrThrow<Takeoff>(r));
}

export function getTakeoff(takeoffId: number): Promise<Takeoff> {
  return fetch(`${BASE}/takeoffs/${takeoffId}`).then((r) => jsonOrThrow<Takeoff>(r));
}

// Manual line-item correction -> recomputes total, sets price_source = "manual".
export function correctItem(
  takeoffId: number,
  symType: string,
  patch: { quantity?: number; unit_price?: number },
): Promise<Takeoff> {
  return fetch(`${BASE}/takeoffs/${takeoffId}/items/${encodeURIComponent(symType)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }).then((r) => jsonOrThrow<Takeoff>(r));
}
