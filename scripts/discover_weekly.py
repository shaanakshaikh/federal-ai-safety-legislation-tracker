#!/usr/bin/env python3
"""Capture weekly federal/state candidates and optionally classify them with AI."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from automation_common import ROOT, automation_metadata, congress_json, request_json, snapshot_id, today, write_json
from discover_openstates import discover as discover_states

PROMPT = ROOT / "prompts" / "weekly-relevance-classification.md"


def discover_federal(api_key: str, days: int) -> tuple[list[dict], dict]:
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=days)
    payload = congress_json("bill", api_key, fromDateTime=start.isoformat().replace("+00:00", "Z"), toDateTime=end.isoformat().replace("+00:00", "Z"), limit=250)
    candidates = []
    for bill in payload.get("bills", []):
        title = bill.get("title", "")
        if any(term in title.lower() for term in ("artificial intelligence", "machine learning", "deepfake", "frontier model", "foundation model")):
            candidates.append({"jurisdiction_level": "federal", "measure_id": f"{bill.get('type', '')} {bill.get('number', '')}".strip(), "title": title, "congress": bill.get("congress"), "official_url": bill.get("url"), "update_date": bill.get("updateDate")})
    return candidates, payload


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
    payload = {"model": model, "instructions": PROMPT.read_text(encoding="utf-8"), "input": json.dumps(candidates), "text": {"format": {"type": "json_schema", "name": "legislation_classification", "strict": True, "schema": schema}}}
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
    if not congress_key or not openstates_key:
        raise SystemExit("CONGRESS_API_KEY and OPENSTATES_API_KEY are required for comprehensive discovery")
    federal, raw_federal = discover_federal(congress_key, args.days)
    states = args.states or ["ca", "co", "ny", "tn", "tx"]
    state_candidates = discover_states(openstates_key, states, 20)
    normalized_states = []
    for item in state_candidates:
        normalized_states.append({**item, "jurisdiction_level": "state", "state": item.get("jurisdiction")})
    raw = {"federal": raw_federal, "state_candidates": normalized_states}
    raw_path = ROOT / "data" / "automation" / "raw" / "sunday" / today() / f"discovery-{snapshot_id(raw)}.json"
    write_json(raw_path, raw)
    candidates = classify(federal + normalized_states)
    write_json(args.output, {"generated_date": today(), "review_notice": "Discovery and drafting only. Every candidate requires human review; state candidates also require an official state source.", "prompt": str(PROMPT.relative_to(ROOT)), "candidates": candidates})
    print(f"Prepared {len(candidates)} review-gated candidate(s).")


if __name__ == "__main__":
    main()
