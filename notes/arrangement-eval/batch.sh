#!/usr/bin/env bash
# Run every subject in both arms, <rounds> times, all runs of a round at once.
#
# Usage: batch.sh <arms-dir> <batch> <rounds> [subject ...]
#
# A round starts every subject × arm pair together, so load on the machine lands on
# both arms alike, and waits for all of them before the next round starts.
set -u
here=$(cd "$(dirname "$0")" && pwd)
arms=$1; batch=$2; rounds=$3; shift 3
subjects=("$@")
[ ${#subjects[@]} -eq 0 ] && subjects=(document dashboard queue)
for n in $(seq 1 "$rounds"); do
  for s in "${subjects[@]}"; do
    for arm in leaf plain; do
      "$here/run.sh" "$arms" "$arm" "$s" "$n" "$batch" &
    done
  done
  wait
done
