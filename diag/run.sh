#!/bin/bash
# Temporary CI A/B for the anchor test's setup frame. Removed before landing.
set -u
mkdir -p .tmp/diag
A="tests/test_render_shift_watch.py::test_native_anchor_scroll_retains_local_motion_proof"
for round in $(seq 24); do
  hogs=()
  if [ $((round % 4)) -ge 2 ]; then
    for h in 1 2 3 4; do (while :; do :; done) & hogs+=($!); done
  fi
  if [ $((round % 2)) -eq 0 ]; then arm=base; export LF_SETUP_BASE=1; else arm=fixed; unset LF_SETUP_BASE; fi
  echo "== round $round arm=$arm hogs=${#hogs[@]}"
  uv run leaf-dev flake "$A[none-]" "$A[scale(.8)-]" "$A[scale(.8) rotate(10deg)-]"
  [ ${#hogs[@]} -gt 0 ] && kill "${hogs[@]}"
done > .tmp/diag/ab.log 2>&1
grep -E "^== |^\| .tests|copies" .tmp/diag/ab.log
exit 0
