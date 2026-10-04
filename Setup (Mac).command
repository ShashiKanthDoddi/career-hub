#!/bin/bash
# One-time setup for Harshitha's Career Hub. Double-click to run.
cd "$(dirname "$0")"
clear
echo "======================================================"
echo "   HARSHITHA'S CAREER HUB  -  ONE-TIME SETUP"
echo "======================================================"
echo
xattr -dr com.apple.quarantine . 2>/dev/null

echo "Step 1 of 3: checking Python..."
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
  echo
  echo "  Python isn't ready on this Mac yet."
  echo "  A window may appear asking to install 'command line developer tools'."
  echo "  -> Click INSTALL, then AGREE, and wait until it finishes (5-15 minutes)."
  echo
  echo "  If no window appears, install Python from:  https://www.python.org/downloads/"
  echo
  echo "  When that's done, double-click this Setup file again."
  xcode-select --install >/dev/null 2>&1
  echo
  read -p "Press Return to close this window..."
  exit 1
fi
echo "  OK: $(python3 --version)"
echo

echo "Step 2 of 3: installing helper parts (1-3 minutes, lots of text is normal)..."
python3 -m pip install --user --upgrade pip >/dev/null 2>&1
if ! python3 -m pip install --user playwright pyyaml pypdf; then
  python3 -m pip install --user --break-system-packages playwright pyyaml pypdf || {
    echo; echo "  Something went wrong. Check your internet and double-click Setup again."
    read -p "Press Return to close..."; exit 1; }
fi
echo

echo "Step 3 of 3: downloading a backup browser (about 150 MB)..."
python3 -m playwright install chromium
echo
echo "======================================================"
echo "   ALL SET, HARSHITHA!"
echo "======================================================"
echo
echo "Next: double-click  'Open Career Hub (Mac)'  and fill in the Profile tab."
echo
read -p "Press Return to close this window..."
