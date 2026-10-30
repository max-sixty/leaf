"""Screenshot a fixed catalogue of UI states on BASE_REF's runtime and HEAD's, and
show which ones changed.

    uv run leaf-dev stills [BASE_REF] [--state NAME]... [--authored]

BASE_REF defaults to the merge base of HEAD and `main`; each arm is the payload at its
commit (`leaf_dev.arms.build_pair`), so commit what you want compared. Each page is
built from this checkout's example source and served by the arm's own launcher, so
only the runtime, theme and server differ between the two stills of a state. With
`--authored`, each arm instead reads its own committed example and companions, so
changes to page markup are visible as well. Each
capture starts with a fresh authored fixture and event log, so a prior gesture cannot
change another state's initial condition.
Message delivery belongs to thread_journey and test_render_thread_snapshots, whose
held checkpoints capture a send before its POST completes; a still cannot hold one.

A state is an example, a viewport, a color scheme and a pointer, and the input that
brings a fresh tab there (`DRIVERS`, which `leaf-dev probe --do drive:NAME` also runs).
The catalogue (`STATES`) covers states a user reaches by acting, not only pages at rest;
add one where a change touches a surface it does not reach. A state may name a
region whose before/after bounds frame the comparison, retaining related controls
without shrinking their details behind unrelated viewport changes. Raw screenshots
always preserve the full viewport and its geometry.
Use repeated `--state` options to compare only the states a change touches.

Whether a state changed, and where, is `lf-shot`'s reading of its two stills, from the
module that owns the rule (the default package's `widgets/image-difference.js`),
loaded into the browser.
Each invocation allocates a run directory under `.tmp/stills/`. Each state's
directory within it holds `base.png` and `head.png`, and for a
change `base-crop.png` and `head-crop.png` cropped to the union of its regions (or
whole, when the reading names none), ready to hand off as an `lf-shot` pair, and
`diff.png` outlining the head's own regions, a change in red and a move in blue. The
crops cover both stills' regions.

Beside each pair, the command reads the cascade a screenshot only shows in part: the
computed `STYLED` properties of every element in the document and its open shadow
trees, hidden ones included, so the corpus states read every page it composes (a
rule that depends on a page's own Layout, such as a sidebar page's panels, reads only
on that page's states).
Elements are keyed by their path of tags, ids and first two classes. A state with a
differing property, or a subtree only one arm has, also counts as changed, and its
`styles.txt` lists them (`style_changes`). The properties are the cascade's own, not
the geometry it produces, which the stills show; width, height and offsets stay out
because they move with every reflow. Below them, for each group's first element, it
lists the declarations Chromium's inspector reads as matching it in only one arm, or
in another order, each with its sheet, layers, scope and selector
(`declaration_changes`): the rule a change added, removed, edited or moved. Where none
differ, the element inherits the difference or reads it from a custom property.

Across the run, the command also collects each arm's faces: the family, size, weight,
style, tracking and case of every shown element that holds words of its own, in the
states both arms completed. The run's `faces.txt` lists each face only one arm draws,
with the elements that wear it and the other arm's nearest face (`face_changes`). A
change that reuses Leaf's faces adds none, so a new face half a pixel or a hundred of
weight from its nearest is usually a drift to fold into that face. A consolidation
lists the faces it retired.

Capture and comparison failures are reported per state, with tracebacks in its
directory; the remaining states still run. Only complete pairs enter the
comparison. Arm construction, browser setup failures, and interrupts end the command.
"""

import json
import re
import tempfile
import traceback
from collections.abc import Callable, Generator, Iterable
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import click
from PIL import Image, ImageDraw
from playwright.sync_api import Locator, Page, expect

from leaf.render_checks import wait_until_ready
from leaf_dev import ROOT
from leaf_dev.arms import (
    PageClient,
    build_pair,
    copy_committed,
    run_directory,
    served_page,
    serving_source,
)
from leaf_dev.browser import (
    BESIDE,
    DESKTOP,
    go_to_threads,
    headless_shell,
    load,
    scroll_settled,
    settle,
    tab,
)

OUT = ROOT / ".tmp" / "stills"
CROP_MARGIN = 32
DIFFERENCE = ROOT / "packages" / "default" / "widgets" / "image-difference.js"
# Where `differences` serves the stills and the module that compares them.
ORIGIN = "http://stills.invalid"
OPEN_CARD = "() => document.querySelector('.lf-margin-preview:not([hidden])')"
# The computed properties `style_changes` compares: the faces, boxes and flow a rule
# sets, not the layout it produces.
STYLED = [
    "color",
    "background-color",
    "background-image",
    "border-top-width",
    "border-right-width",
    "border-bottom-width",
    "border-left-width",
    "border-top-style",
    "border-right-style",
    "border-bottom-style",
    "border-left-style",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "border-top-left-radius",
    "border-top-right-radius",
    "border-bottom-right-radius",
    "border-bottom-left-radius",
    "box-shadow",
    "outline-style",
    "outline-width",
    "outline-color",
    "outline-offset",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "font-variant-numeric",
    "line-height",
    "letter-spacing",
    "text-transform",
    "text-align",
    "text-decoration-line",
    "text-decoration-color",
    "text-underline-offset",
    "text-wrap-style",
    "white-space",
    "overflow-wrap",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "display",
    "position",
    "max-width",
    "min-width",
    "max-height",
    "overflow-x",
    "overflow-y",
    "vertical-align",
    "list-style-type",
    "gap",
    "flex-direction",
    "align-items",
    "justify-content",
    "color-scheme",
    "container-type",
    "opacity",
    "visibility",
    "cursor",
    "box-sizing",
    "z-index",
]
# Every element's `STYLED` values by its path, sharing each distinct set of values, the
# paths of the shown elements with words of their own, and the elements themselves by
# path on `window.stillsRead`, for `declarations`.
STYLES = """(properties) => {
  const skip = new Set(["head", "script", "style", "template", "link", "meta"]);
  const faces = new Map();
  const elements = {};
  const texts = [];
  const read = (window.stillsRead = new Map());
  const walk = (parent, prefix) => {
    const seen = {};
    for (const element of parent.children) {
      if (skip.has(element.localName)) continue;
      const label = element.localName + (element.id
        ? `#${element.id}`
        : [...element.classList].slice(0, 2).map((name) => `.${name}`).join(""));
      seen[label] = (seen[label] ?? -1) + 1;
      const key = prefix + label + (seen[label] ? `:${seen[label]}` : "");
      const style = getComputedStyle(element);
      const face = JSON.stringify(properties.map((name) => style.getPropertyValue(name)));
      if (!faces.has(face)) faces.set(face, faces.size);
      elements[key] = faces.get(face);
      read.set(key, element);
      const words = [...element.childNodes].some(
        (node) => node.nodeType === Node.TEXT_NODE && node.data.trim(),
      );
      if (words && element.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
        texts.push(key);
      walk(element, `${key} > `);
      if (element.shadowRoot) walk(element.shadowRoot, `${key} >> `);
    }
  };
  walk(document, "");
  return { faces: [...faces.keys()].map((face) => JSON.parse(face)), elements, texts };
}"""
# The computed properties that make a face, the voice a run of words is set in, which
# `face_changes` compares across a run.
FACE = [
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "letter-spacing",
    "text-transform",
]


def at_rest(page: Page) -> None:
    """The page as it loads."""


def worktree_summaries(page: Page) -> None:
    """Close the initially open worktree so the list's summary columns stand together."""
    page.locator("#worktree-example-worktree-0 > details > summary").click()
    expect(
        page.locator("#worktree-example-worktree-0 > details")
    ).not_to_have_attribute("open")


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


def native_code(page: Page) -> None:
    """Native fenced code using short language labels."""
    page.locator("#bg-gallery-tabs").get_by_role(
        "tab", name="Page & layout", exact=True
    ).click()
    page.locator("#bg-javascript-code").scroll_into_view_if_needed()


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
    """The page's link as a readonly field reached by keyboard, where the leaf's menu
    leaves it to select under About because the clipboard refused the copy."""
    page.evaluate(
        "() => { Clipboard.prototype.writeText ="
        " () => Promise.reject(new Error('refused')); }"
    )
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu").get_by_role("menuitem", name="Copy link").click()
    link = page.locator(".lf-fp-menu[data-level=group]").get_by_label(
        "Link", exact=True
    )
    page.keyboard.press("Shift")  # keyboard modality, so focus is drawn
    link.focus()
    expect(link).to_be_focused()


