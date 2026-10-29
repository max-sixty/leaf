"""Which modules a page fetches and when: widget modules its markup uses, lazy renderers
and placement, and startup that proceeds while the registry waits."""

import re
from urllib.parse import urlparse

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, response_reference
from playwright.sync_api import expect
from render_cases_interaction import SUGGESTION_PAGE
from render_cases_navigation import JOURNEY_V1, SENTENCE
from render_cases_widgets import MANIFEST_DIFF_PAGE, MULTI_HUNK_PATCH, TYPED_PARTS_PAGE
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    PANEL,
    PANEL_THREAD,
    RELEASE_FOCUS,
    consume_browser_errors,
    holding,
    open_page,
    open_threads,
    page_comment,
    panel_view,
    primed,
    refuse,
    round_trip,
    select,
    sending,
    told,
    watched,
    write,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import data as data_model
from leaf.render_checks import wait_until_ready
from leaf.runtime_selection import serving_runtime
from leaf_dev.example_data import patch_manifest

pytestmark = pytest.mark.shifts_unsurveyed


def test_startup_continues_while_the_registry_fetch_is_held(browser, serve):
    """The chrome and initial state read do not wait behind widget startup.

    That interval is real state, not a missing-registry fallback: the state answer waits
    unapplied until upgrades have captured the authored page, the page comment card accepts
    a send and paints its pending thread while holding delivery until the layer identity
    arrives. Anchored capture waits for widget upgrade to establish the visible document.
    The explicit gate
    proves each assertion runs on the intended side of the fetch rather than racing a timer.
    """
    gate_registry = """
      const nativeFetch = window.fetch.bind(window);
      window.lfRegistryGate = new Promise(resolve => window.lfReleaseRegistry = resolve);
      window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        const path = new URL(url, location.href).pathname;
        if (path.endsWith('/registry.json')) {
          window.lfRegistryBlocked = true;
          return window.lfRegistryGate.then(() => nativeFetch(...args));
        }
        const response = await nativeFetch(...args);
        if (path === '/api/state') window.lfInitialStateReceived = true;
        return response;
      };
    """
    html = JOURNEY_V1.replace(
        '<h2 id="notes">',
        """
<lf-code id="gate-code"><pre>Build feeders
Two classic models.</pre></lf-code>
<h2 id="notes">""",
    )
    page = open_page(
        browser,
        serve(html, anchored=[("intro", SENTENCE)]),
        init_script=gate_registry,
        wait_until="domcontentloaded",
        # The held registry is this test's subject, so the upgrade stamp never lands and
        # waiting for it would hang out a whole timeout.
        upgraded=False,
    )
    page.wait_for_function("() => window.lfRegistryBlocked === true")
    page.wait_for_function("() => window.lfInitialStateReceived === true")
    expect(page.locator("body")).not_to_have_attribute(
        "data-lf-applied", re.compile(".")
    )
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(page.locator("body > main")).to_be_visible()
    assert (
        page.evaluate("() => getComputedStyle(document.body, '::after').content")
        == "none"
    )
    expect(page.locator(PANEL)).to_be_visible()
    expect(page.locator(".lf-fp-on-user")).to_be_enabled()
    expect(page.locator("#gate-code .lf-code-line")).to_have_count(0)
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_count(0)

    rows = page.locator(f"{panel_view('threads')} .lf-fp-thread")
    open_threads(page)
    expect(rows).to_have_count(0)
    write(page_comment(page), "General comment during startup")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-live")).to_have_text("Message added")
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0

    # The visible document has not upgraded yet, so anchored capture is not ready.
    expect(page.locator(".lf-composer")).to_be_hidden()

    page.evaluate("window.lfReleaseRegistry()")
    open_threads(page)
    expect(rows).to_have_count(2)
    expect(page.locator("#gate-code .lf-code-line")).to_have_count(2)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    page.wait_for_function("() => document.body.dataset.lfPresented === '1'")
    words = page.locator("#gate-code .lf-code-line").first.bounding_box()
    assert words, "the upgraded code never produced selectable words"
    y = words["y"] + words["height"] / 2
    select(
        page,
        (words["x"] + 2, y),
        (words["x"] + words["width"] - 2, y),
    )
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Still anchored?")
    page.keyboard.press("ControlOrMeta+Enter")

    open_threads(page)
    expect(rows).to_have_count(3)
    # The comment on the code's words found them: its quote is no detached one.
    rows.filter(has_text="Still anchored?").click()
    quote = page.locator(f"{PANEL_THREAD} .lf-fp-quote")
    expect(quote).to_be_visible()
    expect(quote).not_to_have_class(re.compile(r"\bdetached\b"))


