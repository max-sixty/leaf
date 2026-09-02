"""Observe the actual MCP resource in the upstream reference host's sandbox."""

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from leaf.event_log import read_events
from playwright.sync_api import expect, sync_playwright

RESULTS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "results"


def main() -> None:
    page_dir = Path(sys.argv[1])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.set_default_timeout(30_000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: (
                errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.goto("http://localhost:8080/?tool=leaf_direct_present")
        page.wait_for_function(
            "() => document.querySelectorAll('select')[1]?.value === 'leaf_direct_present'"
        )
        page.locator("textarea").fill("{}")
        page.get_by_role("button", name="Call Tool").click()
        app = page.frame_locator("iframe").frame_locator("iframe")
        expect(app.locator("body")).to_have_attribute("data-lf-presented", "1")
        expect(app.locator("iframe")).to_have_count(0)
        expect(app.get_by_role("heading", name="Where sessions live")).to_be_visible()
        expect(app.locator(".lf-banner")).to_be_visible()
        page.locator("iframe").screenshot(path=RESULTS / "direct-leaf.png")

        choice = app.locator("#opt-redis").get_by_role("checkbox")
        choice.focus()
        choice.press("Space")
        expect(app.locator("#opt-redis")).to_have_attribute("chosen", "")
        page.wait_for_function("() => true")
        # The canonical outbox releases only after the accepted projection is applied.
        expect(app.locator("body")).to_have_attribute("data-lf-applied", "1")
        action = read_events(page_dir)[-1]
        assert action["kind"] == "action" and action["widget"] == "session-options"

        paragraph = app.locator("#decision-lede")
        paragraph.evaluate("""element => {
            const range = document.createRange();
            range.selectNodeContents(element);
            const selection = getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            element.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        }""")
        expect(app.locator(".lf-fab-input")).to_be_visible()
        app.locator(".lf-fab-input").fill(
            "Comment delivered directly through MCP tools."
        )
        app.locator(".lf-fab-input").press("Enter")
        expect(
            app.get_by_text(
                "Comment delivered directly through MCP tools.", exact=True
            ).first
        ).to_be_visible()
        comment = read_events(page_dir)[-1]
        assert comment["kind"] == "comment" and comment["anchor"]["quote"]
        page.locator("iframe").screenshot(path=RESULTS / "direct-comment.png")

        app.get_by_role("button", name="Test Codex follow-up").click()
        expect(
            app.get_by_role("status").filter(has_text="ui/message accepted")
        ).to_be_visible()
        sandbox_url = page.frames[1].url
        csp = json.loads(parse_qs(urlsplit(sandbox_url).query)["csp"][0])
        assert not csp.get("connectDomains") and not csp.get("frameDomains")
        requests = page.frames[-1].evaluate(
            "() => performance.getEntriesByType('resource').map(entry => entry.name)"
        )
        assert not requests, requests
        errors = [
            error
            for error in errors
            if "favicon.ico" not in error and "404" not in error
        ]
        assert not errors, errors
        print(
            json.dumps(
                {
                    "presented": True,
                    "leafChildFrames": 0,
                    "csp": csp,
                    "resourceRequests": requests,
                    "action": action,
                    "comment": comment,
                    "uiMessageAccepted": True,
                    "idleCodexWakeTested": False,
                    "errors": errors,
                },
                indent=2,
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
