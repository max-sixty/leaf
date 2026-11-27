"""An entry's record across a reload and a return from another document: the user
comes back where they left the entry, as Back within the page brings them."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    OBLIGATION_PAGE,
    executable_revision,
    live_url,
    panel_comment,
)
from render_harness import (
    LONG_PAGE,
    compare_with,
    holding,
    leaf_page,
    open_latest,
    open_page,
    open_threads,
    panel_menu,
    panel_view,
    scroll_settled,
    select_words,
    stamp_page,
    take_browser_errors,
    told,
    wait_for_revision,
    write,
)

from browser.startup.test_readiness import answer_as_another_runtime
from browser.test_render_drawing import draw_over
from browser.threads import open_panel_thread
from leaf.source.render_checks import wait_until_ready
from leaf_dev.browser import PANEL_THREAD, choose_threads_in_panel, on_tab

pytestmark = pytest.mark.shifts_unsurveyed

ENGINES = ["browser", "firefox_browser"]

# Whether focus stands on nothing, or on something the window shows.
FOCUS_SEEN = """() => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  if (!at || at === document.body) return true;
  const box = at.getBoundingClientRect();
  return box.bottom > 0 && box.top < innerHeight && box.right > 0 && box.left < innerWidth;
}"""

# The caret of the field focus stands in, as [start, end].
CARET = """() => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement && at.selectionStart === undefined)
    at = at.shadowRoot.activeElement;
  return at && at.selectionStart !== undefined ? [at.selectionStart, at.selectionEnd] : null;
}"""


def reload(page):
    page.wait_for_function("navigation.transition === null")
    page.reload()
    wait_until_ready(page)


def long_card(serve, extra=""):
    """A passage thread with replies long enough to scroll its card, one reply holding a
    link to the last paragraph, and `extra` words in the fourth."""
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    for n in range(7):
        text = f"Reply {n}. " + "More of the explanation. " * 30
        if n == 3:
            text += extra or "See [the last paragraph](#p59)."
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": root,
                "revision": 1,
                "text": text,
            },
        )
    return root


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_a_thread_in_the_reader_it_showed(request, serve, engine):
    """A thread about a passage the user opened in the floating panel, from Threads, is
    there again after a reload, rather than in a card beside a passage the window
    doesn't show, though threads open beside their passages by then: the entry's record
    holds the view the user stood in, which the choice of where threads open doesn't
    say (records/thread/address.js). Focus stands only on what the window shows."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    choose_threads_in_panel(page)
    open_threads(page)
    page.locator(".lf-fp-thread").first.click()
    view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    expect(view).to_be_visible()
    choose_threads_in_panel(page, on=False)
    reload(page)
    expect(view).to_be_visible()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    assert page.evaluate(FOCUS_SEEN)


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_where_a_card_was_read_to(request, serve, engine):
    """A card read partway reopens after a reload at the reply the user had read it to,
    not at its first unread reply or its end."""
    url = serve(LONG_PAGE)
    root = long_card(serve)
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("t")
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_focused()
    transcript = card.locator(".lf-thread-transcript")
    card.get_by_role("link", name="the last paragraph").scroll_into_view_if_needed()
    scroll_settled(page)
    read_to = transcript.evaluate("box => box.scrollTop")
    reload(page)
    expect(card).to_be_visible()
    scroll_settled(page)
    assert abs(transcript.evaluate("box => box.scrollTop") - read_to) <= 2


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("where", ["reply", "rewrite", "comment"])
def test_a_reload_keeps_the_caret_in_words_being_written(request, serve, engine, where):
    """Words being written, a reply in a card, a rewrite of the user's own message or a
    new comment, come back after a reload with the caret where the user left it inside
    them, not at their end."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    if where in {"reply", "rewrite"}:
        page.keyboard.press("t")
        card = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
        )
        expect(card).to_be_focused()
        if where == "reply":
            page.keyboard.press("c")
        else:
            card.locator(f'.lf-msg[data-lf-message="{root}"] .lf-msg-text').dblclick()
            page.wait_for_function(f"() => ({CARET})() !== null")
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.press("Delete")
    else:
        select_words(page, "#p3")
        page.keyboard.press("c")
    page.wait_for_function(f"() => ({CARET})() !== null")
    page.keyboard.type("Take it from the infrastructure reserve")
    for _ in range(8):
        page.keyboard.press("ArrowLeft")
    page.wait_for_function(f"() => ({CARET})()?.[0] === 31")
    reload(page)
    page.wait_for_function(f"() => JSON.stringify(({CARET})()) === '[31,31]'")


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_the_list_the_panel_showed(request, serve, engine):
    """Threads, open in the floating panel, is open again after a reload."""
    url = serve(LONG_PAGE)
    for n in (1, 2):
        panel_comment(
            serve.page_dir,
            f"Question {n}?",
            {"section": f"p{n}", "quote": f"Paragraph {n}."},
        )
    page = open_page(request.getfixturevalue(engine), url)
    open_threads(page)
    expect(page.locator(panel_view("threads"))).to_be_visible()
    reload(page)
    expect(page.locator(panel_view("threads"))).to_be_visible()


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("where", ["On Claude", "Versions", "Threads read down"])
def test_a_reload_keeps_where_the_user_stood_in_the_panel(
    request, serve, engine, where
):
    """Whatever the floating panel shows comes back after a reload as the user left it,
    as the entry's record has it (records/history.js): the agent's On list rather than On Me, a
    list the menu opens, as Versions, and how far down a list the user had read."""
    url = serve(LONG_PAGE)
    if where == "Versions":
        stamp_page(
            serve.page_dir, LONG_PAGE.replace("Paragraph 0.", "Paragraph zero."), "two"
        )
    if where == "Threads read down":
        for n in range(1, 31):
            panel_comment(
                serve.page_dir,
                f"Question {n}?",
                {"section": f"p{n}", "quote": f"Paragraph {n}."},
            )
    page = open_page(request.getfixturevalue(engine), url)
    title = page.locator(".lf-fp-title")
    if where == "On Claude":
        on_tab(page, "On Claude").click()
        expect(title).to_have_text("On Claude")
        view = page.locator(panel_view("queue"))
    elif where == "Versions":
        view = panel_menu(page, "versions")
        expect(title).to_have_text("Versions")
    else:
        open_threads(page)
        view = page.locator(panel_view("threads"))
        expect(view.locator(".lf-fp-thread")).to_have_count(30)
        view.evaluate("view => view.scrollBy({top: 300, behavior: 'instant'})")
        scroll_settled(page)
    read_to = view.evaluate("view => view.scrollTop")
    assert where != "Threads read down" or read_to > 100

    reload(page)
    expect(title).to_have_text(where.split(" read")[0])
    scroll_settled(page)
    assert abs(view.evaluate("view => view.scrollTop") - read_to) <= 2


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("control", ["version", "Compare"])
def test_a_reload_keeps_the_user_on_the_versions_row_they_were_on(
    request, serve, engine, control
):
    """In Versions the user stands on a row as in any list, the press that shows a
    version or the Compare beside it, and a reload returns them to it rather than to
    the version Versions opens at: each row is named by the version it is (the entry's
    record, records/history.js)."""
    url = live_url(serve(LONG_PAGE))
    for mark in ["two", "three"]:
        stamp_page(
            serve.page_dir,
            LONG_PAGE.replace("Paragraph 0.", f"Paragraph {mark}."),
            mark,
        )
    page = open_page(request.getfixturevalue(engine), url)
    view = panel_menu(page, "versions")
    expect(page.locator(".lf-fp-title")).to_have_text("Versions")
    expect(view.locator(".lf-fp-version")).to_have_count(3)
    # An earlier version than the one Versions opens at, which the latest, shown,
    # offers to compare with.
    other = view.locator(
        ".lf-fp-version:not([data-lf-current]):not([data-lf-at])"
    ).first
    row = other.locator(
        ":scope > .lf-fp-item" if control == "version" else ":scope > .lf-fp-compare"
    )
    row.focus()
    expect(row).to_be_focused()
    reload(page)
    expect(page.locator(".lf-fp-title")).to_have_text("Versions")
    expect(row).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_back_returns_a_list_read_from_its_top_to_its_top(request, serve, engine):
    """Back to an entry where the user stood at the top of the panel's Threads returns
    the list to its top, though they read it down on the entry they left: the top is a
    place the list was read to like any other."""
    url = serve(LONG_PAGE)
    for n in range(1, 31):
        panel_comment(
            serve.page_dir,
            f"Question {n}?",
            {"section": f"p{n}", "quote": f"Paragraph {n}."},
        )
    page = open_page(request.getfixturevalue(engine), url)
    open_threads(page)
    view = page.locator(panel_view("threads"))
    expect(view.locator(".lf-fp-thread")).to_have_count(30)
    assert view.evaluate("view => view.scrollTop") == 0
    page.wait_for_function("navigation.transition === null")
    page.evaluate("location.hash = '#p20'")
    page.wait_for_function("navigation.transition === null")
    expect(view).to_be_visible()
    view.evaluate("view => view.scrollBy({top: 300, behavior: 'instant'})")
    scroll_settled(page)
    assert view.evaluate("view => view.scrollTop") > 100
    page.go_back()
    expect(view).to_be_visible()
    # The list returns once the panel has presented it, after the step itself ends.
    expect(view).to_have_js_property("scrollTop", 0)


@pytest.mark.parametrize("engine", ENGINES)
def test_back_from_another_document_returns_to_the_link_followed(
    request, serve, engine
):
    """A link in a card to another document, followed and come Back from, leaves the
    user on that link in the card again, as Back within the page does."""
    url = serve(LONG_PAGE)
    # The page itself, loaded afresh: another document, as any page elsewhere is.
    root = long_card(serve, "See [the elsewhere page](v1.html).")
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("t")
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_focused()
    link = card.get_by_role("link", name="the elsewhere page")
    link.scroll_into_view_if_needed()
    scroll_settled(page)
    page.wait_for_function("navigation.transition === null")
    with page.expect_navigation():
        link.click()
    page.go_back()
    wait_until_ready(page)
    expect(link).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_leaves_a_kept_draft_shut(request, serve, engine):
    """A new comment the user put away with Escape stays put away after a reload that
    finds them elsewhere: focus doesn't go into it, so the next key is a command, not a
    word added to the draft."""
    url = serve(LONG_PAGE)
    panel_comment(
        serve.page_dir, "Why here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    select_words(page, "#p3")
    page.keyboard.press("c")
    page.wait_for_function(f"() => ({CARET})() !== null")
    page.keyboard.type("Is this the overnight scan")
    page.keyboard.press("Escape")
    page.wait_for_function(f"() => ({CARET})() === null")
    page.evaluate("document.activeElement?.blur?.()")
    page.evaluate(
        "scrollTo({top: document.getElementById('p20').offsetTop, behavior: 'instant'})"
    )
    scroll_settled(page)
    reload(page)
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    assert page.evaluate(CARET) is None
    assert page.evaluate(FOCUS_SEEN)
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_focus_on_a_control_in_a_comment_box(request, serve, engine):
    """Focus on a control in a new comment's box, as its drawing's Undo, comes back to
    that control after a reload, with the box and its drawing open again."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    draw_over(page, page.locator("#p3"))
    undo = page.get_by_role("button", name="Undo last stroke")
    undo.focus()
    expect(undo).to_be_focused()
    reload(page)
    expect(undo).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_focus_on_the_add_beside_an_option_being_added(
    request, serve, engine
):
    """Focus on the press that adds an option the user is writing in, beside the box
    they wrote it in, comes back to that press after a reload, so Enter adds the option,
    as it does for a control in a comment's box: the option's box is a draft's box like
    any other (records/drafts.js, `draftFocus`)."""
    page = open_page(request.getfixturevalue(engine), serve(OBLIGATION_PAGE))
    another = page.locator("#jobs .lf-another")
    field = another.locator("leaf-text")
    write(field, "An option of mine.")
    page.keyboard.press("Tab")
    add = another.get_by_role("button")
    expect(add).to_be_focused()
    reload(page)
    expect(field).to_have_js_property("value", "An option of mine.")
    expect(add).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_tab_discarded_while_hidden_comes_back_where_it_was_left(
    request, serve, engine
):
    """A tab the browser discards while hidden, as a phone or a desktop's memory saver
    does, unloads without `beforeunload`; the record written as it was hidden brings
    the user's selection back when it loads again."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    page.evaluate("""() => {
      const text = document.getElementById('p20').firstChild;
      getSelection().setBaseAndExtent(text, 0, text, 'Paragraph 20.'.length);
    }""")
    page.evaluate("""() => {
      Object.defineProperty(document, 'visibilityState', {value: 'hidden', configurable: true});
      document.dispatchEvent(new Event('visibilitychange'));
      // The discard, which runs no unload handler.
      addEventListener('beforeunload', (event) => event.stopImmediatePropagation(), {capture: true});
    }""")
    reload(page)
    page.wait_for_function("() => getSelection().toString() === 'Paragraph 20.'")


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("control", ["Close", "Resolve", "Show on page"])
def test_a_reload_keeps_focus_on_a_control_of_a_thread_view(
    request, serve, engine, control
):
    """Focus on one of the controls on the head of a thread's view in the floating
    panel comes back to that control after a reload, not to the view as a whole."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    # The row's travel to the thread's passage has landed before the reload, which
    # would otherwise cut the glide short; in Firefox, going while it glides past the
    # reply's editor raises a scroll-linked positioning warning.
    open_panel_thread(page, root)
    button = page.locator(".lf-fp-head").get_by_role(
        "button", name=re.compile(f"^{control}")
    )
    button.focus()
    expect(button).to_be_focused()
    reload(page)
    expect(button).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_recovery_asks_for_again_returns_to_the_record(request, serve, engine):
    """A reload whose module failed on its way, so that startup's recovery asks for the
    document once more, still returns the user to where they left the entry: the words
    they had selected come back."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    page.evaluate("""() => {
      const text = document.getElementById('p20').firstChild;
      getSelection().setBaseAndExtent(text, 0, text, 'Paragraph 20.'.length);
    }""")
    documents, failed = [], []
    page.on(
        "request",
        lambda req: (
            documents.append(req.url) if req.resource_type == "document" else None
        ),
    )

    def lose(route):
        if failed:
            route.continue_()
        else:
            failed.append(route.request.url)
            route.abort("internetdisconnected")

    page.route("**/runtime/base/rendering.js", lose)
    page.wait_for_function("navigation.transition === null")
    page.reload(wait_until="commit")
    holding(page, documents, 2, "the document recovery asks for")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    assert len(failed) == 1, failed
    page.wait_for_function("() => getSelection().toString() === 'Paragraph 20.'")
    # The module the test failed on its way, as the browser reports it.
    take_browser_errors(page)


# A page whose prose a revision can add room above, with a field to type in partway
# down and words to select, served live so its revisions reach it.
FILLER = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(30))
ARRIVAL_PAGE = leaf_page(
    "Arrivals",
    f"""<h1>Arrivals</h1><section id="above">{FILLER}</section>
