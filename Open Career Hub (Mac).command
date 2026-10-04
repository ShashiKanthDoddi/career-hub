#!/bin/bash
# Double-click to open Harshitha's Career Hub.
cd "$(dirname "$0")"
clear
echo "Career Hub is starting... This window runs the app: keep it open (it minimises itself)."
osascript -e 'tell application "Terminal" to set miniaturized of front window to true' >/dev/null 2>&1 &
export CAREERHUB_LAUNCHER=1
while true; do
  python3 career_hub.py
  code=$?
  if [ "$code" = "42" ]; then continue; fi     # 42 = an update was installed: start the new version
  break
done
