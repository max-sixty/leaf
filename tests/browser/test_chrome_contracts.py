"""Everyday browser contracts for shared chrome."""

import io
import json
import re
from urllib.parse import urljoin

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.media import store_uploaded_media
from leaf.render_checks import rendered
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    SUGGESTION_PAGE,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    toggle_queue,
    token_colour,
    with_one_ask,
)
from render_cases_navigation import _publish
from render_harness import (
    LONG_PAGE,
    leaf_page,
    open_page,
    open_versions,
    panel_settled,
    resized,
    scroll_settled,
    select,
    told,
    write,
)

# A followed thread shows the arriving turn's newest words in the list's landing band.
FOLLOWED = """id => {
  const list = document.querySelector('.lf-threads');
  const box = list.getBoundingClientRect();
  const fold = box.bottom - parseFloat(getComputedStyle(list).scrollPaddingBottom);
  const tail = list.querySelector(`.lf-msg[data-mid="${id}"]`).getBoundingClientRect().bottom;
  return tail > box.top && tail <= fold + 2;
}"""


# Where an open card's reply box stands, the field the caret is drawn in, and the
# caret itself: the field holding focus and the selection in it; and the list's scroll.
REPLY_BOX = """card => {
  const box = card.querySelector(':scope > .lf-thread-reply');
  const field = box.querySelector('leaf-text');
  const at = (el) => { const r = el.getBoundingClientRect(); return [r.top, r.bottom]; };
  return {
    box: at(box),
    field: at(field),
    caret: [document.activeElement === field, field.selectionStart, field.selectionEnd],
    scroll: card.parentElement.scrollTop,
  };
}"""


def test_tab_into_a_long_thread_lands_above_its_pinned_reply_row(browser, serve):
    """A long thread's reply row is pinned over the turns that scroll under it. Tab
    onto a control there once left it under the row: the browser scrolls focus into
    view only out of the list's box, and the row is inside it. The turns now keep the
    row's height clear below a landing, its ring included, while the row itself
    keeps none, since the caret lives in it and typing must not scroll the list."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "A thread long enough to Tab through.")
    for index in range(14):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": f"Answer {index}. " * 12,
            },
        )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    if card.get_attribute("open") is None:
        card.locator(":scope > .lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    # Stand one reaction button just under the row's top and focus the one before it.
    placed = card.evaluate(
        """card => {
          const list = card.parentElement;
          const reply = card.querySelector(':scope > .lf-thread-reply');
          const triggers = [...card.querySelectorAll('.lf-msg.agent .lf-react-trigger')];
          const target = triggers[Math.floor(triggers.length / 2)];
          list.scrollTop += target.getBoundingClientRect().top
            - reply.getBoundingClientRect().top - 8;
          triggers[triggers.indexOf(target) - 1].focus({preventScroll: true});
          target.dataset.tabTarget = '';
          const t = target.getBoundingClientRect(), r = reply.getBoundingClientRect();
          return {under: t.top > r.top && t.top < r.bottom};
        }"""
    )
    assert placed["under"], placed
    page.keyboard.press("Tab")
    target = card.locator("[data-tab-target]")
    expect(target).to_be_focused()
    page.wait_for_function(
        """() => {
          const t = document.querySelector('[data-tab-target]').getBoundingClientRect();
          const r = document.querySelector('.lf-threads > .lf-thread[open] > .lf-thread-reply')
            .getBoundingClientRect();
          return t.bottom <= r.top;
        }"""
    )
    landed = target.evaluate(
        """el => {
          const row = el.closest('.lf-thread').querySelector(':scope > .lf-thread-reply');
          // The row stands the ring's room above the list's foot.
          const ring = parseFloat(getComputedStyle(row).bottom);
          const t = el.getBoundingClientRect();
          const r = row.getBoundingClientRect();
          const hit = document.elementFromPoint((t.left + t.right) / 2, (t.top + t.bottom) / 2);
          return {clear: r.top - t.bottom, ring, shown: el === hit || el.contains(hit)};
        }"""
    )
    assert landed["ring"] > 0 and landed["clear"] >= landed["ring"] - 0.5, landed
    assert landed["shown"], landed
    # Typing several lines in the row while it is pinned mid-thread keeps the reader
    # there. The list follows the growing draft, but a cover around the caret made the
    # browser carry it to the thread's end on every key.
    threads = page.locator(".lf-threads")
    card.evaluate(
        "card => card.parentElement.scrollTop = card.offsetTop"
        " + (card.offsetHeight - card.parentElement.clientHeight) / 2"
    )
    field = card.locator(".lf-thread-reply leaf-text")
    field.click()
    before = threads.evaluate("el => el.scrollTop")
    write(field, ("A draft line.\n" * 4).strip())
    page.evaluate("() => new Promise(requestAnimationFrame)")
    after = threads.evaluate("el => [el.scrollTop, el.scrollHeight - el.clientHeight]")
    assert before <= after[0] < after[1] - 200, (before, after)


def test_another_threads_reply_keeps_the_selected_thread_in_place(browser, serve):
    url = serve(LONG_PAGE)
    other = panel_comment(serve.page_dir, "An earlier thread.")
    selected = panel_comment(serve.page_dir, "The selected thread.")
    for index in range(14):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": selected,
                "text": f"Selected answer {index}. " * 5,
            },
        )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{selected}"]')
    card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    threads = page.locator(".lf-threads")
    threads.evaluate("el => el.scrollTop = el.scrollHeight")
    last_selected = card.locator(".lf-msg").last
    before = last_selected.evaluate("el => el.getBoundingClientRect().top")

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": other,
            "text": "This belongs to the other thread. " * 5,
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    expect(card).to_have_attribute("open", "")
    assert last_selected.evaluate(
        "el => el.getBoundingClientRect().top"
    ) == pytest.approx(before, abs=2)


class _ProblemPage:
    url = "https://leaf.test/example"

    def add_init_script(self, **_):
        pass

    def expose_binding(self, *_):
        pass

    def on(self, *_):
        pass


def test_live_revision_retains_the_runtime_favicon(browser, serve):
    """In-place activation keeps the banner's runtime-owned tab status surface."""
    second = LONG_PAGE.replace("<title>long</title>", "<title>second</title>")
    page = open_page(browser, live_url(serve(LONG_PAGE)))
    page.evaluate(
        "() => { window.__lfFavicon = document.querySelector('link[rel=icon]'); }"
    )

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("second")
    assert page.evaluate(
        """() => window.__lfFavicon ===
          document.querySelector('link[rel=icon][data-lf-runtime]')"""
    ), "in-place activation replaced or removed the runtime favicon"


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_margin_reply_shares_its_threads_opaque_surface(browser, serve, scheme):
    """The reply surround stays continuous as focus enters and leaves the thread.

    An opaque shared surface also lets a pinned reply cover scrolled messages without
    introducing a differently colored band above its input.
    """
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(browser, url, color_scheme=scheme)
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    preview = page.locator(".lf-margin-preview")
    thread = preview.locator(".lf-page-thread")
    surround = thread.locator(".lf-thread-reply")
    reply = preview.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_be_visible()

    for state in ("resting", "editing", "outside"):
        if state == "editing":
            reply.click()
            expect(reply).to_be_focused()
        elif state == "outside":
            preview.get_by_role("button", name="Dismiss thread").focus()
        surface = thread.evaluate("""node => {
          const color = getComputedStyle(node).backgroundColor;
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 1;
          const paint = canvas.getContext('2d');
          paint.fillStyle = color;
          paint.fillRect(0, 0, 1, 1);
          return {color, alpha: paint.getImageData(0, 0, 1, 1).data[3]};
        }""")
        assert surface["alpha"] == 255, (scheme, state, surface)
        expect(surround).to_have_css("background-color", surface["color"])


