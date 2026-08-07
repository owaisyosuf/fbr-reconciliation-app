"""File I/O helpers: safely persist Streamlit UploadedFile objects to a
scratch working directory. Original uploads are never modified in place --
everything downstream operates on these copies.
"""
from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

WORKDIR = Path(tempfile.gettempdir()) / "fbr_reconciliation_work"


def get_workdir() -> Path:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    return WORKDIR


def save_upload(uploaded_file, label: str) -> Path:
    """Save a Streamlit UploadedFile to a unique path in the work directory.

    `label` (e.g. "fbr" / "local") is included in the filename purely for
    readability during debugging.
    """
    workdir = get_workdir()
    suffix = Path(uploaded_file.name).suffix
    unique_name = f"{label}_{uuid.uuid4().hex[:8]}{suffix}"
    dest = workdir / unique_name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest


def new_output_path(stem: str, suffix: str = ".xlsx") -> Path:
    workdir = get_workdir()
    return workdir / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


def cleanup_workdir() -> None:
    """Remove the entire scratch directory. Call on session end / reset."""
    if WORKDIR.exists():
        shutil.rmtree(WORKDIR, ignore_errors=True)
