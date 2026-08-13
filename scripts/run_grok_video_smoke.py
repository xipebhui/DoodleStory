from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from app.core.config import get_settings
from app.services.grok_video_generation import request_grokcli_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one explicit grokcli T2V/I2V smoke through DoodleStory's adapter."
    )
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--duration", type=int, default=8)
    parser.add_argument("--aspect", default="16:9")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--grokcli-executable", required=True)
    parser.add_argument("--grokcli-home", type=Path, required=True)
    return parser.parse_args()


def require_new_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists():
        raise RuntimeError(f"拒绝覆盖已有文件：{resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def main() -> int:
    args = parse_args()
    output_path = require_new_path(args.output)
    report_path = require_new_path(args.report)
    image_path = args.image.expanduser().resolve() if args.image else None
    settings = get_settings().model_copy(
        update={
            "grokcli_executable": args.grokcli_executable,
            "grokcli_home": str(args.grokcli_home.expanduser().resolve()),
        }
    )
    try:
        generated = request_grokcli_video(
            prompt=args.prompt,
            image_path=image_path,
            duration_seconds=args.duration,
            aspect_ratio=args.aspect,
            settings=settings,
        )
    except Exception as exc:
        failure_report = {
            "schema_version": 1,
            "record_kind": "grokcli_video_smoke",
            "record_status": "failed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "call_count": 1,
            "automatic_retry": False,
            "provider_fallback": False,
            "provider": "grok",
            "model": settings.grokcli_video_model,
            "mode": "image_to_video" if image_path else "text_to_video",
            "prompt": args.prompt,
            "source_image": str(args.image) if args.image else None,
            "output": None,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        report_path.write_text(
            json.dumps(failure_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise
    output_path.write_bytes(generated.content)
    report = {
        "schema_version": 1,
        "record_kind": "grokcli_video_smoke",
        "record_status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "call_count": 1,
        "automatic_retry": False,
        "provider_fallback": False,
        "provider": generated.provider,
        "model": generated.model,
        "mode": generated.mode,
        "prompt": args.prompt,
        "source_image": str(args.image) if args.image else None,
        "output": str(args.output),
        "content_type": generated.content_type,
        "byte_size": len(generated.content),
        "sha256": hashlib.sha256(generated.content).hexdigest(),
        "duration_ms": generated.duration_ms,
        "duration_in_frames": generated.duration_in_frames,
        "fps": generated.fps,
        "width": generated.width,
        "height": generated.height,
        "template_id": generated.template_id,
        "renderer_version": generated.renderer_version,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
