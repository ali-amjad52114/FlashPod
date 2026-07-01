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
import heroTakeoff from "../../assets/hero-takeoff.png";

const CONTINGENCY = 10;

type HomePageProps = {
  jobsCount: number;
  onStart: () => void;
  onMock: () => void;
  onJobs: () => void;
};

const homeMetrics = [
  { value: "1", label: "drawing upload" },
  { value: "3", label: "review steps" },
  { value: "100%", label: "traceable quantities" },
];

const homeValues = [
  {
    title: "Win trust before the bid goes out",
    text: "Every proposed quantity links back to the drawing, so estimators can defend the count instead of sending a black-box total.",
  },
  {
    title: "Turn takeoff review into a clean workflow",
    text: "FlashPod separates upload, detection review, and proposal export so the team can correct misses before pricing is locked.",
  },
  {
    title: "Price with market context",
    text: "Material lines can include supplier offers and source URLs, making the proposal easier to explain and easier to update.",
  },
];

const homeStack = [
  {
    name: "RunPod",
    role: "Remote execution",
    why: "Runs the computer-vision takeoff pipeline away from the browser, keeps the UI responsive, and gives the project a path from CPU template matching to GPU vision workers.",
    accent: "compute",
  },
  {
    name: "Bright Data",
    role: "Live pricing signal",
    why: "Queries supplier-facing shopping data so line items can carry current offer context, source links, and a static fallback when live pricing is unavailable.",
    accent: "pricing",
  },
  {
    name: "React + FastAPI",
    role: "Review workspace",
    why: "React handles drawing review and proposal interaction, while FastAPI stores projects, drawings, templates, takeoffs, and worker results.",
    accent: "app",
  },
];

const homeToolChips = ["RunPod workers", "OpenCV", "Qwen2.5-VL path", "Bright Data SERP", "React review UI"];

const architectureSteps = [
  { n: "01", title: "Decode", tool: "Pillow", detail: "base64 -> image" },
  { n: "02", title: "Detect", tool: "OpenCV", detail: "template match" },
  { n: "03", title: "Count", tool: "NumPy", detail: "group + dedupe" },
  { n: "04", title: "Price", tool: "Bright Data", detail: "live lookup" },
  { n: "05", title: "Propose", tool: "Template", detail: "JSON build" },
];

const architectureCards = [
  {
    title: "RunPod Flash endpoint",
    label: "flashpod-takeoff",
    body: "One warm CPU worker receives the drawing, runs the detection-pricing-proposal pipeline, and returns structured JSON. Heavy compute stays off the browser.",
    tags: ["cpu5c-4-8", "workers 1-1", "Python", "runpod_flash"],
  },
  {
    title: "Bright Data pricing",
    label: "Live material prices",
    body: "Bright Data is called at the price step to collect supplier context per symbol type, then FlashPod keeps source-backed unit prices on the proposal line items.",
    tags: ["Home Depot", "Platt Electric", "Rexel", "unit_price per SKU"],
  },
  {
    title: "Static fallback",
    label: "Demo reliability",
    body: "A local price table is used whenever live pricing is unreachable, so the demo can still produce a complete proposal.",
    tags: ["PRICE_TABLE", "no network fail", "stable output"],
  },
  {
    title: "Rendered output",
    label: "Traceability layer",
    body: "The frontend uses detections, priced_items, and boxes to highlight drawing symbols from proposal rows and prove where each quantity came from.",
    tags: ["Canvas", "SVG overlay", "boxes[]", "proposal export"],
  },
];

