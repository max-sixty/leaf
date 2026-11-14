"""The UI states `leaf-dev stills` compares and `leaf-dev probe --state` opens.

A state is one surface: a page, by the name `leaf-dev probe` also takes
(`named_source`), and the input that brings a fresh tab there (`State.drive`, none for
the page as it loads). `STATES` holds a state at rest for each page the corpus
composes, named after its file (`corpus.sources`), and the surfaces a user reaches by
acting. Where a change touches a surface no state reaches, add one state for it, never
one per size, scheme or pointer: `--viewport`, `--scheme` and `--touch` choose those
for every state a run opens, in stills and probe alike, and a surface laid out
differently on a phone is still one state. A state names its own window only where
its surface appears in no other, such as a card in a short window or the floating
panel's view of a thread on a phone; `--viewport` replaces it, and `--touch` or
`--no-touch` sets its pointer (`browser.chosen_window`).
A state may name a region whose before/after bounds frame stills' comparison,
retaining related controls without shrinking their details behind unrelated viewport
changes.

`leaf_dev.visits` brings each arm's tab to a state, in the engine the run chose. A
state that engine can't reach fails with the reason, as one with an input does on the
iOS simulator, whose Safari takes none.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from playwright.sync_api import Locator, Page, expect

from leaf.render_checks import wait_until_ready
from leaf_dev.arms import PageClient, served_page
from leaf_dev.browser import (
    PANEL,
    WINDOWS,
    Window,
    go_to_threads,
    load,
    panel_view,
    scroll_settled,
    settle,
)
from leaf_dev.commands.corpus import sources as corpus_sources

OPEN_CARD = "() => document.querySelector('.lf-margin-preview:not([hidden])')"


def printed_exhibit(page: Page) -> None:
    """A breakout exhibit within the paper's prose track."""
    page.emulate_media(media="print")


def failed_widget(page: Page) -> None:
    """A failed full-width exhibit beside the document's prose."""
    page.evaluate("""async () => {
        const boot = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
        const {failSoft} = await import(new URL('runtime/widget-api.js', new URL(boot, location.href)));
        const host = document.createElement('div');
        host.id = 'failed-exhibit';
        host.dataset.lfSpace = 'available';
        document.querySelector('main').prepend(host);
        failSoft(host, new Error('The exhibit could not render its source.'),
            'source row: ' + 'unbroken_source_value_'.repeat(12));
    }""")
    expect(page.locator("#failed-exhibit > .lf-error")).to_be_visible()


def worktree_summaries(page: Page) -> None:
    """Close the initially open worktree so the list's summary columns stand together.
    Press the widget's summary by its class, since the authored evidence in the row
    holds a summary of its own."""
    worktree = page.locator("#worktree-example-worktree-0")
    worktree.locator(".lf-worktree-summary").click()
    expect(worktree.locator(".lf-worktree-disclosure")).not_to_have_attribute("open")


def plan_execution(page: Page) -> None:
    """The execution step with its security qualification in view."""
    page.locator("#plan-execute > h3").evaluate(
        "element => element.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    scroll_settled(page)


def captured_source(page: Page) -> None:
    """The gallery's captured source file, with its numbered syntax presentation."""
    page.locator("#bg-gallery-tabs").get_by_role(
        "tab", name="Data & work", exact=True
    ).click()
    page.locator("#bg-source-captures").scroll_into_view_if_needed()


def long_source_selected(page: Page) -> None:
    """A long captured source scrolled to where its 128th line, which ends the first
    run of lines the listing draws, meets the next, each coloured as it shows, with a
    selection from the middle of one into the other."""
    page.locator("#pr-prepared-diff-evidence > summary").click()
    pre = page.locator("#pr-prepared-diff-source pre")
    pre.scroll_into_view_if_needed()
    pre.evaluate("pre => { pre.scrollTop = 2400; }")
    scroll_settled(page, "#pr-prepared-diff-source pre")
    start, end = pre.evaluate("""pre => {
      const walker = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT);
      const at = (words) => {
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          const index = node.data.indexOf(words);
          if (index < 0) continue;
          const range = document.createRange();
          range.setStart(node, index);
          range.setEnd(node, index + words.length);
          return range.getBoundingClientRect().toJSON();
        }
      };
      return [at('from_slice'), at('stream')];
    }""")
    page.mouse.move(start["left"] + 1, start["top"] + start["height"] / 2)
    page.mouse.down()
    page.mouse.move(end["left"] + 1, end["top"] + end["height"] / 2, steps=6)
    page.mouse.up()


def captured_source_by_keyboard(page: Page) -> None:
    """The captured source's scroller focused by keyboard, its ring over the lines."""
    captured_source(page)
    page.keyboard.press("Tab")
    page.locator("#bg-source-live .lf-text-document-listing > pre").focus()


def native_code(page: Page) -> None:
    """Native fenced code using short language labels."""
    page.locator("#bg-gallery-tabs").get_by_role(
        "tab", name="Page & layout", exact=True
    ).click()
    page.locator("#bg-javascript-code").scroll_into_view_if_needed()


def annotated_code(page: Page) -> None:
    """Syntax colours inside authored marks, line wrappers and link targets."""
    native_code(page)
    page.locator("#bg-annotated-code").scroll_into_view_if_needed()


def native_code_copy_hover(page: Page) -> None:
    """A document code block under the pointer, which shows its Copy on its border."""
    native_code(page)
    page.locator("#bg-javascript-code").hover()


def recorded_video(page: Page) -> None:
    """The gallery's recording at rest under its play bar, beside the audio player."""
    page.locator("#bg-gallery-tabs").get_by_role(
        "tab", name="Page & layout", exact=True
    ).click()
    page.locator("#bg-recorded-media").scroll_into_view_if_needed()


def recorded_video_by_keyboard(page: Page) -> None:
    """The recording the keyboard stands on, where Space and the arrows reach it."""
    recorded_video(page)
    page.keyboard.press("Tab")
    page.locator("#bg-recording").focus()


def markdown_preview_scrolled(page: Page) -> None:
    """A Markdown code example scrolled under the preview's focused viewport edge."""
    page.locator("#bg-gallery-tabs").get_by_role(
        "tab", name="Data & work", exact=True
    ).click()
    page.locator("#bg-document-previews").scroll_into_view_if_needed()
    viewer = page.locator("#bg-markdown-preview")
    viewer.scroll_into_view_if_needed()
    viewer.get_by_role("tab", name="Preview", exact=True).click()
    page.keyboard.press("Tab")
    panel = "#bg-markdown-preview--preview"
    expect(page.locator(panel)).to_be_focused()
    page.keyboard.press("PageDown")
    page.wait_for_function(
        "selector => document.querySelector(selector).scrollTop > 0", arg=panel
    )
    scroll_settled(page, panel)


def dynamic_request_preview(page: Page) -> None:
    """The generated request as rendered Markdown inside its padded preview."""
    page.locator(".source-details").first.locator("summary").click()
    page.locator("#leaf-request-document").scroll_into_view_if_needed()


def tab_by_keyboard(page: Page) -> None:
    """The selected tab's focus beside its persistent selection mark."""
    page.keyboard.press("Tab")
    page.locator(".lf-tab-btn").first.focus()


def tab_by_pointer(page: Page) -> None:
    """The pointer's preview of an unselected tab beside the selected one."""
    page.locator(".lf-tab-btn").nth(1).hover()


def boxed_tab_by_keyboard(page: Page) -> None:
    """A boxed tab's compact focus and persistent selection fill."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Page & layout", exact=True
    ).click()
    page.locator("#bg-tabs").scroll_into_view_if_needed()
    page.keyboard.press("Tab")
    page.locator("#bg-tabs .lf-tab-btn").first.focus()


def boxed_tab_panel_by_keyboard(page: Page) -> None:
    """A boxed tab set's open panel focused by keyboard, ringed inside its border."""
    boxed_tab_by_keyboard(page)
    page.keyboard.press("Tab")
    expect(page.locator("#bg-tabs > lf-tab:not([hidden])")).to_be_focused()


def drawing_comment(page: Page) -> None:
    """A freehand comment beside the page area its strokes describe."""
    guide = page.locator("#bg-drawing-comments-guide")
    guide.scroll_into_view_if_needed()
    settle(page)
    box = guide.bounding_box()
    assert box is not None
    page.keyboard.press("w")
    page.mouse.move(box["x"] + 25, box["y"] + 15)
    page.mouse.down()
    page.mouse.move(box["x"] + 180, box["y"] + 32, steps=12)
    page.mouse.move(box["x"] + 80, box["y"] + 48, steps=12)
    page.mouse.up()
    page.locator(".lf-composer-drawing").wait_for(state="visible")
    settle(page)
    page.locator(
        '.lf-composer-drawing canvas[data-lf-drawing-context="ready"]'
    ).wait_for(state="visible")


def drawing_comment_hover(page: Page) -> None:
    """The drawing's corner marks a pointer over it reveals."""
    drawing_comment(page)
    page.locator(".lf-composer-drawing .lf-media-open").hover()


def drawing_comment_keyboard(page: Page) -> None:
    """The drawing's Undo last stroke holding keyboard focus."""
    drawing_comment(page)
    page.get_by_role("button", name="Undo last stroke").focus()


def paste_screenshot(page: Page, field: Locator) -> None:
    """Paste the feature gallery's screenshot into `field` and wait for its picture."""
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        # This exercises the paste handler and shelf; keep its payload local to the
        # tab so captures cannot overwrite or race the machine's clipboard.
        field.evaluate("""async field => {
          const response = await fetch('/media/051bee487bfb5d13.png');
          const image = await response.blob();
          const transfer = new DataTransfer();
          transfer.items.add(new File([image], 'pasted.png', {type: 'image/png'}));
          field.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""")
    expect(
        page.get_by_role("button", name="Remove attached image 1", exact=True)
    ).to_be_visible()
    settle(page)


def drawing_photo_comment(page: Page) -> None:
    """Drawing and photo removal together in the same draft attachment shelf."""
    drawing_comment(page)
    field = page.locator(".lf-fab-input")
    field.focus()
    paste_screenshot(page, field)


def page_comment_photo(page: Page) -> None:
    """The floating panel's field with a pasted screenshot hanging above the panel."""
    field = page.locator(".lf-fp-field leaf-text")
    field.click()
    page.keyboard.insert_text("Is this screenshot right?")
    paste_screenshot(page, field)


def page_comment_photo_hover(page: Page) -> None:
    """The panel's attached screenshot under the pointer, which shows its removal."""
    page_comment_photo(page)
    page.locator(".lf-fp-field .lf-composer-media-open").hover()


def panel_corner_hover(page: Page) -> None:
    """The pointer at the panel's top-right corner, which shows its fold."""
    box = page.locator(".lf-fp-card").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] - 24, box["y"] + 8)
    expect(page.locator(".lf-fp-minimize")).to_be_visible()
    settle(page)


def share_link(page: Page) -> None:
    """The page's link, focused by keyboard as read-only text in About this page,
    which the menu's Copy link opens when the clipboard refuses the copy."""
    page.evaluate(
        "() => { Clipboard.prototype.writeText ="
        " () => Promise.reject(new Error('refused')); }"
    )
    page.locator(".lf-fp-leaf").click()
    page.locator('.lf-fp-item[data-lf-row="share"]').click()
    about = page.get_by_role("dialog", name="About this page", exact=True)
    expect(about).to_contain_text(re.compile(r"Source captured for r\d+"))
    link = about.get_by_label("Link", exact=True)
    page.keyboard.press("Shift")  # keyboard modality, so focus is drawn
    link.focus()
    expect(link).to_be_focused()


def diff_filter(page: Page) -> None:
    """A nonempty file filter with Clear and its match count inside one field, on the
    walkthrough's whole patch, since a diff of one file offers no filter."""
    field = page.locator("#pr-exact-patch").get_by_role(
        "searchbox", name="Filter diff files"
    )
    field.scroll_into_view_if_needed()
    page.keyboard.press("Tab")
    field.fill("no-match")
    expect(field).to_have_value("no-match")
    settle(page)


def diff_separator(page: Page) -> None:
    """A hunk separator's label between the source lines around it."""
    page.locator("#pr-key-hunk [data-separator]").first.scroll_into_view_if_needed()
    settle(page)


def diff_file_comment(page: Page) -> None:
    """A diff file's comment box, opened from the file's Comment once the walkthrough's
    longest file is open beneath its row at the window's top, which leaves the file's
    end, where its thread stands, below the window until the box's focus."""
    files = page.locator("#pr-exact-patch .lf-diff-file")
    longest = files.evaluate_all(
        """files => {
            const size = (file) => [...file.querySelector('.lf-diff-head').textContent
                .matchAll(/[+\u2212-](\\d+)/g)].reduce((sum, [, n]) => sum + +n, 0);
            return files.indexOf(files.reduce((a, b) => (size(b) > size(a) ? b : a)));
        }"""
    )
    file = files.nth(longest)
    file.locator(".lf-diff-head").click()
    file.locator(".lf-diff-line").first.wait_for()
    file.evaluate(
        "file => scrollTo(0, scrollY + file.getBoundingClientRect().top - 80)"
    )
    scroll_settled(page)
    file.locator(".lf-diff-file-comment").click()
    expect(
        page.locator(".lf-fab-bar .lf-composer[data-lf-open] leaf-text")
    ).to_be_focused()
    settle(page)


def playground_text(page: Page) -> None:
    """A playground's native text control with the shared field face and focus."""
    field = page.get_by_role("textbox", name="Notification title", exact=True)
    field.scroll_into_view_if_needed()
    page.keyboard.press("Tab")
    field.fill("Deployment ready")
    expect(field).to_have_value("Deployment ready")


def page_about(page: Page) -> None:
    """The page's identity and captured diagnostics in the menu's inspection dialog."""
    page.locator(".lf-fp-leaf").click()
    page.locator('.lf-fp-item[data-lf-row="inspection"]').click()
    expect(page.locator(".lf-inspection-dialog")).to_contain_text(
        re.compile(r"Source captured for r\d+")
    )


def panel_leaf(page: Page) -> None:
    """The floating panel's leaf, which opens the page's menu, with its keyboard focus
    paint."""
    page.keyboard.press("Tab")
    page.locator(".lf-fp-leaf").focus()


def panel_status_hover(page: Page) -> None:
    """The expanded panel while the pointer rests over its leaf."""
    page.locator(".lf-fp-leaf").hover()


def open_thread(page: Page, key: str) -> None:
    """The thread `key`, opened from Threads in the floating panel's view."""
    go_to_threads(page)
    page.locator(f'.lf-fp-thread[data-lf-key="{key}"]').click()
    expect(page.locator(f"{panel_view('thread')} .lf-msg").first).to_be_visible()


def floating_thread(page: Page) -> None:
    """The floating panel with a thread opened from Threads: the thread's title over
    its view, and under it, on the row, the way back, Show on page, Resolve and Close."""
    go_to_threads(page)
    page.locator(".lf-fp-thread", has_text="One reconnect in forty").click()
    expect(page.locator(panel_view("thread"))).to_be_visible()


