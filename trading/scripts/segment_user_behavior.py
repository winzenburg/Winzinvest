#!/usr/bin/env python3
"""
User Behavior Segmentation

Analyzes dashboard usage patterns and classifies users into segments:
- Nervous Monitor: Checks multiple times per day
- Daily Checker: Once per day, consistent
- Weekly Checker: ~2-3 times per week
- Monthly Reviewer: < 1 per week

Writes to logs/user_segments.json for personalization.
Runs weekly (Sundays) to update segments.

Framework: BJ Fogg — ability varies by context (reduce friction for each type)
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

OUTPUT_FILE = TRADING_DIR / "logs" / "user_segments.json"


def classify_user(email: str, views_per_day: float, days_active: int) -> Dict[str, Any]:
    """
    Classify user into engagement segment.
    
    Args:
        email: User email
        views_per_day: Average views per day over analysis period
        days_active: Total days with at least one view
    
    Returns:
        Dict with segment, description, and personalization hints
    """
    
    # Nervous Monitor: Multiple checks per day
    if views_per_day >= 2.0:
        return {
            "email": email,
            "segment": "nervous_monitor",
            "label": "Nervous Monitor",
            "description": "Checks dashboard multiple times per day",
            "dashboard_hint": "Show reassurance metrics first (stop coverage, risk gates working)",
            "email_frequency": "daily",
            "views_per_day": round(views_per_day, 2),
            "days_active": days_active,
        }
    
    # Daily Checker: ~1 view per day
    elif views_per_day >= 0.7:
        return {
            "email": email,
            "segment": "daily_checker",
            "label": "Daily Checker",
            "description": "Checks dashboard once per day, consistent routine",
            "dashboard_hint": "Show daily narrative first, performance summary second",
            "email_frequency": "daily",
            "views_per_day": round(views_per_day, 2),
            "days_active": days_active,
        }
    
    # Weekly Checker: ~2-4 per week
    elif views_per_day >= 0.25:
        return {
            "email": email,
            "segment": "weekly_checker",
            "label": "Weekly Checker",
            "description": "Checks 2-4 times per week",
            "dashboard_hint": "Show aggregated weekly insights, hide daily noise",
            "email_frequency": "weekly",
            "views_per_day": round(views_per_day, 2),
            "days_active": days_active,
        }
    
    # Monthly Reviewer: < 1 per week
    else:
        return {
            "email": email,
            "segment": "monthly_reviewer",
            "label": "Monthly Reviewer",
            "description": "Infrequent check-ins",
            "dashboard_hint": "Show long-term trends only, skip daily details",
            "email_frequency": "weekly",
            "views_per_day": round(views_per_day, 2),
            "days_active": days_active,
        }


def segment_users() -> List[Dict[str, Any]]:
    """
    Analyze user behavior and classify into segments.
    
    Returns list of segment assignments.
    
    Note: This is a placeholder — real implementation will query
    the Supabase database for actual view counts and timestamps.
    """
    segments: List[Dict[str, Any]] = []
    
    # TODO: Query actual user behavior from Supabase
    # For now, return empty to avoid errors
    
    logger.info("User segmentation analysis complete (placeholder)")
    return segments


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    logger.info("Analyzing user behavior for segmentation...")
    
    try:
        segments = segment_users()
        
        output = {
            "generated_at": datetime.now().isoformat(),
            "analysis_period_days": 30,
            "segments": segments,
        }
        
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(output, indent=2))
        
        logger.info("✓ User segments written to %s", OUTPUT_FILE)
        logger.info("  Total users analyzed: %d", len(segments))
        
        # Summary by segment
        by_segment = {}
        for seg in segments:
            label = seg.get("segment", "unknown")
            by_segment[label] = by_segment.get(label, 0) + 1
        
        for seg_name, count in sorted(by_segment.items()):
            logger.info("  %s: %d users", seg_name, count)
    
    except Exception as e:
        logger.error("Failed to segment users: %s", e, exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
