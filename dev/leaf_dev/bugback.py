"""Prove the branch's tests catch the bug its change removes.

    uv run leaf-dev bugback [NODEID...] [--flip PATCH...] [--base REF]

A test earns its place when it fails without the change it pins. This runs the tests
on HEAD as a control, applies a mutation, runs them again, and reports per test and
mutation whether it went red by its own call (`caught`) or stayed green (`blind`).
Every other reading is its own verdict, `leaf_dev.suite`'s outcome for that test:
`error` (its setup or its module's import broke, which is red but not the test's own
assertion), `vanished` (the mutation removed it, as a case parametrized over a
reverted example), `hung`, `teardown-failed`, `skipped`, or `not run`. A test that
fails the control is `control-failed` under every mutation, and every test is `not
built` under a mutation whose rebuild failed or changed no bundle. The messages say
why, each leading with the test line it failed at.

Every mutation is a patch, applied with `git apply`, whose context lines are the
anchor: a patch whose context no longer matches refuses to apply, so a stale anchor
stops the run, before the control, instead of reading as a blind test. The default
mutation is the branch's change: `git diff HEAD BASE`, BASE being the merge base with
main or `--base` for a branch stacked on another, over every path but the tests, the
tooling they import (`tests/`, `dev/`), and the environment's manifests and locks,
which stay HEAD's. Compiled bundles are committed, so the revert takes them back with
their sources. `--flip` names patches instead, one mutation each, named by its file:
edit one guard in the committed tree, `git diff > .tmp/flips/NAME.patch`, and `git
apply -R` it. Flip at the check that decides, since a rule enforced at several layers
stays standing when an earlier layer is flipped, and reads as a blind test.

The tests are the node ids given, or else every test function the branch added or
changed in `tests/**/test_*.py`, found by mapping the diff's lines onto each
function's span. A changed line outside every test function, such as in a
module-level parameter list, a helper, or a shared module like `render_harness.py`,
selects nothing, and each run of them is printed as `not selected`, even where the
same hunk also touches a test, so the tests reading them can be named. Node tests under
`tests/runtime/` are not pytest's and not run. A test walking several routes goes red
on the first route a mutation breaks and never runs the rest, so read which arm the
message's line is, and flip each arm's guard separately to prove it.

Under each mutation the tests are collected again, one module at a time as far as
pytest allows, so a module the mutation breaks costs only its own tests (`error`) and
a test the mutation removed reads `vanished`; the rest run.

It runs in a scratch worktree detached at HEAD, outside the checkout, so the
checkout's working tree is never touched or restored; it therefore refuses a checkout
with uncommitted changes, which the scratch would not carry. The scratch gets its
environment from its lock and `npm ci`. Each mutation is applied to a clean HEAD and
reset afterwards, so a flip never runs on top of another. A mutation touching a
generator's input (`build/`, or the registry and icon `build/vendor.py` reads) runs
both generators, `npm run build:browser` and `build/vendor.py`; one touching `build/`
must then change a bundle to be run. Each run keeps its bytecode under a prefix of
its own, so a size-preserving flip never runs from another run's cache. A stopped
command (SIGTERM, Ctrl-C) stops its runs and removes the scratch before it exits; a
killed one leaves it, and the next run removes it (`sweep`).

Prints a Markdown table, a column per mutation, then each message; output, report
logs, and patches stay under `.tmp/bugback/`. Exits 1 unless every cell is `caught`.
"""

import ast
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from itertools import groupby
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.harness import base_ref
from leaf_dev.suite import Outcome, collect, present, run, stoppable

OUT = ROOT / ".tmp" / "bugback"
# Each run's scratch worktree, outside every checkout, named by the run's pid.
SCRATCH = Path(tempfile.gettempdir()) / "leaf-bugback"
# What the default mutation leaves at HEAD: the tests, the tooling they import, and
# the environment the runs share.
KEPT = (
    "tests", "dev", "pyproject.toml", "uv.lock", "package.json", "package-lock.json",
)  # fmt: skip
TESTS = ":(glob)tests/**/*.py"
# What the generators read (build/AGENTS.md): their own sources under `build/`, and
# the registry and icon `build/vendor.py` reads from the assets.
GENERATOR_INPUTS = (
    "build", "skills/leaf/assets/registry.json", "skills/leaf/assets/icon.svg",
)  # fmt: skip
# What they ship; `build/browser/generated` holds only source maps, which a comment
# changes.
GENERATED = (
    "skills/leaf/assets/vendor", ":(glob)skills/leaf/packages/*/vendor/**",
    "skills/leaf/mcp-app",
)  # fmt: skip
GENERATORS = (("npm", "run", "build:browser"), ("uv", "run", "--frozen", "build/vendor.py"))  # fmt: skip


