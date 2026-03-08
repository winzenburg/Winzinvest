#!/usr/bin/env python3
import subprocess
import sys

# Run screener on the 295 valid symbols
subprocess.run([
    sys.executable,
    '/Users/pinchy/.openclaw/workspace/trading/scripts/ams_python_screener.py'
], check=False)
