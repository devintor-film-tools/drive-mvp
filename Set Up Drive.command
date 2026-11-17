#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
drive_setup_failed() {
  echo "Setup stopped at a failed check. Existing application data was not reset."
  echo "Keep this window open so the error can be reviewed."
  read -r -p "Press Return to close. "
}
trap drive_setup_failed ERR
bash 'Install Local Tools.command' --continue
npm --prefix frontend ci
.venv/bin/python scripts/verify.py
echo "Automated verification passed. Set up your private local account next."
exec .venv/bin/python scripts/local.py launch --prepared
