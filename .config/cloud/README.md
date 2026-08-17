# Cloud environments

What a cloud container needs before it can pass the gates is `wt configure-cloud`,
declared in `.config/wt.toml` beside the gates themselves: it syncs the locked
developer environment, installs the system Chrome the browser suite attaches to,
and warms the pre-commit hooks. Run it by hand in any container that already has
`wt`; `wt config alias show configure-cloud` prints what it will do.

`environment.sh` is the part that cannot be an alias, because `wt` has to exist
before one can be invoked. It installs Worktrunk, approves this branch's
declarations, and calls the alias. Both hosts run that one file, because both
containers arrive missing the same things; each reaches it its own way, and that is
the only difference between them:

| Host | How it reaches the script |
|---|---|
| Codex Cloud | Setup and maintenance commands, saved in the environment's settings |
| Claude Code on the web | `.claude/hooks/session-start.sh`, a `SessionStart` hook in `.claude/settings.json` |

No tool version is written in either place. `uv.lock` pins what `uv sync` installs,
`.pre-commit-config.yaml`'s hook revs decide the lint, and Worktrunk is installed
unpinned when absent — so a cached container keeps the `wt` it was built with until
the cache is reset, which is also what lets it start with no network at all.

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
ENVIRONMENT_SHA=631878cdf18773b0a4e736ccc92e483b0e3e1c893c539df5edd1e7aa3df26df4; printf '%s  %s\n' "$ENVIRONMENT_SHA" .config/cloud/environment.sh | sha256sum -c - && bash .config/cloud/environment.sh
```

The environment needs no variables or secrets. Internet access remains on
because the nightly tests resolve the launcher's extra Playwright requirement
against the package index; the dependency preset and read-only HTTP methods
cover that use.

After saving the environment, start a Cloud task on the default branch and
validate it with:

```text
Run wt --version,
test "$(wt config approvals list --format=json | jq -r .state)" = approved,
google-chrome --version, wt hook pre-merge, and
test -z "$(git status --short)". Require every command to pass.
```

The approval assert is the one that covers the alias: `configure-cloud` is a
project declaration like the pre-merge commands, so an unapproved container would
stop the setup at a prompt with nobody there to answer it.

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

Now that the steps live in the alias, that checksum covers a bootstrap that has no
reason to change often, so the hand-copied hash stops being a recurring chore. It
also no longer covers the steps themselves: a branch's `configure-cloud` is what
`wt config approvals add --yes` approves unread, which is a container's business —
the agent there can run commands anyway — and not something to rely on elsewhere.

The script is cloud-specific: it installs system packages and approves this
repo's Worktrunk commands without review. Do not use it as workstation setup, and
keep each entry point's guard on it — Claude's hook checks
`CLAUDE_CODE_REMOTE`, and Codex only ever runs it in a container of its own.