def test_a_thread_news_resolves_stays_where_it_stands_until_the_user_moves_on(
    browser, serve
):
    """Under Open, the agent resolving the thread the user is reading used to fold its
    card away, and every card after it rose. The card stays where it stands, drawn as
    it was, with the resolution behind its notice, and the news taking the resolution
    back leaves nothing to hold; the browser fixture's shift watch fails anything that
    moves. Its title stops saying whose turn it is, since nobody's is, without moving
    the card below it. The news lands well after the user's last input, past the half second in
    which Chrome credits a frame to that input.

    The card leaves the Open list once its going moves nothing the user sees. As the
    open card it stays while they scroll it away, since another card would open in its
    place. Once they have opened another card, it goes as they scroll it out of the
    window, and scrolling back does not bring it back."""
    # Enough closed rows follow the open card to scroll that whole card off screen.
    url = serve(LONG_PAGE, comments=32)
    first, second = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ][:2]
    # The thread waits on the user, so its title has a turn to stop saying.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": first,
            "text": "Which of the two should stay?",
            "ask": True,
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-threads > .lf-thread[data-id="{first}"]')
    after = page.locator(f'.lf-threads > .lf-thread[data-id="{second}"]')
    expect(card).to_have_attribute("open", "")
    control = card.get_by_role("button", name="Resolve thread").bounding_box()
    below = after.bounding_box()
    status = card.locator(".lf-thread-status")
    expect(status).to_be_visible()
    page.wait_for_function(
        "at => performance.now() - at > 600", arg=page.evaluate("performance.now()")
    )

    for kind in ["resolve", "unresolve", "resolve"]:
        append_carried_log_record(
            serve.page_dir, {"kind": kind, "author": "agent", "parent": first}
        )
        told(page)
        rendered(page)
        expect(card.get_by_role("button", name="Resolved", exact=True)).to_have_count(
            int(kind == "resolve")
        )
        expect(card).to_have_attribute("data-resolved", "false")
        expect(card).to_have_attribute("open", "")
        assert after.bounding_box() == below
    resolve = card.get_by_role("button", name="Resolve thread")
    assert resolve.bounding_box() == control
    expect(status).to_have_count(0)

    threads = page.locator(".lf-threads")
    threads.hover()
    page.mouse.wheel(0, card.bounding_box()["height"] + 30)
    scroll_settled(page, ".lf-threads")
    assert card.evaluate("node => node.getBoundingClientRect().bottom") < (
        threads.evaluate("list => list.getBoundingClientRect().top")
    ), "the scroll left the resolved card in view, so it tests nothing"
    rendered(page)
    expect(card).to_be_visible()
    expect(card).to_have_attribute("open", "")

    after.locator(".lf-thread-summary").click()
    expect(after).to_have_attribute("open", "")
    # Opening a card lands it below a sliver of the closed one, which still shows.
    page.mouse.wheel(0, 100)
    expect(card).to_be_hidden()
    scroll_settled(page, ".lf-threads")
    page.mouse.wheel(0, -4000)
    scroll_settled(page, ".lf-threads")
    assert threads.evaluate("list => list.scrollTop") == 0
    expect(card).to_be_hidden()


def test_news_that_answers_a_thread_waiting_on_you_leaves_its_card_in_place(
    browser, serve
):
    """Under "Waiting on me", the user's answer from another tab takes the thread out
    of the view. Its card, open in front of them, stays where it stands, and its
    summary's title row stays the same size when the answered status disappears; the
    browser fixture's shift watch fails anything that moves. The news lands well after
    the user's last input."""
    url = serve(PANEL_PAGE)
    asked = panel_comment(serve.page_dir, "Is forty enough?", author="agent")
    other = panel_comment(serve.page_dir, "A thread waiting on nobody.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator(".lf-needs").click()
    card = page.locator(f'.lf-thread[data-id="{asked}"]')
    expect(page.locator(f'.lf-thread[data-id="{other}"]')).to_be_hidden()
    card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    stood = card.locator(".lf-thread-summary").bounding_box()
    page.wait_for_function(
        "at => performance.now() - at > 600", arg=page.evaluate("performance.now()")
    )

    append_carried_log_record(
        serve.page_dir,
        {"kind": "reply", "author": "user", "parent": asked, "token": "keep"},
    )
    told(page)
    expect(page.locator(".lf-needs")).to_have_text("Me (0)")
    rendered(page)
    expect(card).to_be_visible()
    assert card.locator(".lf-thread-summary").bounding_box() == stood


# The long agent name stands on the phone's narrow card, where it has least room.
@pytest.mark.parametrize(
    ("agent", "touch"),
    [("Codex", False), ("Maximilian Roos Research Assistant", True)],
)
def test_resolved_thread_has_one_surface_and_reopens_from_its_title(
    browser, serve, touch, agent
):
    """A resolved card keeps its ground and a reachable action beside its age.

    Pressing that action reopens the conversation without folding its disclosure;
    the button's accessible name names the action while its visible face says the state.
    """
    context = browser.new_context(
        viewport={"width": 390 if touch else 800, "height": 900},
        has_touch=touch,
        is_mobile=touch,
        reduced_motion="reduce",
    )
    url = serve(
        leaf_page(
            "Resolved thread",
            '<h1>Resolved thread</h1><p id="subject">A shared surface.</p>',
        )
    )
    root = panel_comment(
        serve.page_dir, "Keep this discussion together.", {"section": "subject"}
    )
    for event in (
        {
            "kind": "reply",
            "parent": root,
            "text": "The answer has several paragraphs.\n\nIts margins are part of the card.",
        },
        {"kind": "thread_title", "thread": root, "title": "A shared surface"},
        {"kind": "resolve", "parent": root},
    ):
        append_carried_log_record(
            serve.page_dir, {"author": "agent", "agent": agent, **event}
        )
    other = panel_comment(serve.page_dir, "Another resolved discussion.")
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": other}
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-kind="status"][data-filter-value="resolved"]').click()
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    summary = thread.locator(".lf-thread-summary")
    reopen = thread.get_by_role("button", name="Reopen", include_hidden=True)
    collapsed = page.locator(f'.lf-threads > .lf-thread[data-id="{other}"]')
    expect(collapsed).not_to_have_attribute("open", "")
    expect(
        collapsed.get_by_role("button", name="Reopen", include_hidden=True)
    ).to_be_hidden()
    expect(thread).to_have_attribute("open", "")
    assert reopen.evaluate("button => button.parentElement.tagName") == "DETAILS"
    rendered(page)
    image = Image.open(io.BytesIO(thread.screenshot())).convert("RGB")
    start = int(summary.bounding_box()["height"]) + 4
    # The clear strip inside the border crosses message margins and the card's foot.
    # Separate child backgrounds leave panel-colored bands along this strip.
    assert len({image.getpixel((3, y)) for y in range(start, image.height - 2)}) == 1
    expect(reopen).to_have_text(f"✓ Resolved by {agent}")
    expect(reopen).to_have_attribute(
        "aria-label", f"✓ Resolved by {agent} · Reopen thread"
    )
    expect(reopen).to_have_attribute("title", f"✓ Resolved by {agent} · Reopen thread")
    assert reopen.evaluate("""button => {
        const r = button.getBoundingClientRect();
        return [r.top + 1, r.bottom - 1].every(y =>
            button.contains(document.elementFromPoint(r.x + r.width / 2, y)));
    }"""), "The whole Reopen target must take the press, including its top and bottom."
    assert reopen.bounding_box()["height"] >= float(
        page.locator("body")
        .evaluate('node => getComputedStyle(node).getPropertyValue("--aim-floor")')
        .strip()
        .removesuffix("px")
    )
    boxes = thread.evaluate("""node => ['.lf-thread-header-action', '.lf-thread-recency'].map(sel => {
        const range = document.createRange(); range.selectNodeContents(node.querySelector(sel));
        const r = range.getBoundingClientRect(); return {top:r.top, bottom:r.bottom};
    })""")
    assert boxes[0] == boxes[1]
    if touch:
        reopen.tap()
    else:
        summary.focus()
        page.keyboard.press("Tab")
        expect(reopen).to_be_focused()
        page.keyboard.press("Enter")
    told(page)
    expect(thread).to_have_attribute("data-resolved", "false")
    expect(thread).to_have_attribute("open", "")
    expect(thread.locator(".lf-thread-reply leaf-text")).to_be_visible()
    assert (
        len(
            [
                event
                for event in events_model.read_events(serve.page_dir)
                if event["kind"] == "unresolve" and event["parent"] == root
            ]
        )
        == 1
    )


