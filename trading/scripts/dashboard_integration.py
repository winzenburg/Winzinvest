"""
Dashboard integration for growth metrics.

Handles activation tracking, user identity mapping, and non-blocking API calls
to the Winzinvest dashboard. All calls are fire-and-forget — trading execution
never blocks on dashboard availability.

SAFETY: Every function wraps requests in try/except with timeout. If the dashboard
is down, trades still execute. Metrics are "nice to have," not "must have."
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

# User identity mapping — maps IBKR account ID to dashboard user email
ACCOUNT_MAPPING_FILE = TRADING_DIR / "config" / "account_user_map.json"

# Activation state — tracks which users have already been recorded
ACTIVATION_STATE_FILE = TRADING_DIR / "logs" / "dashboard_activation_state.json"


def get_dashboard_url() -> str:
    """Return dashboard base URL from env (production or local dev)."""
    return os.getenv("DASHBOARD_URL", "https://winzinvest.com")


def get_api_token() -> str:
    """Return internal API token for server-to-server auth."""
    return os.getenv("DASHBOARD_API_TOKEN", "")


def get_user_email(account_id: str) -> Optional[str]:
    """Map IBKR account ID to dashboard user email.
    
    Returns None if mapping file doesn't exist or account ID is not mapped.
    
    Example mapping file (trading/config/account_user_map.json):
    {
      "U1234567": "ryan@winzinvest.com",
      "DU9876543": "alice@example.com"
    }
    """
    if not ACCOUNT_MAPPING_FILE.exists():
        return None
    
    try:
        data = json.loads(ACCOUNT_MAPPING_FILE.read_text())
        return data.get(account_id)
    except (OSError, ValueError, TypeError):
        logger.warning("Failed to load account mapping from %s", ACCOUNT_MAPPING_FILE)
        return None


def has_recorded_activation(user_email: str) -> bool:
    """Check if we've already recorded activation for this user.
    
    Local state prevents spamming the API with duplicate activation calls.
    """
    if not ACTIVATION_STATE_FILE.exists():
        return False
    
    try:
        data = json.loads(ACTIVATION_STATE_FILE.read_text())
        recorded = data.get("recorded_users", [])
        return user_email in recorded
    except (OSError, ValueError, TypeError):
        return False


def mark_activation_recorded(user_email: str) -> None:
    """Mark that we've recorded activation for this user (local state)."""
    ACTIVATION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        data = {"recorded_users": []}
        if ACTIVATION_STATE_FILE.exists():
            data = json.loads(ACTIVATION_STATE_FILE.read_text())
        
        recorded = data.get("recorded_users", [])
        if user_email not in recorded:
            recorded.append(user_email)
            data["recorded_users"] = recorded
            ACTIVATION_STATE_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning("Failed to persist activation state: %s", e)


def record_user_activation(user_email: str, milestone: str = "firstAutomatedTrade") -> bool:
    """Record activation milestone to dashboard (non-blocking).
    
    Returns True if successfully recorded, False otherwise.
    
    SAFETY:
    - 5-second timeout (fail fast)
    - Logs warning on failure, does NOT raise
    - Called AFTER trade succeeds (not before)
    - Idempotent (checks local state first)
    """
    # Check local state first (avoid redundant API calls)
    if has_recorded_activation(user_email):
        logger.debug("Activation already recorded for %s (local state)", user_email)
        return True
    
    dashboard_url = get_dashboard_url()
    api_token = get_api_token()
    
    if not api_token:
        logger.warning(
            "DASHBOARD_API_TOKEN not set — cannot record activation for %s. "
            "Set DASHBOARD_API_TOKEN in trading/.env to enable growth tracking.",
            user_email,
        )
        return False
    
    try:
        import requests
        
        response = requests.post(
            f"{dashboard_url}/api/activation",
            json={"milestone": milestone},
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "X-User-Email": user_email,  # Pass email in header for server-to-server calls
            },
            timeout=5,
        )
        
        if response.ok:
            logger.info("✓ Activation milestone recorded for %s: %s", user_email, milestone)
            mark_activation_recorded(user_email)
            return True
        else:
            logger.warning(
                "Dashboard API returned %d for %s: %s (non-critical, continuing)",
                response.status_code, user_email, response.text,
            )
            return False
    
    except requests.exceptions.Timeout:
        logger.warning(
            "Dashboard API timeout for %s (non-critical, continuing trade execution)",
            user_email,
        )
        return False
    except Exception as e:
        logger.warning("Failed to record activation for %s (non-critical): %s", user_email, e)
        return False