<p id="lead">The note below holds what the user types.</p>
<label>Note <input id="note"></label>
<section id="below">{FILLER}</section>""",
)


def hold_the_next_documents_reading(page):
    """Hold every reading of the page's state from the moment the page's address next
    changes, as a revision's reload marks it, so the document that reload brings waits
    for its first reading; returns the held requests."""
    held, gate = [], {"hold": False}
    page.on("framenavigated", lambda frame: gate.update(hold=True))
    page.route(
        "**/api/state*",
        lambda route: held.append(route) if gate["hold"] else route.continue_(),
    )
    return held


def release(page, held):
    page.unroute("**/api/state*")
    for route in held:
        route.continue_()
    held.clear()


def revise(page, serve, source, mark):
    """Stamp `source` as a revision whose inline module is new, so the page reloads
    into it, and press Open latest where the page holds the revision back."""
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(serve.page_dir, executable_revision(source, mark), f"Revise: {mark}")
    told(page)
    if page.evaluate("performance.timeOrigin") == birth:
        open_latest(page)


@pytest.mark.parametrize("engine", ENGINES)
def test_a_revision_keeps_a_field_being_typed_in_where_it_stood(request, serve, engine):
    """A field the user types in stands where it stood in the window after a revision
    that reloads the page and adds room above it, with its words and selection: the
    field taking focus back early, so typing goes on, doesn't stop the return to the
    user's place."""
    page = open_page(request.getfixturevalue(engine), live_url(serve(ARRIVAL_PAGE)))
    note = page.locator("#note")
    note.evaluate("el => el.scrollIntoView({block: 'center', behavior: 'instant'})")
    scroll_settled(page)
    note.fill("kept words")
    note.evaluate("el => el.setSelectionRange(2, 6)")
    top = note.evaluate("el => el.getBoundingClientRect().top")
    revise(
        page,
        serve,
        ARRIVAL_PAGE.replace(
            '<section id="above">',
            '<section id="above"><div style="height: 400px"></div>',
        ),
        "room above",
    )
    wait_for_revision(page, 2)
    scroll_settled(page)
    expect(note).to_be_focused()
    assert note.evaluate("el => [el.value, el.selectionStart, el.selectionEnd]") == [
        "kept words",
        2,
        6,
    ]
    assert abs(note.evaluate("el => el.getBoundingClientRect().top") - top) <= 2


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("when", ["before Leaf starts", "as the arrival waits"])
def test_back_during_a_revisions_arrival_ends_it(request, serve, engine, when):
    """Back while a revision's reload is still arriving ends that arrival: the page
    stays at the entry Back reached and returns the user to that entry's record, rather
    than going back to where the revision's entry was once the arrival's first reading
    of the page comes. So it does whether Back lands before Leaf's modules have started,
    while only the platform hears it, or once the arrival has begun and waits for the
    page's state; and Forward then returns to the entry the reload was for."""
    url = live_url(serve(LONG_PAGE))
    first = panel_comment(
        serve.page_dir, "Why here?", {"section": "p10", "quote": "Paragraph 10."}
    )
    second = panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    card = page.locator(".lf-margin-preview .lf-page-thread")
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", first)
    scroll_settled(page)
    at = page.evaluate("scrollY")
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", second)
    scroll_settled(page)
    there = page.evaluate("scrollY")
    assert abs(there - at) > 200
    page.wait_for_function("navigation.transition === null")
    # The arriving document's entry module, held so Back lands before Leaf starts.
    module = []
    if when == "before Leaf starts":
        page.route("**/leaf.js", lambda route: module.append(route))
    held = hold_the_next_documents_reading(page)
    born = page.evaluate("performance.timeOrigin")
    try:
        stamp_page(serve.page_dir, executable_revision(LONG_PAGE, "back"), "Revise")
        if when == "before Leaf starts":
            holding(page, module, 1, "the arriving document's entry module")
            # Firefox can ask for the arriving document's module before that document
            # commits, so Back waits until the arriving document stands, parsed.
            page.wait_for_function(
                "(born) => performance.timeOrigin !== born"
                " && document.readyState !== 'loading'",
                arg=born,
            )
        else:
            holding(page, held, 1, "the arriving document's first reading")
            wait_until_ready(page, through="upgraded")
        page.evaluate("history.back()")
        page.wait_for_function(
            f"new URL(location.href).searchParams.get('thread') === '{first}'"
        )
        page.unroute("**/leaf.js")
        for route in module:
            route.continue_()
        module.clear()
        release(page, held)
        wait_until_ready(page)
        expect(card).to_have_attribute("data-lf-thread", first)
        scroll_settled(page)
        assert abs(page.evaluate("scrollY") - at) <= 2
        assert new_url_thread(page) == first
        page.wait_for_function("navigation.transition === null")
        page.go_forward()
        expect(card).to_have_attribute("data-lf-thread", second)
        scroll_settled(page)
        assert abs(page.evaluate("scrollY") - there) <= 2
    finally:
        page.unroute("**/leaf.js")
        for route in module:
            route.continue_()
        release(page, held)


