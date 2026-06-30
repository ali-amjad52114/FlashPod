import { useState } from "react";
import { apiBase, getTakeoff } from "./api";
import { loadJobs, saveJob } from "./jobs";
import { buildMockTakeoff } from "./mock";
import { activeDetections, buildReviewModel, computeTotals, deriveLineItems, type ReviewModel } from "./review";
import type { Drawing, JobIndexEntry, Project, Takeoff } from "./types";
import { TopBar, type Step } from "./components/TopBar";
import { ProjectPage } from "./components/ProjectPage";
import { ReviewPage } from "./components/ReviewPage";
import { ProposalPage } from "./components/ProposalPage";
import { JobsView } from "./components/JobsView";

const CONTINGENCY = 10;

export function App() {
  const [page, setPage] = useState<Step>("project");
  const [project, setProject] = useState<Project | null>(null);
  const [drawing, setDrawing] = useState<Drawing | null>(null);
  const [imageUrl, setImageUrl] = useState<string>("");
  const [takeoff, setTakeoff] = useState<Takeoff | null>(null);
  const [review, setReview] = useState<ReviewModel | null>(null);
  const [contingencyPct, setContingencyPct] = useState(CONTINGENCY);
  const [jobsOpen, setJobsOpen] = useState(false);
  const [jobs, setJobs] = useState<JobIndexEntry[]>(() => loadJobs());

  function reset() {
    setProject(null);
    setDrawing(null);
    setImageUrl("");
    setTakeoff(null);
    setReview(null);
    setPage("project");
  }

  // Page 1 -> Review (uploaded drawing; detection runs on the Review page)
  function onReadyUpload(p: Project, d: Drawing, url: string) {
    setProject(p);
    setDrawing(d);
    setImageUrl(url);
    setTakeoff(null);
    setReview(null);
    setPage("review");
  }

  // Page 1 -> Review (mock; detection already present, no backend needed)
  function onMock() {
    const { takeoff: t, imageUrl: url } = buildMockTakeoff();
    setProject({ id: 0, name: "Mock Drawing", created_at: "", updated_at: "" });
    setDrawing(null);
    setImageUrl(url);
    setTakeoff(t);
    setReview(buildReviewModel(t));
    setPage("review");
  }

  // detection finished (real backend run)
  function onRan(t: Takeoff) {
    const model = buildReviewModel(t);
    setTakeoff(t);
    setReview(model);
    const items = deriveLineItems(model);
    const entry: JobIndexEntry = {
      takeoff_id: t.id,
      project_id: t.project_id,
      project_name: project?.name ?? "Takeoff",
      drawing_id: t.drawing_id,
      symbol_count: activeDetections(model).length,
      grand_total: computeTotals(items, contingencyPct).total,
      date: t.created_at,
    };
    setJobs(saveJob(entry));
  }

  function backToProject() {
    if (review && !window.confirm("Go back to Project? Your review edits for this takeoff will be reset.")) return;
    reset();
  }

  async function openJob(entry: JobIndexEntry) {
    setJobsOpen(false);
    try {
      const t = await getTakeoff(entry.takeoff_id);
      setProject({ id: entry.project_id, name: entry.project_name, created_at: "", updated_at: "" });
      setDrawing(null);
      setImageUrl(`${apiBase}/drawings/${t.drawing_id}`);
      setTakeoff(t);
      setReview(buildReviewModel(t));
      setPage("proposal");
    } catch (e) {
      alert(`Could not open proposal: ${(e as Error).message}`);
    }
  }

  return (
    <div style={{ minHeight: "100%", display: "flex", flexDirection: "column" }}>
      <TopBar step={page} jobsCount={jobs.length} onJobs={() => setJobsOpen(true)} onHome={reset} />

      <main style={{ flex: 1, padding: "16px clamp(12px, 4vw, 40px)", maxWidth: 1400, width: "100%", margin: "0 auto" }}>
        {page === "project" && (
          <ProjectPage jobs={jobs} onReadyUpload={onReadyUpload} onMock={onMock} onOpenJob={openJob} />
        )}

        {page === "review" && imageUrl && (
          <ReviewPage
            project={project}
            drawing={drawing}
            imageUrl={imageUrl}
            takeoff={takeoff}
            review={review}
            onRan={onRan}
            onReviewChange={setReview}
            onGenerate={() => setPage("proposal")}
            onBack={backToProject}
          />
        )}

        {page === "proposal" && takeoff && review && imageUrl && (
          <ProposalPage
            projectName={project?.name ?? "Takeoff"}
            imageUrl={imageUrl}
            takeoff={takeoff}
            model={review}
            contingencyPct={contingencyPct}
            onContingency={setContingencyPct}
            onBack={() => setPage("review")}
          />
        )}
      </main>

      {jobsOpen && <JobsView jobs={jobs} onOpen={openJob} onClose={() => setJobsOpen(false)} />}
    </div>
  );
}
