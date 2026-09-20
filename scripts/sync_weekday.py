#!/usr/bin/env python3
"""Synchronize objective federal metadata and prepare review-gated changes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from automation_common import ROOT, automation_metadata, congress_json, govinfo_billstatus, parse_federal_bill, required_secret, snapshot_id, today, write_json

OBJECTIVE_FIELDS = {"title", "sponsor", "cosponsor_count", "committees", "introduced_date", "last_action", "last_action_date"}


def lifecycle_from_actions(actions: list[dict], current: str) -> str:
    text = " ".join(str(item.get("text", "")) for item in actions).lower()
    if "became public law" in text or "signed by president" in text:
        return "enacted"
    if "vetoed by president" in text:
        return "vetoed"
    if "passed senate" in text or "passed house" in text:
        return "passed_chamber"
    if "reported" in text or "ordered to be reported" in text:
        return "committee_advanced"
    if "committee" in text and ("markup" in text or "hearing" in text):
        return "committee_consideration"
    return current


def values(record: dict, bill: dict, actions: list[dict], cosponsor_count: int, committees: list[dict]) -> dict:
    latest = actions[0] if actions else {}
    sponsors = bill.get("sponsors") or []
    committee_names = sorted({item.get("name") for item in committees if item.get("name")})
    return {
        "title": bill.get("title") or record.get("title"),
        "sponsor": (" ".join(filter(None, (sponsors[0].get("firstName"), sponsors[0].get("lastName")))) if sponsors else None) or record.get("sponsor"),
        "cosponsor_count": cosponsor_count,
        "committees": committee_names or record.get("committees", []),
        "introduced_date": bill.get("introducedDate") or record.get("introduced_date"),
        "last_action": latest.get("text") or record.get("last_action"),
        "last_action_date": latest.get("actionDate") or record.get("last_action_date"),
        "lifecycle_status": lifecycle_from_actions(actions, record.get("lifecycle_status", "unknown")),
    }


def ensure_provenance(record: dict) -> None:
    source = next((item for item in record["sources"] if item["source_id"] == "official-congress"), None)
    if source:
        source["accessed_date"] = today()
    covered = set()
    for claim in record["claim_provenance"]:
        covered.update(claim["fields"])
    missing = sorted((OBJECTIVE_FIELDS | {"lifecycle_status"}) - covered)
    if missing:
        record["claim_provenance"].append({"claim_id": "automated-objective-metadata", "fields": missing, "source_ids": ["official-congress"], "note": "Machine-synchronized from the official API; human review required before merge."})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "automation" / "raw" / "weekday")
    parser.add_argument("--report", type=Path, default=ROOT / "data" / "automation" / "weekday-report.json")
    args = parser.parse_args()
    api_key = "fixture" if args.fixture_dir else required_secret("CONGRESS_API_KEY")
    govinfo_key = "fixture" if args.fixture_dir else required_secret("GOVINFO_API_KEY")
    changes = []
    for path in sorted((ROOT / "data" / "records").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        identity = parse_federal_bill(record)
        if not identity or record.get("entity_type") != "bill":
            continue
        congress, bill_type, number = identity
        prefix = f"{congress}-{bill_type}-{number}"
        if args.fixture_dir:
            fixture = json.loads((args.fixture_dir / f"{prefix}.json").read_text())
            bill, actions, cosponsors, committees = fixture["bill"], fixture.get("actions", []), fixture.get("cosponsors", []), fixture.get("committees", [])
            cosponsor_count = fixture.get("cosponsor_count", len(cosponsors))
            raw = fixture
        else:
            detail = congress_json(f"bill/{congress}/{bill_type}/{number}", api_key)
            actions_payload = congress_json(f"bill/{congress}/{bill_type}/{number}/actions", api_key, limit=250)
            cosponsor_payload = congress_json(f"bill/{congress}/{bill_type}/{number}/cosponsors", api_key, limit=250)
            committee_payload = congress_json(f"bill/{congress}/{bill_type}/{number}/committees", api_key, limit=250)
            bill = detail.get("bill", {})
            actions = actions_payload.get("actions", [])
            cosponsors = cosponsor_payload.get("cosponsors", [])
            cosponsor_count = cosponsor_payload.get("pagination", {}).get("count", len(cosponsors))
            committees = committee_payload.get("committees", [])
            govinfo = govinfo_billstatus(congress, bill_type, number, govinfo_key)
            raw = {"bill": bill, "actions": actions, "cosponsors": cosponsors, "committees": committees, "govinfo_billstatus": govinfo}
        proposed = values(record, bill, actions, cosponsor_count, committees)
        diff = {key: {"before": record.get(key), "after": value} for key, value in proposed.items() if record.get(key) != value}
        if not diff:
            continue
        write_json(args.raw_dir / today() / f"{prefix}-{snapshot_id(raw)}.json", raw)
        record.update(proposed)
        record.update(automation_metadata(1.0, ["objective-metadata-sync"], "weekday-status-sync"))
        record["last_verified_date"] = today()
        record["verification_level"] = "Official API metadata synchronized; human review pending"
        ensure_provenance(record)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changes.append({"record_id": record["record_id"], "changes": diff})
    if changes:
        write_json(args.report, {"generated_date": today(), "requires_human_review": True, "changes": changes})
    print(f"Prepared {len(changes)} record update(s); no production branch was modified.")


if __name__ == "__main__":
    main()
