from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..db import get_db
from ..models import (
    Drawing,
    ItemCorrection,
    Project,
    Takeoff,
    TakeoffOut,
    TakeoffRequest,
)
from ..services.pricing import build_proposal_text
from ..services.proposal_export import export_pdf
from ..services.runpod_client import call_analyze_drawing

router = APIRouter(tags=["takeoffs"])


@router.post(
    "/projects/{project_id}/takeoff",
    response_model=TakeoffOut,
    status_code=201,
)
async def run_takeoff(
    project_id: int,
    body: TakeoffRequest,
    db: Session = Depends(get_db),
):
    """Trigger an electrical takeoff for an uploaded schematic.

    Vision-LLM flow: sends only the drawing to the analyze_drawing endpoint —
    the worker detects, counts, prices, and writes the proposal — then persists
    the result.
    """
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    drawing = db.get(Drawing, body.drawing_id)
    if not drawing or drawing.project_id != project_id:
        raise HTTPException(404, "Drawing not found in this project")

    if not Path(drawing.filepath).exists():
        raise HTTPException(400, "Drawing file missing from disk")

    takeoff = Takeoff(
        project_id=project_id, drawing_id=body.drawing_id, status="running"
    )
    db.add(takeoff)
    db.commit()
    db.refresh(takeoff)

    try:
        result = await call_analyze_drawing(
            project_name=proj.name,
            image_path=Path(drawing.filepath),
        )

        if result.get("status") == "error":
            takeoff.status = "error"
            takeoff.error = result.get("error", "Worker returned error")
        else:
            # Worker now handles pricing internally (Bright Data called inside
            # analyze_drawing). Pass priced_items and proposal through unchanged —
            # the worker's response is the source of truth for automated pricing.
            takeoff.status = "done"
            takeoff.detections = result.get("detections") or []
            takeoff.priced_items = result.get("priced_items") or []
            takeoff.proposal = result.get("proposal")
            takeoff.image_size = result.get("image_size")

    except Exception as exc:
        takeoff.status = "error"
        takeoff.error = str(exc)

    db.commit()
    db.refresh(takeoff)
    return takeoff


@router.get("/takeoffs/{takeoff_id}", response_model=TakeoffOut)
def get_takeoff(takeoff_id: int, db: Session = Depends(get_db)):
    t = db.get(Takeoff, takeoff_id)
    if not t:
        raise HTTPException(404, "Takeoff not found")
    return t


@router.get("/takeoffs/{takeoff_id}/proposal")
def get_proposal(takeoff_id: int, db: Session = Depends(get_db)):
    t = db.get(Takeoff, takeoff_id)
    if not t:
        raise HTTPException(404, "Takeoff not found")
    if not t.proposal:
        raise HTTPException(404, "No proposal available — takeoff may still be running or errored")
    return {"proposal": t.proposal}


@router.patch("/takeoffs/{takeoff_id}/items/{sym_type}", response_model=TakeoffOut)
def correct_item(
    takeoff_id: int,
    sym_type: str,
    body: ItemCorrection,
    db: Session = Depends(get_db),
):
    """Manually adjust a line item's quantity or unit price and recompute its total."""
    t = db.get(Takeoff, takeoff_id)
    if not t:
        raise HTTPException(404, "Takeoff not found")
    if not t.priced_items:
        raise HTTPException(400, "Takeoff has no priced items to correct")

    if body.quantity is None and body.unit_price is None:
        raise HTTPException(400, "Provide at least one of 'quantity' or 'unit_price'")

    # Deep-copy so we don't mutate SQLAlchemy's loaded snapshot in place — an
    # in-place edit makes the column compare equal to its committed state and the
    # UPDATE gets skipped. flag_modified then guarantees the JSON column is written.
    items = [dict(it) for it in t.priced_items]
    for item in items:
        if item.get("type") == sym_type:
            if body.quantity is not None:
                item["quantity"] = body.quantity
            if body.unit_price is not None:
                item["unit_price"] = body.unit_price
            item["total"] = round(item.get("quantity", 0) * item.get("unit_price", 0), 2)
            item["price_source"] = "manual"
            t.priced_items = items
            flag_modified(t, "priced_items")
            # Keep the proposal text in sync with the corrected totals.
            t.proposal = build_proposal_text(t.project.name, items)
            db.commit()
            db.refresh(t)
            return t

    raise HTTPException(404, f"Item type '{sym_type}' not found in this takeoff")


@router.post("/takeoffs/{takeoff_id}/proposal/export")
def export_proposal(takeoff_id: int, db: Session = Depends(get_db)):
    t = db.get(Takeoff, takeoff_id)
    if not t:
        raise HTTPException(404, "Takeoff not found")
    if t.status != "done":
        raise HTTPException(400, f"Takeoff status is '{t.status}', not 'done'")

    try:
        pdf_bytes = export_pdf(
            {"priced_items": t.priced_items, "proposal": t.proposal}
        )
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=proposal-{takeoff_id}.pdf"},
    )
