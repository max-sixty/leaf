#!/usr/bin/env bash
# Run the suite where CI runs it. Everything else here is macOS, and what the two
# platforms disagree about is exactly what a browser test measures: how wide a system
# font sets a word, and whether a scrollbar takes a gutter out of the window. Nine tests
# failed on the runner from the day CI landed and none of them could be reproduced.
#
#   scripts/linux-suite.sh
#   scripts/linux-suite.sh tests/test_render.py -k a_press --run-nightly
#
# Needs a Docker daemon that can run linux/amd64 (linux-suite.Dockerfile says why). On
# Apple silicon that is `colima start --vm-type vz --vz-rosetta`.
#
# Size that VM for the suite rather than for a shell. The reproducible Chrome setup is
# `--cpu 8 --memory 16`; a smaller VM can turn runner pressure into product failures.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# The default is CI's own command, `--run-nightly` and all, because reproducing what CI
# saw is the whole point of running here.
if [ $# -eq 0 ]; then set -- tests --run-nightly; fi

docker build --platform linux/amd64 -t leaf-linux-suite \
  -f "$HERE/linux-suite.Dockerfile" "$HERE"

# --shm-size, because Chrome's default 64MB there is where a tab dies mid-suite. The
# named volume is uv's cache, which the first run fills and the rest read, so a container
# thrown away after every run still resolves against a warm one.
exec docker run --rm --platform linux/amd64 --shm-size=2g \
  -v "$ROOT:/repo" -v leaf-linux-suite-uv:/root/.cache/uv \
  leaf-linux-suite uv run --frozen pytest "$@"
