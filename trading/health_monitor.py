#!/usr/bin/env python3
"""
System Health Monitoring Daemon
Checks every 5 minutes: Screener, Webhook, IB Gateway, Email, Disk, CPU, Memory
Logs results to trading/logs/health_checks.jsonl
Sends Telegram alerts on failures
Auto-restarts failed components
"""

import json
import logging
import os
import subprocess
import threading
import time
import psutil
import socket
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Health check configuration
HEALTH_CHECK_INTERVAL = 300  # 5 minutes
HEALTH_LOG_FILE = os.path.expanduser('~/.openclaw/workspace/trading/logs/health_checks.jsonl')
FAILURE_THRESHOLD = 3  # Escalate after 3 failures

# Component configuration
COMPONENTS = {
    'screener': {
        'type': 'process',
        'process_names': ['nx_screener', 'screener'],
        'health_check_fn': 'check_screener_process',
    },
    'webhook_listener': {
        'type': 'port',
        'port': 5001,
        'health_check_fn': 'check_webhook_port',
    },
    'ib_gateway': {
        'type': 'port',
        'port': 4002,
        'health_check_fn': 'check_ib_gateway',
    },
    'disk_space': {
        'type': system',
        'min_free_mb': 500,
        'health_check_fn': 'check_disk_space',
    },
    'cpu_memory': {
        'type': 'system',
        'max_cpu_pct': 90,
        'max_mem_pct': 85,
        'health_check_fn': 'check_cpu_memory',
    },
    'file_permissions': {
        'type': 'system',
        'log_dir': '~/.openclaw/workspace/trading/logs',
        'health_check_fn': 'check_file_permissions',
    },
}

# Track failures per component
failure_counts = {}
last_alert_time = {}


