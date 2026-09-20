#!/usr/bin/env python3
"""Discover state AI-safety candidates through Open States; never publish them directly."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "discovery" / "openstates-candidates.json"
KEYWORDS = (
    '"artificial intelligence" safety',
    '"frontier model"',
    '"foundation model" incident',
    '"artificial intelligence" catastrophic risk',
    '"artificial intelligence" critical infrastructure',
    'deepfake security',
)


def request_json(url: str, api_key: str, *, max_attempts: int = 5) -> dict:
    request = urllib.request.Request(url, headers={"X-API-KEY": api_key, "User-Agent": "federal-ai-safety-legislation-tracker/1.0"})
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            retryable = error.code == 429 or 500 <= error.code < 600
            if not retryable or attempt == max_attempts - 1:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                delay = float(retry_after) if retry_after else min(2 ** attempt, 30)
            except ValueError:
                delay = min(2 ** attempt, 30)
            time.sleep(max(1.0, min(delay, 60.0)))
    raise RuntimeError("Open States request exhausted retries")


def discover(api_key: str, jurisdictions: list[str], per_query: int) -> list[dict]:
    candidates: dict[str, dict] = {}
    for jurisdiction in jurisdictions:
        for keyword in KEYWORDS:
            query = urllib.parse.urlencode({"jurisdiction": jurisdiction, "q": keyword, "per_page": per_query})
            payload = request_json(f"https://v3.openstates.org/bills?{query}", api_key)
            for bill in payload.get("results", []):
                key = bill.get("id") or "|".join((jurisdiction, bill.get("session", ""), bill.get("identifier", "")))
                candidate = candidates.setdefault(key, {
                    "openstates_id": bill.get("id"), "jurisdiction": jurisdiction,
                    "session": bill.get("session"), "identifier": bill.get("identifier"),
                    "title": bill.get("title"), "openstates_url": bill.get("openstates_url"),
                    "matched_queries": [], "review_status": "unverified_candidate",
                    "official_source_required": True,
                })
                candidate["matched_queries"].append(keyword)
            # Open States applies per-key request limits. A small deterministic
            # pause keeps the scheduled discovery job below normal burst limits.
            time.sleep(1.0)
    return sorted(candidates.values(), key=lambda item: (item["jurisdiction"], item.get("session") or "", item.get("identifier") or ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction", action="append", dest="jurisdictions", help="Two-letter state code; repeat as needed")
    parser.add_argument("--per-query", type=int, default=20)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    api_key = os.environ.get("OPENSTATES_API_KEY")
    if not api_key:
        raise SystemExit("OPENSTATES_API_KEY is required; register at https://openstates.org/accounts/signup/")
    jurisdictions = sorted(set(args.jurisdictions or ["ca", "co", "ny", "tn", "tx"]))
    candidates = discover(api_key, jurisdictions, args.per_query)
    output = {"generated_date": date.today().isoformat(), "review_notice": "Discovery only. Verify every candidate against an official state source before publication.", "candidates": candidates}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "
", encoding="utf-8")
    print(f"Wrote {len(candidates)} unverified candidates to {args.output}")


if __name__ == "__main__":
    main()
