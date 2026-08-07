"""Validation helpers: file type checks, column presence, empty-sheet checks,
duplicate detection. All raise ReconciliationError subclasses with
user-friendly messages so the UI layer can display them directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import load_workbook

from utils.exceptions import (
    InvalidFileError,
    MissingColumnError,
    EmptySheetError,
    CorruptDataError,
)
from utils.logging_config import get_logger

logger = get_logger(__name__)

VALID_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}

# Any header that normalizes to this token set is treated as the
# "Sales Tax / FED in ST Mode" column, regardless of exact spacing/casing
# used by a particular export (FBR vs Local reports phrase it slightly
# differently).
TAX_COLUMN_TOKENS = {"sales", "tax", "fed", "st", "mode"}


def normalize_header(text: Optional[str]) -> str:
    """Lowercase, strip punctuation/whitespace variance for header matching."""
    if text is None:
        return ""
    cleaned = "".join(ch if ch.isalnum() else " " for ch in str(text))
    return " ".join(cleaned.lower().split())


def is_tax_column_header(text: Optional[str]) -> bool:
    norm = normalize_header(text)
    tokens = set(norm.split())
    # Require the header to contain the core identifying tokens.
    return {"sales", "tax", "fed"}.issubset(tokens) or (
        "sales" in tokens and "tax" in tokens and "mode" in tokens
    )


def validate_file_type(filename: str) -> None:
    """Raise InvalidFileError if the filename doesn't have a supported Excel extension."""
    suffix = Path(filename).suffix.lower()
    if suffix not in VALID_EXTENSIONS:
        raise InvalidFileError(
            f"'{filename}' isn't a supported Excel file.",
            detail=f"Expected one of {sorted(VALID_EXTENSIONS)}, got '{suffix or 'no extension'}'.",
        )


def validate_readable_excel(path: str) -> None:
    """Confirm the file can actually be opened as an Excel workbook."""
    suffix = Path(path).suffix.lower()
    try:
        if suffix == ".xls":
            # Legacy .xls is handled via LibreOffice conversion elsewhere;
            # here we just confirm the file is non-empty and exists.
            if Path(path).stat().st_size == 0:
                raise CorruptDataError(f"'{Path(path).name}' is empty (0 bytes).")
            return
        load_workbook(path, read_only=True)
    except CorruptDataError:
        raise
    except Exception as exc:
        raise InvalidFileError(
            f"Couldn't open '{Path(path).name}' as an Excel file.",
            detail=str(exc),
        ) from exc


def find_tax_column(df: pd.DataFrame, source_label: str) -> str:
    """Return the actual column name in df that matches the tax column,
    matching flexibly by header tokens rather than an exact string.
    """
    for col in df.columns:
        if is_tax_column_header(col):
            return col
    raise MissingColumnError(
        f"Couldn't find the 'Sales Tax / FED in ST Mode' column in the {source_label} file.",
        detail=f"Columns found: {list(df.columns)}",
    )


def validate_not_empty(df: pd.DataFrame, source_label: str) -> None:
    if df is None or df.empty:
        raise EmptySheetError(f"The {source_label} sheet has no data rows to process.")


def check_duplicates(df: pd.DataFrame, key_columns: list[str]) -> int:
    """Return the count of duplicate rows based on the given key columns
    (only columns that actually exist are used). Never raises -- duplicates
    are surfaced as a warning in the UI, not a hard failure.
    """
    present = [c for c in key_columns if c in df.columns]
    if not present:
        return 0
    dup_count = int(df.duplicated(subset=present, keep=False).sum())
    if dup_count:
        logger.warning("Found %d duplicate rows (subset=%s)", dup_count, present)
    return dup_count
