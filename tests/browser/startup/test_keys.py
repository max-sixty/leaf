"""Keys before the page presents: printed keys held and replayed at upgrade, keys and
controls waiting for saved history, and the help overlay."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url
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
    first_frame,
)
from browser.startup.test_readiness import answer_as_another_runtime
from leaf.log import event_log as events_model
from leaf.source.render_checks import asked_again, rendered, wait_until_ready
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
            "emoji": "👍",
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
            or (event.get("emoji") == "👍" and event["id"] != "saved-reaction")
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
    chip = page.locator('.lf-response-options .lf-react[data-lf-emoji="👍"]')
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
        if event.get("emoji") == "👍"
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
        "emoji": "👍",
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
    # The error takes the field's words, and the held keys stand in its mode chip.
    expect(page.locator(".lf-fp-field .lf-fp-mode .lf-held-key")).to_have_text(
        ["e", "1"]
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
    """The words say held keys run when the page is ready, so no clock lets them go:
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
    not start, what was held is dropped, its words go, and later presses reach the
    page as they come."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held, _ = _hold_startup(page, "module")
    page.goto(asked_again(serve(HELD_KEYS_PAGE)), wait_until="commit")
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
    held: the keys are dropped, later presses reach the page, and the panel's row the
    document served goes with the chrome's sheet, since no panel will take it over."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    answered = []

    # The registry the runtime reads names another layer in its own `$layer`, which
    # speaks for the layer since its headers may be cached from an earlier release. The
    # source it asks next has not moved, so the page waits on this document rather
    # than reloading.
    def foreign(route):
        if answered:
            route.continue_()
            return
        answered.append(route)
        response = route.fetch()
        registry = response.json()
        registry["$layer"]["generation"] = "another-layer"
        route.fulfill(response=response, json=registry)

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
    expect(page.locator(".lf-floating-panel")).to_have_count(0)
    assert page.evaluate("() => document.adoptedStyleSheets.length") == 0
    page.keyboard.press("x")
    assert page.evaluate("heard") == ["x"]


@pytest.mark.parametrize("stage", ["module", "state"])
@pytest.mark.parametrize("touch", [False, True])
def test_a_key_pressed_before_presentation_runs_once_the_page_presents(
    browser, serve, stage, touch
):
    """`t` walks threads the first state answer brings, so a press before presentation
    is held, said in the floating panel's field, and replayed into the presented page —
    whether the runtime had not loaded, when the row the document served says it until
    the panel takes the row over, or had loaded and not yet read the log."""
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
    first_frame(page)
    expect(page.locator("#said")).to_be_visible()

    panel = page.locator(".lf-floating-panel")
    served = page.locator(".lf-floating-panel[data-lf-served]")
    field = panel.locator(".lf-fp-field")
    expect(panel).to_have_count(1)
    expect(served).to_have_count(1 if stage == "module" else 0)
    page.keyboard.press("t")
    expect(field.locator(".lf-held-key")).to_have_text("t")
    expect(field).to_contain_text("runs when the page is ready")
    if stage == "module":
        # A screen reader hears the held keys where the served row shows them, as it
        # does once the panel has mounted and announces them.
        expect(
            page.get_by_role("status").filter(has_text="runs when the page is ready")
        ).to_have_count(1)
    bounds = field.bounding_box()
    assert bounds and bounds["y"] >= 0
    assert bounds["y"] + bounds["height"] <= page.viewport_size["height"], bounds
    if stage == "module":
        # The panel takes the words over where the served row said them.
        release_module()
        holding(page, state, 1, "the state request")
        expect(served).to_have_count(0)
        expect(panel).to_have_count(1)
        expect(field.locator(".lf-held-key")).to_have_text("t")
        expect(field.locator("leaf-text")).to_have_attribute("data-lf-says", "held")
        moved = field.bounding_box()
        assert moved and abs(moved["y"] - bounds["y"]) < 1, (bounds, moved)
        # The row adopted the runtime's own chrome sheet, which stays adopted once.
        assert page.evaluate(
            "() => new Set(document.adoptedStyleSheets).size"
            " === document.adoptedStyleSheets.length"
        )
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


