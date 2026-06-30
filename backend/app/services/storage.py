import os
import uuid
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))


def _ensure(subdir: str) -> Path:
    d = UPLOAD_DIR / subdir
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_file(data: bytes, subdir: str, original_name: str) -> Path:
    ext = Path(original_name).suffix or ".bin"
    dest = _ensure(subdir) / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(data)
    return dest


def delete_file(filepath: str) -> None:
    p = Path(filepath)
    if p.exists():
        p.unlink(missing_ok=True)
