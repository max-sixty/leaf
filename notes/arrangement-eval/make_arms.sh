#!/usr/bin/env bash
# Extract one Leaf payload per arm from a git ref.
#
# Usage: make_arms.sh <ref> <out-dir>
#
# <out-dir>/leaf is the payload at <ref> as an installed plugin carries it (bin,
# skills, the uv project). <out-dir>/plain is the same payload with the arrangement
# vocabulary taken out by plain_arm.py. Neither holds .git, examples, docs, notes or the
# README, so an
# author cannot read its way to the other arm's vocabulary through history or the
# worked corpus. Each arm's launcher is run once so uv builds its environment before
# any timed run starts.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
ref=$1; out=$2
mkdir -p "$out"
for arm in leaf plain; do
  rm -rf "${out:?}/$arm"
  mkdir -p "$out/$arm"
  git -C "$root" archive "$ref" bin skills pyproject.toml uv.lock | tar -x -C "$out/$arm"
done
python3 "$here/plain_arm.py" "$out/plain"
git -C "$root" rev-parse "$ref" > "$out/REF"
for arm in leaf plain; do
  "$out/$arm/bin/leaf" --root
done
