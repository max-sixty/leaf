"""Everyday browser contracts for shared chrome."""

import io
import re
from urllib.parse import urljoin

import pytest
from leaf import event_log as events_model
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
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
    clean_browser,
    compare_with,
    consume_browser_errors,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    sending,
    told,
    watched,
)


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
        page = open_page(browser, url, context=context)
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
    page = open_page(browser, serve(html))
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
    panel_comment(serve.page_dir, "Is this ready?", author="claude")
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


def test_the_thread_card_rule_is_one_piece_of_arithmetic(browser, serve):
    """A preferred spot, then the boundary's clamp; the card's height is never cut."""
    page = open_page(browser, serve(LONG_PAGE))
    answers = page.evaluate(
        """async () => {
          const {threadCardGeometry} =
            await window.__lfRuntimeImport('/runtime/thread-card-geometry.js');
          // A 900px-tall viewport: the banner ends at 42, the bottom chrome starts at 855.
          const boundary = (width) => new DOMRect(8, 50, width - 16, 797);
          const cluster = (left, top) => new DOMRect(left, top, 37, 32);
          const ask = (width, at, natural) => threadCardGeometry({
            cluster: at, boundary: boundary(width), gap: 8, minWidth: 320,
            preferredWidth: 460, heightAt: () => natural});
          return {
            besideClamped: ask(1440, cluster(934, 436), 500),
            besideFits: ask(1440, cluster(934, 100), 500),
            besideWide: ask(2000, cluster(1400, 100), 500),
            tallInRail: ask(1160, cluster(794, 436), 500),
            tallCrossing: ask(1024, cluster(871, 436), 500),
            fitsUnder: ask(1024, cluster(871, 100), 300),
            fitsOver: ask(1024, cluster(871, 700), 300),
            clusterOverTheTop: ask(1024, cluster(871, 30), 300),
            narrowBoundary: ask(316, cluster(100, 100), 200),
            gone: [cluster(934, 900), cluster(934, 0)].map(at => ask(1440, at, 500).detached),
          };
        }"""
    )
    beside = answers["besideClamped"]
    assert (beside["placement"], beside["x"], beside["width"]) == ("right", 979, 453)
    assert (beside["y"], beside["detached"]) == (347, False)
    assert answers["besideFits"]["y"] == 100
    wide = answers["besideWide"]
    assert (wide["x"], wide["width"]) == (1445, 460)
    # Too tall for the room under or over its cluster, the card holds at the foot,
    # across the cluster, rather than taking either room's height.
    rail = answers["tallInRail"]
    assert (rail["placement"], rail["x"], rail["width"], rail["y"]) == (
        "below",
        794,
        358,
        347,
    )
    crossing = answers["tallCrossing"]
    assert (crossing["x"], crossing["width"], crossing["y"]) == (696, 320, 347)
    under = answers["fitsUnder"]
    assert (under["placement"], under["y"]) == ("below", 140)
    over = answers["fitsOver"]
    assert (over["placement"], over["y"]) == ("above", 392)
    top = answers["clusterOverTheTop"]
    assert (top["placement"], top["y"], top["detached"]) == ("below", 70, False)
    assert answers["narrowBoundary"]["width"] == 300
    assert answers["gone"] == [True, True]


PHONE_PAGE = leaf_page(
    "phone",
    "<h1 id='t'>Phone</h1><p id='p1'>Paragraph one. " + "Filler. " * 40 + "</p>",
    head='<meta name="viewport" content="width=device-width, initial-scale=1">',
)


def test_a_phone_starts_the_page_and_comments_on_a_selection(iphone, serve):
    """The runtime starts in WebKit, and a selection alone opens the comment field.

    A module feature WebKit lacks fails the whole module graph before the runtime runs:
    CSS module scripts did, and an iPhone reader saw only that Leaf could not start. A
    long press that selects words hands the page no mouseup, and Playwright cannot make
    one, so the selection is placed with no pointer gesture at all."""
    page = open_page(None, serve(PHONE_PAGE), context=iphone)
    page.locator("#p1").evaluate("""paragraph => {
      const range = document.createRange();
      range.setStart(paragraph.firstChild, 0);
      range.setEnd(paragraph.firstChild, "Paragraph one".length);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.tap()
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
        """(files) => {
          const rules = (sheet) => [...sheet.cssRules].map((rule) => rule.cssText);
          const fromFile = (text) => {
            const sheet = new CSSStyleSheet();
            sheet.replaceSync(text);
            return rules(sheet);
          };
          const [chrome, marks] = document.adoptedStyleSheets;
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
