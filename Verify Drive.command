#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ ! -x .venv/bin/python ]]; then
  echo "Open Install Local Tools.command first."
  read -r -p "Press Return to close. "
  exit 1
fi
echo "Checking the real first-upload workflow in disposable local databases."
echo "Your application account and uploaded files will not be used."
if .venv/bin/python scripts/verify.py; then
  echo "The automated first-upload gates passed."
else
  echo "A gate failed. The printed evidence folder contains the report and log."
fi
read -r -p "Press Return to close. "