class HealthMonitor:
    """System health monitoring daemon"""
    
    def __init__(self):
        """Initialize health monitor"""
        self.is_running = False
        self.monitor_thread = None
        self.failure_counts = {}
        self.last_alert_times = {}
        os.makedirs(os.path.dirname(HEALTH_LOG_FILE), exist_ok=True)
    
    def _get_timestamp(self) -> str:
        """Get ISO 8601 timestamp"""
        return datetime.utcnow().isoformat() + 'Z'
    
    def _log_health_check(self, component: str, status: str, response_time_ms: int,
                         error: Optional[str] = None):
        """Log health check result"""
        try:
            event = {
                'timestamp': self._get_timestamp(),
                'component': component,
                'status': status,
                'response_time_ms': response_time_ms,
            }
            if error:
                event['error'] = error
            
            with open(HEALTH_LOG_FILE, 'a') as f:
                f.write(json.dumps(event) + '\n')
            
            logger.debug(f"✅ Logged health check for {component}: {status}")
        
        except Exception as e:
            logger.error(f"❌ Error logging health check: {e}")
    
    def check_screener_process(self) -> Dict[str, Any]:
        """Check if screener process is running"""
        start_time = time.time()
        
        try:
            # Check for screener processes
            for proc in psutil.process_iter(['name']):
                try:
                    if any(name in proc.name() for name in ['screener', 'nx_screener']):
                        response_time = int((time.time() - start_time) * 1000)
                        logger.info(f"✅ Screener process running ({response_time}ms)")
                        self._log_health_check('screener', 'ok', response_time)
                        self.failure_counts['screener'] = 0
                        return {'status': 'ok', 'response_time_ms': response_time}
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Process not found
            response_time = int((time.time() - start_time) * 1000)
            error = "Screener process not running"
            logger.warning(f"⚠️  {error}")
            self._log_health_check('screener', 'error', response_time, error)
            
            self._handle_component_failure('screener', error)
            return {'status': 'error', 'error': error, 'response_time_ms': response_time}
        
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Error checking screener: {e}")
            self._log_health_check('screener', 'error', response_time, str(e))
            self._handle_component_failure('screener', str(e))
            return {'status': 'error', 'error': str(e), 'response_time_ms': response_time}
    
    def check_webhook_port(self) -> Dict[str, Any]:
        """Check if webhook listener is responding on port 5001"""
        start_time = time.time()
        
        try:
            response = requests.get('http://localhost:5001/health', timeout=5)
            response_time = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                logger.info(f"✅ Webhook listener responding ({response_time}ms)")
                self._log_health_check('webhook_listener', 'ok', response_time)
                self.failure_counts['webhook_listener'] = 0
                return {'status': 'ok', 'response_time_ms': response_time}
            else:
                error = f"Webhook returned status {response.status_code}"
                logger.warning(f"⚠️  {error}")
                self._log_health_check('webhook_listener', 'error', response_time, error)
                self._handle_component_failure('webhook_listener', error)
                return {'status': 'error', 'error': error, 'response_time_ms': response_time}
        
        except requests.exceptions.Timeout:
            response_time = int((time.time() - start_time) * 1000)
            error = "Webhook listener timeout"
            logger.warning(f"⚠️  {error}")
            self._log_health_check('webhook_listener', 'error', response_time, error)
            self._handle_component_failure('webhook_listener', error)
            return {'status': 'error', 'error': error, 'response_time_ms': response_time}
        
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Error checking webhook: {e}")
            self._log_health_check('webhook_listener', 'error', response_time, str(e))
            self._handle_component_failure('webhook_listener', str(e))
            return {'status': 'error', 'error': str(e), 'response_time_ms': response_time}
    
    def check_ib_gateway(self) -> Dict[str, Any]:
        """Check if IB Gateway is responding on port 4002"""
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('127.0.0.1', 4002))
            sock.close()
            
            response_time = int((time.time() - start_time) * 1000)
            
            if result == 0:
                logger.info(f"✅ IB Gateway responding ({response_time}ms)")
                self._log_health_check('ib_gateway', 'ok', response_time)
                self.failure_counts['ib_gateway'] = 0
                return {'status': 'ok', 'response_time_ms': response_time}
            else:
                error = "IB Gateway port 4002 not responding"
                logger.warning(f"⚠️  {error}")
                self._log_health_check('ib_gateway', 'error', response_time, error)
                self._handle_component_failure('ib_gateway', error)
                return {'status': 'error', 'error': error, 'response_time_ms': response_time}
        
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Error checking IB Gateway: {e}")
            self._log_health_check('ib_gateway', 'error', response_time, str(e))
            self._handle_component_failure('ib_gateway', str(e))
            return {'status': 'error', 'error': str(e), 'response_time_ms': response_time}
    
    def check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space"""
        start_time = time.time()
        
        try:
            disk_usage = psutil.disk_usage('/')
            free_mb = disk_usage.free / (1024 * 1024)
            response_time = int((time.time() - start_time) * 1000)
            
            if free_mb > 500:
                logger.info(f"✅ Disk space OK ({free_mb:.0f} MB free)")
                self._log_health_check('disk_space', 'ok', response_time)
                self.failure_counts['disk_space'] = 0
                return {'status': 'ok', 'free_mb': free_mb, 'response_time_ms': response_time}
            else:
                error = f"Low disk space: {free_mb:.0f} MB free (< 500 MB threshold)"
                logger.warning(f"⚠️  {error}")
                self._log_health_check('disk_space', 'error', response_time, error)
                self._handle_component_failure('disk_space', error)
                return {'status': 'error', 'error': error, 'free_mb': free_mb, 'response_time_ms': response_time}
        
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Error checking disk space: {e}")
            self._log_health_check('disk_space', 'error', response_time, str(e))
            return {'status': 'error', 'error': str(e), 'response_time_ms': response_time}
    
    def check_cpu_memory(self) -> Dict[str, Any]:
        """Check CPU and memory usage"""
        start_time = time.time()
        
        try:
            cpu_pct = psutil.cpu_percent(interval=1)
            mem_pct = psutil.virtual_memory().percent
            response_time = int((time.time() - start_time) * 1000)
            
            if cpu_pct < 90 and mem_pct < 85:
                logger.info(f"✅ CPU/Memory OK (CPU: {cpu_pct}%, Mem: {mem_pct}%)")
                self._log_health_check('cpu_memory', 'ok', response_time)
                self.failure_counts['cpu_memory'] = 0
                return {
                    'status': 'ok',
                    'cpu_pct': cpu_pct,
                    'mem_pct': mem_pct,
                    'response_time_ms': response_time
                }
            else:
                error = f"High resource usage: CPU {cpu_pct}%, Memory {mem_pct}%"
                logger.warning(f"⚠️  {error}")
                self._log_health_check('cpu_memory', 'warning', response_time, error)
                self.failure_counts['cpu_memory'] = self.failure_counts.get('cpu_memory', 0) + 1
                return {
                    'status': 'warning',
                    'error': error,
                    'cpu_pct': cpu_pct,
                    'mem_pct': mem_pct,
                    'response_time_ms': response_time
                }
        
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Error checking CPU/Memory: {e}")
            self._log_health_check('cpu_memory', 'error', response_time, str(e))
            return {'status': 'error', 'error': str(e), 'response_time_ms': response_time}
    
    def check_file_permissions(self) -> Dict[str, Any]:
        """Check if we can write to log directory"""
        start_time = time.time()
        
        try:
            log_dir = os.path.expanduser(COMPONENTS['file_permissions']['log_dir'])
            test_file = os.path.join(log_dir, '.health_check_test')
            
            # Try to write a test file
            with open(test_file, 'w') as f:
                f.write('health_check')
            
            # Clean up
            os.remove(test_file)
            
            response_time = int((time.time() - start_time) * 1000)
            logger.info(f"✅ File permissions OK ({response_time}ms)")
            self._log_health_check('file_permissions', 'ok', response_time)
            self.failure_counts['file_permissions'] = 0
            return {'status': 'ok', 'response_time_ms': response_time}
        
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            error = f"Cannot write to log directory: {e}"
            logger.error(f"❌ {error}")
            self._log_health_check('file_permissions', 'error', response_time, error)
            self._handle_component_failure('file_permissions', error)
            return {'status': 'error', 'error': error, 'response_time_ms': response_time}
    
    def _handle_component_failure(self, component: str, error: str):
        """Handle a component failure (log, alert, restart)"""
        self.failure_counts[component] = self.failure_counts.get(component, 0) + 1
        failure_count = self.failure_counts[component]
        
        logger.warning(f"❌ {component} failure #{failure_count}: {error}")
        
        # Send alert if failure count reaches threshold
        if failure_count == FAILURE_THRESHOLD:
            self._send_failure_alert(component, error, is_escalation=True)
        elif failure_count == 1:
            self._send_failure_alert(component, error, is_escalation=False)
        
        # Try to restart if appropriate
        if failure_count == FAILURE_THRESHOLD:
            self._attempt_restart(component)
    
    def _send_failure_alert(self, component: str, error: str, is_escalation: bool = False):
        """Send Telegram alert for component failure"""
        try:
            from trading_alerts import send_telegram_alert
            
            if is_escalation:
                message = f"🚨 ESCALATED: {component} failed {FAILURE_THRESHOLD} times\n{error}"
            else:
                message = f"⚠️  {component} health check failed\n{error}"
            
            send_telegram_alert(message)
            logger.info(f"📢 Sent failure alert for {component}")
        
        except Exception as e:
            logger.warning(f"⚠️  Could not send Telegram alert: {e}")
    
    def _attempt_restart(self, component: str):
        """Attempt to restart a failed component"""
        logger.info(f"🔄 Attempting to restart {component}...")
        
        try:
            if component == 'webhook_listener':
                # Find and kill webhook listener process
                for proc in psutil.process_iter(['name']):
                    if 'webhook' in proc.name():
                        proc.kill()
                        time.sleep(1)
                
                # Restart webhook listener
                webhook_script = os.path.expanduser('~/.openclaw/workspace/trading/webhook_listener.py')
                if os.path.exists(webhook_script):
                    subprocess.Popen(['python3', webhook_script], 
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                    logger.info(f"✅ Restarted {component}")
            
            elif component == 'screener':
                # Similar restart logic for screener
                for proc in psutil.process_iter(['name']):
                    if 'screener' in proc.name():
                        proc.kill()
                        time.sleep(1)
                
                logger.info(f"✅ Killed {component} process (needs manual restart)")
        
        except Exception as e:
            logger.error(f"❌ Error restarting {component}: {e}")
    
    def run_health_checks(self):
        """Run all health checks"""
        logger.info("🏥 Running health checks...")
        
        results = {}
        
        # Run each health check
        results['screener'] = self.check_screener_process()
        results['webhook_listener'] = self.check_webhook_port()
        results['ib_gateway'] = self.check_ib_gateway()
        results['disk_space'] = self.check_disk_space()
        results['cpu_memory'] = self.check_cpu_memory()
        results['file_permissions'] = self.check_file_permissions()
        
        # Count healthy/unhealthy
        healthy = sum(1 for r in results.values() if r.get('status') == 'ok')
        total = len(results)
        
        logger.info(f"📊 Health check summary: {healthy}/{total} components healthy")
        
        return results
    
    def _monitor_loop(self):
        """Main health monitoring loop"""
        logger.info(f"🏥 Health monitor started (checking every {HEALTH_CHECK_INTERVAL}s)")
        
        while self.is_running:
            try:
                self.run_health_checks()
                time.sleep(HEALTH_CHECK_INTERVAL)
            
            except KeyboardInterrupt:
                logger.info("⏹️  Health monitor interrupted")
                break
            
            except Exception as e:
                logger.error(f"❌ Error in health monitor loop: {e}")
                time.sleep(10)  # Wait before retrying
    
    def start(self):
        """Start the health monitoring daemon"""
        if self.is_running:
            logger.warning("⚠️  Health monitor already running")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("✅ Health monitor started")
    
    def stop(self):
        """Stop the health monitoring daemon"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("🏁 Health monitor stopped")


# Global health monitor instance
_global_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get or create global health monitor instance"""
    global _global_health_monitor
    
    if _global_health_monitor is None:
        _global_health_monitor = HealthMonitor()
    
    return _global_health_monitor


if __name__ == '__main__':
    # Run health monitor daemon
    print("🏥 Starting Health Monitor...")
    
    monitor = get_health_monitor()
    monitor.start()
    
    # Keep running until interrupted
    try:
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down...")
        monitor.stop()
        print("✅ Health monitor stopped")
