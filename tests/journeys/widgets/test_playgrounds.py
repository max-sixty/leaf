"""Tests scheduled by the measured cost of their boundary."""

import io

import pytest
from browser.widgets.test_playgrounds import CONTRIBUTOR_PAGE, playground_values
from interact_support import wait_for
from PIL import Image, ImageChops
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    holding,
    http_error_console,
    nudge,
    open_page,
    post_event,
    resized,
    rgb_pixels,
    round_trip,
    sending,
    told,
    undo,
)

from browser.widgets import PLAYGROUND_PAGE
from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered, wait_until_ready
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_playground_records_an_edit_made_while_loading_or_as_the_page_leaves(
    browser, serve
):
    """An edit the pause hadn't recorded when the page reloads records as the page
    leaves, so the reload keeps it; one made before the page could record anything,
    while its state loads, records once it can. Leaving records nothing else, though
    a recorded value the controls can't hold draws as their default."""
    url = serve(PLAYGROUND_PAGE)
    page = open_page(browser, url)
    title = page.locator('input[name="title"]')

    def titles():
        return [
            event["detail"]["values"]["title"]
            for event in events_model.read_events(serve.page_dir)
            if event.get("action") == "tune"
        ]

    title.fill("Leaving note")
    page.reload()
    wait_until_ready(page)
    expect(title).to_have_value("Leaving note")
    assert titles()[-1:] == ["Leaving note"]

    held = []
    page.route("**/api/state", lambda route: held.append(route))
    page.reload()
    holding(page, held, 1, "the reloaded page's initial state")
    title.fill("Loading note")
    page.keyboard.press("Tab")
    held[0].continue_()
    page.unroute("**/api/state")
    wait_until_ready(page)
    wait_for(
        titles,
        lambda recorded: recorded[-1:] == ["Loading note"],
        failure="the edit made while the state loaded was never recorded",
    )

    values = {**playground_values(page), "radius": 40}
    response = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": events_model.read_events(serve.page_dir)[-1]["revision"],
            "widget": "card-playground",
            "action": "tune",
            "detail": {"values": values},
            "answered": False,
        },
    )
    assert response.ok
    recorded = len(titles())
    radius = page.get_by_role("slider", name="Corner radius")
    expect(radius).to_have_value("12")
    for _ in range(2):
        page.reload()
        wait_until_ready(page)
        expect(radius).to_have_value("12")
    # A leaving document posts as it hides, so an edit left for the next leave arrives
    # after whatever the two reloads' leaving documents posted.
    title.fill("Last note")
    page.reload()
    wait_until_ready(page)
    wait_for(
        titles,
        lambda now: now[-1:] == ["Last note"],
        failure="the edit left for the last leave was never recorded",
    )
    assert len(titles()) == recorded + 1, "leaving recorded more than its edit"