def test_a_folded_panel_stands_folded_from_the_first_paint_with_held_keys_in_its_peek(
    browser, serve
):
    """The reader left the panel folded to its leaf, so the row the document serves
    stands folded before the runtime loads, says held keys in the leaf's peek as the
    panel does, and the panel takes it over with the leaf where it stood."""
    url = serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD])
    page = open_page(browser, url)
    page.evaluate("() => window.lfStorage.userStore.set('lf-chrome-rest', 'mark')")
    module, release = _hold_startup(page, "module")
    page.reload(wait_until="commit")
    holding(page, module, 1, "the module request")
    first_frame(page)
    served = page.locator(".lf-floating-panel[data-lf-served]")
    expect(served).to_have_attribute("data-lf-rest", "mark")
    leaf = page.locator(".lf-floating-panel .lf-fp-leaf")
    at = leaf.bounding_box()
    page.keyboard.press("t")
    peek = page.locator(".lf-floating-panel .lf-fp-peek[data-lf-shown]")
    expect(peek.locator(".lf-held-key")).to_have_text("t")
    expect(page.get_by_role("status").filter(has_text="t")).to_have_count(1)

    release()
    expect(served).to_have_count(0)
    expect(page.locator(PANEL)).to_have_attribute("data-lf-rest", "mark")
    assert leaf.bounding_box() == pytest.approx(at, abs=1)
    expect(page.locator('[data-lf-thread="held-thread"]').first).to_be_focused()


def _served_field(browser, serve):
    """A page whose runtime module is held, standing its served row, and that row's
    field, and the release of the module."""
    url = serve(HELD_KEYS_PAGE, events=[HELD_KEYS_THREAD])
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    module, release = _hold_startup(page, "module")
    page.goto(url, wait_until="commit")
    holding(page, module, 1, "the module request")
    first_frame(page)
    served = page.locator(".lf-floating-panel[data-lf-served]")
    return page, served, served.locator(".lf-fp-served-field"), release


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_typed_in_the_served_field_go_on_in_the_panels_field(
    request, serve, engine
):
    """A reader who clicks the panel's field before the runtime loads and types writes
    words, not page keys: the field the document served, a textarea, takes them with
    the caret, Return makes a line, since nothing can send yet, and once the panel
    stands its field holds the words with the caret where it stood, so typing goes on
    there and `t` never walked to the thread. Firefox edits a field standing after
    `body`, as the chrome does, by rules of its own, so the test runs there too."""
    page, served, box, release = _served_field(request.getfixturevalue(engine), serve)
    box.click()
    expect(box).to_be_focused()
    expect(served.locator(".lf-fp-row")).to_have_attribute(
        "data-lf-control-focus-visible", ""
    )
    page.keyboard.type("fix itt")
    page.keyboard.press("Backspace")
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    expect(box).to_have_value("fix it\n")
    expect(served.locator(".lf-fp-words")).to_be_hidden()
    expect(page.locator(".lf-held-key")).to_have_count(0)
    words = box.bounding_box()

    release()
    expect(served).to_have_count(0)
    field = panel_field(page)
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "fix it\n")
    expect(field).to_have_js_property("selectionStart", 5)
    # The words stand where the served field drew them.
    moved = field.bounding_box()
    assert moved and words and abs(moved["x"] - words["x"]) < 1, (words, moved)
    page.keyboard.type("a")
    expect(field).to_have_js_property("value", "fix iat\n")
    wait_until_ready(page)
    expect(page.locator(".lf-held-key")).to_have_count(0)
    expect(field).to_be_focused()
    assert page.evaluate("() => scrollY") == 0


