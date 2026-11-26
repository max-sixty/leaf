"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.controls.test_previews import (
    DRAWN_PAGE,
    FINGER,
    LINKS_PAGE,
    PREVIEW,
    WIDGET_THREADS,
    WIDGET_WORDS,
    _comment_on,
    _reads,
)
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import (
    clocked,
    dwelt,
    leaf_page,
    long_press,
    open_page,
    put_preview_away,
    tab_onto,
    told,
)

from leaf.source.render_checks import rendered


def test_a_focus_preview_adds_to_a_link_s_own_description(browser, serve):
    """A link whose author describes it keeps that description. A focus preview on it
    adds its words to the description while it stands, rather than writing over the
    author's, and the link says only its own once the preview goes."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "described link",
                '<p>Read <a id="to-end" href="#end" aria-describedby="note">the end'
                '</a>.</p><span id="note" hidden>the decision</span>'
                '<div style="height: 1600px"></div><h2 id="end">End</h2><p>Done.</p>',
            )
        ),
    )
    link = page.locator("#to-end")
    expect(link).to_have_accessible_description("the decision")
    tab_onto(link)
    preview = page.locator(PREVIEW)
    expect(preview).to_be_visible()
    rendered(page)
    # Element references, which Playwright's accessible description doesn't follow.
    described = link.evaluate(
        "link => (link.ariaDescribedByElements ?? []).map((el) => el.textContent)"
    )
    assert described == ["the decision", preview.text_content()]
    put_preview_away(page)
    rendered(page)
    expect(link).to_have_accessible_description("the decision")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_link_into_the_page_previews_where_it_points(engine, request, serve):
    """A link into the page previews the place it names: its heading and first lines
    as the page reads them, a question's answer from the reading the page holds, the
    pick of a question authored settled, and the conversations about it or anything in
    it, with whose turn one is: for a heading, about the part of the page it heads. It holds only words, so no id or control of the place is
    repeated. A resting pointer and the keyboard's focus read it, and a press still
    follows the link. A finger held on the link reads it at the platform's long press,
    and letting go presses nothing: the card stands until a tap follows the link. By
    touch in Chromium, and in Firefox, which takes no held touch from a test, by the
    pointer events a finger sends. A link to another site previews nothing."""
    url = serve(LINKS_PAGE)
    question = panel_comment(
        serve.page_dir,
        "Should this wait for the vendor's release?",
        {"section": "stall"},
        author="agent",
        obligation=True,
    )
    panel_comment(
        serve.page_dir,
        "Does backgrounding always clear it?",
        {"section": "stall-detail"},
    )
    panel_comment(
        serve.page_dir, "Does it cover queued edits?", {"section": "support-playbook"}
    )
    panel_comment(
        serve.page_dir, "Is this the right title?", {"section": "second-sibling"}
    )
    browser = request.getfixturevalue(engine)
    page = open_page(browser, url)
    preview = page.locator(PREVIEW)
    name = preview.locator(".lf-preview-name")

    page.locator("#to-stall").hover()
    expect(name).to_have_text("iOS reconnect stall")
    expect(preview).to_have_attribute("data-lf-face", "excerpt")
    expect(preview.locator(".lf-place-text")).to_have_text(
        "One reconnect in about 40 stalls until the app is backgrounded."
    )
    expect(preview).not_to_contain_text("offline editing")
    expect(preview.locator(".lf-place-foot")).to_have_text("2 threadsYour turn")
    assert (
        preview.locator("[id], a, button, input, [tabindex], lf-options").count() == 0
    )
    # Answering the question turns its thread to the agent: the standing preview says
    # so with the thread reading that says it.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": question,
            "revision": 1,
            "text": "Hold it until then.",
        },
    )
    told(page)
    expect(preview.locator(".lf-place-foot")).to_have_text("2 threads")

    page.locator("#to-decision").hover()
    expect(name).to_have_text("Patch decision")
    expect(preview.locator(".lf-place-state")).to_have_text(
        "Answered: Ship with the resend."
    )
    page.locator("#to-support").hover()
    expect(name).to_have_text("Support")
    expect(preview.locator(".lf-place-text").first).to_have_text(
        "The playbook covers the spinner."
    )
    expect(preview.locator(".lf-place-foot")).to_have_text("1 thread")
    # A conversation about a heading is its own part's, not the part before it.
    page.locator("#to-second").hover()
    expect(name).to_have_text("Second section")
    expect(preview.locator(".lf-place-foot")).to_have_text("1 thread")
    page.locator("#to-first").hover()
    expect(name).to_have_text("First section")
    expect(preview.locator(".lf-place-foot")).to_have_count(0)

    page.locator("#to-meeting").hover()
    expect(name).to_have_text("Where should the group meet?")
    expect(preview.locator(".lf-place-item[data-lf-chosen]")).to_have_text(
        "At reception"
    )
    expect(preview.locator(".lf-place-item:not([data-lf-chosen])")).to_have_text(
        "At the door"
    )
    # Each option stands on a line of its own.
    chosen, other = (
        preview.locator(f".lf-place-item{which}").bounding_box()
        for which in ("[data-lf-chosen]", ":not([data-lf-chosen])")
    )
    assert chosen and other, (chosen, other)
    assert abs(other["y"] - chosen["y"]) >= chosen["height"] - 0.5, (chosen, other)
    page.locator("#to-site").hover()
    expect(preview).to_be_hidden()

    # The keyboard's focus reads it at once, and Enter follows the link.
    page.locator("#to-site").focus()
    page.keyboard.press("Shift+Tab")
    expect(page.locator("#to-stall")).to_be_focused()
    expect(name).to_have_text("iOS reconnect stall")
    page.keyboard.press("Enter")
    expect(preview).to_be_hidden()
    page.wait_for_function("location.hash === '#stall'")

    # A held finger reads the preview, letting go presses nothing, and a tap follows.
    chromium = engine == "browser"
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=chromium
    )
    phone = open_page(browser, url, context=context)
    box = phone.locator("#to-decision").bounding_box()
    point = {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2}
    cdp = context.new_cdp_session(phone) if chromium else None

    def touch(start):
        if cdp:
            cdp.send(
                "Input.dispatchTouchEvent",
                {
                    "type": "touchStart" if start else "touchEnd",
                    "touchPoints": [point] if start else [],
                },
            )
        else:
            kind = "pointerdown" if start else "pointerup"
            phone.evaluate(FINGER, [kind, point["x"], point["y"]])

    touch(True)
    assert long_press(phone, point) is False, "the platform's menu opened"
    held = phone.locator(PREVIEW)
    expect(held.locator(".lf-preview-name")).to_have_text("Patch decision")
    touch(False)
    rendered(phone)
    assert phone.evaluate("location.hash") == "", "the held link was followed"
    expect(held).to_be_visible()
    if cdp:
        touch(True)
        touch(False)
    else:
        phone.locator("#to-decision").click()
    phone.wait_for_function("location.hash === '#decision'")
    expect(held).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_link_s_preview_shows_only_what_the_page_draws(engine, request, serve):
    """A place's preview says what the page draws of it now, word by word as the
    browser computes it, in its name, its parts and its code alike: a closed disclosure
    its summary, words `display: none` or `hidden` and a script's text nothing, a title
    without its hidden word, a skipped subtree nothing, a word drawn inside a hidden
    one, a block with no box what it holds draws, a section whose title is hidden its
    body and not the title, code its lines without a hidden word or Leaf's control, a
    break before hidden words still a break, words a block's `content-visibility` skips
    nothing, a folded panel, which draws none of what it holds, all of it, and words a
    `content-visibility: auto` box skips out of view as they will draw: without what
    their own styles hide. Code cut short ends in an ellipsis, as cut prose does, and a
    hidden break joins the line it would have split."""
    page = open_page(request.getfixturevalue(engine), serve(DRAWN_PAGE))
    # Words Leaf writes into a block, as the paint pass writes a comment's count.
    page.evaluate(
        """() => {
          const words = document.createElement('span');
          words.className = 'lf-ui';
          words.textContent = 'COPY CONTROL';
          document.querySelector('#code span[style]').after(words);
        }"""
    )
    preview = page.locator(PREVIEW)
    parts = preview.locator(".lf-preview-detail")
    for link, name, said in (
        ("#to-closed", "Method", None),
        ("#to-held", None, "Intro More"),
        ("#to-spans", None, "Before After"),
        ("#to-titled", "Public", "Body words."),
        ("#to-skipped", None, "Shown words."),
        ("#to-shown", None, "Plain Shown words."),
        ("#to-contents", None, "Boxed words."),
        ("#to-untitled", None, "Visible body."),
        ("#to-code", None, "one two three four…"),
        ("#to-broken", None, "first second"),
        ("#to-skipping", None, "Shown words."),
        ("#to-folded", "Folded title", "Folded body."),
        ("#to-far", None, "Far words."),
        ("#to-joined", None, "const value = 1;"),
    ):
        page.mouse.move(0, 0)
        expect(preview).to_be_hidden()
        page.locator(link).hover()
        expect(preview).to_be_visible()
        if name:
            expect(preview.locator(".lf-preview-word")).to_have_text(name)
        if said:
            assert " ".join(" ".join(parts.all_inner_texts()).split()) == said, link
        else:
            expect(parts).to_have_count(0)
        assert not {"SECRET", "HIDDEN", "CONTROL"} & set(preview.inner_text().split())


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_thread_s_words_where_something_else_takes_the_pointer_preview_that(
    engine, request, serve
):
    """A thread's words preview the thread only where nothing else there takes the
    pointer (dom/widget-elements.js, `aimableAt`). Words inside a link, or all of a link's,
    preview the link; in a titled button, only the title the browser shows; a gloss's
    words, its explanation; and words in a card that says what it holds, the card.
    Words in plain prose preview their thread."""
    url = serve(
        leaf_page(
            "Takers",
            '<p id="inside">Read <a id="holder" href="#destination">the plan for the '
            "small cohort today</a> first.</p>"
            '<p id="equal">Then <a id="whole" href="#destination">the whole link</a>'
            " again.</p>"
            '<p id="titled-block"><button id="titled" type="button" '
            'title="Inspect the rollout">Inspect the small group</button></p>'
            '<p id="glossed">Roll out behind <lf-gloss id="gloss">a gate<span '
            "popover>Check every gate before expanding.</span></lf-gloss> today.</p>"
            # Room under the gloss for its explanation's preview, clear of the card.
            + "<p>Room for the explanation.</p>"
            * 2
            + '<div id="info" tabindex="0"><p id="info-words">Informational marked '
            "words with facts.</p></div>"
            '<p id="prose">Plain prose with marked words in it.</p>'
            + "<p>More words.</p>"
            * 6
            + '<section id="destination"><h2>Destination details</h2>'
            "<p>The second stage starts once the cohort remains healthy.</p></section>",
        )
    )
    _comment_on(
        serve.page_dir,
        [
            {"section": "inside", "quote": "small cohort"},
            {"section": "equal", "quote": "the whole link"},
            {"section": "titled-block", "quote": "small group"},
            {"section": "glossed", "quote": "a gate"},
            {"section": "info-words", "quote": "marked words"},
            {"section": "prose", "quote": "marked words"},
        ],
    )
    page = open_page(clocked(request.getfixturevalue(engine)), url)
    page.locator("#info").evaluate(
        "el => { el.lfPreview = () => ({name: 'Facts about the card'}); }"
    )
    rendered(page)
    readings = {
        "inside": _reads(page, "#holder", "cohort"),
        "equal": _reads(page, "#whole", "whole"),
        "titled": _reads(page, "#titled", "small"),
        "gloss": _reads(page, "#gloss", "gate"),
    }
    explained = page.locator(PREVIEW).locator(".lf-preview-detail").all_inner_texts()
    readings["card"] = _reads(page, "#info-words", "marked")
    readings["prose"] = _reads(page, "#prose", "marked")
    assert readings == {
        "inside": "Destination details",
        "equal": "Destination details",
        "titled": None,
        "gloss": "a gate",
        "card": "Facts about the card",
        "prose": "On prose",
    }
    assert explained == ["Check every gate before expanding."]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_thread_s_words_in_a_widget_preview_it_unless_the_widget_draws_them(
    engine, request, serve
):
    """A thread's words in what a widget holds of the author's markup preview the
    thread where no control there takes the pointer: an option's chip beside the
    option's mark, a suggestion's old words, a playground's preview. A control in that
    markup takes it, as a link in an option previews the link. Words a widget draws
    itself, as code's, preview nothing, and the thread's margin entry previews it."""
    url = serve(leaf_page("Widget words", WIDGET_WORDS))
    _comment_on(serve.page_dir, WIDGET_THREADS.values())
    page = open_page(clocked(request.getfixturevalue(engine)), url)
    word = page.locator(PREVIEW).locator(".lf-preview-word")
    rendered(page)
    readings = {
        "code": _reads(page, "#code", "marked_code"),
        "chip": _reads(page, "#o1", "cohort"),
        "link": _reads(page, "#o2-link", "trim"),
        "old": _reads(page, "#old", "feeder"),
        "preview": _reads(page, "#pg-words", "banner"),
    }
    assert readings == {
        "code": None,
        "chip": "On o1",
        "link": "Destination details",
        "old": "On old",
        "preview": "On pg-words",
    }
    # Code's entry stands for the line its words are on, which has no id.
    page.mouse.move(2, 2)
    entry = page.locator('[data-lf-margin-for^="id:code/"] > .lf-margin-marker')
    entry.scroll_into_view_if_needed()
    entry.hover()
    expect(word).to_have_text("On code")


def test_a_walk_s_landing_previews_nothing_and_tab_reads_it(browser, serve):
    """A preview answers aiming, not arriving. `m` walks to the question waiting on the
    user, opening its card with focus in it, and walks there again once the card
    stands: neither landing previews, since the place a command lands on is what the
    user asked it for, and a preview would cover it. Tab, the keyboard's pointing,
    reads what it reaches. Every element focus reaches previews here, so a preview
    either landing showed would show. The stand-in is set on the window's capture, which
    runs before the document's, where the runtime reads the element focus reached."""
    url = serve(PANEL_PAGE)
    panel_comment(
        serve.page_dir,
        "Which day suits the launch?",
        {"section": "lede"},
        author="agent",
        obligation=True,
    )
    page = open_page(browser, url)
    page.evaluate(
        """() => window.addEventListener('focusin', (event) => {
          const el = event.composedPath()[0];
          if (el instanceof Element && !el.lfPreview)
            el.lfPreview = () => ({name: 'Placed here'});
        }, true)"""
    )
    tip = page.locator(PREVIEW)
    page.locator("body").focus()
    page.keyboard.press("m")
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    page.evaluate("() => { window.landed = document.activeElement; }")
    rendered(page)
    expect(tip).to_be_hidden()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("Placed here")
    page.keyboard.press("m")
    page.wait_for_function("() => document.activeElement === window.landed")
    expect(card).to_be_visible()
    rendered(page)
    expect(tip).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_says_nothing_its_target_shows_whole(engine, request, serve):
    """A preview says only what its target doesn't: a select its label names, however
    long its list, a button whose label is shorter than its face and a row whose words
    stand apart from its key preview nothing, nor does a status that declares its own
    words while they stand whole, though the window has scrolled, nor a word its markup
    splits. Cut short by its own box or the one around it, the status's words preview in
    full, and a symbol's name still previews, as does a slider's whose label the user
    can't see, a button's whose hidden notes run past a face, and one's that shows only
    the start of its name."""
    page = open_page(
        clocked(request.getfixturevalue(engine)),
        serve(
            leaf_page(
                "Faces",
                '<p><button id="before">Before</button></p>'
                # Far enough down that reaching the rest scrolls the window, which
                # clips nothing the user aims at.
                '<div style="height: 150vh"></div>'
                '<p><label>Speed <select id="speed"><option>1×</option>'
                "<option>0.5×</option></select></label></p>"
                # More options than a face holds, none of them saying "Country".
                '<p><label>Country <select id="country">'
                + "".join(f"<option>Region {n:02}</option>" for n in range(60))
                + "</select></label></p>"
                '<p><button id="send" aria-label="Send">Send reply</button></p>'
                '<p><span id="status" tabindex="0">Queued for the agent</span></p>'
                '<p><button id="undo" style="display: inline-grid;'
                ' grid-auto-flow: column; gap: 1em"><span>Undo the comment</span>'
                '<kbd aria-hidden="true">z</kbd></button></p>'
                '<p><button id="undo-cut" style="display: inline-grid;'
                " grid-auto-flow: column; gap: 1em; width: 6em; overflow: hidden;"
                ' white-space: nowrap"><span>Undo the comment</span>'
                '<kbd aria-hidden="true">z</kbd></button></p>'
                '<p><button id="download" aria-label="Download">Down<b>load</b>'
                "</button></p>"
                '<p><button id="file" aria-label="Download file">Down<b>load</b>'
                "</button></p>"
                '<p><button id="contents" aria-label="Download">'
                '<span style="display: contents">Download</span></button></p>'
                '<p><span id="cut" tabindex="0" style="display: inline-block;'
                " width: 5em; overflow: hidden; text-overflow: ellipsis;"
                ' white-space: nowrap">Queued for the agent</span></p>'
                '<p><button id="close" aria-label="Close the notes">×</button></p>'
                '<p style="width: 5em; overflow: hidden; white-space: nowrap">'
                '<span id="clipped" tabindex="0">Queued for the agent</span></p>'
                '<p><label for="rate" hidden>Playback speed</label>'
                '<input id="rate" type="range" aria-label="Playback speed"></p>'
                '<p><label for="volume" style="position: absolute; width: 1px;'
                " height: 1px; overflow: hidden; clip-path: inset(50%);"
                ' white-space: nowrap">Volume</label>'
                '<input id="volume" type="range"></p>'
                '<p><label for="pace" style="visibility: hidden">Pace</label>'
                '<input id="pace" type="range"></p>'
                '<p><button id="remove" aria-label="Delete item">×<span hidden>'
                + "a note "
                * 60
                + "</span></button></p>"
                '<p><button id="purge" aria-label="Delete the selected records"'
                ' style="width: 4.5em; overflow: hidden; white-space: nowrap">Delete'
                " <span>the selected records</span></button></p>"
                '<p><button id="invoice" style="width: 5em; overflow: hidden;'
                ' white-space: nowrap">Invoice <span>123456789</span></button></p>',
            )
        ),
    )
    page.evaluate(
        """() => {
          for (const id of ['status', 'cut', 'clipped']) {
            const el = document.getElementById(id);
            el.lfPreview = () => ({name: el.textContent});
          }
          for (const id of ['undo', 'undo-cut'])
            document.getElementById(id).lfPreview = () => ({});
        }"""
    )
    tip = page.locator(PREVIEW)
    for quiet in (
        "#speed",
        "#country",
        "#send",
        "#status",
        "#undo",
        "#download",
        "#file",
        "#contents",
    ):
        tab_onto(page.locator(quiet))
        rendered(page)
        expect(tip).to_be_hidden()
        page.locator(quiet).hover()
        dwelt(page)
        expect(tip).to_be_hidden()
        page.mouse.move(0, 0)
    for cut, says in (
        ("#cut", "Queued for the agent"),
        ("#close", "Close the notes"),
        ("#clipped", "Queued for the agent"),
        ("#rate", "Playback speed"),
        ("#volume", "Volume"),
        ("#pace", "Pace"),
        ("#remove", "Delete item"),
        ("#purge", "Delete the selected records"),
        ("#invoice", "Invoice 123456789"),
        ("#undo-cut", "Undo the comment"),
    ):
        tab_onto(page.locator(cut))
        expect(tip.locator(".lf-preview-word")).to_have_text(says)


