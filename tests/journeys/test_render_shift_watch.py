"""The browser fixture fails the layout shifts "The page holds still under the user's aim" forbids
(`shift_watch.js`): a shift without input, and typing that carries its field."""


# Input attribution, the plane moved to, and the extra motion are independent, so each
# guard mode is paired with one destination, and each fault kind and axis with one mode,
# rather than crossed.

import re
from datetime import datetime, timedelta

import pytest
from browser.test_render_shift_watch import (
    CLIPPING_CASES,
    FRAMES,
    RESTYLES,
    _far_sample,
    moved_within,
    names_move,
    paint,
    restyle_page,
)
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE
from render_harness import (
    consume_browser_errors,
    judge_watches,
    leaf_page,
    open_page,
    refuse,
    resized,
    take_browser_errors,
    ticked,
)

from leaf.source.render_checks import rendered


def test_native_clipping_preserves_only_painted_carry(browser, serve):
    """Each case stands alone on one page in turn: its boxes shown, the others' out of
    the box tree, so no case's field stands under another's point or clip."""
    source = leaf_page(
        "Native clipping",
        "".join(
            f'<div id="case-{name}" hidden><div id="outer-{name}" style="{outer}">'
            f'<div style="{inner}"><textarea id="field-{name}" style="{field};width:14px;'
            'height:20px"></textarea></div></div></div>'
            for name, outer, inner, field, *_ in CLIPPING_CASES
        )
        + '<div id="evidence" style="position:absolute;left:10px;top:400px;width:300px;'
        'height:30px;background:red"></div>',
        layout=None,
    )
    page = open_page(browser, serve(source))
    for name, _, _, _, hit, painted, delta in CLIPPING_CASES:
        page.evaluate(
            "name => document.getElementById(`case-${name}`).hidden = false", name
        )
        paint(page)
        field = page.locator(f"#field-{name}")
        state = field.evaluate("""async field=>{
          const box=field.getBoundingClientRect();
          const geometry=await window.__lfCheckApi();
          return {hit:document.elementFromPoint(box.x+3,box.y+3)===field,
            shown:!!geometry.shownRect(field,new Map()),
            opacity:field.checkVisibility({checkOpacity:true})};
        }""")
        assert state == {
            "hit": hit,
            "shown": hit,
            "opacity": painted or hit is False,
        }, name
        before = field.bounding_box()
        field.evaluate(
            """(field, delta)=>{
          window.nativeClipEntries=[];
          window.nativeClipObserver?.disconnect();
          window.nativeClipObserver=new PerformanceObserver(list=>nativeClipEntries.push(...list.getEntries()));
          nativeClipObserver.observe({type:'layout-shift'});
          field.style.marginLeft=delta+'px';
          evidence.style.marginLeft=evidence.style.marginLeft==='40px'?'0px':'40px';
        }""",
            delta,
        )
        page.screenshot()
        judge_watches()
        errors = take_browser_errors(page)
        assert page.evaluate("nativeClipEntries.length"), name
        after = field.bounding_box()
        assert after["x"] - before["x"] == (6 if delta == 3 else delta), name
        if painted:
            assert names_move(errors, f"textarea#field-{name}"), (name, errors)
        else:
            assert errors == [], (name, errors)
        page.evaluate(
            "name => document.getElementById(`case-${name}`).hidden = true", name
        )
        paint(page)
        judge_watches()
        assert take_browser_errors(page) == [], name


def test_an_unchanged_frame_misses_no_restyle(browser):
    """An idle frame keeps its last reading (`shift_watch.js`, "Unchanged frames").

    A change no source announces fails the test, naming the innermost node that
    changed; each change that restyles without a DOM write is announced, so the
    periodic full reading finds nothing. The unannounced change runs first, while
    nothing animates; the announced ones then run in turn on the same page, the shadow
    transition last so it is still running when the sensor checks.
    """
    page = restyle_page(browser)
    for call, (script, words, settled) in [
        ("unannounced", RESTYLES["unannounced"]),
        *((call, case) for call, case in RESTYLES.items() if call != "unannounced"),
    ]:
        page.evaluate(script)
        expect(page.locator(words)).to_have_css(*(settled or ("opacity", "0.5")))
        if call == "unannounced":
            # More frames than the sensor's check interval.
            page.evaluate(FRAMES, 90)
            judge_watches()
            consume_browser_errors(
                page,
                {
                    "code": "shift-watch-missed",
                    "node": ["#text", "p#unheard"],
                    "changed": ["opacity"],
                    "others": 1,
                },
            )
    page.evaluate(FRAMES, 90)
    judge_watches()


