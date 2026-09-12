#!/usr/bin/env bash
# Reproduce a Linux CI failure locally. Everything else here is macOS, and what the two
# platforms disagree about is exactly what a browser test measures: how wide a system
# font sets a word, and whether a scrollbar takes a gutter out of the window. Nine tests
# failed on the runner from the day CI landed and none of them could be reproduced.
#
#   scripts/linux-suite.sh tests
#   scripts/linux-suite.sh tests/test_render_controls.py -k banner
#   scripts/linux-suite.sh tests -m nightly
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

# This is a platform-specific diagnostic, not the normal local gate; that remains
# `uv run pytest tests` on the host. Require an explicit selection so invoking this
# diagnostic by accident does not start the whole Linux suite.
if [ $# -eq 0 ]; then
  echo "usage: scripts/linux-suite.sh <pytest arguments>" >&2
  exit 2
fi

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

# --shm-size, because Chrome's default 64MB there is where a tab dies mid-suite.
# Python's bytecode cache stays container-local so concurrent host and Linux runs never
# rewrite the same pytest assertion cache. The named volumes hold uv's packages, managed
# Python, and Playwright's browser; later containers resolve against those warm caches.
# uv otherwise installs Python under the container's ephemeral /root/.local and downloads
# the same interpreter again on every invocation. The cache and environment are separate
# volumes, so copying is the only available link mode.
exec docker run --rm "${run[@]}" --shm-size=2g --workdir "$ROOT" \
  -e PYTHONPYCACHEPREFIX=/tmp/pycache \
  -e UV_LINK_MODE=copy \
  -e UV_PYTHON_INSTALL_DIR=/root/.cache/uv/python \
  -v "$ROOT:$ROOT" -v "$git_common_dir:$git_common_dir:ro" \
  --mount "type=volume,dst=$ROOT/.venv,volume-nocopy" \
  -v "$tag-uv:/root/.cache/uv" \
  -v "$tag-playwright:/root/.cache/ms-playwright" \
  "$tag" bash -c \
    'uv run --frozen playwright install chromium --only-shell \
      && exec uv run --frozen pytest "$@"' \
    bash "$@"
