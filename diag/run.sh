#!/bin/bash
# Temporary CI diagnostic for two load-sensitive tests. Removed before landing.
set -u
mkdir -p .tmp/diag
T1="tests/test_interact_session.py::test_a_user_move_no_carrier_will_pick_up_messages_its_claude_code_session"
A="tests/test_render_shift_watch.py::test_native_anchor_scroll_retains_local_motion_proof"
for i in 1 2 3; do
  for t in none "scale(.8)" "scale(.8) rotate(10deg)"; do
    echo "== probe $t"; uv run python diag/anchor_probe2.py "$t"
  done
done > .tmp/diag/probe.log 2>&1

(for i in $(seq 5); do LF_NUDGE_TRACE=1 uv run leaf-dev flake "$T1"; done) > .tmp/diag/t1-flake.log 2>&1 &
t1=$!
for round in $(seq 8); do
  hogs=()
  if [ $((round % 2)) -eq 0 ]; then
    for h in 1 2 3 4; do (while :; do :; done) & hogs+=($!); done
  fi
  echo "== round $round hogs=${#hogs[@]}"
  uv run leaf-dev flake "$A[none-]" "$A[scale(.8)-]" "$A[scale(.8) rotate(10deg)-]"
  [ ${#hogs[@]} -gt 0 ] && kill "${hogs[@]}"
done > .tmp/diag/t2-flake.log 2>&1
wait $t1

LF_NUDGE_TRACE=1 uv run pytest tests/test_interact_session.py -q > .tmp/diag/t1-file.log 2>&1
echo "file exit $?" >> .tmp/diag/t1-file.log

grep -E "^\| |copies" .tmp/diag/t2-flake.log .tmp/diag/t1-flake.log
grep -c "TRACE-BEGIN" -r .tmp/flake | grep -v ":0" | head -40
tail -5 .tmp/diag/t1-file.log
exit 0
