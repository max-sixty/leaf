"""Keys before the page presents: printed keys held and replayed at upgrade, keys and
controls waiting for saved history, and the help overlay."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_navigation import JOURNEY_V1, _publish
from render_harness import (
    PANEL,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    panel_field,
    panel_menu,
    panel_view,
    refuse,
    round_trip,
    select_words,
    watched,
)

from browser.startup import (
    HELD_KEYS_PAGE,
    _hold_startup,
)
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


HELD_KEYS_THREAD = {
    "id": "held-thread",
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Walk to me.",
    "anchor": {"section": "said"},
}


@pytest.mark.parametrize("command", ["unread", "reaction", "version"])
def test_history_dependent_keys_wait_for_the_first_read(browser, serve, command):
    """Saved-state commands keep their printed keys until their input arrives."""
    source = leaf_page(
        "First reading", '<h1>First reading</h1><button id="target">A target</button>'
    )
    event = (
        {
            "id": "unread-note",
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "A question for the reader.",
        }
        if command != "reaction"
        else {
            "id": "saved-reaction",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "keep",
            "anchor": {"section": "target"},
        }
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held, release = _hold_startup(page, "state")
    url = serve(source, events=[event])
    if command == "version":
        _publish(
            serve.page_dir,
            2,
            source.replace("A target", "A revised target"),
            "Revised target wording",
        )
        url = url.replace("v1.html", "v2.html")
    page.goto(url, wait_until="load")
    holding(page, held, 1, "the first private-state read")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    if command == "unread":
        page.keyboard.press("g")
        page.keyboard.press("u")
        expect(page.locator(".lf-held-key")).to_have_text("u")
    elif command == "version":
        page.keyboard.press("g")
        page.keyboard.press("Shift+V")
        expect(page.locator(".lf-held-key")).to_have_text("V")
    else:
        page.locator("#target").click()
        page.keyboard.press("e")
        page.keyboard.press("1")
        expect(page.locator(".lf-held-key")).to_have_text(["e", "1"])
        assert not any(
            event["kind"] == "undo"
            or (event.get("token") == "keep" and event["id"] != "saved-reaction")
            for event in events_model.read_events(serve.page_dir)
        )
    release()
    wait_until_ready(page)
    if command == "unread":
        expect(page.locator('.lf-msg[data-lf-event="unread-note"]')).to_be_focused()
    elif command == "version":
        expect(page.locator(panel_view("versions"))).to_be_visible()
    else:
        round_trip(page)
        events = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] in {"comment", "undo"}
        ]
        assert [(event["kind"], event.get("undoes")) for event in events] == [
            ("comment", None),
            ("undo", "saved-reaction"),
        ]
    expect(page.locator(".lf-held-key")).to_have_count(0)


@pytest.mark.parametrize("route", ["pointer", "digit"])
def test_response_reaction_controls_wait_for_history(browser, serve, route):
    """Reaction chips and their digit routes share the same input readiness."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held, release = _hold_startup(page, "state")
    posts = []
    page.on(
        "request",
        lambda request: (
            posts.append(request.post_data_json)
            if request.url.endswith("/api/event")
            else None
        ),
    )
    page.goto(serve(HELD_KEYS_PAGE), wait_until="load")
    holding(page, held, 1, "the first private-state read")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    select_words(page, "#said")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    page.keyboard.press("Tab")
    chip = page.locator('.lf-response-options .lf-react[data-lf-token="keep"]')
    expect(chip).to_be_visible()
    expect(chip).to_have_attribute("aria-disabled", "true")
    if route == "pointer":
        bounds = chip.bounding_box()
        page.mouse.click(
            bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
        )
        expect(chip).to_be_focused()
        assert posts == []
    else:
        page.keyboard.press("1")
        expect(page.locator(".lf-held-key")).to_have_text("1")
        assert posts == []
    release()
    wait_until_ready(page)
    if route == "pointer":
        expect(chip).not_to_have_attribute("aria-disabled", "true")
        chip.click()
    round_trip(page)
    reactions = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("token") == "keep"
    ]
    assert len(reactions) == 1
    assert reactions[0]["anchor"]["section"] == "said"