def detached_thread(page: Page) -> None:
    """A thread whose passage a revision took out, opened from Threads: its quote,
    saying it is not in the latest version, over its messages, and no way to the page."""
    go_to_threads(page)
    page.locator(".lf-fp-thread", has_text="Old release plan").click()
    expect(page.locator(f"{panel_view('thread')} .lf-thread-quote")).to_be_visible()


def thread_code_copy(page: Page) -> None:
    """A command in an agent's reply, with its source copy control revealed."""
    as_agent(
        "thread",
        "reply",
        "7b3e0a41",
        "--text",
        "Run this command:\n\n```sh\necho hello\n```\n\nThen continue.",
    )
    floating_thread(page)
    page.locator(f"{panel_view('thread')} pre").hover()


def floating_thread_unread(page: Page) -> None:
    """The same thread holding a reply too long for its view to show whole, which stays
    unread, so Next unread stands on the view's head line."""
    as_agent(
        "thread",
        "reply",
        "7b3e0a41",
        "--text",
        "The resend recovers every one of them. "
        + "The queue holds each edit until the server confirms it. " * 40,
    )
    floating_thread(page)
    expect(
        page.locator(".lf-fp-head").get_by_role("button", name="Next unread")
    ).to_be_visible()


def panel_new_reply(page: Page) -> None:
    """The same thread after the user's own turn, with the agent's answer to it too long
    for the view, arrived below the fold behind New reply."""
    floating_thread(page)
    view = page.locator(panel_view("thread"))
    messages = view.locator(".lf-msg")
    sent = messages.count() + 1
    page.locator(".lf-fp-field leaf-text").click()
    page.keyboard.insert_text("And over the weekend?")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(messages).to_have_count(sent)
    settle(page)
    answer_the_turn()
    expect(view.get_by_role("button", name="New reply")).to_be_visible()


def answer_the_turn() -> None:
    """The agent answers the user's turn, too long for any box, through the delivery
    that hands it over."""
    served = served_page.get()
    delivery = json.loads(served.leaf("wait", str(served.directory)).stdout)

    def refs(node):
        if isinstance(node, dict):
            if isinstance(node.get("answer"), dict) and "ref" in node["answer"]:
                yield node["answer"]["ref"]
            for value in node.values():
                yield from refs(value)
        elif isinstance(node, list):
            for value in node:
                yield from refs(value)

    served.leaf(
        "thread",
        "reply",
        next(refs(delivery)),
        "--done",
        "--text",
        "It would. " + "Someone stays on call through Sunday, and Monday too. " * 80,
    )


def plan_head(page: Page) -> None:
    """On the agent's tab with the agent's plan disclosed from its head at the view's
    foot, one of its steps waiting on the user."""
    as_agent(
        "task",
        "plan",
        "--text",
        '[{"depth": 0, "title": "Ship the resend", "state": "working"},'
        ' {"depth": 1, "title": "Reproduce the stall", "state": "done"},'
        ' {"depth": 1, "item": "widget:off-release"},'
        ' {"depth": 1, "title": "Write the release note", "state": "open"}]',
    )
    wait_until_ready(page, PageClient(served_page.get().address).state())
    on_agent(page)
    page.locator(".lf-fp-plan-head").click()
    expect(page.locator(".lf-fp-plan")).to_be_visible()


def reaction_palette(page: Page) -> None:
    """A reply's reactions in the floating panel's thread, the palette opened from the
    strip's trigger, none in force."""
    floating_thread(page)
    message = page.locator(f"{panel_view('thread')} .lf-msg:has(.lf-react-strip)")
    message.first.hover()
    message.first.locator(".lf-react-trigger").click()
    expect(message.first.locator(".lf-react-palette:popover-open")).to_be_visible()


def reaction_pressed(page: Page) -> None:
    """The same reply once the user has added its first reaction, which the closed
    strip keeps in sight in the accent, under the pointer and away from it."""
    reaction_palette(page)
    strip = page.locator(f"{panel_view('thread')} .lf-react-strip").first
    strip.locator(".lf-react").first.click()
    expect(strip.locator('.lf-react[aria-pressed="true"]')).to_have_count(1)
    # A press beside the palette puts it away, as any popover is.
    page.locator(f"{panel_view('thread')} .lf-msg-body").first.click()
    expect(strip.locator(".lf-react-palette:popover-open")).to_have_count(0)
    settle(page)


MARGIN_SUGGESTION = '.lf-margin-cluster[data-lf-margin-for="rn-sug-dry"]'


def margin_reaction_choices(page: Page) -> None:
    """A suggestion's margin row with the reactions `e` raises from its Accept, each a
    margin entry."""
    row = page.locator(MARGIN_SUGGESTION)
    row.locator('[data-lf-margin-entry-key="accept"]').focus()
    page.keyboard.press("e")
    expect(
        row.locator('[data-lf-margin-entry-owner="responses"]:visible')
    ).to_have_count(6)
    settle(page)


def margin_reaction_mark(page: Page) -> None:
    """The same row once a reaction stands on its target, unfolded to show the
    reaction's own margin entry beside Reject."""
    margin_reaction_choices(page)
    row = page.locator(MARGIN_SUGGESTION)
    row.locator('[data-lf-margin-entry-owner="responses"]:visible').first.click()
    mark = row.locator('[data-lf-margin-entry-owner="reactions"]')
    expect(mark).to_have_count(1)
    row.locator(".lf-margin-more").click()
    expect(mark).to_be_visible()
    page.mouse.move(0, 0)
    settle(page)


def floating_thread_retitled(page: Page) -> None:
    """The same thread once its opening message is rewritten short, so its title is far
    narrower than the view it names."""
    floating_thread(page)
    page.locator(f"{panel_view('thread')} .lf-msg-body").first.dblclick()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Ship it?")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_have_text("Ship it?")


def playground_choice(page: Page) -> None:
    """Keyboard focus on the choice's whole labelled hit target."""
    page.keyboard.press("Tab")
    radio = page.locator("lf-playground input[type=radio]").first
    radio.scroll_into_view_if_needed()
    radio.focus()


def motion_controls(page: Page) -> None:
    """Focus the motion's native speed field beside its playback controls."""
    select = page.locator(".lf-motion-speed select").first
    select.scroll_into_view_if_needed()
    select.focus()


def timeline_steps(page: Page) -> None:
    """A timeline's Previous and Next beside its position, above its lanes."""
    page.locator("#race .lf-timeline-controls").scroll_into_view_if_needed()


def card_by_pointer(page: Page) -> None:
    """The first margin card, opened by a click on its marker."""
    open_card(page, page.locator(".lf-margin-marker").first)


def control_preview(page: Page) -> None:
    """The first margin card's Resolve under a resting pointer, whose preview names its
    word and the key that presses it (preview.js). A runtime without previews shows
    the card alone."""
    card_by_pointer(page)
    page.locator(".lf-margin-preview .lf-resolve").hover()
    page.wait_for_function(
        """() => {
          const tip = document.getElementById('lf-preview');
          return !tip || tip.matches(':popover-open');
        }"""
    )
    settle(page)


# Longer than a preview's dwell (preview.js, `DWELL`), so a runtime that previews what
# the pointer rests on has shown it, and one that doesn't shows the page as it stands.
PREVIEW_DWELL_MS = 400


def word_lines(page: Page, words: str) -> list[dict]:
    """The boxes of the first `words` the page's text holds within one text node, one
    for each line they lie on, with their paragraph scrolled to the window's middle."""
    return page.evaluate(
        """(words) => {
          const walker = document.createTreeWalker(document.querySelector('main'),
            NodeFilter.SHOW_TEXT);
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const at = node.data.indexOf(words);
            if (at < 0) continue;
            node.parentElement.scrollIntoView({block: 'center', behavior: 'instant'});
            const range = document.createRange();
            range.setStart(node, at);
            range.setEnd(node, at + words.length);
            return [...range.getClientRects()].map((box) => box.toJSON());
          }
        }""",
        words,
    )


STOP_PASSAGE = "The trusted supervisor owns shutdown."


def thread_preview(page: Page) -> None:
    """The open thread's passage mark under a resting pointer, which previews who wrote
    its last message and when, that message's opening line and where the thread stands
    (thread/messages.js, `threadPreview`)."""
    line = word_lines(page, STOP_PASSAGE)[0]
    page.mouse.move(line["left"] - 20, line["top"] - 20)
    page.mouse.move(line["left"] + 10, line["top"] + line["height"] / 2, steps=3)
    page.wait_for_timeout(PREVIEW_DWELL_MS)
    settle(page)


def passage_reaction(page: Page) -> None:
    """A passage the user reacted to, selected by pointer and answered with `e` and
    `1`, in the item below the stop thread's commented passage, so a reaction's mark
    and a comment's stand at rest side by side."""
    lines = word_lines(page, "reject symlink path components")
    first, last = lines[0], lines[-1]
    page.mouse.move(first["left"] + 1, first["top"] + first["height"] / 2)
    page.mouse.down()
    page.mouse.move(last["right"] - 1, last["top"] + last["height"] / 2, steps=8)
    page.mouse.up()
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("e")
    page.keyboard.press("1")
    page.wait_for_function("() => (CSS.highlights.get('lf-react')?.size ?? 0) > 0")
    page.keyboard.press("Escape")
    page.mouse.move(0, 0)
    word_lines(page, STOP_PASSAGE)
    settle(page)


def age_preview(page: Page) -> None:
    """The first margin card's first age under a resting pointer, which previews the clock
    time behind it in the reader's zone (presence.js, `agePreview`)."""
    card_by_pointer(page)
    age = page.locator(".lf-margin-preview .lf-msg-head time").first
    box = age.bounding_box()
    assert box, "the card shows no age"
    # The card may open with the age under the pointer, which reads nothing until the
    # pointer moves.
    page.mouse.move(box["x"] - 30, box["y"] + box["height"] + 30)
    age.hover()
    page.wait_for_timeout(PREVIEW_DWELL_MS)
    settle(page)


def link_preview(page: Page) -> None:
    """The gallery's link to its session table under a resting pointer, whose preview
    shows the table's caption, its first rows and the thread about it
    (place-preview.js). A runtime without link previews shows the link alone, once a
    second has passed without one."""
    page.locator("#bg-link-previews").evaluate(
        "el => el.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    scroll_settled(page)
    page.locator("#bg-link-table").hover()
    page.evaluate(
        """() => new Promise((done) => {
          const tip = document.getElementById('lf-preview');
          const until = performance.now() + 1000;
          const look = () =>
            !tip || tip.matches(':popover-open') || performance.now() > until
              ? done()
              : requestAnimationFrame(look);
          look();
        })"""
    )
    settle(page)


def open_card(page: Page, marker: Locator) -> float:
    """The margin card `marker` opens, by a click on it, returning the page's scroll
    just before the click. The margin is fixed to the window and anchored to the page,
    so Playwright's scroll into view leaves a marker below the window where it is: the
    page scrolls it up instead."""
    marker.evaluate(
        "m => { const box = m.getBoundingClientRect();"
        " if (box.top < 0 || box.bottom > innerHeight)"
        " scrollBy(0, box.top - innerHeight / 3); }"
    )
    settle(page)
    before = page.evaluate("scrollY")
    marker.click()
    page.wait_for_function(OPEN_CARD)
    return before


def thread_by_marker(page: Page) -> None:
    """The plan's stop thread, opened by a press on its marker: a margin card on a
    window with room for the rail, the floating panel's view of it on a phone."""
    marker = page.locator('[data-lf-margin-for="plan-stop"] .lf-margin-marker')
    marker.evaluate("m => scrollBy(0, m.getBoundingClientRect().top - innerHeight / 3)")
    settle(page)
    marker.click()
    page.wait_for_function(
        "() => document.activeElement?.closest('.lf-margin-preview, .lf-fp-opened')"
    )
    page.mouse.move(0, 0)


RESYNC_MARKER = '[data-lf-margin-for="off-t-resync"] .lf-margin-marker'


def long_reply(root: str) -> None:
    """An agent's reply in `root`'s thread, too long to read whole in a card, so it
    stands unread."""
    as_agent(
        "thread",
        "reply",
        root,
        "--text",
        "The resend recovers every one of them. "
        + "The queue holds each edit until the server confirms it. " * 40,
    )


def card_next_unread(page: Page) -> None:
    """A margin card opened on a reply too long for it to show whole, which stays
    unread, so Next unread stands on its head line."""
    long_reply("7b3e0a41")
    open_card(page, page.locator(RESYNC_MARKER))
    settle(page)


def card_new_reply(page: Page) -> None:
    """A margin card after the user's own turn, read back up its transcript, with the
    agent's answer arrived past the transcript's foot behind New reply."""
    long_reply("7b3e0a41")
    open_card(page, page.locator(RESYNC_MARKER))
    card = page.locator(".lf-margin-preview")
    messages = card.locator(".lf-msg")
    sent = messages.count() + 1
    card.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.insert_text("And over the weekend?")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(messages).to_have_count(sent)
    settle(page)
    card.locator(".lf-thread-transcript").hover()
    page.mouse.wheel(0, -3000)
    page.wait_for_function(
        "() => document.querySelector('.lf-margin-preview .lf-thread-transcript')"
        ".scrollTop < 1000"
    )
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    answer_the_turn()
    expect(messages).to_have_count(sent + 1)
    settle(page)


def card_cluster_resolved(page: Page) -> None:
    """The second of three threads at one passage resolved in its card, which moves on
    to the thread after it."""
    client = PageClient(served_page.get().address)
    for word in ("First", "Second", "Third"):
        client.post(
            {
                "kind": "comment",
                "attempt": f"stills-cluster-{word}",
                "text": f"{word}: worth a second look.",
                "anchor": {"section": "plan-current"},
            }
        )
    wait_until_ready(page, client.state(), through="state")
    open_card(
        page, page.locator('[data-lf-margin-for="plan-current"] .lf-margin-marker')
    )
    card = page.locator(".lf-margin-preview")
    card.get_by_role("button", name="Next thread").click()
    expect(card.locator(".lf-margin-preview-position")).to_have_text("2/3")
    # Whichever thread takes its place, the card stands on two.
    card.get_by_role("button", name="Resolve thread", exact=True).click()
    expect(card.locator(".lf-margin-preview-position")).to_have_text(
        re.compile(r"^\d/2$")
    )
    settle(page)


def card_next_unread_cluster(page: Page) -> None:
    """The same card with a second thread at its passage, so Next unread shares the head
    line with Previous and Next."""
    client = PageClient(served_page.get().address)
    client.post(
        {
            "kind": "comment",
            "attempt": "stills-resync-second",
            "text": "And does the resend keep their order?",
            "anchor": {
                "section": "off-t-resync",
                "quote": "One reconnect in about 40",
                "suffix": ". Nothing is lost — the ",
            },
        }
    )
    wait_until_ready(page, client.state(), through="state")
    card_next_unread(page)


def card_answer_at_cap(page: Page) -> None:
    """A margin card at its cap, the user at its end after their own turn, with an answer
    too long to show arrived: their turn stays in sight above New reply."""
    long_reply("7b3e0a41")
    open_card(page, page.locator(RESYNC_MARKER))
    card = page.locator(".lf-margin-preview")
    messages = card.locator(".lf-msg")
    sent = messages.count() + 1
    card.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.insert_text("And over the weekend?")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(messages).to_have_count(sent)
    settle(page)
    answer_the_turn()
    expect(messages).to_have_count(sent + 1)
    settle(page)


def card_by_keyboard(page: Page) -> None:
    """The first margin card, opened by `t`, the keyboard's way to the next thread, so
    its thread holds a visible focus."""
    page.keyboard.press("t")
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-margin-preview .lf-page-thread')"
    )