def diff_filter(page: Page) -> None:
    """A nonempty file filter with Clear and its match count inside one field."""
    field = page.locator("#pr-key-hunk").get_by_role(
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
    page.locator('.lf-fp-item[data-row="inspection"]').click()
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
    page.locator(f'.lf-fp-thread[data-key="{key}"]').click()
    expect(page.locator(".lf-fp-view[data-view=thread] .lf-msg").first).to_be_visible()


def floating_thread(page: Page) -> None:
    """The floating panel with a thread opened from Threads: the thread's title over
    its view, and under it, on the row, the way back, Show on page, Resolve and Close."""
    go_to_threads(page)
    page.locator(".lf-fp-thread", has_text="One reconnect in forty").click()
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()


def floating_thread_unread(page: Page) -> None:
    """The same thread holding a reply too long for its view to show whole, which stays
    unread, so Next unread stands among the view's controls."""
    as_agent(
        "thread",
        "reply",
        "7b3e0a41",
        "--text",
        "The resend recovers every one of them. "
        + "The queue holds each edit until the server confirms it. " * 40,
    )
    floating_thread(page)
    expect(page.locator(".lf-fp-controls .lf-fp-next-unread")).to_be_visible()


def floating_thread_retitled(page: Page) -> None:
    """The same thread once its opening message is rewritten short, so its title is far
    narrower than the view it names."""
    floating_thread(page)
    page.locator(".lf-fp-view[data-view=thread] .lf-msg-body").first.dblclick()
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
    page.locator("#race-before .lf-timeline-controls").scroll_into_view_if_needed()


def card_by_pointer(page: Page) -> None:
    """The first margin card, opened by a click on its marker."""
    open_card(page, page.locator(".lf-margin-marker").first)


def open_card(page: Page, marker: Locator) -> None:
    """The margin card `marker` opens, by a click on it. The margin is fixed to the
    window and anchored to the page, so Playwright's scroll into view leaves a marker
    below the window where it is: the page scrolls it up instead."""
    marker.evaluate(
        "m => { const box = m.getBoundingClientRect();"
        " if (box.top < 0 || box.bottom > innerHeight)"
        " scrollBy(0, box.top - innerHeight / 3); }"
    )
    settle(page)
    marker.click()
    page.wait_for_function(OPEN_CARD)


def card_by_keyboard(page: Page) -> None:
    """The first margin card, opened by Enter on its marker, so its thread holds a
    visible focus."""
    page.keyboard.press("Tab")  # keyboard modality, so focus is drawn
    page.locator(".lf-margin-marker").first.focus()
    page.keyboard.press("Enter")
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
    page.locator(".lf-fp-thread:not([data-resolved])").last.click()
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
    page.locator(".lf-fp-field leaf-text").click()
    expect(page.locator(".lf-fp-field leaf-text")).to_be_focused()


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


def card_reply_resolved_elsewhere(page: Page) -> None:
    """An agent resolves the thread while the user keeps writing in its margin card."""
    card_reply(page)
    card = page.locator(".lf-margin-preview .lf-page-thread")
    root = card.get_attribute("data-thread")
    assert root
    as_agent("thread", "resolve", root)
    expect(card.locator(".lf-reopen")).to_be_visible()


def as_agent(command: str, verb: str, *args: str) -> None:
    """Run `leaf COMMAND VERB PAGE ARGS` as the agent on the page being served, with
    its arm's launcher."""
    served = served_page.get()
    served.leaf(command, verb, str(served.directory), *args)


def held_news(page: Page, thread: Locator) -> None:
    """News arriving in `thread` while the user drafts a reply there: the agent's reply
    and the user's own message from another tab, which the thread holds behind its
    notice (held-news.js)."""
    thread.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.insert_text("Drafting a reply while the news arrives")
    root = thread.get_attribute("data-thread")
    assert root
    as_agent("thread", "reply", root, "--text", "That one goes first.")
    notice = thread.locator(".lf-thread-news")
    expect(notice).to_have_attribute("title", "1 new reply")
    client = PageClient(served_page.get().address)
    client.post(
        {
            "kind": "reply",
            "parent": root,
            "revision": client.state()["active"]["revision"],
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
    root = thread.get_attribute("data-thread")
    assert root
    as_agent("thread", "reply", root, "--ephemeral", "--text", "Checking the stop.")
    state = PageClient(served_page.get().address).state()
    wait_until_ready(page, state, through="state")


def seat_held_news(page: Page) -> None:
    """A seat's thread holding a reply and a message from another tab while the user
    drafts a reply in it: the agent's question on a goal, which a reload draws in
    place."""
    as_agent(
        "thread", "create", "--section", "goal-parser", "--text", "Which worker first?"
    )
    load(page, served_page.get().address)
    thread = page.locator("#goal-parser .lf-page-thread")
    thread.scroll_into_view_if_needed()
    held_news(page, thread)


def option_picked(page: Page) -> None:
    """The panel's row just after the plan's rollout option is picked and admitted,
    while a passing notice would still stand in its status seat."""
    option = page.locator("#plan-admin")
    option.scroll_into_view_if_needed()
    option.click()
    expect(page.locator(".lf-live")).to_contain_text("— sent")


def option_references(page: Page) -> None:
    """The patch decision, whose two options both name the stall block above them."""
    page.locator("#off-workaround-review").scroll_into_view_if_needed()


def on_me(page: Page) -> None:
    """On me, opened from the floating panel's On me mark."""
    page.locator(".lf-fp-on-user").click()
    expect(page.locator(".lf-fp-view[data-view=queue]")).to_be_visible()


def on_me_choice(page: Page) -> None:
    """A described choice card in On me, before answering."""
    on_me(page)
    card = page.locator('.lf-fp-on-item[data-obligation="widget:decision-dedupe"]')
    card.scroll_into_view_if_needed()


def on_me_choice_answered(page: Page) -> None:
    """The result and Undo replacing a described choice on its retained card."""
    on_me_choice(page)
    card = page.locator('.lf-fp-on-item[data-obligation="widget:decision-dedupe"]')
    card.locator(".lf-fp-answer").first.click()
    expect(card.locator(".lf-fp-said")).to_contain_text("Answered:")


def on_agent(page: Page) -> None:
    """The On view turned to the agent's tab."""
    on_me(page)
    page.locator(".lf-fp-filters button").filter(
        has_text=re.compile(r"^\s*On (?!me)")
    ).first.click()
    expect(page.locator(".lf-fp-view[data-view=queue]")).to_be_visible()


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


def command_reference_search(page: Page) -> None:
    """Help's focused query above its filtered command results."""
    page.keyboard.press("Tab")
    page.keyboard.press("?")
    page.keyboard.press("?")
    page.get_by_role("combobox", name="Search commands").fill("comment")


def page_map(page: Page) -> None:
    """The Page Map over a plan's threads, questions and controls: its title, its
    groups' headings and its rows' ends."""
    page.keyboard.press("Tab")
    page.keyboard.press("g")
    page.keyboard.press("Shift+P")
    expect(page.locator(".lf-page-map-dialog[open]")).to_be_visible()


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
    child.locator('.lf-fp-thread[data-key="bg-retained-quote-thread"]').click()
    expect(child.locator(".lf-fp-view[data-view=thread] .lf-msg").first).to_be_visible()


def retained_quote_full(page: Page) -> None:
    """The same original words opened locally. Full quote shows a frame after the
    thread's messages, once the panel has measured the quotation as cut, so the click
    waits for it."""
    retained_quote(page)
    child = page.locator("#bg-retained-quote-sample").frame_locator("iframe")
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
    shot.get_by_role("button", name="Pair", exact=True).click()
    shot.locator(".lf-shot-toolbar").evaluate(
        "node => node.scrollIntoView({block: 'start'})"
    )


def screenshot_slider_before(page: Page) -> None:
    """One source fills the slider while change outlines locate its evidence."""
    screenshot_comparison(page)
    shot = page.locator("#bg-shot")
    shot.evaluate("async node => await node.difference")
    shot.get_by_role("button", name="Slider", exact=True).click()
    divider = shot.get_by_role("scrollbar")
    divider.focus()
    page.keyboard.press("End")
    shot.get_by_role("button", name="Outline changes", exact=True).click()
    shot.scroll_into_view_if_needed()


def screenshot_pixels(page: Page) -> None:
    """Pixel evidence occupies the image frame without a separate legend row."""
    screenshot_comparison(page)
    shot = page.locator("#bg-shot")
    shot.get_by_role("button", name="Pixels", exact=True).click()


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
    picture = page.locator(".lf-fp-view[data-view=thread] .lf-message-media img").first
    picture.evaluate("image => image.decode()")
    picture.scroll_into_view_if_needed()


def image_preview(page: Page) -> None:
    """Inspect the gallery's pasted screenshot through the shared image viewer."""
    open_thread(page, "2be2443f0bb6cc49fc86b52f340e6073")
    page.locator(".lf-fp-view[data-view=thread] .lf-media-open").first.click()
    page.get_by_role("dialog", name="Image preview").wait_for(state="visible")
    page.wait_for_function("""() => {
      const zoom = document.querySelector('.lf-media-viewer-zoom');
      return !zoom || zoom.getAttribute('aria-disabled') !== 'true';
    }""")


def panel_by_keyboard(page: Page) -> None:
    """Threads, opened by Go to Threads, with keyboard focus on its view."""
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-fp-view[data-view=threads]')"
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
        page.locator('.lf-fp-field leaf-text[data-says="selection"]').click()


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
    page.locator(".lf-fp-thread:not([data-resolved])").last.click()
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
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
    """A queue's tally after Next on me and one answer: the count down by one, the
    answered row's check above the open marks, and Next on me's second obligation open."""
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


def gallery_plans(page: Page) -> None:
    """Planned work beside observed history, using authored stable section identity."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    page.locator("#bg-plans-and-history").scroll_into_view_if_needed()


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
    head = page.locator("#pr-exact-patch .lf-diff-head[data-path-cut]").first
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
    paint over a target cut where the pane cuts the target."""
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
        "() => document.querySelector('.lf-aim')?.dataset.for === 'sort-source-note'"
    )


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
    """On me once the user has pressed Done in the reconnect thread and picked the
    release: what still waits on them."""
    card_by_pointer(page)
    page.locator(".lf-margin-preview:not([hidden]) .lf-done").click()
    page.keyboard.press("Escape")
    page.locator("#off-release-ship").click()
    page.locator(".lf-fp-on-user").click()
    expect(page.locator(".lf-fp-opened")).to_be_visible()


def card_message_by_keyboard(page: Page) -> None:
    """The agent's question in a margin card, reached by Next on me (`m`), which
    focuses the message, so its card wears the ring."""
    for _ in range(4):
        page.keyboard.press("m")
        settle(page)
        if page.evaluate(
            "() => document.activeElement?.matches('.lf-margin-preview .lf-msg')"
        ):
            return
    raise AssertionError("Next on me never reached a card's message")


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
    """The leaf's menu, opened: the agent's state at its head over the page's
    controls."""
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu").wait_for()


def capture_menu(page: Page) -> None:
    """Capture area, chosen from the leaf menu's Annotations."""
    more_menu(page)
    page.locator('.lf-fp-item[data-row="group:annotate"]').click()
    page.locator('.lf-fp-item[data-row="command:capture.region.open"]').click()


def capture_area(page: Page) -> None:
    """Draw a page area, held before the lift that would attach it, with the way out
    of area capture in the panel's row."""
    page.locator("#plan-context").scroll_into_view_if_needed()
    capture_menu(page)
    page.locator(".lf-region-selection").wait_for(state="visible")
    page.mouse.move(100, 200)
    page.mouse.down()
    page.mouse.move(360, 350, steps=4)


def capture_small_drag(page: Page) -> None:
    """Hold a small selection over words, which must remain visible during the drag."""
    page.locator("#plan-current").scroll_into_view_if_needed()
    capture_menu(page)
    page.locator(".lf-region-selection").wait_for(state="visible")
    target = page.locator("#plan-current").bounding_box()
    assert target is not None
    left, top = round(target["x"]) + 45, round(target["y"]) + 8
    page.mouse.move(left, top)
    page.mouse.down()
    page.mouse.move(left + 88, top + 44, steps=8)


def versions_menu(page: Page) -> None:
    """Versions, opened from the leaf's menu: a row for each version, with its note."""
    more_menu(page)
    page.locator('.lf-fp-item[data-row="versions"]').click()
    page.locator(".lf-fp-menu[data-level=versions] .lf-fp-version").first.wait_for()


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
    """Reveal the contents map with focus on its first section link."""
    page.keyboard.press("Tab")
    page.locator("lf-toc li a").first.focus()


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
    strip.locator('.lf-tabstrip-scroll[data-to="end"] > span').click()
    scroll_settled(page)


def contents_over_reading(page: Page) -> None:
    """Reveal the margin map over a section, including its title's background."""
    contents_by_keyboard(page)
    page.locator("lf-toc li a").first.press("Enter")
    page.locator("lf-toc .lf-toc-start a").focus()


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
    """Details beside the selected SVG commit in the merge film."""
    page.get_by_role("button", name="Inspect next element", exact=True).click()
    expect(page.locator("#merge-film .film-inspect")).to_be_visible()
    page.locator("#merge-film .film-stage").evaluate(
        "node => node.scrollIntoView({block: 'center'})"
    )


def live_sample_embedded(page: Page) -> None:
    """The arrived practice page at its embedded content height."""
    page.get_by_role("tab", name="Page & layout", exact=True).click()
    sample = page.locator("#bg-live-sample")
    expect(
        sample.frame_locator("iframe").locator("#bg-live-sample-copy")
    ).to_be_visible()
    sample.scroll_into_view_if_needed()


def interactive_sample(page: Page) -> None:
    """An interactive sample, whose widgets use this page's state, under its note."""
    page.locator("#bg-inline-sample").scroll_into_view_if_needed()


def live_sample_full_view(page: Page) -> None:
    """The same practice frame promoted into its native full-view dialog."""
    live_sample_embedded(page)
    sample = page.locator("#bg-live-sample")
    sample.get_by_role("button", name="Full view", exact=True).click()
    expect(sample.get_by_role("dialog", name="practice release note")).to_be_visible()


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
    page.locator("#race-before .lf-timeline-step").first.click()
    page.keyboard.press("Tab")
    page.keyboard.press("Space")


@dataclass(frozen=True)
class State:
    name: str
    source: str
    drive: Callable[[Page], None]
    viewport: tuple[int, int] = DESKTOP
    scheme: str = "light"
    touch: bool = False
    region: str | None = None


STATES = (
    State("page-about", "review-a-plan", page_about, region=".lf-inspection-dialog"),
    State(
        "page-about-dark",
        "review-a-plan",
        page_about,
        scheme="dark",
        region=".lf-inspection-dialog",
    ),
    State(
        "page-about-phone",
        "review-a-plan",
        page_about,
        viewport=(390, 844),
        touch=True,
        region=".lf-inspection-dialog",
    ),
    State("authored-timeline", "lost-update", at_rest, region="#race-before"),
    State(
        "authored-timeline-keyboard",
        "lost-update",
        authored_timeline_step,
        region="#race-before",
    ),
    State(
        "authored-timeline-dark",
        "lost-update",
        authored_timeline_step,
        scheme="dark",
        region="#race-before",
    ),
    State(
        "authored-timeline-phone",
        "lost-update",
        at_rest,
        viewport=(390, 900),
        touch=True,
        region="#race-before",
    ),
    State(
        "native-code",
        "developer/feature-gallery",
        native_code,
        region="#bg-javascript-code",
    ),
    State(
        "native-code-copy-hover",
        "developer/feature-gallery",
        native_code_copy_hover,
        region="#bg-javascript-code",
    ),
    State(
        "native-code-dark",
        "developer/feature-gallery",
        native_code,
        scheme="dark",
        region="#bg-javascript-code",
    ),
    State(
        "markdown-preview-scrolled",
        "developer/feature-gallery",
        markdown_preview_scrolled,
        region="#bg-markdown-preview",
    ),
    State(
        "markdown-preview-scrolled-dark",
        "developer/feature-gallery",
        markdown_preview_scrolled,
        scheme="dark",
        region="#bg-markdown-preview",
    ),
    State(
        "captured-source",
        "developer/feature-gallery",
        captured_source,
        region="#bg-source-captures",
    ),
    State(
        "recorded-video",
        "developer/feature-gallery",
        recorded_video,
        region="#bg-recorded-media",
    ),
    State(
        "recorded-video-dark",
        "developer/feature-gallery",
        recorded_video,
        scheme="dark",
        region="#bg-recorded-media",
    ),
    State(
        "recorded-video-keyboard",
        "developer/feature-gallery",
        recorded_video_by_keyboard,
        region="#bg-recorded-media",
    ),
    State(
        "panel-leaf",
        "developer/feature-gallery",
        panel_leaf,
        region=".lf-fp-leaf",
    ),
    State(
        "panel-leaf-phone-dark",
        "developer/feature-gallery",
        panel_leaf,
        viewport=(390, 844),
        scheme="dark",
        touch=True,
        region=".lf-fp-leaf",
    ),
    State("panel-status-hover", "review-a-plan", panel_status_hover),
    State("floating-thread", "ship-review", floating_thread, region=".lf-fp-opened"),
    State(
        "floating-thread-unread",
        "ship-review",
        floating_thread_unread,
        region=".lf-fp-opened",
    ),
    State(
        "floating-thread-unread-dark",
        "ship-review",
        floating_thread_unread,
        scheme="dark",
        region=".lf-fp-opened",
    ),
    State("ship-threads", "ship-review", go_to_threads, region=".lf-fp-opened"),
    State("plan-option-picked", "review-a-plan", option_picked, region=".lf-fp-row"),
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
        "ship-option-references-phone",
        "ship-review",
        option_references,
        viewport=(390, 844),
        region="#off-workaround-decision",
    ),
    State(
        "threads-returning", "ship-review", threads_returning, region=".lf-fp-opened"
    ),
    State(
        "threads-returning-phone",
        "ship-review",
        threads_returning,
        viewport=(390, 844),
        touch=True,
        region=".lf-fp-opened",
    ),
    State(
        "floating-thread-retitled",
        "ship-review",
        floating_thread_retitled,
        region=".lf-fp-opened",
    ),
    State(
        "playground-choice",
        "notification-playground",
        playground_choice,
        region="lf-playground label:has(> input:focus)",
    ),
    State(
        "playground-choice-phone-dark",
        "notification-playground",
        playground_choice,
        viewport=(390, 844),
        scheme="dark",
        touch=True,
        region="lf-playground label:has(> input:focus)",
    ),
    State(
        "trace-transport-icons",
        "developer/playwright-trace-gallery",
        trace_controls,
        viewport=(540, 720),
        region=".lf-trace-toolbar",
    ),
    State(
        "film-inspector",
        "wt-merge",
        film_inspector,
        viewport=(900, 900),
        region="#merge-film .film-stage",
    ),
    State(
        "film-inspector-phone",
        "wt-merge",
        film_inspector,
        viewport=(390, 844),
        touch=True,
        region="#merge-film .film-stage",
    ),
    State(
        "live-sample-embedded",
        "developer/feature-gallery",
        live_sample_embedded,
        region="#bg-live-sample",
    ),
    State(
        "live-sample-embedded-phone",
        "developer/feature-gallery",
        live_sample_embedded,
        viewport=(390, 844),
        touch=True,
        region="#bg-live-sample",
    ),
    State(
        "live-sample-full-view",
        "developer/feature-gallery",
        live_sample_full_view,
        region="#bg-live-sample .lf-sample-view",
    ),
    State(
        "interactive-sample",
        "developer/feature-gallery",
        interactive_sample,
        region="#bg-inline-sample",
    ),
    State(
        "trace-comparison-header",
        "review-a-fix",
        trace_comparison,
        viewport=(900, 900),
        region="#fix-before",
    ),
    State(
        "trace-comparison-header-phone",
        "review-a-fix",
        trace_comparison,
        viewport=(390, 844),
        touch=True,
        region="#fix-before",
    ),
    State("drawing-photo-comment", "developer/feature-gallery", drawing_photo_comment),
    State("page-comment-photo", "developer/feature-gallery", page_comment_photo),
    State(
        "page-comment-photo-hover",
        "developer/feature-gallery",
        page_comment_photo_hover,
    ),
    State(
        "page-comment-photo-hover-dark",
        "developer/feature-gallery",
        page_comment_photo_hover,
        scheme="dark",
    ),
    State("panel-corner-hover", "review-a-plan", panel_corner_hover),
    State("share-link", "developer/feature-gallery", share_link, region=".lf-fp-menu"),
    State("share-link-dark", "developer/feature-gallery", share_link, scheme="dark"),
    State(
        "diff-filter",
        "pr-walkthrough",
        diff_filter,
        region="#pr-key-hunk .lf-diff-tools",
    ),
    State(
        "diff-separator",
        "pr-walkthrough",
        diff_separator,
        region="#pr-key-hunk .lf-diff-rows",
    ),
    State(
        "diff-filter-phone-dark",
        "pr-walkthrough",
        diff_filter,
        viewport=(390, 844),
        scheme="dark",
        touch=True,
        region="#pr-key-hunk .lf-diff-tools",
    ),
    State(
        "playground-text",
        "notification-playground",
        playground_text,
        region='lf-playground-control:has(> input[type="text"])',
    ),
    State(
        "playground-text-dark",
        "notification-playground",
        playground_text,
        scheme="dark",
    ),
    State("drawing-comment", "developer/feature-gallery", drawing_comment),
    State(
        "drawing-comment-dark",
        "developer/feature-gallery",
        drawing_comment,
        scheme="dark",
    ),
    State("drawing-comment-hover", "developer/feature-gallery", drawing_comment_hover),
    State(
        "drawing-comment-hover-dark",
        "developer/feature-gallery",
        drawing_comment_hover,
        scheme="dark",
    ),
    State(
        "drawing-comment-keyboard",
        "developer/feature-gallery",
        drawing_comment_keyboard,
    ),
    State(
        "drawing-comment-touch",
        "developer/feature-gallery",
        drawing_comment,
        viewport=(390, 844),
        touch=True,
    ),
    State("progress-messages", "developer/feature-gallery", progress_messages),
    State(
        "progress-messages-touch",
        "developer/feature-gallery",
        progress_messages,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "screenshot-comparison",
        "developer/feature-gallery",
        screenshot_comparison,
        region="#bg-shot",
    ),
    State(
        "screenshot-pair",
        "developer/feature-gallery",
        screenshot_pair,
        region="#bg-shot",
    ),
    State(
        "screenshot-slider-before",
        "developer/feature-gallery",
        screenshot_slider_before,
        region="#bg-shot",
    ),
    State(
        "screenshot-pixels",
        "developer/feature-gallery",
        screenshot_pixels,
        region="#bg-shot",
    ),
    State(
        "screenshot-options",
        "developer/feature-gallery",
        screenshot_options,
        region="#bg-shot",
    ),
    State(
        "screenshot-comparison-compact",
        "developer/feature-gallery",
        screenshot_comparison,
        viewport=(544, 844),
        region="#bg-shot",
    ),
    State(
        "screenshot-comparison-phone",
        "developer/feature-gallery",
        screenshot_comparison,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "image-in-page",
        "developer/feature-gallery",
        image_in_page,
        region="#bg-image-preview",
    ),
    State(
        "thread-picture",
        "developer/feature-gallery",
        thread_picture,
        region=".lf-fp-opened",
    ),
    State("image-preview", "developer/feature-gallery", image_preview),
    State(
        "image-preview-dark", "developer/feature-gallery", image_preview, scheme="dark"
    ),
    State(
        "image-preview-phone",
        "developer/feature-gallery",
        image_preview,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "visual-review-inspection",
        "developer/visual-review-gallery",
        visual_review_inspection,
    ),
    State("visual-review", "developer/visual-review-gallery", at_rest),
    State("diff-file-threads", "developer/diff-thread-gallery", at_rest),
    State("diff-long-lines", "developer/diff-thread-gallery", diff_long_lines),
    State(
        "diff-author-notes",
        "developer/diff-thread-gallery",
        diff_author_notes,
        region="#dfg-scroll",
    ),
    State(
        "diff-author-notes-dark",
        "developer/diff-thread-gallery",
        diff_author_notes,
        scheme="dark",
        region="#dfg-scroll",
    ),
    State(
        "diff-author-notes-touch",
        "developer/diff-thread-gallery",
        diff_author_notes,
        viewport=(390, 844),
        touch=True,
        region="#dfg-scroll",
    ),
    State("worktree-diffs", "developer/worktree-diffs", at_rest),
    State(
        "worktree-summaries",
        "developer/worktree-diffs",
        worktree_summaries,
        region="#worktree-example-workbench",
    ),
    State(
        "worktree-summaries-dark",
        "developer/worktree-diffs",
        worktree_summaries,
        scheme="dark",
        region="#worktree-example-workbench",
    ),
    State(
        "worktree-summaries-phone",
        "developer/worktree-diffs",
        worktree_summaries,
        viewport=(390, 844),
        touch=True,
        region="#worktree-example-workbench",
    ),
    State("diff-file-reply", "developer/diff-thread-gallery", diff_file_reply),
    State("diff-moved-reply", "developer/diff-thread-gallery", diff_moved_reply),
    State(
        "diff-file-resolved-closed",
        "developer/diff-thread-gallery",
        diff_file_resolved_closed,
    ),
    State("diff-file-resolved", "developer/diff-thread-gallery", diff_file_resolved),
    State(
        "diff-file-reply-dark-touch",
        "developer/diff-thread-gallery",
        diff_file_reply,
        viewport=(390, 844),
        scheme="dark",
        touch=True,
    ),
    State("code-reader-feedback", "code-comparison", code_reader_feedback),
    State(
        "visual-review-inspection-dark",
        "developer/visual-review-gallery",
        visual_review_inspection,
        scheme="dark",
    ),
    State("activity-feed", "triage-board", activity_feed, region="#triage-moves"),
    State(
        "settled-option",
        "developer/feature-gallery",
        settled_option,
        region="#bg-outcome",
    ),
    State(
        "settled-option-hover",
        "developer/feature-gallery",
        settled_option_hover,
        region="#bg-outcome",
    ),
    State("trace-controls", "developer/playwright-trace-gallery", trace_controls),
    State(
        "trace-actions",
        "developer/playwright-trace-gallery",
        trace_controls,
        viewport=(800, 900),
        region=".lf-trace-toolbar",
    ),
    State(
        "trace-pace",
        "developer/playwright-trace-gallery",
        trace_controls,
        region=".lf-trace-pace",
    ),
    State(
        "motion-controls",
        "developer/motion",
        motion_controls,
        region="#fold-motion .lf-motion-controls",
    ),
    State(
        "timeline-steps",
        "lost-update",
        timeline_steps,
        region="#race-before .lf-timeline-controls",
    ),
    State(
        "trace-timeline-keyboard",
        "developer/playwright-trace-gallery",
        trace_timeline_by_keyboard,
    ),
    State(
        "trace-controls-phone",
        "developer/playwright-trace-gallery",
        trace_controls,
        viewport=(390, 844),
        touch=True,
    ),
    State("retained-quote", "developer/feature-gallery", retained_quote),
    State("retained-quote-full", "developer/feature-gallery", retained_quote_full),
    State(
        "retained-quote-full-dark",
        "developer/feature-gallery",
        retained_quote_full,
        scheme="dark",
    ),
    State(
        "retained-quote-touch",
        "developer/feature-gallery",
        retained_quote_full,
        viewport=(390, 844),
        touch=True,
    ),
    State("contents-spine", "developer/feature-gallery", at_rest),
    State(
        "topic-contents",
        "developer/feature-gallery",
        topic_contents,
        region="#bg-topic-contents",
    ),
    State("contents-spine-keyboard", "developer/feature-gallery", contents_by_keyboard),
    State(
        "contents-over-reading",
        "developer/feature-gallery",
        contents_over_reading,
        viewport=(1100, 900),
        region=".lf-toc-start a",
    ),
    State(
        "contents-over-reading-dark",
        "developer/feature-gallery",
        contents_over_reading,
        viewport=(1100, 900),
        scheme="dark",
        region=".lf-toc-start a",
    ),
    State(
        "contents-spine-dark",
        "developer/feature-gallery",
        contents_by_keyboard,
        scheme="dark",
    ),
    # Where the margin has no room for the map, and where a coarse pointer keeps the
    # sidebar's contents in the flow, at a roomy width and on a phone.
    State("contents-narrow", "developer/feature-gallery", at_rest, viewport=(900, 900)),
    State("contents-coarse", "developer/feature-gallery", at_rest, touch=True),
    State(
        "contents-phone",
        "developer/feature-gallery",
        at_rest,
        viewport=(390, 844),
        touch=True,
    ),
    State("playground-controls", "notification-playground", playground_controls),
    State("playground-instruction", "notification-playground", playground_instruction),
    State("playground-inline-end", "motion-playground", page_end),
    State("playground-tall-stage", "alert-thresholds", playground_tall_stage),
    State("playground-short-window", "data-explorer", page_end, viewport=(844, 390)),
    State(
        "playground-controls-phone",
        "notification-playground",
        playground_controls,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "quoted-playground",
        "../tests/fixtures/pages/quoted-playground",
        at_rest,
        region="#quoted-alerts",
    ),
    State(
        "margin-gallery-phone",
        "developer/feature-gallery",
        margin_gallery,
        viewport=(390, 844),
        touch=True,
    ),
    State("release-draft", "release-notes", draft_edit),
    State("release-draft-hover", "release-notes", draft_hover, region="#rn-cli"),
    State(
        "release-draft-phone",
        "release-notes",
        draft_edit,
        viewport=(390, 844),
        touch=True,
    ),
    State("gallery-tabs", "developer/feature-gallery", at_rest),
    State(
        "gallery-tabs-overflow",
        "developer/feature-gallery",
        overflowing_tabs,
        region="#bg-rollout-tabs",
    ),
    State(
        "gallery-tabs-overflow-dark",
        "developer/feature-gallery",
        overflowing_tabs,
        scheme="dark",
        region="#bg-rollout-tabs",
    ),
    State("gallery-tab-focus", "developer/feature-gallery", tab_by_keyboard),
    State("gallery-tab-hover", "developer/feature-gallery", tab_by_pointer),
    State(
        "gallery-boxed-tab-focus", "developer/feature-gallery", boxed_tab_by_keyboard
    ),
    State("side-tab-focus", "alert-review", tab_by_keyboard),
    State("frame-edges", "developer/feature-gallery", frame_edges),
    State("gallery-metrics", "developer/feature-gallery", gallery_metrics),
    State("gallery-plans", "developer/feature-gallery", gallery_plans),
    State("gallery-ask-figure", "developer/feature-gallery", gallery_ask_figure),
    State(
        "gallery-ask-figure-900",
        "developer/feature-gallery",
        gallery_ask_figure,
        viewport=(900, 900),
    ),
    State(
        "gallery-ask-figure-dark",
        "developer/feature-gallery",
        gallery_ask_figure,
        scheme="dark",
    ),
    State(
        "gallery-ask-figure-phone",
        "developer/feature-gallery",
        gallery_ask_figure,
        viewport=(390, 844),
        touch=True,
    ),
    State("gallery-theme", "developer/feature-gallery", theme_hierarchy),
    State(
        "gallery-theme-dark",
        "developer/feature-gallery",
        theme_hierarchy,
        scheme="dark",
    ),
    State(
        "gallery-theme-phone",
        "developer/feature-gallery",
        theme_hierarchy,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "gallery-theme-phone-dark",
        "developer/feature-gallery",
        theme_hierarchy,
        viewport=(390, 844),
        scheme="dark",
        touch=True,
    ),
    State("widget-inline-hints", "developer/feature-gallery", widget_inline_hints),
    State("gallery-wide-passage", "developer/feature-gallery", wide_passage),
    State(
        "gallery-wide-schedule",
        "developer/feature-gallery",
        wide_schedule,
        viewport=(1726, 900),
    ),
    State("gallery-multiline-passage", "developer/feature-gallery", multiline_passage),
    State("plan", "review-a-plan", at_rest),
    State("plan-execution", "review-a-plan", plan_execution, region="#plan-execute"),
    State("plan-caveat", "review-a-plan", plan_caveat, region="#plan-network"),
    State("page-search", "review-a-plan", page_search, region=".lf-floating-panel"),
    State(
        "accepted-page-search",
        "review-a-plan",
        accepted_page_search,
        region=".lf-floating-panel",
    ),
    State(
        "accepted-page-search-touch",
        "review-a-plan",
        accepted_page_search,
        viewport=(390, 844),
        touch=True,
        region=".lf-floating-panel",
    ),
    State(
        "page-search-phone",
        "review-a-plan",
        page_search,
        viewport=(390, 844),
        region=".lf-floating-panel",
    ),
    State("selected-passage-responses", "review-a-plan", selected_passage_responses),
    State(
        "selected-passage-responses-phone",
        "review-a-plan",
        selected_passage_responses,
        viewport=(390, 844),
        touch=True,
    ),
    State("command-reference-search", "review-a-plan", command_reference_search),
    State("page-map", "review-a-plan", page_map, region=".lf-page-map-dialog"),
    State(
        "command-reference-search-dark",
        "review-a-plan",
        command_reference_search,
        scheme="dark",
    ),
    State("plan-dark", "review-a-plan", at_rest, scheme="dark"),
    State("plan-beside", "review-a-plan", at_rest, viewport=BESIDE),
    State("plan-card", "review-a-plan", card_by_pointer),
    State(
        "plan-card-message-width",
        "review-a-plan",
        card_by_pointer,
        viewport=(1920, 900),
    ),
    State("plan-card-keyboard", "review-a-plan", card_by_keyboard),
    State("plan-card-keyboard-dark", "review-a-plan", card_by_keyboard, scheme="dark"),
    State(
        "thread-choice-hints",
        "../tests/fixtures/pages/thread-choice-hints",
        card_by_keyboard,
        viewport=(741, 838),
        region=".lf-margin-preview",
    ),
    State("plan-card-reply", "review-a-plan", card_reply),
    State("plan-card-aging", "review-a-plan", card_aging, region=".lf-margin-preview"),
    State(
        "plan-card-held-news",
        "review-a-plan",
        card_held_news,
        region=".lf-margin-preview",
    ),
    State(
        "plan-card-held-step",
        "review-a-plan",
        card_held_step,
        region=".lf-margin-preview",
    ),
    State(
        "plan-card-held-step-dark",
        "review-a-plan",
        card_held_step,
        scheme="dark",
        region=".lf-margin-preview",
    ),
    State(
        "plan-card-held-news-phone",
        "review-a-plan",
        card_held_news,
        viewport=(390, 844),
        touch=True,
        region=".lf-margin-preview",
    ),
    State(
        "hub-seat-held-news",
        "command-hub",
        seat_held_news,
        region="#goal-parser .lf-page-thread",
    ),
    State(
        "hub-seat-held-news-phone",
        "command-hub",
        seat_held_news,
        viewport=(390, 844),
        touch=True,
        region="#goal-parser .lf-page-thread",
    ),
    State(
        "plan-card-reply-large", "review-a-plan", card_reply_large, viewport=(1440, 600)
    ),
    State("plan-card-beside", "review-a-plan", card_by_pointer, viewport=BESIDE),
    State("plan-panel", "review-a-plan", go_to_threads),
    State("plan-panel-dark", "review-a-plan", go_to_threads, scheme="dark"),
    State(
        "plan-panel-keyboard-dark", "review-a-plan", panel_by_keyboard, scheme="dark"
    ),
    State("plan-panel-keyboard", "review-a-plan", panel_by_keyboard),
    State("plan-panel-beside", "review-a-plan", go_to_threads, viewport=BESIDE),
    State("plan-go-to", "review-a-plan", go_to, viewport=(1024, 768)),
    State("plan-narrow", "review-a-plan", at_rest, viewport=(360, 740)),
    State("plan-touch", "review-a-plan", at_rest, viewport=(390, 844), touch=True),
    State("plan-more", "review-a-plan", more_menu),
    State("plan-capture", "review-a-plan", capture_area),
    State(
        "plan-capture-drag", "review-a-plan", capture_small_drag, viewport=(390, 740)
    ),
    State("plan-capture-dark", "review-a-plan", capture_area, scheme="dark"),
    State(
        "plan-capture-touch",
        "review-a-plan",
        capture_area,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "plan-more-touch", "review-a-plan", more_menu, viewport=(390, 844), touch=True
    ),
    State(
        "plan-versions-touch",
        "review-a-plan",
        versions_menu,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "plan-panel-touch",
        "review-a-plan",
        go_to_threads,
        viewport=(390, 844),
        touch=True,
    ),
    State("plan-card-reply-long", "review-a-plan", card_reply_long),
    State(
        "plan-card-reply-long-touch",
        "review-a-plan",
        card_reply_long,
        viewport=(390, 844),
        touch=True,
    ),
    State("plan-panel-reply-long", "review-a-plan", panel_reply_long),
    State(
        "plan-panel-reply-long-dark", "review-a-plan", panel_reply_long, scheme="dark"
    ),
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
        "plan-page-comment-resting-dark",
        "review-a-plan",
        page_comment_resting,
        scheme="dark",
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
    State("plan-option-empty", "review-a-plan", option_empty, region=".lf-another"),
    State("plan-card-reply-resolved", "review-a-plan", card_reply_resolved),
    State(
        "plan-card-reply-resolved-elsewhere",
        "review-a-plan",
        card_reply_resolved_elsewhere,
        region=".lf-margin-preview",
    ),
    State(
        "plan-card-reply-resolved-elsewhere-dark",
        "review-a-plan",
        card_reply_resolved_elsewhere,
        scheme="dark",
        region=".lf-margin-preview",
    ),
    State("triage", "triage-board", at_rest),
    State("triage-phone", "triage-board", at_rest, viewport=(390, 844), touch=True),
    State(
        "triage-phone-dark",
        "triage-board",
        at_rest,
        viewport=(390, 844),
        scheme="dark",
        touch=True,
    ),
    State("triage-metrics", "triage-board", at_rest, region="#triage-counts"),
    State(
        "triage-metrics-dark",
        "triage-board",
        at_rest,
        scheme="dark",
        region="#triage-counts",
    ),
    State("triage-composer", "triage-board", composer),
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
        "triage-composer-resting-dark",
        "triage-board",
        composer_resting,
        scheme="dark",
        region=".lf-fab-bar",
    ),
    State(
        "triage-composer-caret-motion",
        "triage-board",
        composer_caret_motion,
        region=".lf-fab-bar",
    ),
    State("triage-composer-space", "triage-board", composer_space, viewport=(362, 900)),
    State(
        "triage-composer-scrolling",
        "triage-board",
        composer_scrolling,
        region=".lf-fab-bar",
    ),
    State(
        "triage-composer-scrolling-dark",
        "triage-board",
        composer_scrolling,
        scheme="dark",
        region=".lf-fab-bar",
    ),
    State("triage-composer-long", "triage-board", composer_long),
    State("triage-composer-long-dark", "triage-board", composer_long, scheme="dark"),
    State(
        "triage-composer-long-beside", "triage-board", composer_long, viewport=BESIDE
    ),
    State(
        "triage-composer-long-touch",
        "triage-board",
        composer_long,
        viewport=(390, 844),
        touch=True,
    ),
    State("triage-composer-sent", "triage-board", composer_sent),
    State(
        "plan-composer-sent-zoomed",
        "review-a-plan",
        composer_sent_zoomed,
        viewport=(1200, 900),
    ),
    State("triage-composer-sent-dark", "triage-board", composer_sent, scheme="dark"),
    State(
        "triage-composer-sent-beside", "triage-board", composer_sent, viewport=BESIDE
    ),
    State(
        "triage-composer-sent-touch",
        "triage-board",
        composer_sent,
        viewport=(390, 844),
        touch=True,
    ),
    State("alert-queue", "alert-review", at_rest),
    State(
        "alert-queue-touch", "alert-review", at_rest, viewport=(390, 844), touch=True
    ),
    State("alert-queue-tally", "alert-review", tally_after_an_answer),
    State(
        "alert-queue-tally-touch",
        "alert-review",
        tally_after_an_answer,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "alert-queue-tally-touch-dark",
        "alert-review",
        tally_after_an_answer,
        viewport=(390, 844),
        touch=True,
        scheme="dark",
    ),
    State(
        "option-add-hover",
        "developer/feature-gallery",
        option_add_hover,
        region="#bg-choice",
    ),
    State(
        "option-add-hover-touch",
        "developer/feature-gallery",
        option_add_hover,
        region="#bg-choice",
        viewport=(390, 844),
        touch=True,
    ),
    State("alert-option-long", "alert-review", option_long),
    State("alert-options-in-pane", "alert-review", options_in_pane),
    State("ideas-ask", "ideas-to-implement", ask_by_keyboard),
    State("progress-callout", "live-progress", at_rest),
    State("progress-metrics", "live-progress", at_rest, region="#lp-status"),
    State(
        "progress-metrics-dark",
        "live-progress",
        at_rest,
        scheme="dark",
        region="#lp-status",
    ),
    State(
        "steps",
        "security-boundary",
        steps_in_view,
        region="#security-contract-list",
    ),
    State("stacked-disclosures", "security-boundary", disclosures_in_view),
    # The case study's five-step flow, drawn top-down so a phone shows every step.
    State(
        "security-flow",
        "security-boundary",
        security_flow,
        region="#security-before-flow",
    ),
    State(
        "security-flow-dark",
        "security-boundary",
        security_flow,
        scheme="dark",
        region="#security-before-flow",
    ),
    State(
        "security-flow-phone",
        "security-boundary",
        security_flow,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "security-flow-phone-dark",
        "security-boundary",
        security_flow,
        viewport=(390, 844),
        scheme="dark",
        touch=True,
    ),
    State(
        "table-scrolled-phone",
        "security-boundary",
        table_scrolled_sideways,
        viewport=(390, 844),
        region="#security-vendor-table",
    ),
    State(
        "table-scrolled-phone-dark",
        "security-boundary",
        table_scrolled_sideways,
        viewport=(390, 844),
        scheme="dark",
        region="#security-vendor-table",
    ),
    State(
        "alert-options-in-pane-touch",
        "alert-review",
        options_in_pane,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "alert-option-long-touch",
        "alert-review",
        option_long,
        viewport=(390, 844),
        touch=True,
    ),
    State("triage-grabbed", "triage-board", card_grabbed),
    State("triage-moved", "triage-board", card_moved, region="#release-board"),
    State(
        "triage-moved-touch",
        "triage-board",
        card_moved_by_destination,
        viewport=(390, 844),
        touch=True,
        region="#col-blocking",
    ),
    State("walkthrough", "pr-walkthrough", at_rest),
    State("walkthrough-wide", "pr-walkthrough", into_the_body),
    State(
        "walkthrough-body-short",
        "pr-walkthrough",
        into_the_body,
        viewport=(900, 600),
    ),
    State(
        "walkthrough-body-short-dark",
        "pr-walkthrough",
        into_the_body,
        viewport=(900, 600),
        scheme="dark",
    ),
    State(
        "walkthrough-body-phone",
        "pr-walkthrough",
        into_the_body,
        viewport=(390, 844),
        touch=True,
    ),
    State("progress-body-short", "live-progress", into_the_body, viewport=(900, 600)),
    State("walkthrough-calls", "pr-walkthrough", call_tree, region="#pr-call-diagram"),
    State("diagram-flow", "pr-walkthrough", diagram_flow, region="#pr-flow-diagram"),
    State(
        "diagram-flow-dark",
        "pr-walkthrough",
        diagram_flow,
        scheme="dark",
        region="#pr-flow-diagram",
    ),
    State("diagram-shape-comment", "pr-walkthrough", diagram_shape_comment),
    State(
        "walkthrough-calls-dark",
        "pr-walkthrough",
        call_tree,
        scheme="dark",
        region="#pr-call-diagram",
    ),
    State("walkthrough-code", "pr-walkthrough", code_note),
    State("walkthrough-code-dark", "pr-walkthrough", code_note, scheme="dark"),
    State("walkthrough-diff-comment", "pr-walkthrough", diff_line_composer),
    State(
        "walkthrough-diff-comment-dark",
        "pr-walkthrough",
        diff_line_composer,
        scheme="dark",
    ),
    State(
        "walkthrough-diff-comment-touch",
        "pr-walkthrough",
        diff_line_composer,
        viewport=(390, 844),
        touch=True,
    ),
    State("walkthrough-copy-hover", "pr-walkthrough", code_copy_by_pointer),
    State("walkthrough-copy-keyboard", "pr-walkthrough", code_copy_by_keyboard),
    State(
        "walkthrough-copy-touch",
        "pr-walkthrough",
        code_note,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "walkthrough-path-keyboard",
        "pr-walkthrough",
        diff_path_by_keyboard,
        viewport=(390, 844),
    ),
    State(
        "walkthrough-diff-source-pointer",
        "pr-walkthrough",
        diff_source_by_pointer,
        viewport=(600, 900),
        region="#pr-exact-patch .lf-diff-file:has(code[data-code])",
    ),
    State(
        "walkthrough-diff-source-keyboard",
        "pr-walkthrough",
        diff_source_by_keyboard,
        viewport=(600, 900),
        region="#pr-exact-patch .lf-diff-file:has(code[data-code])",
    ),
    State(
        "walkthrough-source-touch",
        "pr-walkthrough",
        code_source_by_touch,
        viewport=(390, 844),
        touch=True,
    ),
    State("ship-thread", "ship-review", element_thread),
    State(
        "ship-card-message-keyboard",
        "ship-review",
        card_message_by_keyboard,
        region=".lf-margin-preview",
    ),
    State("ship-tasks", "ship-review", ship_tasks, region="#off-readiness"),
    State(
        "ship-tasks-dark",
        "ship-review",
        ship_tasks,
        scheme="dark",
        region="#off-readiness",
    ),
    State(
        "ship-tasks-phone",
        "ship-review",
        ship_tasks,
        viewport=(390, 844),
        touch=True,
    ),
    State("ship-answered", "ship-review", ship_answered, region=".lf-fp-opened"),
    State(
        "ship-thread-open", "ship-review", element_thread_open, region="#off-t-vendor"
    ),
    State(
        "ship-thread-open-dark",
        "ship-review",
        element_thread_open,
        scheme="dark",
        region="#off-t-vendor",
    ),
    State(
        "ship-option-thread-open",
        "ship-review",
        option_thread_open,
        region="#off-workaround-review",
    ),
    State(
        "ship-option-thread-open-dark",
        "ship-review",
        option_thread_open,
        scheme="dark",
        region="#off-workaround-review",
    ),
    State("ship-card-more-room", "ship-review", card_more_room, viewport=(1440, 600)),
    State(
        "ship-card-short-window", "ship-review", card_by_pointer, viewport=(1440, 480)
    ),
    State(
        "ship-card-short-window-dark",
        "ship-review",
        card_by_pointer,
        viewport=(1440, 480),
        scheme="dark",
    ),
    State(
        "ship-card-touch",
        "ship-review",
        card_by_pointer,
        viewport=(390, 500),
        touch=True,
    ),
    State("on-me", "corpus", on_me),
    State("on-me-dark", "corpus", on_me, scheme="dark"),
    State("on-agent", "corpus", on_agent),
    State("hub-on-me", "command-hub", on_me),
    State("hub-choice", "command-hub", on_me_choice),
    State("hub-choice-answered", "command-hub", on_me_choice_answered),
    State(
        "hub-choice-answered-dark", "command-hub", on_me_choice_answered, scheme="dark"
    ),
    State(
        "hub-choice-answered-touch",
        "command-hub",
        on_me_choice_answered,
        viewport=(390, 844),
        touch=True,
    ),
    State("hub-on-agent", "command-hub", on_agent),
    State("hub", "command-hub", at_rest),
    State("hub-workers", "command-hub", hub_workers),
    State("sort", "rust-sort", at_rest),
    State("sort-narrow", "rust-sort", at_rest, viewport=(720, 900)),
    State("sort-pane", "rust-sort", pane_focused),
    State("sort-pane-dark", "rust-sort", pane_focused, scheme="dark"),
    State("sort-aim-cut", "rust-sort", aim_cut_by_pane),
)