def test_a_compact_comment_reserves_only_the_room_send_occupies(browser, serve):
    """At a narrow allocation, Space must not create a blank line while the
    words and Send still fit. The text's right inset already clears part of
    Send's hit box; reserving its full width again wasted eleven pixels."""
    page = open_page(
        browser,
        serve(
            leaf_page("Compact comment", '<p id="passage">A passage to comment on.</p>')
        ),
    )
    resized(page, 346, 900)
    page.locator("#passage").click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.insert_text("this is a nice feature; is it in leaf, or you")
    rendered(page)
    before = field.bounding_box()
    page.keyboard.press("Space")
    rendered(page)
    after = field.bounding_box()
    assert after["height"] == pytest.approx(before["height"], abs=1)
    assert after["y"] == pytest.approx(before["y"], abs=1)
    reservation = field.evaluate("""el => {
      const style = getComputedStyle(el), box = el.getBoundingClientRect();
      const send = el.parentElement.querySelector('.lf-compose-submit').getBoundingClientRect();
      return {textEnd: box.right - parseFloat(style.borderInlineEndWidth)
        - parseFloat(style.paddingInlineEnd)
        - parseFloat(style.getPropertyValue('--lf-field-end-room')),
        sendStart: send.left};
    }""")
    assert reservation["textEnd"] == pytest.approx(reservation["sendStart"], abs=0.1)


# Two threads put the card's navigation on the row too, which a finger's larger
# controls leave least room for.
@pytest.mark.parametrize(("touch", "thread_count"), [(False, 1), (True, 2)])
def test_page_thread_dismiss_and_resolve_share_the_metadata_row(
    browser, serve, thread_count, touch
):
    context = browser.new_context(
        viewport={"width": 900, "height": 844}, is_mobile=touch, has_touch=touch
    )
    url = serve(LONG_PAGE)
    for index in range(thread_count):
        panel_comment(serve.page_dir, f"Comment {index}.", {"section": "p0"})
    page = open_page(browser, url, context=context)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').first.click()
    preview = page.locator(".lf-margin-preview:not([hidden])")
    resolve = preview.get_by_role("button", name="Resolve thread")
    dismiss = preview.get_by_role("button", name="Dismiss thread view")
    expect(resolve).to_be_visible()
    expect(dismiss).to_be_visible()
    assert dismiss.evaluate(
        "button => button.closest('.lf-margin-thread-controls') !== null"
    )
    centers = preview.evaluate(
        """preview => ['.lf-resolve', '.lf-margin-preview-close'].map(selector => {
          const rect = preview.querySelector(selector).getBoundingClientRect();
          return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2};
        })"""
    )
    assert centers[0]["y"] == pytest.approx(centers[1]["y"], abs=1), centers
    assert centers[0]["x"] < centers[1]["x"]
    if thread_count == 2:
        row = preview.evaluate(
            """preview => {
              const actions = preview.querySelector('.lf-margin-thread-controls');
              const head = preview.querySelector('.lf-thread-transcript .lf-msg-head');
              const box = selector => preview.querySelector(selector)
                .getBoundingClientRect();
              const middle = selector => box(selector).y + box(selector).height / 2;
              return {
                nav: middle('.lf-margin-preview-nav'),
                author: middle('.lf-thread-transcript .lf-msg-head > b'),
                actions: middle('.lf-thread-meta-actions'),
                authorRight: head.getBoundingClientRect().right
                  - parseFloat(getComputedStyle(head).paddingInlineEnd),
                navLeft: box('.lf-margin-preview-nav').left,
                navRight: box('.lf-margin-preview-nav').right,
                resolveLeft: box('.lf-resolve').left,
                overflow: actions.scrollWidth - actions.clientWidth
                  + head.scrollWidth - head.clientWidth,
              };
            }"""
        )
        assert row["nav"] == pytest.approx(row["actions"], abs=1), row
        assert row["author"] == pytest.approx(row["actions"], abs=1), row
        assert row["authorRight"] < row["navLeft"], row
        assert row["navRight"] < row["resolveLeft"], row
        assert row["overflow"] == 0, row
    dismiss.focus()
    resized(page, 1000, 844)
    expect(dismiss).to_be_focused()
    resolve.focus()
    page.keyboard.press("Tab")
    expect(dismiss).to_be_focused()
    dismiss.focus()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-thread-summary:focus")).to_have_count(1)


STATE_PAINT = """el => {
  const style = getComputedStyle(el);
  return {background: style.backgroundColor, shadow: style.boxShadow};
}"""


def test_signoff_enabled_face_is_readable(browser, serve):
    """The banner's committing action carries the accent as ink on the ordinary
    card, never as a solid accent fill."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_be_enabled()
    paint = button.evaluate(
        "el => ({ink: getComputedStyle(el).color, "
        "        fill: getComputedStyle(el).backgroundColor})"
    )
    assert paint == {
        "ink": token_colour(page, "--accent"),
        "fill": token_colour(page, "--card"),
    }, f"the banner's primary action lost its readable face: {paint}"


def test_the_approved_face_keeps_the_buttons_inset(browser, serve):
    """The approval control reserves the width of its longest words, "✓ Version
    approved", and those words stand inside it with the inset every chrome button
    keeps. With 2px of padding they filled the reserved box to the border."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    resized(page, 1440, 900)
    button = page.locator(".lf-signoff")
    button.click()
    expect(button).to_have_text("✓ Version approved")
    inset = button.evaluate(
        """el => {
          const box = el.getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(el);
          const words = range.getBoundingClientRect();
          return [words.left - box.left, box.right - words.right];
        }"""
    )
    assert min(inset) >= 8, f"the approved words stand {inset}px from the border"


