"""Threads a page or package places itself: page annotation views, thread surfaces and
their required readers, and the fallback when a surface fails."""

import json

import pytest
from interact_support import append_carried_log_record, wait_for
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    PANEL,
    ROOT,
    close_panel_menu,
    comment_note,
    consume_browser_errors,
    expect_preview_words,
    holding,
    leaf_page,
    open_page,
    panel_control,
    panel_field,
    primed,
    round_trip,
    stored_draft_text,
    told,
    undo,
    write,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.findings import Finding
from leaf.render_checks import rendered
from leaf_dev.browser import PANEL_THREAD

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


def test_a_moved_thread_outlet_continues_the_pointer_opened_reply(browser, serve):
    """A failed outlet must keep the active reply visible after a sibling press."""
    _exercise_failed_thread_surface(
        browser, serve, "moved", activation="pointer-continuation"
    )


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
        "properties": {
            "id": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-data": {
            "rows": {
                "contract": "text-document",
                "source": "source",
                "property": "value",
            }
        },
        "x-example": '<lf-test-surface id="surface-example"></lf-test-surface>',
    }
    module = """
import {LeafElement, setChildren, threadSurface} from '/runtime/widget-api.js';
customElements.define('lf-test-surface', class extends LeafElement {
  setup() {
    const datums = ['first', 'second'].map(key => {
      const row = document.createElement('section');
      const words = document.createElement('p');
      words.textContent = `${this.id} ${key} datum`;
      const outlet = document.createElement('div');
      outlet.className = 'test-outlet';
      row.outlet = outlet;
      row.append(words, outlet);
      row.dataset.lfDatum = key;
      return row;
    });
    setChildren(this, datums);
    this.dispatchEvent(new CustomEvent('drawn', {detail: {value: null}}));
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
    trigger = broken.locator(".lf-react-trigger")
    if activation == "pointer":
        # Exercise retirement of a saved draft separately from active continuations.
        input.press("Escape")
        assert not page.evaluate(editing, roots[0])
    if activation.startswith("pointer"):
        trigger.click()
    else:
        trigger.focus()
        page.keyboard.press("Enter")
    expect(strip.locator(".lf-react-palette:popover-open")).to_have_count(1)
    assert page.evaluate(editing, roots[0]) == (activation != "pointer")
    assert stored_draft_text(page, f"reply:{roots[0]}") == "Keep this unsent reply."

    broken.evaluate("(widget, phase) => widget.fail(phase)", failure)
    rendered(page)
    page.evaluate("lfWordsJudged()")
    if activation == "pointer":
        # Escape already ended this composition, before the passive
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
    expect(healthy.get_by_role("button", name="1 new", exact=True)).to_be_visible()
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
    no_view = page.locator(f"{PANEL}[data-lf-open]")
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
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{roots[0]}"]'
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
        # The notice holding the first reply counts this one too, and its preview
        # says what it holds.
        expect_preview_words(
            healthy.get_by_role("button", name="2 new", exact=True), "2 new replies"
        )
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


def test_a_thread_surface_without_an_id_reports_its_failure(browser, serve):
    """A thread names its widget by id, so an instance without one can seat no thread
    and open no comment box. The page reports that as the widget's own failure once the
    instance would have registered, which `page check` shows without a press. Its opener stays null, so the Comment control a module offers by it never
    shows, and the instance beside it, which has an id, opens its box."""
    entry = {
        "description": "A card that seats the threads about it.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "additionalProperties": False,
        "x-example": '<lf-test-card id="card-example">A card.</lf-test-card>',
    }
    module = """
import {nothing} from '/vendor/lit.js';
import {keepsHidden, LeafElement, offer, offerAction, threadSurface}
  from '/runtime/widget-api.js';
