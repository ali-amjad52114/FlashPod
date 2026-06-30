from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Drawing, DrawingOut, Project
from ..services.storage import save_file

router = APIRouter(tags=["drawings"])


def _drawing_out(drawing: Drawing, request: Request) -> DrawingOut:
    return DrawingOut(
        id=drawing.id,
        project_id=drawing.project_id,
        filename=drawing.filename,
        url=str(request.url_for("serve_drawing", drawing_id=drawing.id)),
        created_at=drawing.created_at,
    )


@router.post(
    "/projects/{project_id}/drawings",
    response_model=DrawingOut,
    status_code=201,
)
def upload_drawing(
    project_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")

    data = file.file.read()
    saved = save_file(data, "drawings", file.filename or "drawing.png")

    drawing = Drawing(
        project_id=project_id,
        filename=file.filename or "drawing.png",
        filepath=str(saved),
        content_type=file.content_type or "image/png",
    )
    db.add(drawing)
    db.commit()
    db.refresh(drawing)
    return _drawing_out(drawing, request)


@router.get("/drawings/{drawing_id}", name="serve_drawing")
def serve_drawing(drawing_id: int, db: Session = Depends(get_db)):
    drawing = db.get(Drawing, drawing_id)
    if not drawing:
        raise HTTPException(404, "Drawing not found")
    p = Path(drawing.filepath)
    if not p.exists():
        raise HTTPException(404, "File not found on disk")
    return FileResponse(str(p), media_type=drawing.content_type, filename=drawing.filename)
