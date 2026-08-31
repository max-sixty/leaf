#!/usr/bin/env python3
"""Measure a complete Leaf page after tool controls have hydrated."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
import sys
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from leaf.event_log import read_events
from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).parent
source = HERE.parent / "15/observe.py"
spec = spec_from_file_location("mcp_apps_experiment_15_observe", source)
base = module_from_spec(spec)
spec.loader.exec_module(base)


def main(
    tool_timeout: int = 20_000,
    wait_for_options: bool = True,
    use_dom_gate: bool = False,
    stable_panels: bool = False,
    body_call_record: bool = False,
    tolerate_mode_control: bool = False,
    exercise_comments_versions: bool = False,
) -> None:
    page_dir = Path(sys.argv[1]).resolve()
    result = {
        "reference_host": {
            "repo": "https://github.com/modelcontextprotocol/ext-apps",
            "commit": "10195ad91851502134930e9b80ec2c04e277a720",
        }
    }
    failed = False

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

        try:
            page.goto(base.HOST)
            if use_dom_gate:
                page.wait_for_function(
                    """() => document.querySelectorAll('select')[1]?.value
                      === 'leaf_open_page'""",
                    timeout=tool_timeout,
                )
                tool_select = page.locator("select").nth(1)
            else:
                tool_select = page.get_by_label("Tool", exact=True)
                if wait_for_options:
                    expect(tool_select.locator("option")).to_have_count(
                        2, timeout=tool_timeout
                    )
                expect(tool_select).to_have_value(
                    "leaf_open_page", timeout=tool_timeout
                )
            tool_input = (
                page.locator("textarea")
                if use_dom_gate
                else page.get_by_label("Input", exact=True)
            )
            expect(tool_input).to_have_value("{}")

            payload = json.dumps({"page": str(page_dir)})
            tool_input.fill(payload)
            expect(tool_input).to_have_value(payload)
            result["invocation"] = {
                "selected_tool": tool_select.input_value(),
                "initial_input": "{}",
                "submitted_input": tool_input.input_value(),
            }

            page.get_by_role("button", name="Call Tool").click()
            if body_call_record:
                page.wait_for_function(
                    "path => document.body.innerText.includes(path)",
                    arg=str(page_dir),
                )
                result["invocation"]["rendered_input"] = str(page_dir)
            elif stable_panels:
                input_panel = page.locator('[title="Click to expand"]').filter(
                    has_text="Tool Input"
                ).last
                expect(input_panel).to_be_visible()
                input_panel.click()
                rendered_input = input_panel.locator("pre")
            else:
                input_panel = page.get_by_text("Tool Input", exact=True).last
                expect(input_panel).to_be_visible()
                input_panel.click()
                rendered_input = input_panel.locator("../..").locator("pre")
            if not body_call_record:
                expect(rendered_input).to_contain_text(str(page_dir))
                result["invocation"]["rendered_input"] = rendered_input.inner_text()

            outer, app, leaf = base.app_frame(page)
            expect(leaf.get_by_role("heading", name="Where sessions live")).to_be_visible()

            inline = base.measure(leaf)
            result["inline"] = inline
            inline_shot = HERE / "results/full-page-inline.png"
            outer.screenshot(path=inline_shot)

            app.get_by_role("button", name="Full screen").click()
            if tolerate_mode_control:
                page.wait_for_timeout(500)
                return_control = app.get_by_role("button", name="Return inline")
                mode_control = {"return_visible": return_control.is_visible()}
            else:
                expect(app.get_by_role("button", name="Return inline")).to_be_visible()
                mode_control = {"hidden": False, "text": "Return inline"}
            fullscreen = base.measure(leaf)
            result["fullscreen"] = fullscreen
            result["mode_control"] = mode_control
            axe = Axe().run(page.frames[-1])
            fullscreen_shot = HERE / "results/full-page-fullscreen.png"
            page.screenshot(path=fullscreen_shot, full_page=True)

            option = leaf.locator("#opt-redis").get_by_role("checkbox")
            option.focus()
            option.press("Space")
            expect(leaf.locator("#opt-redis")).to_have_attribute("chosen", "")
            event = read_events(page_dir)[-1]

            complete_interface = None
            if exercise_comments_versions:
                lede = leaf.locator("#decision-lede")
                lede.evaluate(
                    """node => {
                      const phrase = 'session state homeless: today it rides the app';
                      const text = node.firstChild;
                      const start = text.data.indexOf(phrase);
                      if (start < 0) throw new Error('comment phrase not found');
                      const range = document.createRange();
                      range.setStart(text, start);
                      range.setEnd(text, start + phrase.length);
                      const selection = getSelection();
                      selection.removeAllRanges();
                      selection.addRange(range);
                      document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                    }"""
                )
                comment_button = leaf.locator(".lf-fab")
                expect(comment_button).to_be_visible()
                comment_button.click()
                composer = leaf.locator(".lf-composer")
                expect(composer).to_be_visible()
                composer.locator("textarea").fill("Keep this rationale across versions.")
                composer.get_by_role("button", name="Comment", exact=True).click()
                leaf.locator("body").wait_for(
                    state="visible"
                )
                expect(leaf.locator(".lf-thread .lf-quote").first).to_contain_text(
                    "session state homeless: today it rides the app"
                )
                comment = next(
                    item
                    for item in reversed(read_events(page_dir))
                    if item["kind"] == "comment"
                )

                version = leaf.locator(".lf-version")
                expect(version).to_contain_text("v2")
                version.click()
                leaf.locator('.lf-version-row[data-lf-version="1"]').click()
                expect(lede).to_contain_text(
                    "The monolith split leaves session state homeless"
                )
                expect(leaf.locator(".lf-thread .lf-quote").first).to_contain_text(
                    "session state homeless: today it rides the app"
                )
                marked_v1 = leaf.locator("body").evaluate(
                    "() => CSS.highlights.get('lf-mark')?.size ?? 0"
                )
                v1_url = page.frames[-1].url

                leaf.locator(".lf-version").click()
                leaf.locator('.lf-version-row[data-lf-version="2"]').click()
                expect(lede).to_contain_text(
                    "The monolith extraction leaves session state homeless"
                )
                expect(leaf.locator(".lf-thread .lf-quote").first).to_contain_text(
                    "session state homeless: today it rides the app"
                )
                marked_v2 = leaf.locator("body").evaluate(
                    "() => CSS.highlights.get('lf-mark')?.size ?? 0"
                )
                v2_url = page.frames[-1].url
                complete_interface = {
                    "comment": {
                        "kind": comment["kind"],
                        "text": comment["text"],
                        "revision": comment["revision"],
                        "anchor": comment["anchor"],
                        "seq": comment["seq"],
                    },
                    "version_travel": {
                        "v1_url": v1_url,
                        "v2_url": v2_url,
                        "marked_v1": marked_v1,
                        "marked_v2": marked_v2,
                    },
                }

            result.update(
                {
                    "axe": {
                        "violations": axe.violations_count,
                        "snapshot": axe.generate_snapshot(),
                        "report": axe.generate_report(),
                    },
                    "keyboard_choice": {
                        "widget": event["widget"],
                        "action": event["action"],
                        "detail": event["detail"],
                        "seq": event["seq"],
                    },
                    "complete_interface": complete_interface,
                    "screenshots": {
                        "inline": str(inline_shot),
                        "fullscreen": str(fullscreen_shot),
                    },
                }
            )
        except Exception as error:  # Preserve host evidence before failing the run.
            failed = True
            failure_shot = HERE / "results/failure.png"
            page.screenshot(path=failure_shot, full_page=True)
            result["failure"] = {
                "error": repr(error),
                "url": page.url,
                "body": page.locator("body").inner_text(),
                "screenshot": str(failure_shot),
            }
        finally:
            result["console"] = console
            print(json.dumps(result, indent=2, ensure_ascii=False))
            browser.close()

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
