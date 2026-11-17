# Sourced by the macOS launchers. Django 5.2 is verified for Python through 3.14.
drive_find_python() {
  local candidate
  for candidate in python3.14 /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 /opt/homebrew/opt/python@3.14/bin/python3.14 /usr/local/opt/python@3.14/bin/python3.14 python3.13 python3.12; do
    if command -v "$candidate" >/dev/null 2>&1; then
      DRIVE_PYTHON="$(command -v "$candidate")"
      return 0
    fi
  done
  return 1
}