def card_more_room(page: Page) -> None:
    """An overflowing conversation uses extra room without needing a complete fit."""
    page.set_viewport_size({"width": 1440, "height": 480})
    settle(page)
    card_by_pointer(page)
    settle(page)
    page.set_viewport_size({"width": 1440, "height": 600})


def card_reply_empty(page: Page) -> None:
    """The first margin card's empty reply, ready for typing or dictation."""
    card_by_keyboard(page)
    page.keyboard.press("Enter")
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-margin-preview leaf-text')"
    )


def card_rewrite_empty(page: Page) -> None:
    """The user's message in the first margin card, opened for a rewrite by ↑ from its
    empty reply and emptied, so the editor says only its hint and keys."""
    card_reply_empty(page)
    page.keyboard.press("ArrowUp")
    page.wait_for_function(
        "() => document.activeElement?.closest('.lf-msg')"
        " && !document.activeElement.closest('.lf-thread-reply')"
    )
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Delete")


def panel_reply_empty(page: Page) -> None:
    """The last open thread, opened from Threads in the floating panel, with the caret
    in its empty reply."""
    go_to_threads(page)
    page.locator(".lf-fp-thread:not([data-lf-resolved])").last.click()
    expect(page.locator(panel_view("thread"))).to_be_visible()
    page.locator(".lf-fp-field leaf-text").click()
    expect(page.locator(".lf-fp-field leaf-text")).to_be_focused()


def panel_dictating(page: Page) -> None:
    """The floating panel's field while Dictate listens. Headless has no microphone, so
    the button takes the state a listening dictation renders on it."""
    page.locator(".lf-fp-field leaf-text").click()
    dictate = page.locator(".lf-fp-field .lf-compose-dictate")
    expect(dictate).to_be_visible()
    dictate.evaluate(
        """button => {
          button.setAttribute("aria-pressed", "true");
          button.dataset.lfDictation = "listening";
        }"""
    )
    settle(page)


def comment_on(section: str) -> None:
    """A comment the user left on `section`, posted as another of their tabs would."""
    PageClient(served_page.get().address).post(
        {
            "kind": "comment",
            "attempt": f"stills-proxy-{section}",
            "text": "Worth a second look.",
            "anchor": {"section": section},
        }
    )


def focus_proxy(page: Page, focus: str, *args: str) -> None:
    """Focus the proxy `focus` finds, with the keyboard's modality, as a screen reader
    moving to it focuses it: a proxy on the details shelf is no Tab stop
    (control-faces.js, `proxy`)."""
    page.keyboard.press("Tab")
    page.evaluate(f"([...args]) => ({focus})(...args)", list(args))
    page.wait_for_function(
        "() => document.activeElement?.closest('.lf-details-shelf, lf-gloss')"
    )
    settle(page)


# The comment note the element `id` names as its details, once it has one.
NOTE_OF = """id => {
  const notes = document.getElementById(id).ariaDetailsElements ?? [];
  const note = notes.find((node) => node.matches('.lf-mark-note'));
  if (!note) throw new Error(`#${id} names no comment note`);
  note.focus();
}"""
# The response proxy whose words include `label`, or the first of its group's, its
# drawing's own.
PROXY_OF = """(label, whole) => {
  const proxy = [...document.querySelectorAll('.lf-visual-action')].find((node) =>
    node.textContent.includes(label),
  );
  (whole ? proxy.parentElement.querySelector('.lf-visual-action') : proxy).focus();
}"""


def proxy_note_paragraph(page: Page) -> None:
    """A paragraph's comment note focused, which rings the paragraph."""
    comment_on("pr-approval-premise")
    page.wait_for_function(
        "() => document.getElementById('pr-approval-premise').ariaDetailsElements?.length"
    )
    focus_proxy(page, NOTE_OF, "pr-approval-premise")


def proxy_note_row(page: Page) -> None:
    """A table row's comment note focused, which rings the row."""
    comment_on("pr-focus-latency")
    page.wait_for_function(
        "() => document.getElementById('pr-focus-latency').ariaDetailsElements?.length"
    )
    focus_proxy(page, NOTE_OF, "pr-focus-latency")


def proxy_note_own_annotations(page: Page) -> None:
    """A paragraph's comment note focused on a page that presents its own annotations,
    where no annotation overlay is loaded, which still rings the paragraph."""
    comment_on("rollout-plan")
    page.wait_for_function(
        "() => document.getElementById('rollout-plan').ariaDetailsElements?.length"
    )
    focus_proxy(page, NOTE_OF, "rollout-plan")


def proxy_drawing(page: Page) -> None:
    """A diagram's own response proxy focused, which rings the diagram."""
    page.get_by_role("tab", name="Behavior diff").click()
    focus_proxy(page, PROXY_OF, "PreparedDiff", "whole")


def proxy_part(page: Page) -> None:
    """The response proxy of one of a diagram's declared parts focused, which rings the
    part in its own contour."""
    page.get_by_role("tab", name="Behavior diff").click()
    focus_proxy(page, PROXY_OF, "PreparedDiff")


def proxy_gloss(page: Page) -> None:
    """A gloss's proxy focused, which rings its phrase."""
    focus_proxy(
        page, "() => document.querySelector('#pr-focus-safety .lf-gloss-mark').focus()"
    )


def option_empty(page: Page) -> None:
    """An option list's empty one-line add field, focused."""
    field = page.locator(".lf-another leaf-text").first
    field.scroll_into_view_if_needed()
    field.click()
    expect(field).to_be_focused()


def card_reply(page: Page) -> None:
    """The first margin card with a reply being typed."""
    card_reply_empty(page)
    page.keyboard.insert_text("A reply being drafted, long enough to wrap onto a line")


def card_reply_photo(page: Page) -> None:
    """The first margin card with a screenshot pasted into its reply, standing over
    the field."""
    card_reply(page)
    paste_screenshot(
        page, page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
    )


def card_aging(page: Page) -> None:
    """An open card follows the clock while its reply is being drafted."""
    card_reply(page)
    timestamp = page.locator(".lf-margin-preview time").first.get_attribute("datetime")
    assert timestamp is not None
    now = datetime.fromisoformat(timestamp) + timedelta(seconds=30)

    def aged_state(route):
        response = route.fetch()
        state = response.json()
        state["now"] = now.isoformat()
        route.fulfill(response=response, json=state)

    page.route("**/api/state*", aged_state)
    for seconds in (30, 60):
        now = datetime.fromisoformat(timestamp) + timedelta(seconds=seconds)
        page.clock.set_fixed_time(now)
        page.evaluate("""() => {
          window.__lfStillTicked = false;
          document.addEventListener('lf-tick', () => { window.__lfStillTicked = true; },
                                    {once: true});
        }""")
        page.wait_for_function("() => window.__lfStillTicked")
        settle(page)


def card_reply_large(page: Page) -> None:
    """A pasted reply exhausting the room below the thread, with its caret at the end."""
    card_reply(page)
    page.keyboard.insert_text("\n" + "\n".join(f"Reply line {n}" for n in range(40)))


def card_reply_resolved(page: Page) -> None:
    """The user resolves a thread while its unsent reply has words."""
    card_reply(page)
    page.locator(".lf-margin-preview").get_by_role(
        "button", name="Resolve thread", exact=True
    ).click()


def section_ring_by_keyboard(page: Page) -> None:
    """A thread on a whole section, opened and resolved by keyboard, which hands focus
    back to the section and rings it: where the ring stands against the section's
    heading, which no text in a still otherwise shows."""
    as_agent(
        "thread",
        "create",
        "--section",
        "plan-implementation",
        "--text",
        "Is this order right?",
    )
    marker = page.locator(
        '[data-lf-margin-for="plan-implementation"] .lf-margin-marker'
    )
    marker.wait_for()
    page.keyboard.press("Tab")  # keyboard modality, so focus is drawn
    marker.focus()
    page.keyboard.press("Enter")
    resolve = page.locator(".lf-margin-preview").get_by_role(
        "button", name="Resolve thread", exact=True
    )
    resolve.focus()
    page.keyboard.press("Enter")
    page.wait_for_function("() => document.activeElement?.id === 'plan-implementation'")


def card_reply_resolved_elsewhere(page: Page) -> None:
    """An agent resolves the thread while the user keeps writing in its margin card."""
    card_reply(page)
    card = page.locator(".lf-margin-preview .lf-page-thread")
    root = card.get_attribute("data-lf-thread")
    assert root
    as_agent("thread", "resolve", root)
    expect(card.locator(".lf-reopen")).to_be_visible()


def as_agent(command: str, verb: str, *args: str) -> None:
    """Run `leaf COMMAND VERB PAGE ARGS` as the agent on the page being served, with
    its arm's launcher."""
    served = served_page.get()
    served.leaf(command, verb, str(served.directory), *args)


def held_news(page: Page, thread: Locator, *, drafting: bool = True) -> None:
    """News arriving in `thread`, while the user drafts a reply there or reads beside it:
    the agent's reply and the user's own message from another tab, which the thread
    holds behind its notice (held-news.js)."""
    if drafting:
        thread.get_by_role("textbox", name="Reply", exact=True).click()
        page.keyboard.insert_text("Drafting a reply while the news arrives")
    root = thread.get_attribute("data-lf-thread")
    assert root
    as_agent("thread", "reply", root, "--text", "That one goes first.")
    notice = thread.locator(".lf-thread-news")
    expect(notice).to_have_attribute("title", "1 new reply")
    PageClient(served_page.get().address).post(
        {
            "kind": "reply",
            "parent": root,
            "attempt": "stills-held-news-other-tab",
            "text": "Sent from my other tab.",
        }
    )
    expect(notice).to_have_attribute("title", "1 new reply · 1 new message")


def card_held_news(page: Page) -> None:
    """A margin card holding a reply and a message from another tab while the user
    drafts a reply in it."""
    open_card(page, page.locator('[data-lf-margin-for="plan-stop"] .lf-margin-marker'))
    held_news(page, page.locator(".lf-margin-preview .lf-page-thread"))


def card_held_step(page: Page) -> None:
    """A margin card holding the agent's progress step while the user drafts a reply
    in it, which its notice doesn't say (held-news.js)."""
    open_card(page, page.locator('[data-lf-margin-for="plan-stop"] .lf-margin-marker'))
    thread = page.locator(".lf-margin-preview .lf-page-thread")
    thread.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.insert_text("Drafting a reply while the agent works")
    root = thread.get_attribute("data-lf-thread")
    assert root
    as_agent("thread", "reply", root, "--ephemeral", "--text", "Checking the stop.")
    state = PageClient(served_page.get().address).state()
    wait_until_ready(page, state, through="state")


def card_after_interjection(page: Page) -> None:
    """An arriving answer grows a card after Send has fitted its reply against the window."""
    card_held_step(page)
    card = page.locator(".lf-margin-preview")
    card.get_by_role("textbox", name="Reply", exact=True).press("Enter")
    # Messages are picked by their words, which every arm's runtime draws alike.
    reply = card.locator(
        ".lf-msg", has_text="Drafting a reply while the agent works"
    ).last
    expect(reply).to_be_visible()
    expect(reply).not_to_have_attribute("aria-busy", "true")
    settle(page)
    served = served_page.get()
    delivery = json.loads(served.leaf("wait", str(served.directory), timeout=15).stdout)
    sent = reply.get_attribute("data-lf-event")
    reference = next(
        event["answer"]["ref"]
        for batch in delivery["batches"]
        for event in batch["events"]
        if event["id"] == sent
    )
    served.leaf("delivery", "ack", delivery["id"])
    served.leaf(
        "thread",
        "reply",
        reference,
        "--ephemeral",
        "--text",
        "The answer continues with the detail requested in the interjection. " * 5,
    )
    expect(
        card.locator(".lf-msg", has_text="The answer continues").last
    ).to_be_visible()


def seat_held_news(page: Page) -> None:
    """A seat's thread holding a reply and a message from another tab while the user
    reads beside it: the agent's question on a goal, which a reload draws in place. A
    thread the user drafts in draws its news at once (held-news.js)."""
    as_agent(
        "thread", "create", "--section", "goal-parser", "--text", "Which worker first?"
    )
    load(page, served_page.get().address)
    thread = page.locator("#goal-parser .lf-page-thread")
    thread.scroll_into_view_if_needed()
    held_news(page, thread, drafting=False)


def option_picked(page: Page) -> None:
    """The panel's row just after the plan's rollout option is picked and admitted,
    which the live region alone announces."""
    option = page.locator("#plan-admin")
    option.scroll_into_view_if_needed()
    option.click()
    expect(page.locator(".lf-live")).to_contain_text("Chose “")


def option_answered(page: Page) -> None:
    """The panel's row once the server has read a pick that leaves more On Me, where the
    field's end offers the next item On Me lists."""
    page.locator("#off-release-hold").click()
    expect(page.locator(".lf-fp-on-user .lf-fp-num")).to_have_text("2")


def panel_resolved(page: Page) -> None:
    """The panel's row just after Resolve in its view of a thread moves the user on to
    the next one, the field saying which thread was resolved and, at its end, the press
    the moment offers."""
    floating_thread(page)
    page.locator(panel_view("thread")).focus()
    page.keyboard.press("r")
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-lf-says", "notice"
    )


def panel_draw_mode(page: Page) -> None:
    """The panel's row in Draw mode, the field naming the mode, with its way out."""
    page.keyboard.press("w")
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-lf-says", "stance"
    )


def panel_selection(page: Page) -> None:
    """The panel's row quoting words a script selected on the page, which a press on the
    field comments on."""
    page.locator("main p").first.evaluate(
        """p => {
          const text = [...p.childNodes].find(
            (node) => node.nodeType === Node.TEXT_NODE && node.length > 30,
          );
          const range = document.createRange();
          range.setStart(text, 0);
          range.setEnd(text, Math.min(40, text.length));
          getSelection().removeAllRanges();
          getSelection().addRange(range);
        }"""
    )
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-lf-says", "selection"
    )


def option_references(page: Page) -> None:
    """The patch decision, whose two options both name the stall block above them."""
    page.locator("#off-workaround-review").scroll_into_view_if_needed()


def on_me(page: Page) -> None:
    """On Me, opened from the floating panel's On Me mark."""
    page.locator(".lf-fp-on-user").click()
    expect(page.locator(panel_view("queue"))).to_be_visible()