def test_package_reading_keys_work_while_history_waits_and_after_offline_fallback(
    browser, serve
):
    """Ordinary package UI stays usable; offline fallback discards pending history keys."""
    source = leaf_page(
        "Reading before history",
        '<h1>Reading before history</h1><lf-tabs id="reading-views">'
        '<lf-tab id="first" label="First">First view</lf-tab>'
        '<lf-tab id="second" label="Second">Second view</lf-tab></lf-tabs>',
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(serve(source), wait_until="load")
    holding(page, held, 1, "the first private-state read")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    first = page.get_by_role("tab", name="First", exact=True)
    second = page.get_by_role("tab", name="Second", exact=True)
    first.focus()
    page.keyboard.press("ArrowRight")
    expect(second).to_have_attribute("aria-selected", "true")
    page.get_by_role("heading", name="Reading before history").click()
    page.keyboard.press("t")
    expect(page.locator(".lf-held-key")).to_have_text("t")
    for route in held:
        refuse(route)
    held.clear()
    page.unroute("**/api/state*")
    page.route("**/api/state*", refuse)
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-held-key")).to_have_count(0)
    # The notice comes down when the controller takes the queue; its next
    # presentation frame finishes releasing the offline hold.
    rendered(page)
    second.focus()
    page.keyboard.press("ArrowLeft")
    expect(first).to_have_attribute("aria-selected", "true")
    page.evaluate("""() => window.addEventListener('keydown', event => {
      if (event.key === 'x') window.offlineKeyArrived = true;
    })""")
    page.keyboard.press("x")
    assert page.evaluate("window.offlineKeyArrived") is True
    expect(page.locator(".lf-held-key")).to_have_count(0)


def test_a_failed_first_read_stays_unpresented_across_the_retry_clock(browser, serve):
    """The retry tick cannot turn a malformed reading into an empty valid history."""
    source = leaf_page(
        "Failed first read",
        '<h1>Failed first read</h1><button id="target">A target</button>',
    )
    saved = {
        "id": "saved-reaction",
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "token": "keep",
        "anchor": {"section": "target"},
    }
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    calls, held = [], []
    gate = {"open": False}

    def intercept(route):
        calls.append(route)
        if len(calls) == 1:
            route.fulfill(status=200, content_type="application/json", body="not-json")
        elif gate["open"]:
            route.continue_()
        else:
            held.append(route)

    page.route("**/api/state*", intercept)
    with page.expect_console_message(
        predicate=lambda message: "read failed" in message.text
    ):
        page.goto(serve(source, events=[saved]), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    page.locator("#target").click()
    page.keyboard.press("e")
    page.keyboard.press("1")
    expect(page.locator(".lf-held-key")).to_have_text(["e", "1"])
    holding(page, held, 1, "the clock's retry of the malformed first read")
    rendered(page)
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("^Couldn't show the latest — reload")
    )
    assert (
        page.evaluate(
            "async () => (await window.__lfCheckApi()).readApplication().phase"
        )
        == "waiting"
    )
    gate["open"] = True
    for route in held:
        route.continue_()
    wait_until_ready(page)
    round_trip(page)
    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] in {"comment", "undo"}
    ]
    assert [(event["kind"], event.get("undoes")) for event in events] == [
        ("comment", None),
        ("undo", "saved-reaction"),
    ]
    consume_browser_errors(page, "read failed: Unexpected token")


