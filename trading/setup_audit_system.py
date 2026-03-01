#!/usr/bin/env python3
"""
Audit System Setup & Initialization
Configures and initializes the audit logging and health monitoring system
Run this script to set up everything
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import audit modules
try:
    from audit_logger import get_audit_logger, log_event
    from audit_query import get_audit_query
    from audit_summary import AuditSummary
    from audit_config import (
        AUDIT_LOG_DIR, AUDIT_LOG_FILE, HEALTH_LOG_FILE,
        REPORTS_DIR, COMPONENTS_CONFIG
    )
except ImportError as e:
    logger.error(f"❌ Failed to import audit modules: {e}")
    sys.exit(1)


class AuditSystemSetup:
    """Setup and initialize the audit system"""
    
    def __init__(self):
        """Initialize setup"""
        self.audit_dir = AUDIT_LOG_DIR
        self.reports_dir = REPORTS_DIR
        self.setup_status = {}
    
    def print_header(self, title):
        """Print formatted header"""
        width = 70
        print("\n" + "="*width)
        print(f"  {title}")
        print("="*width)
    
    def create_directories(self):
        """Create necessary directories"""
        self.print_header("📁 Creating Directories")
        
        try:
            os.makedirs(self.audit_dir, exist_ok=True)
            logger.info(f"✅ Created/verified audit directory: {self.audit_dir}")
            
            os.makedirs(self.reports_dir, exist_ok=True)
            logger.info(f"✅ Created/verified reports directory: {self.reports_dir}")
            
            # Create subdirectories
            for subdir in ['daily', 'weekly', 'exports']:
                subdir_path = os.path.join(self.reports_dir, subdir)
                os.makedirs(subdir_path, exist_ok=True)
                logger.info(f"✅ Created {subdir} directory: {subdir_path}")
            
            self.setup_status['directories'] = 'OK'
            return True
        
        except Exception as e:
            logger.error(f"❌ Error creating directories: {e}")
            self.setup_status['directories'] = f'ERROR: {e}'
            return False
    
    def initialize_audit_log(self):
        """Initialize audit log file"""
        self.print_header("📝 Initializing Audit Log")
        
        try:
            if not os.path.exists(AUDIT_LOG_FILE):
                # Create empty file
                Path(AUDIT_LOG_FILE).touch()
                logger.info(f"✅ Created audit log: {AUDIT_LOG_FILE}")
            else:
                logger.info(f"✅ Audit log exists: {AUDIT_LOG_FILE}")
            
            # Get logger instance
            audit_logger = get_audit_logger()
            count = audit_logger.get_event_count()
            size = audit_logger.get_file_size()
            
            logger.info(f"📊 Audit log stats: {count} events, {size}")
            
            self.setup_status['audit_log'] = 'OK'
            return True
        
        except Exception as e:
            logger.error(f"❌ Error initializing audit log: {e}")
            self.setup_status['audit_log'] = f'ERROR: {e}'
            return False
    
    def initialize_health_log(self):
        """Initialize health check log"""
        self.print_header("💚 Initializing Health Log")
        
        try:
            if not os.path.exists(HEALTH_LOG_FILE):
                Path(HEALTH_LOG_FILE).touch()
                logger.info(f"✅ Created health log: {HEALTH_LOG_FILE}")
            else:
                logger.info(f"✅ Health log exists: {HEALTH_LOG_FILE}")
            
            self.setup_status['health_log'] = 'OK'
            return True
        
        except Exception as e:
            logger.error(f"❌ Error initializing health log: {e}")
            self.setup_status['health_log'] = f'ERROR: {e}'
            return False
    
    def test_audit_logging(self):
        """Test audit logging functionality"""
        self.print_header("🧪 Testing Audit Logging")
        
        try:
            # Test various event types
            test_events = [
                ('SCREENER_RUN', {
                    'candidates_found': 5,
                    'symbols': ['AAPL', 'MSFT', 'GOOGL'],
                    'filters_passed': {'price': 5, 'volume': 4}
                }),
                ('ENTRY_SIGNAL', {
                    'symbol': 'AAPL',
                    'entry_price': 150.25,
                    'quantity': 10,
                    'reason': 'test_setup'
                }),
                ('HEALTH_CHECK', {
                    'component': 'audit_system',
                    'status': 'ok',
                    'response_time_ms': 10
                }),
            ]
            
            for event_type, data in test_events:
                log_event(event_type, **data)
                logger.info(f"✅ Logged test event: {event_type}")
            
            self.setup_status['audit_logging'] = 'OK'
            return True
        
        except Exception as e:
            logger.error(f"❌ Error testing audit logging: {e}")
            self.setup_status['audit_logging'] = f'ERROR: {e}'
            return False
    
    def test_audit_queries(self):
        """Test audit query functionality"""
        self.print_header("🔍 Testing Audit Queries")
        
        try:
            query = get_audit_query()
            
            # Test various queries
            all_events = query.events
            logger.info(f"✅ Query loaded {len(all_events)} events")
            
            screener_events = query.query_by_event_type('SCREENER_RUN')
            logger.info(f"✅ Found {len(screener_events)} SCREENER_RUN events")
            
            health_summary = query.get_system_health_summary()
            logger.info(f"✅ Health summary: {health_summary['total_checks']} checks")
            
            recent_trades = query.get_recent_trades(5)
            logger.info(f"✅ Found {len(recent_trades)} recently active symbols")
            
            self.setup_status['audit_queries'] = 'OK'
            return True
        
        except Exception as e:
            logger.error(f"❌ Error testing queries: {e}")
            self.setup_status['audit_queries'] = f'ERROR: {e}'
            return False
    
    def test_reporting(self):
        """Test reporting functionality"""
        self.print_header("📊 Testing Reporting")
        
        try:
            summary = AuditSummary()
            
            # Generate daily summary
            daily = summary.daily_summary()
            logger.info(f"✅ Generated daily summary: {daily.get('total_events')} events")
            
            # Generate failure summary
            failures = summary.failure_summary(hours=24)
            logger.info(f"✅ Generated failure summary: {failures.get('total_failures')} failures")
            
            # Calculate health score
            health = summary.health_score(hours=24)
            logger.info(f"✅ Health score: {health.get('health_score')}/100")
            
            self.setup_status['reporting'] = 'OK'
            return True
        
        except Exception as e:
            logger.error(f"❌ Error testing reporting: {e}")
            self.setup_status['reporting'] = f'ERROR: {e}'
            return False
    
    def verify_file_permissions(self):
        """Verify file permissions"""
        self.print_header("🔐 Verifying File Permissions")
        
        try:
            # Test write permissions
            test_file = os.path.join(self.audit_dir, '.permission_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info(f"✅ Write permissions verified")
            
            self.setup_status['permissions'] = 'OK'
            return True
        
        except Exception as e:
            logger.error(f"❌ Permission error: {e}")
            self.setup_status['permissions'] = f'ERROR: {e}'
            return False
    
    def display_status(self):
        """Display final setup status"""
        self.print_header("✅ SETUP STATUS")
        
        all_ok = True
        for component, status in self.setup_status.items():
            symbol = "✅" if status == "OK" else "❌"
            print(f"  {symbol} {component:<30} {status}")
            if status != "OK":
                all_ok = False
        
        return all_ok
    
    def display_next_steps(self):
        """Display next steps"""
        self.print_header("📚 NEXT STEPS")
        
        print("""
