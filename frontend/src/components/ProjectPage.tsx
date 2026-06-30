import { useRef, useState } from "react";
import { createProject, uploadDrawing } from "../api";
import { money } from "../lib";
import { SymbolSetupModal } from "./SymbolSetupModal";
import type { Drawing, JobIndexEntry, Project } from "../types";

export function ProjectPage(props: {
  jobs: JobIndexEntry[];
  onReadyUpload: (p: Project, d: Drawing, imageUrl: string) => void;
  onMock: () => void;
  onOpenJob: (e: JobIndexEntry) => void;
}) {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [drawing, setDrawing] = useState<Drawing | null>(null);
  const [setupOpen, setSetupOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function pick(f: File | null) {
    if (!f) return;
    if (!f.type.startsWith("image/")) return setError("Choose a PNG or JPG drawing.");
    setError(null);
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
  }

  async function uploadAndSetup() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const p = await createProject(name.trim() || "Electrical Takeoff");
      const d = await uploadDrawing(p.id, file);
      setProject(p);
      setDrawing(d);
      setSetupOpen(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 920, margin: "0 auto", display: "grid", gap: 22 }}>
      <div>
        <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Start a Takeoff</h1>
        <p className="muted" style={{ margin: 0 }}>
          Upload an electrical drawing or use a mock drawing to generate a traceable, first-pass proposal.
        </p>
      </div>

      <div className="panel" style={{ padding: 20, display: "grid", gap: 16 }}>
        <label style={{ display: "grid", gap: 6 }}>
          <span style={{ fontSize: 12, color: "var(--secondary)" }}>Project name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Office Electrical Takeoff" />
        </label>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files?.[0] ?? null); }}
          onClick={() => inputRef.current?.click()}
          role="button" tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
          style={{ border: "1.5px dashed var(--hairline)", borderRadius: "var(--radius)", padding: previewUrl ? 12 : 30, textAlign: "center", background: "var(--sheet)", cursor: "pointer" }}
        >
          {previewUrl ? (
            <img src={previewUrl} alt="Drawing preview" style={{ maxHeight: 260, maxWidth: "100%", borderRadius: 4 }} />
          ) : (
            <div className="muted">Drag a drawing here, or click to choose (PNG / JPG)</div>
          )}
          <input ref={inputRef} type="file" accept="image/png,image/jpeg" hidden onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        </div>

        {error && <div style={{ color: "var(--danger)", fontSize: 13 }}>{error}</div>}

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button data-testid="use-mock" onClick={props.onMock}>Use mock drawing</button>
          <button className="primary" style={{ marginLeft: "auto" }} disabled={!file || busy} onClick={uploadAndSetup}>
            {busy ? "Uploading…" : "Upload & set up symbols"}
          </button>
        </div>
      </div>

      <div>
        <h2 style={{ fontSize: 16, margin: "0 0 10px" }}>Existing proposals</h2>
        {props.jobs.length === 0 ? (
          <p className="muted" style={{ fontSize: 13, margin: 0 }}>No proposals yet — your completed takeoffs will appear here.</p>
        ) : (
          <div className="cards">
            {props.jobs.map((j) => (
              <div key={j.takeoff_id} className="panel" style={{ padding: 14, display: "grid", gap: 8 }}>
                <div style={{ fontWeight: 600 }}>{j.project_name}</div>
                <div className="mono muted" style={{ fontSize: 11, display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <span>{new Date(j.date).toLocaleDateString()}</span>
                  <span>{j.symbol_count} devices</span>
                </div>
                <div className="mono" style={{ fontSize: 14 }}>${money(j.grand_total)}</div>
                <button onClick={() => props.onOpenJob(j)}>Open Proposal</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {setupOpen && project && drawing && previewUrl && (
        <SymbolSetupModal
          project={project}
          drawing={drawing}
          onClose={() => setSetupOpen(false)}
          onContinue={() => props.onReadyUpload(project, drawing, previewUrl)}
        />
      )}
    </div>
  );
}
