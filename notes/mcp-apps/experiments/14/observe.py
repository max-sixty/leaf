#!/usr/bin/env python3
"""Measure the complete Leaf page inside the official MCP Apps host."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from leaf.event_log import read_events
from playwright.sync_api import expect, sync_playwright

HOST = "http://localhost:8080/?tool=leaf_open_page"
HERE = Path(__file__).parent


def app_frame(page):
    expect(page.locator("iframe")).to_have_count(1)
    outer = page.locator("iframe")
    sandbox = page.frame_locator("iframe")
    expect(sandbox.locator("iframe")).to_have_count(1)
    app = sandbox.frame_locator("iframe")
    expect(app.locator("#leaf-page")).to_have_count(1)
    leaf = app.frame_locator("#leaf-page")
    expect(leaf.locator("body")).to_have_attribute("data-lf-presented", "1")
    return outer, app, leaf


def measure(frame):
    return frame.locator("html").evaluate(
        """() => ({
          viewport: {width: innerWidth, height: innerHeight},
          document: {
            client_width: document.documentElement.clientWidth,
            client_height: document.documentElement.clientHeight,
            scroll_width: document.documentElement.scrollWidth,
            scroll_height: document.documentElement.scrollHeight,
          },
          stamps: {
            upgraded: document.body.dataset.lfUpgraded,
            applied: document.body.dataset.lfApplied,
            presented: document.body.dataset.lfPresented,
          },
          headings: [...document.querySelectorAll('h1, h2')].map(
            (node) => node.textContent.trim()
          ),
          widgets: [...document.querySelectorAll('lf-options, lf-compare, lf-gloss')]
            .map((node) => node.localName),
        })"""
    )


def main() -> None:
    page_dir = Path(sys.argv[1]).resolve()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.set_default_timeout(20_000)
        console = []
        page.on(
            "console",
            lambda message: (
                console.append(
                    {
                        "type": message.type,
                        "text": message.text,
                        "location": message.location,
                    }
                )
                if message.type in {"error", "warning"}
                else None
            ),
        )

        page.goto(HOST)
        page.locator("textarea").fill(json.dumps({"page": str(page_dir)}))
        page.get_by_role("button", name="Call Tool").click()
        outer, app, leaf = app_frame(page)
        expect(leaf.get_by_role("heading", name="Where sessions live")).to_be_visible()

        inline = measure(leaf)
        inline_shot = HERE / "results/full-page-inline.png"
        outer.screenshot(path=inline_shot)

        app.get_by_role("button", name="Full screen").click()
        expect(app.get_by_role("button", name="Return inline")).to_be_visible()
        fullscreen = measure(leaf)
        axe = Axe().run(leaf)
        fullscreen_shot = HERE / "results/full-page-fullscreen.png"
        page.screenshot(path=fullscreen_shot, full_page=True)

        option = leaf.locator("#opt-redis").get_by_role("checkbox")
        option.focus()
        option.press("Space")
        expect(leaf.locator("#opt-redis")).to_have_attribute("chosen", "")
        event = read_events(page_dir)[-1]

        print(
            json.dumps(
                {
                    "reference_host": {
                        "repo": "https://github.com/modelcontextprotocol/ext-apps",
                        "commit": "10195ad91851502134930e9b80ec2c04e277a720",
                    },
                    "inline": inline,
                    "fullscreen": fullscreen,
                    "axe": {
                        "violations": axe.violations_count,
                        "snapshot": axe.generate_snapshot(),
                    },
                    "keyboard_choice": {
                        "widget": event["widget"],
                        "action": event["action"],
                        "detail": event["detail"],
                        "seq": event["seq"],
                    },
                    "console": console,
                    "screenshots": {
                        "inline": str(inline_shot),
                        "fullscreen": str(fullscreen_shot),
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
