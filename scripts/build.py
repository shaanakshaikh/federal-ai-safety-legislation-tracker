#!/usr/bin/env python3
"""Build every published data format from data/records/*.json."""

from __future__ import annotations

import argparse, csv, html, io, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = ROOT / "data" / "records"
TEMPLATE = ROOT / "templates" / "index.html"
CSV_COLUMNS = ["record_id", "measure_id", "title", "entity_type", "jurisdiction_level", "jurisdiction_state", "session", "congress", "chamber", "scope", "primary_category", "sponsor", "sponsor_party", "sponsor_state", "cosponsor_count", "committees", "introduced_date", "last_action_date", "lifecycle_status", "status", "public_law_number", "enacted_date", "effective_date", "responsible_agencies", "implementation_status", "advance_tier", "summary", "committee_dynamics", "advance_rationale", "official_url", "last_verified_date", "verification_level"]


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_records() -> list[dict]:
    records = []
    for path in sorted(RECORDS_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8")); record["_source_file"] = path.name
        records.append(record)
    return sorted(records, key=lambda item: item["record_id"])


def public_record(record: dict) -> dict:
    return {key: value for key, value in record.items() if not key.startswith("_")}


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def csv_bytes(records: list[dict]) -> bytes:
    output = io.StringIO(newline=""); writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n"); writer.writeheader()
    for record in records:
        row = {key: record.get(key) for key in CSV_COLUMNS}
        row["jurisdiction_level"] = record["jurisdiction"]["level"]
        row["jurisdiction_state"] = record["jurisdiction"].get("state")
        public_law = record.get("public_law") or {}
        state_law = record.get("state_law") or {}
        implementation = record.get("implementation") or {}
        row["public_law_number"] = public_law.get("number")
        row["enacted_date"] = public_law.get("enacted_date") or state_law.get("enacted_date")
        row["effective_date"] = state_law.get("effective_date")
        row["responsible_agencies"] = implementation.get("responsible_agencies", [])
        row["implementation_status"] = "; ".join(item.get("status", "") for item in implementation.get("agency_status", []))
        row["official_url"] = record.get("official_url") or record.get("congress_url")
        for key, value in row.items():
            if isinstance(value, list): row[key] = "; ".join(map(str, value))
            elif value is None: row[key] = ""
        writer.writerow(row)
    return output.getvalue().encode()


def search_index(records: list[dict]) -> list[dict]:
    fields = ("record_id", "measure_id", "title", "entity_type", "scope", "primary_category", "status", "lifecycle_status", "summary", "session", "congress")
    result = []
    for record in records:
        terms = [str(record.get(field, "")) for field in fields] + record.get("secondary_categories", []) + record.get("committees", [])
        terms += list(filter(None, [record.get("sponsor"), record["jurisdiction"].get("state")]))
        terms += (record.get("implementation") or {}).get("responsible_agencies", [])
        result.append({"record_id": record["record_id"], "measure_id": record["measure_id"], "title": record["title"], "url": f"pages/{record['record_id']}.html", "text": " ".join(terms).lower()})
    return result


def record_page(record: dict) -> bytes:
    esc = lambda value: html.escape(str(value or ""))
    source_items = "".join((f'<li><a href="{esc(s.get("url"))}">{esc(s["title"])}</a> — accessed {esc(s["accessed_date"])}</li>' if s.get("url") else f'<li>{esc(s["title"])} — accessed {esc(s["accessed_date"])}</li>') for s in record["sources"])
    claim_items = "".join(f'<li><strong>{esc(c["claim_id"])}</strong>: {esc(", ".join(c["fields"]))} <small>(sources: {esc(", ".join(c["source_ids"]))})</small></li>' for c in record["claim_provenance"])
    implementation = record.get("implementation") or {}
    deadline_items = "".join(f'<li><strong>{esc(item.get("date") or "Ongoing")}</strong>: {esc(item.get("requirement"))} — {esc(item.get("status"))}</li>' for item in implementation.get("deadlines", []))
    implementation_section = f'<h2>Implementation</h2><p><strong>Responsible agencies:</strong> {esc(", ".join(implementation.get("responsible_agencies", [])) or "Not specified")}</p><ul>{deadline_items}</ul>' if implementation else ""
    content = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(record['measure_id'])} — {esc(record['title'])}</title><style>body{{font:16px/1.55 system-ui;max-width:860px;margin:40px auto;padding:0 20px;color:#17252b}}a{{color:#075f72}}dt{{font-weight:700;margin-top:12px}}dd{{margin-left:0}}small{{color:#52656d}}</style></head><body><p><a href="../index.html">← Tracker</a></p><main><p>{esc(record['entity_type'].title())} · {esc(record['jurisdiction']['level'].title())} · {esc(record['lifecycle_status'])}</p><h1>{esc(record['measure_id'])}: {esc(record['title'])}</h1><p>{esc(record['summary'])}</p><dl><dt>Status</dt><dd>{esc(record['status'])}</dd><dt>Session</dt><dd>{esc(record.get('session') or (str(record.get('congress')) + 'th Congress' if record.get('congress') else 'Not captured'))}</dd><dt>Last action</dt><dd>{esc(record.get('last_action'))}</dd><dt>Primary category</dt><dd>{esc(record['primary_category'])}</dd><dt>Last verified</dt><dd>{esc(record['last_verified_date'])}</dd></dl>{implementation_section}<h2>Sources</h2><ul>{source_items}</ul><h2>Claim provenance</h2><ul>{claim_items}</ul></main></body></html>'''
    return content.encode()


def outputs(records_with_meta: list[dict]) -> dict[Path, bytes]:
    records = [public_record(record) for record in records_with_meta]
    compact = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    site = TEMPLATE.read_text(encoding="utf-8").replace("__RECORDS_JSON__", compact)
    site = re.sub(r'(<div class="num" id="metricTotal">).*?(</div>)', rf'\g<1>{len(records)}\2', site)
    site = re.sub(r'(<strong id="resultCount">).*?(</strong>)', rf'\g<1>{len(records)}\2', site)
    site = site.replace('<strong id="metricTierTotal">36</strong>', f'<strong id="metricTierTotal">{len(records)}</strong>')
    generated = {ROOT/"data/measures.json": json_bytes(records), ROOT/"data/measures.js": ("window.LEGISLATION_RECORDS="+compact+";\n").encode(), ROOT/"data/measures.csv": csv_bytes(records), ROOT/"data/search-index.json": json_bytes(search_index(records)), ROOT/"index.html": site.encode()}
    generated.update({ROOT/"pages"/f"{r['record_id']}.html": record_page(r) for r in records})
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    records = load_records()
    if not records: raise SystemExit("no canonical records found")
    expected, stale = outputs(records), []
    for path, content in expected.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != content: stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    if stale: raise SystemExit("generated files are stale; run python3 scripts/build.py:\n- " + "\n- ".join(stale))
    print(f"{'Checked' if args.check else 'Generated'} {len(expected)} artifacts from {len(records)} canonical records.")


if __name__ == "__main__": main()
