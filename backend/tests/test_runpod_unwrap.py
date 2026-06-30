"""Tests for runpod_client._unwrap().

Covers:
- flash dev shape (worker dict returned directly)
- deployed serverless envelope: {"status": "COMPLETED", "output": {...}}
- job-level failures: FAILED, CANCELLED, TIMED_OUT
- malformed/unexpected inputs
- known edge case: COMPLETED with non-dict output (silent failure)
"""

import pytest

from app.services.runpod_client import _unwrap

WORKER_DICT = {
    "status": "success",
    "project_name": "Test",
    "detections": [{"type": "duplex_outlet", "x": 10, "y": 20, "w": 24, "h": 24, "confidence": 0.9}],
    "priced_items": [{"type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 1, "unit_price": 4.25, "total": 4.25, "boxes": [[10, 20, 24, 24]]}],
    "proposal": "FlashPod Electrical Proposal — Test\n...",
    "image_size": {"width": 800, "height": 600},
}


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

def test_unwrap_flash_dev_returns_worker_dict_unchanged():
    """flash dev returns the worker result directly; _unwrap must pass it through."""
    result = _unwrap(WORKER_DICT)
    assert result is WORKER_DICT


def test_unwrap_completed_envelope_returns_output():
    """Deployed serverless: extract the worker dict from the 'output' key."""
    envelope = {"status": "COMPLETED", "output": WORKER_DICT}
    result = _unwrap(envelope)
    assert result is WORKER_DICT


def test_unwrap_completed_envelope_preserves_all_fields():
    envelope = {"status": "COMPLETED", "output": WORKER_DICT}
    result = _unwrap(envelope)
    assert result["priced_items"] == WORKER_DICT["priced_items"]
    assert result["proposal"] == WORKER_DICT["proposal"]
    assert result["image_size"] == WORKER_DICT["image_size"]


# ---------------------------------------------------------------------------
# Failure envelopes
# ---------------------------------------------------------------------------

def test_unwrap_failed_returns_error_dict():
    result = _unwrap({"status": "FAILED", "error": "OOM killed"})
    assert result["status"] == "error"
    assert "OOM killed" in result["error"]


def test_unwrap_cancelled_returns_error_dict():
    result = _unwrap({"status": "CANCELLED"})
    assert result["status"] == "error"
    assert "CANCELLED" in result["error"]


def test_unwrap_timed_out_returns_error_dict():
    result = _unwrap({"status": "TIMED_OUT"})
    assert result["status"] == "error"
    assert "TIMED_OUT" in result["error"]


def test_unwrap_failed_with_no_error_message():
    """FAILED with no error field still produces a usable error string."""
    result = _unwrap({"status": "FAILED"})
    assert result["status"] == "error"
    assert result["error"]  # non-empty string


# ---------------------------------------------------------------------------
# Malformed / unexpected inputs
# ---------------------------------------------------------------------------

def test_unwrap_non_dict_string():
    result = _unwrap("not a dict")
    assert result["status"] == "error"
    assert "Unexpected" in result["error"]


def test_unwrap_non_dict_list():
    result = _unwrap([1, 2, 3])
    assert result["status"] == "error"


def test_unwrap_non_dict_none():
    result = _unwrap(None)
    assert result["status"] == "error"


def test_unwrap_empty_dict():
    """Empty dict has no 'output', no failure status → returned as-is (flash dev path)."""
    result = _unwrap({})
    assert result == {}


# ---------------------------------------------------------------------------
# Known edge case: COMPLETED with non-dict output  (documented silent failure)
# ---------------------------------------------------------------------------

def test_unwrap_completed_with_string_output_returns_error():
    """COMPLETED but output is a string (not a dict) → explicit error, not silent empty success."""
    envelope = {"status": "COMPLETED", "output": "unexpected string payload"}
    result = _unwrap(envelope)
    assert result["status"] == "error"
    assert "COMPLETED" in result["error"]


def test_unwrap_completed_with_no_output_key_returns_error():
    """COMPLETED with no output key → explicit error, not silent empty success."""
    envelope = {"status": "COMPLETED"}
    result = _unwrap(envelope)
    assert result["status"] == "error"
    assert "COMPLETED" in result["error"]
