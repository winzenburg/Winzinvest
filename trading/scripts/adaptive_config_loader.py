"""
Shared loader for adaptive_config.json.

Other modules call load_adaptive_config() at import/startup time to pick up
the latest self-learning parameter overrides. If the file is missing or
malformed, all helpers return safe defaults.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from paths import WORKSPACE, TRADING_DIR
ADAPTIVE_CONFIG_PATH = TRADING_DIR / "adaptive_config.json"

_cache: Optional[Dict[str, Any]] = None


def load_adaptive_config(
    trading_dir: Optional[Path] = None,
    force_reload: bool = False,
) -> Dict[str, Any]:
    """Load adaptive_config.json and return the params dict.

    Returns an empty dict (safe fallback) if the file is missing or invalid.
    Results are cached after the first successful load; pass force_reload=True
    to re-read from disk.
    """
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    path = (trading_dir or TRADING_DIR) / "adaptive_config.json"
    if not path.exists():
        _cache = {}
        return _cache
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict) and isinstance(data.get("params"), dict):
            _cache = data["params"]
        else:
            _cache = {}
    except (OSError, ValueError, TypeError) as e:
        logger.debug("Could not load adaptive config: %s", e)
        _cache = {}
    return _cache


def get_adaptive_float(key: str, default: float) -> float:
    """Return a float from the adaptive config, or default."""
    cfg = load_adaptive_config()
    v = cfg.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def get_adaptive_dict(key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a dict from the adaptive config, or default."""
    cfg = load_adaptive_config()
    v = cfg.get(key)
    if isinstance(v, dict):
        return v
    return default or {}