def test_held_keys_outlast_any_wait_for_the_runtime(browser, serve):
    """The notice says held keys run when the page is ready, so no clock lets them go:
    a `t` held while the runtime takes half a minute to arrive still walks to the
    thread once the page presents."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.clock.install(time=0)
    page.clock.pause_at(1)
    watched(page)
    held, release = _hold_startup(page, "module")
    page.goto(serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD]), wait_until="commit")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    page.keyboard.press("t")
    page.clock.run_for(30_000)
    expect(page.locator(".lf-held-key")).to_have_text("t")
    page.clock.resume()
    release()
    expect(page.locator('[data-lf-thread="held-thread"]').first).to_be_focused()
    expect(page.locator(".lf-held-key")).to_have_count(0)


def test_a_page_that_cannot_start_lets_its_held_keys_go(browser, serve):
    """A runtime that will never arrive takes nothing: once the page reports it could
    not start, what was held is dropped, its notice goes, and later presses reach the
    page as they come."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held, _ = _hold_startup(page, "module")
    page.goto(serve(HELD_KEYS_PAGE), wait_until="commit")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    page.evaluate(
        "() => { window.heard = [];"
        " document.addEventListener('keydown', (e) => heard.push(e.key)); }"
    )
    page.keyboard.press("t")
    echo = page.locator(".lf-held-key")
    expect(echo).to_be_visible()
    assert page.evaluate("heard") == [], "the positive control: the press was held"

    held.pop().abort()
    expect(
        page.get_by_text("Leaf couldn't start. Waiting for Leaf to update.")
    ).to_be_visible()
    expect(echo).to_have_count(0)
    page.keyboard.press("x")
    assert page.evaluate("heard") == ["x"]
    consume_browser_errors(page, "leaf.js", "net::ERR_FAILED")


def test_a_document_the_runtime_gives_up_on_lets_its_held_keys_go(browser, serve):
    """A runtime that finds the server on another layer as it starts gives this document
    up and waits for a reload rather than upgrading it, so nothing will run what was
    held: the keys are dropped, the notice goes, and later presses reach the page."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    answered = []

    # The runtime's own read of the registry names another layer. The source it asks
    # next has not moved, so the page waits on this document rather than reloading.
    def foreign(route):
        if answered:
            route.continue_()
            return
        answered.append(route)
        route.fulfill(
            status=200,
            headers={"Content-Type": "application/json", "Leaf-Layer": "another-layer"},
            body="{}",
        )

    page.route("**/registry.json", foreign)
    held, release = _hold_startup(page, "module")
    page.goto(serve(HELD_KEYS_PAGE), wait_until="commit")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    page.evaluate(
        "() => { window.heard = [];"
        " document.addEventListener('keydown', (e) => heard.push(e.key)); }"
    )
    page.keyboard.press("t")
    echo = page.locator(".lf-held-key")
    expect(echo).to_be_visible()

    release()
    expect(echo).to_have_count(0)
    assert answered, "the runtime read the registry"
    expect(page.locator("body")).not_to_have_attribute("data-lf-upgraded", "1")
    page.keyboard.press("x")
    assert page.evaluate("heard") == ["x"]


@pytest.mark.parametrize("stage", ["module", "state"])
@pytest.mark.parametrize("touch", [False, True])
def test_a_key_pressed_before_presentation_runs_once_the_page_presents(
    browser, serve, stage, touch
):
    """`t` walks threads the first state answer brings, so a press before presentation
    is held, said in the floating panel's field, and replayed into the presented page —
    whether the runtime had not loaded, when a stand-in for the panel's row says it
    until the panel takes it over, or had loaded and not yet read the log."""
    url = serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD])
    page = browser.new_page(
        viewport={"width": 390 if touch else 1200, "height": 900}, has_touch=touch
    )
    watched(page)
    state, release_state = _hold_startup(page, "state")
    if stage == "module":
        module, release_module = _hold_startup(page, "module")
    page.goto(url, wait_until="commit")
    if stage == "module":
        holding(page, module, 1, "the module request")
    else:
        holding(page, state, 1, "the state request")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    expect(page.locator("#said")).to_be_visible()

    page.keyboard.press("t")
    panel = page.locator(".lf-floating-panel")
    stand_in = page.locator(".lf-floating-panel[data-lf-stand-in]")
    field = panel.locator(".lf-fp-field")
    expect(field.locator(".lf-held-key")).to_have_text("t")
    expect(field).to_contain_text("runs when the page is ready")
    expect(panel).to_have_count(1)
    expect(stand_in).to_have_count(1 if stage == "module" else 0)
    bounds = field.bounding_box()
    assert bounds and bounds["y"] >= 0
    assert bounds["y"] + bounds["height"] <= page.viewport_size["height"], bounds
    if stage == "module":
        # The panel takes the words over where the stand-in said them.
        release_module()
        holding(page, state, 1, "the state request")
        expect(stand_in).to_have_count(0)
        expect(panel).to_have_count(1)
        expect(field.locator(".lf-held-key")).to_have_text("t")
        expect(field.locator("leaf-text")).to_have_attribute("data-lf-says", "held")
        moved = field.bounding_box()
        assert moved and abs(moved["y"] - bounds["y"]) < 1, (bounds, moved)
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")

    release_state()
    # A margin card on a wide window; the panel's thread on a phone.
    expect(
        page.locator(
            f'{PANEL_THREAD}[data-lf-thread="held-thread"], '
            '.lf-margin-preview .lf-page-thread[data-lf-thread="held-thread"]'
        )
    ).to_be_focused()
    expect(page.locator(".lf-held-key")).to_have_count(0)


def test_held_keys_stand_beside_a_saved_draft(browser, serve):
    """A draft in the panel's field hides the words it says at rest, so keys held while
    the page reloads stand in the field's mode chip beside the draft, which stays."""
    url = serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD])
    page = open_page(browser, url)
    panel_field(page).click()
    page.keyboard.type("Half a thought")
    page.keyboard.press("Escape")
    expect(panel_field(page)).not_to_be_focused()
    held, release = _hold_startup(page, "state")
    page.reload(wait_until="commit")
    holding(page, held, 1, "the state request")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")

    page.keyboard.press("t")
    chip = page.locator(".lf-fp-field .lf-fp-mode")
    expect(chip.locator(".lf-held-key")).to_have_text("t")
    expect(chip).to_contain_text("runs when the page is ready")
    expect(panel_field(page)).to_have_js_property("value", "Half a thought")
    # However many keys wait, the draft keeps half the field.
    for _ in range(7):
        page.keyboard.press("t")
    expect(chip.locator(".lf-held-key")).to_have_count(8)
    widths = page.evaluate(
        """() => [document.querySelector('.lf-fp-field leaf-text'),
                  document.querySelector('.lf-fp-field')]
                 .map((node) => node.getBoundingClientRect().width)"""
    )
    assert widths[0] >= widths[1] * 0.45, widths

    release()
    expect(page.locator('[data-lf-thread="held-thread"]').first).to_be_focused()
    expect(chip).to_be_hidden()
    expect(panel_field(page)).to_have_js_property("value", "Half a thought")


