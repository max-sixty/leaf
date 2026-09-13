"""Everyday browser contracts for shared chrome."""

import io
import re

import pytest
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    SUGGESTION_PAGE,
    panel_comment,
)
from render_cases_layout import (
    BANNER_ORDER,
    banner_control,
    button_radius,
    token_colour,
)
from render_cases_navigation import (
    _publish,
)
from render_harness import (
    LONG_PAGE,
    compare_with,
    open_page,
    panel_settled,
    resized,
)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_margin_reply_shares_its_conversations_opaque_surface(browser, serve, scheme):
    """The reply surround stays continuous as focus enters and leaves the conversation.

    An opaque shared surface also lets a pinned reply cover scrolled messages without
    introducing a differently colored band above its input.
    """
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page, errors = open_page(browser, url, color_scheme=scheme)
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

    assert errors == []


@pytest.mark.parametrize("width", [320, 800])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_thread_keeps_submit_in_its_field_and_resolve_beside_its_quote(
    browser, serve, width, scheme
):
    """Submit belongs to the field while Resolve stands beside the quoted target.

    Growing the field carries Submit with it and leaves Resolve fixed. The textarea
    reserves the icon's whole horizontal band, so words and a scrollbar do not run
    underneath it. Resolve aligns with the quoted target instead of either message's
    metadata. The same geometry holds in the panel's narrowest useful window and with
    room beside the page, in both palettes."""
    context = browser.new_context(
        viewport={"width": width, "height": 720}, color_scheme=scheme
    )
    try:
        url = serve(LONG_PAGE)
        panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
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
                          quote: rect('.lf-quote'),
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
                          padding,
                          overflow: thread.scrollWidth - thread.clientWidth};
                }"""
            )

        short = geometry()
        assert short["field"]["x"] == pytest.approx(short["compose"]["x"], abs=1)
        assert short["thread"]["right"] - short["compose"]["right"] == pytest.approx(
            short["compose"]["x"] - short["thread"]["x"], abs=1
        )
        assert short["textarea"]["right"] == pytest.approx(
            short["field"]["right"], abs=1
        )
        assert short["send"]["right"] < short["textarea"]["right"]
        assert short["send"]["bottom"] < short["textarea"]["bottom"]
        assert short["padding"] >= short["send"]["width"] + 10
        assert short["resolve"]["y"] == pytest.approx(short["quote"]["y"], abs=1)
        assert short["resolve"]["right"] == pytest.approx(
            short["thread"]["right"] - 9, abs=1
        )
        assert short["resolve"]["x"] - short["quote"]["right"] >= 8
        assert short["resolve"]["bottom"] <= short["quote"]["bottom"] + 1
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
        assert grown["resolve"] == short["resolve"]
        assert grown["overflow"] == 0
        assert errors == []
    finally:
        context.close()


STATE_PAINT = """el => {
  const style = getComputedStyle(el);
  return {background: style.backgroundColor, shadow: style.boxShadow};
}"""


def test_signoff_enabled_face_is_readable(browser, serve):
    """The banner's committing action keeps its positive face in the everyday gate."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page, errors = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_be_enabled()
    paint = button.evaluate(
        "el => ({ink: getComputedStyle(el).color, "
        "        fill: getComputedStyle(el).backgroundColor})"
    )
    assert paint == {
        "ink": token_colour(page, "--paper"),
        "fill": token_colour(page, "--accent"),
    }, f"the banner's primary action lost its readable face: {paint}"
    assert errors == []


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
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
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
    assert errors == []


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
    panel_comment(serve.page_dir, "Is this ready?", author="claude")
    page, errors = open_page(browser, url)
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
    assert errors == []


def test_notices_stay_at_the_visible_pages_right_edge(browser, serve):
    """A notice keeps the page's right corner through panel and viewport changes."""
    page, errors = open_page(browser, serve(LONG_PAGE))
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
          const {notice} = await import('/runtime/notifications.js');
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
    assert errors == []
