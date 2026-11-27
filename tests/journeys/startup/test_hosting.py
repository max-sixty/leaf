"""Tests scheduled by the measured cost of their boundary."""

from urllib.parse import urlparse

import pytest
from browser.startup.test_hosting import (
    NESTED,
    SAMPLE_DOCUMENT,
    SAMPLE_REGISTRY,
    held_sample_page,
    live_sample,
    readiness,
)
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    holding,
    is_problem,
    leaf_page,
    open_page,
    watched,
)

from leaf.base import server as server_model
from leaf.source.render_checks import rendered, start_near_work, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_live_page_admits_only_leaf_parents_under_its_key(browser, serve, live_leaf):
    """SameSite cookies do not isolate ports, so any server on the host can
    authenticate a frame of a live page without knowing its key. CSP keeps every
    other origin from disguising its controls, and admits another live Leaf server
    under the same key, whose page then shows the framed page live."""
    child_url, _ = live_leaf("child", "Child")
    parent_url, _ = live_leaf("parent", "Parent")
    key = server_model.host_key()
    context = browser.new_context()
    # One keyed arrival earns the cookie every same-key frame below goes out under.
    open_page(browser, f"{child_url}/?t={key}", context=context)
    foreign = open_page(
        browser,
        live_url(serve(leaf_page("Foreign", '<h1 id="foreign">Foreign</h1>'))),
        context=context,
    )
    leaf = open_page(browser, f"{parent_url}/?t={key}", context=context)
    for parent in (foreign, leaf):
        assert urlparse(parent.url).port != urlparse(child_url).port
        with parent.expect_response(f"{child_url}/") as loaded:
            parent.locator("body").evaluate(
                """async (body, url) => {
                    const frame = document.createElement('iframe');
                    frame.id = 'framed-leaf';
                    frame.src = url;
                    const loaded = new Promise(resolve => frame.addEventListener('load', resolve, {once: true}));
                    body.append(frame);
                    await loaded;
                }""",
                f"{child_url}/",
            )
        response = loaded.value
        assert response.status == 200
        assert key in response.request.all_headers()["cookie"]
    errors = consume_browser_errors(foreign, "Content Security Policy")
    assert any(is_problem(error, "frame-ancestors 'self'") for error in errors), errors
    assert foreign.locator("#framed-leaf").evaluate(
        "frame => frame.contentDocument === null"
    )
    framed = leaf.frame_locator("#framed-leaf")
    expect(framed.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(framed.locator("#t")).to_have_text("Long")


def test_a_sample_counts_each_document_its_frame_loads(browser, serve):
    """A sample's child counts as arrived only once its own samples have, so the page
    holding it reads as arriving until then. A departure to a page that is not Leaf's
    ends the count of the document that left, whose inner sample never comes. Reset
    begins a document the page counts as arriving until it, and the samples inside
    it, have arrived."""
    page, _ = held_sample_page(browser, serve, NESTED, hold_first=False)
    page.locator("#outer").evaluate("sample => sample.ready")
    child = page.locator("#outer iframe").content_frame
    expect(child.locator("body")).to_have_attribute("data-lf-presented", "1")
    assert readiness(page) == "arrived"
    child.locator("#leave").click()
    wait_until_ready(page)

    # The departed document's inner sample is never answered; from here every sample
    # document waits until the step releases it. Each new document starts with its
    # admission.
    page.unroute(SAMPLE_DOCUMENT)
    admissions = []
    page.on(
        "request",
        lambda request: request.method == "HEAD" and admissions.append(request),
    )

    held = []
    page.route(SAMPLE_DOCUMENT, lambda route: held.append(route))
    page.locator("#outer").get_by_role("button", name="Reset").click()
    holding(page, admissions, 1, "the new document's sample admission")
    assert readiness(page) == "arrived"
    page.unroute(SAMPLE_DOCUMENT)
    for each in held:
        each.continue_()
    wait_until_ready(page)


def test_a_chart_in_a_sample_off_screen_waits_for_the_reader_and_a_check_shows_it(
    browser, serve
):
    """In Chromium a sample's page gets no rendering while its frame is off screen, so
    a chart in a sample out of view draws only once its frame shows. The page reads as
    ready without it: at once for a window sample, and for a block sample once the
    deadline on its height passes (host/sample.js, `SIZING_MS`). A check that reads every
    document the page can show brings each such frame into view, a sample's own
    samples included, waits for its chart, and puts back every box it scrolled,
    leaving nothing to move after it returns. One a scroll can't show, as in a box
    clipped to nothing, stays as the page has it."""
    chart = (
        '<lf-chart id="line" data-height="120"><pre>'
        '{ariaLabel: "A rising line", marks: [Plot.lineY([1, 3, 2, 4])]}'
        "</pre></lf-chart>"
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.goto(
        serve(
            leaf_page(
                "Charts",
                "<h1>Charts</h1>"
                + live_sample("shown", " window", chart)
                + '<div id="box" style="height: 200px; overflow: auto">'
                + '<div style="height: 1200px"></div>'
                + live_sample("boxed", " window", chart)
                + "</div>"
                + '<div style="max-height: 0; overflow: hidden">'
                + live_sample("clipped", " window", chart)
                + "</div>"
                + live_sample("block", "", chart)
                + '<div style="height: 900px"></div>'
                + live_sample(
                    "outer",
                    "",
                    '<div style="height: 1600px"></div>'
                    + live_sample("inner", " window", chart),
                ),
            )
        )
    )

    def drawn(*samples):
        frame = page
        for sample in samples:
            frame = frame.locator(f"#{sample} iframe").content_frame
        return frame.locator("lf-chart.lf-rendered").count()

    wait_until_ready(page)
    assert (drawn("shown"), drawn("boxed"), drawn("block")) == (1, 0, 0)
    start_near_work(page)
    assert (drawn("boxed"), drawn("block")) == (1, 1)
    assert (drawn("outer", "inner"), drawn("clipped")) == (1, 0)
    places = """() => [scrollY, document.querySelector('#box').scrollTop,
        document.querySelector('#outer iframe').getBoundingClientRect().height]"""
    after = page.evaluate(places)
    assert after[:2] == [0, 0]
    rendered(page)
    assert page.evaluate(places) == after


def test_a_sample_reached_while_loading_holds_growth_the_reader_did_not_cause(
    browser, serve
):
    """A block sample below the window but near it starts loading before the reader
    reaches it, and the page presents and takes keys without it, reading as arriving
    until it has. A reader who scrolls
    to it while it loads sees its frame keep its loading height as the child arrives,
    so what follows stays put, until the frame leaves their sight or the tab is
    hidden. A wheel over the frame scrolls past it and claims nothing. Once they click
    inside it, its growth is theirs: a disclosure they open, and growth the child makes
    of its own accord afterwards, apply at once.

    The inner window sample, in view in the child, keeps the child arriving until the
    final step, which checks that completing arrival does not release later
    unsolicited growth."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held = []
    passing = set()

    def hold(request_route):
        match_3 = SAMPLE_DOCUMENT.search(request_route.request.url)
        assert match_3 is not None
        if match_3.group(1) in passing:
            request_route.continue_()
        else:
            held.append(request_route)

    page.route(SAMPLE_DOCUMENT, hold)
    page.goto(
        serve(
            leaf_page(
                "Sample gesture",
                # Half a window below the window's foot, within a window of it.
                '<h1>Containing page</h1><div style="height: 150vh"></div>'
                + live_sample(
                    "practice",
                    content='<p id="top">Practice</p>'
                    + live_sample("inner", " window", "<p>Inner</p>")
                    + '<details id="more"><summary>More</summary>'
                    '<div style="height: 400px"></div></details>'
                    '<div id="room" style="height: 1200px"></div>',
                )
                + "<p><button id=after>After the sample</button></p>"
                '<div style="height: 300vh"></div>',
            )
        ),
        wait_until="commit",
    )
    holding(page, held, 1, "the sample's document")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    assert readiness(page) == "arrived"
    frame = page.locator("#practice iframe")
    frame.scroll_into_view_if_needed()
    loading = frame.bounding_box()["height"]
    after = page.locator("#after").bounding_box()
    # The sample's document goes on; the inner sample's, once asked for, waits.
    first = held.pop(0)
    match_4 = SAMPLE_DOCUMENT.search(first.request.url)
    assert match_4 is not None
    passing.add(match_4.group(1))
    first.continue_()
    expect(page.locator("#practice .lf-sample-status")).to_have_text("")
    holding(page, held, 1, "the inner sample's document")
    assert frame.bounding_box()["height"] == loading
    assert page.locator("#after").bounding_box() == after

    child = frame.content_frame
    child_document = frame.element_handle().content_frame()
    height = "frame => frame.clientHeight"
    body = "body => Math.ceil(body.getBoundingClientRect().height)"

    def grows_to(expected):
        page.wait_for_function(
            "h => document.querySelector('#practice iframe').clientHeight === h",
            arg=expected,
        )

    def child_grows(room):
        child.locator("#room").evaluate(
            f"room => {{ room.style.height = '{room}px'; }}"
        )
        return child.locator("body").evaluate(body)

    def child_grows_unseen(room):
        before = frame.evaluate(height)
        child_grows(room)
        rendered(child_document)
        rendered(page)
        assert frame.evaluate(height) == before

    child_grows_unseen(1400)
    # Off the frame, so the wheel is the containing page's alone.
    assert page.evaluate("!document.elementFromPoint(5, 450).closest('lf-sample')")
    page.mouse.move(5, 450)
    page.mouse.wheel(0, -20000)
    grows_to(child.locator("body").evaluate(body))

    frame.scroll_into_view_if_needed()
    child_grows_unseen(1600)
    # Over the frame, so the child's document hears the wheel too.
    on_frame = frame.bounding_box()
    x, y = on_frame["x"] + 20, max(on_frame["y"], 0) + 20
    assert page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y)?.localName === 'iframe'", [x, y]
    )
    page.mouse.move(x, y)
    before = frame.evaluate(height)
    page.mouse.wheel(0, 40)
    rendered(child_document)
    rendered(page)
    assert frame.evaluate(height) == before
    page.evaluate("""() => {
      Object.defineProperty(document, 'visibilityState', {
        configurable: true, get: () => 'hidden',
      });
      document.dispatchEvent(new Event('visibilitychange'));
    }""")
    grows_to(child.locator("body").evaluate(body))
    page.evaluate("""async () => {
      window.continuity = await window.__lfCheckApi();
      delete document.visibilityState;
      document.dispatchEvent(new Event('visibilitychange'));
    }""")
    # The reading resumes once the returning page's first refreshed reading lands.
    page.wait_for_function("continuity.readingReturn() === null")

    page.unroute(SAMPLE_DOCUMENT)
    for each in held:
        each.continue_()
    wait_until_ready(page)
    child_grows_unseen(1800)
    child.locator("#more > summary").click()
    expect(child.locator("#more")).to_have_attribute("open", "")
    grows_to(child.locator("body").evaluate(body))
    grows_to(child_grows(2000))


def test_a_sample_starts_its_page_as_it_nears_the_window(browser, serve):
    """A live sample far below the window, or in a closed disclosure, loads nothing,
    and the page reads ready without it while its `ready` waits. Scrolled to within a
    window's height of the window, it starts before the reader sees it, so by the time
    they reach it the frame stands at its child's height. Opening the disclosure starts
    the sample in it, and a page module's Reset starts one still waiting."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    allocated = []
    page.on(
        "request",
        lambda request: (
            request.method == "POST"
            and request.url.endswith("/api/samples")
            and allocated.append(request.post_data_json["template"])
        ),
    )
    page.goto(
        serve(
            leaf_page(
                "Samples far down",
                '<h1>Containing page</h1><div style="height: 400vh"></div>'
                + live_sample(
                    "far", content='<p>Far</p><div style="height: 700px"></div>'
                )
                + '<details id="fold"><summary>More</summary>'
                + live_sample("folded")
                + '</details><div style="height: 400vh"></div>'
                + live_sample("last"),
            )
        )
    )
    wait_until_ready(page)
    assert allocated == []
    waiting = """sample => {
        let settled = false;
        sample.ready.then(() => { settled = true; }, () => { settled = true; });
        return new Promise(done => requestAnimationFrame(() => setTimeout(() => done(settled))));
    }"""
    assert page.locator("#last").evaluate(waiting) is False

    far = page.locator("#far iframe")
    # Half a window below the window's foot.
    page.evaluate(
        """() => scrollBy(0, document.querySelector('#far iframe')
            .getBoundingClientRect().top - 1.5 * innerHeight)"""
    )
    page.locator("#far").evaluate("sample => sample.ready")
    assert allocated == ["far-source"]
    drawn = far.content_frame.locator("body").evaluate(
        "body => Math.ceil(body.getBoundingClientRect().height)"
    )
    assert drawn > 700
    far.scroll_into_view_if_needed()
    assert far.evaluate("frame => frame.clientHeight") == drawn

    page.locator("#fold > summary").click()
    page.locator("#folded").evaluate("sample => sample.ready")
    assert allocated == ["far-source", "folded-source"]

    page.locator("#last").evaluate("sample => sample.reset()")
    assert allocated == ["far-source", "folded-source", "last-source"]


def test_a_reader_who_looks_away_from_a_sample_they_were_shown_lets_the_page_go_on(
    browser, serve
):
    """A sample the reader sees as it starts holds what showed it, the page's
    presentation or the jump that brought it into view, until the frame fits its page.
    Once the reader scrolls past the frame its fit moves nothing they see, so the page
    presents and settles while its page still loads, as it must in Chromium, where a
    chart's page gets no rendering while its frame is off screen."""
    chart = (
        '<lf-chart id="line" data-height="120"><pre>'
        '{ariaLabel: "A rising line", marks: [Plot.lineY([1, 3, 2, 4])]}'
        "</pre></lf-chart>"
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held = []
    page.route(SAMPLE_REGISTRY, lambda request_route: held.append(request_route))
    page.goto(
        serve(
            leaf_page(
                "Charts",
                "<h1>Charts</h1>"
                + live_sample("first", "", chart)
                + '<div id="middle" style="height: 400vh"></div>'
                + live_sample("jumped", "", chart)
                + '<div style="height: 400vh"></div>',
            )
        ),
        wait_until="commit",
    )
    holding(page, held, 1, "the first sample's registry")
    page.locator("#jumped").evaluate("sample => sample.scrollIntoView()")
    holding(page, held, 2, "the jumped-to sample's registry")
    page.locator("#middle").evaluate("middle => middle.scrollIntoView()")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    rendered(page)
    page.unroute(SAMPLE_REGISTRY)
    for each in held:
        each.continue_()