def on_me_question(page: Page) -> None:
    """On Me opened on the card of a question the agent asked in a thread with
    `--obligation`, its whole words over the card's Reply."""
    question = (
        "Can you review the change or name a reviewer, then merge it after checking "
        "the build?"
    )
    as_agent(
        "thread",
        "create",
        "--section",
        "plan-context",
        "--text",
        question,
        "--obligation",
    )
    page.reload()
    wait_until_ready(page, PageClient(served_page.get().address).state())
    on_me(page)
    page.locator(".lf-fp-on-item", has_text=question).scroll_into_view_if_needed()


def on_me_choice(page: Page) -> None:
    """A described choice card in On Me, before answering."""
    on_me(page)
    card = page.locator(
        '.lf-fp-on-item[data-lf-obligation-id="widget:decision-dedupe"]'
    )
    card.scroll_into_view_if_needed()


def on_me_choice_answered(page: Page) -> None:
    """The result and Undo replacing a described choice on its retained card."""
    on_me_choice(page)
    card = page.locator(
        '.lf-fp-on-item[data-lf-obligation-id="widget:decision-dedupe"]'
    )
    card.locator(".lf-fp-answer").first.click()
    expect(card.locator(".lf-fp-said")).to_contain_text("Answered:")


def on_agent(page: Page) -> None:
    """The On view turned to the agent's tab."""
    on_me(page)
    page.locator(".lf-fp-filters button").filter(
        has_text=re.compile(r"^\s*On (?!Me\b)")
    ).first.click()
    expect(page.locator(panel_view("queue"))).to_be_visible()


def threads_scrolled(page: Page) -> None:
    """Threads scrolled in a short window, with Open's band stuck over its rows."""
    go_to_threads(page)
    page.locator(panel_view("threads")).evaluate("view => { view.scrollTop = 36; }")
    settle(page)


def threads_returning(page: Page) -> None:
    """Threads as the user reads it while the agent's reply reopens a resolved thread,
    whose open row would lead the list, and the agent starts a thread on the page."""
    returning = "7b3e0a41"
    as_agent("thread", "resolve", returning)
    # Threads opens on the resolve, which the list would otherwise hold as news.
    wait_until_ready(page, PageClient(served_page.get().address).state())
    go_to_threads(page)
    count = page.locator(".lf-fp-filters button", has_text="Threads").locator(
        ".lf-fp-count"
    )
    opened = int(count.inner_text())
    as_agent(
        "thread", "reply", returning, "--text", "The resend covers a cold start too."
    )
    as_agent("thread", "create", "--text", "Should the beta notes mention the resend?")
    expect(count).to_have_text(str(opened + 2))
    settle(page)


def call_tree(page: Page) -> None:
    """The CallDiff root and its unchanged landmarks beside added and removed calls."""
    page.get_by_role("tab", name="CallDiff", exact=True).click()
    widget = page.locator("#pr-call-diagram")
    widget.scroll_into_view_if_needed()
    widget.locator(".lf-call-root-location a").first.focus()


def diagram_flow(page: Page) -> None:
    """The unified-diff flow with its authored added and removed node colors."""
    page.locator("#pr-flow-diagram").scroll_into_view_if_needed()


def diagram_shape_comment(page: Page) -> None:
    """A comment on one named diagram box, rather than the whole drawing."""
    diagram_flow(page)
    page.locator('#pr-flow-diagram g[data-id="Unified"]').click(modifiers=["Alt"])
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "§ diagram · + unified diff"
    )


def page_search(page: Page) -> None:
    """A focused page query and its match count inside the search frame."""
    page.keyboard.press("Tab")
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("review")


def accepted_page_search(page: Page) -> None:
    """The current match remains named after Return accepts the query."""
    page_search(page)
    page.keyboard.press("Enter")
    expect(page.get_by_role("searchbox", name="Search page text")).not_to_be_visible()


def selected_passage_responses(page: Page) -> None:
    """Other responses beside a comment on a selected search match."""
    page_search(page)
    expect(page.get_by_role("button", name="Next match", exact=True)).to_be_enabled()
    page.keyboard.press("Enter")
    expect(page.get_by_role("searchbox", name="Search page text")).not_to_be_visible()
    page.keyboard.press("c")
    page.keyboard.press("Tab")
    page.keyboard.press("e")
    expect(page.get_by_role("button", name="Suggest", exact=True)).to_be_visible()


def command_reference(page: Page) -> None:
    """The command reference, its sections at rest."""
    page.keyboard.press("Tab")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference[open]")).to_be_visible()


def command_reference_search(page: Page) -> None:
    """Help's focused query above its filtered command results."""
    command_reference(page)
    page.get_by_role("combobox", name="Search commands").fill("comment")


def command_reference_scrolled(page: Page) -> None:
    """The command reference scrolled into a section, whose band stands stuck."""
    command_reference(page)
    page.locator(".lf-command-reference-results").evaluate(
        "list => { list.scrollTop = 420; }"
    )
    settle(page)


def page_map(page: Page) -> None:
    """The Page Map over a plan's threads, questions and controls: its title, its
    groups' headings and its rows' ends."""
    page.keyboard.press("Tab")
    page.keyboard.press("g")
    page.keyboard.press("Shift+P")
    expect(page.locator(".lf-page-map-dialog[open]")).to_be_visible()


def page_map_scrolled(page: Page) -> None:
    """The Page Map scrolled into a group, whose band stands stuck."""
    page_map(page)
    page.locator(".lf-page-map-list").evaluate("list => { list.scrollTop = 100; }")
    settle(page)


def retained_quote(page: Page) -> None:
    """A thread whose passage the page no longer holds, opened in its sample's
    floating panel, where its retained quotation reads once the panel draws one."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Threads", exact=True
    ).click()
    sample = page.locator("#bg-retained-quote-sample")
    sample.scroll_into_view_if_needed()
    child = sample.frame_locator("iframe")
    go_to_threads(page, child)
    child.locator('.lf-fp-thread[data-lf-key="bg-retained-quote-thread"]').click()
    expect(child.locator(f"{panel_view('thread')} .lf-msg").first).to_be_visible()


def retained_quote_full(page: Page) -> None:
    """The same original words opened locally. Full quote stands with the quote's first
    paint, before the view has finished arriving; the click waits until the reply has
    been read where it stood, as a reader's would, since opening the quote at once
    pushes the reply out of view unread and offers Next unread."""
    retained_quote(page)
    child = page.locator("#bg-retained-quote-sample").frame_locator("iframe")
    expect(child.locator(f"{panel_view('thread')} .lf-msg-new")).to_have_count(0)
    full = child.get_by_role("button", name="Full quote", exact=True)
    full.click()
    expect(full).to_have_attribute("aria-expanded", "true")


def progress_messages(page: Page) -> None:
    """The completed answer beside its interim checks, in the floating panel's view of
    the thread."""
    open_thread(page, "bg-progress-question")


def screenshot_comparison(page: Page) -> None:
    """Reach the comparison rail's standalone endpoint controls."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    # Anchor the unchanged guide, so a taller rail does not recenter the entire capture.
    page.locator("#bg-shot-guide").scroll_into_view_if_needed()


def screenshot_pair(page: Page) -> None:
    """Show both images inside the comparison's shared allocation."""
    screenshot_comparison(page)
    shot = page.locator("#bg-shot")
    shot.locator(".lf-shot-views").get_by_text("Pair", exact=True).click()
    shot.locator(".lf-shot-toolbar").evaluate(
        "node => node.scrollIntoView({block: 'start'})"
    )


def screenshot_slider_before(page: Page) -> None:
    """One source fills the slider while change outlines locate its evidence."""
    screenshot_comparison(page)
    shot = page.locator("#bg-shot")
    shot.evaluate("async node => await node.difference")
    shot.locator(".lf-shot-views").get_by_text("Slider", exact=True).click()
    divider = shot.get_by_role("scrollbar")
    divider.focus()
    page.keyboard.press("End")
    shot.get_by_role("button", name="Image options").click()
    shot.get_by_role("checkbox", name="Outline changes", exact=True).check()
    page.keyboard.press("Escape")
    shot.scroll_into_view_if_needed()


def screenshot_pixels(page: Page) -> None:
    """Pixel evidence occupies the image frame without a separate legend row."""
    screenshot_comparison(page)
    shot = page.locator("#bg-shot")
    shot.locator(".lf-shot-views").get_by_text("Pixels", exact=True).click()


def screenshot_views_keyboard(page: Page) -> None:
    """The comparison's chosen view holding keyboard focus."""
    screenshot_comparison(page)
    page.locator("#bg-shot .lf-shot-views").get_by_text("Slider", exact=True).evaluate(
        "node => node.focus({focusVisible: true})"
    )
    page.keyboard.press("Shift")  # keyboard modality, which Chromium's focus reads


def dial_keyboard(page: Page) -> None:
    """The detail dial's chosen depth holding keyboard focus."""
    page.locator("lf-dial").get_by_text("Read", exact=True).evaluate(
        "node => node.focus({focusVisible: true})"
    )
    page.keyboard.press("Shift")  # keyboard modality, which Chromium's focus reads


def screenshot_view_hover(page: Page) -> None:
    """An unchosen view under the pointer, beside the chosen one."""
    screenshot_comparison(page)
    page.locator("#bg-shot .lf-shot-views").get_by_text("Pair", exact=True).hover()


def dial_press(page: Page) -> None:
    """An unchosen depth held down under the pointer, before it is chosen."""
    page.locator("lf-dial").get_by_text("Skim", exact=True).hover()
    page.mouse.down()


def screenshot_options(page: Page) -> None:
    """Image options keep the pixel color key beside the scale choices."""
    screenshot_comparison(page)
    shot = page.locator("#bg-shot")
    shot.locator(".lf-shot-scale").click()
    # Opening a popover may reveal a taller Pair differently from Slider.
    shot.locator(".lf-shot-toolbar").evaluate(
        "node => node.scrollIntoView({block: 'start'})"
    )
    shot.scroll_into_view_if_needed()


def image_in_page(page: Page) -> None:
    """An authored image in the reading flow, before its viewer opens."""
    page.get_by_role("tab", name="Threads", exact=True).click()
    page.locator("#bg-image-preview").scroll_into_view_if_needed()


def thread_picture(page: Page) -> None:
    """The gallery's pasted screenshot, a white page, in its message in the panel."""
    open_thread(page, "2be2443f0bb6cc49fc86b52f340e6073")
    picture = page.locator(f"{panel_view('thread')} .lf-message-media img").first
    picture.evaluate("image => image.decode()")
    picture.scroll_into_view_if_needed()


def image_preview(page: Page) -> None:
    """Inspect the gallery's pasted screenshot through the shared image viewer."""
    open_thread(page, "2be2443f0bb6cc49fc86b52f340e6073")
    page.locator(f"{panel_view('thread')} .lf-media-open").first.click()
    page.get_by_role("dialog", name="Image preview").wait_for(state="visible")


def panel_by_keyboard(page: Page) -> None:
    """Threads, opened by Go to Threads, with keyboard focus on its first row."""
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "selector => document.activeElement?.matches(selector)",
        arg=f"{panel_view('threads')} .lf-fp-thread",
    )


def composer_resting(page: Page) -> None:
    """An empty anchored comment opened by selecting a passage, without focus."""
    box = page.locator("#triage-lede").bounding_box()
    assert box is not None
    y = box["y"] + 10
    assert box is not None
    page.mouse.move(box["x"] + 2, y)
    page.mouse.down()
    assert box is not None
    page.mouse.move(box["x"] + 200, y, steps=8)
    page.mouse.up()
    # Under a finger a selection is offered in the floating panel's field, which quotes
    # it, rather than raising a field beside it. It arrives on a later frame, so the
    # pointer decides, not whether it is there yet.
    if page.evaluate("matchMedia('(pointer: coarse)').matches"):
        page.locator('.lf-fp-field leaf-text[data-lf-says="selection"]').click()


def composer_empty(page: Page) -> None:
    """An empty comment on a passage selected by pointer, with its field focused."""
    composer_resting(page)
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer leaf-text").focus()


def composer(page: Page) -> None:
    """A comment being typed on a passage selected by pointer."""
    composer_empty(page)
    page.keyboard.insert_text("A comment being drafted on the selected words")


def page_comment_empty(page: Page) -> None:
    """The floating panel's empty field, focused by `c` for a page comment, and its
    trailing action."""
    page.keyboard.press("c")
    expect(page.locator(".lf-fp-field leaf-text")).to_be_focused()


def page_comment_resting(page: Page) -> None:
    """The panel field's resting frame and the status it says after tabbing out."""
    page_comment_empty(page)
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    page.wait_for_function(
        "() => !document.querySelector('.lf-fp-field').matches(':focus-within')"
    )


def composer_caret_motion(page: Page) -> None:
    """A line-end caret in the last frame of the comment box's growth."""
    composer_empty(page)
    settle(page)
    page.evaluate("""() => {
      const animate = Element.prototype.animate;
      Element.prototype.animate = function (...args) {
        const motion = animate.apply(this, args);
        if (motion.timeline === document.timeline) {
          motion.pause();
          motion.currentTime = Number(motion.effect.getTiming().duration) - 0.01;
        }
        return motion;
      };
    }""")
    page.keyboard.insert_text(
        "it's not really a feed as much as a list? I see a feed as"
    )


def composer_space(page: Page) -> None:
    """A narrow comment ending in a space, beside Send."""
    composer(page)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text("this is a nice feature; is it in leaf, or you")
    page.keyboard.press("Space")


# A draft of two paragraphs whose lines run past the composer's width, so every field
# shows how its words wrap beside the action in its corner, on the lines above the last
# as well as the last.
LONG_DRAFT = (
    "next phase: could we integrate the status ontology & workflow into our tasks "
    "concept? So when the agent is working on something, they're working on a task?"
    "\n\nwhat else do we need to move around for that to work?"
)


def composer_send_focused(page: Page) -> None:
    """The same comment with the keyboard on its Send."""
    composer(page)
    page.keyboard.press("Tab")
    send = page.locator(".lf-composer .lf-compose-submit")
    send.focus()
    expect(send).to_have_attribute("data-lf-focus-visible", re.compile(".*"))


def composer_long(page: Page) -> None:
    """A comment of two wrapped paragraphs being typed on a selected passage."""
    composer(page)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text(LONG_DRAFT)


def composer_scrolling(page: Page) -> None:
    """A floating draft that fills its available height and scrolls its words."""
    composer_empty(page)
    page.keyboard.insert_text((LONG_DRAFT + "\n\n") * 8)
    page.wait_for_function("""() => {
      const field = document.querySelector('.lf-fab-input');
      return field.scrollHeight > field.clientHeight;
    }""")
    page.locator(".lf-fab-input").hover()


def composer_sent(page: Page) -> None:
    """That comment just sent: its card shares the draft's text column and wrapping."""
    composer_long(page)
    if page.evaluate("matchMedia('(pointer: coarse)').matches"):
        page.locator(".lf-fab-bar").get_by_role(
            "button", name="Comment", exact=True
        ).tap()
    else:
        page.keyboard.press("Enter")
    page.locator(".lf-margin-preview").wait_for()
    page.wait_for_function(
        "() => !document.querySelector('.lf-margin-preview [aria-busy=\"true\"]')"
    )
    page.mouse.move(0, 0)


