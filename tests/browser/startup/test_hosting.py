"""Where a page lives beyond its own tab: embedded at its own origin, arriving as a live
sample in a frame, and published on the Leaf website."""

import re
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect
from render_cases_interaction import SHORT_SUGGESTION, live_url
from render_harness import (
    TOKEN,
    consume_browser_errors,
    holding,
    http_error_console,
    is_problem,
    leaf_page,
    open_page,
    panel_control,
    panel_field,
    refuse,
    watched,
)

from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_live_page_embeds_at_its_own_origin_and_cannot_run_its_data(browser, serve):
    """A same-origin frame is an ordinary operable page; data never runs as code."""
    source = leaf_page(
        "Boundaries",
        """<h1 id="h">Boundaries</h1>
<lf-ask id="decision"><h2>Proceed?</h2><lf-options id="pick" choose>
<lf-option id="yes">Proceed</lf-option><lf-option id="no">Wait</lf-option>
</lf-options></lf-ask>""",
        head="""<script type="module">
window.authoredModuleRan = true;
</script>""",
    )
    page = open_page(browser, live_url(serve(source)))
    page.wait_for_function("() => window.authoredModuleRan === true")
    assert (
        page.evaluate(
            """async () => {
                  try {
                    await import('/api/state');
                    return 'executed';
                  } catch {
                    return 'blocked';
                  }
                }"""
        )
        == "blocked"
    )
    errors = consume_browser_errors(page, 'MIME type of "application/json"')
    assert any(
        is_problem(error, 'MIME type of "application/json"') for error in errors
    ), errors
    framed = page.locator("body").evaluate(
        """async (body, url) => {
              const frame = document.createElement('iframe');
              frame.id = 'framed-leaf';
              frame.src = url;
              const loaded = new Promise((resolve, reject) => {
                frame.addEventListener('load', resolve, {once: true});
                setTimeout(() => reject(new Error('framed Leaf did not settle')), 5000);
              });
              body.append(frame);
              await loaded;
              return frame.contentDocument?.querySelector('#h')?.textContent ?? null;
            }""",
        page.url,
    )
    assert framed == "Boundaries"
    frame = page.frame_locator("#framed-leaf")
    expect(frame.locator("body")).to_have_attribute("data-lf-presented", "1")
    frame.locator("#yes").click()
    page.wait_for_function(
        "() => document.querySelector('#yes')?.hasAttribute('chosen')"
    )
    assert any(
        event.get("kind") == "action"
        and event.get("widget") == "pick"
        and event.get("detail") == {"value": ["yes"]}
        for event in events_model.read_events(serve.page_dir)
    )


def test_a_live_page_refuses_a_same_site_parent_at_another_port(browser, serve):
    """SameSite cookies do not isolate ports, so a different origin can authenticate
    the frame even without knowing its key. CSP blocks disguising its controls."""
    context = browser.new_context()
    child = open_page(
        browser,
        live_url(serve(leaf_page("Child", '<h1 id="h">Child</h1>'))),
        context=context,
    )
    child_url = child.url
    parent_url = live_url(serve(leaf_page("Parent", '<h1 id="parent">Parent</h1>')))
    assert urlparse(child_url).port != urlparse(parent_url).port
    parent = open_page(browser, parent_url, context=context)
    with parent.expect_response(child_url) as loaded:
        parent.locator("body").evaluate(
            """async (body, url) => {
                const frame = document.createElement('iframe');
                frame.id = 'blocked-leaf';
                frame.src = url;
                const loaded = new Promise(resolve => frame.addEventListener('load', resolve, {once: true}));
                body.append(frame);
                await loaded;
            }""",
            child_url,
        )
    response = loaded.value
    assert response.status == 200
    assert TOKEN in response.request.all_headers()["cookie"]
    assert "t=" not in response.url
    errors = consume_browser_errors(parent, "Content Security Policy")
    assert any(is_problem(error, "frame-ancestors 'self'") for error in errors), errors
    assert parent.locator("#blocked-leaf").evaluate(
        "frame => frame.contentDocument === null"
    )


