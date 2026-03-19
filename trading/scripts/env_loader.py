"""
Shared .env file loader for trading scripts.

Handles:
  - Inline comments (# after value)
  - Quoted values: KEY="value" and KEY='value'
  - Whitespace around keys and values
  - Lines that are blank or comment-only

Usage:
    from env_loader import load_env
    load_env()          # auto-discovers .env two levels up (trading/.env)
    load_env(path)      # explicit path
"""

from __future__ import annotations

import os
from pathlib import Path


def _strip_value(raw: str) -> str:
    """Strip whitespace, inline comments, and surrounding quotes from a raw .env value."""
    v = raw.strip()
    # Remove inline comment (unquoted part after #)
    if v and v[0] not in ('"', "'"):
        # Value is unquoted — strip everything after first unescaped #
        v = v.split("#", 1)[0].rstrip()
    else:
        # Value is quoted — find the closing quote, ignore rest
        quote = v[0]
        end = v.find(quote, 1)
        if end != -1:
            v = v[1:end]
        else:
            v = v[1:]  # unclosed quote — strip opening quote only
    return v


def load_env(path: Path | str | None = None) -> None:
    """
    Load key=value pairs from a .env file into os.environ (setdefault — never overwrites).

    If path is None, searches for .env in common locations relative to this file:
      1. trading/.env  (parent of scripts/)
      2. project root .env (two levels up)
    """
    candidates: list[Path]
    if path is not None:
        candidates = [Path(path)]
    else:
        here = Path(__file__).resolve().parent
        candidates = [
            here.parent / ".env",                # trading/.env
            here.parent.parent / ".env",         # project root .env
        ]

    env_path: Path | None = None
    for c in candidates:
        if c.exists():
            env_path = c
            break

    if env_path is None:
        return

    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_val = stripped.partition("=")
        key = key.strip()
        if not key or key.startswith("#"):
            continue
        value = _strip_value(raw_val)
        os.environ.setdefault(key, value)