def test_playground_keeps_contributor_drafts_until_reset_or_a_new_choice(
    browser, serve
):
    """An input edit updates the shared configuration immediately, and reading or
    acknowledging it never replaces the draft. A new choice does; undoing or refusing
    one withdraws only the decision."""
    url = serve(CONTRIBUTOR_PAGE)
    page = open_page(browser, url)
    playground = page.locator("#query-config")
    field = page.get_by_role("textbox", name="Region filter")
    field.fill("us-east-1")
    expect(playground.locator("lf-playground-output")).to_have_text(
        "Implement checkout alerts for region us-east-1."
    )
    field.press("ArrowLeft")
    playground.get_by_role("radio", name="Billing", exact=True).click()
    expect(playground.get_by_role("radio", name="Billing", exact=True)).to_be_focused()
    expect(field).to_have_value("us-east-1")
    assert playground.evaluate("root => root.values.filters.region") == "us-east-1"

    field.fill("ap-south-1")
    # A later component registers while another component owns an unfinished edit.
    playground.evaluate("""root => {
      root.registerContributor('grouped', false, root.querySelector('#query-editor'));
    }""")
    expect(field).to_have_value("ap-south-1")
    assert playground.evaluate("root => root.values.filters.region") == "ap-south-1"

    field.fill("eu-north-1")
    playground.get_by_role("button", name="Checkout stream").click()
    expect(playground.get_by_role("button", name="Checkout stream")).to_be_focused()
    expect(field).to_have_value("eu-north-1")
    assert playground.evaluate("root => root.values") == {
        "stream": "checkout",
        "filters": {"region": "eu-north-1"},
        "grouped": False,
    }

    playground.get_by_role("button", name="Reset", exact=True).click()
    expect(field).to_have_value("eu-west-1")
    field.fill("chosen-region")
    # Programmatic activation leaves focus in the field: input alone has committed it.
    # Hold the choice itself. The tune that records the field goes through, whether
    # the click commits it or the playground's pause commits it before the click.
    held = []

    def hold_choice(route):
        if route.request.post_data_json.get("action") == "choose":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold_choice)
    with page.expect_request(
        lambda request: (
            "api/event" in request.url
            and request.post_data_json.get("action") == "choose"
        )
    ):
        playground.get_by_role("button", name="Use these settings").evaluate(
            "button => button.click()"
        )
    holding(page, held, 1, "the query configuration")
    expect(playground.get_by_role("button", name="Undo choice")).to_be_visible()
    field.fill("unsent-region")
    expect(playground.get_by_role("button", name="Use these settings")).to_be_visible()
    field.press("ArrowLeft")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    choice = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "query-config" and event.get("action") == "choose"
    )
    assert choice["detail"]["values"] == {
        "stream": "checkout",
        "filters": {"region": "chosen-region"},
        "grouped": False,
    }
    expect(field).to_have_value("unsent-region")
    expect(playground.get_by_role("button", name="Use these settings")).to_be_enabled()
    expect(field).to_be_focused()
    assert field.evaluate("input => input.selectionStart") == len("unsent-region") - 1
    nudge(serve.page_dir)
    told(page)
    expect(field).to_have_value("unsent-region")
    playground.evaluate("""root => lfUnwatched(() => {
      window.detachedQuery = {root, parent:root.parentNode, next:root.nextSibling};
      root.remove();
    })""")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
    consume_browser_errors(
        page,
        {
            "code": "words-left-screen",
            "words": "unsent-region",
            "place": ["input#region-filter"],
        },
    )
    page.evaluate("""() => lfUnwatched(() => {
      const {root, parent, next} = window.detachedQuery;
      parent.insertBefore(root, next);
      delete window.detachedQuery;
    })""")
    rendered(page)
    expect(field).to_have_value("unsent-region")
    # Another tab's settings replace the working values here, and its choice of them
    # is this tab's choice too. Undo steps the settings back one gesture, and a reload
    # draws the settings the log holds.
    for verb, detail in (
        ("tune", {"values": choice["detail"]["values"]}),
        ("choose", choice["detail"]),
    ):
        response = post_event(
            page,
            url.rsplit("/versions/", 1)[0] + "/api/event",
            data={
                "kind": "action",
                "revision": choice["revision"],
                "widget": "query-config",
                "action": verb,
                "detail": detail,
                # The choice in force answers it, the tune and the choice after it alike.
                "answered": True,
            },
        )
        assert response.ok
    expect(field).to_have_value("chosen-region")
    expect(playground.get_by_role("button", name="Undo choice")).to_be_enabled()
    billing = playground.get_by_role("radio", name="Billing", exact=True)
    billing.click()
    expect(playground.get_by_role("button", name="Use these settings")).to_be_enabled()
    round_trip(page)
    undo(page)
    expect(billing).not_to_be_checked()
    expect(field).to_have_value("chosen-region")
    expect(playground.get_by_role("button", name="Undo choice")).to_be_enabled()
    page.reload()
    wait_until_ready(page)
    expect(field).to_have_value("chosen-region")
    expect(playground.get_by_role("button", name="Undo choice")).to_be_enabled()

    # A refused choice leaves the configuration the user sent in the controls, to
    # send again, while the earlier choice stays decided.
    def refuse_choice(route):
        if route.request.post_data_json.get("action") != "choose":
            route.continue_()
            return
        route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        )

    page.route("**/api/event", refuse_choice)
    field.fill("refused-region")
    with sending(page, "the refused query configuration"):
        playground.get_by_role("button", name="Use these settings").click()
    expect(field).to_have_value("refused-region")
    expect(playground.get_by_role("button", name="Use these settings")).to_be_enabled()
    consume_browser_errors(page, http_error_console(400))
    page.unroute("**/api/event")

    # An admitted aggregate can precede every page-module contributor. Each joining
    # contributor gets its slice, and an undo keeps the slices still waiting for one.
    page.evaluate("sessionStorage.setItem('delay-query-contributors', 'true')")
    page.reload()
    wait_until_ready(page)
    assert playground.evaluate("root => root.values") == {"stream": "checkout"}
    assert (
        playground.evaluate("""root => {
      return root.registerContributor('grouped', true, root.querySelector('#query-editor')).get();
    }""")
        is False
    )
    undo(page)
    playground.evaluate("""root => {
      const input = document.querySelector('#region-filter');
      root.registerContributor('filters', {region:'eu-west-1'}, root.querySelector('#query-editor'));
      root.subscribe(values => {
        if (input.value !== values.filters.region) input.value = values.filters.region;
      });
    }""")
    expect(field).to_have_value("chosen-region")
    assert playground.evaluate("root => root.values") == {
        "stream": "checkout",
        "filters": {"region": "chosen-region"},
        "grouped": False,
    }


