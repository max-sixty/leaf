"""`python -m leaf`, the form every leaf process runs in.

`bin/leaf` comes through here too — its comment carries why it avoids the
`leaf` console script — so the console script's users are the hook guard and a
developer's `uv run leaf`. A subprocess leaf starts for itself — the page
server in `hosting.py`, the Codex adapter in `codex.py` — has `sys.executable`
in hand and no reason to find a launcher or a script path again.

`prog_name` is fixed rather than left to argv, because `leaf` is the name the
skill hands an agent and so the name every usage line has to say back.
"""

from leaf.cli import cli

if __name__ == "__main__":
    cli(prog_name="leaf")
