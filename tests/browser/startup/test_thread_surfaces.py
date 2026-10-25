"""Threads a page or package places itself: page annotation views, thread surfaces and
their required readers, and the fallback when a surface fails."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    PANEL,
    comment_note,
    consume_browser_errors,
    leaf_page,
    open_page,
    panel_field,
    round_trip,
    stored_draft_text,
    told,
    write,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.findings import Finding
from leaf.render_checks import rendered
from leaf.schema import ELEMENT_ID

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize(
    "failure",
    [
        "outletFor",
        "invalid-count",
        "invalid-outlet",
        "disconnect",
        "moved",
        "detached",
        "hidden",
        "target-removed",
    ],
)
def test_a_failed_thread_surface_returns_its_threads_to_core_fallback(
    browser, serve, failure
):
    _exercise_failed_thread_surface(browser, serve, failure, activation="pointer")


def test_a_failed_thread_surface_continues_the_keyboard_opened_reply(browser, serve):
    """Opening sibling reactions with the keyboard retains the active reply session."""
    _exercise_failed_thread_surface(browser, serve, "hidden", activation="keyboard")


def _exercise_failed_thread_surface(browser, serve, failure, *, activation):
    """An adapter failure cannot keep stale local views or stop the next widget.

    Each case is one way a surface stops holding its threads: its `threadOutlets`
    throws (outletFor, after preparing the first datum) or answers with the wrong
    shape, it leaves the page, its outlet moves out of it or off the page, it places
    nothing, or its datum goes while `threadOutlets` awaits. Its threads
    fall back to the core surface with the unsent draft, and its picker lets go of the
    keyboard. The healthy surface stands later in registration order, so its updated
    reply proves reconciliation continued beyond the broken adapter.
    """
    entry = {
        "description": "A project-supplied thread surface.",
        "type": "object",
        "properties": {"id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-thread-surface": True,
        "x-example": '<lf-test-surface id="surface-example"></lf-test-surface>',
    }
    module = """
