# Codex Cloud

Leaf's Cloud setup lives in `environment.sh`. It installs pinned Worktrunk,
approves the commands in `.config/wt.toml`, syncs the locked developer
environment, installs system Chrome for the browser suite, and warms the
pre-commit hooks.

## Create the environment

Land this directory and `AGENTS.md` on the default branch. Then open
**Codex settings → Environments**, create an environment for `max-sixty/leaf`,
and use these settings:

| Setting | Value |
|---|---|
| Container image | `universal` |
| Container caching | On |
| Agent internet access | On |
| Domain allowlist | Common dependencies |
| Allowed HTTP methods | `GET`, `HEAD`, and `OPTIONS` |

Use this exact command for both **Setup script** and **Maintenance script**:

```bash
ENVIRONMENT_SHA=58e1936cabda3b8f02595ae93b9f6a4304fea15c8aedf054575663aaed6a9f98; printf '%s  %s\n' "$ENVIRONMENT_SHA" .config/codex-cloud/environment.sh | sha256sum -c - && bash .config/codex-cloud/environment.sh
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

The same script prepares fresh and cached containers. It resyncs `uv.lock`,
updates Worktrunk approvals, refreshes browser system dependencies, and warms
the hook environments from the checked-out branch. Reset the environment cache
when a repository change makes the cached container incompatible.

The checksum prevents a task branch from replacing `environment.sh` before
Cloud runs it automatically. After a reviewed change to that script reaches the
default branch, update both saved commands with its new `sha256sum`; changing
the environment settings also invalidates the cache.

The script is Cloud-specific: it installs system packages and approves this
repo's Worktrunk commands without review. Do not use it as workstation setup.
