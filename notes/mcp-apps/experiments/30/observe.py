#!/usr/bin/env python3
"""Exercise one exact CSP origin and its canonical Leaf capability path."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from axe_playwright_python.sync_playwright import Axe
from leaf.event_log import read_events
from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).parent
HOST = "http://localhost:8080/?tool=leaf_present"


def main() -> None:
    page_dir = Path(sys.argv[1]).resolve()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.set_default_timeout(60_000)
        console = []
        page.on(
            "console",
            lambda message: (
                console.append(
                    {
                        "type": message.type,
                        "text": message.text,
                        "url": message.location.get("url"),
                    }
                )
                if message.type in {"error", "warning"}
                else None
            ),
        )

        page.goto(HOST)
        page.wait_for_function(
            "() => document.querySelectorAll('select')[1]?.value === 'leaf_present'"
        )
        page.locator("textarea").fill(json.dumps({"page": str(page_dir)}))
        page.get_by_role("button", name="Call Tool").click()

        expect(page.locator("iframe")).to_have_count(1)
        sandbox = page.frame_locator("iframe")
        expect(sandbox.locator("iframe")).to_have_count(1)
        app = sandbox.frame_locator("iframe")
        expect(app.locator("#leaf-page")).to_have_count(1)
        leaf = app.frame_locator("#leaf-page")
        expect(leaf.locator("body")).to_have_attribute("data-lf-presented", "1")
        expect(leaf.get_by_role("heading", name="Where sessions live")).to_be_visible()

        sandbox_url = page.frames[1].url
        csp = json.loads(parse_qs(urlsplit(sandbox_url).query)["csp"][0])
        inner_url = page.frames[-1].url
        inner = urlsplit(inner_url)
        exact_origin = f"{inner.scheme}://{inner.netloc}"
        assert csp["frameDomains"] == [exact_origin]
        assert inner.path.startswith("/p/") and inner.path.endswith("/")
        assert not inner.query

        option = leaf.locator("#opt-redis").get_by_role("checkbox")
        option.focus()
        option.press("Space")
        expect(leaf.locator("#opt-redis")).to_have_attribute("chosen", "")
        action = read_events(page_dir)[-1]

        inline_shot = HERE / "results/exact-origin-inline.png"
        page.locator("iframe").screenshot(path=inline_shot)
        app.get_by_role("button", name="Full screen").click()
        page.wait_for_timeout(500)
        fullscreen_shot = HERE / "results/exact-origin-fullscreen.png"
        page.screenshot(path=fullscreen_shot, full_page=True)
        axe = Axe().run(page.frames[-1])

        leaf_console = [
            message
            for message in console
            if not (
                message["url"] == "http://localhost:8080/favicon.ico"
                and "404" in message["text"]
            )
        ]
        assert leaf_console == []
        result = {
            "reference_host": {
                "repo": "https://github.com/modelcontextprotocol/ext-apps",
                "commit": "10195ad91851502134930e9b80ec2c04e277a720",
            },
            "tool": page.locator("select").nth(1).input_value(),
            "resource_csp": csp,
            "inner_url": inner_url,
            "queryless_capability_path": True,
            "presented": leaf.locator("body").get_attribute("data-lf-presented"),
            "keyboard_choice": {
                "widget": action["widget"],
                "action": action["action"],
                "detail": action["detail"],
                "seq": action["seq"],
            },
            "mode_control": {
                "return_inline_visible": app.get_by_role(
                    "button", name="Return inline"
                ).is_visible()
            },
            "axe": {
                "violations": axe.violations_count,
                "snapshot": axe.generate_snapshot(),
            },
            "console": console,
            "leaf_console": leaf_console,
            "screenshots": {
                "inline": str(inline_shot),
                "fullscreen": str(fullscreen_shot),
            },
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        browser.close()


if __name__ == "__main__":
    main()
