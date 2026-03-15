#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
from paths import SCRIPTS_DIR

subprocess.run([
    sys.executable,
    str(SCRIPTS_DIR / "ams_python_screener.py")
], check=False)
