#!/usr/bin/env bash
#
# Claude Code on the web starts a container with uv, node and Go on it and none of
# what the gates need: no system Chrome, so every browser test fails at launch; no
# pre-commit, so the lint can't run at all. `.config/cloud/environment.sh` is what
# supplies them, shared with Codex Cloud, and this hook is how that script is
# reached here.
#
# Synchronous on purpose. The session pays the install once — the container is
# cached afterwards — and in exchange no session can open on a half-built
# environment and read a browser failure as the change under test. The timeout in
# `settings.json` is generous for the same reason: a cold container spends around
# ten minutes here, mostly on Chrome's packages and the hook environments, and a cap
# that expires part-way through delivers exactly the half-built environment this is
# written to rule out. Finishing early costs nothing.
#
# The guard is the whole reason this is a wrapper rather than a path straight to the
# script: that script installs system packages and approves this repo's Worktrunk
# commands without review, which is fine in a container that is discarded and not on
# the machine a developer runs `claude` from. The same hook file serves both, so it
# is the environment that decides, not a memory of which one this is.
set -euo pipefail

[[ "${CLAUDE_CODE_REMOTE:-}" == "true" ]] || exit 0

# A SessionStart hook's stdout becomes the session's context, and an install writes
# hundreds of lines nobody asked to read — an apt-get transcript arriving as if the
# repo had said it. So the setup speaks on stderr, where a failure still reaches the
# transcript and a success costs the session nothing.
exec bash "${CLAUDE_PROJECT_DIR:-.}/.config/cloud/environment.sh" >&2
