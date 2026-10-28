"""The comment composer's contents and recovery: the smallest message, pasted pictures
and uploads, Return on a phone, and Resume writing."""

import base64

import pytest
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, live_url
from render_cases_layout import glyph_action_face, token_colour
from render_cases_navigation import compose, pending_text
from render_harness import (
    LONG_PAGE,
    PANEL,
    available_commands,
    draft_control,
    example_media,
    expect_error_waits_in_menu,
    expect_panel_says,
    holding,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_control,
    panel_field,
    panel_settled,
    primed,
    resized,
    scroll_settled,
    select_words,
    sending,
    stamp_page,
    stored_draft_text,
    write,
)

from browser.margin import MARGIN_EDITOR_ROOTS
from browser.threads import clear_of_the_panel
from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_a_single_space_is_message_content_in_every_composer(browser, serve):
    """The shared field and both drawing-aware variants admit the smallest message,
    each box sending in turn on one page: an open thread's reply and the page comment,
    both in the panel's field, and the passage composer.

    The composer sends from the one press the shared field dresses, and that press paints
    nothing of its own: at rest the accent glyph is the whole of what a user sees, and
    the disc behind it is a clear 28px that takes the accent tint under the pointer,
    which is why it stays the same size as the target around it grows.
    """
    page = open_page(browser, serve(LONG_PAGE, comments=True))
    for box in ("reply", "general", "composer"):
        if box == "composer":
            select_words(page, "#p0")
            expect(page.locator(".lf-fab-input")).to_be_visible()
            page.keyboard.press("c")
            surface = page.locator(".lf-composer")
        elif box == "general":
            page_comment(page)
            surface = page.locator(".lf-fp-field")
        else:
            open_threads(page)
            page.locator(".lf-fp-thread").first.click()
            panel_settled(page, view="thread")
            surface = page.locator(".lf-fp-field")
        field = surface.locator("leaf-text")
        send = surface.locator(".lf-compose-submit")
        write(field, " ")
        expect(send).to_have_attribute("aria-disabled", "false")
        if box != "composer":
            # The panel's field shows Send only once its words hold more than space
            # (floating-panel.js, `typing`), so its keys send the space.
            with sending(page, f"the {box} message"):
                field.press("ControlOrMeta+Enter")
        else:
            face = glyph_action_face(send)
            assert face["press"] == "rgba(0, 0, 0, 0)", face
            assert face["glyph"] == token_colour(page, "--accent"), face
            assert face["disc"] == "rgba(0, 0, 0, 0)", face
            assert face["discWidth"] == "28px", face
            send.hover()
            hovered = glyph_action_face(send)
            assert hovered["press"] == "rgba(0, 0, 0, 0)", hovered
            assert hovered["disc"] == token_colour(page, "--accent-tint"), hovered
            assert hovered["discWidth"] == "28px", hovered
            with sending(page, f"the {box} message"):
                send.click()

        message = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] in {"comment", "reply"}
        ][-1]
        assert message["text"] == " ", box


def test_words_typed_over_formatted_words_replace_them_in_firefox(
    firefox_browser, serve
):
    """Typing over a selection replaces it when the selection crosses formatting. In a
    shadow root, Firefox inserted the words beside such a selection and left it in
    place (field-editor.js, `beforeinput`)."""
    page = open_page(firefox_browser, serve(LONG_PAGE), init_script=MARGIN_EDITOR_ROOTS)
    box = page_comment(page)
    page.keyboard.type("aa **bold** zz")
    page.wait_for_function(
        "box => window.marginEditorRoots.get(box)?.querySelector('.cm-content strong')",
        arg=box.element_handle(),
    )
    for select in (["ControlOrMeta+a"], ["End", *["Shift+ArrowLeft"] * 5]):
        for key in select:
            page.keyboard.press(key)
        page.keyboard.type("Q")
        expect(box).to_have_js_property(
            "value", "Q" if len(select) == 1 else "aa **boldQ"
        )
        page.keyboard.press("ControlOrMeta+z")
        expect(box).to_have_js_property("value", "aa **bold** zz")


