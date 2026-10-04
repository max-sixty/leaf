"""Prove the branch's tests catch the bug its change removes.

    uv run leaf-dev bugback NODEID...

A test earns its place when it fails without the change it pins. This runs the named
tests on HEAD as a control, then again with the branch's change reverted, and reports
each as `caught` (its call failed reverted) or `blind` (it passed reverted); any other
reading is the test's outcome (`leaf_dev.suite`) with its message, such as `error`
where the revert broke its setup or its module's import, which is red but not by its
own assertion. The revert restores, from the merge base with `main`, every path but
the tests, the tooling they import, and the environment's manifests and locks
(`KEPT`). Compiled bundles are committed, so they revert with their sources.

Both runs happen in a scratch worktree detached at HEAD, removed when the command ends,
so commit first. Output and reports stay under `.tmp/bugback/`. Exits 1 unless every
test is caught.
"""

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import merge_base
from leaf_dev.suite import collect, run

OUT = ROOT / ".tmp" / "bugback"
# What the revert leaves at HEAD: the tests, the tooling they import, and the
# environment the runs share.
KEPT = (
    "tests", "dev", "pyproject.toml", "uv.lock", "package.json", "package-lock.json",
)  # fmt: skip


def git(*args: str, cwd: Path = ROOT) -> str:
    proc = subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True, check=False
    )
    if proc.returncode:
        raise click.ClickException(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


@click.command()
@click.argument("selection", nargs=-1, required=True)
def bugback(selection: tuple[str, ...]) -> None:
    """Prove tests go red with the branch's change reverted.

    Runs SELECTION, pytest node ids, on HEAD and again with every non-test path
    since the merge base with main reverted, and reports per test whether it was
    caught. Runs in a scratch worktree at HEAD, so commit first. Exits 1 unless
    every test is caught.
    """
    if dirty := git("status", "--porcelain"):
        raise click.ClickException(
            f"bugback runs HEAD in a scratch worktree; commit first:\n{dirty}"
        )
    base = merge_base()
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-")
    out = Path(tempfile.mkdtemp(prefix=stamp, dir=OUT))
    kept = [f":(exclude){path}" for path in KEPT]
    if not git("diff", "--name-only", base, "HEAD", "--", ".", *kept):
        raise click.ClickException(
            f"the branch changes nothing outside {', '.join(KEPT)} since {base[:12]}"
        )
    scratch = Path(tempfile.mkdtemp(prefix="leaf-bugback-"))
    git("worktree", "add", "--detach", str(scratch), "HEAD")
    try:
        items = collect(scratch, selection, out / "collect.log")
        control = run(scratch, selection, items, out / "control")
        git("restore", f"--source={base}", "--", ".", *kept, cwd=scratch)
        reverted = run(
            scratch, selection, items, out / "reverted",
            "--continue-on-collection-errors",
        )  # fmt: skip
    finally:
        remove = ["git", "-C", ROOT, "worktree", "remove", "--force", scratch]
        subprocess.run(remove, check=False)

    def verdict(item: str) -> str:
        if control[item].result != "passed":
            return f"control {control[item].result}"
        result = reverted[item].result
        return {"failed": "caught", "passed": "blind"}.get(result, result)

    verdicts = {item: verdict(item) for item in items}
    click.echo("| test | verdict |\n|---|---|")
    for item in items:
        click.echo(f"| `{item}` | {verdicts[item]} |")
    click.echo("")
    for name, outcomes in (("control", control), ("reverted", reverted)):
        for item in items:
            if first := outcomes[item].message.strip().partition("\n")[0]:
                click.echo(f"- {name}, `{item}`: {first}")
    click.echo(f"\nlogs: {out.relative_to(ROOT)}/")
    raise SystemExit(0 if all(v == "caught" for v in verdicts.values()) else 1)