def record_activation_batch(user_emails: list[str], milestone: str = "firstAutomatedTrade") -> int:
    """Record activation for multiple users in a single batch call.
    
    Returns number of users successfully recorded.
    
    Use this when processing multiple trades in one run to reduce API calls.
    """
    if not user_emails:
        return 0
    
    # Filter out already-recorded users
    pending = [email for email in user_emails if not has_recorded_activation(email)]
    if not pending:
        logger.debug("All users already recorded (local state)")
        return 0
    
    dashboard_url = get_dashboard_url()
    api_token = get_api_token()
    
    if not api_token:
        logger.warning("DASHBOARD_API_TOKEN not set — cannot record batch activation")
        return 0
    
    try:
        import requests
        
        response = requests.post(
            f"{dashboard_url}/api/activation/batch",
            json={"users": pending, "milestone": milestone},
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        
        if response.ok:
            logger.info("✓ Batch activation recorded: %d users", len(pending))
            for email in pending:
                mark_activation_recorded(email)
            return len(pending)
        else:
            logger.warning("Batch activation API returned %d: %s", response.status_code, response.text)
            return 0
    
    except Exception as e:
        logger.warning("Batch activation failed (non-critical): %s", e)
        return 0


def get_account_id_from_ib(ib) -> Optional[str]:
    """Extract IBKR account ID from connected IB instance.
    
    Returns the first managed account or None if unavailable.
    """
    try:
        accounts = ib.managedAccounts()
        if accounts:
            return accounts[0]
    except Exception as e:
        logger.warning("Could not fetch managed accounts: %s", e)
    return None


# ---------------------------------------------------------------------------
# Convenience wrapper for single-user execution flows
# ---------------------------------------------------------------------------


def try_record_activation_for_account(ib, source_script: str = "") -> None:
    """Attempt to record activation for the current IBKR account (convenience wrapper).
    
    Called after successful trade execution. Handles full flow:
    1. Get account ID from IB
    2. Map to user email
    3. Check if already recorded
    4. Call activation API
    
    If any step fails, logs warning and continues (non-blocking).
    
    Usage in executor scripts:
    
        from dashboard_integration import try_record_activation_for_account
        
        # After confirmed fill:
        if fill_successful:
            try_record_activation_for_account(self.ib, source_script=self.script_name)
    """
    account_id = get_account_id_from_ib(ib)
    if not account_id:
        logger.debug("No account ID available — skipping activation tracking")
        return
    
    user_email = get_user_email(account_id)
    if not user_email:
        logger.debug(
            "Account %s not mapped to user email — skipping activation tracking. "
            "Add mapping to %s to enable growth metrics.",
            account_id, ACCOUNT_MAPPING_FILE,
        )
        return
    
    if has_recorded_activation(user_email):
        return
    
    logger.info(
        "First trade for user %s (account %s) — recording activation milestone",
        user_email, account_id,
    )
    record_user_activation(user_email)


if __name__ == "__main__":
    # Quick test — verify env vars and mapping
    print(f"Dashboard URL: {get_dashboard_url()}")
    print(f"API Token set: {'Yes' if get_api_token() else 'No'}")
    
    if ACCOUNT_MAPPING_FILE.exists():
        mapping = json.loads(ACCOUNT_MAPPING_FILE.read_text())
        print(f"Account mapping loaded: {len(mapping)} accounts")
        for account_id in mapping:
            print(f"  {account_id} → {mapping[account_id]}")
    else:
        print(f"Account mapping file not found: {ACCOUNT_MAPPING_FILE}")
        print("Create it with:")
        print('  {"U1234567": "your-email@example.com"}')