@pytest.mark.parametrize("outcome", ["presented", "abandoned", "offline", "slow"])
def test_public_startup_reports_upgrade_separately_from_held_state(
    browser, serve, outcome, request
):
    """Public telemetry names the independent browser and state milestones.

    A local delivered document gets the public release marker at the HTTP boundary.
    The real widget runtime upgrades while its first state read is held. A full
    Resource Timing buffer must not lose that response, an unrelated page's state
    must not stand in for it, and later polling or departure must not send again.
    A refused request has a Resource Timing entry but no state response to report.
    """
    url = serve(SHORT_SUGGESTION)
    page = browser.new_page()
    request.addfinalizer(page.close)
    reports = []
    held = []

    def public_document(route):
        response = route.fetch()
        route.fulfill(
            response=response,
            body=response.text().replace(
                "data-lf-server=", f'data-lf-release="{"a" * 64}" data-lf-server=', 1
            ),
        )

    def report(route):
        reports.append(route.request.post_data_json)
        route.fulfill(status=204)

    page.route("**/versions/v1.html?*", public_document)
    page.route("**/api/performance", report)
    page.route("**/api/state", lambda route: held.append(route))
    page.route("**/other/api/state", lambda route: route.fulfill(json={}))
    page.add_init_script(
        """performance.setResourceTimingBufferSize(1);
        window.firstStateResponses = [];
        new PerformanceObserver(list => {
          for (const entry of list.getEntries())
            if (new URL(entry.name).pathname === '/api/state')
              window.firstStateResponses.push(entry.responseEnd);
        }).observe({type: 'resource', buffered: true});"""
    )
    page.goto(url, wait_until="load")
    page.wait_for_function("document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state read"
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("^Loading comments and choices…")
    )
    assert reports == []
    assert page.evaluate("firstStateResponses") == []
    if outcome == "slow":
        page.clock.install()
        page.clock.fast_forward(16_000)
        assert reports == [], "a usable page waiting on state is not a startup timeout"
    upgraded_before_release = page.evaluate("Math.round(performance.now())")
    page.evaluate("async () => await (await fetch('/other/api/state')).json()")

    if outcome == "abandoned":
        with page.expect_response("**/api/performance"):
            page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
        assert len(reports) == 1
        assert reports[0]["firstStateResponseMs"] is None
        assert reports[0]["presentedMs"] is None

    released_at = page.evaluate("Math.round(performance.now())")
    if outcome != "abandoned":
        with page.expect_response("**/api/performance"):
            first = held.pop(0)
            if outcome == "offline":
                refuse(first)
                expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
            else:
                first.continue_()
                wait_until_ready(page)
    else:
        held.pop(0).continue_()
        wait_until_ready(page)
    page.wait_for_function("firstStateResponses.length === 1")
    with page.expect_request("**/api/state"):
        page.evaluate("void fetch('/api/state').then(response => response.json())")
    holding(page, held, 1, "the follow-up state read")
    held.pop(0).continue_()
    page.wait_for_function("firstStateResponses.length === 2")
    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    assert len(reports) == 1
    reading = reports[0]
    assert reading["outcome"] == (
        "presented" if outcome in {"offline", "slow"} else outcome
    )
    assert 0 <= reading["upgradedMs"] <= upgraded_before_release
    if outcome in {"presented", "slow"}:
        first_response = page.evaluate("Math.round(firstStateResponses[0])")
        assert reading["firstStateResponseMs"] == first_response
        assert first_response <= reading["presentedMs"]
        if outcome != "slow":
            # The slow case advances the JS timer clock, not Resource Timing.
            assert released_at <= first_response
        assert page.evaluate(
            """performance.getEntriesByType('resource').every(entry =>
                new URL(entry.name).pathname !== '/api/state')"""
        ), "the response remained in the global timeline; eviction was not tested"
    elif outcome == "offline":
        assert reading["firstStateResponseMs"] is None
        assert reading["presentedMs"] >= reading["upgradedMs"]


def test_a_website_example_shows_its_public_session_reference(browser, serve):
    url = live_url(
        serve(
            leaf_page("Website reference", "<h1>Website reference</h1>"),
            website_publication={
                "kind": "example",
                "agent": "Leaf guide",
                "install_url": "/#install",
            },
        )
    )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = context.new_page()
    watched(page)

    def identify(response_route):
        response = response_route.fetch()
        response_route.fulfill(
            response=response,
            headers={
                **response.headers,
                "Leaf-Session-Reference": "239383829012",
            },
        )

    page.route("**/api/state*", identify)
    page.goto(url, wait_until="load")
    wait_until_ready(page)
    # The reference is no part of the status the panel's field says, and one press in
    # the leaf's menu copies it.
    expect(panel_field(page)).not_to_have_attribute(
        "placeholder", re.compile("239383829012")
    )
    reference = panel_control(page, "session")
    expect(reference).to_have_text("Copy session reference")
    reference.click()
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("^Session reference copied")
    )
    assert page.evaluate("() => navigator.clipboard.readText()") == "239383829012"


