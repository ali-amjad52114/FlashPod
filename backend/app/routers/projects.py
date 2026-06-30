from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Project, ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    proj = Project(name=body.name)
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    db.delete(proj)
    db.commit()