def two_thread_entries(browser, serve):
    """The page, opened at its second thread's entry with the reply being written there
    after an entry at its first thread; returns it, the two threads' ids and the
    margin's card."""
    url = live_url(serve(LONG_PAGE))
    first = panel_comment(
        serve.page_dir, "Why here?", {"section": "p10", "quote": "Paragraph 10."}
    )
    second = panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(browser, url)
    card = page.locator(".lf-margin-preview .lf-page-thread")
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", first)
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", second)
    write(card.locator(".lf-thread-reply leaf-text"), "Hold")
    page.wait_for_function("navigation.transition === null")
    return page, first, second, card


def leaf_reloads_with_its_module_held(page, serve, module):
    """A reload Leaf asks for, as a server restarted under another Leaf causes, whose
    document's entry module waits in `module`."""
    page.route("**/leaf.js", lambda route: module.append(route))
    answer_as_another_runtime(page)
    with page.expect_navigation(wait_until="commit"):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
        )
    holding(page, module, 1, "the arriving document's entry module")
    page.wait_for_function("document.readyState !== 'loading'")


def start_leaf(page, module):
    page.unroute("**/leaf.js")
    for route in module:
        try:
            route.continue_()
        except Exception:
            pass
    module.clear()
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")


def test_a_key_before_back_taken_before_leaf_starts_leaves_the_entry_its_record(
    browser, serve
):
    """A key the user presses at the entry a reload Leaf asks for brings back, then Back
    to another entry before Leaf starts: the key acted at the entry the user left, so the
    entry Back reached gets its record back, the thread open there."""
    page, first, _, card = two_thread_entries(browser, serve)
    module = []
    try:
        leaf_reloads_with_its_module_held(page, serve, module)
        # A key the hold doesn't keep acts at once, here scrolling the page.
        page.keyboard.press("ArrowDown")
        page.wait_for_function("scrollY > 0")
        page.evaluate("history.back()")
        page.wait_for_function(
            f"new URL(location.href).searchParams.get('thread') === '{first}'"
        )
    finally:
        start_leaf(page, module)
    expect(card).to_have_attribute("data-lf-thread", first)
    expect(card).to_be_focused()


