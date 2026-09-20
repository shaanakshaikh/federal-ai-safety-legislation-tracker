#!/usr/bin/env python3
"""Replace the dataset embedded in index.html and regenerate the CSV export."""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "measures.json"
SITE = ROOT / "index.html"
CSV = ROOT / "data" / "measures.csv"
PATTERN = re.compile(r'(<script id="records" type="application/json">).*?(</script>)', re.S)
COLS = [
    "measure_id", "title", "chamber", "scope", "primary_category", "sponsor",
    "sponsor_party", "sponsor_state", "cosponsor_count", "committees",
    "introduced_date", "last_action_date", "status", "advance_tier", "summary",
    "committee_dynamics", "advance_rationale", "congress_url",
    "last_verified_date", "verification_level",
]


def main() -> None:
    records = json.loads(DATA.read_text(encoding="utf-8"))
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    html = SITE.read_text(encoding="utf-8")
    updated, count = PATTERN.subn(lambda m: m.group(1) + payload + m.group(2), html, count=1)
    if count != 1:
        raise SystemExit("could not locate embedded records in index.html")
    SITE.write_text(updated, encoding="utf-8")

    with CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLS, extrasaction="ignore")
        writer.writeheader()
        for original in records:
            row = original.copy()
            for key, value in row.items():
                if isinstance(value, list):
                    row[key] = "; ".join(str(item) for item in value)
            writer.writerow(row)
    print(f"Synchronized {len(records)} records into index.html and {CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
