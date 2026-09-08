#!/usr/bin/env bash
# Run the suite where CI runs it. Everything else here is macOS, and what the two
# platforms disagree about is exactly what a browser test measures: how wide a system
# font sets a word, and whether a scrollbar takes a gutter out of the window. Nine tests
# failed on the runner from the day CI landed and none of them could be reproduced.
#
#   scripts/linux-suite.sh
#   scripts/linux-suite.sh tests -m nightly --splits 4 --group 2 \
#     --splitting-algorithm least_duration --durations-path .test_durations
#
# Needs a Docker daemon that can run linux/amd64 (linux-suite.Dockerfile says why). On
# Apple silicon that is `colima start --vm-type vz --vz-rosetta`.
#
# Size that VM for the suite rather than for a shell. The reproducible browser setup is
# `--cpu 8 --memory 16`; a smaller VM can turn runner pressure into product failures.
#
#   LEAF_SUITE_NATIVE=1 scripts/linux-suite.sh tests/test_render_controls.py -k banner
#
# Emulating amd64 is what makes this image CI's, and it is also the part that breaks:
# without Rosetta, qemu kills Chromium's GPU process before the first context opens, on
# `about:blank` as readily as on a page, which surfaces as `TargetClosedError` and reads
# like a product failure. `LEAF_SUITE_NATIVE=1` builds and runs for the host's own
# architecture instead.
#
# What that still reproduces is the reason to reach for it: text metrics belong to the
# font, not the CPU, so a native image carrying CI's fonts answers a face-dependent
# failure — a reserved width measured in the wrong face, a line that wraps past its clamp
# — with CI's own numbers. What it gives up is Google Chrome, which ships for amd64 only,
# so the handful of tests that drive the installed launcher are not covered. Reach for it
# when a failure is about how wide something is; use the emulated image otherwise.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
git_common_dir="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)"

# The default reproduces CI's everyday job. A nightly failure's group number and the
# remaining split arguments above reproduce that job's exact selection and parallelism.
if [ $# -eq 0 ]; then set -- tests; fi

# Separate tags and caches per build, so switching between them neither rebuilds the
# other nor runs one image's browser against the other's libraries.
if [ -n "${LEAF_SUITE_NATIVE:-}" ]; then
  tag=leaf-linux-suite-native
  build=(--build-arg CHROME=0)
  run=()
else
  tag=leaf-linux-suite
  build=(--platform linux/amd64)
  run=(--platform linux/amd64)
fi

docker build "${build[@]}" -t "$tag" -f "$HERE/linux-suite.Dockerfile" "$HERE"

# --shm-size, because Chrome's default 64MB there is where a tab dies mid-suite. The
# named volumes hold uv's packages and Playwright's browser. The first run fills them,
# and a container thrown away after every run still resolves against warm caches.
exec docker run --rm "${run[@]}" --shm-size=2g --workdir "$ROOT" \
  -v "$ROOT:$ROOT" -v "$git_common_dir:$git_common_dir:ro" \
  --mount "type=volume,dst=$ROOT/.venv,volume-nocopy" \
  -v "$tag-uv:/root/.cache/uv" \
  -v "$tag-playwright:/root/.cache/ms-playwright" \
  "$tag" bash -c \
    'uv run --frozen playwright install chromium --only-shell \
      && exec uv run --frozen pytest "$@"' \
    bash "$@"