def test_a_short_workspace_shows_more_below_its_playground_regions(browser, serve):
    """In a workspace too short for them, the preview and the controls scroll, and each
    shows over its own content that more is below: the preview's code cards fill it to
    its edge, and a cue painted under them showed nothing. Focus within a region lifts
    its cue, and reaching the end removes it. The notification playground's long list
    also exercises the controls' continuation cue."""

    def cue(page, body):
        """How many pixels of the box's bottom band the mark changes. It puts the mark
        back only where it found one, since a box the runtime already marked as at its
        end is not marked again until it scrolls."""
        box = body.bounding_box()
        clip = {**box, "y": box["y"] + box["height"] - 12, "height": 12}
        marked = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
        had = body.evaluate("el => el.hasAttribute('data-lf-more-below')")
        body.evaluate("el => el.removeAttribute('data-lf-more-below')")
        bare = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
        body.evaluate("(el, had) => el.toggleAttribute('data-lf-more-below', had)", had)
        delta = rgb_pixels(ImageChops.difference(marked, bare))
        return sum(1 for pixel in delta if max(pixel) > 24)

    page = open_page(browser, serve(named_source("code-comparison")))
    resized(page, 1280, 540)
    preview = page.locator("#code-comparison-playground .lf-playground-preview-body")
    assert preview.evaluate("el => el.scrollHeight > el.clientHeight + 1")
    expect(preview).to_have_attribute("data-lf-more-below", "")
    assert cue(page, preview) > 100
    resized(page, 900, 600)
    width = page.get_by_role("slider", name="Comparison viewport")
    for _ in range(5):
        width.press("ArrowLeft")
    titles = page.locator("#code-reader-comparison .code-candidate-title")
    expect(titles.nth(0)).to_be_in_viewport(ratio=1)
    expect(titles.nth(1)).to_be_in_viewport(ratio=1)
    assert titles.nth(0).bounding_box()["y"] == pytest.approx(
        titles.nth(1).bounding_box()["y"], abs=1
    )

    page = open_page(browser, serve(named_source("notification-playground")))
    # Without a Controls label or a Starting points label over them, the list fits
    # at 600px tall; 530 still runs it past the rail's foot.
    resized(page, 1100, 530)
    playground = page.locator("#notification-playground")
    controls = playground.locator(".lf-playground-controls-region > aside")
    assert controls.evaluate("el => el.scrollHeight > el.clientHeight + 1")
    expect(controls).to_have_attribute("data-lf-more-below", "")
    # The cue fades whatever reaches the box's foot, and where a gap between two
    # controls lands there depends on their leading, so the first control the box
    # cuts off is scrolled up until its label sits under the cue.
    controls.evaluate(
        """el => {
            const cut = [...el.children].find(
                (c) => c.offsetTop + c.offsetHeight > el.scrollTop + el.clientHeight
            );
            el.scrollTop = Math.max(el.scrollTop, cut.offsetTop - el.clientHeight + 20);
        }"""
    )
    expect(controls).to_have_attribute("data-lf-more-below", "")
    assert cue(page, controls) > 100
    # A control Tab reaches is not faded out under its own ring.
    slider = playground.get_by_role("slider", name="Concurrent release events")
    slider.press("ArrowRight")
    page.keyboard.press("Tab")
    expect(playground.get_by_role("slider", name="Corner radius")).to_be_focused()
    assert cue(page, controls) == 0
    controls.evaluate("el => { el.scrollTop = el.scrollHeight; }")
    expect(controls).not_to_have_attribute("data-lf-more-below", "")
