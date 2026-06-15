#!/usr/bin/env python3
"""Append a reviewed prediction error to strategy_state/prediction_errors.jsonl."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
REQUIRED_FIELDS = [
    "experiment_id",
    "post_id",
    "prediction",
    "expected_metric",
    "actual_metric",
    "error_type",
    "diagnosis",
    "rule_update_candidate",
]


def load_payload(path: Path | None, inline: str | None) -> dict[str, Any]:
    if path and inline:
        raise ValueError("Use either --json-file or --json, not both")
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    if inline:
        return json.loads(inline)
    raise ValueError("Missing --json-file or --json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append one prediction error JSON object.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="DoodleStory project root")
    parser.add_argument("--json-file", type=Path, help="Path to reviewed prediction error JSON")
    parser.add_argument("--json", help="Inline reviewed prediction error JSON")
    args = parser.parse_args()

    payload = load_payload(args.json_file, args.json)
    missing = [field for field in REQUIRED_FIELDS if not payload.get(field)]
    if missing:
        raise SystemExit(f"Missing required fields: {', '.join(missing)}")

    payload.setdefault("recorded_at", datetime.now().isoformat(timespec="seconds"))
    path = args.root / "content-lab" / "strategy_state" / "prediction_errors.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"appended": str(path), "experiment_id": payload["experiment_id"], "post_id": payload["post_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
