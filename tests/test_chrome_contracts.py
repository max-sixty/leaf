"""Everyday browser contracts for shared chrome."""

import io
import json
import re
import time
from urllib.parse import urljoin

import pytest
from interact_support import append_command
from leaf import event_log as events_model
from leaf.media import store_uploaded_media
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    REPORT_PAGE,
    SUGGESTION_PAGE,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    BANNER_ORDER,
    banner_control,
    button_radius,
    token_colour,
)
from render_cases_navigation import _publish
from render_harness import (
    LONG_PAGE,
    CutOff,
    Traffic,
    _until,
    clean_browser,
    compare_with,
    consume_browser_errors,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    sending,
    take_browser_errors,
    told,
    watched,
)


def test_agent_reply_arrivals_keep_open_panel_drafts_and_summarize_batches(
    browser, serve
):
    """Only new accepted replies announce, regardless of the panel's disclosure."""
    url = serve(leaf_page("Reply arrivals", "<h1>Reply arrivals</h1>"))
    directory = serve.page_dir
    a = events_model.append_event(
        directory, {"kind": "comment", "author": "user", "revision": 1, "text": "A"}
    )
    b = events_model.append_event(
        directory, {"kind": "comment", "author": "user", "revision": 1, "text": "B"}
    )
    events_model.append_event(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": a["id"],
            "text": "Earlier",
        },
    )
    page = open_page(browser, url)
    live = page.locator(".lf-live")
    notice = page.locator(".lf-notice")
    assert "replied" not in live.text_content()
    expect(notice).not_to_have_class(re.compile(r"\bshow\b"))

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(f'.lf-thread[data-id="{a["id"]}"] .lf-thread-summary').click()
    draft = page.locator(f'.lf-thread[data-id="{a["id"]}"] textarea')
    draft.fill("Keep this draft")
    draft.focus()
    page.evaluate(
        """() => {
          window.__lfReplyAnnouncements = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__lfReplyAnnouncements.push(words);
          }).observe(document.querySelector('.lf-live'), {childList: true, subtree: true});
        }"""
    )
    events_model.append_event(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": b["id"],
            "text": "For B",
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    expect(live).to_have_text("Codex replied")
    expect(notice).to_have_text("Codex replied")
    expect(draft).to_be_focused()
    expect(draft).to_have_value("Keep this draft")

    reads = CutOff().hold(page)
    events_model.append_event(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": a["id"],
            "text": "More for A",
        },
    )
    events_model.append_event(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": b["id"],
            "text": "More for B",
        },
    )
    reads.restore()
    told(page)
    expect(live).to_have_text("2 replies in 2 threads")
    expect(notice).to_have_text("2 replies in 2 threads", timeout=5_000)
    expect(draft).to_be_focused()
    expect(draft).to_have_value("Keep this draft")

    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/notifications.js')).holdStatus(10000)"
    )
    for parent in (a["id"], b["id"]):
        events_model.append_event(
            directory,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": parent,
                "text": "Another answer",
            },
        )
        page.evaluate(
            "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
        )
    page.wait_for_function(
        "() => window.__lfReplyAnnouncements.filter(words => words === 'Codex replied').length === 3"
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/notifications.js')).holdStatus(1)"
    )
    expect(notice).to_have_text("4 replies in 2 threads")
    expect(notice).to_be_visible()
    expect(draft).to_be_focused()
    expect(draft).to_have_value("Keep this draft")

    # A duplicate read and a fresh document make no fresh announcement.
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    page.wait_for_timeout(100)
    assert page.evaluate("() => window.__lfReplyAnnouncements") == [
        "Codex replied",
        "2 replies in 2 threads",
        "Codex replied",
        "Codex replied",
    ]
    page.reload()
    expect(notice).not_to_have_class(re.compile(r"\bshow\b"))
    assert "replied" not in live.text_content()


def test_interrupted_background_notice_keeps_the_newer_version(browser, serve):
    """An older visible notice cannot replace a newer one already waiting."""
    page = open_page(browser, serve(leaf_page("Notice order", "<h1>Notice order</h1>")))
    page.evaluate(
        """async () => {
          const {notice} = await window.__lfRuntimeImport('/runtime/notifications.js');
          notice('Updated to v3', {background: true});
          notice('Updated to v4', {background: true});
          notice('Saved — sent');
        }"""
    )
    shown = page.locator(".lf-notice")
    expect(shown).to_have_text("Saved — sent")
    expect(shown).to_have_text("Updated to v4", timeout=5_000)


