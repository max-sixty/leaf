# The suite's other platform: near enough to what `.github/workflows/ci.yaml` runs on
# that a failure here is the failure there. The bulk suite uses Playwright's pinned
# Chromium headless shell; Google Chrome remains for the tests that drive the installed
# launcher's render command. Google ships Chrome for amd64, which is what the image is
# built and run `--platform linux/amd64` for. The fonts are what the platforms differ
# over: `system-ui` resolves to DejaVu here, and a word set wider than the face a number
# was read in is how a reserved width goes short.
FROM ubuntu:24.04

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/venv

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg \
 && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
      | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list \
 && apt-get update && apt-get install -y --no-install-recommends \
      google-chrome-stable fonts-liberation fonts-dejavu-core fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

# The checkout is mounted rather than copied, and linux-suite.sh installs the locked
# headless shell into its persistent browser cache. `/venv` is the container's
# environment; the `.venv` beside the checkout holds the host's binaries.
WORKDIR /repo