1. INTEGRATE LOGGING INTO MODULES:
   - See AUDIT_INTEGRATION_GUIDE.md for detailed patches
   - Start with stop_manager.py (most critical)
   - Add audit_logger imports to key modules

2. START HEALTH MONITOR:
   python3 ~/.openclaw/workspace/trading/health_monitor.py &
   
3. VIEW AUDIT DASHBOARD:
   python3 ~/.openclaw/workspace/trading/audit_dashboard.py

4. GENERATE REPORTS:
   python3 ~/.openclaw/workspace/trading/audit_summary.py

5. QUERY AUDIT TRAIL:
   python3 -c "from audit_query import by_type; print(by_type('ENTRY_SIGNAL'))"

6. MONITOR HEALTH:
   python3 -c "from audit_summary import AuditSummary; s = AuditSummary(); print(s.health_score())"
        """)
    
    def run_setup(self):
        """Run complete setup"""
        self.print_header("🚀 AUDIT SYSTEM SETUP")
        
        print(f"\nSetting up audit system at: {self.audit_dir}")
        print(f"Reports directory: {self.reports_dir}")
        
        steps = [
            ("Creating directories", self.create_directories),
            ("Initializing audit log", self.initialize_audit_log),
            ("Initializing health log", self.initialize_health_log),
            ("Testing audit logging", self.test_audit_logging),
            ("Testing audit queries", self.test_audit_queries),
            ("Testing reporting", self.test_reporting),
            ("Verifying permissions", self.verify_file_permissions),
        ]
        
        for step_name, step_func in steps:
            try:
                if not step_func():
                    logger.warning(f"⚠️  {step_name} completed with warnings")
            except Exception as e:
                logger.error(f"❌ {step_name} failed: {e}")
        
        # Display final status
        success = self.display_status()
        
        # Display next steps
        if success:
            logger.info("\n✅ SETUP COMPLETE - All systems initialized!")
        else:
            logger.warning("\n⚠️  Setup completed with some warnings - see above")
        
        self.display_next_steps()
        
        return success


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup Audit System')
    parser.add_argument('--quick', action='store_true', help='Quick setup without tests')
    parser.add_argument('--test-only', action='store_true', help='Run tests only')
    
    args = parser.parse_args()
    
    setup = AuditSystemSetup()
    
    if args.test_only:
        setup.create_directories()
        setup.initialize_audit_log()
        setup.initialize_health_log()
        setup.test_audit_logging()
        setup.test_audit_queries()
        setup.test_reporting()
    elif args.quick:
        setup.create_directories()
        setup.initialize_audit_log()
        setup.initialize_health_log()
        setup.verify_file_permissions()
        setup.display_status()
    else:
        success = setup.run_setup()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
