#!/usr/bin/env python3
"""Shared, standard-library helpers for controlled legislation automation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "federal-ai-safety-legislation-tracker/2.0 (+https://github.com/shaanakshaikh/federal-ai-safety-legislation-tracker)"
CONGRESS_BILL_URL = re.compile(r"/(?P<congress>\d+)(?:st|nd|rd|th)-congress/(?P<chamber>house|senate)-bill/(?P<number>\d+)")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def snapshot_id(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()[:16]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def request_json(url: str, *, headers: dict[str, str] | None = None, payload: dict | None = None) -> dict:
    request_headers = {"Accept": "application/json", "User-Agent": USER_AGENT, **(headers or {})}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=request_headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def congress_json(path: str, api_key: str, **params: object) -> dict:
    params.update({"api_key": api_key, "format": "json"})
    return request_json(f"https://api.congress.gov/v3/{path}?{urllib.parse.urlencode(params)}")


def govinfo_billstatus(congress: int, bill_type: str, number: int, api_key: str) -> dict:
    package_id = f"BILLSTATUS-{congress}-{bill_type}{number}"
    query = urllib.parse.urlencode({"api_key": api_key})
    return request_json(f"https://api.govinfo.gov/packages/{package_id}/summary?{query}")


def parse_federal_bill(record: dict) -> tuple[int, str, int] | None:
    url = record.get("congress_url") or record.get("official_url") or ""
    match = CONGRESS_BILL_URL.search(url)
    if not match:
        return None
    bill_type = "hr" if match["chamber"] == "house" else "s"
    return int(match["congress"]), bill_type, int(match["number"])


def official_source_url(url: str | None) -> bool:
    if not url:
        return False
    host = urllib.parse.urlparse(url).hostname or ""
    return host.endswith(".gov") or host in {"congress.gov", "www.congress.gov"}


def automation_metadata(confidence: float, flags: list[str], workflow: str) -> dict:
    return {
        "agent_confidence": round(max(0.0, min(1.0, confidence)), 2),
        "agent_flags": sorted(set(flags)),
        "requires_human_review": True,
        "automation_workflow": workflow,
        "automation_generated_at": utc_now(),
    }


def required_secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def today() -> str:
    return date.today().isoformat()
