#!/usr/bin/env python3
"""
Audit Logging Configuration
Central configuration for audit system, health monitoring, and reporting
"""

import os
from datetime import datetime
from typing import Dict, Any

# =====================================================================
# AUDIT LOG CONFIGURATION
# =====================================================================

# Path to audit.jsonl
AUDIT_LOG_DIR = os.path.expanduser('~/.openclaw/workspace/trading/logs')
AUDIT_LOG_FILE = os.path.join(AUDIT_LOG_DIR, 'audit.jsonl')

# Path to health checks log
HEALTH_LOG_FILE = os.path.join(AUDIT_LOG_DIR, 'health_checks.jsonl')

# Path to reports directory
REPORTS_DIR = os.path.expanduser('~/.openclaw/workspace/trading/reports')

# Audit trail retention (days) - 0 = keep forever
AUDIT_RETENTION_DAYS = 0  # Permanent audit trail

# =====================================================================
# HEALTH MONITORING CONFIGURATION
# =====================================================================

# Health check interval (seconds)
HEALTH_CHECK_INTERVAL = 300  # 5 minutes

# Failure threshold before escalation
FAILURE_THRESHOLD = 3

# Failure threshold before auto-restart
RESTART_THRESHOLD = 2

# Health check timeout (seconds)
HEALTH_CHECK_TIMEOUT = 10

# Component health check configuration
COMPONENTS_CONFIG = {
    'screener': {
        'enabled': True,
        'timeout': 30,
        'process_names': ['nx_screener', 'screener'],
        'auto_restart': True,
        'restart_delay': 5,
    },
    'webhook_listener': {
        'enabled': True,
        'timeout': 5,
        'port': 5001,
        'health_endpoint': '/health',
        'auto_restart': True,
        'restart_delay': 5,
    },
    'ib_gateway': {
        'enabled': True,
        'timeout': 5,
        'port': 4002,
        'host': '127.0.0.1',
        'auto_restart': False,  # Manual restart required
    },
    'disk_space': {
        'enabled': True,
        'timeout': 5,
        'min_free_mb': 500,
        'alert_threshold_mb': 1000,
    },
    'cpu_memory': {
        'enabled': True,
        'timeout': 10,
        'max_cpu_percent': 90,
        'max_memory_percent': 85,
        'warning_threshold_cpu': 80,
        'warning_threshold_memory': 75,
    },
    'file_permissions': {
        'enabled': True,
        'timeout': 5,
        'log_dir': '~/.openclaw/workspace/trading/logs',
    },
}

# =====================================================================
# ALERT CONFIGURATION
# =====================================================================

# Alert destinations
ALERT_CONFIG = {
    'telegram': {
        'enabled': True,
        'send_on_failure': True,
        'send_on_restart': True,
        'send_daily_summary': True,
    },
    'email': {
        'enabled': False,
        'send_on_critical': True,
    },
    'log_file': {
        'enabled': True,
        'path': os.path.join(AUDIT_LOG_DIR, 'alerts.log'),
    },
}

# Alert escalation rules
ALERT_ESCALATION = {
    'failure_count_1': {
        'type': 'warning',
        'message': '{component} health check failed',
    },
    'failure_count_3': {
        'type': 'error',
        'message': '{component} failed {count} times - auto-restarting',
    },
    'restart_success': {
        'type': 'info',
        'message': '{component} restarted successfully at {time}',
    },
    'restart_failure': {
        'type': 'error',
        'message': '{component} restart failed: {reason}',
    },
}

# =====================================================================
# REPORTING CONFIGURATION
# =====================================================================

# Report generation schedule
REPORT_SCHEDULE = {
    'daily_summary': {
        'enabled': True,
        'time': '00:00',  # Midnight UTC
        'formats': ['json', 'text'],
    },
    'weekly_summary': {
        'enabled': True,
        'day': 'Sunday',  # Weekly on Sunday
        'time': '02:00',  # 2 AM UTC
        'formats': ['json', 'text'],
    },
}

# Report content sections
REPORT_SECTIONS = {
    'summary': True,
    'event_counts': True,
    'trading_activity': True,
    'pnl_analysis': True,
    'risk_events': True,
    'health_status': True,
    'failures': True,
}

# =====================================================================
# LOGGING CONFIGURATION
# =====================================================================

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'audit': {
            'format': '%(asctime)s - AUDIT - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'standard',
            'filename': os.path.join(AUDIT_LOG_DIR, 'audit_system.log'),
        },
        'audit_file': {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'audit',
            'filename': os.path.join(AUDIT_LOG_DIR, 'audit_events.log'),
        },
    },
    'loggers': {
        'audit_logger': {
            'level': 'INFO',
            'handlers': ['console', 'file', 'audit_file'],
        },
        'audit_query': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
        },
        'health_monitor': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
        },
        'audit_summary': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file'],
    },
}

# =====================================================================
# AUDIT EVENT TYPES
# =====================================================================

