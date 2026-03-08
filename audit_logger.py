#!/usr/bin/env python3
"""
Audit Logger - Logs all API requests, executions, and decisions
"""

import json
import logging
from datetime import datetime
from pathlib import Path

class AuditLogger:
    def __init__(self, log_path='~/.openclaw/workspace/trading/logs/audit/audit.log'):
        self.log_path = Path(log_path).expanduser()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger('AuditLogger')
        handler = logging.FileHandler(self.log_path)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_request(self, endpoint, method, user, status_code, response_time_ms):
        """Log API request"""
        log_entry = {
            'type': 'api_request',
            'timestamp': datetime.now().isoformat(),
            'endpoint': endpoint,
            'method': method,
            'user': user,
            'status_code': status_code,
            'response_time_ms': response_time_ms
        }
        self.logger.info(json.dumps(log_entry))
    
    def log_execution(self, execution_type, action, status, details):
        """Log trade/order execution"""
        log_entry = {
            'type': 'execution',
            'execution_type': execution_type,
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'status': status,
            'details': details
        }
        self.logger.info(json.dumps(log_entry))
    
    def log_security_event(self, event_type, severity, description):
        """Log security events"""
        log_entry = {
            'type': 'security_event',
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'description': description
        }
        self.logger.warning(json.dumps(log_entry))

if __name__ == '__main__':
    print("✅ Audit logger module created")