customElements.define('lf-test-card', class extends LeafElement {
  setup() {
    this.threads = offer('div', 'lf-test-threads');
    this.comment = offerAction('symbol', 'lf-test-comment', undefined, {
      action: 'comment',
    });
    this.comment.addEventListener('click', () => threadSurface(this).open?.(this));
    this.append(this.threads, this.comment);
  }
  threadOutlets(targets) {
    return targets.map(() => this.threads);
  }
  render() {
    keepsHidden(this.comment, !threadSurface(this).open);
    return nothing;
  }
});
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Cards",
                '<h1 id="title">Cards</h1>'
                '<lf-test-card id="named">A card with an id.</lf-test-card>'
                "<lf-test-card>A card without one.</lf-test-card>",
            ),
            layer_registry={"lf-test-card": entry},
            layer_widgets={"lf-test-card.js": module},
        ),
    )
    said = (
        "<lf-test-card> failed: a widget that shows threads needs an id on each"
        " instance, and this one has none"
    )
    logged = wait_for(
        lambda: [
            event["text"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "error"
        ],
        bool,
        failure="the surface without an id reached the log as no error",
    )
    consume_browser_errors(page, said)
    assert len(logged) == 1 and logged[0].startswith(said), logged
    expect(page.locator("lf-test-card:not([id]) > .lf-test-comment")).to_be_hidden()
    named = page.locator("#named")
    named.locator(":scope > .lf-test-comment").click()
    expect(named.locator(":scope > .lf-test-threads .lf-fab-input")).to_be_focused()


def test_page_annotation_view_seats_obligations_and_contributed_controls(
    browser, serve
):
    """A page that owns its annotations shows its obligations and contributed actions in its
    own box: Leaf hands the consumer each entry's items, native controls and the element
    it is about, and the page only arranges them, tying a row to its entry before or
    after it appends the row. Activating an obligation reaches its obligation, and a
    seated control still runs its contribution's action. The view follows the log: an
    answered obligation leaves once the server holds the answer, and Undo brings it back."""
    url = serve(
        leaf_page(
            "Page annotation view",
            """
      <h1 id="title">Review</h1>
      <lf-ask id="choice-question"><h2>Which route?</h2>
        <lf-options id="routes" choose><lf-option id="route-a">Route A</lf-option>
        <lf-option id="route-b">Route B</lf-option></lf-options>
      </lf-ask>
      <p id="subject">The export keeps one file per tenant.</p>
      <aside id="review" aria-label="Review"></aside>
    """,
        ).replace("<body>", '<body data-annotations="page">')
    )
    page = open_page(browser, url)
    page.evaluate("""async () => {
      const {contributionEntry, registerContribution} =
        await window.__lfWidgetApi();
      registerContribution({key: 'review', target: document.getElementById('subject'),
        read: () => ({entries: [contributionEntry({key: 'reviewed', behavior: 'action',
          icon: 'dot', label: 'Mark reviewed'})]}),
        activate: (key) => { window.activated = key; }});
      const {consumeAnnotations} = await window.__lfWidgetApi();
      const box = document.querySelector('#review');
      consumeAnnotations(box, (entries, view) => {
        box.replaceChildren();
        for (const entry of entries) {
          const row = document.createElement('div');
          row.dataset.lfGen = '1';
          row.dataset.about = view.target(entry).id;
          view.place(entry, row);
          box.append(row);
          for (const item of view.items(entry)) {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = [item.label, item.text].filter(Boolean).join(' · ');
            button.addEventListener('click', () => view.activate(item));
            row.append(button);
          }
          row.append(...view.controls(entry));
        }
      });
    }""")
    review = page.locator("#review")
    question = review.get_by_role(
        "button", name="Which route? · Waiting on me", exact=True
    )
    expect(question).to_be_visible()
    assert review.locator("[data-about]").evaluate_all(
        "rows => rows.map(row => row.dataset.about)"
    ) == ["choice-question", "subject"]
    question.click()
    page.wait_for_function("!!document.activeElement?.closest('#choice-question')")
    contributed = review.get_by_role("button", name="Mark reviewed", exact=True)
    expect(contributed).to_be_visible()
    contributed.click()
    page.wait_for_function("window.activated === 'reviewed'")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#route-a .lf-pick").click()
    expect(page.locator("#route-a")).to_have_attribute("chosen", "")
    expect(question).to_be_visible()
    holding(page, held, 1, "the optimistic choice")
    held[0].continue_()
    page.unroute("**/api/event")
    expect(question).to_have_count(0)
    undo(page)
    expect(page.locator("#route-a")).not_to_have_attribute("chosen", "")
    expect(question).to_be_visible()


def test_page_thread_surface_owns_exact_source_elsewhere_in_main(browser, serve):
    url = serve(
        leaf_page(
            "Page review rail",
            """
      <h1 id="title">Review</h1><p id="subject">The nightly export keeps one file per tenant.</p>
      <aside id="review" aria-label="Review" style="height: 500px; overflow:auto"></aside>
    """,
        ).replace("<body>", '<body data-annotations="page">'),
        anchored=[("subject", "one file per tenant")],
    )
    page = open_page(browser, url)
    page.evaluate("""async () => {
      const {placePageThreads} = await window.__lfWidgetApi();
      const rail = document.querySelector('#review');
      const outlets = new Map();
      window.pageSurface = placePageThreads(rail, (targets) => {
        return targets.map(({thread}) => {
          let outlet = outlets.get(thread.key);
          if (!outlet) {
            outlet = document.createElement('div');
            outlet.dataset.lfGen='1'; rail.append(outlet); outlets.set(thread.key,outlet);
          }
          return outlet;
        });
      });
    }""")
    thread = page.locator("#review .lf-page-thread")
    expect(thread).to_have_count(1)
    expect(thread).to_contain_text("About this bit.")
    assert page.evaluate("""async () => {
      const {claimed} = await __lfCheckApi();
      return claimed(document.querySelector('#review .lf-page-thread').dataset.lfThread);
    }""")
    reply = thread.get_by_role("textbox", name="Reply", exact=True)
    write(reply, "Can the archive keep that naming?")
    reply.press("Enter")
    expect(thread).to_contain_text("Can the archive keep that naming?")
    page.evaluate("pageSurface.unregister()")
    expect(thread).to_have_count(0)


def test_a_page_presentation_draws_a_thread_once_a_route_asks_for_it(browser, serve):
    """A page that draws its own annotations is handed every thread with a place, an
    inexact one and a resolved one included, and may draw none of them until asked: `t`
    asks its `reveal`, Leaf places the outlet it then returns and lands the user in it,
    and the panel stays shut. Awaiting the handle's `update()` waits for the placement.
    A presentation that declines leaves the thread to Leaf's panel, and one that draws
    nothing over the page leaves the command that hides annotations disabled. A thread
    with no place is never handed over, so no route asks the page for it. A reveal the
    presentation takes and then returns no outlet for is reported as its failure, and
    the thread is not asked for again until the presentation asks for a pass itself,
    when it goes back to the page."""
    events = [
        {
            "id": f"{i:032x}",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": text,
            "anchor": anchor,
        }
        for i, text, anchor in [
            (
                1,
                "About the passage",
                {"section": "subject", "quote": "one file per tenant"},
            ),
            (2, "About a control", {"section": "other", "part": "A named control"}),
            (3, "Settled already", {"section": "other"}),
            (4, "Lost words", {"section": "subject", "quote": "words not on the page"}),
        ]
    ] + [{"kind": "resolve", "author": "user", "parent": f"{3:032x}"}]
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Page presentation",
                """
      <h1 id="title">Review</h1><p id="subject">The nightly export keeps one file per tenant.</p>
      <p id="other">The archive keeps ninety days of files.</p>
      <aside id="review" aria-label="Review"></aside>
    """,
            ).replace("<body>", '<body data-annotations="page">'),
            events=events,
        ),
    )
    page.evaluate("""async () => {
      const {placePageThreads} = await window.__lfWidgetApi();
      const rail = document.querySelector('#review');
      const outlet = document.createElement('div');
      outlet.dataset.lfGen = '1';
      window.asked = [];
      window.pageSurface = placePageThreads(rail, (targets) => {
        window.targets = targets.map(({thread, placement}) => ({
          text: thread?.root.body.text.trim() ?? null,
          resolved: Boolean(thread?.resolved),
          status: placement.status,
          place: placement.place.id,
          words: (placement.ranges ?? []).map(String),
        }));
        window.ranges = targets.flatMap(({placement}) => placement.ranges ?? []);
        if (!targets.some(({thread}) => thread?.key === window.shown)) outlet.remove();
        return targets.map(({thread}) => {
          if (thread?.key !== window.shown) return null;
          if (!outlet.isConnected) rail.append(outlet);
          return outlet;
        });
      }, {reveal: (key) => {
        window.asked.push(key);
        // The cap ends a route that keeps asking, so the counts below fail it by an
        // assertion rather than the page running until the test's deadline.
        if (window.declines || window.asked.length > 8) return false;
        if (!window.ignores) window.shown = key;
      }});
      await pageSurface.update();
    }""")
    assert page.evaluate("targets") == [
        {
            "text": "About the passage",
            "resolved": False,
            "status": "exact",
            "place": "subject",
            "words": ["one file per tenant"],
        },
        {
            "text": "About a control",
            "resolved": False,
            "status": "fallback",
            "place": "other",
            "words": [],
        },
        {
            "text": "Settled already",
            "resolved": True,
            "status": "exact",
            "place": "other",
            "words": [],
        },
    ]
    # A passage's ranges are live: a script writing words ahead of the passage moves
    # them with it, and the next pass hands over the same ranges.
    assert page.evaluate("""async () => {
      const [before] = window.ranges;
      document.querySelector('#subject').firstChild.insertData(0, 'Since Monday, ');
      await pageSurface.update();
      return [window.ranges[0] === before, String(before)];
    }""") == [True, "one file per tenant"]
    drawn = page.locator("#review .lf-page-thread")
    expect(drawn).to_have_count(0)
    # Nothing here joined the annotation layer, so `o` hides nothing and its row in the
    # leaf's menu stands disabled.
    page.locator("#title").click()
    page.keyboard.press("o")
    expect(page.locator("html")).not_to_have_attribute("data-lf-annotations", "hidden")
    expect(
        panel_control(page, "command:annotations.toggle", at="annotate")
    ).to_be_disabled()
    close_panel_menu(page)
    page.locator("#title").click()

    page.keyboard.press("t")
    expect(drawn).to_have_count(1)
    expect(drawn).to_contain_text("About the passage")
    expect(drawn).to_be_focused()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    assert page.evaluate("asked.length") == 1

    # The page puts the thread away again, and its update is the pass that takes it.
    assert (
        page.evaluate("""async () => {
      document.querySelector('#title').focus();
      window.shown = null;
      await pageSurface.update();
      return document.querySelectorAll('#review .lf-page-thread').length;
    }""")
        == 0
    )

    page.evaluate("window.declines = true")
    page.locator("#title").click()
    page.keyboard.press("t")
    expect(page.locator(PANEL_THREAD)).to_contain_text("About the passage")
    expect(drawn).to_have_count(0)

    # The page has no outlet to give a thread whose words it no longer holds, so the
    # panel takes it unasked. Asked, a page that recorded it open would draw nothing,
    # and every pass after would ask again whether the page could take it back.
    page.evaluate("""async () => {
      const {readThreads, threadActions} = await window.__lfWidgetApi();
      window.declines = false;
      window.asked = [];
      const lost = readThreads().threads.find(
        (thread) => thread.root.body.text.trim() === 'Lost words');
      await threadActions.open(lost.key, {part: 'thread'});
    }""")
    expect(page.locator(PANEL_THREAD)).to_contain_text("Lost words")
    rendered(page)
    assert page.evaluate("asked") == []

    # A presentation that takes a thread and then returns no outlet for it has failed.
    # The page says so once and the panel takes the thread. Each pass after would ask
    # the page to take it back, and each such ask ran a pass of its own, so the page is
    # not asked again until it asks for a pass itself, which then brings the thread back.
    page.evaluate("""async () => {
      const {readThreads, threadActions} = await window.__lfWidgetApi();
      window.asked = [];
      window.ignores = true;
      const passage = readThreads().threads.find(
        (thread) => thread.root.body.text.trim() === 'About the passage');
      await threadActions.open(passage.key, {part: 'thread'});
    }""")
    expect(page.locator(PANEL_THREAD)).to_contain_text("About the passage")
    consume_browser_errors(page, "render returned no outlet for it")
    rendered(page)
    assert page.evaluate("asked.length") == 1
    expect(drawn).to_have_count(0)
    page.evaluate("""async () => {
      window.ignores = false;
      await pageSurface.update();
    }""")
    expect(drawn).to_contain_text("About the passage")
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    assert page.evaluate("asked.length") == 2


