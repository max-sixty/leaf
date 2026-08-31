#!/usr/bin/env python3
"""Repeat the successful reference-host run with bounded diagnostics."""

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from leaf.event_log import read_events
from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).parent
source = HERE.parent / "1/observe.py"
spec = spec_from_file_location("mcp_apps_experiment_1_observe", source)
base = module_from_spec(spec)
spec.loader.exec_module(base)
base.HERE = HERE


def measure(frame):
    return frame.locator("html").evaluate(
        """() => {
          const focused = document.activeElement;
          return {
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
            focused: focused ? {
              tag: focused.localName,
              id: focused.id || null,
              option: focused.dataset?.option || null,
            } : null,
          };
        }"""
    )


def main() -> None:
    page_dir = Path(sys.argv[1]).resolve()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 720, "height": 920})
        page.set_default_timeout(15_000)
        console = []
        failed_responses = []
        failed_requests = []
        page.on(
            "console",
            lambda message: (
                console.append({"type": message.type, "text": message.text})
                if message.type in {"error", "warning"}
                else None
            ),
        )
        page.on(
            "response",
            lambda response: (
                failed_responses.append(
                    {"status": response.status, "url": response.url}
                )
                if response.status >= 400
                else None
            ),
        )
        page.on(
            "requestfailed",
            lambda request: failed_requests.append(
                {"url": request.url, "failure": request.failure}
            ),
        )
        page.goto(base.HOST)
        tool_select = page.locator("select").nth(1)
        expect(tool_select).to_have_value("leaf_open_page")
        model_tools = tool_select.locator("option").all_text_contents()
        tool_input = page.locator("textarea")
        expect(tool_input).to_have_value("{}")
        tool_input.fill(json.dumps({"page": str(page_dir)}))
        page.get_by_role("button", name="Call Tool").click()
        outer, frame = base.app_frame(page)
        expect(
            frame.get_by_role("heading", name="Where should a session live?")
        ).to_be_visible()

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
        _, frame = base.app_frame(page)
        expect(
            frame.get_by_role("heading", name="Nothing waiting here")
        ).to_be_visible()
        reopened = measure(frame)

        print(
            json.dumps(
                {
                    "reference_host": {
                        "repo": "https://github.com/modelcontextprotocol/ext-apps",
                        "commit": "10195ad91851502134930e9b80ec2c04e277a720",
                    },
                    "model_visible_tools": model_tools,
                    "initial": initial,
                    "horizontal_overflow": initial["scroll"]["width"]
                    > initial["client"]["width"],
                    "vertical_overflow": initial["scroll"]["height"]
                    > initial["client"]["height"],
                    "keyboard_choice": {
                        "widget": event["widget"],
                        "action": event["action"],
                        "detail": event["detail"],
                        "seq": event["seq"],
                    },
                    "after_choice": after_choice,
                    "after_teardown_and_reopen": reopened,
                    "console": console,
                    "failed_responses": failed_responses,
                    "failed_requests": failed_requests,
                    "screenshot": str(screenshot),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
