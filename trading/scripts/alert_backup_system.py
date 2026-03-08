#!/usr/bin/env python3
"""
Backup Alert System
Primary: Telegram
Secondary: Email (Resend API)
Tertiary: SMS (Twilio)

If Telegram fails, automatically fallback to email + SMS
"""

import os
import json
import requests
from datetime import datetime
from enum import Enum

class AlertLevel(Enum):
    CRITICAL = "🚨 CRITICAL"
    HIGH = "⚠️ HIGH"
    MEDIUM = "📢 MEDIUM"
    INFO = "ℹ️ INFO"

class BackupAlertSystem:
    def __init__(self):
        # Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Email (Resend)
        self.resend_api_key = os.getenv('RESEND_API_KEY')
        self.email_to = os.getenv('TO_EMAIL', 'ryanwinzenburg@gmail.com')
        self.email_from = os.getenv('FROM_EMAIL', 'onboarding@resend.dev')
        
        # SMS (Twilio) - TODO: Set up when needed
        self.sms_enabled = False
        self.sms_phone = '303-359-3744'  # Your phone
    
    def send_telegram(self, message, alert_level=AlertLevel.INFO):
        """Send via Telegram (PRIMARY)"""
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Telegram alert sent ({alert_level.value})")
                return True
            else:
                print(f"❌ Telegram failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Telegram error: {e}")
            return False
    
    def send_email(self, subject, html_content, alert_level=AlertLevel.INFO):
        """Send via Email (SECONDARY)"""
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.email_from,
                    "to": self.email_to,
                    "subject": f"{alert_level.value} - {subject}",
                    "html": html_content,
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Email alert sent ({alert_level.value})")
                return True
            else:
                print(f"❌ Email failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Email error: {e}")
            return False
    
    def send_sms(self, message):
        """Send via SMS (TERTIARY) - Requires Twilio setup"""
        # TODO: Implement Twilio SMS
        # For now, just log that SMS would be sent
        print(f"📱 SMS would be sent to {self.sms_phone}: {message[:100]}")
        return False
    
    def send_alert(self, message, alert_level=AlertLevel.INFO, force_email=False, force_sms=False):
        """
        Smart alert routing:
        1. Always try Telegram first
        2. If Telegram fails AND level is CRITICAL: Email + SMS
        3. If force_email=True: Send email regardless
        """
        
        timestamp = datetime.now().strftime("%I:%M %p MT")
        full_message = f"{alert_level.value} [{timestamp}]\n\n{message}"
        
        # Try Telegram first
        telegram_success = self.send_telegram(full_message, alert_level)
        
        # If Telegram failed and CRITICAL, or forced email, send email
        if (not telegram_success and alert_level == AlertLevel.CRITICAL) or force_email:
            print("⚠️  Telegram failed, sending email backup...")
            
            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="background: #fff3cd; padding: 20px; border-left: 4px solid #ffc107;">
                  <h2 style="color: #856404; margin-top: 0;">
                    {alert_level.value}
                  </h2>
                  <p><strong>Time:</strong> {timestamp}</p>
                  <hr style="border: none; border-top: 1px solid #ddd;">
                  <p style="white-space: pre-wrap;">{message}</p>
                  <hr style="border: none; border-top: 1px solid #ddd;">
                  <p style="color: #666; font-size: 12px;">
                    <strong>Why did you get this email?</strong><br>
                    Telegram alert failed. This is your backup notification.
                  </p>
                </div>
              </body>
            </html>
            """
            
            email_subject = alert_level.value.replace("🚨 ", "").replace("⚠️ ", "").replace("📢 ", "").replace("ℹ️ ", "")
            self.send_email(email_subject, html_content, alert_level)
            
            # If both Telegram AND Email failed for CRITICAL, try SMS
            if alert_level == AlertLevel.CRITICAL or force_sms:
                print("⚠️  Email likely failed too, attempting SMS...")
                sms_message = f"{alert_level.value} - {message[:100]}"
                self.send_sms(sms_message)
        
        return telegram_success
    
    def test_all_channels(self):
        """Test all alert channels"""
        print("\n📡 Testing Alert Channels")
        print("=" * 50)
        
        test_message = "This is a test alert from OpenClaw Trading System"
        
        # Test Telegram
        print("\n1. Testing Telegram...")
        tg_result = self.send_telegram(test_message, AlertLevel.INFO)
        
        # Test Email
        print("\n2. Testing Email...")
        email_html = f"<p>{test_message}</p>"
        email_result = self.send_email("Trading System Test", email_html, AlertLevel.INFO)
        
        # Test SMS
        print("\n3. Testing SMS...")
        sms_result = self.send_sms(test_message)
        
        print("\n" + "=" * 50)
        print("Channel Test Results:")
        print(f"  Telegram: {'✅ PASS' if tg_result else '❌ FAIL'}")
        print(f"  Email: {'✅ PASS' if email_result else '❌ FAIL'}")
        print(f"  SMS: {'ℹ️  Not configured (TODO)'}")

if __name__ == "__main__":
    alert_system = BackupAlertSystem()
    
    # Test all channels
    alert_system.test_all_channels()
    
    # Example: Send a CRITICAL alert
    print("\n\n📤 Example: Sending CRITICAL Alert")
    print("=" * 50)
    
    example_message = """
    Trump announces 25% tariffs on China starting Monday.
    
    Impact: CRITICAL
    Sectors affected: Technology, Manufacturing, Consumer
    
    Recommended actions:
    - Reduce Tech exposure by 20%
    - Increase Energy/Commodities exposure
    - Monitor earnings guide changes
    - Stand by for market reaction
    """
    
    alert_system.send_alert(example_message, AlertLevel.CRITICAL, force_email=True)
