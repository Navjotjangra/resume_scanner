"""CSV export for scan results.

Writes UTF-8 with BOM (utf-8-sig) so Excel opens it correctly.
"""

from __future__ import annotations

import csv
from pathlib import Path

from scanner.models import ScanReport


def export_csv(report: ScanReport, dest: Path) -> None:
    """Export ranked results to CSV.

    Columns: Rank, File, Path, Match %, Level, Top keywords (terms joined
    by "; "). Ranked rows only; failures are not exported.
    """
    dest = Path(dest)
    with dest.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Rank", "File", "Path", "Match %", "Level", "Top keywords"])
        for row in report.ranked:
            writer.writerow(
                [
                    row.rank,
                    row.path.name,
                    str(row.path),
                    row.percent,
                    row.level.value,
                    "; ".join(row.top_terms),
                ]
            )