class _ProblemPage:
    url = "https://leaf.test/example"

    def add_init_script(self, **_):
        pass

    def on(self, *_):
        pass


def test_browser_health_rejects_an_unconsumed_problem():
    """A forgotten per-test assertion cannot turn a browser fault green."""

    with (
        pytest.raises(
            AssertionError, match="https://leaf.test/example: unexpected browser fault"
        ),
        clean_browser(),
    ):
        watched(_ProblemPage()).append("unexpected browser fault")


def test_consuming_browser_problems_accounts_for_every_entry():
    """Naming one expected fault cannot consume an unrelated one."""

    with clean_browser():
        page = _ProblemPage()
        watched(page).extend(["expected fault", "unrelated fault"])
        with pytest.raises(AssertionError, match="unrelated fault"):
            consume_browser_errors(page, "expected fault")


def test_version_reservation_retains_the_lit_controls(browser, serve):
    """Sizing and folding retain the exact native controls and their Lit parts."""
    page = open_page(browser, serve(LONG_PAGE))
    version = page.locator(".lf-version")
    version.focus()
    retained = page.evaluate(
        """async () => {
          const entry = document.querySelector('script[data-lf-entry]');
          const owner = await import(new URL(
            'runtime/version-chooser.js',
            new URL(entry.dataset.lfEntry, location.href),
          ));
          const button = owner.versionBtn;
          const latest = owner.latestChip;
          window.__lfVersionControls = {
            button,
            latest,
            buttonParts: [...button.childNodes],
            latestParts: [...latest.childNodes],
          };
          owner.reserveVersionControls();
          return {
            focus: document.activeElement === button,
            buttonParts: button.childNodes.length,
            latestParts: latest.childNodes.length,
          };
        }"""
    )
    assert retained["focus"], "measuring the chooser took its native focus"
    assert retained["buttonParts"] and retained["latestParts"]
    assert page.evaluate(
        """() => {
          const held = window.__lfVersionControls;
          return held.button === document.querySelector('.lf-version') &&
            held.latest === document.querySelector('.lf-latest-chip') &&
            held.buttonParts.every((node, index) => held.button.childNodes[index] === node) &&
            held.latestParts.every((node, index) => held.latest.childNodes[index] === node);
        }"""
    ), "version reservation replaced a retained Lit part"

    resized(page, 390, 900)
    resized(page, 1200, 900)
    assert page.evaluate(
        """() => {
          const held = window.__lfVersionControls;
          return held.button === document.querySelector('.lf-version') &&
            held.latest === document.querySelector('.lf-latest-chip') &&
            held.buttonParts.every((node, index) => held.button.childNodes[index] === node) &&
            held.latestParts.every((node, index) => held.latest.childNodes[index] === node);
        }"""
    ), "responsive reservation or folding replaced a version control"
    version.click()
    expect(page.locator(".lf-version-menu")).to_be_visible()
    expect(page.locator(".lf-version-row")).to_be_focused()


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


def test_a_state_read_outlives_the_chrome_the_copy_takes_out(browser, serve):
    """Baking a copy removes `.lf-chrome` from the live page while its state stream is
    still running, so the reads that land in the gap before the tab closes find the
    Leaves tray gone. A tray that has left the document has no region to present into,
    and a reading that arrives after it leaves is not the reading's fault: the read must
    still apply, and the page must report nothing.

    It reported twice per read — `State presentation failed` and `read failed`, both
    naming the tray — because the list threw for the handle its own
    `disconnectedCallback` had dropped, and that throw came back out of the whole state
    application. Which read lands in the gap is a matter of the machine's load, so the
    copy tests saw it as an occasional error on a page whose copy was correct. Here the
    chrome is taken out directly and the read is provoked, so the gap is the
    arrangement rather than the weather."""
    page = open_page(browser, serve(REPORT_PAGE))
    page.evaluate(
        "() => document.querySelectorAll('.lf-chrome').forEach(node => node.remove())"
    )
    append_command(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A word said after the chrome went.",
        },
    )
    # `told` reads the page's own applied reading, which state application writes only
    # once it has presented, so this is the assertion that the read landed rather than a
    # wait for one that quietly failed.
    told(page)
    assert take_browser_errors(page) == []


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_margin_reply_shares_its_conversations_opaque_surface(browser, serve, scheme):
    """The reply surround stays continuous as focus enters and leaves the conversation.

    An opaque shared surface also lets a pinned reply cover scrolled messages without
    introducing a differently colored band above its input.
    """
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(browser, url, color_scheme=scheme)
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    preview = page.locator(".lf-margin-preview")
    thread = preview.locator(".lf-conversation-thread")
    surround = thread.locator(".lf-say")
    reply = preview.get_by_role("button", name="Reply", exact=True)
    editor = preview.locator("textarea")
    expect(reply).to_be_visible()

    for state in ("collapsed", "editing", "outside"):
        if state == "editing":
            reply.click()
            expect(editor).to_be_focused()
        elif state == "outside":
            preview.get_by_role("button", name="Dismiss conversation").focus()
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