def test_keys_held_at_an_entry_go_when_back_leaves_it_before_leaf_starts(
    browser, serve
):
    """A key the user presses while a page loads with nothing handed to it waits for
    Leaf to start, at the entry they pressed it at. The user's Back to another entry
    before Leaf starts lets it go, so it neither runs there nor keeps that entry from
    its record."""
    page, first, _, card = two_thread_entries(browser, serve)
    module = []
    page.route("**/leaf.js", lambda route: module.append(route))
    try:
        with page.expect_navigation(wait_until="commit"):
            page.evaluate("setTimeout(() => location.reload())")
        holding(page, module, 1, "the reloaded document's entry module")
        page.wait_for_function("document.readyState !== 'loading'")
        page.keyboard.press("T")
        expect(page.locator(".lf-held-key")).to_have_text("T")
        page.go_back(wait_until="commit")
        page.wait_for_function(
            f"new URL(location.href).searchParams.get('thread') === '{first}'"
        )
        expect(page.locator(".lf-held-key")).to_have_count(0)
    finally:
        page.unroute("**/leaf.js")
        for route in module:
            route.continue_()
    wait_until_ready(page)
    expect(card).to_have_attribute("data-lf-thread", first)
    expect(card).to_be_focused()


def test_a_key_pressed_before_forward_to_the_reload_s_entry_goes_with_the_step(
    browser, serve
):
    """A reload Leaf asks for at an entry, then Back to an earlier one and a reload of
    it before Leaf starts, and a key pressed there before Forward to the first entry:
    the key goes with the entry it was pressed at, so the first entry gets the place the
    handoff kept for it, the reply being written."""
    page, first, second, card = two_thread_entries(browser, serve)
    reply = card.locator(".lf-thread-reply leaf-text")
    module = []
    try:
        leaf_reloads_with_its_module_held(page, serve, module)
        page.go_back(wait_until="commit")
        page.wait_for_function(
            f"new URL(location.href).searchParams.get('thread') === '{first}'"
        )
        page.reload(wait_until="commit")
        holding(page, module, 2, "the reloaded document's entry module")
        page.wait_for_function("document.readyState !== 'loading'")
        page.keyboard.press("t")
        expect(page.locator(".lf-held-key")).to_have_text("t")
        page.go_forward(wait_until="commit")
        page.wait_for_function(
            f"new URL(location.href).searchParams.get('thread') === '{second}'"
        )
        expect(page.locator(".lf-held-key")).to_have_count(0)
    finally:
        start_leaf(page, module)
    expect(card).to_have_attribute("data-lf-thread", second)
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Hold")