function HomePage(props: HomePageProps) {
  return (
    <div className="home-page">
      <section className="home-hero">
        <img src={heroTakeoff} alt="FlashPod product view showing an electrical plan and priced proposal" />
        <div className="home-hero__shade" />
        <div className="home-hero__content">
          <div className="home-eyebrow">Electrical takeoff, priced and traceable</div>
          <h1>FlashPod</h1>
          <p>
            Turn an electrical drawing into a proposal where every quantity, price, and review decision can be traced back to the plan.
          </p>
          <div className="home-actions">
            <button className="primary" onClick={props.onStart}>Start takeoff</button>
            <button onClick={props.onMock}>View demo drawing</button>
            {props.jobsCount > 0 && <button onClick={props.onJobs}>Open proposals</button>}
          </div>
        </div>
        <div className="home-hero__metrics" aria-label="FlashPod summary metrics">
          {homeMetrics.map((m) => (
            <div key={m.label}>
              <strong>{m.value}</strong>
              <span>{m.label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="home-section home-section--value">
        <div className="home-section__intro">
          <span className="home-kicker">Business value</span>
          <h2>Built for estimators who need speed and proof.</h2>
        </div>
        <div className="home-value-grid">
          {homeValues.map((v) => (
            <article className="home-value-card" key={v.title}>
              <h3>{v.title}</h3>
              <p>{v.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="home-section home-section--workflow">
        <div className="home-section__intro">
          <span className="home-kicker">Product flow</span>
          <h2>From drawing to defendable proposal.</h2>
        </div>
        <div className="home-flow" aria-label="FlashPod workflow">
          <div>
            <span>01</span>
            <h3>Upload plan</h3>
            <p>Start with a drawing and symbol templates for the devices that matter.</p>
          </div>
          <div>
            <span>02</span>
            <h3>Review detections</h3>
            <p>Inspect highlighted symbols, hide mistakes, and keep the proposal tied to visual evidence.</p>
          </div>
          <div>
            <span>03</span>
            <h3>Generate proposal</h3>
            <p>Export material lines, totals, contingency, and source-backed pricing context.</p>
          </div>
        </div>
      </section>

      <section className="home-section home-section--stack">
        <div className="home-section__intro">
          <span className="home-kicker">Tech stack</span>
          <h2>Chosen for a demo that can grow into production.</h2>
        </div>
        <div className="home-architecture-panel">
          <div className="home-architecture-copy">
            <span>Models and tools</span>
            <h3>Decode &gt; Detect &gt; Count &gt; Price &gt; Propose</h3>
            <p>
              The core workflow is intentionally simple: RunPod executes the drawing analysis, vision tools locate symbols, Bright Data adds market-backed pricing context, and the React app turns the result into a reviewable proposal.
            </p>
            <div className="home-tool-chips" aria-label="Models and tools used">
              {homeToolChips.map((tool) => <span key={tool}>{tool}</span>)}
            </div>
          </div>
          <div className="home-architecture-steps" aria-label="Takeoff processing pipeline">
            {architectureSteps.map((step) => (
              <article key={step.n}>
                <span>{step.n}</span>
                <h4>{step.title}</h4>
                <strong>{step.tool}</strong>
                <p>{step.detail}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="home-architecture-grid">
          {architectureCards.map((card) => (
            <article className="home-architecture-card" key={card.title}>
              <span>{card.label}</span>
              <h3>{card.title}</h3>
              <p>{card.body}</p>
              <div>
                {card.tags.map((tag) => <small key={tag}>{tag}</small>)}
              </div>
            </article>
          ))}
        </div>
        <div className="home-stack-grid">
          {homeStack.map((item) => (
            <article className={`home-stack-card home-stack-card--${item.accent}`} key={item.name}>
              <div>
                <span>{item.role}</span>
                <h3>{item.name}</h3>
              </div>
              <p>{item.why}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export function App() {
  const [page, setPage] = useState<Step>("home");
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
    setPage("home");
  }

  function startProject() {
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
      <TopBar step={page} jobsCount={jobs.length} onJobs={() => setJobsOpen(true)} onHome={reset} onStart={startProject} />

      <main className={page === "home" ? "app-main app-main--home" : "app-main"}>
        {page === "home" && (
          <HomePage jobsCount={jobs.length} onStart={startProject} onMock={onMock} onJobs={() => setJobsOpen(true)} />
        )}

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
