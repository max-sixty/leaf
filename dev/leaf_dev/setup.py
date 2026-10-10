"""Prepare development dependencies from either a background hook or `wt setup`.

Worktrunk owns background execution and its logs; this command owns the setup
pipeline and its success. A machine-wide lock serializes callers because browser
system packages are shared, and concurrent npm ci runs in one checkout would
replace each other's node_modules. A foreground caller waits, then refreshes
against warm caches; there is no separate readiness record to invalidate.
"""

import shlex
import subprocess

import click
from leaf.state import flocked, state_home_path

from leaf_dev import ROOT


def run(*command: str) -> None:
    click.echo(f"$ {shlex.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


@click.command()
def setup() -> None:
    """Install this checkout's assets, browsers and npm dependencies.

    Worktrunk's post-start hook runs this in the background. Invoke `wt setup`
    before testing to wait for other installs and verify the current checkout.
    """
    lock = state_home_path() / "development-setup.lock"
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
                "--only-shell",
            )
            run("uv", "run", "--frozen", "playwright", "install", "chrome")
            run("npm", "ci")
    except subprocess.CalledProcessError as error:
        raise click.ClickException(
            f"{shlex.join(error.cmd)} exited with status {error.returncode}"
        ) from error
