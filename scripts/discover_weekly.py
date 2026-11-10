#!/usr/bin/env python3
"""Capture weekly federal/state candidates and optionally classify them with AI."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from automation_common import ROOT, automation_metadata, congress_json, request_json, snapshot_id, today, write_json
from discover_openstates import discover as discover_states

PROMPT = ROOT / "prompts" / "weekly-relevance-classification.md"
POLICY = ROOT / "methodology" / "inclusion-criteria.md"


BILL_TYPES = {
    "hr": ("H.R.", "house-bill"),
    "s": ("S.", "senate-bill"),
    "hjres": ("H.J.Res.", "house-joint-resolution"),
    "sjres": ("S.J.Res.", "senate-joint-resolution"),
    "hconres": ("H.Con.Res.", "house-concurrent-resolution"),
    "sconres": ("S.Con.Res.", "senate-concurrent-resolution"),
    "hres": ("H.Res.", "house-resolution"),
    "sres": ("S.Res.", "senate-resolution"),
}
DISCOVERY_TERMS = (
    "artificial intelligence", "machine learning", "deepfake", "deep fake", "synthetic media",
    "frontier model", "foundation model", "large language model", "model weights",
    "automated decision system", "automated decisionmaking", "algorithmic impact assessment",
    "algorithmic discrimination", "autonomous weapon", "digital replica", "generative AI",
    "AI system", "AI model", "AI agent", "AI chatbot", "AI risk", "AI safety", "AI security",
    "AI-generated", "AI-enabled", "AI-assisted", "AI-powered",
)
TITLE_PATTERN = re.compile(r"\b(?:AI\b|A\.I\.(?!\w)|" + "|".join(re.escape(term) for term in DISCOVERY_TERMS) + r")", re.I)
PACKAGE_PATTERN = re.compile(r"BILLS-(\d+)([a-z]+)(\d+)[a-z]+", re.I)
FIRST_TRACKED_CONGRESS = 118


def recent_congress_bills(api_key: str, since: str, until: str) -> list[dict]:
    bills = []
    while True:
        page = congress_json("bill", api_key, fromDateTime=since, toDateTime=until, limit=250, offset=len(bills))
        items = page["bills"]
        bills.extend(items)
        pagination = page["pagination"]
        if not pagination.get("next"):
            if len(bills) < pagination["count"]:
                raise RuntimeError("Congress.gov ended pagination before returning the reported bill count")
            return bills
        if not items:
            raise RuntimeError("Congress.gov returned an empty page with a next page")


def recent_govinfo_matches(api_key: str, since: str, until: str) -> list[dict]:
    phrases = " or ".join(f'"{term}"' for term in DISCOVERY_TERMS)
    query = f"collection:bills and lastModified:range({since},{until}) and ({phrases})"
    url = "https://api.govinfo.gov/search"
    offset = "*"
    results = []
    while True:
        page = request_json(url, headers={"X-Api-Key": api_key}, payload={
            "query": query, "pageSize": 250, "offsetMark": offset, "resultLevel": "package",
            "sorts": [{"field": "lastModified", "sortOrder": "DESC"}],
        })
        items = page["results"]
        results.extend(items)
        if len(results) >= page["count"]:
            return results
        next_offset = page.get("offsetMark")
        if not items or not next_offset or next_offset == offset:
            raise RuntimeError("GovInfo ended pagination before returning the reported match count")
        offset = next_offset


def discover_federal(congress_key: str, govinfo_key: str, days: int) -> tuple[list[dict], dict]:
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=days)
    since, until = (date.isoformat().replace("+00:00", "Z") for date in (start, end))
    congress_bills = recent_congress_bills(congress_key, since, until)
    text_hits = recent_govinfo_matches(govinfo_key, since, until)
    congress_by_id = {
        (int(bill["congress"]), bill["type"].lower(), int(bill["number"])): bill
        for bill in congress_bills
    }
    text_by_id = {}
    for hit in text_hits:
        match = PACKAGE_PATTERN.fullmatch(hit["packageId"])
        if not match:
            continue
        congress, bill_type, number = match.groups()
        identity = (int(congress), bill_type.lower(), int(number))
        text_by_id.setdefault(identity, {})[hit["packageId"]] = hit

    title_ids = {identity for identity, bill in congress_by_id.items() if TITLE_PATTERN.search(bill.get("title") or "")}
    candidates = []
    for congress, bill_type, number in sorted(title_ids | text_by_id.keys()):
        if congress < FIRST_TRACKED_CONGRESS or bill_type not in BILL_TYPES:
            continue
        identity = (congress, bill_type, number)
        bill = congress_by_id.get(identity, {})
        versions = list(text_by_id.get(identity, {}).values())
        latest_text = versions[0] if versions else {}
        abbreviation, route = BILL_TYPES[bill_type]
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(congress % 10, "th") if congress % 100 not in (11, 12, 13) else "th"
        sources = []
        if identity in title_ids:
            sources.append("congress-title")
        if versions:
            sources.append("govinfo-full-text")
        candidates.append({
            "jurisdiction_level": "federal",
            "measure_id": f"{abbreviation} {number}",
            "congress": congress,
            "bill_type": bill_type,
            "bill_number": number,
            "title": bill.get("title") or latest_text["title"],
            "official_url": f"https://www.congress.gov/bill/{congress}{suffix}-congress/{route}/{number}",
            "update_date": bill.get("updateDate") or latest_text.get("lastModified"),
            "discovery_sources": sources,
            "govinfo_text_matches": [
                {"package_id": hit["packageId"], "url": f"https://www.govinfo.gov/app/details/{hit['packageId']}"}
                for hit in versions
            ],
        })
    return candidates, {
        "window": {"from": since, "to": until},
        "congress_bills": congress_bills,
        "govinfo_full_text_matches": text_hits,
    }


def classify(candidates: list[dict]) -> list[dict]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or not candidates:
        return [{**item, **automation_metadata(0.25, ["ai-classification-unavailable", "official-source-verification-required", *( ["govinfo-verification-required"] if item.get("jurisdiction_level") == "federal" else [] )], "sunday-discovery"), "classification": "unreviewed"} for item in candidates]
    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "classification": {"enum": ["include", "exclude", "uncertain"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "flags": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                    },
                    "required": ["index", "classification", "confidence", "flags", "rationale"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }
    model = os.environ.get("AUTOMATION_MODEL", "").strip()
    if not model:
        raise SystemExit("AUTOMATION_MODEL is required when OPENAI_API_KEY is configured")
    payload = {"model": model, "instructions": PROMPT.read_text(encoding="utf-8") + "\n\n" + POLICY.read_text(encoding="utf-8"), "input": json.dumps(candidates), "text": {"format": {"type": "json_schema", "name": "legislation_classification", "strict": True, "schema": schema}}}
    response = request_json("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {key}"}, payload=payload)
    output_text = response.get("output_text")
    if not output_text:
        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    output_text = content.get("text")
    results = json.loads(output_text)["results"]
    by_index = {item["index"]: item for item in results}
    classified = []
    for index, candidate in enumerate(candidates):
        result = by_index.get(index, {"classification": "uncertain", "confidence": 0, "flags": ["classifier-output-missing"], "rationale": "No classification returned."})
        flags = result["flags"] + ["official-source-verification-required"]
        if candidate.get("jurisdiction_level") == "federal":
            flags.append("govinfo-verification-required")
        classified.append({**candidate, **automation_metadata(result["confidence"], flags, "sunday-discovery"), "classification": result["classification"], "classification_rationale": result["rationale"]})
    return classified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=8)
    parser.add_argument("--state", action="append", dest="states")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "automation" / "weekly-candidates.json")
    args = parser.parse_args()
    congress_key = os.environ.get("CONGRESS_API_KEY", "").strip()
    openstates_key = os.environ.get("OPENSTATES_API_KEY", "").strip()
    govinfo_key = os.environ.get("GOVINFO_API_KEY", "").strip()
    if not congress_key or not openstates_key or not govinfo_key:
        raise SystemExit("CONGRESS_API_KEY, GOVINFO_API_KEY, and OPENSTATES_API_KEY are required for comprehensive discovery")
    if args.days < 1:
        parser.error("--days must be positive")
    federal, raw_federal = discover_federal(congress_key, govinfo_key, args.days)
    states = args.states or ["ca", "co", "ny", "tn", "tx"]
    state_candidates = discover_states(openstates_key, states, 20)
    normalized_states = []
    for item in state_candidates:
        normalized_states.append({**item, "jurisdiction_level": "state", "state": item.get("jurisdiction")})
    raw = {"federal": raw_federal, "state_candidates": normalized_states}
    raw_path = ROOT / "data" / "automation" / "raw" / "sunday" / today() / f"discovery-{snapshot_id(raw)}.json"
    write_json(raw_path, raw)
    combined = federal + normalized_states
    candidates = [
        candidate
        for start in range(0, len(combined), 40)
        for candidate in classify(combined[start:start + 40])
    ]
    write_json(args.output, {"generated_date": today(), "review_notice": "Discovery and drafting only. Every candidate requires human review; state candidates also require an official state source.", "prompt": str(PROMPT.relative_to(ROOT)), "candidates": candidates})
    print(f"Prepared {len(candidates)} review-gated candidate(s).")


if __name__ == "__main__":
    main()
