#!/bin/bash
# Resume trading (deactivates kill switch)
cd "$(dirname "$0")/.."
if [ -f .pause ]; then
    rm .pause
    echo "✅ Trading RESUMED"
    echo "New trade approvals are now allowed."
else
    echo "✅ Trading was not paused (already active)"
fi