def test_the_version_being_read_spans_the_versions_menu(browser, serve):
    """The row for the version being read has no Compare beside it, so it takes both of
    the menu's columns: it was only as wide as its own words, its hover and ring
    stopping short of the rows below. The rows wear the menu's own type."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    _publish(serve.page_dir, 2, html, "reworded the suggestion")
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    resized(page, 1440, 900)
    open_versions(page)
    versions = page.locator(".lf-version-menu")
    expect(versions).to_be_visible()
    reading = versions.evaluate(
        """menu => {
          const style = getComputedStyle(menu);
          const inner = menu.getBoundingClientRect().width
            - 2 * parseFloat(style.borderLeftWidth)
            - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
          const current = menu.querySelector('.lf-version-row[aria-current]');
          return {inner, current: current.getBoundingClientRect().width,
                  font: getComputedStyle(current).fontSize,
                  menuFont: style.fontSize};
        }"""
    )
    assert reading["current"] == pytest.approx(reading["inner"], abs=1), reading
    assert reading["font"] == reading["menuFont"], reading


def test_a_refused_approval_says_why_to_the_keyboard_and_the_finger(browser, serve):
    """Approval waits until every Ask is answered, and the control says so to whoever
    reaches it. Natively disabled, it held its reason in `title` alone: Tab skipped it,
    so a keyboard user never learned why, and a finger never sees a title. It stays in
    the tab order, refused by `aria-disabled` and described by its reason, and a press
    shows the reason in the status line rather than approving."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    approval = page.locator(".lf-signoff")
    reason = "Answer every ask before approving this work"
    expect(approval).to_have_attribute("aria-disabled", "true")
    expect(approval).to_have_attribute("aria-description", reason)
    expect(approval).to_be_disabled()
    # On the desk row Approval stands just before Comment on the page.
    page.locator(".lf-page-comment").focus()
    page.keyboard.press("Shift+Tab")
    expect(approval).to_be_focused()
    before = events_model.read_events(serve.page_dir)
    page.keyboard.press("Enter")
    expect(page.locator(".lf-bottom-status .lf-notice")).to_have_text(reason)
    expect(approval).to_have_text("Approve version")
    assert events_model.read_events(serve.page_dir) == before


@pytest.mark.watch_shifts
@pytest.mark.parametrize(
    "width,touch,ui_size",
    [
        (1200, False, 14),
        (630, False, 14),
        (629, False, 14),
        (500, False, 14),
        (320, True, 20),
        (631, False, 20),
    ],
)
def test_approval_capability_changes_keep_banner_targets(
    browser, serve, width, touch, ui_size
):
    """Approval arriving or leaving cannot change chrome allocation or a resting aim.

    The widths straddle the capacity boundary, include the former page-dependent
    interval, and retain access with enlarged UI text. Native shift watching also
    protects movement between the settled reads.
    """
    original = leaf_page("Reading", '<h1 id="reading">A place to read</h1>').replace(
        "</head>", f"<style>:root {{ --t-5: {ui_size}px; }}</style></head>"
    )
    approval = original.replace(
        "<title>Reading</title>",
        '<title>Reviewing</title><meta name="lf-review" content="sign-off">',
    )
    context = browser.new_context(
        viewport={"width": width, "height": 900}, has_touch=touch, is_mobile=touch
    )
    page = open_page(browser, live_url(serve(original)), context=context)
    resized(page, width, 900)
    selectors = (
        ".lf-banner",
        ".lf-banner-status",
        ".lf-banner-actions",
        ".lf-threads-toggle",
        ".lf-banner-more",
        "#reading",
    )

    def boxes():
        return {
            selector: page.locator(selector).bounding_box() for selector in selectors
        }

    before = boxes()
    more = page.locator(".lf-banner-more")
    more_box = before[".lf-banner-more"]
    aim = (
        more_box["x"] + more_box["width"] / 2,
        more_box["y"] + more_box["height"] / 2,
    )
    page.mouse.move(*aim)
    more.focus()
    expect(more).to_be_focused()
    for source, title, present in (
        (approval, "Reviewing", True),
        (original, "Reading", False),
    ):
        page.wait_for_timeout(600)  # End Chrome's native recent-input grace.
        (serve.page_dir / "index.html").write_text(source)
        told(page)
        expect(page).to_have_title(title)
        rendered(page)
        # A phone seats Approval at the head of More rather than on the row.
        seat = ".lf-banner-actions" if width > 480 else ".lf-banner-menu"
        if present:
            expect(page.locator(f"{seat} > .lf-signoff")).to_have_count(1)
            if width > 480:
                expect(
                    page.get_by_role("button", name="Approve version", exact=True)
                ).to_be_visible()
        else:
            expect(page.locator(".lf-signoff")).to_be_hidden()
        after = boxes()
        assert after[".lf-banner-status"]["width"] >= 150
        reserved_height = page.evaluate(
            "parseFloat(getComputedStyle(document.body, '::before').height)"
        )
        assert after[".lf-banner"]["height"] == pytest.approx(reserved_height, abs=0.5)
        for selector in (".lf-signoff", ".lf-threads-toggle", ".lf-banner-more"):
            target = page.locator(selector)
            if target.is_visible():
                box = target.bounding_box()
                assert box["x"] >= 0 and box["x"] + box["width"] <= width
                if touch:
                    assert box["width"] >= 43.5 and box["height"] >= 43.5
        for selector in selectors:
            assert after[selector] == pytest.approx(before[selector], abs=0.5), (
                selector,
                before,
                after,
            )
        expect(more).to_be_focused()
        assert page.evaluate(
            "([x,y]) => document.elementFromPoint(x,y).closest('.lf-banner-more') !== null",
            aim,
        )
        page.keyboard.press("Enter")
        menu = page.locator(".lf-banner-menu")
        expect(menu).to_be_visible()
        menu_box = menu.bounding_box()
        assert menu_box["x"] >= 0 and menu_box["x"] + menu_box["width"] <= width
        page.keyboard.press("Escape")
        expect(menu).to_be_hidden()
        expect(more).to_be_focused()