def composer_sent_zoomed(page: Page) -> None:
    """A short sent comment at fractional zoom keeps its one line."""
    page.evaluate("document.documentElement.style.zoom = '1.1'")
    page.locator("#plan-lede").click(click_count=3)
    page.locator(".lf-fab-input").click()
    page.keyboard.insert_text(
        "better; is there a way of shortening? or maybe we just remove it??"
    )
    page.keyboard.press("Enter")
    page.locator(".lf-margin-preview").wait_for()
    page.wait_for_function(
        "() => !document.querySelector('.lf-margin-preview [aria-busy=\"true\"]')"
    )
    page.mouse.move(0, 0)


def card_reply_long(page: Page) -> None:
    """The first margin card with a reply of two wrapped paragraphs being typed."""
    card_by_keyboard(page)
    page.keyboard.press("Enter")
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-margin-preview leaf-text')"
    )
    page.keyboard.insert_text(LONG_DRAFT)


def panel_reply_long(page: Page) -> None:
    """The last open thread, opened from Threads in the floating panel, with a reply
    of two wrapped paragraphs in the panel's field, its reply box."""
    go_to_threads(page)
    page.locator(".lf-fp-thread:not([data-lf-resolved])").last.click()
    expect(page.locator(panel_view("thread"))).to_be_visible()
    page.locator(".lf-fp-field leaf-text").click()
    page.keyboard.insert_text(LONG_DRAFT)


def page_comment_long(page: Page) -> None:
    """The floating panel's field with a page comment of two wrapped paragraphs."""
    page.locator(".lf-fp-field leaf-text").click()
    page.keyboard.insert_text(LONG_DRAFT)


def option_long(page: Page) -> None:
    """An option list's added option, typed long enough to wrap beside its Add press."""
    field = page.locator(".lf-another leaf-text").first
    field.scroll_into_view_if_needed()
    field.click()
    page.keyboard.insert_text(
        "Page the on-call owner only when the canary fails twice in a row, hold the "
        "rollout until they acknowledge, and send every single failed probe to the "
        "team channel instead, so the deploy trains stop paging anyone at all while "
        "a real outage still reaches a person within a couple of minutes"
    )


def option_add_hover(page: Page) -> None:
    """A compact alternative's Add face beside its one-line draft."""
    form = page.locator("#bg-choice > .lf-another")
    form.locator("leaf-text").click()
    page.keyboard.insert_text("Keep the current behavior")
    form.get_by_role("button", name="Add and select option", exact=True).hover()


def options_in_pane(page: Page) -> None:
    """An option list in a workspace pane, under the paragraphs it answers."""
    page.get_by_text("Checkout p99 latency", exact=True).click()
    page.locator("#ar-latency-decision > lf-options").scroll_into_view_if_needed()


def tally_after_an_answer(page: Page) -> None:
    """A queue's tally after Next On Me and one answer: the count down by one, the
    answered row's check above the open marks, and Next On Me's second obligation open."""
    next_on_me = page.locator("#ar-left .lf-tally-next")
    next_on_me.click()
    page.locator("#ar-canary-consecutive").click()
    expect(page.locator("#ar-left .lf-tally-words")).to_have_text("8 left to answer")
    next_on_me.click()
    expect(page.locator("#ar-latency-decision")).to_be_focused()
    settle(page)


def card_grabbed(page: Page) -> None:
    """A board card grabbed by keyboard and carried one column left."""
    page.keyboard.press("Tab")
    page.locator("#card-tz > .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowLeft")


def card_moved(page: Page) -> None:
    """A board card carried one column left by keyboard and dropped, its receipt pinned
    by it, where the next column's card stands across the gap."""
    card_grabbed(page)
    page.keyboard.press("Enter")
    expect(page.locator("#col-blocking #card-tz")).to_be_visible()
    expect(
        page.locator('.lf-margin-cluster[data-lf-margin-for="card-tz"]')
    ).to_be_visible()


def card_moved_by_destination(page: Page) -> None:
    """A board card moved by its Move to button, as a phone offers it, its receipt
    pinned by it."""
    page.locator(
        '#card-tz .lf-board-destination[data-lf-board-target="col-blocking"]'
    ).click()
    expect(page.locator("#col-blocking #card-tz")).to_be_visible()
    expect(
        page.locator('.lf-margin-cluster[data-lf-margin-for="card-tz"]')
    ).to_be_visible()


def activity_feed(page: Page) -> None:
    """A committed board move beside the published revision in the opened feed."""
    card_grabbed(page)
    page.keyboard.press("Enter")
    expect(page.locator("#col-blocking #card-tz")).to_be_visible()
    notice = page.locator("#triage-activity .lf-activity-news")
    expect(notice).to_contain_text("new")
    notice.click()
    expect(
        page.locator("#triage-activity .lf-activity-row").filter(has_text="moved")
    ).to_be_visible()
    page.locator("#triage-moves").scroll_into_view_if_needed()


def gloss_open(page: Page) -> None:
    """A gloss's card, pinned open by a press on its phrase."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    gloss = page.locator("#bg-gloss")
    gloss.scroll_into_view_if_needed()
    gloss.click()
    expect(gloss.locator(".lf-gloss-popover")).to_be_visible()


def settled_option(page: Page) -> None:
    """A settled decision collapsed to its one line."""
    page.locator("#bg-outcome").scroll_into_view_if_needed()


def settled_option_hover(page: Page) -> None:
    """An expanded decision answers hover without lifting the card."""
    page.locator("#bg-outcome .lf-settled").click()
    page.locator("#bg-outcome-door").hover()
    settle(page)


def into_the_body(page: Page) -> None:
    """Two windows down the page, where a sidebar page's track stands beside the body
    it scrolls past."""
    page.evaluate("() => scrollTo(0, 2 * innerHeight)")


def plan_caveat(page: Page) -> None:
    """The plan's network caveat, visible between the prose of two steps."""
    page.locator("#plan-network").evaluate(
        "node => node.scrollIntoView({block: 'center'})"
    )


def code_note(page: Page) -> None:
    """The first code block with a note, the note in view."""
    page.locator("lf-code pre lf-note").first.evaluate(
        "note => note.scrollIntoView({block: 'center'})"
    )


def frame_edges(page: Page) -> None:
    """The drawn row's parallel paragraphs, with their declared margins intact."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Page & layout", exact=True
    ).click()
    settle(page)
    page.locator("#bg-frame-edges").evaluate(
        "el => el.scrollIntoView({block: 'start'})"
    )


def gallery_metrics(page: Page) -> None:
    """Headline values and charts, reached through the gallery's page tab."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    page.locator("#bg-metrics-and-chart").scroll_into_view_if_needed()


def chart_preview(page: Page) -> None:
    """The gallery's line chart under a resting pointer by its second run: the ring on
    the baseline's point, its rule to the axis, and the preview above them saying the
    run, the series and the value (lf-chart.js). A runtime whose charts say no values
    shows the chart alone."""
    gallery_metrics(page)
    chart = page.locator("#bg-chart")
    chart.evaluate("el => el.scrollIntoView({block: 'center'})")
    run = chart.locator('[data-lf-part="x-axis tick label"] text').get_by_text(
        "2", exact=True
    )
    value = chart.locator('[data-lf-part="y-axis tick label"] text').get_by_text(
        "6", exact=True
    )
    x, y = run.bounding_box(), value.bounding_box()
    assert x is not None and y is not None
    at = (x["x"] + x["width"] / 2, y["y"] + y["height"] / 2)
    page.mouse.move(at[0] - 8, at[1])
    page.mouse.move(*at)
    page.wait_for_function(
        """() => !document.querySelector('#bg-chart .lf-chart-at')
          || document.getElementById('lf-preview').matches(':popover-open')"""
    )
    settle(page)


def gallery_plans(page: Page) -> None:
    """Planned work beside observed history, using authored stable section identity."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    page.locator("#bg-plans-and-history").scroll_into_view_if_needed()


def gallery_drawing(page: Page) -> None:
    """The reading theme's `svg.drawing`, with each of its text classes on its shapes."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    page.locator("#bg-drawing-figure").scroll_into_view_if_needed()


def gallery_ask_figure(page: Page) -> None:
    """An `lf-ask` enclosing a chart, with its question at the window's top so the chart and
    every option either share the window or run past it."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    settle(page)
    page.locator("#bg-ask-across lf-ask").evaluate(
        "el => el.scrollIntoView({block: 'start'})"
    )


def theme_hierarchy(page: Page) -> None:
    """A neutral callout with open and closed support; exercise the closed row by key."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Page & layout", exact=True
    ).click()
    settle(page)
    summary = page.locator("#bg-theme-support summary")
    for _ in range(12):
        page.keyboard.press("Tab")
        if summary.evaluate("el => el.matches(':focus')"):
            break
    else:
        raise AssertionError("Tab did not reach the supporting disclosure")
    page.keyboard.press("Enter")
    page.wait_for_function("() => document.querySelector('#bg-theme-support').open")
    page.keyboard.press("Enter")
    page.wait_for_function("() => !document.querySelector('#bg-theme-support').open")
    page.locator("#bg-theme-hierarchy").evaluate(
        "el => el.scrollIntoView({block: 'start'})"
    )


def wide_schedule(page: Page) -> None:
    """The gallery's explicitly allocated schedule, with its guide and caption."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Page & layout", exact=True
    ).click()
    page.locator("#bg-margin-layer-figure").scroll_into_view_if_needed()
    settle(page)


def wide_passage(page: Page) -> None:
    """A selected passage in a wide block, with its comment field beside it."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Threads", exact=True
    ).click()
    page.locator("#bg-wide-passage").evaluate(
        "el => el.scrollIntoView({block: 'center'})"
    )
    page.keyboard.press("/")
    page.keyboard.insert_text('"keep the active card"')
    page.keyboard.press("Enter")
    page.locator(".lf-fab-input").wait_for(state="visible")


def multiline_passage(page: Page) -> None:
    """A passage beginning midline and ending on a line that starts further left."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Threads", exact=True
    ).click()
    page.locator("#bg-wide-passage").evaluate(
        "el => el.scrollIntoView({block: 'center'})"
    )
    first, last = page.evaluate("""() => {
      const walker = document.createTreeWalker(
        document.querySelector('#bg-wide-passage code'), NodeFilter.SHOW_TEXT);
      const range = document.createRange();
      for (let node; (node = walker.nextNode());) {
        if (node.data.includes('Keep')) range.setStart(node, node.data.indexOf('Keep'));
        if (node.data.includes('card')) range.setEnd(node, node.data.indexOf('card') + 4);
      }
      const fragments = [...range.getClientRects()].filter(r => r.width && r.height);
      return [fragments[0].toJSON(), fragments.at(-1).toJSON()];
    }""")
    page.mouse.move(first["left"] + 1, first["top"] + first["height"] / 2)
    page.mouse.down()
    page.mouse.move(last["right"] - 1, last["top"] + last["height"] / 2, steps=8)
    page.mouse.up()
    page.locator(".lf-fab-input").wait_for(state="visible")


def code_copy_by_pointer(page: Page) -> None:
    """Code's corner control revealed by hovering its source."""
    code_note(page)
    page.locator("lf-code pre").first.hover()


def code_copy_by_keyboard(page: Page) -> None:
    """Code's corner control focused from the keyboard."""
    code_note(page)
    # After `scrollIntoView`, Chromium's Tab continues from the view but Firefox's from
    # the top of the document, which scrolls the block away; Shift only marks the
    # keyboard as the latest input.
    page.keyboard.press("Shift")
    page.locator("lf-code .lf-code-copy").first.get_by_role("button").focus()


def diff_author_notes(page: Page) -> None:
    """Author prose under old and new lines, beside horizontally scrolling source."""
    page.locator("#dfg-scroll").scroll_into_view_if_needed()


def diff_path_by_keyboard(page: Page) -> None:
    """A folded diff file's row under the keyboard, saying the whole path its row cuts
    short."""
    head = page.locator("#pr-exact-patch .lf-diff-head[data-lf-path-cut]").first
    head.scroll_into_view_if_needed()
    page.keyboard.press("Shift")
    head.focus()


def diff_source_by_pointer(page: Page) -> None:
    """A click stands on the scrolling source without a keyboard ring."""
    file = page.locator("#pr-exact-patch .lf-diff-file").filter(
        has=page.locator("summary", has_text="benches/picker_preview.rs")
    )
    file.locator("summary").click()
    source = file.locator("code[data-code]")
    source.click(position={"x": 150, "y": 25})
    expect(source).to_be_focused()
    page.mouse.move(0, 0)


def diff_source_by_keyboard(page: Page) -> None:
    """Tab returns to the source; its ring stays over shaded, scrolled rows."""
    diff_source_by_pointer(page)
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    source = page.locator(
        '#pr-exact-patch code[data-code][aria-label="benches/picker_preview.rs"]'
    )
    expect(source).to_be_focused()
    page.keyboard.press("ArrowRight")
    page.wait_for_function(
        "document.querySelector('#pr-exact-patch').shadowRoot.querySelector('code[data-code][aria-label=\"benches/picker_preview.rs\"]').scrollLeft > 0"
    )


def diff_long_lines(page: Page) -> None:
    """The gallery's long-line patches at the top of the window: Markdown that wraps
    above code that wraps and code that scrolls."""
    page.locator("#dfg-prose").evaluate("diff => diff.scrollIntoView({block: 'start'})")


def diff_file_reply(page: Page) -> None:
    """A reply to the first of two conversations under a collapsed diff file."""
    threads = page.frame_locator("#dfg-sample iframe").locator(
        "#dfg-patch .lf-page-thread"
    )
    expect(threads).to_have_count(2)
    field = threads.first.get_by_role("textbox", name="Reply", exact=True)
    field.click()
    page.keyboard.insert_text(
        "Keep the file conversations clear while this reply is drafted."
    )


def diff_moved_reply(page: Page) -> None:
    """The active reply after a widget moves its thread outlets outside its owner."""
    diff_file_reply(page)
    sample = page.frame_locator("#dfg-sample iframe")
    diff = sample.locator("#dfg-patch")
    diff.evaluate("""async widget => {
      const boot = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
      const {threadSurface} = await import(new URL('runtime/widget-api.js', new URL(boot, location.href)));
      for (const outlet of widget.shadowRoot.querySelectorAll('.lf-diff-thread-outlet'))
        document.querySelector('main').append(outlet);
      threadSurface(widget).update();
    }""")
    expect(diff.locator(".lf-page-thread")).to_have_count(0)
    settle(page)


def diff_file_resolved_closed(page: Page) -> None:
    """Both conversations under a diff file resolved, their outlet as it folds them."""
    diff = page.frame_locator("#dfg-sample iframe").locator("#dfg-patch")
    resolve = diff.get_by_role("button", name="Resolve thread", exact=True)
    expect(resolve).to_have_count(2)
    for remaining in (1, 0):
        resolve.first.click()
        expect(resolve).to_have_count(remaining)
    page.mouse.move(0, 0)


