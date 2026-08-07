"""Compares FBR Total vs Local Total and reports match/mismatch status."""
from __future__ import annotations

from dataclasses import dataclass

# Tolerance for floating point rounding noise (currency rounded to paisa).
TOLERANCE = 0.01


@dataclass
class ComparisonResult:
    fbr_total: float
    local_total: float
    difference: float
    matched: bool

    @property
    def status_label(self) -> str:
        return "Matched" if self.matched else "Mismatch"


def compare_totals(fbr_total: float, local_total: float) -> ComparisonResult:
    difference = round(fbr_total - local_total, 2)
    matched = abs(difference) <= TOLERANCE
    return ComparisonResult(
        fbr_total=round(fbr_total, 2),
        local_total=round(local_total, 2),
        difference=difference if not matched else 0.0,
        matched=matched,
    )
