# TODO: implement PDF proposal export
#
# Suggested approach:
#   - Use `reportlab` (pure-Python, no system deps) or `weasyprint` (HTML→PDF).
#   - Input: a TakeoffOut dict with `priced_items` (list) and `proposal` (str).
#   - Output: bytes — the raw PDF to stream back as application/pdf.
#
# Stub raises NotImplementedError so the router returns HTTP 501 until this is built.


def export_pdf(takeoff_data: dict) -> bytes:
    raise NotImplementedError(
        "PDF export is not yet implemented. "
        "See backend/app/services/proposal_export.py for the stub and TODO."
    )