def _asked(context):
    """Every logical resource this context asks for, listening before the first one.

    The count is what the reading is about, so the listener goes on the context rather
    than on a page: `open_page` makes the page and navigates it in one call, and a
    listener attached to what it hands back has already missed the document, the theme,
    the registry and every module. Revision resources are immutable addresses; these
    tests compare the logical module or asset loaded, so strip only that captured prefix.
    """
    paths = []

    def record(request):
        path = urlparse(request.url).path
        paths.append(
            re.sub(r"^/revisions/r\d+-[0-9a-f]+/[0-9a-f]+|^/[0-9a-f]+", "", path)
        )

    context.on("request", record)
    return paths


def test_a_page_loads_only_the_widget_modules_its_markup_uses(browser, serve):
    """The vocabulary is the layer's; the modules are this page's.

    Every declared `x-upgrade` tag used to import on every page, so a triage board
    with no diff anywhere on it fetched Pierre's renderer, and that one module was
    more than half the bytes the page moved. The board page's own modules, the board,
    its grid and its activity feed, are the population: a page that asked for nothing
    would satisfy every refusal below and
    say nothing about which of them holds.

    The shadow rules follow the same line: `/shadow.css` is what an `x-shadow` widget
    renders under, so a page with no such widget never asks for it, and the theme
    arrives once, through the document's `<link>`.
    """
    example = next(p for p in EXAMPLES if p.stem == "triage-board")
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    asked = _asked(context)
    page = open_page(browser, serve(example), context=context)

    modules = sorted(p for p in asked if p.startswith("/widgets/"))
    assert modules == [
        "/widgets/lf-activity.js",
        "/widgets/lf-board.js",
    ], modules
    assert not [p for p in asked if "pierre-diffs" in p], asked
    assert not [p for p in asked if "pele" in p], asked
    assert asked.count("/theme.css") == 1, [p for p in asked if p == "/theme.css"]
    assert "/shadow.css" not in asked, asked
    assert asked.count("/registry.json") == 1, [
        p for p in asked if p == "/registry.json"
    ]

    assert page.evaluate("() => !!customElements.get('lf-board')")


def test_composers_take_their_fields_when_they_first_open(browser, serve):
    """The comment composer holds no field on the page until it first opens, since a
    field on the page builds its editor (composing/selection.js). Its open, and `c` into
    the panel's page comment, place the caret in the same turn, so the words typed
    straight after land there, and a draft kept from before a reload reaches the field
    when its composer opens again."""
    page = open_page(browser, serve(LONG_PAGE))
    card_box = page.locator('.lf-fp-field leaf-text[name="comment"]')
    composer_box = page.locator("#lf-composer leaf-text")
    expect(composer_box).to_have_count(0)

    page.keyboard.press("c")
    page.keyboard.type("Words for the page")
    expect(card_box).to_be_focused()
    expect(card_box).to_have_js_property("value", "Words for the page")
    page.keyboard.press("Escape")

    box = page.locator("#p10").bounding_box()
    select(page, (box["x"] + 4, box["y"] + 6), (box["x"] + 150, box["y"] + 6))
    page.keyboard.press("c")
    expect(composer_box).to_be_focused()
    page.keyboard.type("Words for the passage")
    expect(composer_box).to_have_js_property("value", "Words for the passage")

    page.reload()
    wait_until_ready(page)
    expect(composer_box).to_have_js_property("value", "Words for the passage")
    page_comment(page)
    expect(card_box).to_have_js_property("value", "Words for the page")


