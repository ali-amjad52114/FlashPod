"""Tests for PATCH /takeoffs/{id}/items/{sym_type}.

Covers:
- price_source set to "manual" on the corrected item
- total recomputed correctly
- proposal text regenerated and returned
- other items in the takeoff are not mutated
- only quantity changed (unit_price preserved)
- only unit_price changed (quantity preserved)
- 404 on unknown takeoff id
- 404 when sym_type not present in priced_items
- 400 when takeoff has no priced_items at all
"""

import pytest
from app.models import Drawing, Project, Takeoff


# ---------------------------------------------------------------------------
# DB seed helpers
# ---------------------------------------------------------------------------

TWO_ITEMS = [
    {
        "type": "duplex_outlet",
        "label": "Duplex Outlet",
        "quantity": 10,
        "unit_price": 4.25,
        "total": 42.50,
        "boxes": [[1, 2, 3, 4]],
        "price_source": "brightdata",
    },
    {
        "type": "switch",
        "label": "Switch",
        "quantity": 5,
        "unit_price": 3.25,
        "total": 16.25,
        "boxes": [[5, 6, 7, 8]],
        "price_source": "brightdata",
    },
]


def seed_takeoff(db, priced_items=None) -> Takeoff:
    proj = Project(name="Test Project")
    db.add(proj)
    db.flush()

    drawing = Drawing(
        project_id=proj.id,
        filename="test.png",
        filepath="/nonexistent/test.png",
        content_type="image/png",
    )
    db.add(drawing)
    db.flush()

    takeoff = Takeoff(
        project_id=proj.id,
        drawing_id=drawing.id,
        status="done",
        detections=[],
        priced_items=priced_items if priced_items is not None else list(TWO_ITEMS),
        proposal="original proposal text",
    )
    db.add(takeoff)
    db.commit()
    return takeoff


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_patch_sets_price_source_manual(client, db):
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/duplex_outlet", json={"quantity": 12, "unit_price": 5.00})
    assert resp.status_code == 200
    outlet = next(i for i in resp.json()["priced_items"] if i["type"] == "duplex_outlet")
    assert outlet["price_source"] == "manual"


def test_patch_recomputes_total(client, db):
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/duplex_outlet", json={"quantity": 12, "unit_price": 5.00})
    assert resp.status_code == 200
    outlet = next(i for i in resp.json()["priced_items"] if i["type"] == "duplex_outlet")
    assert outlet["total"] == 60.00  # 12 * 5.00


def test_patch_regenerates_proposal_text(client, db):
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/duplex_outlet", json={"quantity": 12, "unit_price": 5.00})
    assert resp.status_code == 200
    proposal = resp.json()["proposal"]
    assert proposal != "original proposal text"
    assert "Duplex Outlet" in proposal


def test_patch_proposal_reflects_corrected_price(client, db):
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/duplex_outlet", json={"unit_price": 99.99})
    assert resp.status_code == 200
    assert "99.99" in resp.json()["proposal"]


def test_patch_only_quantity_preserves_unit_price(client, db):
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/switch", json={"quantity": 8})
    assert resp.status_code == 200
    switch = next(i for i in resp.json()["priced_items"] if i["type"] == "switch")
    assert switch["quantity"] == 8
    assert switch["unit_price"] == 3.25  # unchanged
    assert switch["total"] == 26.00      # 8 * 3.25
    assert switch["price_source"] == "manual"


def test_patch_only_unit_price_preserves_quantity(client, db):
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/switch", json={"unit_price": 6.00})
    assert resp.status_code == 200
    switch = next(i for i in resp.json()["priced_items"] if i["type"] == "switch")
    assert switch["quantity"] == 5       # unchanged
    assert switch["unit_price"] == 6.00
    assert switch["total"] == 30.00      # 5 * 6.00


def test_patch_does_not_mutate_other_items(client, db):
    """Patching duplex_outlet must leave switch untouched."""
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/duplex_outlet", json={"quantity": 1})
    assert resp.status_code == 200

    switch = next(i for i in resp.json()["priced_items"] if i["type"] == "switch")
    assert switch["price_source"] == "brightdata"  # NOT overwritten to "manual"
    assert switch["unit_price"] == 3.25
    assert switch["quantity"] == 5
    assert switch["total"] == 16.25


def test_patch_404_takeoff_not_found(client, db):
    resp = client.patch("/takeoffs/99999/items/duplex_outlet", json={"quantity": 5})
    assert resp.status_code == 404


def test_patch_404_sym_type_not_in_takeoff(client, db):
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/panel", json={"quantity": 1})
    assert resp.status_code == 404
    assert "panel" in resp.json()["detail"]


def test_patch_400_takeoff_has_no_priced_items(client, db):
    proj = Project(name="Empty")
    db.add(proj)
    db.flush()
    drawing = Drawing(
        project_id=proj.id, filename="x.png",
        filepath="/nonexistent/x.png", content_type="image/png",
    )
    db.add(drawing)
    db.flush()
    t = Takeoff(
        project_id=proj.id, drawing_id=drawing.id,
        status="error", priced_items=None, proposal=None,
    )
    db.add(t)
    db.commit()

    resp = client.patch(f"/takeoffs/{t.id}/items/duplex_outlet", json={"quantity": 1})
    assert resp.status_code == 400


def test_patch_response_includes_price_source_in_all_items(client, db):
    """TakeoffOut.priced_items is Optional[list] — verify price_source is not stripped."""
    t = seed_takeoff(db)
    resp = client.patch(f"/takeoffs/{t.id}/items/duplex_outlet", json={"quantity": 3})
    assert resp.status_code == 200

    for item in resp.json()["priced_items"]:
        assert "price_source" in item, f"price_source missing from {item['type']}"
