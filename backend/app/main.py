from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routers import drawings, projects, takeoffs, templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="FlashPod API",
    description="Orchestration layer: persists projects/drawings/takeoffs and calls the Runpod Flash endpoint.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(drawings.router)
app.include_router(templates.router)
app.include_router(takeoffs.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