def test_a_page_presentation_s_update_places_its_threads_while_state_is_applied(
    browser, serve
):
    """The page handle's `update()` settles once its threads are placed, also while Leaf
    is applying a server reading, whose own pass a route may be waiting inside, as a
    revision's landing in a reply is. Asked of the document's pass, which an application
    holds back until it ends, the update answered at once with nothing placed."""
    url = serve(
        leaf_page(
            "Page presentation under a reading",
            """
      <h1 id="title">Review</h1><p id="subject">The nightly export keeps one file per tenant.</p>
      <aside id="review" aria-label="Review"></aside>
    """,
        ).replace("<body>", '<body data-annotations="page">'),
        anchored=[("subject", "one file per tenant")],
    )
    page = open_page(browser, url)
    page.evaluate("""async () => {
      const {placePageThreads} = await window.__lfWidgetApi();
      const rail = document.querySelector('#review');
      const outlet = document.createElement('div');
      outlet.dataset.lfGen = '1';
      window.pageSurface = placePageThreads(rail, (targets) =>
        targets.map(({thread}) => {
          if (!window.shows || !thread) return null;
          if (!outlet.isConnected) rail.append(outlet);
          return outlet;
        }));
      await pageSurface.update();
    }""")
    drawn = page.locator("#review .lf-page-thread")
    expect(drawn).to_have_count(0)
    # A required reader holds the pass of the next reading, so its application stands
    # open while the page asks for its threads to be placed.
    _hold_required_thread_reader(page)
    page.evaluate("window.holdPanel = true")
    [root] = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    append_carried_log_record(
        serve.page_dir,
        {"kind": "reply", "author": "agent", "parent": root, "text": "Noted."},
    )
    page.wait_for_function('typeof releasePanel === "function"')
    page.evaluate("""() => {
      window.shows = true;
      void pageSurface.update().then(() => {
        window.placedAtUpdate =
          document.querySelectorAll('#review .lf-page-thread').length;
      });
      releasePanel();
    }""")
    page.wait_for_function("window.placedAtUpdate !== undefined")
    assert page.evaluate("placedAtUpdate") == 1
    expect(drawn).to_contain_text("Noted.")


