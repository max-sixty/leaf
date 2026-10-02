"""The message delivery journey used by browser checks and visual snapshots.

The server, page and browser belong to the caller. This driver opens a real thread,
types through its field and sends with Return. It holds the POST before admission,
refuses it, resends the restored draft, and finally admits it. Checkpoints run while
those states are held, so a screenshot and an assertion observe the same journey.

First appearance is separate evidence: a MutationObserver records the message's
computed opacity at insertion. A screenshot taken after the browser driver returns
cannot prove that instant, even when the request is still held.
"""

from collections.abc import Callable
from dataclasses import dataclass

from leaf.render_checks import rendered, wait_for_probe
from playwright.sync_api import Locator, Page, expect

WORDS = "Keep the reader's words in the thread while this reply is being sent."
NEXT_WORDS = "Keep the next draft separate from the reply still being sent."
STAGES = (
    "drafted",
    "pending",
    "refused",
    "retry-pending",
    "newer-draft-pending",
    "accepted",
)
Checkpoint = Callable[[str, Page, dict], None]


def watch_message_arrival(root: Locator, selector: str) -> None:
    """Record delivery paint on insertion within a document or declared shadow root."""
    root.evaluate(
        """(node, selector) => {
          const root = node.shadowRoot ?? node;
          window.__messageArrival = null;
          const observer = new MutationObserver(() => {
            const message = root.querySelector(
              `${selector}[data-attempt][aria-busy="true"]`
            );
            if (!message) return;
            window.__messageArrival = Number(getComputedStyle(message).opacity);
            observer.disconnect();
          });
          observer.observe(root, {childList: true, subtree: true});
        }""",
        selector,
    )


@dataclass(frozen=True)
class ThreadSurface:
    """The one locator boundary for a thread's different presentation owners."""

    field: Locator
    messages: Locator
    arrival_root: Locator
    arrival_selector: str
    region: Locator


def open_surface(page: Page, surface: str) -> ThreadSurface:
    """Open the existing last thread, or the panel's page-comment field."""
    if surface in {"panel", "general"}:
        page.locator(".lf-threads-toggle").click()
        expect(page.locator(".lf-thread-panel")).to_be_visible()
        wait_for_probe(page, "pageSettled")
        if surface == "general":
            return ThreadSurface(
                page.locator(".lf-general leaf-text"),
                page.locator(".lf-threads .lf-msg.user"),
                page.locator("body"),
                ".lf-threads .lf-msg",
                page.locator(".lf-thread-panel"),
            )
        thread = page.locator(".lf-threads > .lf-thread").last
        if thread.get_attribute("open") is None:
            thread.locator(".lf-thread-summary").click()
        return ThreadSurface(
            thread.locator("leaf-text"),
            thread.locator(".lf-msg"),
            page.locator("body"),
            ".lf-threads .lf-msg",
            thread,
        )
    if surface == "margin":
        page.locator(".lf-margin-marker").first.click()
        thread = page.locator(".lf-margin-preview .lf-page-thread")
        expect(thread).to_be_visible()
        return ThreadSurface(
            thread.locator("leaf-text"),
            thread.locator(".lf-msg"),
            page.locator("body"),
            ".lf-margin-preview .lf-msg",
            page.locator(".lf-margin-preview"),
        )
    if surface == "inline":
        # The diff's own datum capture creates its thread through the same route a
        # reader uses. No synthetic anchor or injected shadow markup seats it.
        diff = page.locator("#journey-patch")
        diff.scroll_into_view_if_needed()
        diff.locator("[data-lf-datum][data-line-type=change-addition]").first.click(
            modifiers=["Alt"]
        )
        field = page.locator(".lf-fab-input")
        expect(field).to_be_visible()
        field.click()
        page.keyboard.insert_text("Keep this check beside the changed line.")
        page.keyboard.press("Enter")
        thread = page.locator("#journey-patch .lf-page-thread")
        expect(thread).to_be_visible()
        expect(thread.locator('[aria-busy="true"]')).to_have_count(0)
        return ThreadSurface(
            thread.locator("leaf-text"),
            thread.locator(".lf-msg"),
            thread,
            ".lf-msg",
            thread,
        )
    raise ValueError(f"unknown message surface: {surface}")