@pytest.mark.parametrize("width", [320, 800])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_thread_keeps_submit_in_its_field_and_resolve_with_its_metadata(
    browser, serve, width, scheme
):
    """Submit belongs to the field while Resolve stands with the root metadata.

    Growing the field carries Submit with it and leaves Resolve fixed. The textarea
    reserves the icon's whole horizontal band, so words and a scrollbar do not run
    underneath it. Resolve aligns with the root author and time instead of the quoted
    target. The same geometry holds in the panel's narrowest useful window and with
    room beside the page, in both palettes."""
    context = browser.new_context(
        viewport={"width": width, "height": 720}, color_scheme=scheme
    )
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
    thread.locator(".lf-thread-summary").click()
    compose = thread.locator(".lf-compose")
    textarea = compose.locator("textarea")
    send = thread.get_by_role("button", name="Send", exact=True)
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    close = page.get_by_role("button", name="Close threads", exact=True)
    expect(send).to_be_visible()
    expect(resolve).to_be_visible()
    expect(send.locator('svg[data-lf-icon="send"]')).to_have_count(1)
    expect(resolve.locator('svg[data-lf-icon="check"]')).to_have_count(1)
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    expect(thread.get_by_role("button", name="Close thread", exact=True)).to_have_count(
        0
    )
    expect(send).to_have_text("")
    expect(resolve).to_have_text("")
    expect(close).to_have_text("")

    def geometry():
        return thread.evaluate(
            """thread => {
                  const rect = sel => {
                    const r = thread.querySelector(sel).getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height,
                            right: r.right, bottom: r.bottom};
                  };
                  const own = thread.getBoundingClientRect();
                  const padding = parseFloat(getComputedStyle(
                    thread.querySelector('textarea')).paddingInlineEnd);
                  const radius = (selector, pseudo = null) => getComputedStyle(
                    selector.startsWith('.lf-thread-panel')
                      ? document.querySelector(selector)
                      : thread.querySelector(selector), pseudo).borderRadius;
                  return {thread: {x: own.x, y: own.y, width: own.width,
                                   height: own.height, right: own.right, bottom: own.bottom},
                          compose: rect('.lf-compose'), field: rect('.lf-compose-field'),
                          textarea: rect('.lf-compose textarea'),
                          metadata: rect('.lf-thread-root-meta'),
                          metadataActions: rect('.lf-thread-meta-actions'),
                          send: rect('.lf-thread-send'), resolve: rect('.lf-resolve'),
                          closeBorder: getComputedStyle(document.querySelector(
                            '.lf-thread-panel-head [aria-label="Close threads"]')).borderTopWidth,
                          resolveBorder: getComputedStyle(thread.querySelector(
                            '.lf-resolve'), '::before').borderTopWidth,
                          sendBorder: getComputedStyle(thread.querySelector(
                            '.lf-thread-send'), '::before').borderTopWidth,
                          radii: {
                            send: radius('.lf-thread-send'),
                            sendFill: radius('.lf-thread-send', '::before'),
                            resolve: radius('.lf-resolve'),
                            resolveFill: radius('.lf-resolve', '::before'),
                            close: radius('.lf-thread-panel-head [aria-label="Close threads"]'),
                          },
                          messageStart: rect('.lf-msg-body').x,
                          padding,
                          overflow: thread.scrollWidth - thread.clientWidth};
                }"""
        )

    short = geometry()
    assert short["field"]["x"] == pytest.approx(short["compose"]["x"], abs=1)
    assert short["field"]["x"] == pytest.approx(short["messageStart"], abs=1)
    assert short["field"]["x"] - short["thread"]["x"] == pytest.approx(
        short["thread"]["right"] - short["field"]["right"], abs=1
    )
    assert short["textarea"]["right"] == pytest.approx(short["field"]["right"], abs=1)
    assert short["send"]["right"] < short["textarea"]["right"]
    assert short["send"]["bottom"] < short["textarea"]["bottom"]
    assert short["padding"] >= short["send"]["width"] + 10
    assert short["resolve"]["y"] == pytest.approx(short["metadata"]["y"], abs=1)
    assert short["metadataActions"]["right"] == pytest.approx(
        short["compose"]["right"], abs=1
    )
    assert short["resolve"]["right"] == pytest.approx(
        short["metadataActions"]["right"], abs=1
    )
    assert short["metadata"]["x"] == pytest.approx(short["messageStart"], abs=1)
    assert short["resolve"]["bottom"] <= short["metadata"]["bottom"] + 1
    assert float(short["closeBorder"][:-2]) == 0
    assert float(short["resolveBorder"][:-2]) == 0
    assert float(short["sendBorder"][:-2]) == 0
    assert set(short["radii"].values()) == {button_radius(page)}
    assert short["overflow"] == 0

    textarea.focus()
    focused = geometry()
    assert focused["send"] == short["send"]
    assert focused["resolve"] == short["resolve"]

    textarea.fill("First line.\nSecond line.\nThird line.\nFourth line.")
    grown = geometry()
    assert grown["send"]["x"] == pytest.approx(short["send"]["x"], abs=1)
    assert grown["send"]["bottom"] == pytest.approx(
        grown["textarea"]["bottom"] - 6, abs=1
    )
    assert grown["send"]["y"] > short["send"]["y"]
    assert grown["metadataActions"] == short["metadataActions"]
    assert grown["resolve"] == short["resolve"]
    assert grown["overflow"] == 0


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