def test_words_left_in_the_served_field_wait_in_the_panels_field(browser, serve):
    """Words typed in the served field before the reader went back to the page wait in
    the panel's field once it stands, and the caret stays where the reader went."""
    page, served, box, release = _served_field(browser, serve)
    box.click()
    page.keyboard.type("fix it")
    page.locator("#said").click()
    expect(box).not_to_be_focused()
    expect(served.locator(".lf-fp-row")).not_to_have_attribute(
        "data-lf-control-focus-visible", ""
    )

    release()
    expect(served).to_have_count(0)
    expect(panel_field(page)).to_have_js_property("value", "fix it")
    expect(panel_field(page)).not_to_be_focused()
    assert page.evaluate("() => document.activeElement === document.body")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_the_panels_field_takes_backspace_before_its_editor_loads(
    request, serve, engine
):
    """Words typed in the served field go on in the panel's field as it mounts, before
    the field's editor has loaded, and Backspace and Shift+Return edit there: Firefox deletes nothing
    from a `contenteditable` standing after `body`, as the chrome does, so the field's
    box before its editor is a textarea."""
    page, served, box, release = _served_field(request.getfixturevalue(engine), serve)
    editor = []
    page.route("**/vendor/codemirror.esm.js*", lambda route: editor.append(route))
    box.click()
    page.keyboard.type("catz")

    release()
    expect(served).to_have_count(0)
    field = panel_field(page)
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "catz")
    holding(page, editor, 1, "the editor module")
    page.keyboard.press("Backspace")
    page.keyboard.type("s")
    expect(field).to_have_js_property("value", "cats")
    # Shift+Return makes a line there, as in the editor.
    page.keyboard.press("Shift+Enter")
    expect(field).to_have_js_property("value", "cats\n")
    page.keyboard.press("Backspace")

    page.unroute("**/vendor/codemirror.esm.js*")
    editor.pop().continue_()
    page.keyboard.press("Backspace")
    expect(field).to_have_js_property("value", "cat")


def test_words_in_the_served_field_stay_when_no_panel_comes(browser, serve):
    """A page that cannot start keeps the words typed in its served field where they
    were written, so the reader can still copy them, rather than taking the row away
    with them."""
    url = serve(HELD_KEYS_PAGE)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    module, _ = _hold_startup(page, "module")
    page.goto(asked_again(url), wait_until="commit")
    holding(page, module, 1, "the module request")
    first_frame(page)
    box = page.locator(".lf-floating-panel[data-lf-served] .lf-fp-served-field")
    box.click()
    page.keyboard.type("fix it")

    module.pop().abort()
    expect(
        page.get_by_text("Leaf couldn't start. Waiting for Leaf to update.")
    ).to_be_visible()
    expect(box).to_have_value("fix it")
    expect(box).to_be_visible()
    consume_browser_errors(page, "leaf.js", "net::ERR_FAILED")


def test_an_input_method_composing_as_the_panel_stands_finishes_first(browser, serve):
    """An input method still composing in the served field as the panel mounts
    finishes there, and the panel's field then takes the words it wrote, once: taken
    mid-composition, the unfinished letters stood before the method's own words."""
    page, served, box, release = _served_field(browser, serve)
    box.click()
    ime = page.context.new_cdp_session(page)
    ime.send(
        "Input.imeSetComposition",
        {"text": "にほ", "selectionStart": 2, "selectionEnd": 2},
    )
    expect(box).to_have_value("にほ")

    release()
    expect(page.locator(".lf-floating-panel:not([data-lf-served])")).to_be_visible()
    expect(served).to_have_count(1)
    ime.send("Input.insertText", {"text": "日本"})
    expect(served).to_have_count(0)
    field = panel_field(page)
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "日本")


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


# A page whose frames each take a while once Leaf takes the held keys, so the keys run
# one per slow frame and the user can act between them.
SLOW_REPLAY_PAGE = leaf_page(
    "Held keys",
    "<h1>Held keys</h1><p id='said'>A sentence the user commented on.</p>"
    """<script>
      document.addEventListener("lf-held-keys", () => {
        if (window.slowFrames) return;
        window.slowFrames = true;
        const slow = () => {
          const start = performance.now();
          while (performance.now() - start < 250) {}
          requestAnimationFrame(slow);
        };
        requestAnimationFrame(slow);
      });
    </script>""",
)

# The held keys the tab keeps for the page (bootstrap.js, `holdEarlyKeys`).
STORED_KEYS = """() => {
  const key = Object.keys(sessionStorage).find((key) => key.endsWith("lf-held-keys"));
  return key ? JSON.parse(sessionStorage.getItem(key)) : null;
}"""


