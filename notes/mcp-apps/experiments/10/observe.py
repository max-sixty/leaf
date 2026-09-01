#!/usr/bin/env python3
"""Measure the reviewed, evidence-bearing compact surface."""

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
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
          const root = document.documentElement;
          const content = document.querySelector('#content');
          return {
            viewport: {width: innerWidth, height: innerHeight},
            document: {
              client_width: root.clientWidth,
              client_height: root.clientHeight,
              scroll_width: root.scrollWidth,
              scroll_height: root.scrollHeight,
            },
            content: {
              client_height: content.clientHeight,
              scroll_height: content.scrollHeight,
            },
            question: document.querySelector('h1')?.textContent,
            labels: [...document.querySelectorAll('.option-label')].map(
              (node) => node.textContent
            ),
            summary_lengths: [...document.querySelectorAll('.option-summary')].map(
              (node) => node.textContent.length
            ),
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
        expect(frame.locator(".option-summary")).to_have_count(3)

        option = frame.get_by_role("button", name="Redis, cookie fallback")
        option.focus()
        initial = measure(frame)
        axe = Axe().run(frame)
        screenshot = HERE / "results/compact-ask-420x360.png"
        outer.screenshot(path=screenshot)

        option.press("Enter")
        expect(
            frame.get_by_role("heading", name="Nothing waiting here")
        ).to_be_visible()
        expect(frame.get_by_role("status")).to_have_text(
            "Recorded Redis, cookie fallback"
        )
        event = read_events(page_dir)[-1]
        status_box = frame.get_by_role("status").bounding_box()

        print(
            json.dumps(
                {
                    "reference_host": {
                        "repo": "https://github.com/modelcontextprotocol/ext-apps",
                        "commit": "10195ad91851502134930e9b80ec2c04e277a720",
                    },
                    "model_visible_tools": model_tools,
                    "initial": initial,
                    "document_horizontal_overflow": (
                        initial["document"]["scroll_width"]
                        > initial["document"]["client_width"]
                    ),
                    "document_vertical_overflow": (
                        initial["document"]["scroll_height"]
                        > initial["document"]["client_height"]
                    ),
                    "content_scrolls": (
                        initial["content"]["scroll_height"]
                        > initial["content"]["client_height"]
                    ),
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
                    "visible_status_box": status_box,
                    "console": console,
                    "screenshot": str(screenshot),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