def test_a_folded_banner_control_keeps_its_active_paint(browser, serve):
    """A comparison standing behind the overflow menu is the same comparison, and has
    to go on looking like one.

    Both places clear the border and the fill `.lf-btn.on` states, each for its own
    reason: the row so that a control cannot resize it and displace the controls
    before it, the menu so that a control reads as a row rather than as a chip. Left
    at that, the class is ink alone in either — two characters at 2.16:1 against the
    control's own resting ink. The row was answered first and the menu was not, which
    put the banner's two active states on opposite sides of one fold: an open
    auxiliary surface's own selector outranks the menu's resting rule and keeps its face
    across it, and a standing comparison did not. So this reads the one control in
    both places rather than a number in either, because what the fold promises is that
    nothing about a control changes except where it stands.
    """
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    _publish(serve.page_dir, 2, html, "reworded the suggestion")
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    chooser = page.locator(".lf-version")
    expect(chooser).to_be_enabled()

    resized(page, 1440, 900)
    compare_with(page, 1)
    expect(chooser).to_have_class(re.compile(r"\bon\b"))
    expect(page.locator(".lf-banner-actions > .lf-version")).to_have_count(1)
    on_the_row = chooser.evaluate(STATE_PAINT)
    assert (
        on_the_row["shadow"] != "none"
        and "rgba(0, 0, 0, 0)" not in on_the_row["background"]
    ), f"the comparison stood on the row with nothing but ink: {on_the_row}"

    resized(page, 320, 844)
    expect(page.locator(".lf-banner-menu > .lf-version")).to_have_count(1)
    banner_control(page, ".lf-version")
    folded = chooser.evaluate(STATE_PAINT)

    assert folded == on_the_row, (
        f"the comparison changed face when it folded: row {on_the_row}, menu {folded}"
    )
    door = page.locator(".lf-banner-more")
    door.evaluate("el => el.toggleAttribute('data-lf-news', true)")
    expect(door).to_have_css("border-top-color", token_colour(page, "--accent"))