def test_a_step_after_the_user_left_a_pending_return_keeps_their_newer_place(
    browser, serve
):
    """A reload brings an entry back while the page's state is still on its way, and
    the user moves on there before it lands, then steps Back and Forward: Forward
    returns them where they had moved to, not where the reload would have put them."""
    page = open_page(browser, live_url(serve(LONG_PAGE)))
    page.evaluate("document.getElementById('p20').scrollIntoView({block: 'start'})")
    page.wait_for_function("navigation.transition === null")
    page.evaluate("location.hash = '#p20'")
    page.wait_for_url(re.compile("#p20$"))
    page.wait_for_function("navigation.transition === null")
    held = hold_the_next_documents_reading(page)
    try:
        with page.expect_navigation(wait_until="commit"):
            page.evaluate("setTimeout(() => location.reload())")
        holding(page, held, 1, "the reloaded document's first reading")
        # The panel mounts in the task that installs the arrival (leaf.js).
        page.wait_for_function(
            "document.querySelector('.lf-floating-panel:not([data-lf-served])') !== null"
        )
        page.keyboard.press("End")
        page.wait_for_function(
            "scrollY + innerHeight >= document.body.scrollHeight - 4"
        )
        page.go_back(wait_until="commit")
        page.wait_for_function("location.hash === ''")
        release(page, held)
        wait_until_ready(page)
        page.go_forward(wait_until="commit")
        page.wait_for_function("location.hash === '#p20'")
        wait_until_ready(page)
        scroll_settled(page)
        assert page.evaluate(
            "scrollY + innerHeight >= document.body.scrollHeight - 4"
        ), page.evaluate("[scrollY, innerHeight, document.body.scrollHeight]")
    finally:
        release(page, held)