def test_the_gallery_s_page_margin_draws_a_page_s_annotations_itself(browser, serve):
    """`lf-x-margin`, the feature gallery's worked example, is a margin built on the
    public package interface alone. On a page that draws its own annotations, in a window
    with no room beside the column, it pins a mark for each commented passage, each
    obligation and each contributed action, saying whose turn a thread is and what it
    holds unread; opens a thread's card from its mark or `t`, and closes it on Escape
    from inside the card or a press elsewhere, keeping the words typed there; follows
    its words through a box's scroll with no script answering the scroll; seats the
    comment box by the words; is Go-to's margin; and goes while annotations are hidden,
    its contributed controls working once they return."""
    companion = ROOT / "examples/developer/feature-gallery.page"
    events = [
        {
            "id": f"{1:032x}",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the passage",
            "anchor": {"section": "subject", "quote": "one file per tenant"},
        },
        {
            "kind": "reply",
            "author": "agent",
            "parent": f"{1:032x}",
            "responds": f"{1:032x}",
            "revision": 1,
            "text": "It does.",
        },
        {
            "id": f"{2:032x}",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the window",
            "anchor": {"section": "note-3", "quote": "the nightly window"},
        },
    ]
    # A window with no room for the marks beside the column, from its first layout.
    context = browser.new_context(viewport={"width": 920, "height": 780})
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Page margin",
                """
      <h1 id="title">Review</h1>
      <p id="subject" style="text-align: end">The nightly export keeps one file per tenant.</p>
      <lf-ask id="route"><h2>Which route?</h2><lf-options id="routes" choose>
        <lf-option id="route-a">Route A</lf-option><lf-option id="route-b">Route B</lf-option>
      </lf-options></lf-ask>
      <div id="notes" style="block-size: 6rem; overflow: auto">
        <p id="note-1">The first note.</p><p id="note-2">The second note.</p>
        <p id="note-3">The third note is about the nightly window.</p>
        <p id="note-4">The fourth note.</p><p id="note-5">The fifth note.</p>
        <p id="note-6">The sixth note.</p>
      </div>
      <p id="wording">It is switched off <lf-suggestion id="suggestion"
        ><lf-old>at the end</lf-old><lf-new>a week later</lf-new></lf-suggestion>.</p>
      <p id="tail">Until then both exports run side by side.</p>
      <lf-x-margin id="margin"></lf-x-margin>
    """,
            ).replace("<body>", '<body data-annotations="page">'),
            layer_registry={
                "lf-x-margin": json.loads((companion / "registry.json").read_text())[
                    "lf-x-margin"
                ]
            },
            layer_widgets={
                "lf-x-margin.js": (companion / "widgets/lf-x-margin.js").read_text()
            },
            events=events,
        ),
        context=context,
    )
    margin = page.locator("lf-x-margin")
    expect(margin).to_have_attribute("data-pinned", "")
    passage = margin.get_by_role("button", name="Thread: About the passage, 1 unread")
    window = margin.get_by_role("button", name="Thread: About the window")
    owed = margin.get_by_role("button", name="Waiting on me: Which route?", exact=True)
    accept = margin.get_by_role("button", name="Accept the suggested change")
    card = margin.locator(".lf-page-thread")
    for mark in (passage, window, owed, accept):
        expect(mark).to_be_visible()
    # The tint paints from the ranges Leaf hands over, under a rule naming the elements
    # that hold the words.
    tinted = "[...CSS.highlights.get('lf-x-margin-passage')].map(String)"
    assert page.evaluate(tinted) == ["one file per tenant", "the nightly window"]
    assert page.evaluate(
        "[...document.querySelectorAll('[data-lf-marked-words]')].map((node) => node.id)"
    ) == ["subject", "note-3"]

    # A pin has no room for its words, so its face and its preview say them: a dot for
    # what is unread, the turn's colour on what waits on the user, and its line on Tab.
    assert margin.evaluate("""(margin) => [...margin.querySelectorAll('.xm-mark')].map(
      (mark) => [mark.hasAttribute('data-unread'), mark.hasAttribute('data-turn'),
        Boolean(mark.querySelector('.xm-word')?.checkVisibility())])""") == [
        [True, False, False],
        [False, True, False],
        [False, False, False],
        [False, False, False],
    ]
    expect_preview_words(passage, "1 unread")
    # The dot stands on its symbol's upper corner, also in a press as wide as a finger's,
    # where the symbol stands further in.
    assert margin.locator(".xm-mark[data-unread]").evaluate("""(mark) => {
      const press = mark.querySelector('.xm-press');
      const onCorner = () => {
        const dot = mark.querySelector('.xm-dot').getBoundingClientRect();
        const icon = press.querySelector('svg').getBoundingClientRect();
        return Math.abs(dot.left + dot.width / 2 - icon.right) <= 2 &&
          Math.abs(dot.top + dot.height / 2 - icon.top) <= 2;
      };
      const narrow = onCorner();
      press.style.inlineSize = '44px';
      const wide = onCorner();
      press.style.removeProperty('inline-size');
      return [narrow, wide];
    }""") == [True, True]
    # Tab reads the margin down the page.
    page.locator("#title").click()
    reached = []
    for _ in range(16):
        page.keyboard.press("Tab")
        name = page.evaluate(
            "document.activeElement.closest('lf-x-margin')"
            " ? document.activeElement.getAttribute('aria-label') : null"
        )
        if name:
            reached.append(name.split(":")[0].split(" the ")[0])
        elif reached:
            break
    assert reached == ["Thread", "Waiting on me", "Thread", "Accept", "Reject"]

    # A press opens the thread's card, and Escape from inside it returns to the mark:
    # Leaf's step out of the reply first, then the card's own, declared on its outlet.
    passage.click()
    expect(card).to_contain_text("About the passage")
    reply = card.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_be_focused()
    # With no room beside the column the card stands under its words, at the width
    # that says a message's line whole. These words end at the column's edge, where a
    # card starting with them would run under the pins: it ends short of them, so a
    # press where each stands still reaches it.
    assert margin.locator(".xm-card").evaluate(
        """(card) => {
          const words = [...CSS.highlights.get('lf-x-margin-passage')][0];
          const box = card.getBoundingClientRect();
          const pins = [...document.querySelectorAll('lf-x-margin .xm-mark button')];
          return [box.top >= words.getClientRects()[0].bottom,
            Math.round(box.width / parseFloat(getComputedStyle(document.documentElement).fontSize)),
            pins.map((pin) => {
              const at = pin.getBoundingClientRect();
              return pin.contains(document.elementFromPoint(
                at.left + at.width / 2, at.top + at.height / 2));
            })];
        }"""
    ) == [True, 26, [True] * 5]
    page.keyboard.press("Escape")
    expect(card).to_be_focused()
    page.keyboard.press("Escape")
    expect(card).to_have_count(0)
    expect(
        margin.get_by_role("button", name="Thread: About the passage")
    ).to_be_focused()

    # A press elsewhere puts the card away, and Leaf keeps the words typed in it.
    opener = margin.get_by_role("button", name="Thread: About the passage")
    opener.click()
    write(reply, "Does the archive too?")
    page.locator("#tail").click()
    expect(card).to_have_count(0)
    opener.click()
    expect(reply).to_have_js_property("value", "Does the archive too?")
    page.locator("#title").click()
    expect(card).to_have_count(0)

    # `t` reaches the page's own card, and Leaf's panel stays shut.
    page.keyboard.press("t")
    expect(card).to_contain_text("About the passage")
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    page.keyboard.press("Escape")
    expect(card).to_have_count(0)

    # The browser carries a mark with its words through the box's scroll: once the
    # scroll has painted the mark stands on them again, and the widget wrote no style to
    # put it there.
    assert page.evaluate("""async () => {
      const mark = [...document.querySelectorAll('lf-x-margin .xm-mark')].find((node) =>
        node.querySelector('button').getAttribute('aria-label').includes('the window'));
      const words = [...CSS.highlights.get('lf-x-margin-passage')].find((range) =>
        String(range) === 'the nightly window');
      const gap = () =>
        Math.round(mark.getBoundingClientRect().top - words.getClientRects()[0].top);
      const before = gap();
      let writes = 0;
      const watch = new MutationObserver((records) => { writes += records.length; });
      watch.observe(document.querySelector('lf-x-margin'),
        {subtree: true, attributes: true, attributeFilter: ['style']});
      document.querySelector('#notes').scrollTop = 12;
      await new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)));
      writes += watch.takeRecords().length;
      watch.disconnect();
      return {before, after: gap(), writes};
    }""") == {"before": 0, "after": 0, "writes": 0}

    # Go-to letters the page's marks as it letters Leaf's own margin: all of them as
    # margin targets, and the threads' as Thread controls.
    chips = page.locator(".lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]:visible")
    page.locator("#title").click()
    page.keyboard.press("g")
    page.keyboard.press("m")
    expect(chips).to_have_count(5)
    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(chips).to_have_count(2)
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(chips).to_have_count(0)

    # The comment box opens in the page's own outlet, by the words, and no empty outlet
    # stands before or after it.
    page.locator("#tail").select_text()
    page.keyboard.press("c")
    box = margin.get_by_role("textbox")
    expect(box).to_be_focused()
    page.keyboard.press("Escape")
    expect(box).to_have_count(0)
    assert (
        margin.locator(".xm-card").evaluate_all(
            "(cards) => cards.filter((card) => card.checkVisibility()).length"
        )
        == 0
    )

    # An obligation's mark goes to its question.
    owed.click()
    page.wait_for_function("!!document.activeElement?.closest('#route')")

    # The margin joined the annotation layer, so `o` hides its pins and tints, and they
    # come back with their controls working.
    page.locator("#title").click()
    page.keyboard.press("o")
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")
    expect(margin.locator(".xm-mark")).to_have_count(0)
    assert page.evaluate(tinted) == []
    assert (
        page.evaluate("document.querySelectorAll('[data-lf-marked-words]').length") == 0
    )
    page.keyboard.press("o")
    expect(opener).to_be_visible()
    assert page.evaluate(tinted) == ["one file per tenant", "the nightly window"]
    expect(accept).to_be_enabled()
    accept.click()
    expect(page.locator("#suggestion")).to_have_attribute("data-lf-state", "accept")