@pytest.mark.parametrize("width", [320, 1440])
def test_more_menu_stays_put_when_the_layer_age_gains_a_digit(browser, serve, width):
    """A clock tick can change a menu label without moving its other controls."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, width, 844)
    page.locator(".lf-banner-more").click()
    menu = page.locator(".lf-banner-menu")
    expect(menu).to_be_visible()
    version = menu.locator(".lf-layer-reference")
    expect(version).to_be_visible()

    def age_at(minutes):
        page.evaluate(
            """async minutes => {
              const {observeServerNow, tickClock} = await window.__lfRuntimeImport(
                '/runtime/presence.js');
              const title = document.querySelector('.lf-layer-reference').title;
              const stamp = title.match(/(?:committed|installed): ([^\\n]+)/)?.[1];
              if (!stamp) throw new Error(`Layer has no dated provenance: ${title}`);
              observeServerNow(new Date(Date.parse(stamp) + minutes * 60000).toISOString());
              await tickClock(error => { throw new Error(error); });
            }""",
            minutes,
        )
        rendered(page)

    age_at(9)
    expect(version).to_contain_text("9m ago")
    before = menu.bounding_box()
    control = menu.locator(".lf-version")
    control_before = control.bounding_box()
    age_at(10)
    expect(version).to_contain_text("10m ago")
    assert menu.bounding_box()["x"] == pytest.approx(before["x"], abs=0.5)
    assert control.bounding_box()["x"] == pytest.approx(control_before["x"], abs=0.5)


def test_notices_stay_at_the_visible_pages_right_edge(browser, serve):
    """A notice keeps the page's right corner through panel and viewport changes."""
    page = open_page(browser, serve(LONG_PAGE))
    notice = page.locator(".lf-notice")
    # The panel normally has the same card ground as the notice. Give it a contrasting
    # ground so the pixel reading also detects the panel covering the feedback.
    page.locator(".lf-thread-panel").evaluate(
        "panel => { panel.style.background = 'rgb(255, 0, 255)'; }"
    )
    for width, panel_open in [
        (1200, False),
        (1200, True),
        (390, True),
        (320, True),
        (390, False),
        (300, False),
    ]:
        resized(page, width, 800)
        if panel_open != page.locator(".lf-thread-panel").is_visible():
            if panel_open:
                page.locator(".lf-threads-toggle").click()
            else:
                page.get_by_role("button", name="Close threads", exact=True).click()
            panel_settled(page, open=panel_open)
        page.evaluate("""async () => {
          const {notice} = await window.__lfRuntimeImport('/runtime/notifications.js');
          notice('Update recorded');
        }""")
        if width <= 480 and not panel_open:
            # A phone's banner says it in its status words, where the page is live; a
            # covering panel leaves the banner under its scrim, so it stays at the foot.
            expect(page.locator(".lf-banner .lf-status-notice")).to_be_visible()
            expect(page.locator(".lf-bottom-status")).to_be_hidden()
            continue
        expect(notice).to_be_visible()
        geometry = page.locator(".lf-bottom-status").evaluate("""status => {
          const box = status.getBoundingClientRect();
          const panel = document.querySelector('.lf-thread-panel').getBoundingClientRect();
          const beside = panel.width > 0 && innerWidth > 840;
          return {right: box.right, left: box.left, bottom: box.bottom, top: box.top,
            availableRight: beside ? panel.left : innerWidth};
        }""")
        assert geometry["right"] == pytest.approx(
            geometry["availableRight"] - 18, abs=1
        ), (width, panel_open, geometry)
        assert geometry["left"] >= 0, (width, panel_open, geometry)
        if panel_open and width <= 840:
            foot = page.locator(".lf-thread-panel-foot").bounding_box()
            assert geometry["bottom"] == pytest.approx(foot["y"] - 14, abs=1)
        else:
            # Centred on the bottom bar's row, inside the bar: the row More stands on.
            band = page.locator(".lf-shortcut-bar").bounding_box()
            more = page.locator(".lf-shortcut-more").bounding_box()
            assert band["y"] <= geometry["top"] and geometry["bottom"] <= 800, (
                width,
                panel_open,
                geometry,
                band,
            )
            assert (geometry["top"] + geometry["bottom"]) / 2 == pytest.approx(
                more["y"] + more["height"] / 2, abs=1
            ), (width, panel_open, geometry, more)
        pixels = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        # The notice's own card ground, inside its padding: a scrim over it would tint it.
        ground = tuple(map(int, re.findall(r"\d+", token_colour(page, "--card"))))
        assert (
            pixels.getpixel(
                (
                    round(geometry["left"] + 5),
                    round((geometry["top"] + geometry["bottom"]) / 2),
                )
            )
            == ground
        ), (width, panel_open, "the notice is covered by a scrim")


PHONE_PAGE = leaf_page(
    "phone",
    "<h1 id='t'>Phone</h1><p id='p1'>Paragraph one. " + "Filler. " * 40 + "</p>",
)


PHONE_READING_PAGE = leaf_page(
    "phone reading",
    "<h1 id='t'>Phone</h1>"
    + "<aside class='sidenote'><lf-draft id='note'><pre>A draft set in the sidenote's"
    " type.</pre></lf-draft></aside>"
    + "".join(
        f"<p id='p{n}'>Paragraph {n}. "
        + "Filler words for the reading column. " * 8
        + "</p>"
        for n in range(12)
    ),
)