def git(*args: str, cwd: Path = ROOT, input: bytes | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", cwd, *args], input=input, capture_output=True, check=False
    )
    if proc.returncode:
        raise click.ClickException(
            f"git {' '.join(args)}: {proc.stderr.decode().strip()}"
        )
    return proc.stdout.decode()


def changed_tests(base: str) -> tuple[tuple[str, ...], list[str]]:
    """The node ids of the test functions the diff from `base` to HEAD adds or
    changes, decorators included, and each run of changed lines under `tests/`
    outside every test function, as `path:first-last`."""
    hunks: dict[str, list[range]] = {}
    diff = git("diff", "--unified=0", "--no-renames", base, "HEAD", "--", TESTS)
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/")
            # A deleted file's lines name nothing that still runs.
            spans = hunks.setdefault(path, []) if path != "/dev/null" else []
        elif match := re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", line):
            # A pure deletion names the line before it, inside the same function.
            start, count = int(match[1]), int(match[2] or 1)
            spans.append(range(start, start + max(count, 1)))
    ids, unselected = [], []
    for path, spans in hunks.items():
        tests = []
        if Path(path).name.startswith("test_"):
            tree = ast.parse((ROOT / path).read_text())
            for node, prefix in functions(tree.body, path):
                first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
                tests.append((f"{prefix}::{node.name}", range(first, node.end_lineno + 1)))  # fmt: skip
        covered = {line for _, body in tests for line in body}
        for span in spans:
            hit = [name for name, body in tests if set(span) & set(body)]
            ids.extend(name for name in hit if name not in ids)
            outside = [line for line in span if line not in covered]
            # Consecutive lines share `line - index`, so each group is one run.
            for _, stretch in groupby(enumerate(outside), lambda p: p[1] - p[0]):
                lines = [line for _, line in stretch]
                unselected.append(f"{path}:{lines[0]}-{lines[-1]}")
    return tuple(ids), unselected


def functions(body: list, prefix: str):
    """Each test function in a module or `Test` class body, with its node id's
    prefix."""
    for node in body:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith("test"):
            yield node, prefix
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            yield from functions(node.body, f"{prefix}::{node.name}")


def branch_patch(base: str) -> bytes:
    """The patch that takes HEAD back to `base` everywhere but `KEPT`."""
    kept = [f":(exclude){path}" for path in KEPT]
    patch = git("diff", "--binary", "--no-renames", "HEAD", base, "--", ".", *kept)
    if not patch:
        raise click.ClickException(
            f"the branch changes nothing outside {', '.join(KEPT)} since {base[:12]}"
        )
    return patch.encode()


