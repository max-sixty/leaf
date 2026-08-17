# Cloud environments

`environment.sh` is what a cloud container runs before it can pass the gates: it
installs pinned Worktrunk, approves the commands in `.config/wt.toml`, syncs the
locked developer environment, installs system Chrome for the browser suite, and
warms the pre-commit hooks.

Both hosts run that one script, because both containers arrive missing the same
things. Each host reaches it its own way, and that is the only difference between
them:

| Host | How it reaches the script |
|---|---|
| Codex Cloud | Setup and maintenance commands, saved in the environment's settings |
| Claude Code on the web | `.claude/hooks/session-start.sh`, a `SessionStart` hook in `.claude/settings.json` |

Neither is workstation setup — see the last section.

## Claude Code on the web

Nothing to configure. The hook is in the repo, so a session on a branch that
carries it is set up by it, and merging it to the default branch is what puts it
under every session after.

The container it starts with has uv, node and Go and none of what the gates want.
Without the hook, `uv run pytest tests` fails at browser launch on all of it: there
is no system Chrome, and the Chromium that is preinstalled is some other build than
the locked Playwright expects, which is no substitute for a suite that attaches to
`channel="chrome"`. `pre-commit` isn't there at all, so the lint can't run either.

The hook runs synchronously, so a session opens on a finished environment rather
than racing the install — the container is cached afterwards, so it is the first
session that waits. It does nothing outside the cloud: `CLAUDE_CODE_REMOTE` is
what it checks, and the same file on a workstation exits without touching it.

Two tests still fail there and no setup can fix them: the container has no IPv6
stack at all — no `/proc/net/if_inet6`, and an `AF_INET6` socket is refused on
creation — so the pair that bind the stated-host wildcard `::` cannot run
(`test_the_stated_host_wildcard_serves_both_families` and
`test_others_ships_on_a_network_facing_bind_too`, one failing and one erroring in
its fixture). Everything else passes: 725 passed, 8 skipped on the everyday run,
around fourteen minutes on the container's four cores rather than the two minutes
a workstation takes. They are left failing rather than skipped because landing is
`wt merge` from a workstation, where the stack exists and the gate means what it
says; a cloud session that reads those two names has found the container, not its
own change.

## Codex Cloud

Open **Codex settings → Environments**, create an environment for
`max-sixty/leaf`, and use these settings:

| Setting | Value |
|---|---|
| Container image | `universal` |
| Container caching | On |
| Agent internet access | On |
| Domain allowlist | Common dependencies |
| Allowed HTTP methods | `GET`, `HEAD`, and `OPTIONS` |

Use this exact command for both **Setup script** and **Maintenance script**:

```bash
ENVIRONMENT_SHA=02ab3801de89b9f7c2761f66af956fbf4471f1c0503813e30dbc93b38b8da3d1; printf '%s  %s\n' "$ENVIRONMENT_SHA" .config/cloud/environment.sh | sha256sum -c - && bash .config/cloud/environment.sh
```

The environment needs no variables or secrets. Internet access remains on
because the nightly tests resolve the launcher's extra Playwright requirement
against the package index; the dependency preset and read-only HTTP methods
cover that use.

After saving the environment, start a Cloud task on the default branch and
validate it with:

```text
Run test "$(wt --version)" = "wt v0.74.0",
test "$(wt config approvals list --format=json | jq -r .state)" = approved,
google-chrome --version, wt hook pre-merge, and
test -z "$(git status --short)". Require every command to pass.
```

## Keep it current

The same script prepares fresh and cached containers on either host. It resyncs
`uv.lock`, updates Worktrunk approvals, refreshes browser system dependencies,
and warms the hook environments from the checked-out branch. Reset the
environment cache when a repository change makes the cached container
incompatible.

Codex's checksum prevents a task branch from replacing `environment.sh` before
Cloud runs it automatically. After a reviewed change to that script reaches the
default branch, update both saved commands with its new `sha256sum`; changing the
environment settings also invalidates the cache. Claude's hook is read from the
branch it runs on and needs no such update, the settings that name it being in
the repo beside it.

The script is cloud-specific: it installs system packages and approves this
repo's Worktrunk commands without review. Do not use it as workstation setup, and
keep each entry point's guard on it — Claude's hook checks
`CLAUDE_CODE_REMOTE`, and Codex only ever runs it in a container of its own.
