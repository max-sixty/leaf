# The shipped payload

This directory is installed into hosts. It has no install-time build step and
must work when the install directory is read-only.

## The host supplies the runtime

`skills/leaf/scripts/interact.py` declares payload dependencies in its PEP 723
header. State the lowest version the suite passes on, with no upper cap. The
payload ships no lock: `uv` must resolve through the index and Python supply the
host configured, including private mirrors and Python download mirrors.

`bin/leaf` invokes that script and resolves Playwright through the same host
environment when a browser check needs it. Browser checks launch the host's
installed Chrome; the payload does not download a browser.

Do not write caches, generated files, or repaired state back into the installed
payload. Plugin updates may replace this directory wholesale.

The repository's `pyproject.toml` and `uv.lock` define the developer and test
environment only. They are not part of the installed dependency contract.

## Generated bundles

Files under `skills/leaf/assets/vendor/` and
`skills/leaf/packages/default/vendor/` are committed payload outputs. Their
generators and source-version choices live under the repository's `scripts/`.
Follow `scripts/CLAUDE.md`, update or run the owning script, and do not patch a
generated bundle directly.