def test_a_checkbox_keeps_page_keys_after_reveal(browser, serve):
    """A checkbox takes no letters, so its printed page key still walks threads."""
    url = serve(
        leaf_page(
            "Checkbox key",
            "<h1>Checkbox key</h1>"
            "<p id='said'>A sentence the user commented on.</p>"
            "<label><input type='checkbox' id='box'> Agreed</label>",
        ),
        events=[HELD_KEYS_THREAD],
    )
    page = open_page(browser, url)
    page.locator("#box").focus()
    page.keyboard.press("t")
    expect(page.locator('[data-lf-thread="held-thread"]').first).to_be_focused()


def test_editors_and_select_typeahead_keep_letters_while_history_waits(browser, serve):
    """A native field keeps typing and a select keeps typeahead while page keys wait."""
    url = serve(
        leaf_page(
            "Typing while loading",
            '<h1>Typing while loading</h1><p id="said">A commented sentence.</p>'
            '<textarea id="editor" aria-label="Notes"></textarea>'
            '<select id="pick" aria-label="Animal"><option>dog</option>'
            "<option>cat</option></select>",
        ),
        events=[HELD_KEYS_THREAD],
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held, release = _hold_startup(page, "state")
    page.goto(url, wait_until="commit")
    holding(page, held, 1, "the first state read")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    page.locator("#editor").click()
    page.keyboard.press("c")
    expect(page.locator("#editor")).to_have_value("c")
    page.locator("#pick").focus()
    page.keyboard.press("c")
    expect(page.locator("#pick")).to_have_value("cat")
    expect(page.locator(".lf-held-key")).to_have_count(0)
    page.locator("#said").click()
    page.keyboard.press("t")
    expect(page.locator(".lf-held-key")).to_have_text("t")
    release()
    expect(page.locator('[data-lf-thread="held-thread"]').first).to_be_focused()
    expect(page.locator("#editor")).to_have_value("c")


@pytest.mark.parametrize("stage", ["module", "state"])
def test_disabled_quick_shortcuts_are_not_held_before_presentation(
    browser, serve, stage
):
    """The saved preference applies before either bootstrap or controller can act."""
    url = serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD])
    page = open_page(browser, url)
    panel_menu(page).locator(".lf-fp-item", has_text="Keyboard shortcuts").click()
    page.get_by_role("checkbox", name="Quick keyboard shortcuts").uncheck()
    page.keyboard.press("Escape")
    held, release = _hold_startup(page, stage)
    page.reload(wait_until="commit")
    holding(page, held, 1, f"the {stage} request")
    expect(page.locator("#said")).to_be_visible()
    page.keyboard.press("t")
    expect(page.locator(".lf-held-key")).to_have_count(0)
    release()
    wait_until_ready(page)
    expect(page.locator('[data-lf-thread="held-thread"]:focus')).to_have_count(0)
    expect(page.locator(".lf-held-key")).to_have_count(0)