# Every state's input by name, for `leaf-dev probe --do drive:NAME`.
DRIVERS: dict[str, Callable[[Page], None]] = {
    getattr(state.drive, "__name__").replace("_", "-"): state.drive  # noqa: B009 - Callable does not expose function attributes to ty.
    for state in STATES
}


@contextmanager
def capture(
    browser, address: str, state: State, path: Path
) -> Generator[tuple[dict | None, dict[str, list[str]], list[str], Page]]:
    """Bring a fresh tab to `state` and screenshot its viewport to `path`, at the
    density of the displays its pairs are read on, so a crop shows text and hairlines
    as the reader's screen draws them. Yield the state's region in the screenshot,
    if it names one, its elements' styles and the paths of those showing words
    (`STYLES`), and the tab, open until the block ends so `declaration_changes` can
    read it."""
    scale = 2
    with tab(browser, state.viewport, state.scheme, state.touch, scale=scale) as page:
        load(page, address)
        state.drive(page)
        settle(page)
        clip = None
        if state.region:
            target = page.locator(state.region)
            expect(target).to_be_visible()
            bounds = target.bounding_box()
            assert bounds is not None
            # Keep the focus paint outside the target while omitting unrelated chrome.
            room = 8
            x, y = max(0, bounds["x"] - room), max(0, bounds["y"] - room)
            clip = {
                "x": x,
                "y": y,
                "width": min(state.viewport[0], bounds["x"] + bounds["width"] + room)
                - x,
                "height": min(state.viewport[1], bounds["y"] + bounds["height"] + room)
                - y,
            }
        page.screenshot(path=path)
        reading = page.evaluate(STYLES, STYLED)
        styles = {
            key: reading["faces"][face] for key, face in reading["elements"].items()
        }
        region = {key: value * scale for key, value in clip.items()} if clip else None
        yield region, styles, reading["texts"], page


