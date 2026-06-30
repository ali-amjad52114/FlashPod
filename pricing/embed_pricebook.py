"""Bake the cached catalog's prices into the takeoff worker.

    uv run python -m pricing.embed_pricebook            # inject into takeoff_worker.py
    uv run python -m pricing.embed_pricebook --print     # just print the literal

Flash ships only the function body, so the worker can't read catalog.json at runtime — it
carries an EMBEDDED_PRICEBOOK literal instead. This script regenerates that literal from
catalog.json and rewrites the block between the PRICEBOOK markers inside the worker, keeping
the worker's fallback prices in sync with the catalog (single source of truth).
"""
from __future__ import annotations

import sys
from pathlib import Path

from .catalog import build_pricebook, load_catalog

WORKER_PATH = Path(__file__).parent.parent / "takeoff_worker.py"
START = "# >>> PRICEBOOK_START"
END = "# <<< PRICEBOOK_END"
INDENT = "    "  # inside the async function body

# Worker only needs these fields to price + label + source a line item.
_FIELDS = ("label", "unit_price", "sku", "supplier", "source_url", "unit")


def render_literal(pricebook: dict[str, dict], indent: str = INDENT) -> str:
    """Render EMBEDDED_PRICEBOOK as a Python dict literal at the given indent."""
    lines = [f"{indent}EMBEDDED_PRICEBOOK = {{"]
    for sym_type, entry in pricebook.items():
        fields = ", ".join(f'"{k}": {entry.get(k)!r}' for k in _FIELDS)
        lines.append(f'{indent}    "{sym_type}": {{{fields}}},')
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def inject(worker_path: Path, literal: str) -> None:
    """Replace the block between the PRICEBOOK markers with `literal`."""
    src = worker_path.read_text()
    if START not in src or END not in src:
        raise SystemExit(
            f"Markers {START!r} / {END!r} not found in {worker_path.name}. "
            "Add them inside the function body around EMBEDDED_PRICEBOOK first."
        )
    head, rest = src.split(START, 1)
    _, tail = rest.split(END, 1)
    indent = head.rsplit("\n", 1)[-1]  # whitespace preceding the START marker
    block = f"{START}\n{literal}\n{indent}{END}"
    worker_path.write_text(f"{head}{block}{tail}")


def main() -> None:
    pricebook = build_pricebook(load_catalog())
    literal = render_literal(pricebook)
    if "--print" in sys.argv:
        print(literal)
        return
    inject(WORKER_PATH, literal)
    print(f"Embedded {len(pricebook)} priced items into {WORKER_PATH.name}.")


if __name__ == "__main__":
    main()
