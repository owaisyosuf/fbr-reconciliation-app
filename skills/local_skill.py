"""Skill 02 -- Local Processing Skill (wrapper).

Wraps the bundled `process_annex_c.py` logic (FBR "Annex C" local sales
report processor) so it can be called programmatically from the Streamlit
app. Underlying logic is untouched -- see
`skills/local_processing/process_annex_c.py`.

What it does to the Local file:
  1. Never modifies the original upload -- always works on a copy.
  2. Converts legacy .xls to .xlsx via LibreOffice if needed.
  3. Deletes fully blank separator rows.
  4. Merges the two-row header into one clean row.
  5. Hides every column except the 7 kept columns (Name, Number, Date,
     HS Code, Qty, Value Of Sales Excluding Sales Tax,
     Sales Tax / FED In ST Mode).
  6. Applies consistent styling (fonts, banding, borders, number formats).
  7. Adds a Total row with live =SUM() formulas.
"""
from __future__ import annotations

from pathlib import Path

from skills.local_processing.process_annex_c import process
from utils.exceptions import CorruptDataError
from utils.logging_config import get_logger

logger = get_logger(__name__)


def apply_local_skill(input_path: Path, output_path: Path) -> Path:
    """Apply Skill 02 to the Local (Annex C) file. Returns path to processed copy."""
    logger.info("Applying Local skill to %s", input_path.name)
    try:
        result_path, data_start, data_end, total_row = process(str(input_path), str(output_path))
    except Exception as exc:
        raise CorruptDataError(
            "Couldn't process the Local (Annex C) file -- it may not match the "
            "expected layout.",
            detail=str(exc),
        ) from exc

    if data_end < data_start:
        raise CorruptDataError("The Local (Annex C) file has no data rows after cleanup.")

    logger.info(
        "Local skill complete -> %s (data rows %d-%d, total row %d)",
        Path(result_path).name, data_start, data_end, total_row,
    )
    return Path(result_path)