def test_a_phone_comment_field_keeps_its_passage_clear(iphone, serve):
    """Phone fields keep their text size and stand clear of a selected paragraph.

    Safari zooms the page onto a text field set under 16px as the field takes focus, and
    leaves it zoomed: tapping the field jumped the view, then left the user panning
    sideways across a page wider than the screen. So no field the page holds is smaller,
    and a draft, whose editor wears the words' own face, shows them on the same floor, or
    one set in a sidenote's smaller type opens a size larger than it showed.

    With too little room below, the field stands above without scrolling the page.
    This emulation cannot show the native iOS
    selection menu, whose placement needs actual-device verification."""
    page = open_page(None, serve(PHONE_READING_PAGE), context=iphone)
    # Every field in the composed tree, the vendored controls' own native fields in
    # their shadow roots included: the Threads find box and the Map's search are
    # Web Awesome inputs, and Safari zooms onto the field inside them.
    sizes = page.evaluate("""() => {
      const sizes = {};
      const walk = (root) => {
        for (const node of root.querySelectorAll('*')) {
          if (node.matches('input, textarea, leaf-text, select')) {
            const host = node.getRootNode().host;
            const name = (host ?? node).localName + '.' + ((host ?? node).className || '');
            sizes[name] = Math.min(
              sizes[name] ?? Infinity, parseFloat(getComputedStyle(node).fontSize));
          }
          if (node.shadowRoot) walk(node.shadowRoot);
        }
      };
      walk(document);
      return sizes;
    }""")
    assert any(name.startswith("wa-input.") for name in sizes), sizes
    assert min(sizes.values()) >= 16, sizes
    note = page.locator("#note")
    shown = note.locator(".lf-draft-body").evaluate(
        "body => parseFloat(getComputedStyle(body).fontSize)"
    )
    note.locator(".lf-draft-body").tap()
    editing = note.locator(".lf-draft-edit").evaluate(
        "field => parseFloat(getComputedStyle(field).fontSize)"
    )
    assert shown == editing >= 16, (shown, editing)
    page.keyboard.press("Escape")
    # Close returns focus to the persistent Edit control. Complete that handoff
    # before installing the next native selection, which WebKit focus collapses.
    expect(note.get_by_role("button", name="Edit", exact=True)).to_be_focused()

    page.locator("#p6").evaluate("""paragraph => {
      const box = paragraph.getBoundingClientRect();
      document.scrollingElement.scrollTop += box.bottom - (innerHeight - 20);
      const range = document.createRange();
      range.setStart(paragraph.firstChild, 0);
      range.setEnd(paragraph.firstChild, "Paragraph 6".length);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    comment = page.locator(".lf-banner-actions").get_by_role(
        "button", name="Comment on selection"
    )
    box = comment.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    before_scroll = page.evaluate("scrollY")
    comment.tap()
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    placed = page.evaluate("""() => {
      const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
      const paragraph = document.getElementById('p6').getBoundingClientRect();
      return {barTop: bar.top, barBottom: bar.bottom, paragraphTop: paragraph.top};
    }""")
    assert page.evaluate("scrollY") == before_scroll
    assert placed["barBottom"] <= placed["paragraphTop"], placed
    assert placed["barTop"] >= 0, placed
    assert placed["barBottom"] <= page.evaluate("innerHeight"), placed


ORDERED_PAGE = leaf_page(
    "ordered",
    "<h1 id='t'>Ordered</h1><p id='p1'>One paragraph.</p>",
    head="""<script type="module">
import "/runtime/widget-api.js";
window.__leafReadyHeard = false;
document.addEventListener("DOMContentLoaded", () => {
  window.__leafReadyHeard = true;
});
</script>""",
)


def test_a_page_module_importing_the_widget_api_hears_dom_content_loaded(
    browser, serve
):
    """A page module runs before `DOMContentLoaded`, as every deferred module does.

    Pages wire their behavior on that event. The widget API sits over the runtime's
    stylesheets, so an await at module scope anywhere under it starts the page module
    after the event instead, and a listener like this one never hears it."""
    page = open_page(browser, serve(ORDERED_PAGE))
    assert page.evaluate("() => window.__leafReadyHeard")


@pytest.mark.parametrize("mode", ["overlay", "page"])
def test_the_delivered_stylesheets_read_exactly_as_their_files_do(browser, serve, mode):
    """Delivered sheets parse like their captured files in document and shadow stages.

    Page mode carries and constructs no physical annotation sheet, while shared paint
    still reaches both trees. The selected overlay adds its actual annotation sheets.
    """
    page = open_page(
        browser, serve(LONG_PAGE.replace("<body>", f'<body data-annotations="{mode}">'))
    )
    layer = urljoin(
        page.url,
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').dataset.lfEntry"
        ),
    )
    files = {}
    names = ["chrome", "marks"]
    if mode == "overlay":
        names.extend(["annotation-chrome", "annotation-marks"])
    for name in names:
        directory = (
            "runtime/annotation-overlay"
            if name.startswith("annotation-")
            else "runtime"
        )
        answer = page.request.get(urljoin(layer, f"{directory}/{name}.css"))
        assert answer.ok, answer.status
        files[name] = answer.text()

    readings = page.evaluate(
        """async (files) => {
          const rules = (sheet) => [...sheet.cssRules].map((rule) => rule.cssText);
          const fromFile = (text) => {
            const sheet = new CSSStyleSheet();
            sheet.replaceSync(text);
            return rules(sheet);
          };
          const { chromeSheet: chrome, marksSheet: marks, annotationSheets,
            annotationMarkSheets } =
            await window.__lfRuntimeImport("/runtime/stylesheets.js");
          if (![chrome, marks, ...annotationSheets].every(sheet => document.adoptedStyleSheets.includes(sheet)))
            throw new Error("The document did not adopt its chrome and marks sheets");
          const {shadowStage}=await window.__lfRuntimeImport('/runtime/shadow-stage.js');
          const host=document.createElement('div'); document.querySelector('main').append(host);
          const root=shadowStage(host,[document.createTextNode('A declared shadow stage')]);
          if (![marks,...annotationMarkSheets].every(sheet=>root.adoptedStyleSheets.includes(sheet)))
            throw new Error('The shadow stage did not adopt its selected marks');
          if (annotationSheets.length !== (files['annotation-chrome'] ? 2 : 0) ||
              annotationMarkSheets.length !== (files['annotation-marks'] ? 1 : 0))
            throw new Error('The document constructed an unselected annotation sheet');
          const answer = {
            chrome: {delivered: rules(chrome), file: fromFile(files.chrome)},
            marks: {delivered: rules(marks), file: fromFile(files.marks)},
          };
          if (annotationSheets.length) {
            answer['annotation-chrome']={delivered:rules(annotationSheets[0]),file:fromFile(files['annotation-chrome'])};
            answer['annotation-marks']={delivered:rules(annotationMarkSheets[0]),file:fromFile(files['annotation-marks'])};
          }
          return answer;
        }""",
        files,
    )
    for name, reading in readings.items():
        assert reading["delivered"], f"the page adopted no {name} rules"
        assert reading["delivered"] == reading["file"], name
    carrier = page.locator("script[data-lf-sheets]").text_content()
    selected = json.loads(carrier)
    assert ("annotations" in selected) == (mode == "overlay")
    assert page.locator("style[data-lf-annotation-theme]").count() == (
        mode == "overlay"
    )
    if mode == "page":
        assert ".lf-margin-cluster" not in carrier
        assert ".lf-visual-mark {" not in carrier
        assert "::highlight(lf-mark)" not in carrier
        assert ".lf-margin-preview { position: fixed" not in carrier
    assert ".lf-aim {" in selected["chrome"]
    assert ".lf-target-trace {" in selected["chrome"]
    assert ".lf-drawing-mark path" in selected["chrome"]
    assert "::highlight(lf-version-insert)" in selected["marks"]


def test_indication_defaults_yield_to_widget_faces_in_document_and_shadow(
    browser, serve
):
    """A widget can choose its indication face in either kind of rendering root.

    Ordinary indicated elements still get the shared contour. The default must
    yield to layered widget rules, while action-target apparatus keeps its face.
    """
    page = open_page(
        browser, serve(leaf_page("indication-faces", '<h1 id="t">Indication</h1>'))
    )
    readings = page.evaluate(
        """async () => {
          const {shadowStage} = await window.__lfRuntimeImport('/runtime/shadow-stage.js');
          const {inBaseLayer} = await window.__lfRuntimeImport('/runtime/stylesheets.js');
          const nodes = () => {
            const style = document.createElement('style');
            style.textContent = inBaseLayer('.custom-indication, .lf-action-target { outline: 4px dashed red; }');
            return [style, ...['default-indication', 'custom-indication', 'lf-action-target'].map(cls => {
              const p = document.createElement('p');
              p.className = cls;
              p.textContent = cls;
              p.setAttribute('data-lf-indicated', '');
              return p;
            })];
          };
          const main = document.querySelector('main');
          main.append(...nodes());
          const host = document.createElement('div');
          main.append(host);
          const shadow = shadowStage(host, nodes());
          return [main, shadow].map(root =>
            [...root.querySelectorAll('[data-lf-indicated]')].map(p => {
              const s = getComputedStyle(p);
              return [s.outlineStyle, s.outlineWidth];
            }));
        }"""
    )
    assert readings == [[["solid", "2px"], ["dashed", "4px"], ["solid", "1px"]]] * 2


def test_message_markdown_reads_a_link_scheme_as_the_attribute_resolves_it(
    browser, serve
):
    """The web-protocol guard reads the href the document will resolve, not its source.

    Character references in destinations must be interpreted before scheme
    admission. The parser's normalized attributes and flattened image alt are
    shared by message rendering and media inspection, including titles and
    autolink destinations. A refused destination retains its visible label.
    """
    url = serve(LONG_PAGE)
    pixels = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(pixels, format="PNG")
    media = store_uploaded_media(serve.page_dir, pixels.getvalue(), "image/png")
    panel_comment(
        serve.page_dir,
        "[press me](javascript&#58;window.leaked=true)"
        " ![blocked *image*](javascript&#58;window.leaked=true)"
        " beside [the page](https://example.com/?a=1&amp;b=2)"
        " and <https://example.com/?a=1&amp;b=2>"
        ' and ![Q&amp;A *chart* with [details](https://example.com/)](/icon.svg "Sales &amp; revenue")'
        f" and ![A **media** chart]({media})",
        {"section": "p0"},
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    prose = page.locator(".lf-msg-text").first
    # The prose goes on past these words, so they are read as a run inside it rather
    # than as the whole of its text.
    expect(prose).to_contain_text("press me blocked image beside the page")
    admitted = prose.evaluate(
        """node => [...node.querySelectorAll('a')].map(link => link.href)"""
    )
    assert admitted == [
        "https://example.com/?a=1&b=2",
        "https://example.com/?a=1&amp;b=2",
    ], admitted
    expect(prose.locator("img")).to_have_count(2)
    image = prose.locator("img").first
    expect(image).to_have_attribute("alt", "Q&A chart with details")
    expect(image).to_have_attribute("title", "Sales & revenue")

    page.locator(".lf-thread-summary").first.click()
    media_button = prose.get_by_role("button", name="View A media chart", exact=True)
    expect(media_button.locator("img")).to_have_attribute("alt", "A media chart")
    media_button.focus()
    page.keyboard.press("Enter")
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute("alt", "A media chart")
    page.keyboard.press("Escape")
    expect(media_button).to_be_focused()


MARKDOWN = (
    "Words, `inline code`, **strong**, *emphasis*, ~~struck~~ and a"
    " [link](https://example.com/).\n\n> A quoted line\n\n## A heading\n\n"
    "```\nfenced(code)\n```\n\nend"
)
# Each construct as the sent message draws it, and as the draft draws the same source.
# The draft is set in the box's type and the message in the body's, so sizes are
# compared as a share of each one's container; the rest is the face itself.
FACES = {
    "inline code": ("p code", "code"),
    "strong": ("strong", "strong"),
    "emphasis": ("em", "em"),
    "strikethrough": ("s", "s"),
    "link": ("a", ".lf-md-link"),
    "quote": ("blockquote", ".lf-md-quote"),
    "heading": ("h2", ".lf-md-heading"),
    "code block": ("pre", ".lf-md-code-block"),
}
FACE = [
    "font-family",
    "font-style",
    "font-weight",
    "color",
    "background-color",
    "padding-left",
    "border-top-left-radius",
    "border-left-width",
    "border-left-style",
    "border-left-color",
    "text-decoration-line",
    "text-decoration-color",
    "text-underline-offset",
]


def test_words_in_a_threaded_page_element_stay_selectable_beside_threads(
    browser, serve
):
    """Selecting annotated page text outranks the panel's selected thread.

    The panel's thread highlight must not reclaim focus during a native drag. The
    resulting passage, rather than that selected thread, is what c comments on.
    """
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Discuss this paragraph.", {"section": "p0"})
    page = open_page(browser, url)
    resized(page, 1440, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    paragraph = page.locator("#p0")
    rect = paragraph.bounding_box()
    select(
        page,
        (rect["x"] + 2, rect["y"] + 8),
        (rect["x"] + min(rect["width"] - 2, 250), rect["y"] + 8),
    )
    selected = page.evaluate("getSelection().toString()")
    assert selected.strip() and selected in paragraph.inner_text()
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer leaf-text")).to_be_focused()
    expect(page.locator("#lf-composer-quote")).to_contain_text(selected)
    expect(page.locator(".lf-thread-panel")).to_be_visible()


# A wide page of a body and its side track: a long body beside a short side track, the
# side track being the part of the page a panel standing over the window's right edge
# would cover.
WIDE_PAGE = leaf_page(
    "wide page",
    """
<header><h1 id="t">Wide page</h1></header>
<div id="body">{paras}</div>
<aside id="side">
  <section class="panel" id="rail"><h2>Rail</h2><p>Counts beside the body.</p></section>
</aside>
""",
    layout="sidebar",
).format(
    paras="\n".join(
        f"<p id='p{i}'>Paragraph {i}. " + "Filler. " * 40 + "</p>" for i in range(40)
    )
)


SURFACE_PAGES = {
    "threads-column": ("threads", lambda: LONG_PAGE),
    "threads-wide-page": ("threads", lambda: WIDE_PAGE),
    "queue": ("queue", lambda: with_one_ask(LONG_PAGE)),
}


def toggle_surface(page, surface, open=True):
    if surface == "queue":
        toggle_queue(page, open)
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page, open)


# The wide page, whose side track the surface stands over, at both widths; the column
# and the Questions panel at one each.
@pytest.mark.parametrize(
    ("case", "width"),
    [
        ("threads-column", 900),
        ("threads-wide-page", 900),
        ("threads-wide-page", 1440),
        ("queue", 1440),
    ],
)
def test_an_auxiliary_surface_stands_over_the_page_and_moves_none_of_it(
    browser, serve, case, width
):
    """Opening Threads or the Questions panel never moves the page: each stands over the
    right edge of the window they share, so the reading column keeps its place, its width and its wrapping, a
    wide page's side track stays where its Layout put it, and the document neither grows nor
    scrolls under it. The page beside the surface stays live rather than going inert
    behind a covering boundary."""
    surface, html = SURFACE_PAGES[case]
    page = open_page(browser, serve(html(), comments=2))
    resized(page, width, 640)
    page.evaluate("() => document.scrollingElement.scrollTop = 900")
    shape = """() => {
      const main = document.querySelector('body > main').getBoundingClientRect();
      const rail = document.querySelector('#rail')?.getBoundingClientRect();
      return {
        left: main.left, width: main.width, rail: rail ? rail.left : null,
        scroll: document.scrollingElement.scrollTop,
        tall: document.documentElement.scrollHeight,
        shell: document.body.clientWidth,
      };
    }"""
    before = page.evaluate(shape)
    region = page.locator(
        ".lf-queue-panel" if surface == "queue" else ".lf-thread-panel"
    )

    toggle_surface(page, surface)
    expect(region).to_be_visible()
    region.evaluate("el => el.getAnimations().forEach((a) => a.finish())")
    assert page.evaluate(shape) == pytest.approx(before, abs=0.5)
    box = region.bounding_box()
    assert box["x"] + box["width"] == pytest.approx(width, abs=1)
    assert not region.evaluate("el => el.closest('dialog').matches(':modal')")

    toggle_surface(page, surface, open=False)
    assert page.evaluate(shape) == pytest.approx(before, abs=0.5)


def test_the_panel_covers_a_wide_page_where_it_would_leave_no_usable_page(
    browser, serve
):
    """Where the window would leave less than a usable page beside it, the panel covers
    a wide page as it does any page: modal, with the page inert underneath."""
    page = open_page(browser, serve(WIDE_PAGE))
    resized(page, 700, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert page.locator(".lf-thread-panel").evaluate(
        "el => el.closest('dialog').matches(':modal')"
    )
    assert page.locator("main").evaluate(
        """el => {
          const focused = document.activeElement;
          el.tabIndex = -1;
          el.focus();
          el.removeAttribute('tabindex');
          return document.activeElement === focused;
        }"""
    )


def test_a_page_map_update_keeps_the_row_the_user_was_on(browser, serve):
    """A state update re-rendering the open Page Map leaves the user's rows in place.

    A group arriving above the rows in view pushes them down in the list's content by
    its own height. The place the user had is the rows they were looking at, so the
    list follows them by the same amount rather than standing at the scroll offset it
    had, which would show them one group further down.
    """
    fixture = leaf_page(
        "Page Map place",
        "".join(f'<p id="place-{index}">Target {index}</p>' for index in range(30)),
    )
    page = open_page(browser, serve(fixture))
    resized(page, 1280, 600)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfRuntimeImport('/runtime/widget-api.js');
          const contribute = (key, target, label) => registerContribution({
            key, target,
            read: () => ({entries: [contributionEntry({key: 'action', icon: 'dot', label})]}),
            activate: () => {},
          });
          for (let index = 0; index < 29; index++)
            contribute(`place-${index}`, document.querySelector(`#place-${index}`),
              `Action ${index}`);
          let at = 29;
          const moving = contribute(
            'moving', () => document.querySelector(`#place-${at}`), 'Moving action');
          window.lfMoveToTop = () => {
            at = 0;
            moving.update({immediate: true});
          };
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(dialog).to_be_visible()
    row = dialog.get_by_role("button", name="Action 15", exact=True)
    row.evaluate("node => node.scrollIntoView({block: 'center'})")
    top = row.evaluate("node => node.getBoundingClientRect().top")
    room = dialog.locator(".lf-page-map-list").evaluate(
        "list => list.scrollHeight - list.clientHeight - list.scrollTop"
    )
    moving = dialog.get_by_role("button", name="Moving action", exact=True)
    grown = moving.evaluate(
        "node => node.closest('.lf-page-map-group').getBoundingClientRect().height"
    )
    assert room > grown, "the list cannot follow the rows without passing its end"

    page.evaluate("() => window.lfMoveToTop()")
    first = dialog.locator(".lf-page-map-action-label-word").first
    expect(first).to_have_text("Moving action")
    assert row.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        top, abs=1
    )


def test_a_repaint_unsettles_the_rendering_until_it_lands(browser, serve):
    """The settled reading turns false in the same turn as a gesture that queues a
    repaint, and true once that repaint has landed, so a reader after the gesture waits
    on the page rather than on a guessed number of frames. The fold itself — chained
    work, observer deliveries, cancellation — is tests/runtime/rendering.test.mjs."""
    url = serve(leaf_page("Settled", '<h1 id="h">Settled</h1><p id="p">Words.</p>'))
    page = open_page(browser, url)
    toggle = page.locator(".lf-threads-toggle")
    toggle.hover()
    rendered(page)
    # The reading on either side of the press: as it goes down, before any listener has
    # answered it, and once its click has passed every listener.
    page.evaluate(
        """() => {
          const state = document.querySelector('script[data-lf-entry]').lfRenderingState;
          const settled = () => Object.values(state()).every(Boolean);
          window.__lfPress = [];
          const read = () => window.__lfPress.push(settled());
          addEventListener('pointerdown', read, {capture: true, once: true});
          addEventListener('click', read, {once: true});
        }"""
    )
    toggle.click()
    assert page.evaluate("window.__lfPress") == [True, False]
    rendered(page)
    # Completion is the reading rendered waited on. A later slide-end scan can
    # queue new work, so a second reading need not still be settled.
    expect(page.locator(".lf-thread-panel")).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_auxiliary_posture_keeps_live_browser_state(engine, request, serve):
    """A native boundary changes posture without disconnecting any live descendant.

    Focus/caret restoration cannot repair an iframe's destroyed browsing context. The
    actual draft and a small embedded document distinguish retention from replacing
    nodes or removing and reinserting them, in both engines.
    """
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE, comments=1))
    resized(page, 1200, 800)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-thread[open]").first
    field = thread.locator(":scope > .lf-thread-reply leaf-text")
    write(field, "Keep this live draft")
    field.evaluate("field => field.setSelectionRange(2, 6)")
    page.locator(".lf-thread-panel").evaluate("""async panel => {
      const frame = document.createElement('iframe');
      frame.id = 'retained-browsing-context';
      frame.style.cssText = 'position:absolute;left:0;top:0;width:80px;height:80px';
      frame.srcdoc = '<details open><summary>Kept disclosure</summary><input>' +
        '<div id="reading" style="height:20px;overflow:auto"><div style="height:200px">Reading</div></div></details>';
      const loaded = new Promise(resolve => frame.onload = resolve);
      panel.append(frame);
      await loaded;
      const embedded = frame.contentDocument;
      embedded.querySelector('input').value = 'Kept embedded edit';
      embedded.querySelector('#reading').scrollTop = 40;
      frame.contentWindow.retainedIdentity = {};
      window.heldAuxiliaryFrame = frame;
      window.heldAuxiliaryIdentity = frame.contentWindow.retainedIdentity;
    }""")
    field.focus()
    before = field.evaluate(
        "field => [field.value, field.selectionStart, field.selectionEnd]"
    )
    for width in (390, 1200):
        resized(page, width, 800)
        panel_settled(page)
        expect(field).to_be_focused()
        assert (
            field.evaluate(
                "field => [field.value, field.selectionStart, field.selectionEnd]"
            )
            == before
        )
        kept = page.evaluate("""() => {
          const frame = document.querySelector('#retained-browsing-context');
          return frame === heldAuxiliaryFrame &&
            frame.contentWindow.retainedIdentity === heldAuxiliaryIdentity &&
            frame.contentDocument.querySelector('details').open &&
            frame.contentDocument.querySelector('input').value === 'Kept embedded edit' &&
            frame.contentDocument.querySelector('#reading').scrollTop === 40;
        }""")
        assert kept, width


def test_a_popover_reseated_by_the_panel_stays_on_its_source(browser, serve):
    """A widget in a thread hangs a popover from its button, opened through the package
    API with the button as its source, which anchors it. Resizing the panel into
    covering re-seats the popover, and it reopens from the same source, so it still
    hangs from the button rather than landing wherever an unanchored popover falls. The
    button stands in the widget's shadow root, where the toggle event names its host
    instead. No shipped popover with a source stays open across a re-seat: this is the
    package route."""
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    resized(page, 1200, 800)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    door = page.locator(".lf-thread[open] .lf-msg").first.evaluate_handle("""async message => {
      const {showNativeLayer} = await window.__lfRuntimeImport('/runtime/widget-api.js');
      const widget = document.createElement('span');
      const door = Object.assign(document.createElement('button'), {textContent: 'Details'});
      widget.attachShadow({mode: 'open'}).append(door);
      const popover = Object.assign(document.createElement('div'),
        {id: 'widget-popover', popover: 'auto', textContent: 'Widget details'});
      // Out of flow, so the thread's own lines keep their places; padded, so the host's
      // box is not the button's.
      widget.style.cssText = 'position: absolute; padding: 24px';
      popover.style.cssText = 'position-area: bottom span-right; margin: 0';
      message.append(widget, popover);
      showNativeLayer(popover, {source: door});
      return door;
    }""")
    popover = page.locator("#widget-popover")
    hangs = """([door, popover]) => {
      const from = door.getBoundingClientRect(), box = popover.getBoundingClientRect();
      return Math.abs(box.top - from.bottom) < 1 && Math.abs(box.left - from.left) < 1;
    }"""
    expect(popover).to_be_visible()
    assert page.evaluate(hangs, [door, popover.element_handle()])
    resized(page, 390, 800)
    assert popover.evaluate("el => el.closest('dialog').matches(':modal')")
    expect(popover).to_be_visible()
    assert page.evaluate(hangs, [door, popover.element_handle()])


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_send_room_moves_to_every_line_only_while_the_field_scrolls(
    engine, request, serve
):
    """The field holds Send's room after its last words until its words scroll, and on
    every line while they do, in an engine without CSS scroll-state queries as in
    Chromium. Keyed on the query alone, WebKit and Firefox held it on every line
    always, so the change never reached them."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(request.getfixturevalue(engine), url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
    thread.locator(".lf-thread-summary").click()
    field = thread.locator(".lf-thread-reply leaf-text")
    scrolls = "el => el.scrollHeight > el.clientHeight"

    write(field, "First line.\nSecond line.")
    assert not field.evaluate(scrolls)
    expect(field).to_have_js_property("endRoom", "last-line")
    write(field, "A long draft scrolls inside its field. " * 120)
    assert field.evaluate(scrolls)
    expect(field).to_have_js_property("endRoom", "every-line")
    write(field, "Short again.")
    expect(field).to_have_js_property("endRoom", "last-line")