SUPPORTED_EVENT_TYPES = {
    'SCREENER_RUN': {
        'description': 'Screener completed a run',
        'required_fields': ['candidates_found', 'filters_passed'],
    },
    'ENTRY_SIGNAL': {
        'description': 'Entry signal generated',
        'required_fields': ['symbol', 'entry_price', 'quantity', 'reason'],
    },
    'STOP_PLACED': {
        'description': 'Stop-loss order placed',
        'required_fields': ['symbol', 'stop_price', 'order_id'],
    },
    'STOP_FILLED': {
        'description': 'Stop-loss order filled',
        'required_fields': ['symbol', 'fill_price'],
    },
    'POSITION_CLOSED': {
        'description': 'Position manually closed',
        'required_fields': ['symbol', 'exit_price', 'reason'],
    },
    'RISK_GATE_TRIGGERED': {
        'description': 'Risk gate blocked action',
        'required_fields': ['gate_name', 'reason', 'blocked'],
    },
    'CIRCUIT_BREAKER': {
        'description': 'VIX regime change',
        'required_fields': ['vix_level', 'regime_change', 'action'],
    },
    'EARNINGS_ALERT': {
        'description': 'Earnings event detected',
        'required_fields': ['symbol', 'earnings_date', 'action'],
    },
    'OPTIONS_DECISION': {
        'description': 'Options trading decision',
        'required_fields': ['symbol', 'strike', 'decision', 'reason'],
    },
    'HEALTH_CHECK': {
        'description': 'System component health check',
        'required_fields': ['component', 'status'],
    },
    'WEBHOOK_ALERT': {
        'description': 'Webhook signal received',
        'required_fields': ['signal_type', 'symbol'],
    },
    'GAP_PROTECTION': {
        'description': 'Gap protection triggered',
        'required_fields': ['symbol', 'action', 'gap_size'],
    },
    'CORRELATION_CHECK': {
        'description': 'Correlation limit breached',
        'required_fields': ['symbols', 'correlation'],
    },
    'LIQUIDATION': {
        'description': 'Position liquidated',
        'required_fields': ['symbol', 'reason', 'price'],
    },
    'ERROR_EVENT': {
        'description': 'Error or exception occurred',
        'required_fields': ['error_type', 'component', 'message'],
    },
}

# =====================================================================
# PERFORMANCE THRESHOLDS
# =====================================================================

PERFORMANCE_THRESHOLDS = {
    'slow_health_check': 5000,  # ms
    'slow_query': 1000,  # ms
    'high_audit_log_size': 100 * 1024 * 1024,  # 100 MB
    'audit_log_archival_threshold': 500 * 1024 * 1024,  # 500 MB
}

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def get_component_config(component_name: str) -> Dict[str, Any]:
    """Get configuration for a specific component"""
    return COMPONENTS_CONFIG.get(component_name, {})


def is_component_enabled(component_name: str) -> bool:
    """Check if a component is enabled for health monitoring"""
    config = get_component_config(component_name)
    return config.get('enabled', False)


def get_all_enabled_components() -> list:
    """Get list of all enabled components"""
    return [name for name, config in COMPONENTS_CONFIG.items() 
            if config.get('enabled', False)]


def get_report_time(report_type: str) -> str:
    """Get scheduled time for report generation"""
    config = REPORT_SCHEDULE.get(report_type, {})
    return config.get('time', '00:00')


def should_auto_restart(component_name: str) -> bool:
    """Check if component should be auto-restarted"""
    config = get_component_config(component_name)
    return config.get('auto_restart', False)


def get_health_check_timeout(component_name: str) -> int:
    """Get health check timeout for component (seconds)"""
    config = get_component_config(component_name)
    return config.get('timeout', HEALTH_CHECK_TIMEOUT)


def create_default_config() -> Dict[str, Any]:
    """Return default configuration as dictionary"""
    return {
        'audit': {
            'log_file': AUDIT_LOG_FILE,
            'health_log_file': HEALTH_LOG_FILE,
            'retention_days': AUDIT_RETENTION_DAYS,
        },
        'health_monitoring': {
            'check_interval': HEALTH_CHECK_INTERVAL,
            'failure_threshold': FAILURE_THRESHOLD,
            'components': COMPONENTS_CONFIG,
        },
        'reporting': {
            'schedule': REPORT_SCHEDULE,
            'sections': REPORT_SECTIONS,
        },
        'alerts': {
            'config': ALERT_CONFIG,
            'escalation': ALERT_ESCALATION,
        },
    }


def print_config():
    """Print current configuration"""
    print("\n" + "="*70)
    print("AUDIT SYSTEM CONFIGURATION")
    print("="*70)
    
    print("\n📁 DIRECTORIES:")
    print(f"  Audit Log Dir: {AUDIT_LOG_DIR}")
    print(f"  Reports Dir: {REPORTS_DIR}")
    
    print(f"\n⏰ HEALTH MONITORING:")
    print(f"  Check Interval: {HEALTH_CHECK_INTERVAL}s")
    print(f"  Failure Threshold: {FAILURE_THRESHOLD}")
    print(f"  Enabled Components: {get_all_enabled_components()}")
    
    print(f"\n📊 REPORTING:")
    for report_type, config in REPORT_SCHEDULE.items():
        if config.get('enabled'):
            print(f"  {report_type}: {config.get('time')}")
    
    print(f"\n🚨 ALERTS:")
    print(f"  Telegram: {ALERT_CONFIG['telegram']['enabled']}")
    print(f"  Email: {ALERT_CONFIG['email']['enabled']}")
    print(f"  Log File: {ALERT_CONFIG['log_file']['enabled']}")
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    print_config()
