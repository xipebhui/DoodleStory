#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import unquote


DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def setting_value(env_file: dict[str, str], name: str, default: str) -> str:
    return os.environ.get(name) or env_file.get(name) or default


def sqlite_path_from_url(database_url: str, root: Path) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise SystemExit("cleanup script only supports sqlite DATABASE_URL")
    raw_path = unquote(database_url.removeprefix("sqlite:///"))
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def safe_storage_path(storage_root: Path, storage_key: str) -> Path:
    path = (storage_root / storage_key).resolve()
    try:
        path.relative_to(storage_root.resolve())
    except ValueError as exc:
        raise SystemExit(f"unsafe storage_key outside storage root: {storage_key}") from exc
    return path


def file_size(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    return path.stat().st_size


def remove_file(path: Path, *, delete: bool) -> int:
    size = file_size(path)
    if delete and size > 0:
        path.unlink()
    return size


def cleanup_cloud_mirrors(conn: sqlite3.Connection, storage_root: Path, *, backend: str, delete: bool) -> tuple[int, int]:
    rows = conn.execute(
        """
        select id, storage_key
        from file_assets
        where storage_backend = ?
        """,
        (backend,),
    ).fetchall()
    matched = 0
    bytes_total = 0
    for _, storage_key in rows:
        path = safe_storage_path(storage_root, storage_key)
        size = remove_file(path, delete=delete)
        if size > 0:
            matched += 1
            bytes_total += size
    return matched, bytes_total


def cleanup_download_archives(conn: sqlite3.Connection, storage_root: Path, *, delete: bool) -> tuple[int, int]:
    rows = conn.execute(
        """
        select task_downloads.id, file_assets.id, file_assets.storage_key
        from task_downloads
        join file_assets on file_assets.id = task_downloads.asset_id
        where file_assets.purpose = 'download_archive'
          and file_assets.storage_backend = 'local'
        """
    ).fetchall()
    matched = 0
    bytes_total = 0
    download_ids: list[str] = []
    asset_ids: list[str] = []
    for download_id, asset_id, storage_key in rows:
        path = safe_storage_path(storage_root, storage_key)
        size = remove_file(path, delete=delete)
        if size > 0:
            matched += 1
            bytes_total += size
        download_ids.append(download_id)
        asset_ids.append(asset_id)

    if delete and download_ids:
        conn.executemany("delete from task_downloads where id = ?", [(item,) for item in download_ids])
        conn.executemany("delete from file_assets where id = ?", [(item,) for item in asset_ids])
    return matched, bytes_total


def cleanup_directory(path: Path, *, delete: bool) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    bytes_total = 0
    file_count = 0
    for item in path.rglob("*"):
        if item.is_file():
            file_count += 1
            bytes_total += item.stat().st_size
    if delete:
        shutil.rmtree(path)
    return file_count, bytes_total


def human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean local files that are no longer the source of truth.")
    parser.add_argument("--delete", action="store_true", help="Actually delete files and related download archive rows.")
    parser.add_argument("--backend", default="aliyun_oss", choices=("aliyun_oss", "qiniu"))
    parser.add_argument("--skip-cloud-mirrors", action="store_true")
    parser.add_argument("--include-download-archives", action="store_true")
    parser.add_argument("--include-cache", action="store_true")
    parser.add_argument("--include-derived", action="store_true")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="DoodleStory repository/deploy root.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    env_file = {**read_env_file(root / ".env"), **read_env_file(root / "backend" / ".env")}
    storage_root_raw = setting_value(env_file, "DOODLESTORY_STORAGE_ROOT", "./storage")
    storage_root = Path(storage_root_raw)
    if not storage_root.is_absolute():
        storage_root = root / storage_root
    storage_root = storage_root.resolve()
    database_url = setting_value(env_file, "DATABASE_URL", "sqlite:///./doodlestory.db")
    db_path = sqlite_path_from_url(database_url, root)
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")

    print(f"mode={'delete' if args.delete else 'dry-run'}")
    print(f"database={db_path}")
    print(f"storage_root={storage_root}")

    with sqlite3.connect(db_path) as conn:
        if not args.skip_cloud_mirrors:
            count, bytes_total = cleanup_cloud_mirrors(conn, storage_root, backend=args.backend, delete=args.delete)
            print(f"cloud_mirrors backend={args.backend} files={count} bytes={human_size(bytes_total)}")

        if args.include_download_archives:
            count, bytes_total = cleanup_download_archives(conn, storage_root, delete=args.delete)
            print(f"download_archives files={count} bytes={human_size(bytes_total)}")

        if args.include_cache:
            count, bytes_total = cleanup_directory(storage_root / "_cache", delete=args.delete)
            print(f"cache files={count} bytes={human_size(bytes_total)}")

        if args.include_derived:
            count, bytes_total = cleanup_directory(storage_root / "_derived", delete=args.delete)
            print(f"derived files={count} bytes={human_size(bytes_total)}")


if __name__ == "__main__":
    main()
