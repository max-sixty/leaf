"""Prove the branch's tests catch the bug its change removes.

    uv run leaf-dev suite bugback NODEID...

A test earns its place when it fails without the change it pins. This runs the named
tests on the working tree as it stands, uncommitted edits included, as a control, then
again with the branch's change reverted, and reports each as `caught` (its call failed
reverted) or `blind` (it passed reverted); any other reading is the test's outcome
(`leaf_dev.suite`) with its message, such as `error` where the revert broke its setup
or its module's import, which is red but not by its own assertion. The revert
restores, from the merge base with `main`, every path but the tests, the tooling they
import, and the environment's manifests and locks (`KEPT`). Compiled bundles are
committed, so they revert with their sources.

Both runs happen in one checkout (`suite.checkout`) of a snapshot of the working tree
taken as the command starts (`suite.snapshot`), removed when it ends, so an edit made
during the runs reaches neither. Output and reports stay under `.tmp/bugback/`. Exits 1
unless every test is caught.

This keeps its own revert rather than taking a base from `arms.choose_arms`: that base
is the whole tree at the merge base, tests included, while the reverted run needs this
working tree's tests over the merge base's code.
"""

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import merge_base
from leaf_dev.suite import Outcome, checkout, collect, run, snapshot

OUT = ROOT / ".tmp" / "bugback"
# What the revert leaves as the working tree has it: the tests, the tooling they
# import, and the environment the runs share.
KEPT = (
    "tests", "dev", "pyproject.toml", "uv.lock", "package.json", "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
)  # fmt: skip


def git(*args: str, cwd: Path) -> str:
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

    Runs SELECTION, pytest node ids, on the working tree, uncommitted edits included,
    and again with every non-test path since the merge base with main reverted, and
    reports per test whether it was caught. Exits 1 unless every test is caught.
    """
    base = merge_base()
    kept = [f":(exclude){path}" for path in KEPT]
    # The tracked paths the working tree changes, and the untracked ones it adds.
    if not (
        git("diff", "--name-only", base, "--", ".", *kept, cwd=ROOT)
        + git("ls-files", "--others", "--exclude-standard", "--", ".", *kept, cwd=ROOT)
    ):
        raise click.ClickException(
            f"the working tree changes nothing outside {', '.join(KEPT)} "
            f"since {base[:12]}"
        )
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-")
    out = Path(tempfile.mkdtemp(prefix=stamp, dir=OUT))
    with tempfile.TemporaryDirectory(prefix="leaf-bugback-") as directory:
        candidate, tree = Path(directory) / "snapshot", Path(directory) / "checkout"
        snapshot(candidate)
        checkout(candidate, tree)
        items = collect(tree, selection, out / "collect.log")
        control = run(tree, selection, items, out / "control")
        git("restore", f"--source={base}", "--", ".", *kept, cwd=tree)
        reverted = run(
            tree, selection, items, out / "reverted",
            "--continue-on-collection-errors",
        )  # fmt: skip
        # Reported before the snapshot is removed, so a failure to remove it can't
        # hide the verdicts.
        caught = report(items, control, reverted, out)
    raise SystemExit(0 if caught else 1)


def report(
    items: list[str],
    control: dict[str, Outcome],
    reverted: dict[str, Outcome],
    out: Path,
) -> bool:
    """Print each test's verdict and the first line of each message, and return
    whether every test was caught."""

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
    return all(v == "caught" for v in verdicts.values())
