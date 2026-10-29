"""The message delivery journey used by browser checks and visual snapshots.

The server, page and browser belong to the caller. This driver opens a real thread,
types through its field and sends with Return. It holds the POST before admission,
refuses it, resends the restored draft, and finally admits it. Checkpoints run while
those states are held, so a screenshot and an assertion observe the same journey.

First appearance is separate evidence: a MutationObserver records the message's
computed opacity, busy state and body words at insertion. A screenshot taken after
the browser driver returns cannot prove that instant, even while the request is held.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from playwright.sync_api import Locator, Page, expect

from leaf.registry.kernel import kinds_declaring
from leaf.render_checks import rendered, wait_for_probe
from leaf_dev.browser import go_to_threads, scroll_settled

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
# The floating panel's view of a thread, rather than one still leaving.
THREAD_VIEW = ".lf-fp-view[data-view=thread]:not([data-leaving])"
# Where the floating panel says a passing notice: in its empty field's place, on the
# line over its field, or, while a view stands open, in the leaf's peek.
NOTICE = (
    ".lf-fp-field leaf-text[data-says=notice],"
    " .lf-fp-context[data-notice]:not([hidden]), .lf-fp-peek[data-shown]"
)


def retire_notice(page: Page) -> None:
    """Run the page's timer clock until the floating panel's notice has retired.

    The caller fixes the context's wall clock (`clock.set_fixed_time`), which leaves
    timers on a clock `run_for` advances, so the notice's own timer retires it
    without the journey waiting out its interval in real time.
    """
    notice = page.locator(NOTICE)
    deadline = time.monotonic() + 6
    while notice.count():
        assert time.monotonic() < deadline, "the notice never retired"
        page.clock.run_for(250)


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
    """Open the existing last thread in the floating panel, or its field at rest, which
    starts a page thread; either way the panel's field is the box written in."""
    if surface in {"panel", "general"}:
        field = page.locator(".lf-fp-field leaf-text")
        view = page.locator(THREAD_VIEW)
        if surface == "general":
            # The send opens its new thread's view over the field, which shows it
            # arrive, the field becoming its reply box.
            wait_for_probe(page, "pageSettled")
            return ThreadSurface(
                field,
                view.locator(".lf-msg.user"),
                page.locator("body"),
                f"{THREAD_VIEW} .lf-msg",
                page.locator(".lf-floating-panel"),
                "comment",
            )
        go_to_threads(page)
        page.locator(".lf-fp-thread:not([data-resolved])").last.click()
        expect(view).to_be_visible()
        wait_for_probe(page, "pageSettled")
        return ThreadSurface(
            field,
            view.locator(".lf-msg"),
            page.locator("body"),
            f"{THREAD_VIEW} .lf-msg",
            page.locator(".lf-floating-panel"),
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
    retire_notice(page)
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
        if page.locator(THREAD_VIEW).count():
            scroll_settled(page, THREAD_VIEW)
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
            reading["refusal_feedback"] = page.evaluate("window.__refusalFeedback")
        observations[stage] = reading
        checkpoint(stage, page, reading)

    observe("drafted")
    held = []

    def hold(route):
        if route.request.post_data_json.get("kind") in kinds_declaring("message"):
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
                    and (request.post_data_json or {}).get("kind")
                    in kinds_declaring("message")
                )
            ):
                page.keyboard.press("Enter")
            expect(messages).to_have_count(before + 1)
            # The observer runs in the insertion turn; read it before any settled
            # screenshot or auto-retrying visual assertion can hide the first frame.
            appearance = page.evaluate("window.__messageArrival")
            expected = {"opacity": 1, "busy": True, "words": WORDS}
            assert appearance == expected, (
                f"first inserted message was {appearance!r}; expected {expected!r}"
            )
            assert len(held) == 1, "the send did not reach the held POST"

        send()
        observe("pending")
        route = held.pop()
        attempt = route.request.post_data_json["attempt"]
        # Observe feedback in its mutation turn, before transport or capture time
        # can spend its actual four-second interval. The panel says it over the
        # words it returned, or in the leaf's peek while a view stands open.
        page.locator(".lf-floating-panel").evaluate(
            """node => {
              window.__refusalFeedback = null;
              const observer = new MutationObserver(() => {
                const said = [
                  ...node.querySelectorAll(".lf-fp-context-words, .lf-fp-peek"),
                ].find(said => said.textContent.trim().startsWith("Couldn't send"));
                if (!said) return;
                window.__refusalFeedback = {
                  words: said.textContent.trim(),
                  visible: said.checkVisibility({
                    opacityProperty: true, visibilityProperty: true,
                  }),
                };
                observer.disconnect();
              });
              observer.observe(node, {
                attributes: true, childList: true, subtree: true, characterData: true,
              });
            }"""
        )
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
        feedback = page.evaluate("window.__refusalFeedback")
        assert feedback == {
            "words": "Couldn't send — refused before append",
            "visible": True,
        }, f"refusal feedback at its mutation was {feedback!r}"
        # The refused screenshot owns restored draft/layout after the feedback's
        # timer retires it; a capture must not race a finite user-notice interval.
        retire_notice(page)
        observe("refused")
        send()
        observe("retry-pending")
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