import {projectData, setChildren, threadSurface} from '/runtime/widget-api.js';
customElements.define('lf-test-surface', class extends HTMLElement {
  connectedCallback() {
    const datums = ['first', 'second'].map(key => {
      const row = document.createElement('section');
      const words = document.createElement('p');
      words.textContent = `${this.id} ${key} datum`;
      const outlet = document.createElement('div');
      outlet.className = 'test-outlet';
      row.outlet = outlet;
      row.append(words, outlet);
      return {node: row, key};
    });
    setChildren(this, datums.map(({node}) => node));
    projectData(this, datums);
  }
  async threadOutlets(targets) {
    const outlets = targets.map((target) => {
      const {anchor, placement} = target;
      if (anchor.datum === 'second' && this.failure === 'outletFor')
        throw new Error('surface fixture: outletFor');
      return this.failure === 'hidden' ? null : placement.datumElement.outlet;
    });
    for (const row of this.children) {
      if (this.failure === 'moved') {
        const main = document.querySelector('main');
        if (row.outlet.parentElement !== main) main.append(row.outlet);
      }
      if (this.failure === 'detached') row.outlet.remove();
    }
    if (this.failure === 'target-removed') {
      await Promise.resolve();
      for (const row of [...this.children].filter(row => row.outlet)) {
        this.append(row.outlet);
        row.remove();
      }
    }
    if (this.failure === 'invalid-count') return outlets.slice(1);
    if (this.failure === 'invalid-outlet') return outlets.map(() => undefined);
    return outlets;
  }
  fail(phase) {
    this.failure = phase;
    if (phase === 'disconnect') {
      this.remove();
      threadSurface(document.querySelector('#healthy')).update();
    }
    else threadSurface(this).update();
  }
});
"""
    roots = [f"{index:032x}" for index in range(1, 4)]
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "Adapter isolation",
                    "<h1>Adapter isolation</h1>"
                    '<lf-test-surface id="broken"></lf-test-surface>'
                    '<lf-test-surface id="healthy"></lf-test-surface>',
                ),
                layer_registry={"lf-test-surface": entry},
                layer_widgets={"lf-test-surface.js": module},
                events=[
                    {
                        "id": root,
                        "kind": "comment",
                        "author": "user",
                        "revision": 1,
                        "text": f"Discuss {section} {datum}",
                        "anchor": {"section": section, "datum": datum},
                    }
                    for root, section, datum in zip(
                        roots,
                        ["broken", "broken", "healthy"],
                        ["first", "second", "first"],
                        strict=True,
                    )
                ]
                + [
                    {
                        "id": "surface-reply",
                        "kind": "reply",
                        "author": "agent",
                        "parent": roots[0],
                        "revision": 1,
                        "text": "The first datum deserves a closer look.",
                    }
                ],
            )
        ),
    )
    broken = page.locator("#broken")
    broken_element = broken.element_handle()
    prior_outlets = broken.locator(".test-outlet").element_handles()
    healthy = page.locator("#healthy .lf-page-thread")
    expect(broken.locator(".lf-page-thread")).to_have_count(2)
    expect(healthy).to_contain_text("Discuss healthy first")
    markers = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    expect(markers).to_have_count(0)
    input = broken.locator(".lf-page-thread leaf-text").first
    write(input, "Keep this unsent reply.")
    editing = """async key => {
      const replies = await window.__lfCheckApi();
      return replies.replyIsEditing(key);
    }"""
    assert page.evaluate(editing, roots[0])
    retired_words = Finding(
        "words-left-screen",
        values={
            "words": "Keep this unsent reply.",
            "place": input.evaluate("field => window.lfPlace(field)"),
        },
    )
    strip = broken.locator(".lf-react-strip")
    trigger = strip.locator(".lf-react-trigger")
    if activation == "pointer":
        trigger.click()
    else:
        trigger.focus()
        page.keyboard.press("Enter")
    expect(strip).to_have_class(re.compile(r"\blf-react-open\b"))
    assert page.evaluate(editing, roots[0]) == (activation == "keyboard")
    assert stored_draft_text(page, f"reply:{roots[0]}") == "Keep this unsent reply."

    broken.evaluate("(widget, phase) => widget.fail(phase)", failure)
    rendered(page)
    page.evaluate("lfWordsJudged()")
    if activation == "pointer":
        # The reaction press already ended this composition, before the passive
        # adapter fault. Retiring its unfocused view withdraws saved work, not a
        # typing continuation. Calibrate only this exact report at that handoff;
        # adapter faults and every other loss remain with the strict collector.
        assert not page.evaluate(editing, roots[0])
        assert page.lf_errors.count(retired_words) == 1, page.lf_errors
        page.lf_errors.remove(retired_words)
    else:
        assert page.evaluate(editing, roots[0])
        assert "Keep this unsent reply." in page.locator(
            "leaf-text:visible"
        ).evaluate_all("fields => fields.map(field => field.value)")
        assert retired_words not in page.lf_errors, page.lf_errors
        # This control now deliberately leaves its continuing editor before
        # exercising the original retired-picker and explicit fallback routes.
        page.keyboard.press("Escape")
    assert stored_draft_text(page, f"reply:{roots[0]}") == "Keep this unsent reply."
    if failure != "disconnect":
        expect(broken.locator(".lf-page-thread")).to_have_count(0)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": roots[2],
            "revision": 1,
            "text": "The healthy thread still updates.",
        },
    )
    told(page)
    # The reply lands in view, so the healthy thread holds it behind its notice.
    expect(healthy.get_by_role("button", name="1 new reply")).to_be_visible()
    assert (
        broken_element.evaluate(
            "widget => widget.querySelectorAll('.lf-page-thread').length"
        )
        == 0
    ), "core views survived in a failed or disconnected widget"
    assert [
        outlet.evaluate("node => node.childElementCount") for outlet in prior_outlets
    ] == [
        0,
        0,
    ], "old core views survived in moved, detached, or retired outlets"
    # A removed picker must release the keyboard, not accept a reaction on its
    # now-invisible target. The following page-comment gesture is the positive
    # completion edge before checking that the digit produced no stale send.
    page.keyboard.press("1")
    page.keyboard.press("c")
    expect(page.locator('.lf-fp-field leaf-text[name="comment"]')).to_be_focused()
    round_trip(page)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("token")
    ]
    page.keyboard.press("Escape")  # out of the panel's field
    expect(panel_field(page)).not_to_be_focused()
    no_view = page.locator(f"{PANEL}[data-open]")
    expect(no_view).to_have_count(0)
    # A retired thread lands on the surface the user's own gesture reaches. With the
    # widget still on the page its passages keep a page-local destination, so each datum
    # gets a margin entry and its comment note opens the fallback card with the panel's
    # views shut; a disconnected widget leaves no such destination and the panel's
    # Threads answers, the thread's reply standing in the panel's field.
    if failure in {"disconnect", "target-removed"}:
        expect(markers).to_have_count(0)
        fallback = open_panel_thread(page, roots[0])
        reply = panel_field(page)
    else:
        expect(markers).to_have_count(2)
        comment_note(page, "#broken").press("Enter")
        fallback = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{roots[0]}"]'
        )
        reply = fallback.locator("leaf-text")
        expect(no_view).to_have_count(0)
    expect(fallback).to_be_visible()
    expect(fallback).to_contain_text("Discuss broken")
    expect(reply).to_have_js_property("value", "Keep this unsent reply.")
    if failure not in {"disconnect", "target-removed"}:
        page.keyboard.press("Escape")
        broken.evaluate("""widget => {
            widget.failure = null;
            for (const row of widget.children)
              if (row.outlet.parentElement !== row) row.append(row.outlet);
        }""")
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": roots[2],
                "revision": 1,
                "text": "A later reading retries the repaired adapter.",
            },
        )
        told(page)
        # The notice holding the first reply counts this one too.
        expect(healthy.get_by_role("button", name="2 new replies")).to_be_visible()
        expect(broken.locator(".lf-page-thread")).to_have_count(2)
        expect(broken.locator(".lf-page-thread leaf-text").first).to_have_js_property(
            "value", "Keep this unsent reply."
        )
        expect(markers).to_have_count(0)
    # Invalid output is a failed preparation, never a partial successful claim.
    if failure in {"outletFor", "moved", "invalid-count", "invalid-outlet"}:
        expected = {
            "outletFor": "surface fixture: outletFor",
            "moved": "returned an outlet outside its presentation owner",
            "invalid-count": "return one outlet or null per target",
            "invalid-outlet": "A Thread outlet must be an Element or null",
        }[failure]
        consume_browser_errors(page, expected)
