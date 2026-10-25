"""Prepare development dependencies from either a background hook or `wt setup`.

Worktrunk owns background execution and its logs; this command owns the setup
pipeline and its success. A machine-wide lock serializes callers because browser
system packages are shared, and concurrent installs in one checkout would replace
each other's node_modules. A foreground caller waits, then refreshes against warm
caches; there is no separate readiness record to invalidate.
"""

import os
import shlex
import subprocess
import sys

import click

from leaf.state import flocked, state_home
from leaf_dev import ROOT


def run(*command: str) -> None:
    click.echo(f"$ {shlex.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


@click.command()
def setup() -> None:
    """Install this checkout's assets, browsers and Node dependencies.

    Worktrunk's post-start hook runs this in the background. Invoke `wt setup`
    before testing to wait for other installs and verify the current checkout.
    """
    lock = state_home() / "development-setup.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with flocked(lock):
            run("uv", "run", "--frozen", "leaf-dev", "fetch-assets")
            run(
                "uv",
                "run",
                "--frozen",
                "playwright",
                "install",
                "--with-deps",
                "chromium",
                "webkit",
                "firefox",
            )
            run("uv", "run", "--frozen", "playwright", "install", "chrome")
            if sys.platform == "linux":
                # Playwright installs browser libraries, but not the complete
                # DejaVu faces the suite's fixed fontconfig requires.
                privilege = () if os.geteuid() == 0 else ("sudo",)
                run(*privilege, "apt-get", "install", "-y", "fonts-dejavu")
            run("pnpm", "install", "--frozen-lockfile")
    except subprocess.CalledProcessError as error:
        raise click.ClickException(
            f"{shlex.join(error.cmd)} exited with status {error.returncode}"
        ) from error