@pytest.mark.parametrize("engine", ENGINES)
def test_back_before_leaf_starts_leaves_the_reload_s_place_to_its_entry(
    request, serve, engine
):
    """A reload Leaf asks for, as a server restarted under another Leaf causes, hands
    its document the place the user left: the reply they were writing. Back taken
    before Leaf starts lands on another entry, whose record says where the user is
    there, so the handoff's place stays with the entry it was written on, where Forward
    returns to the reply. The words typed into the page's own form are the document's,
    as they stay through a Back within one document, so they come back wherever the
    document arrives."""
    source = LONG_PAGE.replace(
        '<h1 id="t">Long</h1>',
        '<h1 id="t">Long</h1><p><input id="who" autocomplete="off"></p>',
    )
    url = live_url(serve(source))
    first = panel_comment(
        serve.page_dir, "Why here?", {"section": "p10", "quote": "Paragraph 10."}
    )
    second = panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    card = page.locator(".lf-margin-preview .lf-page-thread")
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", first)
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", second)
    reply = card.locator(".lf-thread-reply leaf-text")
    write(reply, "Hold")
    page.wait_for_function("navigation.transition === null")
    module = []
    page.route("**/leaf.js", lambda route: module.append(route))
    answer_as_another_runtime(page)
    try:
        with page.expect_navigation(wait_until="commit"):
            append_carried_log_record(
                serve.page_dir,
                {"kind": "comment", "author": "user", "revision": 1, "text": "Wake."},
            )
        holding(page, module, 1, "the arriving document's entry module")
        page.evaluate("history.back()")
        page.wait_for_function(
            f"new URL(location.href).searchParams.get('thread') === '{first}'"
        )
    finally:
        page.unroute("**/leaf.js")
        for route in module:
            route.continue_()
    wait_until_ready(page)
    page.unroute("**/api/**")
    page.unroute("**/registry.json")
    expect(card).to_have_attribute("data-lf-thread", first)
    expect(card).to_be_focused()
    expect(page.locator("#who")).to_have_value("Ada")
    page.wait_for_function("navigation.transition === null")
    page.go_forward()
    expect(card).to_have_attribute("data-lf-thread", second)
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Hold")