def test_the_banner_reads_in_one_order_at_every_width(browser, serve, other_leaf):
    """The row says the same thing at 1440 that it says on a phone.

    It used to turn round at the covering breakpoint: Threads went from the far right of
    the banner to the far left, and approval — the page's one committing press — swapped
    ends with it, so a reader narrowing the window found every control somewhere else.
    What a narrow window may change is how many controls stand on the row at once; the
    rest fold into the row's own menu, in this same order.

    Two things legitimately differ with width and neither is an order: the Page Map is a
    narrow window's stand-in for the margin's own markers, and a reserved news slot is not
    a banner control until it has news. So each width is held to being this one order with
    the controls that width does not have taken out of it, rather than to a fixed list — a
    reversal fails that just as loudly, and a control appearing at the wrong seat fails it
    where a fixed list would only have said the list was different.
    """
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="agent")
    page = open_page(browser, url)
    expect(page.locator(".lf-others")).to_have_text("All leaves (2)")
    expect(page.locator(".lf-signoff")).to_be_disabled()
    expect(page.locator(".lf-signoff")).to_have_attribute(
        "title", "Answer every Ask before approving this work"
    )
    expect(page.locator(".lf-answer-all")).to_be_visible()

    orders = {}
    for width in (1440, 860, 800, 390):
        resized(page, width, 900)
        orders[width] = page.evaluate(BANNER_ORDER)

    # One order, put as the thing it is: no two controls ever swap. Held pair by pair
    # rather than against a list taken at one width, because the widths do not all show
    # the same controls and a fixed list would then be failing about the Page Map rather
    # than about the order. A reversal breaks this on its first pair.
    first = {}
    for width, order in orders.items():
        for index, before in enumerate(order):
            for after in order[index + 1 :]:
                assert (after, before) not in first, (
                    f"{after!r} comes before {before!r} at {first[(after, before)]}px "
                    f"and after it at {width}px, so the banner reads in two orders: "
                    f"{orders}"
                )
                first.setdefault((before, after), width)
    assert len(first) >= 15, (
        f"too few controls stood at these widths to have an order at all: {orders}"
    )

    # And the order it settled on: every banner control the page offers, with the reading loop
    # finishing the row beside the panel it opens.
    widest = max(orders.values(), key=len)
    for wanted in ("All leaves", "Asks", "Accept all", "v1", "Approve version"):
        assert any(wanted in name for name in widest), (
            f"{wanted} was not on the row at all, so this order proves little: {widest}"
        )
    for width, order in orders.items():
        assert order[-1].startswith("Threads"), (
            f"the conversation no longer finishes the row at {width}px: {order}"
        )
    resized(page, 500, 900)
    control = banner_control(page, ".lf-others")
    control.click()
    page.mouse.move(0, page.viewport_size["height"] - 1)
    expect(control).to_have_attribute("aria-expanded", "true")
    expect(control).to_have_css("background-color", token_colour(page, "--chip"))


