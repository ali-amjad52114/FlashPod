// Client-side Jobs index. The backend persists takeoffs but exposes no
// "list takeoffs" endpoint, so we keep a small local index of IDs + metadata
// (NO base64 images -> no localStorage quota problem) and hydrate full data
// from GET /takeoffs/{id} when a job is reopened.
// Upgrade path: a backend GET /takeoffs (or /api/jobs) list endpoint.
import type { JobIndexEntry } from "./types";

const KEY = "flashpod.jobs.v1";

export function loadJobs(): JobIndexEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as JobIndexEntry[]) : [];
  } catch {
    return [];
  }
}

export function saveJob(entry: JobIndexEntry): JobIndexEntry[] {
  const existing = loadJobs().filter((j) => j.takeoff_id !== entry.takeoff_id);
  const next = [entry, ...existing].slice(0, 100);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* ignore quota — entries are tiny, but be safe */
  }
  return next;
}
