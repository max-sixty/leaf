#!/usr/bin/env python3
"""Drive the official reference host through append, teardown, and reopen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from leaf.event_log import read_events
from playwright.sync_api import expect, sync_playwright

HOST = "http://localhost:8080/?tool=leaf_open_page"
HERE = Path(__file__).parent


def app_frame(page):
    expect(page.locator("iframe")).to_have_count(1)
    outer = page.locator("iframe")
    outer.evaluate(
        """node => {
          node.style.setProperty('width', '420px', 'important');
          node.style.setProperty('height', '360px', 'important');
        }"""
    )
    sandbox = page.frame_locator("iframe")
    expect(sandbox.locator("iframe")).to_have_count(1)
    sandbox.locator("iframe").evaluate(
        """node => {
          node.style.setProperty('width', '100%', 'important');
          node.style.setProperty('height', '100%', 'important');
        }"""
    )
    frame = sandbox.frame_locator("iframe")
    expect(frame.locator("#sequence")).to_contain_text("event ")
    return outer, frame


def measure(frame):
    return frame.locator("html").evaluate(
        """() => ({
          viewport: {width: innerWidth, height: innerHeight},
          client: {
            width: document.documentElement.clientWidth,
            height: document.documentElement.clientHeight,
          },
          scroll: {
            width: document.documentElement.scrollWidth,
            height: document.documentElement.scrollHeight,
          },
          question: document.querySelector('h1')?.textContent,
          options: [...document.querySelectorAll('[data-option]')].map((node) => node.textContent),
          focused: document.activeElement?.textContent,
        })"""
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("page", type=Path)
    args = parser.parse_args()
    page_dir = args.page.resolve()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 720, "height": 920})
        console = []
        page.on(
            "console",
            lambda message: (
                console.append({"type": message.type, "text": message.text})
                if message.type in {"error", "warning"}
                else None
            ),
        )
        page.goto(HOST)
        page.locator("textarea").fill(json.dumps({"page": str(page_dir)}))
        page.get_by_role("button", name="Call Tool").click()
        outer, frame = app_frame(page)
        expect(
            frame.get_by_role("heading", name="Where should a session live?")
        ).to_be_visible()
        expect(frame.locator("[data-option]")).to_have_count(3)

        option = frame.get_by_role("button", name="Redis, cookie fallback")
        option.focus()
        initial = measure(frame)
        screenshot = HERE / "results/compact-ask-420x360.png"
        outer.screenshot(path=screenshot)

        option.press("Enter")
        expect(
            frame.get_by_role("heading", name="Nothing waiting here")
        ).to_be_visible()
        after_choice = measure(frame)
        event = read_events(page_dir)[-1]

        page.get_by_title("Close").click()
        expect(page.locator("iframe")).to_have_count(0)
        page.get_by_role("button", name="Call Tool").click()
        _, frame = app_frame(page)
        expect(
            frame.get_by_role("heading", name="Nothing waiting here")
        ).to_be_visible()
        reopened = measure(frame)

        result = {
            "reference_host": {
                "repo": "https://github.com/modelcontextprotocol/ext-apps",
                "commit": "10195ad91851502134930e9b80ec2c04e277a720",
            },
            "initial": initial,
            "horizontal_overflow": initial["scroll"]["width"]
            > initial["client"]["width"],
            "keyboard_choice": {
                "widget": event["widget"],
                "action": event["action"],
                "detail": event["detail"],
                "seq": event["seq"],
            },
            "after_choice": after_choice,
            "after_teardown_and_reopen": reopened,
            "console": console,
            "screenshot": str(screenshot),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        browser.close()


if __name__ == "__main__":
    main()
