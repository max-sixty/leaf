# Cloud environments

The setup is `wt configure-cloud`, declared in `.config/wt.toml` beside the gates it
exists to make runnable: it syncs the locked developer environment, installs the
system Chrome the browser suite attaches to, and warms the pre-commit hooks. Run it
by hand in any container that already has `wt`; `wt config alias show
configure-cloud` prints what it will do.

That alias is the whole of what the repo carries. There is no setup script, because
the only thing one would hold is the step that cannot be an alias — `wt` has to
exist before one can be invoked — and every host already has a field where a
command string goes:

| Host | Where the chain goes |
|---|---|
| Codex Cloud | Setup and maintenance scripts, in the environment's settings |
| Claude Code on the web | A `SessionStart` hook in `.claude/settings.local.json`, written per container |

One chain serves both:

```sh
command -v wt >/dev/null 2>&1 || {
  curl --proto '=https' --tlsv1.2 -LsSf --retry 6 --retry-all-errors --retry-delay 2 \
    -o /tmp/wt-install.sh \
    https://github.com/max-sixty/worktrunk/releases/latest/download/worktrunk-installer.sh
  WORKTRUNK_UNMANAGED_INSTALL="$HOME/.local/bin" sh /tmp/wt-install.sh
}
export PATH="$HOME/.local/bin:$PATH"
wt config approvals add --yes
wt configure-cloud
```

Nothing in it is piped, which is what lets one form run under either host's shell:
`sh` has no `pipefail`, so a downloader piped into a shell reports success when the
download failed, having installed nothing and left the setup to run without its
tools. Downloading to a file and running the file fails where it should.

The approvals step comes before the alias and not after. A project alias is
approval-gated exactly like the pre-merge commands, so an unapproved container
stops the setup at a prompt with nobody there to answer it.

No tool version is written down anywhere. `uv.lock` pins what `uv sync` installs and
`.pre-commit-config.yaml`'s hook revs decide the lint, so pinning the runner that
reads them was a second number to bump for no behaviour it could change. Worktrunk
is installed unpinned and only when absent, so a cached container keeps the `wt` it
was built with until the cache is reset — which is also what lets it start with no
network at all.

## Claude Code on the web

Written per container, the file being gitignored. Paste into
`.claude/settings.local.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "[ \"${CLAUDE_CODE_REMOTE:-}\" = true ] || exit 0; { command -v wt >/dev/null 2>&1 || { curl --proto '=https' --tlsv1.2 -LsSf --retry 6 --retry-all-errors --retry-delay 2 -o /tmp/wt-install.sh https://github.com/max-sixty/worktrunk/releases/latest/download/worktrunk-installer.sh && WORKTRUNK_UNMANAGED_INSTALL=\"$HOME/.local/bin\" sh /tmp/wt-install.sh; } && export PATH=\"$HOME/.local/bin:$PATH\" && wt config approvals add --yes && wt configure-cloud; } >&2",
            "timeout": 1800,
            "statusMessage": "Preparing leaf's cloud environment"
          }
        ]
      }
    ]
  }
}
```

Untracked is the point rather than an inconvenience: the chain installs system
packages and approves this repo's Worktrunk commands unread, which is a discarded
container's business and not that of the machine a developer runs `claude` from. A
checked-in `settings.json` would put it under every session, workstation ones
included; the `CLAUDE_CODE_REMOTE` test is what covers the copy that lands on one
anyway.

The hook runs synchronously, so a session opens on a finished environment rather
than racing the install — the container is cached afterwards, so it is the first
session that waits. The timeout is generous for the same reason: a cold container
spends around ten minutes, mostly on Chrome's packages and the hook environments,
and a cap expiring part-way through delivers exactly the half-built environment the
sync is written to rule out. It writes to stderr because a `SessionStart` hook's
stdout becomes the session's context, where an install's hundreds of lines would
arrive as if the repo had said them.

The container starts with uv, node and Go and none of what the gates want. Without
the chain, `uv run pytest tests` fails at browser launch on all of it: there is no
system Chrome, and the Chromium that is preinstalled is some other build than the
locked Playwright expects, which is no substitute for a suite that attaches to
`channel="chrome"`. `pre-commit` isn't there at all, so the lint can't run either.

Two tests still fail there and no setup can fix them: the container has no IPv6
stack at all — no `/proc/net/if_inet6`, and an `AF_INET6` socket is refused on
creation — so the pair that bind the stated-host wildcard `::` cannot run
(`test_the_stated_host_wildcard_serves_both_families` and
`test_others_ships_on_a_network_facing_bind_too`, one failing and one erroring in
its fixture). Everything else passes: 725 passed, 8 skipped on the everyday run,
around fourteen minutes on the container's four cores rather than the two minutes a
workstation takes. They are left failing rather than skipped because landing is
`wt merge` from a workstation, where the stack exists and the gate means what it
says; a cloud session that reads those two names has found the container, not its
own change.

## Codex Cloud

Open **Codex settings → Environments**, create an environment for `max-sixty/leaf`,
and use these settings:

| Setting | Value |
|---|---|
| Container image | `universal` |
| Container caching | On |
| Agent internet access | On |
| Domain allowlist | Common dependencies |
| Allowed HTTP methods | `GET`, `HEAD`, and `OPTIONS` |

Use this for both **Setup script** and **Maintenance script** — the chain above, on
one line and without the hook's guard:

```bash
command -v wt >/dev/null 2>&1 || { curl --proto '=https' --tlsv1.2 -LsSf --retry 6 --retry-all-errors --retry-delay 2 -o /tmp/wt-install.sh https://github.com/max-sixty/worktrunk/releases/latest/download/worktrunk-installer.sh && WORKTRUNK_UNMANAGED_INSTALL="$HOME/.local/bin" sh /tmp/wt-install.sh; } && export PATH="$HOME/.local/bin:$PATH" && wt config approvals add --yes && wt configure-cloud
```

There is no checksum on it any more, and nothing left for one to guard. It used to
read a script out of the branch, which a task branch could rewrite before Cloud ran
it unattended; the chain now lives in the environment's own settings, where a branch
cannot reach it at all. What the branch still decides is the alias body, which
`--yes` approves unread — as it always did, the checksum never having covered it.

The environment needs no variables or secrets. Internet access remains on because
the nightly tests resolve the launcher's extra Playwright requirement against the
package index; the dependency preset and read-only HTTP methods cover that use.

After saving the environment, start a Cloud task on the default branch and validate
it with:

```text
Run wt --version,
test "$(wt config approvals list --format=json | jq -r .state)" = approved,
google-chrome --version, wt hook pre-merge, and
test -z "$(git status --short)". Require every command to pass.
```

The approval assert is the one that covers the alias, for the reason above.

## Keep it current

The chain prepares fresh and cached containers alike. It resyncs `uv.lock`, updates
Worktrunk approvals, refreshes browser system dependencies, and warms the hook
environments from the checked-out branch. Reset the environment cache when a
repository change makes the cached container incompatible.

None of it is workstation setup: it installs system packages and approves this
repo's Worktrunk commands without review. Keep it in a container — Codex only ever
runs it in one of its own, and Claude's copy is untracked and guarded.