def test_held_keys_still_to_run_go_when_the_user_steps_back(browser, serve):
    """Keys the user typed while the page started run one at a time once Leaf takes
    them. A step Back the user takes meanwhile leaves the entry they typed them at, so
    the keys still to run go, rather than run at the entry the step reached."""
    url = serve(SLOW_REPLAY_PAGE)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.goto(url)
    wait_until_ready(page)
    page.wait_for_function("navigation.transition === null")
    page.evaluate("location.hash = '#said'")
    page.wait_for_url(re.compile("#said$"))
    page.wait_for_function("navigation.transition === null")
    held, release = _hold_startup(page, "module")
    with page.expect_navigation(wait_until="commit"):
        page.evaluate("setTimeout(() => location.reload())")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    for key in ["c", "h", "e", "l", "l", "o"]:
        page.keyboard.press(key)
    expect(page.locator(".lf-held-key")).to_have_count(6)
    release()
    page.wait_for_function("window.slowFrames === true")
    page.go_back(wait_until="commit")
    assert page.evaluate(STORED_KEYS) is None
    expect(page.locator(".lf-held-key")).to_have_count(0)


# A document that hears of steps Back and Forward only through `popstate`, as a live
# sample's opaque frame does, whose Navigation API holds no entries.
POPSTATE_ONLY = """Object.defineProperty(navigation, "currentEntry", {
  get: () => null,
  configurable: true,
});"""


@pytest.mark.parametrize(
    "reload", ["the user's", "Leaf's, handing back a place", "heard by popstate alone"]
)
def test_held_words_outlast_a_step_the_page_takes_itself(browser, serve, reload):
    """Keys the user typed while the page started stay held through a step Back the
    page's own script takes, which the user didn't ask for, and land once Leaf starts:
    `c` opens the comment box and the rest are its words. So they do after a reload
    Leaf asked for, which hands back where the user was, and where the page hears of
    steps only through `popstate`, which can't say who took one."""
    url = live_url(serve(HELD_KEYS_PAGE))
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    if reload == "heard by popstate alone":
        page.add_init_script(POPSTATE_ONLY)
    page.goto(url)
    wait_until_ready(page)
    page.wait_for_function("navigation.transition === null")
    page.evaluate("location.hash = '#said'")
    page.wait_for_url(re.compile("#said$"))
    page.wait_for_function("navigation.transition === null")
    held, release = _hold_startup(page, "module")
    if reload.startswith("Leaf's"):
        answer_as_another_runtime(page)
        with page.expect_navigation(wait_until="commit"):
            append_carried_log_record(
                serve.page_dir,
                {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
            )
    else:
        with page.expect_navigation(wait_until="commit"):
            page.evaluate("setTimeout(() => location.reload())")
    holding(page, held, 1, "the runtime module")
    expect(page.locator("#said")).to_be_attached()
    if reload.startswith("Leaf's"):
        assert page.evaluate("window.lfStorage.placesUser()")
    for key in ["c", "h", "i"]:
        page.keyboard.press(key)
    expect(page.locator(".lf-held-key")).to_have_text(["c", "h", "i"])
    page.evaluate("history.back()")
    page.wait_for_function("location.hash === ''")
    expect(page.locator(".lf-held-key")).to_have_text(["c", "h", "i"])
    release()
    expect(page.locator("leaf-text:focus")).to_have_js_property("value", "hi")
    if reload.startswith("Leaf's"):
        page.unroute("**/api/**")
        page.unroute("**/registry.json")


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
    """Open or closed is state with one writer — not several writers and
    classList read-backs, the exact shape the first norm forbids.

    A section is its title, so two drafts on a page are one heading and a project
    widget declaring under a heading a standard one already uses joins it. That is
    the scope talking rather than the declaration: "On a draft" names where the
    user would be located, and there is one such place however many modules
    have something to say about it. Sections keyed on their exact rows would make
    the same heading twice two headings — and the user, who has one keyboard
    and one draft in front of them, would get the reference split in half."""
    html = JOURNEY_V1.replace(
        "</main>",
        '<lf-draft id="draft-second"><pre>A second editable draft.</pre></lf-draft></main>',
    )
    page = open_page(browser, serve(html))
    page.evaluate(
        """async () => {
          document.body.lfCommands = { title: 'On a draft', rows: [{ id: 'test.project-widget', keys: ['F2'],
                  title: 'a project widget using the same heading' }] };
          document.body.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
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
