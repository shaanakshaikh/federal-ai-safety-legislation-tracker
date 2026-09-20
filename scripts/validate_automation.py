#!/usr/bin/env python3
"""Fail closed when an automation proposal lacks provenance or review controls."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from automation_common import ROOT


def fail(message: str) -> None:
    raise SystemExit(f"automation validation error: {message}")


def validate_candidate(candidate: dict, index: int) -> None:
    prefix = f"candidate {index}"
    if candidate.get("requires_human_review") is not True:
        fail(f"{prefix} must require human review")
    confidence = candidate.get("agent_confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        fail(f"{prefix} has invalid agent_confidence")
    if not isinstance(candidate.get("agent_flags"), list) or not candidate["agent_flags"]:
        fail(f"{prefix} requires at least one uncertainty or review flag")
    if candidate.get("jurisdiction_level") == "state" and "official-source-verification-required" not in candidate["agent_flags"]:
        fail(f"{prefix} state lead is missing the official-source verification flag")
    for key in ("official_url", "openstates_url"):
        if candidate.get(key) and urlparse(candidate[key]).scheme != "https":
            fail(f"{prefix} has a non-HTTPS source URL")


def main() -> None:
    path = ROOT / "data" / "automation" / "weekly-candidates.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for index, candidate in enumerate(payload.get("candidates", [])):
            validate_candidate(candidate, index)
    for path in sorted((ROOT / "data" / "records").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if any(key in record for key in ("agent_confidence", "agent_flags", "requires_human_review")):
            if record.get("requires_human_review") is not True:
                fail(f"{path.name} must require human review")
            if not isinstance(record.get("agent_confidence"), (int, float)) or not 0 <= record["agent_confidence"] <= 1:
                fail(f"{path.name} has invalid agent_confidence")
            if not isinstance(record.get("agent_flags"), list) or not record["agent_flags"]:
                fail(f"{path.name} requires agent_flags")
    print("Validated automation review gates and uncertainty metadata.")


if __name__ == "__main__":
    main()
