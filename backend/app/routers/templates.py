from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Project, Template, TemplateOut
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