def style_changes(
    base: dict[str, list[str]], head: dict[str, list[str]]
) -> tuple[int, list[str], list[str]]:
    """Each `STYLED` property whose value differs between an element's base and head
    readings, grouped by property and values with up to four of its elements, then
    the subtrees only one arm has, each named by its outermost element, since a widget
    that draws in one arm and not the other adds every node of its drawing. Return how
    many element properties differ, plus those subtrees, the lines that list them, and
    each group's first element."""
    groups: dict[tuple[str, str, str], list[str]] = {}
    for key in base.keys() & head.keys():
        for name, before, after in zip(STYLED, base[key], head[key], strict=True):
            if before != after:
                groups.setdefault((name, before, after), []).append(key)
    alone = {
        heading: sorted(
            key for key in keys if re.sub(r" >>? [^ ]+$", "", key) not in keys
        )
        for heading, keys in (
            ("only in base", base.keys() - head.keys()),
            ("only in head", head.keys() - base.keys()),
        )
    }
    lines = []
    firsts = {}
    for (name, before, after), keys in sorted(
        groups.items(), key=lambda group: -len(group[1])
    ):
        keys.sort()
        firsts[keys[0]] = None
        lines.append(f"{name}: {before} -> {after}  x{len(keys)}")
        lines.extend(f"    {key}" for key in keys[:4])
    for heading, keys in alone.items():
        if keys:
            lines.append(f"{heading}  x{len(keys)}")
            lines.extend(f"    {key}" for key in keys[:4])
    count = sum(map(len, groups.values())) + sum(map(len, alone.values()))
    return count, lines, list(firsts)