@pytest.mark.parametrize("surface", ["card", "inline"])
def test_message_age_may_shift_metadata_but_leaves_the_thread_in_place(
    browser, serve, surface
):
    """As days pass, a message's head says when it was said with more words, from how
    long ago ("just now") to "Yesterday" and its time, then its date and time, while
    the thread and its controls stay put.

    Metadata may move or stay reserved. The passive-region fault controls above
    exercise the watcher's permitted motion independently of this surface's layout.
    """
    source = (
        leaf_page(
            "Inline task thread",
            '<h1 id="title">Before the frost</h1><lf-test-plan id="jobs" label="Jobs">'
            '<lf-test-task id="bracket" status="active" talk>'
            "<strong>Which jobs can share a visit?</strong></lf-test-task></lf-test-plan>",
        )
        if surface == "inline"
        else OBLIGATION_PAGE
    )
    page = open_page(
        browser,
        serve(
            source,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Check whether these jobs can share one visit.",
                    "anchor": {"section": "bracket"},
                }
            ],
        ),
    )
    resized(page, 1440, 900)
    if surface == "card":
        page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
        surface_root = page.locator(".lf-margin-preview")
    else:
        surface_root = page.locator(".lf-page-thread[data-lf-runtime]")
    header = surface_root.locator(".lf-msg-head").first
    receipt = header.locator(".lf-msg-sending")
    timestamp = header.locator("time")
    expect(receipt).to_have_text(re.compile(r"^Queued for "))
    expect(timestamp).to_have_text(re.compile(r"^(just now|\d+m ago)$"))
    # The time of day the head says once the message is a day old, as the browser
    # writes it (state/presence.js, `timeOfDay`).
    clock = timestamp.evaluate(
        "node => new Date(node.dateTime)"
        ".toLocaleTimeString(undefined, {timeStyle: 'short'})"
    )
    # Age changes are news after Chrome's recent-input grace, even when opening the
    # surface and resizing it happened immediately before this clock transition.
    rendered(page)
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    protected = surface_root.locator("b, button, leaf-text, .lf-msg-body")
    boxes = "nodes => nodes.map(node => node.getBoundingClientRect().toJSON())"
    before = protected.evaluate_all(boxes)
    assert before
    thread_before = surface_root.bounding_box()
    owner = header.locator("xpath=..")
    owner_before = owner.bounding_box()
    page.route("**/api/state*", refuse)
    now = datetime.now().astimezone()
    for delta, age in [
        (timedelta(days=1), f"Yesterday {clock}"),
        (timedelta(days=3), re.compile(rf"^\w+ \d{{1,2}} {re.escape(clock)}$")),
    ]:
        # Fixed Date advances the age without changing Chrome's monotonic clock;
        # LayoutShift, frame readings and input attribution still share native time.
        page.clock.set_fixed_time(now + delta)
        ticked(page)
        expect(timestamp).to_have_text(age)
        expect(receipt).to_have_text(re.compile(r"^Queued for "))
        judge_watches()
        assert surface_root.bounding_box() == thread_before
        assert owner.bounding_box() == owner_before
        assert protected.evaluate_all(boxes) == before


def test_a_jump_owns_the_fit_of_the_live_sample_it_brings_near(browser, serve):
    """A link that jumps to a live sample far down starts its page there (`whenNear`),
    and the frame fits that page as soon as it draws, carrying what follows it: the
    jump owns that landing, however late it comes. It owns nothing after the landing,
    so a control that moves once the frame has fitted is reported. A sample a script
    brings near, with no input, fits as news, and its fit is reported too."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Fit on arrival",
                '<p><a id="jump" href="#far">Jump to the sample</a></p>'
                '<div style="height: 400vh"></div>'
                + _far_sample("far", "after")
                + '<div style="height: 400vh"></div>'
                + _far_sample("scripted", "later")
                + '<div style="height: 100vh"></div>',
            )
        ),
    )
    fitted = """sample => {
        const frame = sample.querySelector('iframe');
        return sample.ready.then(() => frame.clientHeight < 300);
    }"""
    page.locator("#jump").click()
    page.wait_for_function(f"({fitted})(document.querySelector('#far'))")
    rendered(page)
    judge_watches()
    assert page.lf_errors == []

    page.locator("#after").evaluate("node => { node.style.marginTop = '40px'; }")
    rendered(page)
    judge_watches()
    consume_browser_errors(page, moved_within("button#after"))

    page.locator("#scripted").evaluate(
        "sample => sample.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    page.wait_for_function(f"({fitted})(document.querySelector('#scripted'))")
    rendered(page)
    judge_watches()
    moved = consume_browser_errors(page, {"code": "moved-without-input"})
    assert names_move(moved, "button#later"), moved