def test_disabling_quick_shortcuts_discards_keys_already_held(browser, serve):
    """Changing the shortcut preference during handover withdraws the held trip."""
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    watched(page)
    # The queue has transferred to the controller, but its first frame has not run.
    page.add_init_script(
        """document.addEventListener('lf-upgraded', () => queueMicrotask(() =>
          window.lfKeyboard.setQuick(false)));"""
    )
    held, release = _hold_startup(page, "module")
    page.goto(serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD]), wait_until="commit")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    try:
        expect(page.locator(".lf-held-key")).to_have_text(["g", "T"])
    finally:
        release()
    wait_until_ready(page)
    expect(page.locator(".lf-held-key")).to_have_count(0)
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", "threads")
    page.keyboard.press("t")
    expect(page.locator('[data-lf-thread="held-thread"]:focus')).to_have_count(0)


def test_a_key_pressed_while_held_keys_run_waits_its_turn(browser, serve):
    """Upgrade hands the held keys over and presses them a frame apart, so a key
    arriving between the handover and the first press has to queue behind them: `g`
    held, then `Shift+T` in that gap, is still `g T`, the trip to Threads."""
    url = serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD])
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    watched(page)
    # The instant is inside the page: after every upgrade listener has run,
    # the handover included, and before the next frame presses the first held key.
    page.add_init_script(
        """document.addEventListener('lf-upgraded', () => queueMicrotask(() =>
          document.body.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'T', code: 'KeyT', shiftKey: true, bubbles: true,
            cancelable: true, composed: true}))));"""
    )
    held, release = _hold_startup(page, "module")
    page.goto(url, wait_until="commit")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    page.keyboard.press("g")
    expect(page.locator(".lf-held-key")).to_have_text("g")

    release()
    expect(page.locator(PANEL)).to_have_attribute("data-lf-open", "threads")


def test_held_keys_after_one_that_opens_a_box_are_typed_into_it(browser, serve):
    """Pre-runtime `c` opens the comment box at upgrade.

    Keys held behind it arrive as comment text, Space included, rather than as page
    commands the box swallows."""
    url = serve(HELD_KEYS_PAGE)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held, release = _hold_startup(page, "module")
    page.goto(url, wait_until="commit")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    for key in ["c", "h", "i", "Space", "x"]:
        page.keyboard.press(key)
    expect(page.locator(".lf-held-key")).to_have_text(["c", "h", "i", "Space", "x"])

    release()
    expect(page.locator("leaf-text:focus")).to_have_js_property("value", "hi x")