def face_of(values: list[str]) -> tuple[str, ...]:
    """The `FACE` values among an element's `STYLED` ones."""
    return tuple(values[STYLED.index(name)] for name in FACE)


def describe_face(face: tuple[str, ...]) -> str:
    family, size, weight, style, tracking, case = face
    words = [weight, size, family.split(",")[0].strip('"')]
    words += [style] if style != "normal" else []
    words += [f"tracked {tracking}"] if tracking != "normal" else []
    words += [case] if case != "none" else []
    return " ".join(words)


def face_distance(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """How far apart two faces read: a pixel of size, a hundred of weight and a
    tenth of an em of tracking each count one, and a different family, style or case
    puts them apart altogether."""
    if (a[0], a[3], a[5]) != (b[0], b[3], b[5]):
        return float("inf")

    def pixels(value: str) -> float:
        return float(value.removesuffix("px")) if value.endswith("px") else 0.0

    tracks = [pixels(face[4]) / (pixels(face[1]) or 1) for face in (a, b)]
    return (
        abs(pixels(a[1]) - pixels(b[1]))
        + abs(int(a[2]) - int(b[2])) / 100
        + abs(tracks[0] - tracks[1]) * 10
    )


def face_changes(drawn: dict[str, dict[tuple[str, ...], list[str]]]) -> list[str]:
    """The faces only one arm draws in `drawn` (each arm's faces, by the states and
    elements that wear them), each with up to three of those and the other arm's
    nearest face."""
    lines = []
    for arm, other in (("head", "base"), ("base", "head")):
        alone = sorted(drawn[arm].keys() - drawn[other].keys(), key=describe_face)
        if not alone:
            continue
        lines.append(f"faces only {arm} draws  x{len(alone)}")
        for face in alone:
            wearers = drawn[arm][face]
            nearest = min(
                drawn[other],
                key=lambda candidate: face_distance(face, candidate),
                default=None,
            )
            near = (
                f"; {other}'s nearest {describe_face(nearest)}"
                if nearest and face_distance(face, nearest) < float("inf")
                else ""
            )
            lines.append(f"  {describe_face(face)}  x{len(wearers)}{near}")
            lines.extend(f"      {wearer}" for wearer in wearers[:3])
    return lines


def declarations(page: Page) -> Callable[[str], list[str]]:
    """Read an element `STYLES` read, by its key, through Chromium's inspector: every
    authored declaration of the rules that match it and of its style attribute, in the
    order the inspector lists them, each with its sheet, layers, scope and selector."""
    session = page.context.new_cdp_session(page)
    sheets: dict[str, dict] = {}
    session.on(
        "CSS.styleSheetAdded",
        lambda event: sheets.update({event["header"]["styleSheetId"]: event["header"]}),
    )
    session.send("DOM.enable")
    session.send("CSS.enable")
    session.send("DOM.getDocument")

    def label(rule: dict) -> str:
        header = sheets.get(rule.get("styleSheetId"), {})
        if rule["origin"] != "regular":
            sheet = rule["origin"]
        elif header.get("isConstructed"):
            sheet = "constructed"
        # An inline sheet's URL is its document's, which names the arm's port.
        elif header.get("isInline") or not header.get("sourceURL"):
            sheet = "<style>"
        else:
            sheet = header["sourceURL"].rsplit("/", 1)[-1]
        layers = ".".join(layer["text"] or "anonymous" for layer in rule["layers"])
        return " ".join(
            [
                sheet,
                *([f"@layer {layers}"] if layers else []),
                *(f"@scope {scope['text']}" for scope in rule["scopes"]),
                rule["selectorList"]["text"],
            ]
        )

    def read(key: str) -> list[str]:
        element = session.send(
            "Runtime.evaluate", {"expression": f"stillsRead.get({json.dumps(key)})"}
        )
        node = session.send(
            "DOM.requestNode", {"objectId": element["result"]["objectId"]}
        )
        matched = session.send("CSS.getMatchedStylesForNode", node)
        rules = [
            (label(entry["rule"]), entry["rule"]["style"])
            for entry in matched["matchedCSSRules"]
        ]
        if matched.get("inlineStyle"):
            rules.append(("style attribute", matched["inlineStyle"]))
        return [
            f"{rule} {{ {' '.join(declaration['text'].split())} }}"
            for rule, style in rules
            for declaration in style["cssProperties"]
            if "text" in declaration
        ]

    return read


def declaration_changes(pages: dict[str, Page], keys: Iterable[str]) -> list[str]:
    """For each element, the declarations (`declarations`) that match it in only one
    of the arms' `pages`, or in another order, as lines under its key."""
    read = {arm: declarations(page) for arm, page in pages.items()}
    lines = ["declarations that differ, on each group's first element"]
    for key in keys:
        before, after = read["base"](key), read["head"](key)
        changes = [
            line
            for tag, i, j, k, m in SequenceMatcher(
                None, before, after, autojunk=False
            ).get_opcodes()
            if tag != "equal"
            for line in [
                *(f"- {row}" for row in before[i:j]),
                *(f"+ {row}" for row in after[k:m]),
            ]
        ]
        lines.append(f"    {key}")
        lines.extend(
            f"        {line}"
            for line in changes
            or ["none: it inherits the difference or reads it from a custom property"]
        )
    return lines


@contextmanager
def differences(browser, out: Path):
    """One comparison tab, yielding `lf-shot`'s reading of a named state's pair.

    Reuse the browser module for the catalogue; each comparison is a separate call
    so a state's unreadable image or failed crop leaves the other pairs available.
    """

    def serve(route) -> None:
        path = route.request.url.removeprefix(ORIGIN)
        if path == "/image-difference.js":
            route.fulfill(path=DIFFERENCE, content_type="text/javascript")
        elif path.startswith("/vendor/"):
            route.fulfill(path=ROOT / "packages" / "default" / path.lstrip("/"))
        elif path.endswith(".png"):
            route.fulfill(path=out / path.lstrip("/"))
        else:
            route.fulfill(body="<!doctype html>", content_type="text/html")

    context = browser.new_context()
    try:
        context.route(f"{ORIGIN}/**", serve)
        page = context.new_page()
        page.goto(f"{ORIGIN}/")
        compare_images = page.evaluate_handle(
            "async () => (await import('/image-difference.js')).compareImages"
        )

        def compare(name: str) -> dict:
            return compare_images.evaluate(
                """async (compareImages, name) => {
                  const load = async (arm) => {
                    const image = new Image();
                    image.src = `/${name}/${arm}.png`;
                    await image.decode();
                    return image;
                  };
                  return compareImages(await load("base"), await load("head"));
                }""",
                name,
            )

        yield compare
    finally:
        context.close()


def crop(
    folder: Path, regions: list[dict], *, framing: list[dict] | None = None
) -> None:
    """Crop both stills around framing (or changed regions); retain actual diff outlines."""
    base = Image.open(folder / "base.png").convert("RGB")
    head = Image.open(folder / "head.png").convert("RGB")
    framing = regions if framing is None else framing
    box = (
        (
            max(min(r["x"] for r in framing) - CROP_MARGIN, 0),
            max(min(r["y"] for r in framing) - CROP_MARGIN, 0),
            min(max(r["x"] + r["width"] for r in framing) + CROP_MARGIN, head.width),
            min(max(r["y"] + r["height"] for r in framing) + CROP_MARGIN, head.height),
        )
        if framing
        else (0, 0, head.width, head.height)
    )
    base.crop(box).save(folder / "base-crop.png")
    head.crop(box).save(folder / "head-crop.png")
    faded = Image.blend(head, Image.new("RGB", head.size, "white"), 0.6)
    draw = ImageDraw.Draw(faded)
    for r in (r for r in regions if r["side"] == "after"):
        draw.rectangle(
            (r["x"] - 3, r["y"] - 3, r["x"] + r["width"] + 2, r["y"] + r["height"] + 2),
            outline=(220, 0, 0) if r["kind"] == "changed" else (40, 110, 230),
            width=2,
        )
    faded.crop(box).save(folder / "diff.png")


@click.command()
@click.argument("base_ref", required=False)
@click.option(
    "--state",
    "names",
    type=click.Choice([state.name for state in STATES]),
    multiple=True,
    help="Capture a named state; repeat for more. Defaults to the whole catalogue.",
)
@click.option(
    "--authored",
    is_flag=True,
    help="Compare each commit’s authored examples as well as its runtime.",
)
def stills(base_ref: str | None, names: tuple[str, ...], authored: bool) -> None:
    """Screenshot a catalogue of UI states on BASE_REF's runtime and HEAD's, and crop
    each state that changed into a before/after pair under .tmp/stills/."""
    states = [state for state in STATES if not names or state.name in names]
    out = run_directory(OUT)
    failed: dict[str, list[str]] = {}
    read: dict[str, dict] = {}
    drawn: dict[str, dict[tuple[str, ...], list[str]]] = {"base": {}, "head": {}}

    def failure(state: State, phase: str, error: Exception) -> None:
        message = (
            error.message.strip().rsplit("\n", 1)[-1].split("; ")[0]
            if isinstance(error, click.ClickException)
            else str(error).split("\n", 1)[0]
        ) or type(error).__name__
        failed.setdefault(state.name, []).append(f"on {phase}: {message}")
        (out / state.name / f"{phase}-error.txt").write_text(traceback.format_exc())

    with tempfile.TemporaryDirectory(prefix="leaf-stills-") as built:
        scratch = Path(built)
        arms, commits = build_pair(base_ref, scratch)
        source_roots = {arm: ROOT for arm in arms}
        if authored:
            for arm, commit in commits.items():
                source_roots[arm] = scratch / f"{arm}-source"
                source_roots[arm].mkdir()
                copy_committed(
                    (
                        "examples",
                        "tests/fixtures/pages",
                        "docs/examples.html",
                        "leaf-assets.json",
                    ),
                    source_roots[arm],
                    commit,
                )
        # Capture the scrollbars readers see, including the room a classic bar takes.
        with (
            headless_shell(ignore_default_args=["--hide-scrollbars"]) as browser,
            differences(browser, out) as compare,
        ):
            for state in states:
                folder = out / state.name
                folder.mkdir()
                crop_regions = []
                styles = {}
                texts = {}
                pages = {}
                # Both arms stay open through the comparison, which reads their tabs.
                with ExitStack() as held:
                    for arm, arm_dir in arms.items():
                        # Every state starts from its authored fixture. A prior Send
                        # or Resolve must not become the next state's initial event
                        # log. The base refuses a source written in vocabulary only
                        # the head declares; that state has no base still, and the
                        # head's still stands alone in its folder.
                        try:
                            address = held.enter_context(
                                serving_source(
                                    arm_dir,
                                    source_roots[arm]
                                    / "examples"
                                    / f"{state.source}.html",
                                    scratch / f"{arm}-{state.name}",
                                )
                            )
                            region, styles[arm], texts[arm], pages[arm] = (
                                held.enter_context(
                                    capture(
                                        browser, address, state, folder / f"{arm}.png"
                                    )
                                )
                            )
                            if region:
                                crop_regions.append(region)
                        except Exception as error:
                            failure(state, arm, error)
                    if state.name in failed:
                        continue
                    for arm, keys in texts.items():
                        for key in keys:
                            drawn[arm].setdefault(face_of(styles[arm][key]), []).append(
                                f"{state.name}: {key}"
                            )
                    try:
                        difference = compare(state.name)
                        if difference["changed"]:
                            crop(
                                folder,
                                difference["regions"],
                                framing=crop_regions or None,
                            )
                        difference["styles"], lines, firsts = style_changes(
                            styles["base"], styles["head"]
                        )
                        if firsts:
                            lines += declaration_changes(pages, firsts)
                        if lines:
                            (folder / "styles.txt").write_text("\n".join(lines) + "\n")
                        read[state.name] = difference
                    except Exception as error:
                        failure(state, "comparison", error)
    click.echo(f"base {commits['base'][:10]} vs head {commits['head'][:10]}")
    unchanged = 0
    for state in states:
        folder = out / state.name
        if state.name in failed:
            click.echo(f"  failed  {state.name} {'; '.join(failed[state.name])}")
        elif (difference := read[state.name])["changed"] or difference["styles"]:
            click.echo(
                f"  changed {state.name}: {difference['changed']} px,"
                f" {difference['styles']} styles -> {folder}"
            )
        else:
            unchanged += 1
    click.echo(f"{unchanged} of {len(states)} states unchanged")
    if lines := face_changes(drawn):
        (out / "faces.txt").write_text("\n".join(lines) + "\n")
        click.echo(
            "faces one arm alone draws: "
            + ", ".join(line.strip() for line in lines if line.startswith("faces"))
            + f" -> {out / 'faces.txt'}"
        )
    click.echo(f"files in {out}")
