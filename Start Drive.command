#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
source scripts/python-path.sh
if ! drive_find_python; then
  echo "Open Install Local Tools.command first to install a supported Python version."
  read -r -p "Press Return to close. "
  exit 1
fi
"$DRIVE_PYTHON" scripts/local.py launch
