#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
source scripts/python-path.sh
echo "Drive MVP — install local prerequisites"
echo "Installs PostgreSQL 18, Python app dependencies, the reviewed Figma icons and Roboto font."
echo "Application files stay on this Mac. No hosting account or paid service is created."
if ! command -v brew >/dev/null; then
  echo "Homebrew was not found. Install PostgreSQL from https://www.postgresql.org/download/macosx/"
  read -r -p "Press Return to close. "
  exit 1
fi
if [[ ! -x "$(brew --prefix)/opt/postgresql@18/bin/pg_ctl" ]]; then
  brew install postgresql@18
fi
if ! command -v node >/dev/null; then
  brew install node
fi
if ! drive_find_python; then
  brew install python@3.14
  drive_find_python
fi
if [[ ! -x .venv/bin/python ]]; then
  "$DRIVE_PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install -r backend/requirements.txt
mkdir -p frontend/public/assets
curl --fail --location --retry 2 'https://www.figma.com/api/mcp/asset/886d22d9-9fdc-4b88-8151-4adeafe1e07d.svg' -o frontend/public/assets/upload.svg
curl --fail --location --retry 2 'https://www.figma.com/api/mcp/asset/592c8d70-486a-49ce-b96d-7c8d2460205b.svg' -o frontend/public/assets/add.svg
curl --fail --location --retry 2 'https://www.figma.com/api/mcp/asset/a3be2001-913b-4dd5-851d-30efd27f87a7.svg' -o frontend/public/assets/attach.svg
curl --fail --location --retry 2 'https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto%5Bwdth%2Cwght%5D.ttf' -o frontend/public/assets/roboto.ttf
curl --fail --location --retry 2 'https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/OFL.txt' -o frontend/public/assets/Roboto-LICENSE.txt
echo "Local tools are ready."
if [[ "${1:-}" != "--continue" ]]; then
  echo "Open Set Up Drive.command to run the verification gates and launch."
  read -r -p "Press Return to close. "
fi