def diff_file_resolved(page: Page) -> None:
    """Both conversations under a diff file resolved, and the outlet's one Resolved
    disclosure, which holds them, opened."""
    diff_file_resolved_closed(page)
    resolved = page.frame_locator("#dfg-sample iframe").locator(
        "#dfg-patch .lf-diff-thread-outlet details.lf-resolved-threads"
    )
    expect(resolved).to_have_count(1)
    resolved.locator(":scope > summary").click()
    expect(resolved).to_have_attribute("open", "")


def diff_line_composer(page: Page) -> None:
    """A line's thread control, number and shared composer in one reading."""
    diff = page.locator("#pr-exact-patch")
    head = diff.locator("summary").first
    head.scroll_into_view_if_needed()
    head.click()
    comment = diff.locator(".lf-diff-line-comment").first
    comment.locator("..").hover()
    comment.click()
    expect(diff.locator(".lf-fab-input")).to_be_visible()


def code_source_by_touch(page: Page) -> None:
    """Code stood on by touch, its corner Copy shown by the tap."""
    code_note(page)
    page.locator("lf-code pre").first.tap(position={"x": 60, "y": 20})


def pane_focused(page: Page) -> None:
    """A workspace pane's body focused by keyboard: a pane standing flush with the
    workspace's own scrollport, which clipped a ring drawn outside the body."""
    page.keyboard.press("Tab")
    page.locator("#sort-source").focus()


def aim_cut_by_pane(page: Page) -> None:
    """The aim over a paragraph whose top a workspace pane has scrolled out of view:
    the pane cuts the aim where it cuts the paragraph."""
    page.locator("#sort-source").evaluate(
        """source => {
          const note = document.getElementById('sort-source-note');
          source.scrollTop += note.getBoundingClientRect().top
            - source.getBoundingClientRect().top + 24;
        }"""
    )
    box = page.locator("#sort-source").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 120, box["y"] + 20)
    page.keyboard.down("Alt")
    page.wait_for_function(
        "() => document.getElementById('sort-source-note')?.hasAttribute('data-lf-aimed')"
    )


def breakout_captions_scrolled(page: Page) -> None:
    """Keep the captions visible after scrolling both tables to their far ends."""
    page.locator("table").evaluate_all("""tables => tables.forEach(table => {
      table.scrollLeft = table.dir === 'rtl' ? -table.scrollWidth : table.scrollWidth;
    })""")
    settle(page)


def table_scrolled_sideways(page: Page) -> None:
    """A table whose rows open with their names, scrolled to its far end on a phone."""
    page.locator("#security-deep-record > summary").click()
    page.locator("#security-vendor-table").evaluate(
        """table => {
          table.scrollIntoView({block: 'center'});
          table.scrollLeft = table.scrollWidth;
        }"""
    )
    page.wait_for_function(
        "() => document.getElementById('security-vendor-table')"
        ".hasAttribute('data-lf-more-before')"
    )


def element_thread(page: Page) -> None:
    """An element holding a thread, in view, with nothing indicating it."""
    page.locator("#off-t-vendor").evaluate("el => el.scrollIntoView({block: 'center'})")


def ship_tasks(page: Page) -> None:
    """The ship review's task list, each task's status beside its title."""
    page.locator("#off-readiness").evaluate(
        "el => el.scrollIntoView({block: 'center'})"
    )


def ship_answered(page: Page) -> None:
    """On Me once the user has pressed Done in the reconnect thread and picked the
    release: what still waits on them."""
    card_by_pointer(page)
    page.locator(".lf-margin-preview:not([hidden]) .lf-done").click()
    page.keyboard.press("Escape")
    page.locator("#off-release-ship").click()
    page.locator(".lf-fp-on-user").click()
    expect(page.locator(".lf-fp-opened")).to_be_visible()


def card_message_by_keyboard(page: Page) -> None:
    """The agent's question in a margin card, reached by Next On Me (`m`), which
    focuses the message, so its card wears the ring."""
    for _ in range(4):
        page.keyboard.press("m")
        settle(page)
        if page.evaluate(
            "() => document.activeElement?.matches('.lf-margin-preview .lf-msg')"
        ):
            return
    raise AssertionError("Next On Me never reached a card's message")


def card_ask_by_keyboard(page: Page) -> None:
    """The agent's ask in a margin card, reached by Next On Me (`m`), which focuses the
    ask, so the location ring stands round it inside the card's transcript."""
    page.keyboard.press("m")
    expect(page.locator(".lf-margin-preview lf-ask")).to_be_focused()
    settle(page)


def element_thread_open(page: Page) -> None:
    """The same element while the user is in its thread, opened from its margin card:
    the contour that says which element the thread is about, beside the heading's
    first letters."""
    open_card(
        page, page.locator('[data-lf-margin-for="off-t-vendor"] .lf-margin-marker')
    )


def option_thread_open(page: Page) -> None:
    """A thread on the chosen card of a joined option group, opened from its margin
    card: the contour standing on a cell its group's frame clips."""
    as_agent(
        "thread",
        "create",
        "--section",
        "off-workaround-approve",
        "--text",
        "Ship it with the workaround?",
    )
    load(page, served_page.get().address)
    open_card(
        page,
        page.locator('[data-lf-margin-for="off-workaround-approve"] .lf-margin-marker'),
    )


def more_menu(page: Page) -> None:
    """The leaf's menu, the On view's first tab, opened: the agent's state at its head
    over the page's controls, the field its search and the tabs at its foot."""
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu").wait_for()


def capture_menu(page: Page) -> None:
    """Capture area, chosen from the leaf menu's Annotations, standing over the dimmed
    page with no area drawn until a drag draws one."""
    more_menu(page)
    page.locator('.lf-fp-item[data-lf-row="group:annotate"]').click()
    page.locator('.lf-fp-item[data-lf-row="command:capture.region.open"]').click()
    expect(page.get_by_role("region", name="Capture area", exact=True)).to_be_visible()


def capture_area(page: Page) -> None:
    """Draw a page area, held before the lift that would attach it, with the way out
    of area capture in the panel's row."""
    page.locator("#plan-context").scroll_into_view_if_needed()
    capture_menu(page)
    page.mouse.move(100, 200)
    page.mouse.down()
    page.mouse.move(360, 350, steps=4)


def capture_small_drag(page: Page) -> None:
    """Hold a small selection over words, which must remain visible during the drag."""
    page.locator("#plan-current").scroll_into_view_if_needed()
    capture_menu(page)
    target = page.locator("#plan-current").bounding_box()
    assert target is not None
    left, top = round(target["x"]) + 45, round(target["y"]) + 8
    page.mouse.move(left, top)
    page.mouse.down()
    page.mouse.move(left + 88, top + 44, steps=8)


def versions_menu(page: Page) -> None:
    """Versions, opened from the leaf's menu: a row for each version, with its note,
    the agent's latest as long as a stamp's note runs on real pages (about 90
    characters), where the fixture's own say only Earlier draft."""
    source = served_page.get().directory / "index.html"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "remaining decision", "one decision left", 1
        ),
        encoding="utf-8",
    )
    as_agent(
        "page",
        "stamp",
        "--text",
        "Moved the self-hosted runner decision into its own section and reordered "
        "shutdown so cleanup runs after the supervisor collects output",
    )
    wait_until_ready(page, PageClient(served_page.get().address).state())
    more_menu(page)
    page.locator('.lf-fp-item[data-lf-row="versions"]').click()
    page.locator(".lf-fp-version").first.wait_for()


def all_pages(page: Page) -> None:
    """All pages with two neighbours of one title, told apart only by where their
    sessions work. A stills server has no neighbour of its own, so a rewritten state
    supplies them."""

    def with_neighbours(route):
        response = route.fetch()
        state = response.json()
        state["others"] = [
            {
                "page_key": place,
                "url": f"http://127.0.0.1:9/{place}",
                "title": "Move Tend's agent runs into one sandbox and retire its setup",
                "session_cwd": f"/workspace/tend.{place}",
                "activity": {
                    **state["activity"],
                    "presence": "here",
                    "state": "running",
                    "reason": None,
                    "next_actor": "agent",
                    "detail": "Running the sandbox suite against both harnesses",
                },
            }
            for place in ("sandbox-runner", "release-notes")
        ]
        route.fulfill(response=response, json=state)

    page.route("**/api/state*", with_neighbours)
    page.reload()
    wait_until_ready(page)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    page.locator(panel_view("leaves")).wait_for()


def obligation_marker_by_keyboard(page: Page) -> None:
    """An obligation's margin marker and the location ring it projects onto the page."""
    marker = page.locator('.lf-margin-entry[data-lf-kinds="on-me"]').first
    for _ in range(400):
        page.keyboard.press("Tab")
        if marker.evaluate("node => node === document.activeElement"):
            return
    raise AssertionError("Tab did not reach the obligation's margin marker")


def ask_by_keyboard(page: Page) -> None:
    """The next open obligation, an `lf-ask`, reached with `m`: its ring and its marker in view."""
    page.keyboard.press("m")
    page.locator("lf-ask").first.wait_for()


def steps_in_view(page: Page) -> None:
    """A list of steps in body prose, each number beside its first line."""
    page.locator("#security-contract-list").scroll_into_view_if_needed()


def disclosures_in_view(page: Page) -> None:
    """Two closed disclosures written one after the other at the page's end."""
    page.locator("#security-source-disclosure").scroll_into_view_if_needed()


def security_flow(page: Page) -> None:
    """The case study's five-step flow diagram, every step in view."""
    page.locator("#security-before-flow").scroll_into_view_if_needed()


def go_to(page: Page) -> None:
    """The Go-to sequence armed from the keyboard, its destinations on the line."""
    page.keyboard.press("g")
    page.wait_for_function("() => document.body.hasAttribute('data-lf-go-to-active')")


def contents_by_keyboard(page: Page) -> None:
    """The contents map revealed by focus on its first section link."""
    page.keyboard.press("Tab")
    page.locator("lf-toc li a").first.focus()


def contents_marks(page: Page) -> None:
    """Where each section's threads and On me items stand along the contents: on the
    map where the track stands beside the body, and in the outline the reader opened
    where the track stacks over it."""
    toggle = page.locator("lf-toc .lf-toc-toggle")
    if toggle.is_visible():
        toggle.click()
        expect(page.locator("lf-toc details")).to_have_attribute("open", "")
    settle(page)


def contents_marks_changes(page: Page) -> None:
    """The contents' marks with the changes view on, each changed section marked."""
    contents_marks(page)
    page.keyboard.press("v")
    expect(page.locator(".lf-ins-block").first).to_be_attached()
    settle(page)


def topic_contents(page: Page) -> None:
    """The topic's inline index in the gallery's page-tabs sample."""
    page.locator("#bg-gallery-tabs").get_by_role(
        "tab", name="Page & layout", exact=True
    ).click()
    page.locator("#bg-tab-set").scroll_into_view_if_needed()
    sample = page.locator("#bg-topic-contents")
    sample.scroll_into_view_if_needed()
    page.evaluate("document.getElementById('bg-topic-contents').ready")


def overflowing_tabs(page: Page) -> None:
    """Reveal the far end of a boxed tab strip through its overflow arrow."""
    page.locator("#bg-gallery-tabs").get_by_role(
        "tab", name="Page & layout", exact=True
    ).click()
    strip = page.locator("#bg-rollout-tabs > .lf-tabstrip")
    strip.scroll_into_view_if_needed()
    strip.locator('.lf-tabstrip-scroll[data-lf-to="end"] > span').click()
    scroll_settled(page)


def widget_inline_hints(page: Page) -> None:
    """A standalone command scope with an active inline hint, outside an `lf-ask`."""
    page.locator("#bg-widget-shortcut-hints").scroll_into_view_if_needed()
    page.keyboard.press("Tab")
    page.locator("#bg-local-shortcuts").focus()


def hub_workers(page: Page) -> None:
    """The plan with the parser goal's workers shown, its worktree in view."""
    page.locator("#w-1 > details > summary").click()
    page.locator("#tree-w-1").scroll_into_view_if_needed()


def draft_edit(page: Page) -> None:
    """A passage opened in its shared editor, with Markdown source and a focused caret."""
    page.locator("#rn-cli .lf-draft-body").click()
    page.keyboard.press("Tab")
    page.locator("#rn-cli .lf-draft-edit").focus()


def draft_long_edit(page: Page) -> None:
    """Open a visible word after scrolling through a long Markdown draft."""
    page.locator("#rn-cli .lf-draft-body").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text(
        "\n".join(
            f"Line {i}: The **release note** remains `editable`." for i in range(60)
        )
    )
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("#rn-cli .lf-draft-edit")).to_have_count(0)
    body = page.locator("#rn-cli .lf-draft-body")
    expect(body).to_contain_text("Line 59:")
    word = """el => {
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode()) && !node.data.includes('Line 30:')) {}
      const at = node.data.indexOf('Line 30:');
      const range = document.createRange();
      range.setStart(node, at + 3); range.setEnd(node, at + 4);
      const box = range.getBoundingClientRect();
      return [box.x + box.width / 2, box.y + box.height / 2];
    }"""
    point = body.evaluate(word)
    page.evaluate("y => window.scrollBy(0, y - 350)", point[1])
    scroll_settled(page)
    page.mouse.click(*body.evaluate(word))
    expect(page.locator("#rn-cli .lf-draft-edit")).to_be_focused()


def draft_hover(page: Page) -> None:
    """A draft under the pointer, which shows its toolbar of marks on its border."""
    page.locator("#rn-cli .lf-draft-body").hover()
    expect(page.locator("#rn-cli .lf-draft-tools")).to_have_css("opacity", "1")


def playground_controls(page: Page) -> None:
    """The playground's controls and instruction, with keyboard focus on its range."""
    page.keyboard.press("Tab")
    control = page.get_by_role("slider", name="Concurrent release events")
    control.focus()
    control.press("ArrowRight")
    page.locator(".lf-playground-controls").scroll_into_view_if_needed()


def playground_instruction(page: Page) -> None:
    """The playground's instruction opened over the page, with its copy."""
    page.get_by_role("button", name="Show instruction").click()
    expect(page.locator("lf-playground-output")).to_be_visible()
    page.mouse.move(0, 0)


def playground_tall_stage(page: Page) -> None:
    """The last alert's controls, pressed far down a stage taller than the window."""
    control = page.locator("lf-playground-preview lf-playground-control").last
    control.scroll_into_view_if_needed()
    control.get_by_role("radio").last.click()
    page.mouse.move(0, 0)


def page_end(page: Page) -> None:
    """Scrolled to the page's end, where a rail beside a short window's stage stops."""
    page.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")


def visual_review_inspection(page: Page) -> None:
    """Capture the artifact inspection popover beside the selected comparison."""
    page.locator(".lf-vr-case:not([hidden]) .lf-vr-inspect").click()
    page.mouse.move(0, 0)


