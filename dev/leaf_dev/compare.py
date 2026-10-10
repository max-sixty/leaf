"""Two live previews, using the canonical arm builder and preview lifecycle.

The baseline is an immutable full source arm; the candidate watches this checkout.
Both read the candidate's authored source unless --authored selects each arm's own
copy. Each invocation owns fresh preview slots. User previews keep their baseline
under .tmp/compare after startup because detached watchers still need its files.
Foreground previews end together.
"""

import signal
import subprocess
import time
from pathlib import Path
from threading import Thread

import click
from leaf.harness import session_harness

from leaf_dev import ROOT
from leaf_dev.arms import base_ref, build_arm, run_directory
from leaf_dev.preview import authored_source


@click.command()
@click.argument("example", required=False)
@click.option(
    "--source", type=click.Path(path_type=Path), help="Shared authored HTML source."
)
@click.option("--base", help="Baseline ref; defaults to the merge base with main.")
@click.option("--authored", is_flag=True, help="Use each arm's own authored source.")
@click.option("--user", is_flag=True, help="Receive user feedback from both previews.")
def compare(example, source, base, authored, user):
    """Serve baseline and candidate previews together, including live source edits."""
    if example and source:
        raise click.UsageError("choose an example name or --source, not both")
    source = authored_source(example, source)
    if authored and not source.is_relative_to(ROOT):
        raise click.UsageError("--authored needs a source inside this checkout")
    directory = run_directory(ROOT / ".tmp" / "compare")
    baseline = directory / "baseline"
    build_arm(base_ref(base), baseline, paths=(".",))
    sources = {
        "baseline": baseline / source.relative_to(ROOT) if authored else source,
        "candidate": source,
    }
    prefix = f"{source.stem}-{directory.name}"
    harness = session_harness() if user else None
    detached = bool(harness and harness.lifetime() == {"chat": True})
    processes = []
    readers = []

    def output(name, process):
        for line in process.stdout:
            click.echo(f"{name}: {line.rstrip()}")

    def terminated(_signal, _frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, terminated)
    try:
        for name, runtime in (("baseline", baseline), ("candidate", ROOT)):
            process = subprocess.Popen(
                [
                    "uv",
                    "run",
                    "--project",
                    str(ROOT),
                    "leaf-dev",
                    "preview",
                    "--source",
                    str(sources[name]),
                    "--runtime",
                    str(runtime),
                    "--slot",
                    f"{prefix}-{name}",
                    *(["--user"] if user else []),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            processes.append(process)
            reader = Thread(target=output, args=(name, process))
            reader.start()
            readers.append(reader)
        # A failed arm ends the pair; successful detached startup may exit while
        # the other arm is still preparing. Polling here never inspects page state.
        while processes:
            for process in tuple(processes):
                code = process.poll()
                if code is not None:
                    if code:
                        raise click.ClickException(f"preview exited {code}")
                    if not detached:
                        return
                    processes.remove(process)
            if processes:
                time.sleep(0.1)
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    finally:
        signal.signal(signal.SIGTERM, previous)
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait()
        for reader in readers:
            reader.join()


if __name__ == "__main__":
    compare()