def new_url_thread(page):
    return page.evaluate("new URL(location.href).searchParams.get('thread')")


@pytest.mark.parametrize("engine", ENGINES)
def test_hiding_the_page_while_it_arrives_keeps_what_the_arrival_owes(
    request, serve, engine
):
    """A page hidden while its reload is still arriving writes the record it is
    returning the user to, not a reading of the page it hasn't put back yet, so a
    discard then loses nothing: the words the user had selected come back."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    page.evaluate("""() => {
      const text = document.getElementById('p20').firstChild;
      getSelection().setBaseAndExtent(text, 0, text, 'Paragraph 20.'.length);
    }""")
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        page.wait_for_function("navigation.transition === null")
        page.reload(wait_until="commit")
        holding(page, held, 1, "the reload's first reading")
        # The page's widgets and words have settled, so its words can be anchored, as
        # they can before any state reading answers.
        wait_until_ready(page, through="upgraded")
        page.evaluate("""() => {
          Object.defineProperty(document, 'visibilityState', {value: 'hidden', configurable: true});
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
        assert page.evaluate(
            "navigation.currentEntry.getState()?.selection?.anchor?.quote"
        )
    finally:
        page.unroute("**/api/state*")
        for route in held:
            route.continue_()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_revision_during_a_revisions_arrival_keeps_what_it_owes(
    request, serve, engine
):
    """A second revision that reloads the page while the first one's reload is still
    arriving carries what the first owes the user, the comparison they had open and
    the words they had selected, rather than a reading of the page half put back."""
    reworded = ARRIVAL_PAGE.replace(
        "holds what the user types", "keeps what the user types"
    )
    url = live_url(serve(ARRIVAL_PAGE))
    page = open_page(request.getfixturevalue(engine), url)
    stamp_page(serve.page_dir, reworded, "Reword the lead")
    wait_for_revision(page, 2)
    compare_with(page, 1)
    marks = page.locator(".lf-ins-block, .lf-ins")
    expect(marks.first).to_be_visible()
    page.keyboard.press("Escape")
    page.evaluate("""() => {
      const text = document.getElementById('p20') ?? document.querySelector('#below p');
      const words = text.firstChild;
      getSelection().setBaseAndExtent(words, 0, words, words.data.length);
    }""")
    selected = page.evaluate("getSelection().toString()")
    assert selected
    held = hold_the_next_documents_reading(page)
    try:
        revise(page, serve, reworded, "third")
        holding(page, held, 1, "the third revision's first reading")
        stamp_page(serve.page_dir, executable_revision(reworded, "fourth"), "Fourth")
        release(page, held)
        wait_for_revision(page, 4)
        expect(marks.first).to_be_visible()
        page.wait_for_function("t => getSelection().toString() === t", arg=selected)
    finally:
        release(page, held)


@pytest.mark.parametrize("then", ["the arrival goes on", "another revision comes"])
def test_back_during_a_revisions_arrival_keeps_its_comparison(browser, serve, then):
    """The comparison a revision's reload carries is the document's: Back to an earlier
    entry of the page while that reload still arrives doesn't take it away, whether the
    arrival then goes on or another revision reloads the page first."""
    reworded = ARRIVAL_PAGE.replace(
        "holds what the user types", "keeps what the user types"
    )
    page = open_page(browser, live_url(serve(ARRIVAL_PAGE)))
    stamp_page(serve.page_dir, reworded, "Reword the lead")
    wait_for_revision(page, 2)
    compare_with(page, 1)
    marks = page.locator(".lf-ins-block, .lf-ins")
    expect(marks.first).to_be_visible()
    page.keyboard.press("Escape")
    page.wait_for_function("navigation.transition === null")
    page.evaluate("location.hash = '#lead'")
    # The hold opens at the next navigation, so this step's own lands first.
    page.wait_for_url(re.compile("#lead$"))
    page.wait_for_function("navigation.transition === null")
    held = hold_the_next_documents_reading(page)
    try:
        stamp_page(serve.page_dir, executable_revision(reworded, "third"), "Third")
        holding(page, held, 1, "the third revision's first reading")
        # The panel mounts in the task that installs the arrival (leaf.js).
        page.wait_for_function(
            "document.querySelector('.lf-floating-panel:not([data-lf-served])') !== null"
        )
        page.evaluate("history.back()")
        page.wait_for_function("location.hash === ''")
        if then == "another revision comes":
            stamp_page(
                serve.page_dir, executable_revision(reworded, "fourth"), "Fourth"
            )
            release(page, held)
            wait_for_revision(page, 4)
        else:
            release(page, held)
            wait_until_ready(page)
        expect(marks.first).to_be_visible()
    finally:
        release(page, held)


@pytest.mark.parametrize("engine", ENGINES)
def test_two_backs_while_the_page_starts_leave_each_entry_its_record(
    request, serve, engine
):
    """Back twice while a reload's first reading of the page is held: the entry the
    first Back reached keeps the record it had, rather than a reading of the page that
    hadn't been put back yet."""
    url = serve(LONG_PAGE)
    ids = [
        panel_comment(
            serve.page_dir,
            f"Question {n}?",
            {"section": f"p{n}", "quote": f"Paragraph {n}."},
        )
        for n in (10, 30, 50)
    ]
    page = open_page(request.getfixturevalue(engine), url)
    card = page.locator(".lf-margin-preview .lf-page-thread")
    for root in ids:
        page.keyboard.press("t")
        expect(card).to_have_attribute("data-lf-thread", root)
    page.wait_for_function("navigation.transition === null")
    states = (
        "navigation.entries().map((entry) => JSON.stringify(entry.getState() ?? null))"
    )
    before = page.evaluate(states)
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        page.reload(wait_until="commit")
        holding(page, held, 1, "the reload's first reading")
        for root in (ids[1], ids[0]):
            page.evaluate("history.back()")
            page.wait_for_function(
                f"new URL(location.href).searchParams.get('thread') === '{root}'"
            )
        release(page, held)
        wait_until_ready(page)
        after = page.evaluate(states)
        assert before[-2] != "null"
        assert after[-2] == before[-2]
    finally:
        release(page, held)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("how", ["push", "replace"])
def test_a_visit_whose_address_moves_while_it_starts_opens_no_stale_thread(
    request, serve, engine, how
):
    """A visit to a thread's address whose page moves to another address before it
    presents doesn't then open the first thread, or name it in the address again."""
    url = serve(LONG_PAGE)
    first = panel_comment(
        serve.page_dir, "Why here?", {"section": "p10", "quote": "Paragraph 10."}
    )
    second = panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = request.getfixturevalue(engine).new_page()
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        joined = "&" if "?" in url else "?"
        page.goto(f"{url}{joined}thread={first}", wait_until="commit")
        holding(page, held, 1, "the visit's first reading")
        page.evaluate(f"history.{how}State(null, '', '?thread={second}')")
        release(page, held)
        wait_until_ready(page)
        scroll_settled(page)
        assert new_url_thread(page) == second
        expect(
            page.locator(f'.lf-page-thread[data-lf-thread="{first}"]')
        ).to_have_count(0)
        expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{first}"]')).to_have_count(
            0
        )
    finally:
        release(page, held)


