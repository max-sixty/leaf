"""Serve a native Playwright trace without opening a desktop browser.

Playwright owns the viewer, trace routes and root redirect. Its `show-trace`
command also opens a browser, with suppression depending on the agent harness.
This command calls only the server primitives and prints their URL. Opening that
URL belongs to the user or the harness's explicit preview handoff.
"""

import os
from pathlib import Path

import click
from playwright._impl._driver import compute_driver_executable


@click.command("trace-server")
@click.argument("trace", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=0, type=click.IntRange(0, 65535), show_default=True)
def trace_server(trace: Path, host: str, port: int) -> None:
    """Serve TRACE and print its viewer URL; leave browser opening to the user.

    Runs in the foreground until interrupted. Port 0 chooses a free port.
    """
    node, driver = compute_driver_executable()
    os.execv(
        node,
        [
            node,
            str(Path(__file__).with_suffix(".cjs")),
            str(Path(driver).parent),
            str(trace.resolve()),
            host,
            str(port),
        ],
    )
