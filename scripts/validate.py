#!/usr/bin/env python3
"""Validate canonical records, provenance links, and generated artifacts."""

import re, subprocess, sys
from datetime import date
from urllib.parse import urlparse
from build import ROOT, load_records

REQUIRED = {"record_id", "measure_id", "title", "entity_type", "jurisdiction", "chamber", "scope", "primary_category", "status", "lifecycle_status", "last_verified_date", "sources", "claim_provenance"}
ENTITY_TYPES = {"bill", "amendment", "provision", "law"}
LIFECYCLES = {"introduced", "referred", "committee_consideration", "committee_advanced", "floor", "passed_chamber", "passed_legislature", "enacted", "vetoed", "failed", "withdrawn", "inactive", "unknown"}
CHAMBERS = {"House", "Senate", "Bicameral", "Executive", "State legislature", "N/A"}
SCOPES = {"Core", "Adjacent", "Vehicle"}
RECORD_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

def fail(message): raise SystemExit(f"validation error: {message}")
def valid_date(value, label, nullable=False):
    if nullable and value is None: return
    try: date.fromisoformat(value)
    except (TypeError, ValueError): fail(f"{label} must use YYYY-MM-DD")

def main():
    records = load_records()
    if not records: fail("data/records must contain at least one JSON record")
    seen_ids, seen_measures = set(), set()
    for record in records:
        filename = record["_source_file"]
        missing = REQUIRED - record.keys()
        if missing: fail(f"{filename} missing: {', '.join(sorted(missing))}")
        rid = record["record_id"]
        if not isinstance(rid, str) or not RECORD_ID.fullmatch(rid): fail(f"{filename}: invalid record_id")
        if filename != f"{rid}.json": fail(f"{filename}: filename must match record_id")
        if rid in seen_ids or record["measure_id"] in seen_measures: fail(f"{filename}: duplicate identifier")
        seen_ids.add(rid); seen_measures.add(record["measure_id"])
        if record["entity_type"] not in ENTITY_TYPES: fail(f"{rid}: invalid entity_type")
        jurisdiction = record["jurisdiction"]
        if not isinstance(jurisdiction, dict) or jurisdiction.get("level") not in {"federal", "state"} or jurisdiction.get("country") != "US": fail(f"{rid}: invalid jurisdiction")
        if jurisdiction["level"] == "state" and not re.fullmatch(r"[A-Z]{2}", jurisdiction.get("state", "")): fail(f"{rid}: state jurisdiction requires a state code")
        if jurisdiction["level"] == "federal" and jurisdiction.get("state") is not None: fail(f"{rid}: federal jurisdiction state must be null")
        if record["lifecycle_status"] not in LIFECYCLES: fail(f"{rid}: invalid lifecycle_status")
        if record["chamber"] not in CHAMBERS or record["scope"] not in SCOPES: fail(f"{rid}: invalid chamber or scope")
        valid_date(record["last_verified_date"], f"{rid}.last_verified_date")
        for key in ("introduced_date", "last_action_date"): valid_date(record.get(key), f"{rid}.{key}", nullable=True)
        if record.get("public_law"):
            if record["jurisdiction"]["level"] != "federal": fail(f"{rid}: public_law is federal-only")
            valid_date(record["public_law"].get("enacted_date"), f"{rid}.public_law.enacted_date")
        if record.get("state_law"):
            if record["jurisdiction"]["level"] != "state": fail(f"{rid}: state_law requires state jurisdiction")
            valid_date(record["state_law"].get("enacted_date"), f"{rid}.state_law.enacted_date")
            valid_date(record["state_law"].get("effective_date"), f"{rid}.state_law.effective_date", nullable=True)
        sources = record["sources"]
        if not isinstance(sources, list) or not sources: fail(f"{rid}: sources must be non-empty")
        source_ids = set()
        for source in sources:
            if not {"source_id", "title", "source_type", "accessed_date"} <= source.keys(): fail(f"{rid}: incomplete source")
            if source["source_id"] in source_ids: fail(f"{rid}: duplicate source_id")
            source_ids.add(source["source_id"]); valid_date(source["accessed_date"], f"{rid}.source.accessed_date")
            if source.get("url") and urlparse(source["url"]).scheme != "https": fail(f"{rid}: source URL must use HTTPS")
        if record["jurisdiction"]["level"] == "state" and not any(
            source.get("source_type") == "official" for source in sources
        ):
            fail(f"{rid}: state records require an official source")
        implementation = record.get("implementation")
        if implementation:
            for item in implementation.get("deadlines", []):
                valid_date(item.get("date"), f"{rid}.implementation.deadline", nullable=True)
                unknown = set(item.get("source_ids", [])) - source_ids
                if unknown: fail(f"{rid}: deadline references unknown sources {sorted(unknown)}")
            for item in implementation.get("agency_status", []):
                valid_date(item.get("as_of"), f"{rid}.implementation.agency_status.as_of")
                unknown = set(item.get("source_ids", [])) - source_ids
                if unknown: fail(f"{rid}: agency status references unknown sources {sorted(unknown)}")
        claims = record["claim_provenance"]
        if not isinstance(claims, list) or not claims: fail(f"{rid}: claim_provenance must be non-empty")
        covered = set()
        for claim in claims:
            if not {"claim_id", "fields", "source_ids"} <= claim.keys() or not claim["fields"] or not claim["source_ids"]: fail(f"{rid}: incomplete provenance claim")
            unknown = set(claim["source_ids"]) - source_ids
            if unknown: fail(f"{rid}: claim references unknown sources {sorted(unknown)}")
            covered.update(claim["fields"])
        for field in ("title", "status", "summary"):
            if field not in covered: fail(f"{rid}: {field} lacks claim-level provenance")
        automation_fields = {"agent_confidence", "agent_flags", "requires_human_review"}
        if automation_fields & record.keys():
            if not automation_fields <= record.keys(): fail(f"{rid}: incomplete automation review metadata")
            if record["requires_human_review"] is not True: fail(f"{rid}: agent-authored changes must require human review")
            if not isinstance(record["agent_confidence"], (int, float)) or not 0 <= record["agent_confidence"] <= 1: fail(f"{rid}: invalid agent_confidence")
            if not isinstance(record["agent_flags"], list) or not record["agent_flags"]: fail(f"{rid}: agent_flags must be non-empty")
    result = subprocess.run([sys.executable, str(ROOT/"scripts/build.py"), "--check"])
    if result.returncode: raise SystemExit(result.returncode)
    print(f"Validated {len(records)} canonical records, provenance, and generated artifacts.")

if __name__ == "__main__": main()
