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
if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c "import sys; sys.path.insert(0, 'scripts'); import local, django, psycopg, waitress; local.pg_bin(); local.require_assets(local.REPO / 'frontend/public/assets')" >/dev/null 2>&1; then
  bash 'Install Local Tools.command' --continue
fi
npm --prefix frontend ci
.venv/bin/python scripts/verify.py
echo "Automated verification passed. Set up your private local account next."
exec .venv/bin/python scripts/local.py launch --prepared