@pytest.mark.parametrize(
    ("response", "status_words", "problem"),
    [
        (
            {"status": 503, "body": ""},
            "Lost the connection — reconnecting",
            http_error_console(503),
        ),
        (
            {"status": 200, "body": "{"},
            "Couldn't show the latest",
            "read failed",
        ),
    ],
)
def test_a_website_session_reference_survives_a_failed_first_read(
    browser, serve, response, status_words, problem
):
    url = live_url(serve(leaf_page("Failed website read", "<h1>Still a page</h1>")))
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(
        "**/api/state*",
        lambda route: route.fulfill(
            **response,
            headers={"Leaf-Session-Reference": "239383829012"},
        ),
    )
    try:
        page.goto(url, wait_until="load")
        expect(panel_field(page)).to_have_attribute(
            "placeholder", re.compile(status_words)
        )
        expect(panel_control(page, "session")).to_have_text("Copy session reference")
    finally:
        page.close()
    # The route stands for the whole test and the page asks again every two seconds,
    # so what it said is a complete list only once the page is gone.
    consume_browser_errors(page, problem)


SAMPLE_DOCUMENT = re.compile(r"/api/samples/([^/]+)/$")


# A page that does not start Leaf, answered for a sample document to make it fail.
NOT_LEAF = {"status": 200, "content_type": "text/html", "body": "<p>Unavailable</p>"}


def held_sample_page(
    browser, serve, body, *, head="", hold_first=True, documents=1, **options
):
    """A page whose live sample documents wait until `release()`: every sample's when
    `hold_first`, otherwise all but the first sample a page allocates, so an outer
    sample presents while the one inside it waits. `documents` is how many are held
    before this returns. `release(failing)` answers the documents of the samples whose
    element ids `failing` names with a page that does not start Leaf, and lets the
    rest through. `options` go to `new_page`. Returns the page and `release`."""
    page = browser.new_page(viewport={"width": 1200, "height": 900}, **options)
    watched(page)
    held = []
    passing = []
    # Each sample's allocation: its template, posted, and its document, answered.
    allocations = []
    page.on(
        "response",
        lambda response: (
            response.request.method == "POST"
            and response.url.endswith("/api/samples")
            and allocations.append(response)
        ),
    )

    def route(request_route):
        match = SAMPLE_DOCUMENT.search(request_route.request.url)
        assert match is not None
        sample = match.group(1)
        if not hold_first and (not passing or sample in passing):
            passing.append(sample)
            request_route.continue_()
        else:
            held.append(request_route)

    page.route(SAMPLE_DOCUMENT, route)
    page.goto(serve(leaf_page("Sample arrival", body, head=head)), wait_until="commit")
    holding(page, held, documents, "the samples' documents")

    def release(failing=()):
        templates = {f"{sample}-source" for sample in failing}
        broken = {
            next(SAMPLE_DOCUMENT.finditer(allocation.json()["url"])).group(1)
            for allocation in allocations
            if allocation.request.post_data_json["template"] in templates
        }
        page.unroute(SAMPLE_DOCUMENT)
        for each in held:
            match_2 = SAMPLE_DOCUMENT.search(each.request.url)
            assert match_2 is not None
            if match_2.group(1) in broken:
                each.fulfill(**NOT_LEAF)
            else:
                each.continue_()

    return page, release


def readiness(frame):
    return frame.evaluate(
        "document.querySelector('script[data-lf-entry]').lfReadiness(null)"
    )


def live_sample(sample_id, attributes="", content="<p>Practice</p>"):
    return (
        f'<lf-sample id="{sample_id}"{attributes}><template id="{sample_id}-source"'
        f" data-sample>{content}</template></lf-sample>"
    )