def code_reader_feedback(page: Page) -> None:
    """The built reader and the place where its author receives design feedback."""
    page.get_by_role("tab", name="Comment on the reader").click()
    settle(page)
    page.locator("#code-reader-feedback").scroll_into_view_if_needed()


def margin_gallery(page: Page) -> None:
    """The margin gallery's real controls and labels in a finger-sized column."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Page & layout", exact=True
    ).click()
    settle(page)
    page.locator(
        "#bg-margin-controls-samples .margin-entry-gallery-group"
    ).first.evaluate("group => group.scrollIntoView({block: 'start'})")


def trace_controls(page: Page) -> None:
    """The recording's moments and playback controls, with its checkpoint ready."""
    page.wait_for_function(
        "() => !!document.querySelector('#release-trace .lf-trace-action')?.textContent"
    )
    page.locator("#release-trace .lf-trace-controls").evaluate(
        "controls => controls.scrollIntoView({block: 'start'})"
    )


def trace_image_scale(page: Page) -> None:
    """A recording's image scale with its choices open, hung below their trigger."""
    trace = page.locator("#release-trace")
    scale = trace.get_by_role("button", name="Image scale", exact=True)
    expect(scale).to_be_enabled()
    scale.evaluate("node => node.scrollIntoView({block: 'center'})")
    scale.click()
    expect(trace.locator(".lf-trace-scale-options:popover-open")).to_be_visible()
    page.mouse.move(0, 0)


def trace_comparison(page: Page) -> None:
    """Recording choice, transport and saved moments in the shared workspace."""
    page.get_by_role("radio", name="Before the fix", exact=True).click()
    page.locator("#fix-before").get_by_role(
        "button", name="Screenshot attached", exact=False
    ).click()
    page.wait_for_function(
        "() => !!document.querySelector('#fix-before .lf-trace-action')?.textContent"
    )
    page.locator("#fix-compare").evaluate(
        "node => node.scrollIntoView({block: 'start'})"
    )


def film_inspector(page: Page) -> None:
    """Details beside the selected SVG commit in the merge film. The pointer leaves
    before the stage scrolls into place: one the scroll left over the stage would close
    the details at its next `pointermove`, which WebKit sends by itself after a
    scroll."""
    page.get_by_role("button", name="Inspect next element", exact=True).click()
    expect(page.locator("#merge-film .film-inspect")).to_be_visible()
    page.mouse.move(0, 0)
    page.locator("#merge-film .film-stage").evaluate(
        "node => node.scrollIntoView({block: 'center'})"
    )


def live_sample_embedded(page: Page) -> None:
    """The arrived practice page at its embedded content height."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    sample = page.locator("#bg-live-sample")
    # As a reader scrolling toward it brings it, half a window below the window, where
    # its page starts and takes its height before they reach it.
    sample.evaluate(
        "sample => scrollBy(0, sample.getBoundingClientRect().top - 1.5 * innerHeight)"
    )
    sample.evaluate("sample => sample.ready")
    sample.scroll_into_view_if_needed()
    expect(
        sample.frame_locator("iframe").locator("#bg-live-sample-copy")
    ).to_be_visible()


def interactive_sample(page: Page) -> None:
    """An interactive sample, whose widgets use this page's state, under its note."""
    page.locator("#bg-inline-sample").scroll_into_view_if_needed()


def live_sample_full_view(page: Page) -> None:
    """The same practice frame promoted into its native full-view dialog."""
    live_sample_embedded(page)
    sample = page.locator("#bg-live-sample")
    sample.get_by_role("button", name="Full view", exact=True).click()
    expect(sample.get_by_role("dialog", name="practice release note")).to_be_visible()


def trace_image_by_keyboard(page: Page) -> None:
    """The recording's captured image focused by keyboard, its ring over the marks."""
    trace_controls(page)
    page.keyboard.press("Tab")
    page.locator("#release-trace .lf-trace-canvas").first.focus()


def trace_timeline_by_keyboard(page: Page) -> None:
    """The timeline focused, after tabbing away from it and back."""
    trace_controls(page)
    page.keyboard.press("Tab")
    trace = page.locator("#release-trace")
    trace.get_by_role("group", name="Recording timeline", exact=True).focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    page.wait_for_function(
        "() => document.activeElement?.matches('#release-trace .lf-trace-timeline')"
    )


def authored_timeline_step(page: Page) -> None:
    """A step reached by Tab, with the timeline's playhead on it."""
    page.locator("#race .lf-timeline-step").first.click()
    page.keyboard.press("Tab")
    page.keyboard.press("Space")


@dataclass(frozen=True)
class State:
    """The page `source` names, brought to this state by `drive` once it has loaded,
    or as it loads when there is none. A state that isn't `activated` holds the
    runtime's entry module in flight, so its tab shows the authored layout before the
    runtime upgrades it."""

    name: str
    source: str
    drive: Callable[[Page], None] | None = None
    window: Window = WINDOWS["macbook"]
    region: str | None = None
    activated: bool = True