def test_notices_stay_at_the_visible_pages_right_edge(browser, serve):
    """A notice keeps the page's right corner through panel and viewport changes."""
    page = open_page(browser, serve(LONG_PAGE))
    notice = page.locator(".lf-notice")
    for width, panel_open in [
        (1200, False),
        (1200, True),
        (390, True),
        (320, True),
        (390, False),
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
        assert geometry["bottom"] <= 800 - 14, (width, panel_open, geometry)
        if panel_open and width <= 840:
            foot = page.locator(".lf-thread-panel-foot").bounding_box()
            assert geometry["bottom"] == pytest.approx(foot["y"] - 14, abs=1)
        pixels = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        accent = tuple(map(int, re.findall(r"\d+", token_colour(page, "--accent"))))
        assert (
            pixels.getpixel(
                (
                    round(geometry["left"] + 5),
                    round((geometry["top"] + geometry["bottom"]) / 2),
                )
            )
            == accent
        ), (width, panel_open, "the notice is covered by the panel or its scrim")


PHONE_PAGE = leaf_page(
    "phone",
    "<h1 id='t'>Phone</h1><p id='p1'>Paragraph one. " + "Filler. " * 40 + "</p>",
)


@pytest.mark.parametrize("viewport", [None, "width=device-width, initial-scale=1"])
def test_a_phone_starts_the_page_and_comments_on_a_selection(iphone, serve, viewport):
    """The runtime starts in WebKit; selection offers an explicit Comment action.

    A module feature WebKit lacks fails the whole module graph before the runtime runs:
    CSS module scripts did, and an iPhone reader saw only that Leaf could not start. A
    long press that selects words hands the page no mouseup, and Playwright cannot make
    one, so the selection is placed with no pointer gesture at all."""
    source = PHONE_PAGE
    if viewport:
        source = source.replace(
            "<head>", f'<head><meta name="viewport" content="{viewport}">'
        )
    page = open_page(None, serve(source), context=iphone)
    assert page.evaluate("innerWidth") == page.viewport_size["width"]
    metas = page.locator('meta[name="viewport"]')
    expect(metas).to_have_count(1)
    expect(metas).to_have_attribute(
        "content", viewport or "width=device-width, initial-scale=1, viewport-fit=cover"
    )
    page.locator("#p1").evaluate("""paragraph => {
      const range = document.createRange();
      range.setStart(paragraph.firstChild, 0);
      range.setEnd(paragraph.firstChild, "Paragraph one".length);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_hidden()
    page.get_by_role("button", name="Comment on selection", exact=True).tap()
    expect(field).to_be_focused()
    field.fill("From a phone")
    with sending(page, "the comment"):
        page.locator(".lf-fab-bar").get_by_role("button", name="Comment").tap()
    [comment] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert comment["text"] == "From a phone"
    assert comment["anchor"]["quote"] == "Paragraph one", comment


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
    """Phone fields keep their text size and stand below a selected paragraph.

    Safari zooms the page onto a text field set under 16px as the field takes focus, and
    leaves it zoomed: tapping the field jumped the view, then left the reader panning
    sideways across a page wider than the screen. So no field the page holds is smaller,
    and a draft, whose editor wears the words' own face, shows them on the same floor, or
    one set in a sidenote's smaller type opens a size larger than it showed.

    The field goes below this paragraph even though it has more room above and too
    little below: the page makes the room. This emulation cannot show the native iOS
    selection menu, whose placement needs actual-device verification."""
    page = open_page(None, serve(PHONE_READING_PAGE), context=iphone)
    sizes = page.evaluate(
        "() => [...document.querySelectorAll('input, textarea, select')]"
        ".map(field => parseFloat(getComputedStyle(field).fontSize))"
    )
    assert sizes and min(sizes) >= 16, sizes
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
    page.get_by_role("button", name="Comment on selection", exact=True).tap()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    placed = page.evaluate("""() => {
      const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
      const paragraph = document.getElementById('p6').getBoundingClientRect();
      return {barTop: bar.top, barBottom: bar.bottom, paragraphBottom: paragraph.bottom};
    }""")
    assert placed["barTop"] >= placed["paragraphBottom"], placed
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


def test_the_delivered_stylesheets_read_exactly_as_their_files_do(browser, serve):
    """Delivery drops the sheets' comments and re-serializes what is left, so what a page
    adopts is not the file's own bytes. The two have to say the same thing to the browser:
    a stylesheet oddity the serializer repairs would change the rules every page runs
    under, and no parser here would report it."""
    page = open_page(browser, serve(LONG_PAGE))
    layer = urljoin(
        page.url,
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').dataset.lfEntry"
        ),
    )
    files = {}
    for name in ("chrome", "marks"):
        answer = page.request.get(urljoin(layer, f"runtime/{name}.css"))
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
          const { chromeSheet: chrome, marksSheet: marks } =
            await window.__lfRuntimeImport("/runtime/stylesheets.js");
          if (![chrome, marks].every(sheet => document.adoptedStyleSheets.includes(sheet)))
            throw new Error("The document did not adopt its chrome and marks sheets");
          return {
            chrome: {delivered: rules(chrome), file: fromFile(files.chrome)},
            marks: {delivered: rules(marks), file: fromFile(files.marks)},
          };
        }""",
        files,
    )
    for name, reading in readings.items():
        assert reading["delivered"], f"the page adopted no {name} rules"
        assert reading["delivered"] == reading["file"], name


def test_a_traffic_wait_stops_when_repaints_outlive_its_deadline(monkeypatch):
    """A page that repaints its ledger forever cannot keep a false fact alive forever."""

    class BusyPage:
        reads = 0

        def evaluate(self, _script):
            self.reads += 1
            return json.dumps(
                {"sends": self.reads, "acked": 0, "asked": 0, "heard": 0, "pending": []}
            )

        def wait_for_function(self, *_args, **_kwargs):
            raise AssertionError("the expired wait listened for another paint")

    page = BusyPage()
    page.lf_traffic = Traffic(page)
    times = iter((0, 31, 31, 31))
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    with pytest.raises(AssertionError, match="never reached a false fact"):
        _until(page, lambda _traffic: False, "reached a false fact")


def test_message_markdown_reads_a_link_scheme_as_the_attribute_resolves_it(
    browser, serve
):
    """The web-protocol guard reads the href the document will resolve, not its source.

    marked hands a renderer the authored destination with its character references
    undecoded, and an href attribute decodes them when that markup lands. A guard
    reading the authored text sees `javascript&#58;` as a relative path, admits it,
    and the reader gets a live script link out of ordinary message prose. Reading the
    destination as the document will refuses that link, and the same reading is what
    keeps an ordinary `&amp;` reaching the query it names rather than landing in it.

    Marked owns each field's rendering, including flattened inline alt text, titles,
    and the literal character references in autolinks. Page-media inspection must use
    that same image alt for its accessible name.
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
    # The surviving link carries the chrome's external-link note, so the words are read
    # as a run inside the prose rather than as the whole of its text.
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
