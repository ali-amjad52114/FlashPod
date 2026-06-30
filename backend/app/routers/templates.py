# Symbol templates (Option A): auto-detected from the drawing's legend, confirmed
# by the user, then sent to the worker for template matching.
import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Drawing, Project, Template, TemplateOut
from ..services.legend import extract_legend_symbols
from ..services.storage import save_file

router = APIRouter(tags=["templates"])


@router.post(
    "/projects/{project_id}/templates",
    response_model=TemplateOut,
    status_code=201,
)
def upload_template(
    project_id: int,
    sym_type: str = Form(..., description="Symbol type key, e.g. 'duplex_outlet'"),
    label: str = Form(..., description="Human label, e.g. 'Duplex Outlet'"),
    threshold: float = Form(
        0.7, ge=0.0, le=1.0, description="Template-match confidence threshold (0–1)"
    ),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")

    data = file.file.read()
    if not data:
        raise HTTPException(400, "Uploaded template is empty")
    saved = save_file(data, "templates", file.filename or "template.png")

    tpl = Template(
        project_id=project_id,
        sym_type=sym_type,
        label=label,
        threshold=threshold,
        filepath=str(saved),
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.get("/projects/{project_id}/templates", response_model=list[TemplateOut])
def list_templates(project_id: int, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    return (
        db.query(Template)
        .filter(Template.project_id == project_id)
        .order_by(Template.created_at)
        .all()
    )


# --- Auto-detect (Option A): legend extraction + confirm ---------------------

class ConfirmSymbol(BaseModel):
    bbox: list[int]                  # [x, y, w, h] in original-image pixels
    sym_type: str
    label: str
    threshold: float = 0.7


class ConfirmSymbolsRequest(BaseModel):
    symbols: list[ConfirmSymbol]


def _get_drawing(project_id: int, drawing_id: int, db: Session) -> Drawing:
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    drawing = db.get(Drawing, drawing_id)
    if not drawing or drawing.project_id != project_id:
        raise HTTPException(404, "Drawing not found in this project")
    if not Path(drawing.filepath).exists():
        raise HTTPException(400, "Drawing file missing from disk")
    return drawing


@router.post("/projects/{project_id}/drawings/{drawing_id}/auto-symbols")
def auto_detect_symbols(project_id: int, drawing_id: int, db: Session = Depends(get_db)):
    """Auto-detect the legend's symbol glyphs as selectable candidates."""
    drawing = _get_drawing(project_id, drawing_id, db)
    return extract_legend_symbols(drawing.filepath)


@router.post(
    "/projects/{project_id}/drawings/{drawing_id}/confirm-symbols",
    response_model=list[TemplateOut],
    status_code=201,
)
def confirm_symbols(
    project_id: int,
    drawing_id: int,
    body: ConfirmSymbolsRequest,
    db: Session = Depends(get_db),
):
    """Crop each confirmed glyph from the drawing and save it as a Template.

    Replaces any existing templates for the project so re-confirming is idempotent.
    """
    drawing = _get_drawing(project_id, drawing_id, db)
    if not body.symbols:
        raise HTTPException(400, "No symbols selected")

    db.query(Template).filter(Template.project_id == project_id).delete()

    im = Image.open(drawing.filepath).convert("RGB")
    created: list[Template] = []
    for s in body.symbols:
        if len(s.bbox) != 4:
            raise HTTPException(400, f"bbox must be [x,y,w,h], got {s.bbox}")
        x, y, w, h = s.bbox
        crop = im.crop((x, y, x + w, y + h))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        saved = save_file(buf.getvalue(), "templates", f"{s.sym_type}.png")
        tpl = Template(
            project_id=project_id, sym_type=s.sym_type, label=s.label,
            threshold=s.threshold, filepath=str(saved),
        )
        db.add(tpl)
        created.append(tpl)
    db.commit()
    for t in created:
        db.refresh(t)
    return created
