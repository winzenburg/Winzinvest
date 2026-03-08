#!/usr/bin/env python3
"""
Send email via Resend API
Usage: python3 send_email.py --to email@example.com --subject "Subject" --body "Body text"
"""

import os
import sys
import argparse
import requests
from pathlib import Path

# Load from .env if available
env_file = Path.home() / '.openclaw' / 'workspace' / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key, value)

RESEND_API_KEY = os.getenv('RESEND_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'onboarding@resend.dev')  # Default Resend test email


def send_email(to: str, subject: str, body: str, html: bool = False):
    """Send email via Resend API."""
    
    if not RESEND_API_KEY:
        print("❌ RESEND_API_KEY not set")
        print("Add to ~/.openclaw/workspace/.env:")
        print("RESEND_API_KEY=re_xxxx")
        return False
    
    url = "https://api.resend.com/emails"
    
    payload = {
        "from": FROM_EMAIL,
        "to": [to],
        "subject": subject,
    }
    
    if html:
        payload["html"] = body
    else:
        payload["text"] = body
    
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Email sent successfully!")
        print(f"   ID: {result.get('id')}")
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send email via Resend")
    parser.add_argument('--to', required=True, help="Recipient email")
    parser.add_argument('--subject', required=True, help="Email subject")
    parser.add_argument('--body', required=True, help="Email body")
    parser.add_argument('--html', action='store_true', help="Send as HTML")
    
    args = parser.parse_args()
    
    success = send_email(args.to, args.subject, args.body, args.html)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