# A window sample whose child holds a sample below its own window, so the child
# presents while the inner sample's document can wait, and a link out of Leaf.
NESTED = (
    '<h1>Containing page</h1><lf-sample id="outer" window>'
    '<template id="outer-source" data-sample><h1>Outer</h1>'
    '<a href="about:blank" id="leave">Leave</a><div style="height: 300vh"></div>'
    '<lf-sample id="inner"><template id="inner-source" data-sample>'
    "<p>Inner</p></template></lf-sample></template></lf-sample>"
)


def test_a_sample_the_reader_would_see_arrive_holds_presentation(browser, serve):
    """A block sample whose growth the reader would see presents with the page, so
    the page's first presented frame already holds it at its child's height. A sample
    whose arrival would not be seen does not hold it
    (`test_a_sample_reached_while_loading_holds_growth_the_reader_did_not_cause`)."""
    page, release = held_sample_page(
        browser, serve, "<h1>Containing page</h1>" + live_sample("practice")
    )
    page.evaluate("""() => {
        window.presentedAtSampleReady = document.querySelector('#practice').ready.then(
            () => document.body.hasAttribute('data-lf-presented'));
    }""")
    release()
    wait_until_ready(page)
    assert page.evaluate("presentedAtSampleReady") is False


def test_a_sample_reached_while_loading_holds_growth_the_reader_did_not_cause(
    browser, serve
):
    """A block sample below the window starts loading at once, but the page presents
    and takes keys without it, reading as arriving until it has. A reader who scrolls
    to it while it loads sees its frame keep its loading height as the child arrives,
    so what follows stays put. Growth their own gesture in the child causes, such as a
    disclosure they open, applies at once. Growth the child makes of its own accord
    while still arriving waits until they press inside it, the frame leaves their
    sight, or the tab is hidden.

    The inner window sample's document is held throughout, so the child is still
    arriving at every step."""
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
                '<h1>Containing page</h1><div style="height: 300vh"></div>'
                + live_sample(
                    "practice",
                    content='<p id="top">Practice</p><details id="more">'
                    '<summary>More</summary><div style="height: 400px"></div>'
                    '</details><div id="room" style="height: 1200px"></div>'
                    + live_sample("inner", " window", "<p>Inner</p>"),
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

    def child_grows_by_itself(room):
        # Once the last gesture's rendering has settled, growth comes of nothing the
        # reader did, and the frame keeps its height.
        rendered(child_document)
        before = frame.evaluate(height)
        child.locator("#room").evaluate(
            f"room => {{ room.style.height = '{room}px'; }}"
        )
        rendered(child_document)
        rendered(page)
        assert frame.evaluate(height) == before
        return before

    child.locator("#more > summary").click()
    expect(child.locator("#more")).to_have_attribute("open", "")
    opened = child.locator("body").evaluate(body)
    grows_to(opened)

    child_grows_by_itself(1400)
    child.locator("#top").click()
    grows_to(opened + 200)

    child_grows_by_itself(1600)
    # Off the frame, so the wheel is the containing page's alone.
    assert page.evaluate("!document.elementFromPoint(5, 450).closest('lf-sample')")
    page.mouse.move(5, 450)
    page.mouse.wheel(0, -20000)
    grows_to(opened + 400)

    frame.scroll_into_view_if_needed()
    child_grows_by_itself(1800)
    page.evaluate("""() => {
      Object.defineProperty(document, 'visibilityState', {
        configurable: true, get: () => 'hidden',
      });
      document.dispatchEvent(new Event('visibilitychange'));
    }""")
    grows_to(opened + 600)


def test_a_narrow_window_samples_status_keeps_its_row_as_it_arrives_or_fails(
    browser, serve
):
    """A narrow window sample's status row keeps its size whatever it says, so
    neither the frame nor what follows moves when "Loading sample…" clears or a
    failure too long for the row replaces it, open or shut. The reader opens the
    failure to read it whole by Tab and Enter or by a press. At a mouse the row is a
    line high, so any growth of it shows."""
    page, release = held_sample_page(
        browser,
        serve,
        "<h1>Containing page</h1>"
        + live_sample("broken", " window")
        + live_sample("practice", " window")
        + "<p><button id=after>After the samples</button></p>",
        head="<style>#broken, #practice { width: 180px }</style>",
        documents=2,
    )
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-sample-status")).to_have_text(["Loading sample…"] * 2)
    places = """() => ['#broken iframe', '#practice iframe', '#after'].map(selector => {
        const box = document.querySelector(selector).getBoundingClientRect();
        return [box.left, box.top + scrollY, box.width, box.height];
    })"""
    before = page.evaluate(places)
    release(failing={"broken"})
    status = page.locator("#broken .lf-sample-status")
    summary = status.locator("details > summary")
    expect(summary).to_have_text("The sample document did not start Leaf")
    wait_until_ready(page)
    expect(page.locator("#practice .lf-sample-status")).to_have_text("")
    assert page.evaluate(places) == before
    clipped = "summary => summary.scrollWidth > summary.clientWidth"
    assert summary.evaluate(clipped)

    page.locator("#broken").get_by_role("button", name="Full view").focus()
    page.keyboard.press("Tab")
    expect(summary).to_be_focused()
    page.keyboard.press("Enter")
    expect(status.locator("details")).to_have_attribute("open", "")
    assert not summary.evaluate(clipped)
    assert page.evaluate(places) == before

    summary.click()
    expect(status.locator("details")).not_to_have_attribute("open", "")
    summary.click()
    expect(status.locator("details")).to_have_attribute("open", "")
    assert not summary.evaluate(clipped)
    assert page.evaluate(places) == before


def test_a_sample_counts_each_document_its_frame_loads(browser, serve):
    """A sample's child counts as arrived only once its own samples have, so the page
    holding it reads as arriving until then. A departure to a page that is not Leaf's
    ends the count of the document that left, whose inner sample never comes. Reset,
    and a Reset inside the sample's child, each begin a document the page counts as
    arriving until it, and the samples inside it, have arrived."""
    page, _ = held_sample_page(browser, serve, NESTED, hold_first=False)
    page.locator("#outer").evaluate("sample => sample.ready")
    child = page.locator("#outer iframe").content_frame
    expect(child.locator("body")).to_have_attribute("data-lf-presented", "1")
    assert readiness(page) == "arrived"
    child.locator("#leave").click()
    wait_until_ready(page)

    # The departed document's inner sample is never answered; from here every sample
    # document waits until its step releases it. Each new document starts with its
    # admission: the outer one Reset allocates, or the inner one the inner Reset does.
    page.unroute(SAMPLE_DOCUMENT)
    admissions = []
    page.on(
        "request",
        lambda request: request.method == "HEAD" and admissions.append(request),
    )

    def counts_until_released(reset):
        held = []
        page.route(SAMPLE_DOCUMENT, lambda route: held.append(route))
        admitted = len(admissions)
        reset.click()
        holding(page, admissions, admitted + 1, "the new document's sample admission")
        assert readiness(page) == "arrived"
        page.unroute(SAMPLE_DOCUMENT)
        for each in held:
            each.continue_()
        wait_until_ready(page)

    counts_until_released(page.locator("#outer").get_by_role("button", name="Reset"))
    counts_until_released(child.locator("#inner").get_by_role("button", name="Reset"))


def test_a_sample_arriving_again_holds_growth_the_reader_did_not_cause(browser, serve):
    """A Reset inside an arrived sample's child begins its arrival again, and while
    the new document waits the frame holds growth that came of nothing the reader
    did, as it did on the first arrival, so what follows the frame stays put."""
    page, release = held_sample_page(
        browser,
        serve,
        "<h1>Containing page</h1>"
        + live_sample(
            "outer",
            content='<div id="room" style="height: 400px"></div>'
            + live_sample("inner", " window", "<p>Inner</p>"),
        )
        + "<p><button id=after>After the sample</button></p>",
        hold_first=False,
    )
    release()
    wait_until_ready(page)
    frame = page.locator("#outer iframe")
    child = frame.content_frame
    child_document = frame.element_handle().content_frame()
    held = []
    page.route(SAMPLE_DOCUMENT, lambda route: held.append(route))
    child.locator("#inner").get_by_role("button", name="Reset").click()
    holding(page, held, 1, "the inner sample's new document")
    assert readiness(page) == "arrived"
    rendered(child_document)
    before = frame.evaluate("frame => frame.clientHeight")
    after = page.locator("#after").bounding_box()
    child.locator("#room").evaluate("room => { room.style.height = '700px'; }")
    rendered(child_document)
    rendered(page)
    assert frame.evaluate("frame => frame.clientHeight") == before
    assert page.locator("#after").bounding_box() == after
    page.unroute(SAMPLE_DOCUMENT)
    for each in held:
        each.continue_()
    wait_until_ready(page)