def test_a_message_s_parts_follow_its_accepted_edit(browser, serve):
    """A message's markup is outlined as the page is, and an edit the log accepts
    outlines it again: the paragraph after a heading the edit changed stands under the
    new heading."""
    url = serve(PANEL_PAGE)
    thread = panel_comment(
        serve.page_dir, "## Original heading\n\nWords after the heading."
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, thread)
    part = """async () => {
      const {partOver} = await import('/runtime/records/thread/placement.js');
      const words = [...document.querySelectorAll('.lf-msg-body p')]
        .find((p) => p.textContent.includes('Words after the heading'));
      return partOver(words)?.textContent.trim() ?? null;
    }"""
    expect(view.locator("h2")).to_have_text("Original heading")
    assert page.evaluate(part) == "Original heading"
    view.locator(".lf-msg-text").dblclick()
    expect(view.locator(".lf-msg-editor leaf-text")).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("### Changed heading")
    page.keyboard.press("Shift+Enter")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("Words after the heading.")
    page.keyboard.press("Enter")
    expect(view.locator(".lf-msg-editor")).to_have_count(0)
    expect(view.locator(".lf-edited")).to_have_text("edited")
    told(page)
    expect(view.locator("h3")).to_have_text("Changed heading")
    assert page.evaluate(part) == "Changed heading"