def test_diagrams_load_one_renderer_bundle_when_they_draw(browser, serve):
    """The page's six diagram types share one lazy module import and one vendored file."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    asked = _asked(context)
    page = open_page(browser, serve(TYPED_PARTS_PAGE), context=context)

    expect(page.locator("lf-diagram svg")).to_have_count(6)
    assert [p for p in asked if "pele" in p] == ["/vendor/pele.esm.js"]


def test_comment_focus_waits_for_the_lazy_placement_module(browser, serve):
    """The positioning engine stays off the presentation path: held, it keeps the page
    from reading as arrived but not from presenting. A comment entered before it has
    arrived keeps its focus request while it loads, rather than focusing a still-hidden
    text box."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    held = []
    context.route("**/vendor/floating-ui.esm.js", lambda route: held.append(route))
    page = open_page(browser, serve(LONG_PAGE), context=context, upgraded=False)
    field = page.locator(".lf-fab-input")
    try:
        wait_until_ready(page, through="presented")
        holding(page, held, 1, "the response placement module")
        assert (
            page.evaluate(
                "() => document.querySelector('script[data-lf-entry]').lfReadiness(null)"
            )
            == "arrived"
        )
        box = page.locator("#p10").bounding_box()
        select(
            page,
            (box["x"] + 4, box["y"] + 6),
            (box["x"] + 150, box["y"] + 6),
        )
        page.keyboard.press("c")
        expect(field).to_be_hidden()
        assert page.evaluate("() => document.activeElement === document.body")
        assert page.evaluate("() => getSelection().toString().length > 0")

        held.pop(0).continue_()
        expect(field).to_be_visible()
        expect(field).to_be_focused()
        assert page.evaluate("() => getSelection().toString()") == ""
    finally:
        for route in held:
            route.continue_()
        context.unroute_all(behavior="wait")


def _hold_the_editor(context):
    """Hold CodeMirror's module; the returned list collects each held request."""
    held = []
    context.route("**/vendor/codemirror.esm.js", lambda route: held.append(route))
    return held


def _release(page, held, context):
    while held:
        held.pop(0).continue_()
    wait_until_ready(page)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_typed_while_the_editor_loads_are_its_first_words(engine, request, serve):
    """CodeMirror stays off the presentation path: held, it keeps the page from reading
    as arrived but not from presenting. `c` still puts the user in the page comment's
    field in the same turn, and what they type before CodeMirror arrives, where they
    moved the caret to and the line Shift+Return broke included, is what the editor
    holds once it does, as one step undo takes back."""
    browser = request.getfixturevalue(engine)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    held = _hold_the_editor(context)
    page = open_page(browser, serve(LONG_PAGE), context=context, upgraded=False)
    field = page.locator('.lf-fp-field leaf-text[name="comment"]')
    try:
        wait_until_ready(page, through="presented")
        holding(page, held, 1, "CodeMirror")
        assert (
            page.evaluate(
                "() => document.querySelector('script[data-lf-entry]').lfReadiness(null)"
            )
            == "arrived"
        )
        page.keyboard.press("c")
        expect(field).to_be_focused()
        page.keyboard.type("Typed early")
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft")
        page.keyboard.type(" and")
        page.keyboard.press("Shift+Enter")
        expect(field).to_have_js_property("value", "Typed ear and\nly")
        expect(field).to_have_js_property("selectionStart", len("Typed ear and\n"))

        _release(page, held, context)
        expect(field).to_be_focused()
        page.keyboard.type("kept ")
        expect(field).to_have_js_property("value", "Typed ear and\nkept ly")
        page.keyboard.press("ControlOrMeta+z")
        expect(field).to_have_js_property("value", "Typed ear and\nly")
        page.keyboard.press("ControlOrMeta+z")
        expect(field).to_have_js_property("value", "")
    finally:
        for route in held:
            route.continue_()
        context.unroute_all(behavior="wait")


