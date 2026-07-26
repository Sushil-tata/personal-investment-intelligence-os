import csv
import io
from typing import Iterable


def to_csv(rows: Iterable[dict]) -> str:
    rows = list(rows)
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def from_csv(content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    return [dict(row) for row in reader]