def test_a_draft_the_chrome_stands_down_says_so_and_keeps_an_address(browser, serve):
    """A press on the chrome takes the composer off screen and keeps the words, and for
    a long time that was the whole of it: the bar went, the mark went, no notice and no
    dialog said anything, and the only way back was returning to that version and
    reselecting that exact passage. Words a user cannot find again are words they have
    lost, whatever localStorage still holds.

    So the moment says what became of them and names the address that answers — and the
    address is offered only while there is a draft still there to go to, which is the half
    that keeps the sentence honest."""
    page = open_page(browser, serve(LONG_PAGE))
    kept = "Half a sentence, and then the panel."

    # Nothing written, nothing to return to: the address is not offered.
    assert "writing.resume" not in available_commands(page)

    compose(page, "#p3", kept)
    assert pending_text(page), "the open box left its own passage unmarked"

    open_threads(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert pending_text(page) == "", "a box off screen left its passage marked"
    expect_panel_says(page, "Draft kept — g i resumes writing")

    assert "writing.resume" in available_commands(page)
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", kept)
    assert pending_text(page), "the box came back on nothing"


def test_picture_paste_belongs_to_the_composer_not_the_shared_text_field(
    browser, serve
):
    """A direct editor pastes text; a composer takes pictures before text insertion."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Paste ownership",
                '<h1>Paste ownership</h1><p id="passage">Comment on this passage.</p>'
                '<lf-draft id="text-only"><pre>Keep WORD tail</pre></lf-draft>',
            )
        ),
    )
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    pixels = base64.b64encode(
        (example_media() / "051bee487bfb5d13.png").read_bytes()
    ).decode()
    page.evaluate(
        """async encoded => {
      window.clipboardBeforePasteTest = await navigator.clipboard.read();
      const bytes=Uint8Array.from(atob(encoded), char=>char.charCodeAt(0));
      window.pasteTestPicture=new Blob([bytes], {type:'image/png'});
    }""",
        pixels,
    )

    def paste(box, text, picture):
        box.focus()
        box.evaluate("el=>el.setSelectionRange(5,9)")
        page.evaluate(
            """async ([text,picture]) => {
          const payload={};
          if(text!==null)payload['text/plain']=new Blob([text],{type:'text/plain'});
          if(picture)payload['image/png']=window.pasteTestPicture;
          await navigator.clipboard.write([new ClipboardItem(payload)]);
        }""",
            [text, picture],
        )
        page.keyboard.press("ControlOrMeta+v")

    try:
        draft_control(page, "edit", "text-only").click()
        editor = page.locator("#text-only leaf-text")
        for text, picture, expected in [
            ("Pasted words", False, "Keep Pasted words tail"),
            ("Pasted words", True, "Keep Pasted words tail"),
            (None, True, "Keep  tail"),
        ]:
            write(editor, "Keep WORD tail")
            paste(editor, text, picture)
            expect(editor).to_have_js_property("value", expected)
        draft_control(page, "cancel", "text-only").click()

        compose(page, "#passage")
        composer = page.locator(".lf-fab-input")
        write(composer, "Keep WORD tail")
        with page.expect_response(lambda response: response.url.endswith("/api/media")):
            paste(composer, "Pasted words", True)
        expect(page.locator(".lf-composer-media img")).to_have_count(1)
        expect(composer).to_have_js_property("value", "Keep WORD tail")
        # Editing another surface chooses it; attachment removal is an edit that
        # chooses this composer again even though focusing it alone did not.
        page.keyboard.press("Escape")
        draft_control(page, "edit", "text-only").click()
        write(editor, "A later document edit")
        page.keyboard.press("Escape")
        compose(page, "#passage")
        page.get_by_role("button", name="Remove attached image 1", exact=True).click()
        expect(page.locator(".lf-composer-media img")).to_have_count(0)
        page.locator("h1").click()
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(composer).to_be_focused()
        expect(composer).to_have_js_property("value", "Keep WORD tail")
    finally:
        page.evaluate("""async () => {
          const previous=window.clipboardBeforePasteTest;
          if(previous.length)await navigator.clipboard.write(previous);
          else await navigator.clipboard.writeText('');
        }""")


@pytest.mark.parametrize("leave", [False, True])
def test_image_upload_completion_preserves_the_readers_focus_and_scroll(
    browser, serve, leave
):
    """Finishing a paste updates the draft without repeating the user's entry gesture."""
    held = []
    controlled = primed(
        browser,
        lambda page: page.route("**/api/media", lambda route: held.append(route)),
    )
    page = open_page(controlled, serve(LONG_PAGE))
    compose(page, "#p3")
    box = page.locator(".lf-fab-input")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    box.evaluate(
        """(box, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
          box.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""",
        base64.b64encode(pixels).decode(),
    )
    holding(page, held, 1, "the pasted image")
    expect(box).to_have_attribute("aria-busy", "true")
    expect(box).to_be_focused()
    if leave:
        page.keyboard.press("Tab")
        expect(box).not_to_be_focused()
        page.mouse.move(100, 500)
        page.mouse.wheel(0, 1000)
        page.wait_for_function("scrollY > 800")
        scroll_settled(page)
    before = page.evaluate("scrollY")
    page.evaluate("window.uploadFocus = document.activeElement")
    held.pop().continue_()
    expect(box).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-composer-media img")).to_have_count(1)
    assert page.evaluate("scrollY") == before
    assert page.evaluate("document.activeElement === window.uploadFocus")


def test_a_picture_still_uploading_stays_out_of_the_next_passages_draft(browser, serve):
    """The comment box moves to another passage while a pasted picture uploads. The
    picture was the first passage's, so it does not land in the second one's draft, and
    the user is told it was not added rather than finding it somewhere they did not put
    it."""
    held = []
    controlled = primed(
        browser,
        lambda page: page.route("**/api/media", lambda route: held.append(route)),
    )
    page = open_page(controlled, serve(LONG_PAGE))
    compose(page, "#p3")
    box = page.locator(".lf-fab-input")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    box.evaluate(
        """(box, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
          box.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""",
        base64.b64encode(pixels).decode(),
    )
    holding(page, held, 1, "the pasted image")
    compose(page, "#p1")
    held.pop().continue_()
    expect(box).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-composer-media img")).to_have_count(0)
    # The error is about the composer, so it stands over the box the paste was made in,
    # and waits in the leaf's menu once the user writes there.
    cover = page.locator(".lf-fab-bar .lf-compose-error")
    expect(cover).to_have_text(
        "Image not added — the comment moved before it finished uploading"
    )
    page.keyboard.type("Instead")
    expect(cover).to_be_hidden()
    expect(box).to_have_js_property("value", "Instead")
    expect_error_waits_in_menu(
        page, "Image not added — the comment moved before it finished uploading"
    )


def test_a_pasted_image_is_a_whole_draft_and_leaves_with_the_send_that_took_it(
    browser, serve
):
    """An image and no words is a draft, and the text box is the one place it does not
    show: the box keeps the Markdown and the shelf shows the thumbnail. So a reading
    that asks the text box whether anything is in here answers "empty" about a box the
    user can see holds a picture, and the two directions fail in opposite ways — the
    kept notice never appears for a picture put away, and it appears for a picture that
    has just been sent, over a box with nothing left in it.

    Both directions here, and the box the user opens next, because a shelf that
    outlived its send is an image that rides into the next passage's draft."""
    page = open_page(browser, serve(LONG_PAGE))
    image_markdown = "![Attached image](/media/051bee487bfb5d13.png)"
    compose(page, "#p3")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.locator(".lf-fab-input").evaluate(
            """(box, encoded) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
              box.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: transfer,
              }));
            }""",
            base64.b64encode(pixels).decode(),
        )
    shelf = page.locator(".lf-composer .lf-composer-media")
    expect(shelf.locator("img")).to_be_visible()

    # Put away: the picture is words enough to keep, and to be told about.
    open_threads(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect_panel_says(page, "Draft kept — g i resumes writing")
    assert "writing.resume" in available_commands(page)
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", "")
    expect(shelf.locator("img")).to_be_visible()

    # Sent: the box is empty because the send emptied it, and says nothing about drafts.
    # Every word a notice says through the send, not the one left standing at the end of
    # it: a wrong sentence four seconds long is one the user reads. The live region hears
    # every notice the panel shows, wherever it seats it.
    page.evaluate("""() => {
      const el = document.querySelector('.lf-live');
      window.__said = [];
      new MutationObserver(() => window.__said.push(el.textContent)).observe(el, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }""")
    with sending(page, "the image-only comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert events_model.read_events(serve.page_dir)[-1]["text"] == image_markdown
    said = page.evaluate("window.__said")
    assert not [words for words in said if "Draft kept" in words], said

    # And the next passage's box opens on nothing, shelf included.
    typed = "A second comment, and no image with it."
    compose(page, "#p5", typed)
    expect(shelf).to_be_hidden()
    with sending(page, "the second comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    assert events_model.read_events(serve.page_dir)[-1]["text"] == typed


def test_resume_writing_is_a_touch_action_and_does_not_steal_hint_addresses(
    browser, serve
):
    """A finger can resume the general box; gi never collides with generated hints."""
    source = leaf_page(
        "Resume targets",
        '<h1 id="heading">Resume targets</h1>'
        + "".join(
            f'<p><a id="link{index}" href="#heading">Jump {index}</a></p>'
            for index in range(30)
        ),
    )
    page = open_page(browser, serve(source))
    write(page_comment(page), "A page-wide draft")
    page.keyboard.press("Escape")
    expect(panel_field(page)).not_to_be_focused()
    page.keyboard.press("g")
    expect(page.locator(".lf-go-to-hint[data-lf-hint-code]").first).to_be_visible()
    labels = page.locator(".lf-go-to-hint[data-lf-hint-code]").evaluate_all(
        "els => els.map(el => el.dataset.lfHintCode)"
    )
    assert labels and all("i" not in label for label in labels)
    # The page's draft resumes in the panel's field.
    page.keyboard.press("i")
    box = page.locator('.lf-fp-field leaf-text[name="comment"]')
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "A page-wide draft")
    page.keyboard.press("Escape")
    context = browser.new_context(
        is_mobile=True, has_touch=True, viewport={"width": 390, "height": 844}
    )
    touch = open_page(browser, serve(LONG_PAGE), context=context)
    general = page_comment(touch)
    write(general, "A touch draft")
    touch.keyboard.press("Escape")
    expect(general).not_to_be_focused()
    # A finger has no `g i`, so Resume writing stands under the menu's Navigate.
    panel_control(touch, "command:writing.resume", at="navigate").click()
    expect(general).to_be_focused()
    expect(general).to_have_js_property("value", "A touch draft")


@pytest.mark.parametrize("hidden_tab", [False, True])
def test_resume_writing_reveals_page_editor_from_a_covering_panel_and_keeps_back(
    browser, serve, hidden_tab
):
    """Resume exposes a hidden editor's place immediately and keeps the outgoing reading.

    The user leaves the open draft by the keyboard and by scrolling: a press away from
    it would save it, leaving nothing to resume."""
    writing = (
        '<details id="fold" open><summary>Editable content</summary>'
        '<lf-draft id="editable"><pre>Initial words</pre></lf-draft></details>'
    )
    reading = (
        '<div style="height:2200px"></div><h2 id="elsewhere">Elsewhere</h2>'
        "<p>Keep this reading position.</p>"
    )
    body = writing + reading
    if hidden_tab:
        body = (
            '<lf-tabs id="views"><lf-tab id="writing-view" label="Writing">'
            + writing
            + '<div style="height:3300px"></div>'
            '</lf-tab><lf-tab id="reading-view" label="Reading">'
            + reading
            + "</lf-tab></lf-tabs>"
        )
    page = open_page(
        browser,
        serve(leaf_page("Resume travel", '<h1 id="top">Resume travel</h1>' + body)),
    )
    page.locator("#editable .lf-draft-body").click()
    edit = page.locator("#editable .lf-draft-edit")
    write(edit, "Last edit")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.locator("#fold > summary").focus()
    page.keyboard.press("Enter")
    if hidden_tab:
        page.get_by_role("tab", name="Reading", exact=True).focus()
        page.keyboard.press("Enter")
    page.locator("#elsewhere").scroll_into_view_if_needed()
    resized(page, 390, 844)
    scroll_settled(page)
    source_entry = page.evaluate("navigation.currentEntry.key")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(PANEL)).to_have_attribute("data-open", "threads")
    page.keyboard.press("g")
    page.keyboard.press("i")
    if hidden_tab:
        expect(page.locator("#writing-view")).to_be_visible()
        first_view = page.locator("#editable").evaluate("""async draft => {
          const {landingBand} = await window.__lfCheckApi();
          const rect = draft.getBoundingClientRect();
          const band = landingBand(document.scrollingElement);
          return {top: rect.top, bottom: rect.bottom, low: band.top, high: band.bottom};
        }""")
        assert first_view["top"] >= first_view["low"], first_view
        assert first_view["bottom"] <= first_view["high"], first_view
    expect(edit).to_be_focused()
    # In sight: in the window, clear of the panel's open view where it covers the page.
    assert clear_of_the_panel(page, edit)
    expect(edit).to_have_js_property("value", "Last edit")
    assert edit.evaluate("el => el.selectionStart") == 1
    page.go_back()
    scroll_settled(page)
    expect(page.locator("#elsewhere")).to_be_in_viewport()
    assert page.evaluate("navigation.currentEntry.key") == source_entry
    # Clearing every word still records a real editor destination.
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(edit).to_be_focused()
    edit.press("ControlOrMeta+a")
    edit.press("Backspace")
    edit.blur()
    if hidden_tab:
        page.get_by_role("tab", name="Reading", exact=True).focus()
        page.keyboard.press("Enter")
    page.locator("#elsewhere").scroll_into_view_if_needed()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(edit).to_be_focused()
    expect(edit).to_have_js_property("value", "")


def test_resume_writing_opens_words_whose_box_is_gone_as_a_comment_on_the_page(
    browser, serve
):
    """Words whose box the page no longer has open, unsent, in Comment on the page.

    The agent's next version removes the content the user was editing. Their edit
    stays saved, and Resume writing moves it into the page's comment box after the
    words that box already held, so the words stand in one place and nothing is lost."""
    edited = (
        '<lf-draft id="editable"><pre>Initial words</pre></lf-draft>'
        "<p>The rest of the page.</p>"
    )
    source = leaf_page("Removed box", '<h1 id="top">Removed box</h1>' + edited)
    url = live_url(serve(source))
    context = browser.new_context()
    page = open_page(browser, url, context=context)
    write(page_comment(page), "A page-wide thought.")
    page.keyboard.press("Escape")
    page.locator("#editable .lf-draft-body").click()
    write(page.locator("#editable .lf-draft-edit"), "An unsent edit.")
    stamp_page(
        serve.page_dir, source.replace(edited, "<p>The rest of the page.</p>"), "cut"
    )
    page = open_page(browser, url, context=context)
    expect(page.locator("#editable")).to_have_count(0)

    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("i")
    box = page.locator('.lf-fp-field leaf-text[name="comment"]')
    joined = "A page-wide thought.\n\nAn unsent edit."
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", joined)
    assert box.evaluate("el => [el.selectionStart, el.selectionEnd]") == [
        len(joined),
        len(joined),
    ]
    # The caret stands in the field, where nothing passing is said but to a listener.
    expect(page.locator(".lf-live")).to_have_text(
        "Its box is gone, so its words moved to a comment on the page"
    )
    assert stored_draft_text(page, "edit:editable") is None
    assert stored_draft_text(page, "general") == joined


def test_resume_writing_returns_to_an_option_being_added(browser, serve):
    """The field adding an option the author did not list is a writing place like any
    other: Resume writing comes back to it with its words, which stay its own."""
    page = open_page(browser, serve(OBLIGATION_PAGE))
    field = page.locator("#jobs > .lf-another leaf-text")
    write(field, "An option of mine.")
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "An option of mine.")
    assert stored_draft_text(page, "general") is None


def test_an_older_version_leaves_words_its_box_is_missing_from_where_they_are(
    browser, serve
):
    """A version behind the newest may lack a box the newest holds, so there Resume
    writing says the place is unavailable and the words stay in their own draft."""
    edited = '<lf-draft id="editable"><pre>Initial words</pre></lf-draft>'
    older = leaf_page("Added box", '<h1 id="top">Added box</h1><p>The page.</p>')
    first = serve(older)
    stamp_page(serve.page_dir, older.replace("<p>The page.</p>", edited), "add")
    context = browser.new_context()
    page = open_page(browser, live_url(first), context=context)
    page.locator("#editable .lf-draft-body").click()
    write(page.locator("#editable .lf-draft-edit"), "An unsent edit.")
    page = open_page(browser, first, pin=True, context=context)
    expect(page.locator("#editable")).to_have_count(0)

    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect_panel_says(page, "That writing place is unavailable on this version")
    assert stored_draft_text(page, "edit:editable") == "An unsent edit."
    assert stored_draft_text(page, "general") is None


@pytest.mark.parametrize("keyboard", ["desktop", "touch", "android"])
def test_composer_return_edits_or_sends_according_to_its_keyboard(
    browser, serve, keyboard
):
    """Mobile Return keeps a source newline, including Android's EditContext path."""
    options = {
        "viewport": {"width": 360 if keyboard != "desktop" else 1280, "height": 732},
        "is_mobile": keyboard != "desktop",
        "has_touch": keyboard != "desktop",
    }
    if keyboard == "android":
        options["user_agent"] = (
            "Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/155.0.8059.12 Mobile Safari/537.36"
        )
    context = browser.new_context(**options)
    page = open_page(browser, serve(LONG_PAGE), context=context)
    editor = page_comment(page)
    page.keyboard.type("First sentence.")
    editor.press("Shift+Enter" if keyboard == "desktop" else "Enter")
    expect(editor).to_have_js_property("value", "First sentence.\n")
    page.keyboard.type("Second sentence.")
    exact = "First sentence.\nSecond sentence."
    expect(editor).to_have_js_property("value", exact)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    with sending(page, "the complete multiline comment"):
        editor.press("Enter" if keyboard == "desktop" else "ControlOrMeta+Enter")
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [exact]


def test_markdown_decoration_keeps_source_editable(browser, serve):
    """Headings and code follow the renderer; new bullets render before typing text."""
    page = open_page(browser, serve(LONG_PAGE))
    field = page_comment(page)
    source = "> - # Heading\n\n````\n```\nbody\n````\n\n**end**"
    write(field, source)
    expect(field).to_have_js_property("value", source)
    cdp = page.context.new_cdp_session(page)

    def reading():
        focused = cdp.send(
            "Runtime.evaluate", {"expression": "document.activeElement"}
        )["result"]["objectId"]
        node = cdp.send("DOM.describeNode", {"objectId": focused, "depth": 1})["node"]
        root = cdp.send(
            "DOM.resolveNode",
            {"backendNodeId": node["shadowRoots"][0]["backendNodeId"]},
        )["object"]["objectId"]
        return cdp.send(
            "Runtime.callFunctionOn",
            {
                "objectId": root,
                "returnByValue": True,
                "functionDeclaration": """function() {
              return [...this.querySelectorAll('.cm-line')].map(line => ({
                text: line.textContent, heading: line.classList.contains('lf-md-heading'),
                syntax: [...line.querySelectorAll('.lf-md-mark, .lf-md-unseen')].map(mark => mark.textContent),
                strong: line.querySelector('strong')?.textContent,
                listed: getComputedStyle(line.closest('.lf-md-item') ?? line).display === 'list-item',
                shownMarkers: [...line.querySelectorAll('.lf-md-marker:not(.lf-md-unseen)')].map(mark => mark.textContent),
              }));
            }""",
            },
        )["result"]["value"]

    lines = reading()
    assert lines[0]["heading"] and "Heading" in lines[0]["text"], lines
    assert lines[3]["text"] == "```" and not lines[3]["syntax"], lines
    assert lines[2]["syntax"] == ["````"] and lines[5]["syntax"] == ["````"], lines
    assert lines[-1]["strong"] == "**end**", lines
    # Native caret movement and undo preserve the exact source, including the
    # delimiter the renderer reads as literal code.
    page.keyboard.press("ControlOrMeta+Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.insert_text("x")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", source)
    assert reading()[0]["heading"]

    # Continuing a list already shows its bullet. Typing the first letter must not
    # be what changes the marker, and moving into its source must still expose it.
    write(field, "- First")
    field.press("Shift+Enter")
    expect(field).to_have_js_property("value", "- First\n- ")
    lines = reading()
    assert len(lines) == 2, lines
    assert all(line["listed"] and not line["shownMarkers"] for line in lines), lines
    field.press("ArrowLeft")
    assert reading()[-1]["shownMarkers"] == ["- "]
    field.press("Backspace")
    expect(field).to_have_js_property("value", "- First\n ")
    page.keyboard.type("*")
    expect(field).to_have_js_property("value", "- First\n* ")
    assert reading()[-1]["shownMarkers"] == ["* "]
    field.press("ArrowRight")
    assert reading()[-1]["listed"]
    page.keyboard.type("Carts")
    expect(field).to_have_js_property("value", "- First\n* Carts")
    assert reading()[-1]["listed"]
    field.press("ArrowLeft")
    field.press("Backspace")
    expect(field).to_have_js_property("value", "- First\n* Cars")
    field.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "- First\n* Carts")
    cdp.detach()
