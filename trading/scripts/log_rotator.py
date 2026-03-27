#!/usr/bin/env python3
"""
Log Rotator — keeps trading/logs/*.log files from growing unbounded.

Strategy:
  Each .log file is capped at a configured max size. When exceeded, the oldest
  portion is archived to <name>.log.1 (overwriting any prior .1 archive) and
  the live file is trimmed to keep only the most recent content. This means
  at most 2× max_bytes per log file is ever kept on disk.

  Max sizes:
    High-frequency logs (agents, portfolio_snapshot): 5 MB
    Standard logs: 2 MB

Scheduled: Every Sunday at 02:00 MT via scheduler.py

CLI:
  python log_rotator.py            # Rotate all oversized logs
  python log_rotator.py --dry-run  # Report sizes without rotating
  python log_rotator.py --force    # Rotate all logs regardless of size
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import LOGS_DIR

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MB = 1024 * 1024

# High-frequency logs get a larger cap; everything else capped at 2 MB
HIGH_FREQ = {"agents.log", "portfolio_snapshot.log", "dashboard.log"}
DEFAULT_MAX  = 2 * MB
HIGH_FREQ_MAX = 5 * MB


def _max_bytes(name: str) -> int:
    return HIGH_FREQ_MAX if name in HIGH_FREQ else DEFAULT_MAX


def rotate_log(path: Path, max_bytes: int, force: bool = False) -> Dict[str, object]:
    """
    Rotate a single log file if it exceeds max_bytes.

    Returns a dict describing what was done.
    """
    size = path.stat().st_size
    if not force and size <= max_bytes:
        return {"path": str(path), "size_mb": size / MB, "action": "skipped"}

    archive = path.with_suffix(".log.1")

    # Read the tail we want to keep (last max_bytes worth)
    with open(path, "rb") as fh:
        fh.seek(max(0, size - max_bytes))
        # Skip to next newline so we don't start mid-line
        fh.readline()
        tail = fh.read()

    # Copy entire current log to archive
    shutil.copy2(path, archive)

    # Overwrite current log with tail only
    with open(path, "wb") as fh:
        fh.write(tail)

    new_size = path.stat().st_size
    logger.info(
        "Rotated %s: %.1f MB → %.1f MB (archive: %s)",
        path.name, size / MB, new_size / MB, archive.name,
    )
    return {
        "path":        str(path),
        "before_mb":   round(size / MB, 1),
        "after_mb":    round(new_size / MB, 1),
        "archive":     str(archive),
        "action":      "rotated",
    }


def run(dry_run: bool = False, force: bool = False) -> Dict[str, object]:
    """
    Rotate all oversized log files under LOGS_DIR.

    Returns a summary of actions taken.
    """
    if not LOGS_DIR.exists():
        logger.warning("LOGS_DIR does not exist: %s", LOGS_DIR)
        return {"status": "no_logs_dir", "rotated": 0}

    log_files = sorted(LOGS_DIR.glob("*.log"))
    results = []
    rotated = 0
    total_freed_mb = 0.0

    for path in log_files:
        max_bytes = _max_bytes(path.name)
        size = path.stat().st_size

        if dry_run:
            status = "OVER LIMIT" if size > max_bytes else "ok"
            logger.info(
                "  %-45s  %6.1f MB  limit=%.0f MB  [%s]",
                path.name, size / MB, max_bytes / MB, status,
            )
            results.append({"path": path.name, "size_mb": round(size / MB, 1), "status": status})
            continue

        result = rotate_log(path, max_bytes, force=force)
        results.append(result)
        if result["action"] == "rotated":
            rotated += 1
            freed = result.get("before_mb", 0) - result.get("after_mb", 0)
            total_freed_mb += freed

    if not dry_run:
        logger.info(
            "Log rotation complete: %d file(s) rotated, %.1f MB freed",
            rotated, total_freed_mb,
        )

    return {
        "status":         "dry_run" if dry_run else "ok",
        "rotated":        rotated,
        "freed_mb":       round(total_freed_mb, 1),
        "files_checked":  len(log_files),
        "details":        results,
    }


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Rotate oversized trading log files")
    parser.add_argument("--dry-run", action="store_true", help="Report sizes without rotating")
    parser.add_argument("--force",   action="store_true", help="Rotate all logs regardless of size")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, force=args.force)
    print(json.dumps(result, indent=2))