def delivery_journey(page: Page, surface: str, checkpoint: Checkpoint) -> dict:
    """Draft → pending → refused → pending → accepted, with the POST ordered.

    Return the observations at each checkpoint. The caller owns its correctness
    oracle and reads the admitted log after this function returns. No snapshot is
    updated here, and no production state is injected to reach a checkpoint.
    """
    shown = open_surface(page, surface)
    field, messages = shown.field, shown.messages
    expect(field).to_be_visible()
    before = messages.count()
    field.click()
    page.keyboard.insert_text(WORDS)
    observations = {}

    def observe(stage):
        rendered(page)
        wait_for_probe(page, "pageSettled")
        reading = {
            "region": shown.region.bounding_box(),
            "field_region": field.bounding_box(),
            "draft": field.evaluate("node => node.value"),
            "caret": field.evaluate("node => [node.selectionStart, node.selectionEnd]"),
            "focused": field.evaluate("node => node.matches(':focus-within')"),
            "messages_added": messages.count() - before,
            "pending": messages.evaluate_all(
                "nodes => nodes.filter(node => node.matches('[aria-busy=\"true\"]')).length"
            ),
        }
        if stage in {"pending", "retry-pending", "newer-draft-pending", "accepted"}:
            reading["message"] = messages.last.inner_text()
            reading["opacity"] = messages.last.evaluate(
                "node => Number(getComputedStyle(node).opacity)"
            )
        if stage in {"pending", "retry-pending"}:
            reading["first_opacity"] = page.evaluate("window.__messageArrival")
        observations[stage] = reading
        checkpoint(stage, page, reading)

    observe("drafted")
    held = []

    def hold(route):
        if route.request.post_data_json.get("kind") in {"comment", "reply"}:
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    try:

        def send():
            watch_message_arrival(shown.arrival_root, shown.arrival_selector)
            field.click()
            with page.expect_request(
                lambda request: (
                    request.url.endswith("/api/event")
                    and request.post_data_json.get("kind") in {"comment", "reply"}
                )
            ):
                page.keyboard.press("Enter")
            expect(messages).to_have_count(before + 1)
            # The observer runs in the insertion turn; read it before any settled
            # screenshot or auto-retrying visual assertion can hide the first frame.
            assert page.evaluate("window.__messageArrival") == 0.5
            assert len(held) == 1, "the send did not reach the held POST"

        send()
        observe("pending")
        route = held.pop()
        attempt = route.request.post_data_json["attempt"]
        with page.expect_response(lambda response: response.url.endswith("/api/event")):
            route.fulfill(
                status=400,
                json={
                    "ok": False,
                    "attempt": attempt,
                    "error": "refused before append",
                    "final": True,
                },
            )
        expect(messages).to_have_count(before)
        expect(field).to_have_js_property("value", WORDS)
        expect(page.locator(".lf-notice")).to_contain_text("Couldn't send")
        observe("refused")
        send()
        observe("retry-pending")
        if surface == "general":
            # Keep the next edit inside the provisional card while its parent's
            # name is adopted, so focus/caret proof covers that card's lifetime.
            field = page.locator(".lf-threads > .lf-thread").last.locator("leaf-text")
            expect(field).to_be_visible()
        field.click()
        page.keyboard.insert_text(NEXT_WORDS)
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft")
        observe("newer-draft-pending")
        route = held.pop()
        assert route.request.post_data_json["attempt"] == attempt
        with page.expect_response(lambda response: response.url.endswith("/api/event")):
            route.continue_()
        expect(messages.last).not_to_have_attribute("aria-busy", "true")
        observe("accepted")
        return observations
    finally:
        page.unroute("**/api/event", hold)
