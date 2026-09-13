#!/usr/bin/env python3
"""Measure one Leaf page, comment, requested edit, publication, and reply journey."""

import json

import click
from leaf.render_gate.browser import launch_browser
from playwright.sync_api import sync_playwright
from verify_site import local_adapter, target_origin, verify_agent_turn


def measure(
    origin: str, release: str | None = None, *, direct_agent: bool = False
) -> dict:
    """Run the shared browser journey against explicit endpoint inputs."""
    with sync_playwright() as playwright:
        browser, browser_name = launch_browser(playwright)
        try:
            result = verify_agent_turn(
                browser, release, origin=origin, direct_agent=direct_agent, report=False
            )
        finally:
            browser.close()
    return {"browser": browser_name, **result}


@click.command()
@click.argument("target", metavar="local|ORIGIN")
def main(target: str) -> None:
    """Measure local Leaf or a deployed HTTP origin, emitting one JSON sample."""
    if target == "local":
        with local_adapter() as (origin, release):
            result = measure(origin, release, direct_agent=True)
    else:
        result = measure(target_origin(target))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