def _hold_required_thread_reader(page):
    """Hold a real required presentation through the public package contract."""
    page.evaluate("""async () => {
      const {registerThreadPresentation} = await window.__lfWidgetApi();
      const owner = document.createElement('aside');
      owner.dataset.lfGen = '1';
      document.body.append(owner);
      window.requiredReader = registerThreadPresentation(owner, {
        render: async () => {
          if (window.holdPanel) {
            window.holdPanel = false;
            await new Promise(resolve => { window.releasePanel = resolve; });
          }
        },
        reveal: () => false,
      });
      await requiredReader.update();
    }""")


def _prepare_surface_refresh(page):
    page.evaluate("""() => {
      window.refreshSurface = async handle => {
        handle.update();
        // update enqueues its document invalidation in this turn.
        await Promise.resolve();
        const {whenDocumentPresented} = await window.__lfCheckApi();
        // These fixtures deliberately fail a required renderer and inspect its
        // pending proof after the owner has reported the failed pass.
        await whenDocumentPresented().catch(() => undefined);
      };
    }""")


def test_widgets_claim_before_page_and_only_required_page_failures_fail_proof(
    browser, serve
):
    entry = {
        "description": "An exact source seat.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "style": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-data": {
            "rows": {
                "contract": "text-document",
                "source": "source",
                "property": "value",
            }
        },
        "x-example": '<lf-test-seat id="sample"></lf-test-seat>',
    }
    module = """
import {LeafElement, setChildren, threadSurface} from '/runtime/widget-api.js';
customElements.define('lf-test-seat', class extends LeafElement {
  setup() {
    const row = document.createElement('section');
    row.textContent = 'Source row';
    row.outlet = document.createElement('div');
    row.append(row.outlet);
    row.dataset.lfDatum = 'row';
    setChildren(this, [row]);
    this.dispatchEvent(new CustomEvent('drawn', {detail: {value: null}}));
  }
  // Until `start`, the seat offers none, so the page presents every thread first.
  threadOutlets(targets) {
    if (this.fail) throw new Error('exact widget failed');
    return targets.map(target => this.started ? target.placement.datumElement.outlet : null);
  }
  start() {
    this.started = true;
    threadSurface(this).update();
  }
});
"""
    events = [
        {
            "id": f"{i:032x}",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": text,
            "anchor": anchor,
        }
        for i, text, anchor in [
            (1, "Widget conversation", {"section": "seat", "datum": "row"}),
            (
                2,
                "Passage conversation",
                {"section": "subject", "quote": "one file per tenant"},
            ),
        ]
    ]
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Widget first page review",
                """
      <h1>Review</h1><button id="fail-widget">Break widget</button><button id="retire-outlet">Retire outlet</button><lf-test-seat id="seat" style="display:block;height:250px;overflow:auto"></lf-test-seat>
      <p id="subject">The nightly export keeps one file per tenant.</p>
      <aside id="review" aria-label="Review" style="height:500px; overflow:auto"></aside>
    """,
            ).replace("<body>", '<body data-annotations="page">'),
            layer_registry={"lf-test-seat": entry},
            layer_widgets={"lf-test-seat.js": module},
            events=events,
        ),
    )
    _prepare_surface_refresh(page)
    page.evaluate("""async () => {
      const app = await window.__lfWidgetApi();
      window.refreshProof = () => refreshSurface(pageSurface);
      document.querySelector("#fail-widget").addEventListener("click", () => {
        document.querySelector("#seat").fail = true; void refreshProof();
      });
      document.querySelector('#retire-outlet').onclick=()=>{
        document.querySelector('#seat [data-lf-datum]').outlet.remove();
      };
      const rail = document.querySelector('#review');
      const outlets = new Map();
      window.pageSurface = app.placePageThreads(rail, (targets) => {
        if (window.failPage) throw new Error('required page failed');
        return targets.map(({thread}) => {
          let outlet = outlets.get(thread.key);
          if (!outlet) { outlet = document.createElement('div');
            outlet.dataset.lfGen='1'; outlet.style.cssText='display:flow-root;height:250px;overflow:auto'; rail.append(outlet); outlets.set(thread.key,outlet); }
          return outlet;
        });
      });
    }""")
    expect(page.locator("#review .lf-page-thread")).to_have_count(2)
    page.locator("#seat").evaluate("(seat) => seat.start()")
    expect(page.locator("#seat .lf-page-thread")).to_have_count(1)
    expect(page.locator("#review .lf-page-thread")).to_have_count(1)
    expect(page.locator("#review")).to_contain_text("Passage conversation")
    # An actual page-presented reply stands at its source, not its authored rail.
    reply = page.locator("#review .lf-page-thread").get_by_role(
        "textbox", name="Reply", exact=True
    )
    reply.click()
    assert (
        page.evaluate("""async () => {
      const {placeOf} = await __lfCheckApi();
      return placeOf(document.activeElement)?.id;
    }""")
        == "subject"
    )
    # A widget outlet can disappear while a required sibling prepares. The page's
    # existing fallback nomination receives its Thread on this same cohort commit.
    _hold_required_thread_reader(page)
    page.evaluate("()=>{window.holdPanel=true;void refreshProof();}")
    page.wait_for_function('typeof releasePanel === "function"')
    page.locator("#retire-outlet").click()
    page.evaluate("()=>releasePanel()")
    expect(page.locator("#seat .lf-page-thread")).to_have_count(0)
    expect(page.locator("#review .lf-page-thread")).to_have_count(2)
    page.evaluate("""async()=>{
      const row=document.querySelector('#seat [data-lf-datum]');row.append(row.outlet);
      await refreshProof();
    }""")
    expect(page.locator("#seat .lf-page-thread")).to_have_count(1)
    expect(page.locator("#review .lf-page-thread")).to_have_count(1)
    page.locator("#fail-widget").click()
    assert page.evaluate("async () => { await refreshProof(); return true; }")
    expect(page.locator("#seat .lf-page-thread")).to_have_count(0)
    expect(page.locator("#review .lf-page-thread")).to_have_count(2)
    consume_browser_errors(page, "exact widget failed")
    page.locator("#seat").evaluate("(seat) => { seat.fail = false; }")
    page.evaluate("window.failPage = true")
    proof = page.evaluate("""async () => {
      await refreshProof();
      const {readApplicationPresentation, applicationPresented} =
        await window.__lfCheckApi();
      return {pending: readApplicationPresentation().pending, presented: applicationPresented()};
    }""")
    assert "thread" in proof["pending"]
    assert proof["presented"] is False
    consume_browser_errors(page, "required page failed")
    # Core indexes remain readable and the same selected renderer can recover.
    assert page.evaluate("async () => pageSurface.read().threads.length") == 2
    page.evaluate("window.failPage = false")
    page.evaluate("async () => { await refreshProof(); }")
    expect(page.locator("#seat .lf-page-thread")).to_have_count(1)
    expect(page.locator("#review .lf-page-thread")).to_have_count(1)