# What the restoration under way allows the routes it starts, a thread view's opening
# without focus among them (records/thread/destination.js, `openPageThread`): whether its intent
# is still available (records/history.js, `pendingRestoration`).
HISTORY = """async () => {
  const entry = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
  window.__lfHistory = await import(new URL('runtime/records/history.js', new URL(entry, location.href)).href);
}"""
RESTORATION_AVAILABLE = (
    "() => window.__lfHistory.pendingRestoration()?.intent.available() ?? null"
)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("move", ["key", "wheel"])
def test_a_restoration_ends_at_the_users_own_input(request, serve, engine, move):
    """A reload's return to its entry, and every route it starts, as the opening of the
    thread view the entry names, ends once the user presses a key or scrolls while it
    still waits: none of it moves a user who has moved."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    choose_threads_in_panel(page)
    open_threads(page)
    page.locator(".lf-fp-thread").first.click()
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')).to_be_visible()
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        page.wait_for_function("navigation.transition === null")
        page.reload(wait_until="commit")
        holding(page, held, 1, "the reload's first reading")
        wait_until_ready(page, through="upgraded")
        page.evaluate(HISTORY)
        assert page.evaluate(RESTORATION_AVAILABLE) is True
        if move == "key":
            page.keyboard.press("ArrowDown")
        else:
            page.mouse.move(400, 300)
            page.mouse.wheel(0, 200)
        page.wait_for_function(f"() => ({RESTORATION_AVAILABLE})() === false")
    finally:
        release(page, held)
