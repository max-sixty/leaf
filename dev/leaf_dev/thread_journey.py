"""The message delivery journey used by browser checks and visual snapshots.

The server, page and browser belong to the caller. This driver opens a real thread,
types through its field and sends with Return. It holds the POST before admission,
refuses it, resends the restored draft, and finally admits it. Checkpoints run while
those states are held, so a screenshot and an assertion observe the same journey.

First appearance is separate evidence: a MutationObserver records the message's
computed opacity, busy state and body words at insertion. A screenshot taken after
the browser driver returns cannot prove that instant, even while the request is held.
"""

from collections.abc import Callable
from dataclasses import dataclass

from leaf.render_checks import rendered, wait_for_probe
from playwright.sync_api import Locator, Page, expect

from leaf_dev.browser import scroll_settled

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
          const before = new Set(root.querySelectorAll(selector));
          window.__messageArrival = null;
          const observer = new MutationObserver(() => {
            const message = [...root.querySelectorAll(selector)].find(
              node => !before.has(node)
            );
            if (!message) return;
            window.__messageArrival = {
              opacity: Number(getComputedStyle(message).opacity),
              busy: message.getAttribute("aria-busy") === "true",
              words: message.querySelector(":scope > .lf-msg-body").textContent.trim(),
            };
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
    kind: str

    def intent(self) -> dict:
        """Read the chosen root before sending; page comments have no anchor."""
        parent = None
        if self.kind == "reply":
            parent = self.messages.first.evaluate(
                "node => node.dataset.mid ?? node.dataset.event"
            )
            assert parent, "the chosen thread has no durable root identity"
        return {"kind": self.kind, "parent": parent, "anchor": None}


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
                "comment",
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
            "reply",
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
            "reply",
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
        focus_field(page, field)
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
            "reply",
        )
    raise ValueError(f"unknown message surface: {surface}")


def focus_field(page: Page, field: Locator) -> None:
    """Focus through the real gesture, then park the pointer for keyboard editing."""
    field.click()
    page.mouse.move(0, 0)


def delivery_journey(page: Page, surface: str, checkpoint: Checkpoint) -> dict:
    """Draft → pending → refused → pending → accepted, with the POST ordered.

    Return the observations at each checkpoint. The caller owns its correctness
    oracle and reads the admitted log after this function returns. No snapshot is
    updated here, and no production state is injected to reach a checkpoint.
    """
    shown = open_surface(page, surface)
    field, messages = shown.field, shown.messages
    intent = shown.intent()
    expect(field).to_be_visible()
    before = messages.count()
    rendered(page)
    wait_for_probe(page, "pageSettled")
    # Seeded agent news is initial feedback, not part of this send journey. Let
    # its actual notice expire before drafting rather than racing its timer.
    expect(page.locator(".lf-notice")).to_be_hidden(timeout=6_000)
    focus_field(page, field)
    page.keyboard.insert_text(WORDS)
    observations = {}

    def observe(stage):
        rendered(page)
        wait_for_probe(page, "pageSettled")
        # A held appearance follows its finite entry motion. Observe geometry here,
        # before screenshot's animation handling can move the captured region.
        page.wait_for_function(
            """node => !node.getAnimations({subtree: true}).some(move =>
              move.playState !== 'finished' && move.playState !== 'idle'
                && Number.isFinite(move.effect.getComputedTiming().endTime))""",
            arg=shown.region.element_handle(),
        )
        # Send/open has already initiated any landing scroll. Scroll belongs to
        # the browser, and its smooth travel is not a Web Animation.
        if surface in {"panel", "general"}:
            scroll_settled(page, ".lf-threads")
        scroll_settled(page)
        reading = {
            "intent": intent,
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
            reading["first_appearance"] = page.evaluate("window.__messageArrival")
        if stage == "refused":
            expect(page.locator(".lf-notice")).to_be_visible()
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
            focus_field(page, field)
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
            appearance = page.evaluate("window.__messageArrival")
            expected = {"opacity": 0.5, "busy": True, "words": WORDS}
            assert appearance == expected, (
                f"first inserted message was {appearance!r}; expected {expected!r}"
            )
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
        # Refusal feedback is visible in that checkpoint. Its actual expiry is the
        # next boundary, so later images cannot depend on how quickly capture ran.
        expect(page.locator(".lf-notice")).to_be_hidden(timeout=6_000)
        send()
        observe("retry-pending")
        if surface == "general":
            # Keep the next edit inside the provisional card while its parent's
            # name is adopted, so focus/caret proof covers that card's lifetime.
            field = page.locator(".lf-threads > .lf-thread").last.locator("leaf-text")
            expect(field).to_be_visible()
        focus_field(page, field)
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
