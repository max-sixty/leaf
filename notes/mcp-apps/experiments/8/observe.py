#!/usr/bin/env python3
"""Locate the reference host's generic browser error."""

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from leaf.event_log import read_events
from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).parent


def load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("mcp_apps_experiment_1_observe", HERE.parent / "1/observe.py")
previous = load("mcp_apps_experiment_7_observe", HERE.parent / "7/observe.py")
base.HERE = HERE


def main() -> None:
    page_dir = Path(sys.argv[1]).resolve()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 720, "height": 920})
        page = context.new_page()
        page.set_default_timeout(15_000)
        console = []
        failed_responses = []
        failed_requests = []
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
        context.on(
            "response",
            lambda response: (
                failed_responses.append(
                    {
                        "status": response.status,
                        "url": response.url,
                        "method": response.request.method,
                        "resource_type": response.request.resource_type,
                    }
                )
                if response.status >= 400
                else None
            ),
        )
        context.on(
            "requestfailed",
            lambda request: failed_requests.append(
                {
                    "url": request.url,
                    "method": request.method,
                    "resource_type": request.resource_type,
                    "failure": request.failure,
                }
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
        initial = previous.measure(frame)
        screenshot = HERE / "results/compact-ask-420x360.png"
        outer.screenshot(path=screenshot)
        option.press("Enter")
        expect(
            frame.get_by_role("heading", name="Nothing waiting here")
        ).to_be_visible()
        event = read_events(page_dir)[-1]

        page.get_by_title("Close").click()
        expect(page.locator("iframe")).to_have_count(0)
        page.get_by_role("button", name="Call Tool").click()
        _, frame = base.app_frame(page)
        expect(
            frame.get_by_role("heading", name="Nothing waiting here")
        ).to_be_visible()

        print(
            json.dumps(
                {
                    "reference_host": {
                        "repo": "https://github.com/modelcontextprotocol/ext-apps",
                        "commit": "10195ad91851502134930e9b80ec2c04e277a720",
                    },
                    "model_visible_tools": model_tools,
                    "initial": initial,
                    "keyboard_choice": {
                        "widget": event["widget"],
                        "action": event["action"],
                        "detail": event["detail"],
                        "seq": event["seq"],
                    },
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
