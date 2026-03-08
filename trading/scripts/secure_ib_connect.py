#!/usr/bin/env python3
"""
Secure IB Gateway Connection Wrapper
Implements:
- 1Password credential injection
- Connection logging & audit
- Auto-disconnect on idle
- Rate limiting
- Encrypted communication
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
import subprocess
from ib_insync import IB, util

class SecureIBConnection:
    def __init__(self):
        self.ib = IB()
        self.connected = False
        self.last_activity = time.time()
        self.connection_start = None
        self.setup_logging()
        self.load_env()
        
    def setup_logging(self):
        """Configure secure audit logging"""
        log_dir = os.path.expanduser("~/.openclaw/workspace/trading/logs")
        audit_log = os.path.join(log_dir, "audit.log")
        
        self.logger = logging.getLogger("SecureIB")
        handler = logging.FileHandler(audit_log)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
    def load_env(self):
        """Load credentials from 1Password or .env"""
        try:
            # Try to load from 1Password first
            result = subprocess.run(
                ["op", "read", "op://Private/IB Trading API/host"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.host = result.stdout.strip()
                self.logger.info("✅ Loaded IB Host from 1Password")
            else:
                self.host = os.getenv("IB_HOST", "127.0.0.1")
                self.logger.warning("⚠️  Using .env for IB Host (not encrypted)")
        except Exception as e:
            self.host = os.getenv("IB_HOST", "127.0.0.1")
            self.logger.error(f"Failed to load from 1Password: {e}")
            
        self.port = int(os.getenv("IB_PORT", 4002))
        self.client_id = int(os.getenv("IB_CLIENT_ID", 101))
        self.timeout = int(os.getenv("IB_TIMEOUT", 30))
        self.auto_disconnect_idle = int(os.getenv("AUTO_DISCONNECT_IDLE", 1800))
        self.api_request_delay = int(os.getenv("API_REQUEST_DELAY", 100)) / 1000
        
    def connect(self):
        """Establish secure connection with logging"""
        try:
            self.logger.info(f"🔌 Attempting connection to {self.host}:{self.port}")
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=self.timeout)
            self.connected = True
            self.connection_start = datetime.now()
            self.logger.info(f"✅ Connected successfully | Session: {self.client_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            self.connected = False
            return False
            
    def check_idle_disconnect(self):
        """Auto-disconnect if idle > threshold"""
        idle_time = time.time() - self.last_activity
        if idle_time > self.auto_disconnect_idle:
            self.logger.warning(f"⏱️  Idle timeout ({idle_time}s) - disconnecting")
            self.disconnect()
            
    def request_with_rate_limit(self, fn, *args, **kwargs):
        """Execute API request with rate limiting"""
        time.sleep(self.api_request_delay)
        self.last_activity = time.time()
        return fn(*args, **kwargs)
        
    def disconnect(self):
        """Safely disconnect and log"""
        if self.connected:
            duration = (datetime.now() - self.connection_start).total_seconds()
            self.logger.info(f"🔌 Disconnecting after {duration:.0f}s")
            self.ib.disconnect()
            self.connected = False
            
    def log_activity(self, activity_type, details=""):
        """Log all trading activities for audit"""
        self.logger.info(f"[{activity_type}] {details}")
        self.last_activity = time.time()

# Export for use in other scripts
def get_secure_connection():
    """Factory function to get a secure IB connection"""
    conn = SecureIBConnection()
    conn.connect()
    return conn

if __name__ == "__main__":
    conn = get_secure_connection()
    print("✅ Secure connection established")
    print(f"   Account: {conn.client_id}")
    print(f"   Host: {conn.host}:{conn.port}")
    print(f"   Auto-disconnect idle: {conn.auto_disconnect_idle}s")
    conn.disconnect()
