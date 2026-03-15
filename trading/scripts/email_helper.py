#!/usr/bin/env python3
"""
Universal Email Helper Module
Handles all email delivery operations with robust .env loading and error handling.

Usage:
  from email_helper import load_email_config, send_email, validate_email_config, test_email_delivery
  
  config = load_email_config()
  if config:
    send_email("Subject", "Body", config['to_email'], config)
"""

import os
import sys
import json
import requests
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_env_file(env_path: str) -> Dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars = {}
    env_file = Path(env_path).expanduser()
    
    if not env_file.exists():
        return env_vars
    
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    env_vars[key] = value
        
        return env_vars
    except Exception as e:
        logger.warning(f"Error reading {env_file}: {e}")
        return env_vars


def load_email_config() -> Optional[Dict[str, str]]:
    """
    Load email configuration from .env files with fallback to system environment.
    
    Priority:
    1. trading/.env (relative to workspace)
    2. System environment variables
    
    Returns:
        Dict with keys: resend_api_key, from_email, to_email, workspace_dir
        Returns None if critical configuration is missing
    """
    config = {}
    
    # Get workspace directory
    workspace_dir = os.getenv('WORKSPACE_DIR') or str(Path(__file__).resolve().parent.parent.parent)
    config['workspace_dir'] = workspace_dir
    
    # Step 1: Load from workspace .env
    workspace_env_path = os.path.join(workspace_dir, '.env')
    env_vars = load_env_file(workspace_env_path)
    for key, value in env_vars.items():
        config[key] = value
    
    # Log what was loaded
    for key in ['RESEND_API_KEY', 'FROM_EMAIL', 'TO_EMAIL']:
        if key in env_vars:
            masked_value = env_vars[key][:10] + '...' if len(env_vars[key]) > 10 else env_vars[key]
            logger.info(f"[LOAD] {key} from {workspace_env_path}")
    
    # Step 2: Load from trading .env (may override workspace .env)
    trading_env_path = os.path.join(workspace_dir, 'trading', '.env')
    trading_env_vars = load_env_file(trading_env_path)
    for key, value in trading_env_vars.items():
        config[key] = value
    
    # Log what was loaded
    for key in ['RESEND_API_KEY', 'FROM_EMAIL', 'TO_EMAIL']:
        if key in trading_env_vars:
            logger.info(f"[LOAD] {key} from {trading_env_path}")
    
    # Step 3: Fallback to system environment variables
    for key in ['RESEND_API_KEY', 'FROM_EMAIL', 'TO_EMAIL']:
        if key not in config and key in os.environ:
            config[key] = os.environ[key]
            logger.info(f"[LOAD] {key} from system environment")
    
    # Extract and normalize keys
    result = {
        'resend_api_key': config.get('RESEND_API_KEY'),
        'from_email': config.get('FROM_EMAIL', 'onboarding@resend.dev'),
        'to_email': config.get('TO_EMAIL', 'ryanwinzenburg@gmail.com'),
        'workspace_dir': workspace_dir,
    }
    
    return result


def validate_email_config(config: Optional[Dict[str, str]]) -> Tuple[bool, str]:
    """
    Validate that all required email configuration is present.
    
    Args:
        config: Configuration dict from load_email_config()
    
    Returns:
        Tuple[bool, str] - (is_valid, error_message)
    """
    if not config:
        return False, "No configuration provided"
    
    required_keys = ['resend_api_key', 'from_email', 'to_email']
    missing = [k for k in required_keys if not config.get(k)]
    
    if missing:
        return False, f"Missing configuration: {', '.join(missing)}"
    
    # Validate API key format (Resend keys start with 're_')
    api_key = config.get('resend_api_key', '')
    if not api_key.startswith('re_'):
        return False, "Invalid RESEND_API_KEY format (should start with 're_')"
    
    # Validate email formats
    from_email = config.get('from_email', '')
    to_email = config.get('to_email', '')
    
    if '@' not in from_email:
        return False, f"Invalid FROM_EMAIL: {from_email}"
    
    if '@' not in to_email:
        return False, f"Invalid TO_EMAIL: {to_email}"
    
    logger.info("[VALIDATE] Email configuration is complete and valid")
    return True, ""


def send_email(subject: str, html_body: str, to_email: Optional[str] = None, 
               config: Optional[Dict[str, str]] = None) -> bool:
    """
    Send email via Resend API with proper error handling.
    
    Args:
        subject: Email subject line
        html_body: HTML email body
        to_email: Recipient email (optional, uses config if not provided)
        config: Configuration dict (loads if not provided)
    
    Returns:
        bool - True if successful, False otherwise
    """
    # Load config if not provided
    if config is None:
        config = load_email_config()
    
    # Validate configuration
    is_valid, error_msg = validate_email_config(config)
    if not is_valid:
        logger.error(f"[SEND] Configuration invalid: {error_msg}")
        return False
    
    # Use provided recipient or config default
    recipient = to_email or config.get('to_email')
    
    try:
        logger.info(f"[SEND] Sending email to {recipient} with subject: {subject[:50]}...")
        
        payload = {
            "from": config.get('from_email'),
            "to": recipient,
            "subject": subject,
            "html": html_body,
        }
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {config.get('resend_api_key')}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            email_id = result.get('id', 'UNKNOWN')
            logger.info(f"[SEND] ✓ Email sent successfully (ID: {email_id})")
            return True
        else:
            error_detail = response.text
            try:
                error_detail = response.json().get('message', response.text)
            except:
                pass
            logger.error(f"[SEND] ✗ HTTP {response.status_code}: {error_detail}")
            return False
    
    except requests.exceptions.Timeout:
        logger.error("[SEND] ✗ Request timeout (Resend API did not respond)")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("[SEND] ✗ Connection error (unable to reach Resend API)")
        return False
    except Exception as e:
        logger.error(f"[SEND] ✗ Unexpected error: {e}")
        return False


def test_email_delivery() -> bool:
    """
    Send a test email to validate configuration.
    
    Returns:
        bool - True if test succeeded
    """
    logger.info("[TEST] Starting email delivery test...")
    
    config = load_email_config()
    is_valid, error_msg = validate_email_config(config)
    
    if not is_valid:
        logger.error(f"[TEST] Configuration invalid: {error_msg}")
        return False
    
    test_subject = "🧪 OpenClaw Email System Test"
    test_html = """
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Email System Test</h2>
        <p>This is a test email from OpenClaw email system.</p>
        <p><strong>If you received this, email delivery is working correctly!</strong></p>
        <hr>
        <p style="color: #999; font-size: 12px;">
          Configuration validated at {timestamp}
        </p>
      </body>
    </html>
    """.format(timestamp=__import__('datetime').datetime.now().isoformat())
    
    success = send_email(test_subject, test_html, config=config)
    
    if success:
        logger.info("[TEST] ✓ Test email delivered successfully")
        return True
    else:
        logger.error("[TEST] ✗ Test email delivery failed")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Email helper utilities")
    parser.add_argument('--test', action='store_true', help="Send test email")
    parser.add_argument('--validate', action='store_true', help="Validate configuration only")
    args = parser.parse_args()
    
    if args.test:
        success = test_email_delivery()
        sys.exit(0 if success else 1)
    elif args.validate:
        config = load_email_config()
        is_valid, msg = validate_email_config(config)
        if is_valid:
            logger.info("✓ Configuration is valid")
            sys.exit(0)
        else:
            logger.error(f"✗ {msg}")
            sys.exit(1)
    else:
        parser.print_help()
