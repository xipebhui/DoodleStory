#!/usr/bin/env python3
"""Validate Maze Controller file-state and experiment readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]

REQUIRED_STATE_FILES = [
    "controller_constitution.md",
    "strategy_memory.md",
    "rubric.md",
    "rejected_patterns.md",
    "persona_wounds.md",
    "keyword_weights.json",
    "category_weights.json",
    "account_fit_profile.json",
    "account_style_bindings.json",
    "narrative_persona_profiles.json",
    "successful_hypotheses.jsonl",
    "failed_hypotheses.jsonl",
    "prediction_errors.jsonl",
]

REQUIRED_PREDICTION_FIELDS = [
    "hypothesis",
    "expected_metric",
    "account_group",
    "fixed_variables",
    "changed_variable",
    "narrative_persona_profile",
    "review_checkpoints",
    "market_evidence",
    "risk_notes",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_jsonl(path: Path) -> list[str]:
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_no}: invalid JSONL: {exc}")
    return errors


def validate_state(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    state_dir = root / "content-lab" / "strategy_state"
    for name in REQUIRED_STATE_FILES:
        path = state_dir / name
        if not path.exists():
            errors.append(f"missing strategy_state file: {path}")
            continue
        if name.endswith(".json"):
            try:
                payload = load_json(path)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}: invalid JSON: {exc}")
                continue
            if name == "account_style_bindings.json":
                if not isinstance(payload, dict) or not isinstance(payload.get("accounts"), dict):
                    errors.append(f"{path}: account_style_bindings.json must contain an accounts object")
                else:
                    for account, binding in payload["accounts"].items():
                        if not isinstance(binding, dict):
                            errors.append(f"{path}: account `{account}` binding must be an object")
                            continue
                        if not binding.get("style_id"):
                            errors.append(f"{path}: account `{account}` missing style_id")
        if name.endswith(".jsonl"):
            errors.extend(validate_jsonl(path))
    for folder in ["experiments", "market_scans", "content_library/items"]:
        path = root / "content-lab" / folder
        if not path.exists():
            warnings.append(f"missing optional workspace folder: {path}")
    return errors, warnings


def validate_experiment(root: Path, experiment_id: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    exp_dir = root / "content-lab" / "experiments" / experiment_id
    if not exp_dir.exists():
        return [f"missing experiment directory: {exp_dir}"], warnings

    for name in ["experiment.md", "prediction.json", "publish_plan.json", "deviation_review.md", "strategy_update.json"]:
        path = exp_dir / name
        if not path.exists():
            errors.append(f"missing experiment file: {path}")

    prediction_path = exp_dir / "prediction.json"
    if prediction_path.exists():
        try:
            prediction = load_json(prediction_path)
            missing = [field for field in REQUIRED_PREDICTION_FIELDS if field not in prediction]
            if missing:
                errors.append(f"{prediction_path}: missing prediction fields: {', '.join(missing)}")
            incomplete = [field for field in REQUIRED_PREDICTION_FIELDS if not prediction.get(field)]
            if incomplete:
                warnings.append(f"{prediction_path}: incomplete prediction fields: {', '.join(incomplete)}")
            persona = prediction.get("narrative_persona_profile")
            if isinstance(persona, dict):
                persona_missing = [
                    field
                    for field in [
                        "profile_id",
                        "crowd_desire",
                        "moral_position",
                        "emotion_curve",
                        "taboo_boundary",
                        "comment_trigger",
                    ]
                    if not persona.get(field)
                ]
                if persona_missing:
                    warnings.append(f"{prediction_path}: incomplete narrative_persona_profile fields: {', '.join(persona_missing)}")
        except json.JSONDecodeError as exc:
            errors.append(f"{prediction_path}: invalid JSON: {exc}")

    post_results_dir = exp_dir / "post_results"
    if not post_results_dir.exists():
        errors.append(f"missing post_results directory: {post_results_dir}")
    else:
        result_files = [item for item in post_results_dir.iterdir() if item.name != ".gitkeep"]
        if not result_files:
            warnings.append(f"{post_results_dir}: no post result files yet")
    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate content iteration controller state.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="DoodleStory project root")
    parser.add_argument("--experiment-id", help="Optional experiment id to validate")
    args = parser.parse_args()

    errors, warnings = validate_state(args.root)
    if args.experiment_id:
        exp_errors, exp_warnings = validate_experiment(args.root, args.experiment_id)
        errors.extend(exp_errors)
        warnings.extend(exp_warnings)

    payload = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