@pytest.mark.parametrize("ending", ["Enter", "ControlOrMeta+a"])
def test_a_key_that_is_not_printed_ends_the_held_run(browser, serve, ending):
    """A held run is printed keys. Enter or a chord acts where focus stands, which a
    replay cannot reproduce and which must not act ahead of the keys before it, so after
    `c h i` it drops the run rather than waiting behind it: no comment box opens and
    nothing is sent. `test_held_keys_after_one_that_opens_a_box_are_typed_into_it` is
    the same run without the ending key; Shift alone leaves the run in place."""
    url = serve(HELD_KEYS_PAGE)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held, release = _hold_startup(page, "module")
    page.goto(url, wait_until="commit")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    for key in ["c", "h", "i"]:
        page.keyboard.press(key)
    echo = page.locator(".lf-held-key")
    expect(echo).to_have_text(["c", "h", "i"])
    page.keyboard.press("Shift")
    expect(echo).to_have_count(3)

    page.keyboard.press(ending)
    expect(echo).to_have_count(0)
    release()
    wait_until_ready(page)
    # A replay would run a frame after presentation; let the repaint it causes land.
    rendered(page)
    expect(page.locator("leaf-text:focus")).to_have_count(0)


@pytest.mark.parametrize("gesture", ["Escape", "pointer"])
def test_escape_or_a_pointer_press_lets_go_of_held_keys(browser, serve, gesture):
    """A user who changes their mind, or points somewhere else, while the page loads
    does not have their earlier keys run later."""
    url = serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD])
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held, release = _hold_startup(page, "state")
    page.goto(url, wait_until="commit")
    holding(page, held, 1, "the first state read")
    page.keyboard.press("t")
    echo = page.locator(".lf-held-key")
    expect(echo).to_be_visible()

    if gesture == "Escape":
        page.keyboard.press("Escape")
    else:
        page.mouse.click(600, 450)
    expect(echo).to_have_count(0)

    release()
    wait_until_ready(page)
    # A replay would run a frame after presentation; let the repaint it causes land.
    rendered(page)
    assert page.evaluate("() => !document.activeElement?.closest('[data-lf-thread]')")
    # The positive control: the same key on the presented page walks to the thread.
    page.keyboard.press("t")
    expect(page.locator('[data-lf-thread="held-thread"]').first).to_be_focused()


def test_the_help_overlay_answers_to_one_owner(browser, serve):
    """Open or closed is state with one writer now — it was three writers and
    two classList read-backs, the exact shape the first norm forbids.

    A section is its title, so two drafts on a page are one heading and a project
    widget declaring under a heading a standard one already uses joins it. That is
    the scope talking rather than the declaration: "On a draft" names where the
    user would be located, and there is one such place however many modules
    have something to say about it. Sections used to key on their exact rows, so
    the same heading twice was two headings — and the user, who has one keyboard
    and one draft in front of them, got the reference split in half."""
    html = JOURNEY_V1.replace(
        "</main>",
        '<lf-draft id="draft-second"><pre>A second editable draft.</pre></lf-draft></main>',
    )
    page = open_page(browser, serve(html))
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          document.body.lfCommands = { title: 'On a draft', rows: [{ id: 'test.project-widget', keys: ['F2'],
                  title: 'a project widget using the same heading' }] };
          commandsChanged(document.body);
        }"""
    )
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    expect(
        page.locator(".lf-command-reference h3", has_text="On a draft")
    ).to_have_count(1)
    expect(
        page.locator(
            ".lf-command-reference", has_text="a project widget using the same heading"
        )
    ).to_be_visible()
    expect(
        page.locator(
            '.lf-command-reference [role=option][data-lf-command="draft.edit"]'
        )
    ).to_be_attached()
    # Help is a scope: the table stands down behind it, so c must open nothing under
    # the sheet, neither a panel view nor the page comment in the panel's field.
    page.keyboard.press("c")
    expect(page.locator(f"{PANEL}[data-lf-open]")).to_have_count(0)
    expect(panel_field(page)).not_to_be_focused()
    expect(page.locator(".lf-command-reference")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-command-reference")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    page.mouse.click(300, 600)
    expect(page.locator(".lf-command-reference")).to_be_hidden()