def test_required_page_failure_retains_composer_seat_focus_and_caret(browser, serve):
    entry = {
        "description": "An exact datum seat.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-data": {
            "rows": {
                "contract": "text-document",
                "source": "source",
                "property": "value",
            }
        },
        "x-example": '<lf-test-seat id="seat"></lf-test-seat>',
    }
    module = """
import {LeafElement,setChildren} from '/runtime/widget-api.js';
customElements.define('lf-test-seat',class extends LeafElement{
  setup(){
    this.style.cssText='display:block;height:360px;overflow:auto';
    const datums=['row'].map(key=>{
      const row=document.createElement('section');row.textContent='Source row';
      for(const name of ['a','b']){row[name]=document.createElement('div');row[name].dataset.seat=name;row.append(row[name]);}
      row.dataset.lfDatum=key;
      return row;
    });
    setChildren(this,datums);
    this.dispatchEvent(new CustomEvent('drawn',{detail:{value:null}}));
    this.side='a';
  }
  threadOutlets(targets){
    return targets.map(target=>this.side?target.placement.datumElement[this.side]:null);
  }
});
"""
    events = [
        {
            "id": f"{i:032x}",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": text,
            "anchor": anchor,
        }
        for i, text, anchor in [
            (1, "Widget thread", {"section": "seat", "datum": "row"}),
            (2, "Source thread", {"section": "subject"}),
        ]
    ]
    # This journey changes presentation seats, not admitted state. Keep the
    # origin's freshness at the initial reading so a background state admission
    # cannot acquire the intentionally held presentation proof.
    state_readings = []

    def steady_state_origin(page):
        def state(route):
            response = route.fetch()
            state_readings.append(response.json()["reading"])
            route.fulfill(response=response)

        page.route("**/api/state*", state)
        page.route(
            "**/api/news*",
            lambda route: route.fulfill(
                json={"reading": state_readings[0], "pages": None, "drafts": 0}
            ),
        )

    page = open_page(
        primed(browser, steady_state_origin),
        serve(
            leaf_page(
                "Cohort ownership",
                """
      <h1>Cohort ownership</h1><lf-test-seat id="seat"></lf-test-seat>
      <p id="subject">An ordinary source.</p><aside id="rail" style="height:300px;overflow:auto"></aside>
      <div id="foreign"></div>
    """,
            ).replace("<body>", '<body data-annotations="page">'),
            layer_registry={"lf-test-seat": entry},
            layer_widgets={"lf-test-seat.js": module},
            events=events,
        ),
    )
    _prepare_surface_refresh(page)
    page.evaluate("""async()=>{
      const app=await window.__lfWidgetApi();window.refresh=()=>refreshSurface(pageSurface);
      const rail=document.querySelector('#rail'); const outlet=document.createElement('div');outlet.dataset.lfGen='1';rail.append(outlet);
      window.pageSurface=app.placePageThreads(rail,async(targets,{signal})=>{
        if(window.holdNext){
          window.holdNext=false;
          window.heldPageSignal=signal;
          await new Promise(resolve=>window.releasePage=resolve);
        }
        return targets.map(()=>window.invalid?document.querySelector('#foreign'):outlet);
      });
    }""")
    expect(page.locator("#rail .lf-page-thread")).to_have_count(1)
    expect(page.locator("[data-seat=a] .lf-page-thread")).to_have_count(1)
    page.evaluate("""async () => {
      const {threadSurface}=await window.__lfWidgetApi();
      const seat=document.querySelector('#seat');
      threadSurface(seat).open(seat.querySelector('[data-lf-datum]'));
    }""")
    editor = page.locator(".lf-fab-input")
    expect(editor).to_be_focused()
    write(editor, "Keep this typing place.")
    editor.press("ArrowLeft")
    editor.press("Shift+ArrowLeft")
    before = editor.evaluate(
        "(field)=>[field.selectionStart,field.selectionEnd,field.selectionDirection]"
    )
    assert (
        page.evaluate(
            "document.querySelector('.lf-fab-bar').parentElement.dataset.seat"
        )
        == "a"
    )
    assert (
        page.evaluate("""async()=>{
      document.querySelector('#seat').side='b';window.invalid=true;await refresh();
      const {applicationPresented}=await window.__lfCheckApi();return applicationPresented();
    }""")
        is False
    )
    consume_browser_errors(page, "outside its presentation owner")
    expect(page.locator("[data-seat=a] .lf-page-thread")).to_have_count(1)
    expect(page.locator("[data-seat=b] .lf-page-thread")).to_have_count(0)
    expect(editor).to_be_focused()
    assert (
        editor.evaluate(
            "(field)=>[field.selectionStart,field.selectionEnd,field.selectionDirection]"
        )
        == before
    )
    assert (
        page.evaluate(
            "document.querySelector('.lf-fab-bar').parentElement.dataset.seat"
        )
        == "a"
    )
    assert page.evaluate(
        "document.querySelector('[data-seat=a]').hasAttribute('data-lf-thread-surface')"
    )
    assert not page.evaluate(
        "document.querySelector('[data-seat=b]').hasAttribute('data-lf-thread-surface')"
    )

    page.evaluate("async()=>{window.invalid=false;await refresh();}")
    expect(page.locator("[data-seat=b] .lf-page-thread")).to_have_count(1)
    expect(page.locator("[data-seat=a] .lf-page-thread")).to_have_count(0)
    expect(page.locator("#seat .lf-page-thread")).to_have_count(1)

    expect(editor).to_be_focused()
    assert (
        editor.evaluate(
            "(field)=>[field.selectionStart,field.selectionEnd,field.selectionDirection]"
        )
        == before
    )
    assert (
        page.evaluate(
            "document.querySelector('.lf-fab-bar').parentElement.dataset.seat"
        )
        == "b"
    )
    assert page.evaluate(
        "document.querySelector('[data-seat=b]').hasAttribute('data-lf-thread-surface')"
    )
    assert not page.evaluate(
        "document.querySelector('[data-seat=a]').hasAttribute('data-lf-thread-surface')"
    )

    # A cancelled preparation never moves the editor; newer native typing belongs to
    # the next current cohort, and releasing the stale callback cannot reclaim it.
    page.evaluate(
        "() => { document.querySelector('#seat').side='a'; window.holdNext=true; void refresh(); }"
    )
    page.wait_for_function('typeof window.releasePage === "function"')
    assert (
        page.evaluate(
            "document.querySelector('.lf-fab-bar').parentElement.dataset.seat"
        )
        == "b"
    )
    editor.press("End")
    editor.press_sequentially(" More")
    page.evaluate("() => { void refresh(); }")
    page.wait_for_function(
        "document.querySelector('.lf-fab-bar').parentElement.dataset.seat === 'a'"
    )
    assert page.evaluate("() => heldPageSignal.aborted") is True
    current = editor.evaluate(
        "(field)=>({value:field.value,caret:[field.selectionStart,field.selectionEnd,field.selectionDirection]})"
    )
    page.evaluate("async()=>{releasePage();await refresh();}")
    expect(editor).to_be_focused()
    assert (
        editor.evaluate(
            "(field)=>({value:field.value,caret:[field.selectionStart,field.selectionEnd,field.selectionDirection]})"
        )
        == current
    )
    assert (
        page.evaluate(
            "document.querySelector('.lf-fab-bar').parentElement.dataset.seat"
        )
        == "a"
    )

    # The widget can lose its contained outlet during the page callback itself.
    # Its already prepared fallback keeps the same native editor and typing place.
    page.evaluate(
        "()=>{delete window.releasePage;window.holdNext=true;void refresh();}"
    )
    page.wait_for_function('typeof window.releasePage === "function"')
    page.evaluate("""()=>{
      document.querySelector('#foreign').moveBefore(document.querySelector('[data-seat=a]'),null);
      releasePage();
    }""")
    # The widget's thread, its seat gone, joins the page's rail and draws at once.
    expect(page.locator("#rail .lf-page-thread")).to_have_count(2)
    page.wait_for_function(
        "document.querySelector('#rail').contains(document.querySelector('.lf-fab-bar'))"
    )
    consume_browser_errors(page, "outside its presentation owner")
    expect(editor).to_be_focused()
    assert (
        editor.evaluate(
            "(field)=>({value:field.value,caret:[field.selectionStart,field.selectionEnd,field.selectionDirection]})"
        )
        == current
    )
    # The widget stops offering its seat, so the page keeps presenting both threads.
    page.evaluate("""async()=>{
      const {threadSurface}=await window.__lfWidgetApi();
      const seat=document.querySelector('#seat');seat.side=null;threadSurface(seat).update();
    }""")
    expect(page.locator("#rail .lf-page-thread")).to_have_count(2)
    assert len(state_readings) == 1


