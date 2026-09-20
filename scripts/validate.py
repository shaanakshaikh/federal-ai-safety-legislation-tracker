#!/usr/bin/env python3
"""Validate the canonical legislative dataset and deployable static site."""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "measures.json"
SITE = ROOT / "index.html"

REQUIRED = {
    "measure_id",
    "title",
    "chamber",
    "scope",
    "primary_category",
    "status",
    "last_verified_date",
}
ALLOWED_SCOPES = {"Core", "Adjacent", "Vehicle"}
ALLOWED_CHAMBERS = {"House", "Senate", "Bicameral", "Executive"}


def fail(message: str) -> None:
    raise SystemExit(f"validation error: {message}")


def main() -> None:
    if not DATA.is_file() or not SITE.is_file():
        fail("data/measures.json and index.html must exist")
    records = json.loads(DATA.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        fail("dataset must be a non-empty JSON array")

    seen = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            fail(f"record {index} is not an object")
        missing = REQUIRED - record.keys()
        if missing:
            fail(f"record {index} missing: {', '.join(sorted(missing))}")
        measure_id = record["measure_id"]
        if measure_id in seen:
            fail(f"duplicate measure_id: {measure_id}")
        seen.add(measure_id)
        if record["scope"] not in ALLOWED_SCOPES:
            fail(f"{measure_id}: invalid scope {record['scope']!r}")
        if record["chamber"] not in ALLOWED_CHAMBERS:
            fail(f"{measure_id}: invalid chamber {record['chamber']!r}")
        try:
            date.fromisoformat(record["last_verified_date"])
        except (TypeError, ValueError):
            fail(f"{measure_id}: last_verified_date must use YYYY-MM-DD")
        for key in ("introduced_date", "last_action_date"):
            if record.get(key):
                try:
                    date.fromisoformat(record[key])
                except (TypeError, ValueError):
                    fail(f"{measure_id}: {key} must use YYYY-MM-DD")
        if record.get("congress_url"):
            parsed = urlparse(record["congress_url"])
            if parsed.scheme != "https" or parsed.netloc not in {"congress.gov", "www.congress.gov"}:
                fail(f"{measure_id}: congress_url must be an HTTPS congress.gov URL")

    html = SITE.read_text(encoding="utf-8")
    match = re.search(r'<script id="records" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        fail("index.html does not contain the embedded records dataset")
    embedded = json.loads(match.group(1))
    if embedded != records:
        fail("embedded index.html dataset differs from data/measures.json")
    if "Federal AI Safety &amp; Security Bill Tracker" not in html and "Federal AI Safety & Security Bill Tracker" not in html:
        fail("index.html does not appear to be the tracker site")

    print(f"Validated {len(records)} unique measures and the static site snapshot.")


if __name__ == "__main__":
    main()
