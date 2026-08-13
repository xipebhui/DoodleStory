from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.native_agent_g3_gate import (  # noqa: E402
    G3_REPORT_REF,
    G3_REQUEST_BUDGET,
    build_report,
    build_stopped_report,
    create_probe_run,
    http_request_rows,
    initialize_probe_tables,
    make_session_factory,
    preflight,
    run_request_count,
    run_z1,
    run_z2_stage_a,
    run_z2_stage_b,
    run_z3,
    run_z4,
    safe_error,
    sqlite_url,
    utc_now,
    validate_report,
    evaluate_z1,
    evaluate_z2,
    evaluate_z3,
    evaluate_z4,
)


RESULT_PREFIX = "G3_RESULT="


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed SiliconFlow Native Agent G3 zero-media gate."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument(
        "--internal-stage",
        choices=("z2a", "z2b"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--authorization-ref")
    parser.add_argument("--source-git-commit")
    parser.add_argument("--attempt-label")
    parser.add_argument("--previous-attempt-ref")
    parser.add_argument("--database-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--run-id", help=argparse.SUPPRESS)
    return parser.parse_args()


def run_migrations(database_path: Path) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = sqlite_url(database_path)
    completed = subprocess.run(
        [
            str(BACKEND / ".venv" / "Scripts" / "alembic.exe"),
            "-c",
            str(ROOT / "alembic.ini"),
            "upgrade",
            "head",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "temporary G3 database migration failed: "
            + (completed.stderr or completed.stdout)[-500:]
        )


def parse_child_result(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    if completed.returncode != 0:
        raise RuntimeError(
            "G3 child process failed: "
            + (completed.stderr or completed.stdout)[-500:]
        )
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line.removeprefix(RESULT_PREFIX))
    raise RuntimeError("G3 child process returned no structured result")


def run_child(
    *,
    stage: str,
    database_path: Path,
    run_id: str,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--internal-stage",
            stage,
            "--database-path",
            str(database_path),
            "--run-id",
            run_id,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return parse_child_result(completed)


def write_report(report: dict[str, object]) -> Path:
    path = ROOT / G3_REPORT_REF
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def execute_gate(
    *,
    authorization_ref: str,
    source_git_commit: str,
    attempt_label: str,
    previous_attempt_ref: str | None,
) -> int:
    started_at = utc_now()
    preflight_result = preflight(
        root=ROOT,
        source_git_commit=source_git_commit,
    )
    if not preflight_result["ok"]:
        report = build_stopped_report(
            root=ROOT,
            database_path=None,
            source_git_commit=source_git_commit,
            authorization_ref=authorization_ref,
            attempt_label=attempt_label,
            previous_attempt_ref=previous_attempt_ref,
            started_at=started_at,
            failed_case="preflight",
            error={
                "type": "BlockedPrecondition",
                "summary": ",".join(preflight_result["errors"]),
            },
        )
        write_report(report)
        print(json.dumps(report["gate_decision"], ensure_ascii=False))
        return 2

    report: dict[str, object] | None = None
    failed_case = "preflight"
    database_path: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="doodlestory-g3-") as temp_dir:
            database_path = Path(temp_dir) / "g3.db"
            run_migrations(database_path)
            initialize_probe_tables(database_path)
            session_factory = make_session_factory(database_path)
            z1_run_id = create_probe_run(session_factory, case_id="z1")
            z2_run_id = create_probe_run(
                session_factory,
                case_id="z2",
                tool_names=["echo_probe"],
            )
            z3_run_id = create_probe_run(session_factory, case_id="z3")

            failed_case = "z1"
            z1 = asyncio.run(run_z1(database_path, run_id=z1_run_id))
            if not evaluate_z1(
                z1,
                run_request_count(database_path, case_ids={"z1"}),
            ):
                raise RuntimeError("Z1 fixed assertions failed")

            failed_case = "z2a"
            z2a = run_child(
                stage="z2a",
                database_path=database_path,
                run_id=z2_run_id,
            )
            if run_request_count(database_path, case_ids={"z2a"}) != 1:
                raise RuntimeError("Z2 stage A request count is not one")

            failed_case = "z2b"
            z2b = run_child(
                stage="z2b",
                database_path=database_path,
                run_id=z2_run_id,
            )
            if not evaluate_z2(
                z2a,
                z2b,
                run_request_count(database_path, case_ids={"z2a", "z2b"}),
            ):
                raise RuntimeError("Z2 fixed assertions failed")

            failed_case = "z3"
            z3 = asyncio.run(run_z3(database_path, run_id=z3_run_id))
            if not evaluate_z3(
                z3,
                run_request_count(database_path, case_ids={"z3"}),
            ):
                raise RuntimeError("Z3 fixed assertions failed")

            failed_case = "z4"
            z4 = asyncio.run(run_z4(database_path))
            if not evaluate_z4(
                z4,
                run_request_count(database_path, case_ids={"z4"}),
            ):
                raise RuntimeError("Z4 fixed assertions failed")
            if run_request_count(database_path) > G3_REQUEST_BUDGET:
                raise RuntimeError("G3 provider request budget exceeded")

            report = build_report(
                root=ROOT,
                database_path=database_path,
                source_git_commit=source_git_commit,
                authorization_ref=authorization_ref,
                attempt_label=attempt_label,
                previous_attempt_ref=previous_attempt_ref,
                started_at=started_at,
                z1=z1,
                z2a=z2a,
                z2b=z2b,
                z3=z3,
                z4=z4,
            )
            errors = validate_report(report)
            if errors:
                raise RuntimeError("G3 report validation failed: " + ",".join(errors))
            write_report(report)
    except Exception as exc:
        if report is None:
            report = build_stopped_report(
                root=ROOT,
                database_path=database_path,
                source_git_commit=source_git_commit,
                authorization_ref=authorization_ref,
                attempt_label=attempt_label,
                previous_attempt_ref=previous_attempt_ref,
                started_at=started_at,
                failed_case=failed_case,
                error=safe_error(exc),
            )
            write_report(report)
        print(json.dumps(report["gate_decision"], ensure_ascii=False))
        return 2

    print(json.dumps(report["gate_decision"], ensure_ascii=False))
    return (
        0
        if report["gate_decision"]["status"]
        == "pass_for_s03_single_image_review"
        else 2
    )


def internal_stage(args: argparse.Namespace) -> int:
    if args.database_path is None or not args.run_id:
        raise SystemExit("internal G3 stage requires database path and run id")
    if args.internal_stage == "z2a":
        result = asyncio.run(
            run_z2_stage_a(args.database_path, run_id=args.run_id)
        )
    else:
        result = asyncio.run(
            run_z2_stage_b(args.database_path, run_id=args.run_id)
        )
    print(RESULT_PREFIX + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


def main() -> int:
    args = parse_args()
    if args.internal_stage:
        return internal_stage(args)
    if args.preflight:
        result = preflight(
            root=ROOT,
            source_git_commit=args.source_git_commit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2
    if (
        not args.authorization_ref
        or not args.source_git_commit
        or not args.attempt_label
    ):
        raise SystemExit(
            "--execute requires --authorization-ref, --source-git-commit and "
            "--attempt-label"
        )
    return execute_gate(
        authorization_ref=args.authorization_ref,
        source_git_commit=args.source_git_commit,
        attempt_label=args.attempt_label,
        previous_attempt_ref=args.previous_attempt_ref,
    )


if __name__ == "__main__":
    raise SystemExit(main())