def test_source_retired_during_required_reader_prepare_is_not_claimed(browser, serve):
    """A source nomination expires before placement if required preparation retires it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Source admission at commit",
                """
      <h1>Source review</h1><p id="subject">An ordinary durable target.</p>
      <button id="retire">Retire the target</button>
      <aside id="rail" style="height:220px;overflow:auto"></aside>
    """,
            ).replace("<body>", '<body data-annotations="page">'),
            anchored=[("subject", None)],
        ),
    )
    _prepare_surface_refresh(page)
    page.evaluate("""async()=>{
      const app=await window.__lfWidgetApi();
      const rail=document.querySelector('#rail');const outlet=document.createElement('div');outlet.dataset.lfGen='1';rail.append(outlet);
      window.surface=app.placePageThreads(rail,targets=>{
        window.offered=targets.map(({thread})=>thread.id);
        return targets.map(()=>outlet);
      });
      document.querySelector('#retire').onclick=()=>{document.querySelector('#subject').id='retired';};
      window.refresh=()=>refreshSurface(surface);
      await refresh();
    }""")
    _hold_required_thread_reader(page)
    expect(page.locator("#rail .lf-page-thread")).to_have_count(1)
    page.evaluate("()=>{window.holdPanel=true;void refresh();}")
    page.wait_for_function('typeof releasePanel === "function"')
    page.locator("#retire").click()
    assert page.locator("#subject").count() == 0
    page.evaluate("()=>releasePanel()")
    # `wait_for_function` takes an async predicate's promise as its answer, so the
    # reading is installed first and waited on synchronously.
    page.evaluate("""async()=>{
      window.__lfPresented=(await window.__lfCheckApi()).applicationPresented;
    }""")
    page.wait_for_function("()=>window.__lfPresented()")
    expect(page.locator("#rail .lf-page-thread")).to_have_count(0)