def mutate(scratch: Path, name: str, patch: bytes, out: Path) -> str | None:
    """Apply one mutation to the clean scratch, and regenerate the bundles where it
    touches a generator's input; return why no run would see it, if none would."""
    git("apply", "--binary", "-", cwd=scratch, input=patch)
    if not git("status", "--porcelain", "--", *GENERATOR_INPUTS, cwd=scratch):
        return None
    compiled = git("status", "--porcelain", "--", "build", cwd=scratch)
    log = out / f"{name}.build.log"
    with log.open("w") as stream:
        for generator in GENERATORS:
            status = subprocess.run(
                generator,
                cwd=scratch,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode
            if status:
                return f"{' '.join(generator)} exited {status}; see {log}"
    if compiled and not git("status", "--porcelain", "--", *GENERATED, cwd=scratch):
        return "the rebuild left every bundle as HEAD has it"
    return None


@click.command()
@click.argument("selection", nargs=-1)
@click.option(
    "--flip",
    "flips",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="A patch to apply as one mutation; repeat for more. "
    "Without one, the mutation is the branch's own change.",
)
@click.option(
    "--base",
    help="Where the branch starts, for a branch stacked on another; "
    "the merge base with main by default.",
)
def bugback(
    selection: tuple[str, ...], flips: tuple[Path, ...], base: str | None
) -> None:
    """Prove tests go red with the branch's change reverted.

    Runs SELECTION, pytest node ids, on HEAD and again with the change since
    --base reverted, and reports per test whether it was caught. Without node ids,
    runs the test functions the branch added or changed. --flip replaces the
    revert with patches, one mutation each. Runs in a scratch worktree at HEAD,
    so commit first. Exits 1 unless every test is caught by every mutation.
    """
    if dirty := git("status", "--porcelain"):
        raise click.ClickException(
            f"bugback runs HEAD in a scratch worktree; commit first:\n{dirty}"
        )
    base = git("rev-parse", "--verify", f"{base_ref(base)}^{{commit}}").strip()
    if not selection:
        selection, unselected = changed_tests(base)
        for hunk in unselected:
            click.echo(f"not selected: {hunk}")
    if not selection:
        raise click.ClickException(
            f"the branch changes no test function since {base[:12]}; name node ids"
        )
    mutations = (
        {flip.stem: flip.read_bytes() for flip in flips}
        if flips
        else {"revert": branch_patch(base)}
    )
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-")
    out = Path(tempfile.mkdtemp(prefix=stamp, dir=OUT))
    for name, patch in mutations.items():
        (out / f"{name}.patch").write_bytes(patch)
    sweep()
    scratch = Path(tempfile.mkdtemp(prefix=f"{os.getpid()}-", dir=SCRATCH)) / "checkout"
    with stoppable():
        try:
            git("worktree", "add", "--detach", str(scratch), "HEAD")
            control, runs, items = trial(scratch, selection, mutations, out)
        finally:
            # Removing the directory first leaves nothing for a failing `worktree
            # remove` to report over the error that got here; prune drops the entry.
            shutil.rmtree(scratch.parent, ignore_errors=True)
            subprocess.run(["git", "-C", ROOT, "worktree", "prune"], check=False)
    report(control, runs, items, out)


def sweep() -> None:
    """Remove the scratch of every earlier run whose process is gone.

    A command stopped by SIGKILL never reaches its own cleanup, and `TaskStop`
    sends SIGKILL about a second and a half after SIGTERM, too soon to remove a
    checkout holding an environment and `node_modules`. Each scratch is named by
    its run's pid, so the next run removes what a killed one left."""
    SCRATCH.mkdir(exist_ok=True)
    for stale in SCRATCH.iterdir():
        pid = stale.name.partition("-")[0]
        if not pid.isdigit():
            continue
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            shutil.rmtree(stale, ignore_errors=True)
        except PermissionError:
            pass
    subprocess.run(["git", "-C", ROOT, "worktree", "prune"], check=False)


def trial(
    scratch: Path, selection: tuple[str, ...], mutations: dict[str, bytes], out: Path
):
    """The control and each mutation's outcomes, in the scratch at HEAD."""
    for name, patch in mutations.items():
        git("apply", "--check", "--binary", "-", cwd=scratch, input=patch)
    command(scratch, out / "npm-ci.log", "npm", "ci")
    items = collect(scratch, selection, out / "collect.log")

    def phase(name: str, targets: list[str]) -> dict[str, Outcome]:
        prefix = {"PYTHONPYCACHEPREFIX": str(out / "pycache" / name)}
        return run(scratch, tuple(targets), targets, out / name, env=prefix)

    control = phase("control", items)
    if not any(o.result == "passed" for o in control.values()):
        failures = "\n".join(
            f"- `{i}`: {first_line(o.message)}" for i, o in control.items()
        )
        raise click.ClickException(f"no test passes on HEAD:\n{failures}")
    runs = {}
    for name, patch in mutations.items():
        if unbuilt := mutate(scratch, name, patch, out):
            runs[name] = {item: Outcome("not built", unbuilt) for item in items}
        else:
            kept, lost = present(scratch, items, out / f"{name}.collect")
            runs[name] = {**lost, **(phase(name, kept) if kept else {})}
        git("reset", "--hard", "--quiet", "HEAD", cwd=scratch)
        git("clean", "-fd", "--quiet", cwd=scratch)
    return control, runs, items


def report(control, runs, items, out: Path) -> None:
    def verdict(item: str, name: str) -> str:
        if control[item].result != "passed":
            return "control-failed"
        result = runs[name][item].result
        return {"failed": "caught", "passed": "blind"}.get(result, result)

    click.echo(f"| test | control | {' | '.join(runs)} |")
    click.echo(f"|---|---|{'---|' * len(runs)}")
    cells = {(i, n): verdict(i, n) for i in items for n in runs}
    for item in items:
        row = " | ".join(cells[item, n] for n in runs)
        click.echo(f"| `{item}` | {control[item].result} | {row} |")
    click.echo("")
    for item in items:
        if control[item].message:
            click.echo(f"- control, `{item}`: {first_line(control[item].message)}")
        for name, outcomes in runs.items():
            if outcomes[item].message:
                click.echo(f"- {name}, `{item}`: {first_line(outcomes[item].message)}")
    click.echo(f"\nlogs: {out.relative_to(ROOT)}/")
    raise SystemExit(0 if all(v == "caught" for v in cells.values()) else 1)


def first_line(message: str) -> str:
    return message.strip().partition("\n")[0]


def command(cwd: Path, log: Path, *args: str) -> None:
    """Run a setup command in the scratch, its output to `log`, and stop if it
    fails: a run on a half-built scratch would read as the tests' result."""
    with log.open("w") as stream:
        status = subprocess.run(
            args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, check=False
        ).returncode
    if status:
        raise click.ClickException(
            f"{' '.join(args)} exited {status}:\n{log.read_text()[-2000:]}"
        )