STATES = (
    State(
        "dynamic-request-preview",
        "dynamic-widgets",
        dynamic_request_preview,
        region="#leaf-request-document",
    ),
    State("printed-exhibit", "lost-update", printed_exhibit, region="main"),
    State("failed-widget", "review-a-plan", failed_widget, window=Window((1600, 900))),
    State("page-about", "review-a-plan", page_about, region=".lf-inspection-dialog"),
    State(
        "authored-timeline-keyboard",
        "lost-update",
        authored_timeline_step,
        region="#race",
    ),
    State(
        "native-code",
        "feature-gallery",
        native_code,
        region="#bg-javascript-code",
    ),
    State(
        "annotated-code",
        "feature-gallery",
        annotated_code,
        region="#bg-annotated-code",
    ),
    State(
        "native-code-copy-hover",
        "feature-gallery",
        native_code_copy_hover,
        region="#bg-javascript-code",
    ),
    State(
        "markdown-preview-scrolled",
        "feature-gallery",
        markdown_preview_scrolled,
        region="#bg-markdown-preview",
    ),
    State(
        "long-source-selected",
        "pr-walkthrough",
        long_source_selected,
        region="#pr-prepared-diff-source",
    ),
    State(
        "captured-source",
        "feature-gallery",
        captured_source,
        region="#bg-source-captures",
    ),
    State(
        "captured-source-keyboard",
        "feature-gallery",
        captured_source_by_keyboard,
        region="#bg-source-live",
    ),
    State(
        "recorded-video",
        "feature-gallery",
        recorded_video,
        region="#bg-recorded-media",
    ),
    State(
        "recorded-video-keyboard",
        "feature-gallery",
        recorded_video_by_keyboard,
        region="#bg-recorded-media",
    ),
    State(
        "panel-leaf",
        "feature-gallery",
        panel_leaf,
        region=".lf-fp-leaf",
    ),
    State("panel-status-hover", "review-a-plan", panel_status_hover),
    State("floating-thread", "ship-review", floating_thread, region=".lf-fp-opened"),
    State(
        "detached-thread", "feature-gallery", detached_thread, region=".lf-fp-opened"
    ),
    State("thread-code-copy", "ship-review", thread_code_copy, region=".lf-fp-opened"),
    State(
        "floating-thread-unread",
        "ship-review",
        floating_thread_unread,
        region=".lf-fp-opened",
    ),
    State("ship-threads", "ship-review", go_to_threads, region=".lf-fp-opened"),
    State(
        "ship-threads-scrolled",
        "ship-review",
        threads_scrolled,
        region=".lf-fp-opened",
        window=Window((1440, 300)),
    ),
    State("plan-option-picked", "review-a-plan", option_picked, region=".lf-fp-row"),
    State("ship-option-answered", "ship-review", option_answered, region=".lf-fp-row"),
    State("panel-resolved", "ship-review", panel_resolved, region=".lf-fp-row"),
    State("panel-draw-mode", "review-a-plan", panel_draw_mode, region=".lf-fp-row"),
    State("panel-selection", "review-a-plan", panel_selection, region=".lf-fp-row"),
    State(
        "plan-option-card-picked",
        "review-a-plan",
        option_picked,
        region="lf-options:has(> #plan-admin)",
    ),
    State(
        "ship-option-references",
        "ship-review",
        option_references,
        region="#off-workaround-decision",
    ),
    State(
        "threads-returning", "ship-review", threads_returning, region=".lf-fp-opened"
    ),
    State(
        "floating-thread-retitled",
        "ship-review",
        floating_thread_retitled,
        region=".lf-fp-opened",
    ),
    State("panel-new-reply", "ship-review", panel_new_reply, region=".lf-fp-opened"),
    State("plan-head", "ship-review", plan_head, region=PANEL),
    State(
        "playground-choice",
        "notification-playground",
        playground_choice,
        region="lf-playground label:has(> input:focus)",
    ),
    State(
        "film-inspector",
        "wt-merge",
        film_inspector,
        window=Window((900, 900)),
        region="#merge-film .film-stage",
    ),
    State(
        "live-sample-embedded",
        "feature-gallery",
        live_sample_embedded,
        region="#bg-live-sample",
    ),
    State(
        "live-sample-full-view",
        "feature-gallery",
        live_sample_full_view,
        region="#bg-live-sample .lf-sample-view",
    ),
    State(
        "interactive-sample",
        "feature-gallery",
        interactive_sample,
        region="#bg-inline-sample",
    ),
    State(
        "trace-comparison-header",
        "review-a-fix",
        trace_comparison,
        window=Window((900, 900)),
        region="#fix-before",
    ),
    State("drawing-photo-comment", "feature-gallery", drawing_photo_comment),
    State("page-comment-photo", "feature-gallery", page_comment_photo),
    State(
        "page-comment-photo-hover",
        "feature-gallery",
        page_comment_photo_hover,
    ),
    State("panel-corner-hover", "review-a-plan", panel_corner_hover),
    State(
        "share-link",
        "feature-gallery",
        share_link,
        region='.lf-inspection-dialog [aria-label="Page details"]',
    ),
    State(
        "diff-filter",
        "pr-walkthrough",
        diff_filter,
        region="#pr-exact-patch .lf-diff-tools",
    ),
    State(
        "diff-separator",
        "pr-walkthrough",
        diff_separator,
        region="#pr-key-hunk .lf-diff-rows",
    ),
    State("diff-file-comment", "pr-walkthrough", diff_file_comment),
    State(
        "playground-text",
        "notification-playground",
        playground_text,
        region='lf-playground-control:has(> input[type="text"])',
    ),
    State("drawing-comment", "feature-gallery", drawing_comment),
    State("drawing-comment-hover", "feature-gallery", drawing_comment_hover),
    State(
        "drawing-comment-keyboard",
        "feature-gallery",
        drawing_comment_keyboard,
    ),
    State("progress-messages", "feature-gallery", progress_messages),
    State(
        "screenshot-comparison",
        "feature-gallery",
        screenshot_comparison,
        region="#bg-shot",
    ),
    State(
        "screenshot-pair",
        "feature-gallery",
        screenshot_pair,
        region="#bg-shot",
    ),
    State(
        "screenshot-slider-before",
        "feature-gallery",
        screenshot_slider_before,
        region="#bg-shot",
    ),
    State(
        "screenshot-pixels",
        "feature-gallery",
        screenshot_pixels,
        region="#bg-shot",
    ),
    State(
        "screenshot-options",
        "feature-gallery",
        screenshot_options,
        region="#bg-shot",
    ),
    State(
        "screenshot-views-keyboard",
        "feature-gallery",
        screenshot_views_keyboard,
        region="#bg-shot .lf-shot-toolbar",
    ),
    State(
        "screenshot-view-hover",
        "feature-gallery",
        screenshot_view_hover,
        region="#bg-shot .lf-shot-toolbar",
    ),
    State("dial-keyboard", "detail", dial_keyboard, region="lf-dial"),
    State("dial-press", "detail", dial_press, region="lf-dial"),
    State(
        "image-in-page",
        "feature-gallery",
        image_in_page,
        region="#bg-image-preview",
    ),
    State(
        "thread-picture",
        "feature-gallery",
        thread_picture,
        region=".lf-fp-opened",
    ),
    State("image-preview", "feature-gallery", image_preview),
    State(
        "visual-review-inspection",
        "visual-review-gallery",
        visual_review_inspection,
    ),
    State("diff-long-lines", "diff-thread-gallery", diff_long_lines),
    State(
        "diff-author-notes",
        "diff-thread-gallery",
        diff_author_notes,
        region="#dfg-scroll",
    ),
    State(
        "worktree-startup",
        "worktree-diffs",
        activated=False,
        region="#worktree-example-workbench",
    ),
    State(
        "worktree-summaries",
        "worktree-diffs",
        worktree_summaries,
        region="#worktree-example-workbench",
    ),
    State("diff-file-reply", "diff-thread-gallery", diff_file_reply),
    State("diff-moved-reply", "diff-thread-gallery", diff_moved_reply),
    State(
        "diff-file-resolved-closed",
        "diff-thread-gallery",
        diff_file_resolved_closed,
    ),
    State("diff-file-resolved", "diff-thread-gallery", diff_file_resolved),
    State("code-reader-feedback", "code-comparison", code_reader_feedback),
    State("activity-feed", "triage-board", activity_feed, region="#triage-moves"),
    State(
        "gloss-open",
        "feature-gallery",
        gloss_open,
        region="#bg-gloss .lf-gloss-popover",
    ),
    State(
        "settled-option",
        "feature-gallery",
        settled_option,
        region="#bg-outcome",
    ),
    State(
        "settled-option-hover",
        "feature-gallery",
        settled_option_hover,
        region="#bg-outcome",
    ),
    State("trace-controls", "playwright-trace-gallery", trace_controls),
    State(
        "trace-pace",
        "playwright-trace-gallery",
        trace_controls,
        region=".lf-trace-pace",
    ),
    State("trace-image-scale", "playwright-trace-gallery", trace_image_scale),
    State(
        "motion-controls",
        "motion",
        motion_controls,
        region="#fold-motion .lf-motion-controls",
    ),
    State(
        "timeline-steps",
        "lost-update",
        timeline_steps,
        region="#race .lf-timeline-controls",
    ),
    State(
        "trace-timeline-keyboard",
        "playwright-trace-gallery",
        trace_timeline_by_keyboard,
    ),
    State(
        "trace-image-keyboard",
        "playwright-trace-gallery",
        trace_image_by_keyboard,
        region="#release-trace .lf-trace-canvas",
    ),
    State("retained-quote", "feature-gallery", retained_quote),
    State("retained-quote-full", "feature-gallery", retained_quote_full),
    State(
        "topic-contents",
        "feature-gallery",
        topic_contents,
        region="#bg-topic-contents",
    ),
    # The contents map draws only in a document's sidebar narrowed to it, beside a
    # `.layout-column` under a mouse. No example draws one, so these states read a
    # fixture built that way.
    State(
        "contents-map-keyboard",
        "sidebar-contents",
        contents_by_keyboard,
    ),
    State(
        "contents-marks", "sidebar-contents", contents_marks, region="#rotation-route"
    ),
    State(
        "contents-marks-changes",
        "sidebar-contents",
        contents_marks_changes,
        region="#rotation-route",
    ),
    State("playground-controls", "notification-playground", playground_controls),
    State("playground-instruction", "notification-playground", playground_instruction),
    State("playground-inline-end", "motion-playground", page_end),
    State("playground-tall-stage", "alert-thresholds", playground_tall_stage),
    State(
        "playground-short-window", "data-explorer", page_end, window=Window((844, 390))
    ),
    State(
        "margin-gallery",
        "feature-gallery",
        margin_gallery,
        window=WINDOWS["phone"],
    ),
    State("release-draft", "release-notes", draft_edit),
    State("release-draft-long", "release-notes", draft_long_edit),
    State("release-draft-hover", "release-notes", draft_hover, region="#rn-cli"),
    State(
        "gallery-tabs-overflow",
        "feature-gallery",
        overflowing_tabs,
        region="#bg-rollout-tabs",
    ),
    State("gallery-tab-focus", "feature-gallery", tab_by_keyboard),
    State("gallery-tab-hover", "feature-gallery", tab_by_pointer),
    State("gallery-boxed-tab-focus", "feature-gallery", boxed_tab_by_keyboard),
    State(
        "boxed-tab-panel-keyboard",
        "feature-gallery",
        boxed_tab_panel_by_keyboard,
        region="#bg-tabs",
    ),
    State("side-tab-focus", "alert-review", tab_by_keyboard),
    State("frame-edges", "feature-gallery", frame_edges),
    State("gallery-metrics", "feature-gallery", gallery_metrics),
    State("chart-preview", "feature-gallery", chart_preview, region="#bg-chart"),
    State("gallery-plans", "feature-gallery", gallery_plans),
    State(
        "gallery-drawing",
        "feature-gallery",
        gallery_drawing,
        region="#bg-drawing-figure",
    ),
    State("gallery-ask-figure", "feature-gallery", gallery_ask_figure),
    State("gallery-theme", "feature-gallery", theme_hierarchy),
    State("widget-inline-hints", "feature-gallery", widget_inline_hints),
    State("gallery-wide-passage", "feature-gallery", wide_passage),
    State(
        "gallery-wide-schedule",
        "feature-gallery",
        wide_schedule,
        window=Window((1726, 900)),
    ),
    State("gallery-multiline-passage", "feature-gallery", multiline_passage),
    State("plan-execution", "review-a-plan", plan_execution, region="#plan-execute"),
    State("plan-caveat", "review-a-plan", plan_caveat, region="#plan-network"),
    State("page-search", "review-a-plan", page_search, region=PANEL),
    State(
        "accepted-page-search",
        "review-a-plan",
        accepted_page_search,
        region=PANEL,
    ),
    State("selected-passage-responses", "review-a-plan", selected_passage_responses),
    State("command-reference", "review-a-plan", command_reference),
    State("command-reference-search", "review-a-plan", command_reference_search),
    State("command-reference-scrolled", "review-a-plan", command_reference_scrolled),
    State("page-map", "review-a-plan", page_map, region=".lf-page-map-dialog"),
    State(
        "page-map-scrolled",
        "ship-review",
        page_map_scrolled,
        region=".lf-page-map-dialog",
        window=Window((1440, 360)),
    ),
    # Its threads on the user's turn, tinted and saying so at their ends.
    State("page-map-turn", "ship-review", page_map, region=".lf-page-map-dialog"),
    State("plan-card", "review-a-plan", card_by_pointer),
    State("control-preview", "review-a-plan", control_preview),
    State("thread-preview", "review-a-plan", thread_preview),
    State("passage-reaction", "review-a-plan", passage_reaction),
    State("age-preview", "review-a-plan", age_preview),
    State("link-preview", "feature-gallery", link_preview),
    State("reaction-palette", "ship-review", reaction_palette),
    State("reaction-pressed", "ship-review", reaction_pressed),
    State(
        "margin-reaction-choices",
        "release-notes",
        margin_reaction_choices,
        region=MARGIN_SUGGESTION,
    ),
    State(
        "margin-reaction-mark",
        "release-notes",
        margin_reaction_mark,
        region=MARGIN_SUGGESTION,
    ),
    State("plan-card-keyboard", "review-a-plan", card_by_keyboard),
    State(
        "plan-card-cluster-resolved",
        "review-a-plan",
        card_cluster_resolved,
        region=".lf-margin-preview",
    ),
    State(
        "ship-card-next-unread",
        "ship-review",
        card_next_unread,
        region=".lf-margin-preview",
    ),
    State(
        "ship-card-next-unread-cluster",
        "ship-review",
        card_next_unread_cluster,
        region=".lf-margin-preview",
    ),
    State(
        "ship-card-answer-at-cap",
        "ship-review",
        card_answer_at_cap,
        region=".lf-margin-preview",
    ),
    State(
        "ship-card-new-reply",
        "ship-review",
        card_new_reply,
        region=".lf-margin-preview",
    ),
    # A window with room for the rail but none beside the ask, so the card stands over
    # its options and covers a choice's hint.
    State(
        "thread-choice-hints-card",
        "thread-choice-hints",
        card_by_keyboard,
        window=Window((1000, 838)),
        region=".lf-margin-preview",
    ),
    State("plan-card-reply", "review-a-plan", card_reply),
    State(
        "plan-card-reply-photo",
        "review-a-plan",
        card_reply_photo,
        region=".lf-margin-preview .lf-thread-reply",
    ),
    State(
        "plan-card-after-interjection",
        "review-a-plan",
        card_after_interjection,
        region=".lf-margin-preview",
    ),
    State("plan-card-aging", "review-a-plan", card_aging, region=".lf-margin-preview"),
    # A window with no room beside the stop's words, so its card stands under them and
    # holds what would move the reply the user drafts (thread-preview.js,
    # `endNewsMoves`); beside them, it shows the news at once.
    State(
        "plan-card-held-news",
        "review-a-plan",
        card_held_news,
        window=Window((1200, 900)),
        region=".lf-margin-preview",
    ),
    State(
        "plan-card-held-step",
        "review-a-plan",
        card_held_step,
        window=Window((1200, 900)),
        region=".lf-margin-preview",
    ),
    State(
        "hub-seat-held-news",
        "command-hub",
        seat_held_news,
        region="#goal-parser .lf-page-thread",
    ),
    State(
        "plan-card-reply-large",
        "review-a-plan",
        card_reply_large,
        window=Window((1440, 600)),
    ),
    State("plan-panel", "review-a-plan", go_to_threads),
    State("plan-panel-keyboard", "review-a-plan", panel_by_keyboard),
    State("plan-go-to", "review-a-plan", go_to, window=Window((1024, 768))),
    State(
        "plan-thread-in-panel",
        "review-a-plan",
        thread_by_marker,
        window=WINDOWS["phone"],
    ),
    State("plan-more", "review-a-plan", more_menu),
    State("plan-capture", "review-a-plan", capture_area),
    State(
        "plan-capture-drag",
        "review-a-plan",
        capture_small_drag,
        window=Window((390, 740)),
    ),
    State(
        "plan-versions-touch",
        "review-a-plan",
        versions_menu,
        window=WINDOWS["phone"],
    ),
    State("all-pages", "review-a-plan", all_pages, region=".lf-fp-opened"),
    State("plan-card-reply-long", "review-a-plan", card_reply_long),
    State("plan-panel-reply-long", "review-a-plan", panel_reply_long),
    State("plan-page-comment-long", "review-a-plan", page_comment_long),
    State(
        "plan-page-comment-empty",
        "review-a-plan",
        page_comment_empty,
        region=".lf-fp-row",
    ),
    State(
        "plan-page-comment-resting",
        "review-a-plan",
        page_comment_resting,
        region=".lf-fp-row",
    ),
    State(
        "plan-card-reply-empty",
        "review-a-plan",
        card_reply_empty,
        region=".lf-margin-preview .lf-thread-reply",
    ),
    State(
        "plan-card-rewrite-empty",
        "review-a-plan",
        card_rewrite_empty,
        region=".lf-margin-preview .lf-msg:has(:focus)",
    ),
    State(
        "plan-panel-reply-empty",
        "review-a-plan",
        panel_reply_empty,
        region=".lf-fp-row",
    ),
    State(
        "plan-panel-dictating", "review-a-plan", panel_dictating, region=".lf-fp-row"
    ),
    State("plan-option-empty", "review-a-plan", option_empty, region=".lf-another"),
    State(
        "proxy-note-own-annotations",
        "page-annotations",
        proxy_note_own_annotations,
    ),
    State("proxy-note-paragraph", "pr-walkthrough", proxy_note_paragraph),
    State("proxy-note-row", "pr-walkthrough", proxy_note_row),
    State("proxy-drawing", "pr-walkthrough", proxy_drawing),
    State("proxy-part", "pr-walkthrough", proxy_part),
    State("proxy-gloss", "pr-walkthrough", proxy_gloss),
    State("plan-card-reply-resolved", "review-a-plan", card_reply_resolved),
    State("section-ring-keyboard", "review-a-plan", section_ring_by_keyboard),
    State(
        "plan-card-reply-resolved-elsewhere",
        "review-a-plan",
        card_reply_resolved_elsewhere,
        region=".lf-margin-preview",
    ),
    State("triage-composer", "triage-board", composer),
    State("triage-composer-send-focused", "triage-board", composer_send_focused),
    State(
        "triage-composer-empty",
        "triage-board",
        composer_empty,
        region=".lf-composer .lf-compose-field",
    ),
    State(
        "triage-composer-resting",
        "triage-board",
        composer_resting,
        region=".lf-fab-bar",
    ),
    State(
        "triage-composer-caret-motion",
        "triage-board",
        composer_caret_motion,
        region=".lf-fab-bar",
    ),
    State(
        "triage-composer-space",
        "triage-board",
        composer_space,
        window=Window((362, 900)),
    ),
    State(
        "triage-composer-scrolling",
        "triage-board",
        composer_scrolling,
        region=".lf-fab-bar",
    ),
    State("triage-composer-long", "triage-board", composer_long),
    State("triage-composer-sent", "triage-board", composer_sent),
    State(
        "plan-composer-sent-zoomed",
        "review-a-plan",
        composer_sent_zoomed,
        window=Window((1200, 900)),
    ),
    State("alert-queue-tally", "alert-review", tally_after_an_answer),
    State(
        "option-add-hover",
        "feature-gallery",
        option_add_hover,
        region="#bg-choice",
    ),
    State("alert-option-long", "alert-review", option_long),
    State("alert-options-in-pane", "alert-review", options_in_pane),
    State("ideas-ask", "ideas-to-implement", ask_by_keyboard),
    State(
        "pr-obligation-marker",
        "pr-walkthrough",
        obligation_marker_by_keyboard,
        region="#pr-approval-decision",
    ),
    State(
        "steps",
        "security-boundary",
        steps_in_view,
        region="#security-contract-list",
    ),
    State("stacked-disclosures", "security-boundary", disclosures_in_view),
    State(
        "security-flow",
        "security-boundary",
        security_flow,
        region="#security-before-flow",
    ),
    State(
        "breakout-captions-scrolled",
        "breakout-table-caption",
        breakout_captions_scrolled,
        window=Window(WINDOWS["phone"].size),
    ),
    State(
        "table-scrolled-sideways",
        "security-boundary",
        table_scrolled_sideways,
        window=Window(WINDOWS["phone"].size),
        region="#security-vendor-table",
    ),
    State("triage-grabbed", "triage-board", card_grabbed),
    State("triage-moved", "triage-board", card_moved, region="#release-board"),
    State(
        "triage-moved-touch",
        "triage-board",
        card_moved_by_destination,
        window=WINDOWS["phone"],
        region="#col-blocking",
    ),
    State("walkthrough-body", "pr-walkthrough", into_the_body),
    State(
        "progress-body-short", "live-progress", into_the_body, window=Window((900, 600))
    ),
    State("walkthrough-calls", "pr-walkthrough", call_tree, region="#pr-call-diagram"),
    State("diagram-flow", "pr-walkthrough", diagram_flow, region="#pr-flow-diagram"),
    State("diagram-shape-comment", "pr-walkthrough", diagram_shape_comment),
    State("walkthrough-code", "pr-walkthrough", code_note),
    State("walkthrough-diff-comment", "pr-walkthrough", diff_line_composer),
    State("walkthrough-copy-hover", "pr-walkthrough", code_copy_by_pointer),
    State("walkthrough-copy-keyboard", "pr-walkthrough", code_copy_by_keyboard),
    State(
        "walkthrough-path-keyboard",
        "pr-walkthrough",
        diff_path_by_keyboard,
        window=Window(WINDOWS["phone"].size),
    ),
    State(
        "walkthrough-diff-source-pointer",
        "pr-walkthrough",
        diff_source_by_pointer,
        window=Window((600, 900)),
        region="#pr-exact-patch .lf-diff-file:has(code[data-code])",
    ),
    State(
        "walkthrough-diff-source-keyboard",
        "pr-walkthrough",
        diff_source_by_keyboard,
        window=Window((600, 900)),
        region="#pr-exact-patch .lf-diff-file:has(code[data-code])",
    ),
    State(
        "walkthrough-source-touch",
        "pr-walkthrough",
        code_source_by_touch,
        window=WINDOWS["phone"],
    ),
    State("ship-thread", "ship-review", element_thread),
    State(
        "ship-card-ask-keyboard",
        "ship-review",
        card_ask_by_keyboard,
        region=".lf-margin-preview",
    ),
    State(
        "ship-card-message-keyboard",
        "ship-review",
        card_message_by_keyboard,
        region=".lf-margin-preview",
    ),
    State("ship-tasks", "ship-review", ship_tasks, region="#off-readiness"),
    State("ship-answered", "ship-review", ship_answered, region=".lf-fp-opened"),
    State(
        "ship-thread-open", "ship-review", element_thread_open, region="#off-t-vendor"
    ),
    State(
        "ship-option-thread-open",
        "ship-review",
        option_thread_open,
        region="#off-workaround-review",
    ),
    State(
        "ship-card-more-room", "ship-review", card_more_room, window=Window((1440, 600))
    ),
    State(
        "ship-card-short-window",
        "ship-review",
        card_by_pointer,
        window=Window((1440, 480)),
    ),
    State("on-me-question", "review-a-plan", on_me_question),
    State("on-me", "corpus", on_me),
    State("on-agent", "corpus", on_agent),
    State("hub-on-me", "command-hub", on_me),
    State("hub-choice", "command-hub", on_me_choice),
    State("hub-choice-answered", "command-hub", on_me_choice_answered),
    State("hub-on-agent", "command-hub", on_agent),
    State("hub-workers", "command-hub", hub_workers),
    State("sort-pane", "rust-sort", pane_focused),
    State("sort-aim-cut", "rust-sort", aim_cut_by_pane),
    # Each page the corpus composes, as it loads, named after its file.
    *(State(source.stem, source.stem) for source in corpus_sources()),
)
