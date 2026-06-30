import { useMemo, useState } from "react";
import { apiBase, getTakeoff } from "./api";
import { symbolCount, computeTotals } from "./lib";
import { loadJobs, saveJob } from "./jobs";
import type { Drawing, JobIndexEntry, Project, Takeoff, Template } from "./types";
import { TopBar, type Step } from "./components/TopBar";
import { UploadScreen } from "./components/UploadScreen";
import { SymbolsScreen } from "./components/SymbolsScreen";
import { RunScreen } from "./components/RunScreen";
import { ResultsScreen } from "./components/ResultsScreen";
import { JobsView } from "./components/JobsView";

const LABOR_PCT = 35; // UI-side labeled estimate; backend doesn't return labor

export function App() {
  const [step, setStep] = useState<Step>("upload");
  const [project, setProject] = useState<Project | null>(null);
  const [drawing, setDrawing] = useState<Drawing | null>(null);
  const [localImageUrl, setLocalImageUrl] = useState<string | null>(null); // for cropping
  const [templates, setTemplates] = useState<Template[]>([]);
  const [takeoff, setTakeoff] = useState<Takeoff | null>(null);
  const [laborPct, setLaborPct] = useState<number>(LABOR_PCT);
  const [jobsOpen, setJobsOpen] = useState(false);
  const [jobs, setJobs] = useState<JobIndexEntry[]>(() => loadJobs());

  // Image shown on Results: backend-served (works for live + reopened jobs).
  const resultsImageUrl = useMemo(
    () => (takeoff ? `${apiBase}/drawings/${takeoff.drawing_id}` : null),
    [takeoff],
  );

  function reset() {
    setProject(null);
    setDrawing(null);
    setLocalImageUrl(null);
    setTemplates([]);
    setTakeoff(null);
    setStep("upload");
  }

  function onUploaded(p: Project, d: Drawing, fileUrl: string) {
    setProject(p);
    setDrawing(d);
    setLocalImageUrl(fileUrl);
    setStep("symbols");
  }

  function onTakeoffDone(t: Takeoff) {
    setTakeoff(t);
    if (t.status === "done") {
      const items = t.priced_items ?? [];
      const entry: JobIndexEntry = {
        takeoff_id: t.id,
        project_id: t.project_id,
        project_name: project?.name ?? "Takeoff",
        drawing_id: t.drawing_id,
        symbol_count: symbolCount(items),
        grand_total: computeTotals(items, laborPct).grand,
        date: t.created_at,
      };
      setJobs(saveJob(entry));
    }
    setStep("results");
  }

  async function openJob(entry: JobIndexEntry) {
    setJobsOpen(false);
    try {
      const t = await getTakeoff(entry.takeoff_id);
      setProject({ id: entry.project_id, name: entry.project_name, created_at: "", updated_at: "" });
      setTakeoff(t);
      setStep("results");
    } catch (e) {
      alert(`Could not load job: ${(e as Error).message}`);
    }
  }

  return (
    <div style={{ minHeight: "100%", display: "flex", flexDirection: "column" }}>
      <TopBar
        step={step}
        jobsCount={jobs.length}
        onJobs={() => setJobsOpen(true)}
        onHome={reset}
      />

      <main style={{ flex: 1, padding: "20px clamp(12px, 4vw, 40px)", maxWidth: 1400, width: "100%", margin: "0 auto" }}>
        {step === "upload" && <UploadScreen onUploaded={onUploaded} />}

        {step === "symbols" && project && drawing && localImageUrl && (
          <SymbolsScreen
            project={project}
            imageUrl={localImageUrl}
            templates={templates}
            onTemplatesChange={setTemplates}
            onRun={() => setStep("run")}
            onBack={() => setStep("upload")}
          />
        )}

        {step === "run" && project && drawing && (
          <RunScreen
            project={project}
            drawing={drawing}
            onDone={onTakeoffDone}
            onBack={() => setStep("symbols")}
          />
        )}

        {step === "results" && takeoff && resultsImageUrl && (
          <ResultsScreen
            takeoff={takeoff}
            projectName={project?.name ?? "Takeoff"}
            imageUrl={resultsImageUrl}
            laborPct={laborPct}
            onLaborPct={setLaborPct}
            onTakeoffUpdate={setTakeoff}
            onNew={reset}
            onAdjust={() => setStep("symbols")}
          />
        )}
      </main>

      {jobsOpen && (
        <JobsView jobs={jobs} onOpen={openJob} onClose={() => setJobsOpen(false)} />
      )}
    </div>
  );
}