def test_a_kept_draft_and_an_input_method_reach_the_editor_as_it_loads(browser, serve):
    """While CodeMirror loads, a field's kept draft stands in its place with the caret
    where the draft left it, so words typed on arrival follow the draft, and a selection
    the page sets is where typing lands. Words an input
    method is still composing as CodeMirror lands join the field once committed, once."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = open_page(browser, serve(LONG_PAGE), context=context)
    field = page.locator('.lf-fp-field leaf-text[name="comment"]')
    page.keyboard.press("c")
    page.keyboard.type("Kept")
    expect(field).to_have_js_property("value", "Kept")
    held = _hold_the_editor(context)
    try:
        page.reload()
        wait_until_ready(page, through="presented")
        holding(page, held, 1, "CodeMirror")
        page.keyboard.press("c")
        expect(field).to_be_focused()
        page.keyboard.type(" words")
        expect(field).to_have_js_property("value", "Kept words")
        # A selection the page sets stands where the user types next.
        field.evaluate("(field) => field.setSelectionRange(0, 4)")
        page.keyboard.type("Held")
        expect(field).to_have_js_property("value", "Held words")
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.press("Backspace")
        expect(field).to_have_js_property("value", "")

        ime = context.new_cdp_session(page)
        ime.send(
            "Input.imeSetComposition",
            {"text": "にほ", "selectionStart": 2, "selectionEnd": 2},
        )
        _release(page, held, context)
        ime.send("Input.insertText", {"text": "日本"})
        expect(field).to_have_js_property("value", "日本")
        expect(field).to_be_focused()
    finally:
        for route in held:
            route.continue_()
        context.unroute_all(behavior="wait")


def test_an_unavailable_editor_module_leaves_fields_writing_plain_words(browser, serve):
    """When CodeMirror's module fails to load, Leaf reports it each time a field asks
    for its editor, and the field keeps the plain words it holds while waiting for one:
    the user types, Shift+Return breaks the line, and Return sends."""
    url = serve(LONG_PAGE)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    watched(page)
    page.route("**/vendor/codemirror.esm.js", lambda route: route.abort())
    page.goto(url, wait_until="load")
    wait_until_ready(page)
    failed = ("Failed to fetch dynamically imported module", "net::ERR_FAILED")
    consume_browser_errors(page, *failed)

    page.evaluate(RELEASE_FOCUS)
    field = page.locator('.lf-fp-field leaf-text[name="comment"]')
    with page.expect_event("pageerror") as raised:
        page.keyboard.press("c")
    assert failed[0] in str(raised.value)
    consume_browser_errors(page, *failed)
    expect(field).to_be_focused()
    page.keyboard.type("Written")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("plain")
    expect(field).to_have_js_property("value", "Written\nplain")
    # The thread's reply field, opening in the sent comment's place, asks for the
    # editor again.
    with page.expect_event("pageerror") as raised:
        page.keyboard.press("Enter")
    assert failed[0] in str(raised.value)
    expect(page.locator(".lf-live")).to_have_text("Message added")
    consume_browser_errors(page, *failed)


def test_an_unavailable_floating_ui_module_leaves_no_surface_open_and_unseen(
    browser, serve
):
    """A surface the failed lazy module cannot place goes away: the thread card
    closes rather than standing open and unseen, and the response composer is
    withdrawn rather than holding focus while hidden."""
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    watched(page)
    page.route("**/vendor/floating-ui.esm.js", lambda route: route.abort())
    page.goto(url, wait_until="load")
    wait_until_ready(page)
    failed = ("Failed to fetch dynamically imported module", "net::ERR_FAILED")
    consume_browser_errors(page, *failed)

    page.evaluate(RELEASE_FOCUS)
    with page.expect_event("pageerror") as raised:
        page.keyboard.press("t")
    assert failed[0] in str(raised.value)
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    consume_browser_errors(page, *failed)

    with page.expect_event("pageerror") as raised:
        page.locator("#p10").click(modifiers=["Alt"])
    assert failed[0] in str(raised.value)
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    expect(page.locator(".lf-composer")).to_be_hidden()
    consume_browser_errors(page, *failed)


def test_a_page_with_a_diff_loads_the_renderer_when_it_draws_lines(browser, serve):
    """The other side of the narrowing, on a diff bound as a manifest of collapsed files.

    That is the form a captured patch arrives in, and its module draws the file rows
    without rendering a line, so the renderer follows the lines rather than the tag: the
    module loads because the markup carries `<lf-diff>`, and Pierre loads when a file is
    opened and its lines are drawn. Both halves are asserted, because either alone would
    pass on a diff that never rendered at all.

    A fixture rather than the walkthrough, which opens on an inline hunk as well as its
    manifest and so draws lines, and needs the renderer, at load. Only a page whose one
    diff is the manifest can show the manifest's half.
    """
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    asked = _asked(context)
    url = serve(MANIFEST_DIFF_PAGE)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        patch_manifest(
            MULTI_HUNK_PATCH + "diff --git a/old.py b/new.py\nsimilarity index 100%\n"
            "rename from old.py\nrename to new.py\n"
        ),
    )
    page = open_page(browser, url, context=context)

    assert "/widgets/lf-diff.js" in asked
    assert not [p for p in asked if "pierre-diffs" in p], (
        "a collapsed manifest draws no lines, so nothing has needed the renderer yet"
    )
    diff = page.locator("lf-diff#patch")
    expect(diff).to_have_class(re.compile(r"\blf-rendered\b"))
    files = diff.locator("details > summary")
    expect(files.first).to_be_visible()
    expect(diff.locator(".lf-diff-metadata")).to_contain_text("old.py → new.py")
    assert "/vendor/pierre-parser.esm.js" in asked

    files.first.click()
    expect(diff.locator("[data-line]").first).to_be_visible()
    assert [p for p in asked if "pierre-diffs" in p] == ["/vendor/pierre-diffs.esm.js"]
    assert diff.locator(".lf-error").count() == 0


def test_a_widget_a_reply_carries_arrives_with_its_module(browser, serve):
    """A tag the document never had still upgrades in the panel.

    The frozen markup an agent's reply carries is the third boundary that can
    introduce a widget, and `buildMsgBody` instantiates it synchronously once the
    panel builds a body — so the module has to be in hand before the state that
    carries the reply is applied, not fetched on a mutation once the element is
    already connected. The board is served first with no options anywhere on it, so
    the module can only have arrived because the reply asked for it.
    """
    example = next(p for p in EXAMPLES if p.stem == "triage-board")
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    asked = _asked(context)
    page = open_page(browser, serve(example), context=context)
    assert "/widgets/lf-options.js" not in asked
    assert page.evaluate("() => !customElements.get('lf-options')")

    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-store",
            "author": "user",
            "revision": 1,
            "text": "Which store should we write up?",
        },
    )
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(d, "c-store"),
            "--text",
            "Depends what you want to keep:",
            "--markup",
            (
                '<lf-ask id="store-decision"><h3>Which store?</h3>'
                '<lf-options id="store-pick" choose>'
                '<lf-option id="store-redis"><strong>Redis</strong></lf-option>'
                '<lf-option id="store-cookie"><strong>A signed cookie</strong>'
                "</lf-option></lf-options></lf-ask>"
            ),
        ],
    )
    assert replied.exit_code == 0, replied.output

    told(page)
    assert "/widgets/lf-options.js" in asked
    assert page.evaluate("() => !!customElements.get('lf-options')")

    options = open_panel_thread(page, "c-store").locator("lf-options#store-pick")
    expect(options).to_be_visible()
    # Its module's own work, not the markup's: the pick control each option is chosen by.
    expect(options.locator("lf-option [data-lf-offer='checkbox']")).to_have_count(2)


def test_a_state_waiting_for_markdown_cannot_overwrite_a_newer_one(browser, serve):
    """Sequence order is judged again after the lazy Markdown import. A newer POST
    response can enter that await before an older held poll; when the shared import
    finishes, the older continuation must not repaint the log backwards. The test
    starts that import before either state arrives, as an editor that is shown does,
    and holds it."""
    marked = []
    page = open_page(
        primed(
            browser,
            lambda page: page.route(
                "**/vendor/markdown-it.esm.js", lambda route: marked.append(route)
            ),
        ),
        serve(LONG_PAGE),
    )
    open_threads(page)
    page.evaluate(
        "() => { window.__lfWidgetApi().then((markdown) => markdown.loadMarkdown()); }"
    )
    holding(page, marked, 1, "the Markdown module")
    assert len(marked) == 1

    older = []

    def hold_older_state(route):
        if older:
            refuse(route)
            return
        older.append(route)

    page.route("**/api/state*", hold_older_state)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Older **snapshot**",
        },
    )
    with page.expect_request("**/api/state"):
        pass
    holding(page, older, 1, "the older state read")
    assert len(older) == 1
    old_route = older[0]
    old_state = old_route.fetch().json()

    write(page_comment(page), "Newest **snapshot**")
    with sending(page, "the newer comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    old_route.fulfill(json=old_state)
    page.title()  # let the old response join the shared import before releasing it
    marked[0].continue_()
    page.unroute("**/vendor/markdown-it.esm.js")

    open_threads(page)
    rows = page.locator(f"{panel_view('threads')} .lf-fp-thread")
    expect(rows.filter(has_text="Older")).to_have_count(1)
    expect(rows.filter(has_text="Newest")).to_have_count(1)


def test_the_public_widget_api_can_load_before_boot_registers_page_keys(browser, serve):
    """Importing capabilities does not start a half-constructed browser application."""
    url = serve(SUGGESTION_PAGE)
    boot = serving_runtime().resources({}, {})["/leaf.js"].data.decode()
    context = browser.new_context()
    context.route(
        "**/leaf.js",
        lambda route: route.fulfill(
            content_type="text/javascript",
            body="await window.__lfWidgetApi();\n"
            "window.apiImportedBeforeBoot = true;\n"
            "await import('./leaf-boot.js');",
        ),
    )

    def boot_after_one_frame(route):
        # Import side effects have a real frame in which to escape before boot owns
        # presentation; this is controlled ordering rather than a network-speed race.
        context.pages[0].evaluate("() => new Promise(requestAnimationFrame)")
        route.fulfill(content_type="text/javascript", body=boot)

    context.route("**/leaf-boot.js", boot_after_one_frame)
    page = open_page(browser, url, context=context)
    assert page.evaluate("window.apiImportedBeforeBoot") is True
    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
