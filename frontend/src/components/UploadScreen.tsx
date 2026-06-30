import { useRef, useState } from "react";
import { createProject, uploadDrawing } from "../api";
import type { Drawing, Project } from "../types";

export function UploadScreen(props: { onUploaded: (p: Project, d: Drawing, fileUrl: string) => void }) {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function pickFile(f: File | null) {
    if (!f) return;
    if (!f.type.startsWith("image/")) {
      setError("Please choose a PNG or JPG drawing.");
      return;
    }
    setError(null);
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreviewUrl(url);
    const img = new Image();
    img.onload = () => setDims({ w: img.naturalWidth, h: img.naturalHeight });
    img.src = url;
  }

  async function go() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const project = await createProject(name.trim() || "Electrical Takeoff");
      const drawing = await uploadDrawing(project.id, file);
      props.onUploaded(project, drawing, previewUrl!);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", display: "grid", gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 22, margin: "8px 0 4px" }}>New takeoff</h1>
        <p className="muted" style={{ margin: 0 }}>
          Upload an electrical drawing. Next you'll mark the symbols to count.
        </p>
      </div>

      <div className="panel" style={{ padding: 20, display: "grid", gap: 16 }}>
        <label style={{ display: "grid", gap: 6 }}>
          <span style={{ fontSize: 12, color: "var(--secondary)" }}>Project name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Office Electrical Takeoff" />
        </label>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            pickFile(e.dataTransfer.files?.[0] ?? null);
          }}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
          style={{
            border: "1.5px dashed var(--hairline)",
            borderRadius: "var(--radius)",
            padding: previewUrl ? 12 : 36,
            textAlign: "center",
            background: "var(--sheet)",
            cursor: "pointer",
          }}
        >
          {previewUrl ? (
            <div style={{ display: "grid", gap: 8, justifyItems: "center" }}>
              <img src={previewUrl} alt="Drawing preview" style={{ maxHeight: 320, maxWidth: "100%", borderRadius: 4 }} />
              <span className="mono" style={{ fontSize: 12, color: "var(--secondary)" }}>
                {file?.name} {dims ? `· ${dims.w}×${dims.h}px` : ""}
              </span>
            </div>
          ) : (
            <div className="muted">Drag a drawing here, or click to choose (PNG / JPG)</div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg"
            hidden
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          />
        </div>

        {error && <div style={{ color: "var(--danger)", fontSize: 13 }}>{error}</div>}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="primary" disabled={!file || busy} onClick={go}>
            {busy ? "Uploading…" : "Next: pick symbols"}
          </button>
        </div>
      </div>
    </div>
  );
}
