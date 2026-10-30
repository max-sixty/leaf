"""File-authored anchors, drawings, width, and handover tests."""

import io
import json
import math
import re

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    declare_on_page,
    record_claim,
)
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_OBLIGATION_LAYER,
    SEATED_OBLIGATION_WIDGETS,
    live_url,
)
from render_cases_layout import (
    SHOT_SRC,
    SHOTS,
    current_location_ring,
)
from render_cases_navigation import (
    composer_quote,
)
from render_cases_widgets import (
    BROKEN_DIAGRAM_PAGE,
    CHROME_ROOM,
    CUT_BOXES_PAGE,
    DIAGRAM_AND_RAIL_PAGE,
    DIAGRAM_ROOM,
    DRAWING_PLACEMENT,
    DRAWN_PAST_A_RAIL_PAGE,
    FRAMED_WIDE_PAGE,
    LONG_CHAIN_PAGE,
    NOTE_AND_WIDE_PAGE,
    NOTE_BAND,
    PICTURE_PAGE,
    RAIL_BAND_PAGE,
    RAIL_BANDS,
    ROOM_GEOMETRY,
    TWIN_V1,
    TWIN_V2,
    TYPED_PARTS_PAGE,
    WIDE_AND_NARROW_PAGE,
    WIDE_DIAGRAM_PAGE,
)
from render_harness import (
    EXAMPLES,
    INLINE_PAGE,
    LONG_PAGE,
    REPLY_HOST_PAGE,
    TOKEN,
    consume_browser_errors,
    expect_open_threads,
    held_frames,
    http_error_console,
    leaf_page,
    margins_laid_out,
    nudge,
    open_page,
    panel_field,
    panel_menu,
    panel_settled,
    refuse,
    resized,
    root_overflow,
    scroll_settled,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    wide_width,
    write,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import schema as schema_model
from leaf.registry.storage import load_registry
from leaf.render_checks import evaluate_probe, rendered, wait_until_ready
from leaf.render_gate.scheme import console_finding

pytestmark = pytest.mark.shifts_unsurveyed


def test_sort_film_readout_and_narration(browser, serve):
    """Changing step numbers hold their space, and narration renders inline Markdown."""
    example = next(path for path in EXAMPLES if path.stem == "rust-sort")
    page = open_page(browser, serve(example))
    assert (
        "collapse(): merge if one is true"
        in page.locator("#sort-film svg[role='img']").text_content()
    )
    readings = page.evaluate(
        """async () => {
          const imports = JSON.parse(document.querySelector('script[type="importmap"]').textContent).imports;
          const source = new URL('../page/sort.js', new URL(imports['/runtime/'], location.href));
          const {makeInput, trace} = await import(source);
          const steps = trace(makeInput('random', 7)).steps;
          const film = document.querySelector('#sort-film');
          const scrub = film.querySelector('.sort-scrub');
          const moment = film.querySelector('.sort-moment');
          const tail = film.querySelector('.sort-moment-tail');
          const widths = [];
          for (const index of [0, 1, 8, 9, 98, 99, 198, 199]) {
            // Each position its own task, as each move of a user's scrub is.
            await new Promise(resolve => setTimeout(resolve));
            scrub.value = steps[index].start + steps[index].dur - 0.01;
            scrub.dispatchEvent(new Event('input', {bubbles: true}));
            widths.push([
              moment.getBoundingClientRect().width,
              tail.getBoundingClientRect().left - moment.getBoundingClientRect().left,
            ]);
          }
          const comparison = steps.find(step => step.note.includes('≤') && step.note.includes('buf'));
          const run = steps.find(step => step.note.startsWith('A natural run'));
          return {
            widths,
            comparisonTime: comparison.start + comparison.dur - 0.01,
            runTime: run.start + run.dur - 0.01,
          };
        }"""
    )
    assert all(max(values) - min(values) < 0.1 for values in zip(*readings["widths"]))
    note = page.locator("#sort-film .sort-narration > span:first-of-type")
    scrub = page.locator("#sort-film .sort-scrub")
    scrub.evaluate(
        "(element, time) => { element.value = time; element.dispatchEvent(new Event('input', {bubbles: true})); }",
        readings["runTime"],
    )
    expect(note.locator("code")).to_have_text(re.compile(r"v\[\d+\.\.\d+\]"))
    expect(note).to_contain_text("A natural run")
    scrub.evaluate(
        "(element, time) => { element.value = time; element.dispatchEvent(new Event('input', {bubbles: true})); }",
        readings["comparisonTime"],
    )
    expect(note.locator("strong")).to_contain_text("≤")
    expect(note.locator("code")).to_have_text("buf")


def test_sort_film_fits_its_pane_where_the_panes_stand_side_by_side(browser, serve):
    """A workspace is a screen, so in a 900px-tall window at the narrowest width the
    page sets its panes side by side, the whole player shows in its pane, the last
    step's longer summary included (page-layout.md, "A workspace")."""
    example = next(path for path in EXAMPLES if path.stem == "rust-sort")
    context = browser.new_context(
        reduced_motion="reduce", viewport={"width": 720, "height": 900}
    )
    page = open_page(browser, serve(example), context=context)
    overruns = page.evaluate(
        """() => {
          const pane = document.querySelector('#sort-stage-pane');
          const film = pane.querySelector('#sort-film');
          const overrun = () =>
            film.querySelector('.sort-stats').getBoundingClientRect().bottom -
            pane.getBoundingClientRect().bottom;
          const atRest = overrun();
          const scrub = film.querySelector('.sort-scrub');
          scrub.value = scrub.max;
          scrub.dispatchEvent(new Event('input', {bubbles: true}));
          return [atRest, overrun()];
        }"""
    )
    assert all(overrun <= 0 for overrun in overruns), overruns


def test_ship_review_summary_is_addressable_and_baseline_aligned(browser, serve):
    example = next(path for path in EXAMPLES if path.stem == "ship-review")
    page = open_page(browser, serve(example))
    summary = page.locator("#off-facts")
    expect(summary).to_be_visible()
    assert (
        summary.evaluate("element => getComputedStyle(element).alignItems")
        == "baseline"
    )

    summary.scroll_into_view_if_needed()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    code = summary.evaluate(
        """element => {
          const box = element.getBoundingClientRect();
          const hints = [...document.querySelectorAll('.lf-target-picker-hint')].map(node => {
            const at = node.getBoundingClientRect();
            return {
              code: node.dataset.lfHintCode,
              distance: Math.hypot(
                at.left + at.width / 2 - box.left,
                at.top + at.height / 2 - box.top,
              ),
            };
          });
          hints.sort((a, b) => a.distance - b.distance);
          return hints[0]?.distance < 30 ? hints[0].code : null;
        }"""
    )
    assert code, "the summary had no target-picker hint"
    page.keyboard.type(code)
    expect(page.locator(".lf-live")).to_contain_text("Chosen list: Observed")


def test_a_written_anchor_keeps_its_copy_when_the_page_grows_another(browser, serve):
    """A quote unique when it was written is not unique forever. The neighbours a written
    anchor stores are what hold it on the passage it was made about — without them the
    search takes the first copy, and a comment ends up on words nobody wrote it about."""
    url = serve(TWIN_V1)
    d = serve.page_dir
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(d),
            "--quote",
            "The version stamp never lands",
            "--text",
            "capped where?",
        ],
    )
    assert result.exit_code == 0, result.output
    anchor = json.loads(result.output)["anchor"]
    assert anchor["prefix"] and anchor["suffix"], (
        f"nothing stored to tell copies apart: {anchor}"
    )

    page = open_page(browser, live_url(url))
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    stamp_page(d, TWIN_V2, "a twin")
    wait_for_revision(page, 2)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    where = page.evaluate(
        "() => [...CSS.highlights.get('lf-mark')][0].startContainer.parentElement.id"
    )
    assert where == "p-original", f"the new copy took the comment ({where})"


def stand_on_thread(page, thread_id):
    """Open the thread in the panel and go from it to its words on the page, where it
    stands selected."""
    open_panel_thread(page, thread_id)
    page.locator(".lf-fp-aux").get_by_role(
        "button", name="Show on page", exact=True
    ).click()
    panel_settled(page, open=False)


def test_a_written_comment_keeps_its_originating_agent(browser, serve, monkeypatch):
    """An agent's side of a thread is the user's side with the author flipped.
    Its label belongs to the message — the poster's own environment stamps it as
    the comment is written — so another host claiming the page later cannot
    rewrite who said it."""
    url = serve(TWIN_V1)
    d = serve.page_dir
    monkeypatch.setenv("LEAF_SESSION_ID", "codex")
    monkeypatch.setenv("LEAF_AGENT", "Codex")
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            [
                "thread",
                "create",
                str(d),
                "--quote",
                "Retries are capped at three",
                "--text",
                "is three right?",
            ],
        )
        .exit_code
        == 0
    )
    record_claim(d, id="claude")
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Counted as open, like any other thread.
    expect_open_threads(page, 1)
    [root] = [e["id"] for e in events_model.read_events(d) if e["kind"] == "comment"]
    thread = open_panel_thread(page, root)
    expect(thread.locator(".lf-msg.agent")).to_have_count(1)
    expect(thread.locator(".lf-msg.agent > .lf-msg-head b")).to_have_text("Codex")
    expect(thread.locator(".lf-fp-quote")).to_contain_text(
        "“Retries are capped at three”"
    )

    write(panel_field(page), "three is the retry budget, not a guess")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(thread.locator(".lf-msg.user")).to_have_count(1)
    with sending(page, "the resolve"):
        page.locator(".lf-fp-settle").click()

    kinds = [(e["kind"], e.get("author")) for e in events_model.read_events(d)]
    assert ("comment", "agent") in kinds
    assert ("reply", "user") in kinds and ("resolve", "user") in kinds


@pytest.mark.parametrize("draft", [False, True], ids=["empty", "draft"])
def test_a_failed_agent_root_restores_the_focused_first_message_composer(
    browser, serve, draft
):
    """A rejected inline root gives the authored seat and its focused editor back."""
    url = serve(
        leaf_page(
            "Inline rollback",
            '<h1>Review</h1><lf-verdict id="proposal" asks>Ship it?</lf-verdict>',
        ),
        layer_registry=SEATED_OBLIGATION_LAYER,
        layer_widgets=SEATED_OBLIGATION_WIDGETS,
    )
    page = open_page(browser, live_url(url))
    seat = page.locator("#proposal > .lf-thread-seat")
    composer = seat.locator(":scope > .lf-say leaf-text")
    words = "keep this first message" if draft else ""
    write(composer, words)
    composer.evaluate(
        "(input, selection) => input.setSelectionRange(...selection)",
        [3, 12, "backward"] if draft else [0, 0, "none"],
    )
    # Read the arrangement back rather than pinning the literal that made it: Chromium
    # reports a collapsed selection as `forward` whichever direction set it, so the
    # restored reading is compared with the one the browser actually held.
    selection = composer.evaluate(
        "input => [input.selectionStart, input.selectionEnd, input.selectionDirection]"
    )
    expect(composer).to_be_focused()

    broken = []

    def fail_after_rendering_the_inline_root(route):
        if broken:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        view = state["browser"]["views"][str(state["active"]["revision"])]
        view["document"]["projection"]["entries"].append(None)
        broken.append(True)
        route.fulfill(status=response.status, json=state)

    page.route("**/api/state*", fail_after_rendering_the_inline_root)
    with page.expect_console_message(
        lambda message: "read failed" in message.text
    ) as fault:
        root = append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "agent",
                "agent": "Codex",
                "revision": 1,
                "anchor": {"section": "proposal"},
                "text": "candidate root",
            },
        )
    page.lf_errors.remove(console_finding(fault.value))

    inline = seat.locator(f':scope > .lf-page-thread[data-thread="{root["id"]}"]')
    expect(inline).to_have_count(0)
    expect(composer).to_have_count(1)
    expect(composer).to_be_focused()
    expect(composer).to_have_js_property("value", words)
    assert (
        composer.evaluate(
            "input => [input.selectionStart, input.selectionEnd, input.selectionDirection]"
        )
        == selection
    )

    page.unroute("**/api/state*")
    nudge(serve.page_dir)
    told(page)
    expect(inline.locator(".lf-msg-body")).to_have_text("candidate root")
    expect(composer).to_have_count(1 if draft else 0)
    if draft:
        expect(composer).to_have_js_property("value", words)


def test_a_failed_resolution_restores_a_focused_inline_reply(browser, serve):
    """Inline rollback restores the logical thread's direct reply box and selection."""
    url = serve(
        leaf_page(
            "Inline reply rollback",
            '<h1>Review</h1><lf-verdict id="proposal" asks>Ship it?</lf-verdict>',
        ),
        layer_registry=SEATED_OBLIGATION_LAYER,
        layer_widgets=SEATED_OBLIGATION_WIDGETS,
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "proposal"},
            "text": "keep discussing this",
        },
    )
    page = open_page(browser, live_url(url))
    thread = page.locator(f'#proposal > .lf-thread-seat > [data-thread="{root["id"]}"]')
    reply = thread.locator(":scope > .lf-thread-reply leaf-text")
    write(reply, "keep this inline reply")
    reply.evaluate("node => node.setSelectionRange(5, 16, 'backward')")
    expect(reply).to_be_focused()

    broken = []

    def fail_after_resolving_the_inline_thread(route):
        if broken:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        view = state["browser"]["views"][str(state["active"]["revision"])]
        view["document"]["projection"]["entries"].append(None)
        broken.append(True)
        route.fulfill(status=response.status, json=state)

    page.route("**/api/state*", fail_after_resolving_the_inline_thread)
    with page.expect_console_message(
        lambda message: "read failed" in message.text
    ) as fault:
        append_carried_log_record(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "parent": root["id"]},
        )
    page.lf_errors.remove(console_finding(fault.value))

    expect(reply).to_have_js_property("value", "keep this inline reply")
    expect(reply).to_be_focused()
    assert reply.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [5, 16, "backward"]

    page.unroute("**/api/state*")
    nudge(serve.page_dir)
    told(page)
    expect(reply).to_be_visible()
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "keep this inline reply")
    assert reply.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [5, 16, "backward"]
    # The remote resolution waits behind the thread's notice while the focused
    # draft is in view. The user can reveal it without losing their reply.
    notice = thread.locator(".lf-thread-news")
    expect(notice).to_have_text("Resolved")
    expect(thread).to_have_attribute("data-resolved", "false")
    notice.click()
    expect(thread.get_by_role("button", name="Reopen")).to_be_visible()
    expect(reply).to_have_js_property("value", "keep this inline reply")


def test_failed_resolve_candidate_restores_focused_reply(browser, serve):
    """A refused resolution restores the user's reply destination and selection."""
    url = serve(TWIN_V1)
    page_dir = serve.page_dir
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "which host answers?",
        },
    )
    page = open_page(browser, live_url(url))
    view = open_panel_thread(page, root["id"])
    draft = panel_field(page)
    write(draft, "keep this unfinished reply")
    expect(draft).to_be_focused()
    draft.evaluate("node => node.setSelectionRange(5, 12, 'backward')")

    broken = []

    def fail_after_resolving_the_focused_thread(route):
        if broken:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        view = state["browser"]["views"][str(state["active"]["revision"])]
        view["document"]["projection"]["entries"].append(None)
        broken.append(True)
        route.fulfill(status=response.status, json=state)

    page.route("**/api/state*", fail_after_resolving_the_focused_thread)
    with page.expect_console_message(
        lambda message: "read failed" in message.text
    ) as fault:
        append_carried_log_record(
            page_dir,
            {"kind": "resolve", "author": "agent", "parent": root["id"]},
        )

    page.lf_errors.remove(console_finding(fault.value))
    expect(draft).to_have_js_property("value", "keep this unfinished reply")
    expect(draft).to_be_focused()
    assert draft.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [5, 12, "backward"]

    page.unroute("**/api/state*")
    nudge(page_dir)
    told(page)
    # The view keeps the user's editing place and says the remote resolution in a
    # notice the user opens.
    news = page.locator(".lf-fp-controls .lf-thread-news")
    expect(news).to_have_text("Resolved")
    expect(draft).to_have_js_property("value", "keep this unfinished reply")
    news.click()
    expect(view).to_be_visible()
    expect(page.locator(".lf-fp-settle")).to_have_accessible_name("Reopen")
    expect(draft).to_have_js_property("value", "keep this unfinished reply")


def test_a_failed_state_keeps_focus_in_the_open_versions_menu(browser, serve):
    """Rollback preserves an unchanged picker subtree and its focused row."""
    url = serve(TWIN_V1)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    stamp_page(d, TWIN_V2, "a twin")
    wait_for_revision(page, 2)
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    menu = page.locator(".lf-fp-menu[data-level=versions]")
    row = menu.locator(".lf-fp-version .lf-fp-item").first
    expect(row).to_be_focused()

    broken = []

    def fail_after_rendering_versions(route):
        if broken:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        view = state["browser"]["views"][str(state["active"]["revision"])]
        view["document"]["projection"]["entries"].append(None)
        broken.append(True)
        route.fulfill(status=response.status, json=state)

    page.route("**/api/state*", fail_after_rendering_versions)
    with page.expect_console_message(
        lambda message: "read failed" in message.text
    ) as fault:
        nudge(d)
    expect(menu).to_be_visible()
    expect(row).to_be_focused()
    page.lf_errors.remove(console_finding(fault.value))

    page.unroute("**/api/state*")
    nudge(d)
    told(page)


def test_a_widget_declaring_it_renders_a_picture_exposes_a_comment_target(
    browser, serve
):
    """A rendering has no text of the page's in it to select, so an explicit Comment
    gesture anchors on the whole element. Which widgets those are is theirs to declare
    (x-visual): the runtime names none of them, so a widget added to the vocabulary exposes
    the target on the strength of its entry. This rules out a consumer that knows one
    widget by name and silently misses the next."""
    url = serve(PICTURE_PAGE)
    registry = load_registry(serve.page_dir)
    assert registry["lf-diagram"]["x-visual"], "this test needs the shipped declaration"
    declare_on_page(
        serve.page_dir,
        # A widget core has never heard of.
        lambda registry: registry["lf-code"].update({"x-visual": "whole"}),
    )
    page = open_page(browser, url)

    # The inner svg belongs to the renderer and carries generated ids; the anchor
    # belongs to the widget that holds it, which is the element the page gave a name.
    page.locator("#flow svg").click(modifiers=["Alt"])
    page.locator(".lf-fab-input").click()
    page.locator("#flow.lf-mark-el.lf-pending.lf-projected-mark").wait_for()
    expect(page.locator(".lf-visual-mark-pending")).to_be_visible()
    assert not composer_quote(page)["shown"], "a picture has no words to quote back"
    page.keyboard.press("Escape")

    page.locator("#tree").click(modifiers=["Alt"])
    page.locator(".lf-fab-input").click()
    page.locator("#tree.lf-mark-el.lf-pending.lf-projected-mark").wait_for()
    overlay = page.locator(".lf-visual-mark-pending")
    expect(overlay).to_be_visible()
    look = overlay.evaluate(
        """el => { const style = getComputedStyle(el, '::after'); return {
          background: getComputedStyle(el).backgroundImage,
          outline: [style.outlineStyle, style.outlineWidth],
        }; }"""
    )
    assert look["background"] == "none", look
    assert look["outline"][0] == "solid" and look["outline"][1] != "0px", look
    page.keyboard.press("Escape")

    # And a paragraph is still text: the click reaches no picture and raises nothing.
    page.locator("#p").click()
    expect(
        page.locator(".lf-fab-input"),
        "a click on prose was read as a click on a picture",
    ).not_to_be_visible()


def _bracket_ink_changes(quiet, painted, target, clip, ink):
    """Count new ink along both bracket sides and each of their four end caps."""
    difference = ImageChops.difference(quiet, painted)
    left = target["x"] - clip["x"]
    top = target["y"] - clip["y"]
    right = left + target["width"]
    bottom = top + target["height"]
    boxes = {
        "left": (
            math.floor(left) - 1,
            math.floor(top) + 4,
            math.ceil(left) + 2,
            math.ceil(bottom) - 4,
        ),
        "right": (
            math.floor(right) - 2,
            math.floor(top) + 4,
            math.ceil(right) + 1,
            math.ceil(bottom) - 4,
        ),
    }
    for side, x1, x2 in [
        ("left", left + 4, left + 10),
        ("right", right - 10, right - 4),
    ]:
        for end, y in [("top", top), ("bottom", bottom)]:
            boxes[f"{end}-{side}"] = (
                math.floor(x1),
                math.floor(y) - 1,
                math.ceil(x2),
                math.ceil(y) + 2,
            )
    changed = {
        name: sum(
            delta != (0, 0, 0)
            and max(abs(channel - expected) for channel, expected in zip(pixel, ink))
            <= 40
            for pixel, delta in zip(
                painted.crop(edge).get_flattened_data(),
                difference.crop(edge).get_flattened_data(),
            )
        )
        for name, edge in boxes.items()
    }
    missing = [
        name
        for name, count in changed.items()
        if count < max(difference.crop(boxes[name]).size) / 2
    ]
    return changed, missing


def test_a_screenshot_comment_contour_paints_above_its_edge_to_edge_frame(
    browser, serve
):
    """A declared visual's annotation contour is above its package-owned children.

    lf-shot is the causal case: its positioned frame reaches every side of a host with
    no border of its own. A source-element outline sits below that frame and disappears
    down both sides. Both projected brackets, including their end caps, remain above
    the frame.
    """
    example = next(path for path in EXAMPLES if path.stem == "release-notes")
    page = open_page(browser, serve(example))
    shot = page.locator("#rn-console-shot")
    shot.get_by_role("button", name="Slider", exact=True).click()
    shot.scroll_into_view_if_needed()
    box = shot.bounding_box()
    clip = {
        "x": math.floor(box["x"]) - 8,
        "y": math.floor(box["y"]) - 8,
        "width": math.ceil(box["x"] + box["width"]) - math.floor(box["x"]) + 16,
        "height": math.ceil(box["y"] + box["height"]) - math.floor(box["y"]) + 16,
    }

    def screenshot():
        return Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")

    quiet = screenshot()
    comparison = shot.locator("wa-comparison")
    comparison.click(modifiers=["Alt"], position={"x": box["width"] / 4, "y": 80})
    expect(comparison).to_have_attribute("position", "50")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(shot).to_have_class(re.compile(r"\blf-projected-mark\b"))
    overlay = page.locator(".lf-visual-mark-pending")
    expect(overlay).to_be_visible()
    contour = overlay.evaluate(
        """element => { const style = getComputedStyle(element, '::after');
          // A mixed ink computes as color(srgb …); a canvas reads any colour as bytes.
          const pen = document.createElement('canvas').getContext('2d');
          pen.fillStyle = style.outlineColor;
          pen.fillRect(0, 0, 1, 1);
          return {
            ink: [...pen.getImageData(0, 0, 1, 1).data.slice(0, 3)],
            outset: parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth),
          }; }"""
    )
    marked = screenshot()

    # The contour stands outside the frame, so its edges are the outline's outer box.
    outset = contour["outset"]
    outer = {
        "x": box["x"] - outset,
        "y": box["y"] - outset,
        "width": box["width"] + 2 * outset,
        "height": box["height"] + 2 * outset,
    }
    changed, _ = _bracket_ink_changes(quiet, marked, outer, clip, contour["ink"])
    assert all(changed[side] > 0 for side in changed), (
        f"the screenshot frame covered part of its annotation contour: {changed}"
    )


def test_a_focused_card_comment_never_paints_over_the_cards_contents(browser, serve):
    """The selected thread may strengthen its contour, but its overlay stays hollow.

    This is the checkout-release regression: the metric fills its host edge to edge,
    so a mark projected above the widget also sits above every word the widget draws.
    Comparing the interior with that overlay hidden makes the guarantee independent of
    the widget's DOM, colors, and stacking choices.
    """
    example = next(path for path in EXAMPLES if path.stem == "live-progress")
    url = serve(example)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "blocked-card-comment",
            "author": "user",
            "revision": 1,
            "text": "Swap this with the next block.",
            "anchor": {"section": "lp-k-checks"},
        },
    )
    page = open_page(browser, url)
    stand_on_thread(page, "blocked-card-comment")

    card = page.locator("#lp-k-checks")
    mark = page.locator('.lf-visual-mark[data-for="lp-k-checks"].lf-visual-mark-here')
    expect(mark).to_be_visible()
    card.scroll_into_view_if_needed()
    # Include the floating thread's final placement and shadow in both captures.
    rendered(page)
    box = card.bounding_box()

    def screenshot():
        return Image.open(io.BytesIO(page.screenshot(clip=box))).convert("RGB")

    marked = screenshot()
    mark.evaluate("element => { element.style.visibility = 'hidden'; }")
    bare = screenshot()
    inset = math.ceil(3 * page.evaluate("devicePixelRatio"))
    interior = (inset, inset, marked.width - inset, marked.height - inset)
    difference = ImageChops.difference(marked.crop(interior), bare.crop(interior))
    assert difference.getbbox() is None, (
        "the selected comment painted inside the metric card instead of only around it"
    )
    mark.evaluate("element => { element.style.removeProperty('visibility'); }")


def test_a_screenshot_margin_trace_paints_both_quiet_brackets(browser, serve):
    """A margin control traces a visual target above its edge-to-edge children."""
    example = next(path for path in EXAMPLES if path.stem == "release-notes")
    page = open_page(browser, serve(example))
    resized(page, 1200, 900)
    margins_laid_out(page)
    shot = page.locator("#rn-console-shot")
    shot.scroll_into_view_if_needed()
    box = shot.bounding_box()
    clip = {
        "x": math.floor(box["x"]) - 2,
        "y": math.floor(box["y"]) - 2,
        "width": math.ceil(box["x"] + box["width"]) - math.floor(box["x"]) + 4,
        "height": math.ceil(box["y"] + box["height"]) - math.floor(box["y"]) + 4,
    }

    def screenshot():
        return Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")

    quiet = screenshot()
    # Exercise the generic contribution trace with a real public registration;
    # the screenshot's own endpoint actions live in its native control rail.
    page.evaluate("""async () => {
      const {contributionEntry, registerContribution} =
        await window.__lfWidgetApi();
      registerContribution({key: 'review-capture',
        target: document.querySelector('#rn-console-shot'),
        read: () => ({entries: [contributionEntry({key: 'review', glyph: 'R',
          label: 'Review capture'})]}), activate: () => {},
      });
    }""")
    margins_laid_out(page)
    toggle = page.get_by_role("button", name="Review capture", exact=True)
    toggle.hover()
    trace = page.locator('.lf-target-trace[data-for="rn-console-shot"]')
    expect(trace).to_be_visible()
    ink = trace.evaluate(
        """element => {
          const canvas = document.createElement('canvas');
          const context = canvas.getContext('2d');
          context.fillStyle = getComputedStyle(element, '::after').outlineColor;
          context.fillRect(0, 0, 1, 1);
          return [...context.getImageData(0, 0, 1, 1).data.slice(0, 3)];
        }"""
    )
    traced = screenshot()

    outset = trace.evaluate(
        "element => { const s = getComputedStyle(element, '::after');"
        " return parseFloat(s.outlineOffset) + parseFloat(s.outlineWidth); }"
    )
    outer = {
        "x": box["x"] - outset,
        "y": box["y"] - outset,
        "width": box["width"] + 2 * outset,
        "height": box["height"] + 2 * outset,
    }
    changed, missing = _bracket_ink_changes(quiet, traced, outer, clip, ink)
    assert not missing, (
        f"the screenshot frame covered the trace's {missing} edge: {changed} ink pixels"
    )
    assert shot.evaluate("element => getComputedStyle(element).outlineStyle") == "none"
    shot.get_by_role("button", name="Pair", exact=True).click()
    expect(shot.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()


def test_a_diagram_follows_the_scheme_it_is_read_in(browser, serve):
    """The SVG keeps Leaf's theme variables, so a scheme flip repaints it live."""
    page = open_page(browser, serve(WIDE_DIAGRAM_PAGE))
    node = (
        page.locator('#flow g[data-id="S"]')
        .locator("rect, polygon, path, circle, ellipse")
        .first
    )
    expect(node).to_be_visible()
    fill = "el => getComputedStyle(el).fill"
    light = node.evaluate(fill)
    expected = page.evaluate(
        """() => {
          const probe = document.createElement('i');
          probe.style.cssText = 'color:color-mix(in srgb, var(--accent) 10%, var(--paper))';
          document.body.append(probe);
          const color = getComputedStyle(probe).color;
          probe.remove();
          return color;
        }"""
    )
    assert light == expected, "the renderer must receive Leaf's accent-tinted surface"
    page.emulate_media(color_scheme="dark")
    assert node.evaluate(fill) != light, (
        "a diagram's node surface must follow the page's scheme"
    )


def test_diagrams_keep_fonts_and_svg_definitions_inside_the_page(browser, serve):
    """Renderer output cannot import a web font or reuse one SVG's definition ids.

    The renderer emits the same marker ids in every result unless it is given a prefix,
    and names its own faces. Leaf passes each rendering a prefix and the page's faces,
    so several diagrams remain independent and the page stays self-contained.
    """
    page = open_page(browser, serve(TYPED_PARTS_PAGE))
    readings = page.evaluate(
        r"""() => {
          const svgs = [...document.querySelectorAll('lf-diagram svg')];
          const ids = svgs.flatMap(svg => [...svg.querySelectorAll('[id]')]
            .map(el => el.id));
          const badReferences = svgs.flatMap((svg, diagram) =>
            [...svg.querySelectorAll('*')].flatMap(el =>
              [...el.attributes].flatMap(attr => {
                const refs = [...attr.value.matchAll(/(?:url\()?\(#([^\s)]+)\)?/g)];
                return refs
                  .filter(([, id]) => !svg.querySelector(`#${CSS.escape(id)}`))
                  .map(([, id]) => ({diagram, attribute: attr.name, id}));
              })));
          const probe = document.createElement('i');
          probe.style.cssText = 'font-family:var(--sans);position:fixed;visibility:hidden';
          document.body.append(probe);
          const expectedFont = getComputedStyle(probe).fontFamily;
          probe.remove();
          return {
            count: svgs.length,
            ids,
            badReferences,
            styles: svgs.map(svg => svg.querySelector('style')?.textContent ?? ''),
            fonts: svgs.map(svg => svg.querySelector('text')).filter(Boolean)
              .map(text => getComputedStyle(text).fontFamily),
            expectedFont,
          };
        }"""
    )
    assert readings["count"] == 6, "the fixture covers every supported diagram type"
    assert len(readings["ids"]) == len(set(readings["ids"])), readings["ids"]
    assert readings["badReferences"] == []
    assert not any(
        "@import" in style or "fonts.googleapis.com" in style
        for style in readings["styles"]
    )
    assert len(readings["fonts"]) == readings["count"]
    # The renderer appends its own generic fallbacks after the face it is handed; the
    # page's face resolves first, so they are never reached.
    assert all(f.startswith(readings["expectedFont"]) for f in readings["fonts"]), (
        readings["fonts"]
    )


def test_a_diagram_label_cannot_inject_markup_into_the_rendered_svg(browser, serve):
    """Renderer text remains text when Leaf inserts the returned SVG markup."""
    hostile = leaf_page(
        "diagram text",
        """
<h1 id="title">Diagram text</h1>
<lf-diagram id="flow"><pre>
flowchart LR
  A["&lt;img src=x onerror=window.lfInjected=true&gt;"] --&gt; B
</pre></lf-diagram>
""",
    )
    page = open_page(browser, serve(hostile))

    expect(page.locator("#flow svg text").filter(has_text="<img")).to_have_count(1)
    expect(page.locator("#flow img, #flow script")).to_have_count(0)
    assert not page.evaluate("() => !!window.lfInjected")


def test_a_diagram_takes_the_room_and_scrolls_only_past_it(browser, serve):
    """A diagram keeps the natural geometry its renderer laid out.

    Scaling a wide drawing to the column takes its labels below legibility. The module
    states the viewBox width explicitly, so only how much of that natural drawing fits
    in the available room changes.

    Which is the whole of it wherever the window has the room. A drawing is not a box
    that fills whatever it is given, so the one width the vocabulary shares is no promise
    about it: held to that number, this 1147px flowchart was cut off at 1080 on a window
    with 470px to spare. The board on the
    same page is the half that says the declaration is doing this rather than the tag —
    it declares `wide` with its `data-width` and lays its columns out into whatever it is
    given, so it takes that shared number and stops there on the same window that hands
    the diagram all of the room.

    Past the room there is nothing left to give, and the answer is the theme's for any
    wide content: the widget's own box scrolls sideways and the document does not."""
    page = open_page(browser, serve(WIDE_DIAGRAM_PAGE))

    # This width leaves the complete drawing room on both supported font platforms.
    resized(page, 1920, 900)
    wide = page.evaluate(DIAGRAM_ROOM)
    assert wide["natural"] > wide["wide"], (
        f"the fixture must lay out wider than the shared width ({wide['wide']:.0f}px), "
        "or the window having room says nothing"
    )
    assert wide["natural"] < wide["room"], (
        "and inside the room this window has, or nothing here is about being cut off"
    )
    assert round(wide["drawn"]) == round(wide["natural"]), (
        f"the drawing was scaled to fit: natural {wide['natural']:.0f}px, "
        f"drawn {wide['drawn']:.0f}px"
    )
    assert not wide["scrolls"], (
        f"a window with the room for the whole drawing still cut it off: "
        f"{wide['natural']:.0f}px of diagram in a {wide['box']:.0f}px box"
    )
    assert wide["board"] <= wide["wide"] + 1, (
        f"the board took the room too, so what grew was the tag and not what it "
        f"declares: board {wide['board']:.0f}px against {wide['wide']:.0f}px"
    )
    assert wide["board"] > wide["column"] + 1, (
        "and the board must still be growing, or its half of this proves nothing"
    )
    assert root_overflow(page) == 0, "the page itself must not scroll sideways"

    resized(page, 1000, 900)
    narrow = page.evaluate(DIAGRAM_ROOM)
    assert narrow["natural"] > narrow["room"], (
        "the narrow half proves nothing unless the drawing outgrows the room"
    )
    assert round(narrow["drawn"]) == round(narrow["natural"]), (
        "a drawing that no longer fits is still not scaled down"
    )
    assert narrow["scrolls"], "a drawing wider than the room must scroll inside its box"
    assert root_overflow(page) == 0, "nor may the page scroll sideways for it"


def test_a_marked_scrolling_visual_keeps_its_keyboard_focus_ring(browser, serve):
    """A focused visual paints one projected ring; entering its thread keeps the
    reference on the same target without restoring a second source outline."""
    url = serve(WIDE_DIAGRAM_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "diagram-comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the focus visible.",
            "anchor": {"section": "flow"},
        },
    )
    page = open_page(browser, url)
    resized(page, 760, 900)
    diagram = page.locator("#flow")
    expect(diagram).to_have_attribute("tabindex", "0")
    diagram.focus()
    assert diagram.evaluate("element => element.matches(':focus-visible')")
    rendered(page)
    ring = current_location_ring(page)
    assert ring and ring["cuts"] == ring["covers"] == [], ring
    mark = page.locator(".lf-visual-mark")
    expect(page.locator(".lf-visual-mark-focus")).to_have_attribute("data-for", "flow")

    resized(page, 1200, 900)
    stand_on_thread(page, "diagram-comment")
    expect(diagram).to_have_class(re.compile(r"\blf-mark-here\b"))
    expect(diagram).to_have_css("outline-style", "none")
    expect(mark).to_have_class(re.compile(r"\blf-visual-mark-here\b"))


def test_a_widget_that_failed_soft_claims_no_room(browser, serve):
    """A wide widget's room is for the thing it draws, and a widget whose upgrade failed
    has not drawn it: what stands there is the message and the source it choked on, which
    is prose and belongs in the measure the page's prose is set to. Taking the room
    anyway put a parse error across the whole window with its message on one line."""
    page = open_page(browser, serve(BROKEN_DIAGRAM_PAGE))
    # The page reports the renderer's refusal, which is what the fixture is for.
    consume_browser_errors(page, '<lf-diagram id="bad"> failed: ')
    resized(page, 1600, 900)
    at = page.evaluate("""() => {
        const box = document.getElementById('bad').querySelector('.lf-error');
        const main = document.querySelector('main'), ms = getComputedStyle(main);
        const mb = main.getBoundingClientRect();
        return { failed: !!box,
                 box: box ? box.getBoundingClientRect().width : 0,
                 widget: document.getElementById('bad').getBoundingClientRect().width,
                 // What the box would be floored at if nothing said otherwise: the
                 // source is a `pre`, so its longest line is its minimum width.
                 source: box ? box.querySelector('pre').scrollWidth : 0,
                 column: mb.width - parseFloat(ms.paddingLeft)
                         - parseFloat(ms.paddingRight) };
    }""")
    assert at["failed"], "the fixture must fail to render, or this proves nothing"
    assert at["source"] > at["column"], (
        f"the fixture's source must be wider than the {at['column']:.0f}px column at the "
        f"size it is set in, or the box has nothing to be floored at"
    )
    assert at["box"] <= at["column"] + 1, (
        f"the message stands {at['box']:.0f}px wide in a {at['column']:.0f}px column"
    )
    assert at["widget"] <= at["column"] + 1, (
        f"and the widget with it: {at['widget']:.0f}px, so the message hangs into the "
        "margin behind a scrollbar"
    )


def test_a_tab_set_whose_runtime_could_not_start_shows_every_panel(browser, serve):
    """A live page draws a tab set's first panel alone before its module upgrades it,
    and the strip the module builds is the only way to the rest. Where the runtime could
    not start, no strip will come, so every panel stands under its label. Without the
    startup failure guard the second panel computes to `display: none` and the page
    keeps a word the user cannot reach."""
    url = serve(
        leaf_page(
            "tabs",
            '<h1 id="t">Tabs</h1>\n<lf-tabs id="views">'
            '<lf-tab id="one" label="One"><p id="first">First.</p></lf-tab>'
            '<lf-tab id="two" label="Two"><p id="second">Second.</p></lf-tab></lf-tabs>',
        )
    )
    page = browser.new_page()
    page.route("**/widgets/lf-tabs.js", lambda route: route.abort())
    page.goto(url, wait_until="load")
    expect(
        page.get_by_text("Leaf couldn't start. Waiting for Leaf to update.")
    ).to_be_visible()
    expect(page.locator("#views")).not_to_have_class("lf-rendered")
    expect(page.locator("#first")).to_be_visible()
    expect(page.locator("#second")).to_be_visible()
    assert (
        page.evaluate(
            "getComputedStyle(document.getElementById('two'), '::before').content"
        )
        == '"Two"'
    )
    consume_browser_errors(page, "lf-tabs.js", "net::ERR_FAILED")


def test_a_drawing_that_will_never_draw_claims_no_room(browser, serve):
    """The room is for the drawing. While the renderer loads, a live page gives the box
    that room from first paint so the drawing lands without moving anything; once the
    renderer cannot arrive, the page did not start, and the source is the whole of what
    the user sees. It is evidence, which reads at the column's width from the column's
    own edge. Held to the room, three sources came out centred at three indents, none of
    them the column's."""
    url = serve(DIAGRAM_AND_RAIL_PAGE)
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    page.route("**/widgets/lf-diagram.js", lambda route: route.abort())
    page.goto(url, wait_until="load")
    expect(
        page.get_by_text("Leaf couldn't start. Waiting for Leaf to update.")
    ).to_be_visible()
    expect(page.locator("body")).not_to_have_attribute("data-lf-upgraded", "1")
    at = page.evaluate("""() => {
        const main = document.querySelector('main'), ms = getComputedStyle(main);
        const mb = main.getBoundingClientRect();
        const left = mb.left + parseFloat(ms.paddingLeft);
        const right = mb.right - parseFloat(ms.paddingRight);
        return { column: right - left, left,
                 sources: ['small', 'flow'].map((id) => {
                     const el = document.getElementById(id);
                     return { id, drawn: !!el.querySelector('svg'),
                              box: el.getBoundingClientRect().width,
                              at: el.querySelector('pre').getBoundingClientRect().left };
                 }) };
    }""")
    for source in at["sources"]:
        assert not source["drawn"], (
            f"#{source['id']} rendered anyway, so the blocked module proves nothing"
        )
        assert source["box"] <= at["column"] + 1, (
            f"#{source['id']}'s box took {source['box']:.0f}px of room for a drawing it "
            f"has not made, against a {at['column']:.0f}px column"
        )
        assert abs(source["at"] - at["left"]) <= 1, (
            f"#{source['id']}'s source starts at {source['at']:.0f}px and the column at "
            f"{at['left']:.0f}px: it is set as a drawing is placed rather than read"
        )
    # The blocked module is the state under test, and what the page says about it is
    # the refusal itself.
    consume_browser_errors(page, "lf-diagram.js", "net::ERR_FAILED")


def test_a_drawing_stands_on_the_columns_axis_until_it_needs_the_free_margin(
    browser, serve
):
    """A drawing's box is the room, and a drawing is placed rather than the box: on the
    column's axis while it fits, out into the margins when it needs the room, and behind
    a reachable scrollbar when even the room is short. The rail claims nothing, so with
    a row standing in it both margins are still the drawings' to take: the wide one held
    to the column's right edge with the margin beside it empty is the fault.

    The narrow read is the other half. With the window closed in, the room genuinely
    runs short, the box scrolls, and the overflow must be laid out where the scroll can
    reach it: an overflow off the start edge is unreachable in any direction, and the
    drawing's first node is the one a user follows the graph from."""
    page = open_page(browser, serve(DIAGRAM_AND_RAIL_PAGE))
    # Check both a roomy page and one whose available width is shorter than the drawing.
    resized(page, 1920, 900)
    at = page.evaluate(DRAWING_PLACEMENT)

    assert at["place"] == "rail", (
        "the row is not in the rail, so nothing here shows a rail leaving the "
        "margin to the drawing"
    )
    assert at["small"]["width"] < at["col"]["right"] - at["col"]["left"], (
        "the small drawing must fit the column, or its placement says nothing"
    )
    assert abs(at["small"]["offAxis"]) <= 1, (
        f"a drawing that fits sits off the axis of the prose it explains by "
        f"{at['small']['offAxis']:.0f}px: it reads as an exhibit that slipped"
    )

    assert at["flow"]["width"] > at["col"]["right"] - at["col"]["left"], (
        "the wide drawing must outgrow the column, or the margin is never asked for"
    )
    assert at["flow"]["box"]["left"] < at["col"]["left"] - 1, (
        "a drawing that needs the room must take the free margin: its box starts at "
        f"{at['flow']['box']['left']:.0f}px, the column at {at['col']['left']:.0f}px"
    )
    assert at["flow"]["box"]["right"] > at["col"]["right"] + 1, (
        f"a drawing no row is level with is held to the column's right edge: its box "
        f"ends at {at['flow']['box']['right']:.0f}px, the column at "
        f"{at['col']['right']:.0f}px — the rail claims none of the margin"
    )
    assert not at["flow"]["scrolls"], (
        "with both margins the room holds this drawing whole, so a scrollbar here is "
        "room withheld"
    )
    assert abs(at["flow"]["offAxis"]) <= 1, (
        f"a drawing the room holds sits {at['flow']['offAxis']:.0f}px off the column's "
        "axis"
    )

    resized(page, 1000, 900)
    at = page.evaluate(DRAWING_PLACEMENT)
    assert at["flow"]["scrolls"], (
        "this drawing outgrows the narrow page's room, so its box must scroll"
    )
    assert abs(at["flow"]["left"] - at["flow"]["box"]["left"]) <= 1, (
        f"the overflow was laid out off the box's start edge, where no scroll reaches "
        f"it: drawing from {at['flow']['left']:.0f}px, box from "
        f"{at['flow']['box']['left']:.0f}px"
    )
    assert root_overflow(page) == 0, "the page must not scroll sideways for either"


def test_a_widget_that_declares_width_takes_the_room_and_the_column_stays_put(
    browser, serve
):
    """A board's columns are as wide as what they hold, a diff's lines are as long as its
    files', and prose is set to a measure, so a page carrying all three used to be a
    cramped board or a page widened past its own measure for one exhibit. x-space
    declares the capacity a widget needs, and the theme spends the room the layout
    measured, so each exhibit grows and the prose does not move. The board, a surface,
    takes all the room; the diff, slightly wider than the column, starts at the prose's
    edge and stops at the shared cap.

    The code block is the half that says the declaration is doing this. It is a widget
    too, and declares nothing, so it stays in the column: a rule that reached every
    widget, or one naming lf-board, would pass every other assertion here and fail this
    one."""
    page = open_page(browser, serve(WIDE_AND_NARROW_PAGE))

    wide = page.evaluate(ROOM_GEOMETRY)
    board, patch, column = wide["board"], wide["widePatch"], wide["column"]
    # The room is the body's box; a breakout stops at the shell's 24px gutter.
    for edge, inset in (("left", 24), ("right", -24)):
        assert board[edge] == pytest.approx(wide["room"][edge] + inset, abs=1), (
            f"an available board fills the room: its {edge} edge is at "
            f"{board[edge]:.0f}px, the room's at {wide['room'][edge]:.0f}px"
        )
    assert patch["left"] == pytest.approx(column["left"], abs=1), (
        "a wide exhibit starts where the prose starts, or it reads as one that slipped: "
        f"diff at {patch['left']:.0f}, column at {column['left']:.0f}"
    )
    # Room to spare at this viewport, so a diff stopping short of it is the shared cap
    # binding rather than the window: one width for the vocabulary, not each widget's own.
    assert column["width"] < patch["width"] < wide["room"]["width"], (
        "the wide breakout must stop at one stated width, not fill whatever is there: "
        f"diff {patch['width']:.0f}px, room {wide['room']['width']:.0f}px"
    )
    assert abs(wide["diff"]["width"] - column["width"]) <= 1, (
        "a widget that declares nothing keeps the column: code block "
        f"{wide['diff']['width']:.0f}px against {column['width']:.0f}px"
    )
    assert abs(wide["prose"]["width"] - column["width"]) <= 1, (
        "prose keeps its measure whatever the exhibits beside it do"
    )
    assert root_overflow(page) == 0, "the page must not scroll sideways"

    # Under the column's own width there is no room to take, and the rule has to come out
    # as the layout the page already had: the same edge, not an inset approximation of it.
    resized(page, 700, 900)
    narrow = page.evaluate(ROOM_GEOMETRY)
    assert narrow["column"]["width"] < 720, (
        "the narrow half proves nothing unless the window is under the column"
    )
    for name in ("board", "widePatch"):
        assert abs(narrow[name]["left"] - narrow["column"]["left"]) <= 1, (
            f"the {name} on a narrow window must start where the prose starts: at "
            f"{narrow[name]['left']:.0f}, column at {narrow['column']['left']:.0f}"
        )
        assert abs(narrow[name]["width"] - narrow["column"]["width"]) <= 1, (
            f"and be the column exactly: {name} "
            f"{narrow[name]['width']:.0f}px, column {narrow['column']['width']:.0f}px"
        )
    assert root_overflow(page) == 0, "nor scroll sideways on a narrow window"


def test_authored_blocks_choose_wide_or_available_space(browser, serve):
    """One authored width contract applies to native and package blocks. A widget read
    as text keeps the prose measure when nested in a wider section rather than taking
    its containing block's allocation: there an option list starts at the section's
    edge and keeps the measure, as the section's text does, rather than centred in the
    room."""
    source = leaf_page(
        "Authored block widths",
        """
<h1 id="title">Authored block widths</h1>
<p id="prose">Standard prose.</p>
<section id="wide" data-width="wide">
  <table id="table" data-width="available"><thead><tr><th>Case</th><th>Result</th></tr></thead>
    <tbody><tr><td>Native table</td><td>Uses its authored allocation.</td></tr></tbody></table>
  <p id="nested-prose">Prose within wide evidence.</p>
  <lf-options id="options" choose><lf-option id="option">One</lf-option></lf-options>
</section>
""",
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 1726, 900)
    at = page.evaluate("""() => {
      const result = {};
      for (const id of ['prose', 'wide', 'table', 'nested-prose', 'options']) {
        const el = document.getElementById(id), box = el.getBoundingClientRect();
        result[id] = {width: box.width, left: box.left,
          space: el.getAttribute('data-lf-space'), role: el.getAttribute('role')};
      }
      return result;
    }""")
    assert at["wide"]["space"] == "wide"
    assert at["table"]["space"] == "available"
    assert at["wide"]["width"] > at["prose"]["width"]
    assert at["table"]["width"] == pytest.approx(at["wide"]["width"], abs=1)
    assert at["options"]["space"] is None
    assert at["wide"]["left"] == pytest.approx(at["prose"]["left"], abs=1)
    for column in ("nested-prose", "options"):
        assert at[column]["width"] == pytest.approx(at["prose"]["width"], abs=1)
        assert at[column]["left"] == pytest.approx(at["wide"]["left"], abs=1)
    assert page.locator("#table").evaluate("el => el.tagName") == "TABLE"
    assert root_overflow(page) == 0

    next_source = source.replace(' data-width="wide"', "", 1)
    stamp_page(serve.page_dir, next_source, "remove an authored width")
    wait_for_revision(page, 2)
    expect(page.locator("#wide")).not_to_have_attribute("data-lf-space", "wide")

    resized(page, 540, 720)
    narrow = page.locator("#wide").evaluate(
        "el => ({box: el.getBoundingClientRect().width, viewport: innerWidth})"
    )
    assert narrow["box"] < narrow["viewport"]
    assert root_overflow(page) == 0


def test_a_boards_minimum_keeps_the_room_the_column_can_grant(browser, serve):
    """A widget's preferred minimum never claims the sidebar's margin. Native wide and
    available blocks read the same capacity; four and five board columns previously
    overrode it at mid widths, while the control without a sidebar fitted there.
    A board too narrow to share between columns stacks them inside that allocation,
    so neither it nor the page scrolls sideways.
    """
    sidebar = '<div class="layout-sidebar"><aside><div class="layout-track"><lf-toc id="contents"></lf-toc></div></aside><div class="layout-column">'
    boards = "".join(
        f'<lf-board id="board-{count}">'
        + "".join(
            f'<lf-column id="col-{count}-{i}" label="Column {i}"></lf-column>'
            for i in range(count)
        )
        + "</lf-board>"
        for count in (4, 5, 6)
    )
    for margin_content in (sidebar, ""):
        page = open_page(
            browser,
            serve(
                leaf_page(
                    "Board beside contents",
                    margin_content
                    + '<h1>Board beside contents</h1><section id="boards" class="layout-flow"><h2>Boards</h2>'
                    + '<div id="wide" data-width="wide">Wide evidence.</div>'
                    + '<div id="room" data-width="available">Available evidence.</div>'
                    + boards
                    + "</section>"
                    + ("</div></div>" if margin_content else ""),
                )
            ),
        )
        for width in (540, 840, 1040, 1440):
            resized(page, width, 900)
            at = page.evaluate("""() => Object.fromEntries(
              ['wide', 'room', 'board-4', 'board-5', 'board-6'].map(id => {
                const el = document.getElementById(id), b = el.getBoundingClientRect();
                return [id, {left: b.left, right: b.right, width: b.width,
                             scrolls: el.scrollWidth - el.clientWidth}];
              }))""")
            for name in ("wide", "board-4", "board-5", "board-6"):
                assert at[name]["left"] >= at["room"]["left"] - 1, (width, at)
                assert at[name]["right"] <= at["room"]["right"] + 1, (width, at)
            assert root_overflow(page) == 0, (width, at)
            if width == 540:
                assert at["board-4"]["scrolls"] == 0, at
                assert at["board-5"]["scrolls"] == 0, at
            elif width == 1440:
                assert at["wide"]["width"] == pytest.approx(wide_width(page), abs=1), at
                assert at["room"]["width"] > at["wide"]["width"], at


def test_an_obligation_and_a_callout_keep_the_column_and_widen_to_what_they_hold(
    browser, serve
):
    """On a sidebar page an obligation and a callout keep the prose's width and left edge, so
    the obligation's ring and pin stand beside what it asks, as on a column page. One granted
    `data-width`, or holding a block of its own that declares one, takes that room for
    the evidence. On a column page the wide block breaks out of the column, as it would
    from a section, and the obligation spans it, so the ring it wears goes round the block
    rather than cutting across it, while its heading keeps the column; the table's
    twelve columns need the room, since a table granted it takes only what its columns
    need. A workspace states neither width, so there every one of them, and a board,
    fills the region it stands in."""
    cells = "<td>p95 latency</td>" * 12
    table = '<table id="{id}-t" data-width="wide"><tr>' + cells + "</tr></table>"
    item = (
        '<lf-ask id="{id}"{width}><h3>Ship it?</h3>{table}<lf-options id="{id}-o" '
        'choose><lf-option id="{id}-yes">Yes</lf-option></lf-options></lf-ask>'
    )
    body = (
        '<p id="prose">Prose.</p>'
        + item.format(id="ask", width="", table="")
        + item.format(id="granted", width=' data-width="wide"', table="")
        + item.format(id="holds", width="", table=table.format(id="holds"))
        + '<aside class="callout" id="callout"><p>Paused.</p></aside>'
        + '<aside class="callout" id="granted-c" data-width="wide"><p>Wide.</p></aside>'
        + '<lf-options id="list" choose><lf-option id="list-a">Leave it</lf-option>'
        + f'<lf-option id="list-b">Raise it {table.format(id="list")}</lf-option>'
        + "</lf-options>"
    )
    measure = """() => Object.fromEntries(
      ['prose', 'ask', 'granted', 'granted-c', 'holds', 'holds-t', 'callout', 'list']
        .map(id => {
        const box = document.getElementById(id).getBoundingClientRect();
        return [id, {width: Math.round(box.width), left: Math.round(box.left)}];
      }))"""
    page = open_page(
        browser,
        serve(leaf_page("Sidebar body", f"<div>{body}</div>", layout="sidebar")),
    )
    resized(page, 1726, 900)
    at = page.evaluate(measure)
    edge = at["prose"]["left"]
    wide = round(wide_width(page))
    # An option list keeps the measure whatever one option holds: only a box's own
    # blocks widen it.
    for boxed in ("ask", "callout", "list"):
        assert at[boxed] == {"width": 720, "left": edge}, (boxed, at)
    # A granted callout's padding and border fall inside the wide measure.
    for granted in ("granted", "granted-c", "holds"):
        assert at[granted] == {"width": wide, "left": edge}, (granted, at)
    # The widened obligation frames its table, which stands wider than the measure.
    assert at["holds-t"]["width"] > 720, at

    # The obligation spans its block wherever the block breaks out, and an obligation granted the
    # room itself holds its block in that room. In a list obligation, which stands in from the
    # column, and where the page arranged the obligation, in a grid track, neither grows.
    extras = (
        "<ol><li>"
        + item.format(id="listed", width="", table=table.format(id="listed"))
        + "</li></ol>"
        + item.format(
            id="both", width=' data-width="wide"', table=table.format(id="both")
        )
        + '<div style="display: grid; grid-template-columns: 350px 1fr">'
        + item.format(id="tracked", width="", table=table.format(id="tracked"))
        + "<p>Beside.</p></div>"
        + item.format(
            id="narrow",
            width="",
            table='<table data-width="wide"><tr><td>a</td><td>b</td></tr></table>',
        )
        + '<div id="wrapper" data-width="wide">'
        + item.format(
            id="wrapped",
            width="",
            table=f'<table data-width="available"><tr>{cells}</tr></table>',
        )
        + "</div>"
        + '<div id="pulled" style="margin-inline: -150px">Pulled words.'
        + '<div data-width="available">Room.</div></div>'
        + '<div><span id="spilled" style="margin-left: -150px">Spilled words.'
        + '<div data-width="wide">Room.</div></span></div>'
        + '<div id="padded" style="margin-inline: -600px; padding-inline: 600px">'
        + '<div data-width="wide">Room.</div></div>'
        + '<div id="pinned" style="position: fixed; inset: auto 0 0 0">Pinned.</div>'
    )
    column = open_page(browser, serve(leaf_page("Column", body + extras)))
    resized(column, 1726, 900)
    at = column.evaluate(
        measure.replace(
            "'list']",
            "'list', 'listed', 'listed-t', 'both', 'both-t', 'tracked', 'wrapper',"
            " 'wrapped']",
        )
    )
    assert at["holds-t"]["width"] == wide, at
    assert at["holds-t"]["left"] == at["prose"]["left"], at
    assert at["holds"] == at["holds-t"], at
    heading = column.locator("#holds h3").bounding_box()
    assert round(heading["x"]) == at["prose"]["left"], (heading, at)
    assert at["ask"] == at["prose"], at
    assert at["listed"] == at["listed-t"], at
    assert at["listed"]["width"] < at["prose"]["width"], at
    assert at["both"] == at["both-t"] == {"width": wide, "left": at["holds"]["left"]}, (
        at
    )
    assert at["tracked"]["width"] == 350, at
    # An obligation inside a breakout takes its holder's room, as any block
    # there does, however much room its own block asks for.
    assert at["wrapped"] == at["wrapper"], at
    # An obligation that spans its block is a breakout the theme grows, so the gate reads it
    # as one, even where it reaches further than a table of two columns does; a box the
    # page pulls out of the column by its margins, an inline one, or one it grows round
    # its block by margins and padding of its own, still stands in the margin. A fixed
    # box across the column's edges answers for itself, as it hangs off the window.
    misplaced = evaluate_probe(column, "misplacedBoxes")
    assert [(m["code"], m["at"]) for m in misplaced] == [
        ("past-column", "<div id=pulled>"),
        ("past-column", "<span id=spilled>"),
        ("past-column", "<div id=padded>"),
        ("clipped-out", "<div id=padded>"),
    ], misplaced

    board = (
        '<lf-board id="board"><lf-column id="board-c" label="Open">'
        '<lf-card id="board-k">Retry</lf-card></lf-column></lf-board>'
    )
    workspace = open_page(
        browser,
        serve(
            leaf_page(
                "Workspace",
                f'<div id="region">{body}{board}</div>',
                layout="workspace",
            )
        ),
    )
    resized(workspace, 1726, 900)
    at = workspace.evaluate(measure.replace("'list']", "'list', 'region', 'board']"))
    for block in ("prose", "ask", "granted", "granted-c", "holds", "callout", "list"):
        assert at[block] == at["region"], (block, at)
    assert at["board"] == at["region"], at

    # With no evidence width, a board reaches only its holder: six columns in a narrow
    # cell of the page's grid scroll inside it rather than spread over the next cell.
    columns = "".join(
        f'<lf-column id="c{i}" label="C{i}"></lf-column>' for i in range(6)
    )
    cells = leaf_page(
        "Workspace cells",
        f'<div id="cells"><div id="cell"><lf-board id="six">{columns}</lf-board></div>'
        "<div>Beside.</div></div>",
        head="<style>#cells { display: grid; grid-template-columns: 290px 1fr; }</style>",
        layout="workspace",
    )
    workspace = open_page(browser, serve(cells))
    resized(workspace, 1726, 900)
    box = workspace.evaluate(
        """() => Object.fromEntries(['cell', 'six'].map(id =>
          [id, Math.round(document.getElementById(id).getBoundingClientRect().width)]))"""
    )
    assert box["six"] == box["cell"], box


@pytest.mark.parametrize(
    ("margin_content", "placement", "engine"),
    [
        ("", "even", engine)
        for engine in ("browser", "firefox_browser", "webkit_browser")
    ],
)
@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_table_granted_room_stands_on_the_prose_axis(
    request, serve, margin_content, placement, engine, direction
):
    """A table given `data-width` keeps its columns' natural width and stands where any
    breakout of that width stands. A `wide` one starts at the prose's start edge and
    grows toward the end. An `available` one is centred on the prose axis while both margins have
    room for it, the freer side taking what the narrower lacks, as where a contents
    map's spine or a column moved over for a sidenote leaves one side narrower. One that
    fits the column keeps its natural width and starts where the prose starts. Where a
    sidebar stands in the left margin the room is all on the right, so the table starts
    at the prose's left edge and grows right. In a right-to-left page the same holds
    with the narrow table at the prose's right edge, where its text starts; the sidebar
    stands on the left there too.

    A table written in the other direction from its holder stands there too, since the
    browser keeps an over-wide box at its holder's start, not its own. Where the page
    arranges the box itself, as in a cell of its own two-track grid or as an item of
    that grid, the room beside it is the page's other track, so the table stays in its
    box and scrolls its columns there: its natural width had widened its track and
    crushed the other to 30px, and as an item it had stood across both tracks. Chromium,
    Firefox and WebKit place them the same."""
    browser = request.getfixturevalue(engine)
    head = "".join(f"<th>Column {i}</th>" for i in range(8))
    row = "".join(f"<td>measured value {i}</td>" for i in range(8))
    grid = f"<thead><tr>{head}</tr></thead><tbody><tr>{row}</tr></tbody>"
    other = "rtl" if direction == "ltr" else "ltr"
    body = (
        f"{margin_content}<h1>Tables</h1>"
        '<p id="prose">A paragraph at the measure, long enough to fill the column it '
        "stands in from one edge to the other.</p>"
        f'<table id="wide" data-width="available">{grid}</table>'
        f'<table id="edge" data-width="wide">{grid}</table>'
        '<div id="room" data-width="available">The room.</div>'
        '<table id="narrow" data-width="available"><tr><th>Plan</th><td>60</td></tr>'
        "</table>"
        f'<table id="turned" dir="{other}" data-width="available">{grid}</table>'
        '<div class="pair"><div id="beside"><p>Left cell.</p></div>'
        f'<div id="cell"><p>Right cell.</p><table id="celled" data-width="available">'
        f"{grid}</table></div></div>"
        '<div class="pair"><p>Left cell.</p>'
        f'<table id="itemed" data-width="available">{grid}</table></div>'
    )
    source = leaf_page(
        "Tables granted room",
        body,
        head="<style>.pair { display: grid; grid-template-columns: 1fr 1fr; "
        "gap: 16px; }</style>",
    ).replace('<html lang="en">', f'<html lang="en" dir="{direction}">', 1)
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    margins_laid_out(page)
    at = page.evaluate("""() => {
      const edges = (el) => {
        const box = el.getBoundingClientRect();
        return {left: box.left, right: box.right, centre: (box.left + box.right) / 2};
      };
      const grid = (id) => edges(document.querySelector(`#${id} tr`));
      return {
        prose: edges(document.getElementById('prose')),
        room: edges(document.getElementById('room')),
        wide: grid('wide'),
        edge: grid('edge'),
        narrow: grid('narrow'),
        turned: grid('turned'),
        celled: edges(document.getElementById('celled')),
        itemed: edges(document.getElementById('itemed')),
        beside: edges(document.getElementById('beside')),
        cell: edges(document.getElementById('cell')),
      };
    }""")
    prose = at["prose"]
    start = "left" if direction == "ltr" else "right"
    assert at["narrow"][start] == pytest.approx(prose[start], abs=1), at
    width = lambda box: box["right"] - box["left"]
    over = width(at["wide"]) - width(prose)
    assert 0 < over <= width(at["room"]) - width(prose) + 1, at
    free_left = prose["left"] - at["room"]["left"]
    free_right = at["room"]["right"] - prose["right"]
    grown = max(max(0, over - free_right), min(over / 2, free_left))
    assert at["wide"]["left"] == pytest.approx(prose["left"] - grown, abs=1), at
    if placement == "sidebar":
        assert at["wide"]["left"] == pytest.approx(prose["left"], abs=1), at
    elif placement == "even":
        assert at["wide"]["centre"] == pytest.approx(prose["centre"], abs=1), at
    # A `wide` table grows only from the prose's start edge, toward the end side.
    assert at["edge"][start] == pytest.approx(prose[start], abs=1), at
    free_end = free_right if direction == "ltr" else free_left
    wide = wide_width(page)
    if width(prose) + free_end >= wide:
        expected = min(wide, width(at["wide"]))
        assert width(at["edge"]) == pytest.approx(expected, abs=1), at
    for edge in ("left", "right"):
        assert at["turned"][edge] == pytest.approx(at["wide"][edge], abs=1), at
        for kept in ("celled", "itemed"):
            assert at[kept][edge] == pytest.approx(at["cell"][edge], abs=1), (kept, at)
    assert width(at["beside"]) == pytest.approx(width(at["cell"]), abs=1), at
    assert root_overflow(page) == 0


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_scrolling_breakout_table_keeps_its_caption_in_its_scrollport(
    browser, serve, subtests, direction
):
    """A table granted room sizes its box to its columns, so it is no longer the
    container its caption reads its width from; the caption is held to the box instead.
    On a phone, where the room is the column and an eight-column table scrolls, a long
    caption stays inside the scrollport at either end of the scroll: in the page's flow,
    and in a list item and a quotation, which hold it to their own width. Each holder's
    table scrolls alone, so one page holds all three."""
    cells = "".join(f"<td>measured value {i}</td>" for i in range(8))
    caption = "Services in the migration, by stage, with their owners and windows"

    def table(holder):
        return (
            f'<table id="{holder}" data-width="available"><caption>{caption}</caption>'
            f"<tr>{cells}</tr></table>"
        )

    body = (
        "<h1>Tables</h1><p>A paragraph at the measure.</p>"
        + table("flow")
        + f"<ol><li>An item holding the table.{table('list-item')}</li></ol>"
        + "<blockquote><p>A quotation holding the table.</p>"
        + f"{table('quotation')}</blockquote>"
    )
    source = leaf_page("Caption", body).replace(
        '<html lang="en">', f'<html lang="en" dir="{direction}">', 1
    )
    page = open_page(browser, serve(source))
    resized(page, 390, 844)
    reading = """t => {
      const box = t.getBoundingClientRect(), cap = t.querySelector('caption')
        .getBoundingClientRect();
      return {box: [box.left, box.right], caption: [cap.left, cap.right]};
    }"""
    for holder in ("flow", "list-item", "quotation"):
        with subtests.test(holder=holder):
            wide = page.locator(f"#{holder}")
            assert wide.evaluate("t => t.scrollWidth > t.clientWidth")
            for end in (0, -10_000 if direction == "rtl" else 10_000):
                wide.evaluate("(t, x) => { t.scrollLeft = x; }", end)
                rendered(page)
                at = wide.evaluate(reading)
                assert at["caption"][0] >= at["box"][0] - 1, (end, at)
                assert at["caption"][1] <= at["box"][1] + 1, (end, at)
    assert root_overflow(page) == 0


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_scrolling_table_keeps_its_row_names_in_view(browser, serve, direction):
    """A table whose rows open with a `<th scope="row">` keeps that column at its start
    as the other columns scroll sideways, the heading over the names with it, and the
    names paint over the columns passing under them. An overnight dashboard's table
    scrolled its run names away, leaving values no reader could place."""
    cells = "".join(f"<td>measured value {i}</td>" for i in range(8))
    heads = "".join(f"<th>Measure {i}</th>" for i in range(8))
    rows = "".join(
        f'<tr><th scope="row" id="name-{n}">run {n}</th>{cells}</tr>' for n in range(3)
    )
    body = (
        "<h1>Runs</h1>"
        f'<table id="runs"><thead><tr><th id="corner">Run</th>{heads}</tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )
    source = leaf_page("Runs", body).replace(
        '<html lang="en">', f'<html lang="en" dir="{direction}">', 1
    )
    page = open_page(browser, serve(source))
    resized(page, 390, 844)
    table = page.locator("#runs")
    assert table.evaluate("t => t.scrollWidth > t.clientWidth")
    table.evaluate(
        "(t, x) => { t.scrollLeft = x; }", -10_000 if direction == "rtl" else 10_000
    )
    rendered(page)
    at = table.evaluate("""t => {
      const box = t.getBoundingClientRect();
      const start = getComputedStyle(t).direction === 'rtl' ? 'right' : 'left';
      return [...t.querySelectorAll('tr > :first-child')].map(c => {
        const r = c.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return {id: c.id, offset: Math.abs(r[start] - box[start]), on_top: c.contains(hit)};
      });
    }""")
    assert [cell["id"] for cell in at] == ["corner", "name-0", "name-1", "name-2"]
    for cell in at:
        assert cell["offset"] <= 0.5, at
        assert cell["on_top"], at


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_what_an_outer_column_draws_outside_itself_stays_whole(
    browser, serve, direction
):
    """A table clips to its own edges, since it scrolls its columns, so whatever a cell
    in its first or last column draws outside its box keeps its outer side only if the
    cell keeps room for it: a capture's frame, a shadow reaching 8px beside the image,
    alone, linked or in a figure, and the ring on a link the keyboard stands on, in
    either direction. A focused link in the first column lost its ring's outer side."""
    src = SHOT_SRC["before"]
    capture = f'<img src="{src}" width="300" height="150" alt="A capture.">'
    body = (
        "<h1>Captures</h1><p>A paragraph at the measure.</p>"
        f'<table id="captures"><tr><td>{capture}</td>'
        f'<td><a href="{src}">{capture}</a></td>'
        f"<td><figure>{capture}<figcaption>After.</figcaption></figure></td></tr>"
        "</table>"
        '<table id="links"><tr><td><a id="first" href="#a">#3189</a></td>'
        '<td>A note on the change.</td><td><a id="last" href="#b">#3190</a></td></tr>'
        "</table>"
    )
    source = leaf_page("Captures", body).replace(
        '<html lang="en">', f'<html lang="en" dir="{direction}">', 1
    )
    page = open_page(browser, serve(source, media={src: SHOTS["before"]}))
    at = page.locator("#captures").evaluate("""t => {
      const box = t.getBoundingClientRect();
      return {table: [box.left, box.right], scrolls: t.scrollWidth > t.clientWidth,
        images: [...t.querySelectorAll('img')].map(i => {
          const r = i.getBoundingClientRect();
          return [r.left, r.right];
        })};
    }""")
    assert not at["scrolls"], at
    left = min(image[0] for image in at["images"])
    right = max(image[1] for image in at["images"])
    assert left - at["table"][0] >= 8 - 0.5, at
    assert at["table"][1] - right >= 8 - 0.5, at

    page.keyboard.press("Tab")  # keyboard modality, so focus draws its ring
    for link in ("#first", "#last"):
        page.locator(link).focus()
        rendered(page)
        ring = current_location_ring(page)
        assert ring, f"the link {link} the keyboard stands on wears no ring"
        assert ring["cuts"] == [], (link, ring["cuts"])


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_tables_rows_span_the_prose_and_its_outer_words_stand_in_alike(
    browser, serve, direction
):
    """A table as wide as the column runs its row lines from where the prose starts to
    where it ends, and sets its first column's words, a short heading's included, as far
    inside the start as its last column's stop inside the end, in either direction. A
    right-to-left table kept the left-to-right gutter on its first column's right and set
    its words from the left."""
    words = "Each column holds enough words to fill its share of the measure. "
    body = (
        f"<h1>Columns</h1><p id='prose'>{words * 4}</p>"
        '<table id="columns"><thead><tr><th scope="col">Name</th>'
        '<th scope="col">Note</th><th scope="col">More</th></tr></thead>'
        f"<tbody><tr><td>{words}</td><td>{words}</td><td>{words}</td></tr></tbody>"
        "</table>"
    )
    source = leaf_page("Columns", body).replace(
        '<html lang="en">', f'<html lang="en" dir="{direction}">', 1
    )
    page = open_page(browser, serve(source))
    at = page.evaluate("""() => {
      const rtl = getComputedStyle(document.getElementById('columns')).direction === 'rtl';
      const sign = rtl ? -1 : 1;
      const prose = document.getElementById('prose').getBoundingClientRect();
      const [from, to] = rtl ? [prose.right, prose.left] : [prose.left, prose.right];
      const ink = node => {
        const range = document.createRange();
        range.selectNodeContents(node);
        const r = range.getBoundingClientRect();
        return rtl ? r.right : r.left;
      };
      const content = cell => {
        const r = cell.getBoundingClientRect(), cs = getComputedStyle(cell);
        return rtl ? r.left + parseFloat(cs.paddingLeft) : r.right - parseFloat(cs.paddingRight);
      };
      return [...document.querySelectorAll('#columns tr')].map(row => {
        const first = row.firstElementChild.getBoundingClientRect();
        const last = row.lastElementChild.getBoundingClientRect();
        return {
          line: rtl ? [first.right - from, last.left - to] : [first.left - from, last.right - to],
          inset: [sign * (ink(row.firstElementChild) - from), sign * (to - content(row.lastElementChild))],
        };
      });
    }""")
    for row in at:
        assert row["line"] == [pytest.approx(0, abs=0.5)] * 2, at
        start, end = row["inset"]
        assert start > 0.5, at
        assert start == pytest.approx(end, abs=0.5), at


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_row_of_metrics_sets_every_figure_on_one_line(request, serve, engine):
    """A row of metric tiles reads as figures compared across it, so each figure stands
    on one line whichever labels wrap and whichever figures carry a change beside them.
    A label wrapping to a second line had set its own figure a line lower."""
    tile = '<dl id="{}" class="metric"><dt>{}</dt><dd><strong>{}</strong>{}</dd></dl>'
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "metrics",
                '<h1>This week</h1><div class="layout-tiles">'
                + tile.format("short", "checks", "12", " <small>change: +3</small>")
                + tile.format(
                    "long",
                    "open failures across every regional cluster since the last release",
                    "2",
                    "",
                )
                + tile.format("plain", "duration", "4 min", "")
                + "</div>",
            )
        ),
    )
    resized(page, 1440, 900)
    figures = page.evaluate(
        """() => ['short', 'long', 'plain'].map((id) => {
          const tile = document.getElementById(id);
          const label = document.createRange();
          label.selectNodeContents(tile.querySelector('dt'));
          return {
            lines: new Set([...label.getClientRects()].map((r) => Math.round(r.top))).size,
            figure: Math.round(tile.querySelector('strong').getBoundingClientRect().top),
          };
        })"""
    )
    assert figures[1]["lines"] > figures[0]["lines"], f"no label wraps: {figures}"
    assert len({f["figure"] for f in figures}) == 1, figures


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_a_table_of_prose_wraps_inside_its_box_in_every_engine(request, serve, engine):
    """A table whose cells hold sentences wraps them inside the box it stands in, and
    scrolls nothing: in an obligation, in a panel, and in a figure granted the page's room.
    Firefox and WebKit have no scroll-state container and dropped the table's
    `container-type: inline-size scroll-state` whole, so the width its caption reads
    (100cqi) was the window's: an obligation's two-column table laid its rows out 1728px wide
    in a 720px column and cut its second column off."""
    sentence = (
        "When a new copy is installed, the update copies each commit and records it. "
    )
    row = f"<tr><td>{sentence * 2}</td><td>{sentence}</td></tr>"
    table = f'<table id="{{id}}"><caption>{sentence * 3}</caption>'
    table += "<thead><tr><th>Decides</th><th>Can do</th></tr></thead>"
    table += f"<tbody>{row * 2}</tbody></table>"
    body = (
        "<h1>Tables of prose</h1>"
        '<lf-ask id="asked"><h2>Which copy should a session read?</h2>'
        + table.format(id="in-ask")
        + '<lf-options id="asked-choice" choose>'
        '<lf-option id="asked-reload"><strong>Reload</strong> Ask for a reload.</lf-option>'
        '<lf-option id="asked-leave"><strong>Leave</strong> Keep the old copy.</lf-option>'
        "</lf-options></lf-ask>"
        '<section class="panel" id="panel"><h2>Framed</h2>'
        + table.format(id="in-panel")
        + "</section>"
        '<figure data-width="available">' + table.format(id="in-figure") + "</figure>"
    )
    page = open_page(request.getfixturevalue(engine), serve(leaf_page("Prose", body)))
    resized(page, 1440, 900)
    at = page.evaluate("""() => Object.fromEntries(['in-ask', 'in-panel', 'in-figure']
      .map(id => { const t = document.getElementById(id), box = t.getBoundingClientRect();
        const end = t.querySelector('tbody tr').getBoundingClientRect().right;
        return [id, {scrolls: t.scrollWidth - t.clientWidth,
                     past: Math.round(end - box.right)}]; }))""")
    for held in at.values():
        assert held["scrolls"] <= 1 and held["past"] <= 1, at
    assert root_overflow(page) == 0


INDENTED_CELLS = "".join(f"<td>measured value {i}</td>" for i in range(8))


def _indented(name):
    """The breakouts one indented holder holds, each id prefixed with the holder's."""
    return (
        f'<div id="{name}-wide" data-width="wide">Wide.</div>'
        f'<div id="{name}-available" data-width="available">Available.</div>'
        f'<table id="{name}-table" data-width="available"><tr>{INDENTED_CELLS}</tr>'
        "</table>"
        f'<table id="{name}-narrow" data-width="available"><tr><th>Plan</th>'
        "<td>60</td></tr></table>"
    )


INDENTED_PAGE = leaf_page(
    "Indented holders",
    '<h1>Holders</h1><p id="prose">A paragraph at the measure, long enough to fill '
    "the column it stands in from one edge to the other.</p>"
    + _indented("control")
    + f'<ul><li>One<ol><li>Two<ul><li id="nested">Three{_indented("nested")}</li></ul>'
    "</li></ol></li></ul>"
    + f'<ol class="steps"><li id="steps">A step{_indented("steps")}</li></ol>'
    + f'<ul class="plain"><li id="plain">An item{_indented("plain")}</li></ul>'
    + f'<div class="inset" id="inset">An indented block{_indented("inset")}</div>'
    # Boxes the page arranges itself: breakouts that are items in the second track of
    # its own grid, one that shares a flex row, and a table in an inline block.
    + '<div class="pair" id="gridded"><i class="gutter"></i>'
    '<p id="gridded-track">The second track.</p>'
    '<div id="gridded-wide" data-width="wide">Wide.</div>'
    '<div id="gridded-available" data-width="available">Available.</div></div>'
    '<div class="row"><p id="flexed-beside">Beside the block, in the same row.</p>'
    '<div id="flexed-wide" data-width="wide">Wide.</div></div>'
    '<div class="boxed" id="boxed"><p>An inline block holding a table.</p>'
    f'<table id="boxed-table" data-width="available"><tr>{INDENTED_CELLS}</tr></table>'
    "</div>"
    # A block the browser sets in an anonymous block of the column's flow: one wrapped
    # in a link and one in a span, as a chart a page links from is.
    '<a href="#prose"><div id="linked-wide" data-width="wide">Linked.</div></a>'
    '<span><div id="spanned-wide" data-width="wide">Spanned.</div></span>'
    # A block in the second of a holder's columns, beside the first's text.
    '<div class="cols" id="cols"><p>A paragraph long enough to fill the first column '
    "of two from its top to its foot, then carry on into the second, beside the block "
    "that stands there.</p>"
    '<div id="cols-wide" data-width="wide">In the second column.</div></div>',
    head="<style>ul.plain { padding: 0; list-style: none; }"
    " .inset { padding-left: 40px; }"
    " .pair { display: grid; grid-template-columns: 1fr 1fr; column-gap: 16px; }"
    " .pair > .gutter { grid-row: span 3; }"
    " .row { display: flex; gap: 16px; } .row > * { flex: 1; }"
    " .boxed { display: inline-block; }"
    " .cols { columns: 2; column-gap: 16px; }</style>",
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_breakout_grows_only_from_a_holder_that_spans_the_column(
    request, serve, direction, engine
):
    """An explicit flow shares document tracks; ordinary holders contain their exhibits."""
    browser = request.getfixturevalue(engine)
    source = leaf_page(
        "Native exhibit tracks",
        '<h1>Evidence</h1><p id="prose">Reading measure.</p>'
        '<section class="layout-flow"><div id="wide" data-width="wide">Wide</div>'
        '<div id="available" data-width="available">Available</div></section>'
        '<div id="holder" style="margin-inline-start:40px"><div id="nested" data-width="available">Contained</div></div>'
        '<div id="grid" style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
        '<p>Sibling</p><div id="cell" data-width="wide">In its track</div></div>',
        head=f"<style>main {{direction:{direction}}}</style>",
    )
    page = open_page(browser, serve(source))
    for width in (1440, 390):
        resized(page, width, 900)
        at = page.evaluate(
            """() => Object.fromEntries(['prose','wide','available','holder','nested','grid','cell'].map(id => [id,document.getElementById(id).getBoundingClientRect().toJSON()]))"""
        )
        assert at["available"]["width"] == pytest.approx(width - 48, abs=1)
        assert at["wide"]["width"] >= at["prose"]["width"]
        assert at["nested"]["left"] == pytest.approx(at["holder"]["left"], abs=1)
        assert at["nested"]["right"] == pytest.approx(at["holder"]["right"], abs=1)
        assert at["cell"]["width"] == pytest.approx(
            (at["grid"]["width"] - 16) / 2, abs=1
        )
        assert root_overflow(page) == 0


def test_a_breakout_a_revision_inserts_deeper_lands_before_it_paints(browser, serve):
    """A revision's replacement can put a breakout in a list deeper than the one it
    replaced. The breakout keeps to its list item from the first paint that shows it,
    without waiting for a frame's margin pass or the next resize: it is read in the
    microtask its insertion queues, before the rendering update that lays it out
    paints. Unread, it would grow out of the column as one in the page's flow does."""
    page = open_page(browser, serve(INDENTED_PAGE))
    resized(page, 1440, 900)
    margins_laid_out(page)
    before = page.evaluate(
        "() => document.getElementById('nested-narrow').getBoundingClientRect().left"
    )
    with held_frames(page):
        at = page.evaluate("""async () => {
          const edges = (id) => {
            const box = document.getElementById(id).getBoundingClientRect();
            return {left: box.left, right: box.right};
          };
          // The next rendering update, read in a ResizeObserver made after the
          // runtime's: after its frame callbacks, layout and the runtime's own
          // observers, and before it paints.
          const update = () => new Promise((resolve) => {
            const sentinel = document.createElement('div');
            sentinel.style.cssText = 'position: fixed; width: 1px; height: 1px';
            document.body.append(sentinel);
            const observer = new ResizeObserver(() => {
              observer.disconnect();
              sentinel.remove();
              resolve();
            });
            observer.observe(sentinel);
          });
          // Frame callbacks are held, so after one update and a task none the runtime
          // asked for before the change is left to run in the update that lays the
          // change out.
          await update();
          await new Promise((resolve) => setTimeout(resolve));
          // As a revision replaces a passage: the list holding the holder, anew, with
          // one more list inside.
          const list = document.getElementById('nested').closest('main > ul');
          const copy = list.cloneNode(true);
          copy.querySelector('#nested').insertAdjacentHTML('beforeend',
            '<ul><li id="late">Four'
            + '<div id="late-wide" data-lf-space="wide">Wide.</div>'
            + '<table id="late-narrow" data-lf-space="available"><tr><th>Plan</th>'
            + '<td>60</td></tr></table></li></ul>');
          list.replaceWith(copy);
          await update();
          const item = document.getElementById('late');
          const box = item.getBoundingClientRect(), style = getComputedStyle(item);
          return {
            moved: edges('late-narrow'),
            wide: edges('late-wide'),
            holder: {left: box.left + parseFloat(style.paddingLeft),
                     right: box.right - parseFloat(style.paddingRight)},
          };
        }""")
    assert at["moved"]["left"] > before + 20, ("the list was not deeper", at)
    for edge in ("left", "right"):
        assert at["wide"][edge] == pytest.approx(at["holder"][edge], abs=1), at


def test_a_sample_fills_the_room_its_authored_width_takes(browser, serve):
    """The breakout rule widens a block by negative margins, which an auto-width box
    fills and a box with a width of its own does not. A sample is a table box with a
    stated width, so `data-width="available"` moved it left by the margin and left it
    at the column's width. Each wide sample is measured against a plain block given the
    same width, which is where the room ends. A sample with no width of its own is the
    control for the inherited surplus: in a list item inside a wide section it takes the
    item's width, not the item's width plus the section's surplus."""
    source = leaf_page(
        "Sample widths",
        """
<h1 id="title">Sample widths</h1>
<p id="prose">Standard prose.</p>
<div id="block-wide" data-width="wide">A wide block.</div>
<lf-sample id="sample-wide" data-width="wide"><p>A wide sample.</p></lf-sample>
<div id="block-available" data-width="available">An available block.</div>
<lf-sample id="sample-available" data-width="available"><p>An available sample.</p></lf-sample>
<lf-sample id="sample-plain"><p>A plain sample.</p></lf-sample>
<section data-width="wide"><ul><li id="item">
  <p>A list item inside wide evidence.</p>
  <lf-sample id="sample-nested"><p>A sample in that item.</p></lf-sample>
</li></ul></section>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    at = page.evaluate("""() => Object.fromEntries(
      [...document.querySelectorAll('main [id]')].map(el => {
        const box = el.getBoundingClientRect();
        return [el.id, {left: box.left, right: box.right, width: box.width}];
      }))""")
    assert (
        at["block-available"]["width"]
        > at["block-wide"]["width"]
        > (at["prose"]["width"] + 100)
    ), at
    for width in ("wide", "available"):
        sample, block = at[f"sample-{width}"], at[f"block-{width}"]
        for edge in ("left", "right"):
            assert sample[edge] == pytest.approx(block[edge], abs=1), (
                f'a data-width="{width}" sample\'s {edge} edge is at '
                f"{sample[edge]:.0f}px, the room's at {block[edge]:.0f}px"
            )
    assert at["sample-plain"]["width"] == pytest.approx(at["prose"]["width"], abs=1), at
    assert at["sample-nested"]["width"] == pytest.approx(at["item"]["width"], abs=1), at
    assert root_overflow(page) == 0


def test_paper_keeps_the_column(browser, serve):
    """Paper has no window to take room from: a printed page is the column's width,
    whatever the screen it was sent from was showing. The rule that grants the room is
    therefore screen-only, and leaving it out of print is the whole of what paper needs —
    the same bargain paper already has with every affordance a copy keeps.

    Asked here rather than left to the print gate beside it, which reads what a medium
    drops rather than how wide it sets what it keeps: a board printed at a screen's width
    loses its right-hand columns off the edge of the sheet, and every word of it is still
    in the document for that gate to find."""
    page = open_page(browser, serve(WIDE_AND_NARROW_PAGE))
    on_screen = page.evaluate(
        "() => document.getElementById('sprint').getBoundingClientRect().width"
    )
    column = page.evaluate("""() => {
        const m = document.querySelector('main'), s = getComputedStyle(m);
        const b = m.getBoundingClientRect();
        return b.width - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
    }""")
    assert on_screen > column + 1, (
        "the board must be wider than the column on screen, or print proves nothing"
    )

    page.emulate_media(media="print")
    printed = page.evaluate(
        "() => document.getElementById('sprint').getBoundingClientRect().width"
    )
    assert abs(printed - column) <= 1, (
        f"paper set the board to {printed:.0f}px, past a {column:.0f}px column: a sheet "
        "has no window to take the room from, so what runs past it is off the page"
    )


def test_paper_holds_no_room_for_the_chrome_it_does_not_print(browser, serve):
    """The panel stands over the foot of the document, so the document leaves it room.
    The panel is not on a sheet — the runtime's whole layer is withheld from print — and
    chrome's room went to paper anyway once: written as body's own padding it printed as
    a blank strip under the last line.

    The reservations now belong to the document box whose chrome they make room for,
    rather than to the scroll container. The same CSS disappears with the chrome in
    print, so paper cannot inherit an empty screen-only strip.

    The screen half is read as room rather than as a covered last line, which is where a
    user would meet it, because the column's own bottom padding is taller than the line:
    nothing is covered either way today, so an assertion about the last block would pass
    with the reservation deleted. The room is what the runtime answers for; the column's
    padding is the theme's to change."""
    page = open_page(browser, serve(LONG_PAGE))
    for width in (1440, 390):
        resized(page, width, 844)
        room = page.evaluate(CHROME_ROOM)
        assert room["panel"] > 0, f"no panel is shown to reserve for: {room}"
        assert room["head"] <= 1, f"the document starts {room['head']:.0f}px down"
        assert room["foot"] >= room["panel"] - 1, (
            f"at {width}px the document ends {room['foot']:.0f}px short of its own "
            f"end, under a {room['panel']:.0f}px panel"
        )

    page.emulate_media(media="print")
    printed = page.evaluate(CHROME_ROOM)
    assert printed["head"] <= 1 and printed["foot"] <= 1, (
        f"a sheet held {printed['head']:.0f}px over the first line and "
        f"{printed['foot']:.0f}px under the last, for chrome it does not print"
    )


def test_a_wide_widget_keeps_its_margins_and_its_comment_lands_on_it(browser, serve):
    """The rail claims nothing: its markers hang 22px off the column wherever the room
    beside it holds them, and a wide widget grows into that same room, so a widget grown
    toward the right margin reaches the rail's markers.

    Nothing Leaf draws moves the page's content, so a comment arriving on a board cannot
    narrow it: both boards grow both ways at every width. The change inside the near
    board belongs to the board, which reaches past the rail's inner edge, so its row
    stands on the board as a pin at the top-right of the change it decides, where it
    lands on what it is about. The change above the board keeps the rail. Either way
    the controls stay pressable: they stand over the page, not under it.

    A range of windows rather than one, because what stops the boards' growth changes
    with the window: the free room beside the column just past where the rail first
    stands, the wide measure beyond it. A single viewport reads only one of the two."""
    url = serve(RAIL_BAND_PAGE)
    page = open_page(browser, url)

    for width in (1000, 1200, 1400, 1600):
        resized(page, width, 900)
        margins_laid_out(page)
        at = page.evaluate(RAIL_BANDS)
        places = {r["for"]: r["place"] for r in at["rows"]}
        assert places == {"sug-copy": "rail", "sug-card": "pin"}, (width, at)
        for r in at["rows"]:
            assert r["pressable"], f"at {width}px a row is covered: {r}"
        card = next(r for r in at["rows"] if r["for"] == "sug-card")
        plan = at["plan"]
        assert plan["left"] < card["left"] and card["right"] <= plan["right"] + 1, (
            f"at {width}px the change's pin stands off its board: {at}"
        )
        for name in ("plan", "later"):
            b = at[name]
            assert b["left"] < at["column"]["left"] - 1, (width, name, at)
            assert b["right"] > at["column"]["right"] + 1, (
                f"at {width}px the {name} board is held to the column's right edge, so "
                f"a row in the margin took room from the page's content: {at}"
            )
            assert b["right"] <= at["pageRight"] + 1, (
                f"at {width}px the {name} board is past the page's box as well"
            )
        assert root_overflow(page) == 0, f"at {width}px the page scrolls sideways"


def test_a_drawing_the_room_can_hold_is_shown_whole(browser, serve):
    """Scrolling is the theme's honest degrade when even the room runs short, and only
    then: a drawing wider than the column and narrower than the room beside it, with
    nothing standing in the margin at its band, is shown whole. The guard pins the
    premise: the graph is wider than the column and narrower than the room."""
    url = serve(DRAWN_PAST_A_RAIL_PAGE)
    page = open_page(browser, url)
    # The shell owns --lf-room in CSS, so its computed value is the unresolved
    # expression and only a probe answers in the width a wide exhibit would receive.
    fit = page.evaluate("""() => {
        const el = document.getElementById('flow');
        const m = document.querySelector('main');
        const s = getComputedStyle(m), b = m.getBoundingClientRect();
        const probe = document.createElement('i');
        probe.style.cssText = 'position:fixed;visibility:hidden;height:0;padding:0;'
          + 'border:0;width:var(--lf-room)';
        el.append(probe);
        const room = probe.getBoundingClientRect().width;
        probe.remove();
        return { shows: el.clientWidth, drawn: el.scrollWidth, room,
                 column: b.width - parseFloat(s.paddingLeft)
                         - parseFloat(s.paddingRight) };
    }""")
    assert fit["column"] < fit["drawn"] <= fit["room"], (
        f"the premise is gone — the graph must need growing and fit the room, or "
        f"this test asks nothing: drawn {fit['drawn']:.0f}px, "
        f"column {fit['column']:.0f}px, room {fit['room']:.0f}px"
    )
    assert fit["shows"] >= fit["drawn"] - 1, (
        f"the page had {fit['room']:.0f}px of room and no note or row beside the "
        f"drawing, and still shows {fit['shows']:.0f}px of its {fit['drawn']:.0f}px"
    )


def test_a_box_that_shows_less_than_it_holds_says_so(browser, serve):
    """A drawing that genuinely could not fit scrolls, and on a platform drawing overlay
    scrollbars the scrollbar is no sign at rest: measured, a twelve-node flowchart in a
    tab panel showed seven of them at 1200, 1440 and 1920 with nothing saying so. So the
    box marks each edge with content beyond it, which fades the drawing there. The line
    of code that fits is the control: a mark on a box holding nothing back would be a
    promise of more with nothing behind it."""
    url = serve(CUT_BOXES_PAGE)
    page = open_page(browser, url)
    resized(page, 900, 900)
    marks = page.evaluate("""() => {
        const read = (id) => {
            const el = document.getElementById(id);
            return { short: el.scrollWidth - el.clientWidth,
                     before: el.hasAttribute('data-lf-more-before'),
                     after: el.hasAttribute('data-lf-more-after'),
                     paints: getComputedStyle(el).maskImage !== 'none' };
        };
        return { flow: read('flow'), fits: read('short') };
    }""")
    assert marks["flow"]["short"] > 1, (
        f"the graph fits its box here, so nothing is being cut: {marks}"
    )
    assert not marks["flow"]["before"] and marks["flow"]["after"], marks
    assert marks["flow"]["paints"], marks
    assert marks["fits"]["short"] == 0, (
        f"the control box scrolls too, so it controls nothing: {marks}"
    )
    assert not marks["fits"]["before"] and not marks["fits"]["after"], marks
    assert not marks["fits"]["paints"], marks

    flow = page.locator("#flow")
    flow.evaluate("el => { el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2; }")
    expect(flow).to_have_attribute("data-lf-more-before", "")
    expect(flow).to_have_attribute("data-lf-more-after", "")
    flow.evaluate("el => { el.scrollLeft = el.scrollWidth; }")
    expect(flow).to_have_attribute("data-lf-more-before", "")
    expect(flow).not_to_have_attribute("data-lf-more-after", "")

    page.evaluate("""() => {
        document.documentElement.style.direction = 'rtl';
        document.dispatchEvent(new Event('lf-layout'));
    }""")
    expect(flow).not_to_have_attribute("data-lf-more-before", "")
    expect(flow).to_have_attribute("data-lf-more-after", "")
    flow.evaluate("el => { el.scrollLeft = -(el.scrollWidth - el.clientWidth); }")
    expect(flow).to_have_attribute("data-lf-more-before", "")
    expect(flow).not_to_have_attribute("data-lf-more-after", "")


def test_a_scroller_that_stops_scrolling_drops_its_continuation(browser, serve):
    source = leaf_page(
        "Changing scrollport",
        '<div id="box" class="scroll" style="width:200px;overflow-x:auto;white-space:nowrap">'
        '<span style="display:inline-block;width:600px">Wide content</span></div>',
    )
    page = open_page(browser, serve(source))
    box = page.locator("#box")
    expect(box).to_have_attribute("data-lf-more-after", "")
    page.evaluate("""() => {
      const box = document.querySelector('#box');
      box.style.overflowX = 'hidden';
      box.firstElementChild.style.width = '650px';
    }""")
    rendered(page)
    expect(box).not_to_have_attribute("data-lf-more-after", "")


def test_a_scroller_reclassifies_when_an_ancestor_changes_its_style(browser, serve):
    source = leaf_page(
        "Inherited scrollport",
        '<div id="parent" style="--flow:auto">'
        '<div id="box" class="scroll" '
        'style="width:200px;overflow-x:var(--flow);white-space:nowrap">'
        '<span style="display:inline-block;width:600px">Wide content</span>'
        "</div></div>",
    )
    page = open_page(browser, serve(source))
    box = page.locator("#box")
    expect(box).to_have_attribute("data-lf-scroll-direction", "ltr")
    expect(box).to_have_attribute("data-lf-more-after", "")
    page.evaluate("""() => {
      const parent = document.querySelector('#parent');
      parent.style.direction = 'rtl';
      parent.style.setProperty('--flow', 'hidden');
      document.querySelector('#box').firstElementChild.style.width = '650px';
    }""")
    rendered(page)
    expect(box).not_to_have_attribute("data-lf-scroll-direction", "ltr")
    expect(box).not_to_have_attribute("data-lf-more-after", "")


def test_a_drawing_cut_at_its_edge_fades_toward_the_ground_and_still_reaches_it(
    browser, serve
):
    """Three agent-written pages drew a five-step plan `flowchart LR`; at 1440px each
    box showed two and a half steps, and every reader took the plan for three. The mark
    was the layer's fade, all the way to the ground, and a node faded out looks like the
    node's own end.

    So a drawing's fade stops short of the ground: the node cut at an edge fades toward
    the page's ground and still reaches the scrollport's side, which is what reads as
    cut. This reads the pixels rather than the rule, in a row through the cut node's
    fill above its label: at the very edge the fill is lighter than a little inside the
    box and still darker than the ground. Over blank canvas the edge is the ground
    itself, where a grey shadow used to lie. The fade follows the scroll: the end edge
    at rest, the start edge once a node straddles it. The drawing keeps the size it was
    drawn at throughout, and the same five steps drawn top-down fit the column and fade
    nothing."""
    page = open_page(browser, serve(LONG_CHAIN_PAGE))
    resized(page, 950, 900)
    rendered(page)
    sizes = page.evaluate("""() => Object.fromEntries(['chain', 'stack'].map((id) => {
        const el = document.getElementById(id), svg = el.querySelector('svg');
        return [id, { short: el.scrollWidth - el.clientWidth,
                      drawn: svg.getBoundingClientRect().width,
                      natural: svg.viewBox.baseVal.width,
                      mask: getComputedStyle(el).maskImage }];
    }))""")
    assert sizes["chain"]["short"] > 1, f"the chain fits, so nothing is cut: {sizes}"
    assert sizes["stack"]["short"] == 0, f"the stack scrolls too: {sizes}"
    assert sizes["stack"]["mask"] == "none", sizes
    for box in sizes.values():
        assert abs(box["drawn"] - box["natural"]) < 1, (
            f"a drawing was scaled away from its natural size: {sizes}"
        )

    def edge(side):
        """Luminance at the chain's `side` edge, in a row through the fill of the node
        standing across it, beside the node's fill 60px inside the edge, past the
        fade's reach; and the same two places in the blank band above the nodes."""
        box = page.evaluate(
            """(side) => {
            const el = document.getElementById('chain'), r = el.getBoundingClientRect();
            const x = side === 'end' ? r.right - 1 : r.left + 1;
            const node = [...el.querySelectorAll('g.pele-node')]
                .map((n) => n.getBoundingClientRect())
                .find((n) => n.left < x && n.right > x);
            return node && { x: r.left, y: r.top, width: r.width,
                             height: node.bottom - r.top, row: node.top + 10 - r.top };
            }""",
            side,
        )
        assert box, f"no node stands across the {side} edge, so nothing is cut there"
        clip = {k: box[k] for k in ("x", "y", "width", "height")}
        shot = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("L")
        w, row = shot.size[0], round(box["row"])
        at, inside = (
            ((w - 3, w), (w - 63, w - 57)) if side == "end" else ((0, 3), (57, 63))
        )

        def mean(x, y0, y1):
            return ImageStat.Stat(shot.crop((x[0], y0, x[1], y1))).mean[0]

        return {
            "ground": mean(at, 0, 4),
            "ground_inside": mean(inside, 0, 4),
            "edge": mean(at, row, row + 4),
            "fill": mean(inside, row, row + 4),
        }

    at_rest = edge("end")
    assert abs(at_rest["ground"] - at_rest["ground_inside"]) < 2, (
        f"the blank canvas at the edge is not the page's ground: {at_rest}"
    )
    assert at_rest["fill"] + 3 < at_rest["edge"] < at_rest["ground"] - 3, (
        f"the cut node does not fade toward the ground and still reach the edge: "
        f"{at_rest}"
    )
    chain = page.locator("#chain")
    chain.evaluate("""(el) => {
        const node = el.querySelectorAll('g.pele-node')[1].getBoundingClientRect();
        el.scrollLeft += (node.left + node.right) / 2 - el.getBoundingClientRect().left;
    }""")
    expect(chain).to_have_attribute("data-lf-more-before", "")
    rendered(page)
    scrolled = edge("start")
    assert scrolled["fill"] + 3 < scrolled["edge"] < scrolled["ground"] - 3, scrolled


def test_a_wide_widget_in_a_reply_takes_the_panels_room(browser, serve):
    """The room a wide widget spends is the document's, and a thread's message is the one
    place a widget of the page's vocabulary renders outside the document. The skill offers
    a diagram in a reply as the way to explain a fix in the margin, and a diagram is
    declared wide — so marked as one it would lay itself out to a wide page inside a
    420px panel, and the explanation would be the half of it the panel could show.

    The mark that would do that is the one deliberately left out of the message render
    (x-space, the half of markDeclared the page keeps to itself). Nothing about a message
    says so, which is why this asks: the widget is in the panel, and the panel's width is
    what bounds it."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-fix",
            "author": "user",
            "revision": 1,
            "text": "How does the fallback read?",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "id": "r-fix",
            "author": "agent",
            "parent": "c-fix",
            "revision": 1,
            "text": "Like this:",
            "markup": '<lf-diagram id="fallback-flow"><pre>\n'
            "graph LR\n  R[request] --> C{cookie}\n  C --> S[session]\n</pre></lf-diagram>",
        },
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, "c-fix")
    expect(view.locator("#fallback-flow svg")).to_be_visible()

    fit = page.evaluate("""() => {
        const el = document.querySelector('.lf-floating-panel #fallback-flow');
        const holder = el.closest('.lf-msg-body');
        const a = el.getBoundingClientRect(), b = holder.getBoundingClientRect();
        return { widget: a.width, message: b.width, past: a.right - b.right,
                 marked: el.hasAttribute('data-lf-space') };
    }""")
    assert not fit["marked"], (
        "a widget in a thread was handed the page's room; the panel is not the page"
    )
    assert fit["past"] <= 1, (
        "the diagram stands past the message that holds it by "
        f"{fit['past']:.0f}px — widget {fit['widget']:.0f}px in a "
        f"{fit['message']:.0f}px panel"
    )


def test_a_message_carries_the_marks_a_page_would_except_its_room(browser, serve):
    """A message's markup renders in the panel and never passes through delivery, so the
    runtime paints its marks as it renders them, and paints what delivery would paint on
    the same markup on a page: a quoted sample is an exhibit, a gloss sets among words,
    and an occurrence's own `data-bound` holds its height. The room is the one mark left
    behind, even where an occurrence asks for it with `data-width`: it is the page's to
    give, and the panel's width bounds a message."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-log",
            "author": "user",
            "revision": 1,
            "text": "What did the old copy say?",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "id": "r-log",
            "author": "agent",
            "parent": "c-log",
            "revision": 1,
            "text": "Here it is, with the log:",
            "markup": '<lf-sample id="rp-quoted" label="the old copy">'
            '<p>Sessions <lf-gloss tip="Still under review.">draft</lf-gloss> live in Redis.</p></lf-sample>'
            '<pre id="rp-log" data-bound="end">one\ntwo\nthree</pre>'
            '<section id="rp-room" data-width="wide"><p>Wide on a page.</p></section>'
            '<lf-options id="rp-choice"><lf-option id="rp-keep">Keep</lf-option></lf-options>',
        },
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, "c-log")
    expect(view.locator("#rp-quoted")).to_be_visible()

    marks = page.evaluate("""() => Object.fromEntries(
        [['sample', '#rp-quoted'], ['gloss', '#rp-quoted lf-gloss'], ['log', '#rp-log'],
         ['room', '#rp-room'], ['choice', '#rp-choice']].map(([name, selector]) => {
            const el = document.querySelector('.lf-floating-panel ' + selector);
            return [name, Object.fromEntries(
                ['data-lf-exhibit', 'data-lf-inline', 'data-lf-bound', 'data-lf-space', 'data-lf-awaits']
                    .filter(attr => el.hasAttribute(attr))
                    .map(attr => [attr, el.getAttribute(attr)]))];
        }))""")
    assert marks == {
        "sample": {"data-lf-exhibit": ""},
        "gloss": {"data-lf-inline": ""},
        "log": {"data-lf-bound": "end"},
        "room": {},
        "choice": {"data-lf-awaits": ""},
    }, marks


def test_a_wide_widget_stays_inside_a_box_that_frames_it(browser, serve):
    """The room is the page's to give, and a widget inside a box that paints is not held
    by the page. A quoted board that took the window stood outside the gutter marking it
    as quoted — the exhibit escaping its own exhibit — while a diagram in an option card
    was worse for being invisible: a choose group clips to its own cells, so the widest
    part of the evidence an option argued on was cut off at the card's edge rather than
    drawn past it, and nothing on the page said a word.

    A plain section is the control. It paints nothing and is the column's own width, so a
    board inside one takes the room exactly as it would standing alone — which is what
    says this is about the box and not about being nested.

    Which boxes those are is read off `--lf-block-frame`, the word a box already says where it
    draws its frame, so the metric here is held by declaring one and the page's own div by
    declaring the same one. A list of tags stood in for that reading and shadowed it: the
    metric declared the frame and was not in the list, and no list a layer writes can
    reach the div at all.

    The nested section and the note are the two a list of tags could not have named
    even in principle. A section's rail is drawn by `.nested-frame > .nested-frame`,
    so it frames what it holds only where it is nested, and a note's box is drawn by `lf-code > pre > lf-note`,
    a rule on where the code block's module docks it rather than on the tag. Each let a diagram out ~245px over the
    column until the rule that draws it declared the frame.

    The row form is the declaration's limit, and the reason the sizing is asserted
    too. A row option is a table hugging its words, and legacy table sizing answers
    to content where every modern layout clamps a scroll container — so with the
    frame declared all along, a diagram in a row grew the row, the row grew the
    shared track, and the group's clip cut the evidence off at its border. And a
    separated table adds its padding outside the width it is given, so every row on
    every joined group stood 30px past its group, diagram or no diagram, the clip
    spending the overhang out of the pick's word-room. The box a wide widget gets
    answers to the room and never to its content (contain: inline-size, theme.css),
    and the row keeps its reservation inside the width it states (box-sizing:
    border-box, packages/default/theme.css)."""
    source = FRAMED_WIDE_PAGE
    page = open_page(browser, serve(source))
    # Wide enough that the sidebar, the column and the rail leave the loose board room.
    resized(page, 1280, 900)
    boxes = page.evaluate("""() => {
        const box = (sel) => {
            const r = document.querySelector(sel).getBoundingClientRect();
            return { left: r.left, right: r.right, width: r.width };
        };
        const main = document.querySelector('main');
        const s = getComputedStyle(main), b = main.getBoundingClientRect();
        return { column: document.querySelector("main h1").getBoundingClientRect().width,
                 loose: box('#in-section'), sample: box('#quoted'),
                 quoted: box('#in-sample'), card: box('#opt-a'),
                 diagram: box('#in-card'),
                 boardCard: box('#ek1'), inBoardCard: box('#in-board-card'),
                 metric: box('#me1'), inMetric: box('#in-metric'),
                 task: box('#t-inner'), inTask: box('#in-task'),
                 note: box('lf-code pre > lf-note'), inNote: box('#in-note'),
                 rowGroup: box('#row-pick'), rowCell: box('#row-a'),
                 inRow: box('#in-row'), rowPick: box('#row-a .lf-pick'),
                 ownBox: box('#own-box'), inOwnBox: box('#in-own-box') };
    }""")

    assert boxes["loose"]["width"] > boxes["column"] + 1, (
        "a transparent wrapper must not cost the exhibit its room: board "
        f"{boxes['loose']['width']:.0f}px in a {boxes['column']:.0f}px column"
    )
    assert boxes["quoted"]["left"] >= boxes["sample"]["left"] - 1, (
        "the quoted board escaped its frame on the left"
    )
    assert boxes["quoted"]["right"] <= boxes["sample"]["right"] + 1, (
        "the quoted board escaped its frame on the right: board out to "
        f"{boxes['quoted']['right']:.0f}, frame ends at {boxes['sample']['right']:.0f}"
    )
    assert boxes["diagram"]["left"] >= boxes["card"]["left"] - 1, (
        "the diagram crossed the card's left edge, where the group's clip cuts it off"
    )
    assert boxes["diagram"]["right"] <= boxes["card"]["right"] + 1, (
        "the diagram crossed the card's right edge, where the group's clip cuts it off: "
        f"diagram out to {boxes['diagram']['right']:.0f}, card ends at "
        f"{boxes['card']['right']:.0f}"
    )
    assert boxes["rowCell"]["right"] <= boxes["rowGroup"]["right"] + 1, (
        "the row grew past the group that clips it: row out to "
        f"{boxes['rowCell']['right']:.0f}, group ends at {boxes['rowGroup']['right']:.0f}"
    )
    assert boxes["inRow"]["left"] >= boxes["rowCell"]["left"] - 1, (
        "the diagram crossed the row's left edge"
    )
    assert boxes["inRow"]["right"] <= boxes["rowCell"]["right"] + 1, (
        "the diagram crossed the row's right edge, where the group's clip cuts it off: "
        f"diagram out to {boxes['inRow']['right']:.0f}, row ends at "
        f"{boxes['rowCell']['right']:.0f}"
    )
    assert boxes["rowPick"]["right"] <= boxes["rowGroup"]["right"] + 1, (
        "the pick's word-room runs past the group and the clip spends it: pick out to "
        f"{boxes['rowPick']['right']:.0f}, group ends at {boxes['rowGroup']['right']:.0f}"
    )
    # A board's own card is the same box asked from inside a scroller, which is where the
    # gate below had been blind: this diagram stood 332px past its card and across the
    # next column of the board, and every reading of the page called it clean.
    assert boxes["inBoardCard"]["left"] >= boxes["boardCard"]["left"] - 1, (
        "the diagram crossed its card's left edge on the board"
    )
    assert boxes["inBoardCard"]["right"] <= boxes["boardCard"]["right"] + 1, (
        "the diagram crossed its card's right edge and is drawn over the next column: "
        f"diagram out to {boxes['inBoardCard']['right']:.0f}, card ends at "
        f"{boxes['boardCard']['right']:.0f}"
    )
    assert boxes["inMetric"]["left"] >= boxes["metric"]["left"] - 1, (
        "the diagram crossed the metric's left edge"
    )
    assert boxes["inMetric"]["right"] <= boxes["metric"]["right"] + 1, (
        "the diagram crossed the metric's right edge and is drawn over the metric "
        f"beside it: diagram out to {boxes['inMetric']['right']:.0f}, metric ends at "
        f"{boxes['metric']['right']:.0f}"
    )
    assert boxes["inTask"]["left"] >= boxes["task"]["left"] - 1, (
        "the diagram crossed the left edge of the task that holds it"
    )
    assert boxes["inTask"]["right"] <= boxes["task"]["right"] + 1, (
        "the diagram crossed the right edge of the task that holds it and is drawn past "
        "the rail marking it as nested: diagram out to "
        f"{boxes['inTask']['right']:.0f}, task ends at {boxes['task']['right']:.0f}"
    )
    assert boxes["inNote"]["left"] >= boxes["note"]["left"] - 1, (
        "the diagram crossed the left edge of the note that holds it"
    )
    assert boxes["inNote"]["right"] <= boxes["note"]["right"] + 1, (
        "the diagram crossed the right edge of the note that holds it and is drawn over "
        "the code block it annotates: diagram out to "
        f"{boxes['inNote']['right']:.0f}, note ends at {boxes['note']['right']:.0f}"
    )
    assert boxes["inOwnBox"]["left"] >= boxes["ownBox"]["left"] - 1, (
        "the diagram crossed the left edge of the box the page drew for it"
    )
    assert boxes["inOwnBox"]["right"] <= boxes["ownBox"]["right"] + 1, (
        "the diagram crossed the right edge of the box the page drew for it, so a "
        "project declaring the frame does not get the room held in: diagram out to "
        f"{boxes['inOwnBox']['right']:.0f}, box ends at {boxes['ownBox']['right']:.0f}"
    )


def test_a_wide_widget_leaves_the_sidenote_its_margin(browser, serve):
    """The page has two claims on its right margin now: a note is read out there, and a
    wide widget expands into it. A widget drawn over a note is the note lost — it is the
    thing on top — and the user loses words the page states, which is the same fault
    the clipped-float reading refuses a version for.

    The claim is settled at the height it arises and nowhere else, which is what the two
    boards are for. One stands level with the note and drops below it to take the margin;
    the other is 600px further down with nothing out there, and takes the margin where it
    stands. Asserting only the first would pass just as well for a page that refused every
    exhibit the margin because a note existed somewhere above it — the reading that held a
    diagram to the column's own width with the margin beside it empty."""
    page = open_page(browser, serve(NOTE_AND_WIDE_PAGE))
    resized(page, NOTE_BAND, 900)
    wide = page.evaluate(ROOM_GEOMETRY)

    assert wide["note"]["width"] > 0, (
        "the page lost the note entirely, so this proves nothing about the margin"
    )
    note = wide["note"]
    assert wide["later"]["width"] > wide["column"]["width"] + 1, (
        f"the page never grows the unobstructed board past prose, so neither "
        f"exhibit asks to share the note's margin: {wide}"
    )
    for name in ("board", "later"):
        exhibit = wide[name]
        across = exhibit["left"] < note["right"] and exhibit["right"] > note["left"]
        down = exhibit["top"] < note["bottom"] and exhibit["bottom"] > note["top"]
        assert not (across and down), (
            f"the page stands the {name} board over the note it shares the margin "
            f"with: board {exhibit['left']:.0f}–{exhibit['right']:.0f}px across and "
            f"{exhibit['top']:.0f}–{exhibit['bottom']:.0f}px down, note "
            f"{note['left']:.0f}–{note['right']:.0f}px and "
            f"{note['top']:.0f}–{note['bottom']:.0f}px"
        )
    assert wide["later"]["right"] > wide["column"]["right"] + 1, (
        f"the page held a board with no note anywhere near it to the column's own "
        f"right edge: board to {wide['later']['right']:.0f}px, column to "
        f"{wide['column']['right']:.0f}px. A note claims the margin at its own height, "
        f"not down the whole page."
    )
    assert root_overflow(page) == 0, (
        "the page scrolls sideways, so the room it took was not the room it had"
    )
    assert wide["board"]["width"] >= wide["column"]["width"] - 1, (
        f"the page shrank the board inside the measure its own prose is set to: "
        f"board {wide['board']['width']:.0f}px, column {wide['column']['width']:.0f}px"
    )


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_note_hangs_in_the_margin_where_the_room_holds_it(browser, serve, direction):
    """Notes wrap after their passage without shifting centered prose."""
    source = NOTE_AND_WIDE_PAGE.replace("<html", f'<html dir="{direction}"', 1)
    page = open_page(browser, serve(source))
    for width, beside in ((1100, False), (1190, False), (1600, True)):
        resized(page, width, 900)
        at = page.evaluate(ROOM_GEOMETRY)
        axis = at["pageBox"]["left"] + at["pageBox"]["width"] / 2
        assert at["column"]["centre"] == pytest.approx(axis, abs=1)
        note, prose = at["note"], at["prose"]
        assert note["width"] > 0
        assert (note["top"] < prose["bottom"]) == beside
        if beside:
            if direction == "ltr":
                assert note["left"] >= prose["right"] + 23
            else:
                assert note["right"] <= prose["left"] - 23
        assert root_overflow(page) == 0


def test_a_note_the_page_does_not_show_takes_no_room(browser, serve):
    source = leaf_page(
        "a note in a disclosure",
        '<h1>Migration plan</h1><details id="more"><summary>Why twice a month</summary>'
        '<div class="layout-note"><p>The cadence follows the support rota.</p>'
        '<aside class="note" id="frequency">Support runs this twice a month.</aside></div>'
        '</details><p id="after">Shift one cohort at a time.</p>',
    ).replace(
        '<main class="layout-column">', '<main class="layout-column layout-notes">'
    )
    page = open_page(browser, serve(source))
    before = page.locator("#after").bounding_box()
    page.locator("#more > summary").click()
    expect(page.locator("#frequency")).to_be_visible()
    assert page.locator("#after").bounding_box()["y"] > before["y"]
    page.locator("#more > summary").click()
    expect(page.locator("#frequency")).not_to_be_visible()
    assert page.locator("#after").bounding_box() == before


def test_a_sidebar_pages_track_is_its_aside_in_the_order_it_is_written(browser, serve):
    """A sidebar page's track is its `aside`, wherever it is written. One written before
    the body stands on the left and, stacked on a phone, comes first; one written after
    it stands on the right and comes last. Source order is the reading order at every
    width, so a summary a reader needs first never lands below the whole body."""
    body = "<div id='body'>" + "<p>Body paragraph. " * 40 + "</p></div>"
    track = "<aside id='track'><div class='layout-track'><p>Summary and contents.</p></div></aside>"
    for first in (True, False):
        source = leaf_page(
            "a sidebar page",
            "<header><h1>Review</h1></header>"
            + (track + body if first else body + track),
            layout="sidebar",
        )
        page = open_page(browser, serve(source))
        box = """(id) => document.getElementById(id).getBoundingClientRect()"""
        resized(page, 1440, 900)
        body_box, track_box = page.evaluate(box, "body"), page.evaluate(box, "track")
        assert track_box["top"] == pytest.approx(body_box["top"], abs=1)
        assert (track_box["x"] < body_box["x"]) is first
        assert track_box["width"] < body_box["width"]
        resized(page, 390, 844)
        body_box, track_box = page.evaluate(box, "body"), page.evaluate(box, "track")
        assert (track_box["top"] < body_box["top"]) is first


def test_a_sidebar_pages_aside_takes_the_width_the_page_sets(browser, serve):
    """A page sizes a sidebar page's `aside` with `--aside` (page-layout.md, "A sidebar
    page"): beside the body it stands that wide and the body takes the rest of the row,
    and where the body's base no longer fits beside it the two stack, each across the
    row. Authors otherwise read the Layout's flex shares to find a rule to override."""
    source = leaf_page(
        "a sidebar page",
        "<header><h1>Review</h1></header>"
        "<aside id='track'><div class='layout-track'><p>Summary and contents.</p></div></aside>"
        "<div id='body'>" + "<p>Body paragraph. " * 40 + "</p></div>",
        head="<style>main { --aside: 16rem; }</style>",
        layout="sidebar",
    )
    page = open_page(browser, serve(source))
    box = "(id) => document.getElementById(id).getBoundingClientRect()"
    resized(page, 1440, 900)
    body_box, track_box = page.evaluate(box, "body"), page.evaluate(box, "track")
    assert track_box["width"] == pytest.approx(256, abs=0.5)
    assert track_box["top"] == pytest.approx(body_box["top"], abs=1)
    row = page.locator("main").evaluate(
        "node => node.clientWidth - parseFloat(getComputedStyle(node).paddingLeft)"
        " - parseFloat(getComputedStyle(node).paddingRight)"
    )
    gap = page.locator("main").evaluate(
        "node => parseFloat(getComputedStyle(node).columnGap)"
    )
    assert body_box["width"] == pytest.approx(row - 256 - gap, abs=0.5)
    resized(page, 760, 844)
    body_box, track_box = page.evaluate(box, "body"), page.evaluate(box, "track")
    assert track_box["top"] < body_box["top"]
    assert track_box["width"] == pytest.approx(body_box["width"], abs=0.5)


def test_a_sidebar_pages_items_trim_their_words_at_both_edges(browser, serve):
    """Each item in a sidebar page's row trims its words' outer margins, through any
    wrapper, as a column does at its edges: beside the body, a track whose heading sits in
    a wrapper starts level with a body whose heading doesn't, and stacked, the body ends
    at its last line, so only the row's gap stands before the track. Only an item's own
    first child was trimmed, so a wrapped heading stood its margin lower, and every item
    but the last kept its last paragraph's margin."""
    source = leaf_page(
        "a sidebar page",
        "<header><h1>Review</h1></header>"
        "<div id='body'><h2 id='body-head'>Findings</h2>"
        + "<p>Body paragraph. "
        * 40
        + "</p><p id='last'>The last line.</p></div>"
        "<aside id='track'><div class='layout-track'><h2 id='track-head'>Summary</h2>"
        "<p>Summary and contents.</p></div></aside>",
        layout="sidebar",
    )
    page = open_page(browser, serve(source))
    box = "(id) => document.getElementById(id).getBoundingClientRect()"
    resized(page, 1440, 900)
    body_head, track_head = (
        page.evaluate(box, "body-head"),
        page.evaluate(box, "track-head"),
    )
    assert track_head["x"] > body_head["x"]
    assert track_head["top"] == pytest.approx(body_head["top"], abs=0.5)
    resized(page, 390, 844)
    body, last = page.evaluate(box, "body"), page.evaluate(box, "last")
    assert body["bottom"] == pytest.approx(last["bottom"], abs=0.5)


@pytest.mark.parametrize("aside", ["16rem", "25%"])
def test_a_sidebar_pages_track_stays_in_view_only_beside_the_body(
    browser, serve, aside
):
    """An authored track scrolls beside the body, flows when stacked, and never covers the footer."""
    source = leaf_page(
        "Sidebar reading",
        '<aside id="route"><div class="layout-track" id="track">'
        + "<p>Follow-up to check.</p>" * 60
        + '</div></aside><div id="body">'
        + "<p>Body paragraph.</p>" * 100
        + '</div><footer id="foot">Reviewed.</footer>',
        head=f"<style>main {{ --aside:{aside} }}</style>",
        layout="sidebar",
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 800)
    track = page.locator("#track")
    assert track.evaluate("node => node.scrollHeight > node.clientHeight")
    page.evaluate("scrollTo(0,1000)")
    scroll_settled(page)
    assert track.bounding_box()["y"] >= 0
    track.evaluate("node => node.scrollTop=node.scrollHeight")
    assert track.evaluate("node => node.scrollTop > 0")
    page.evaluate("scrollTo(0,document.scrollingElement.scrollHeight)")
    scroll_settled(page)
    assert (
        track.bounding_box()["y"] + track.bounding_box()["height"]
        <= page.locator("#foot").bounding_box()["y"]
    )
    resized(page, 390, 800)
    assert track.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    route, body = (
        page.locator("#route").bounding_box(),
        page.locator("#body").bounding_box(),
    )
    assert route["y"] + route["height"] <= body["y"]


def test_a_revision_keeps_the_readers_place_in_a_sidebar_tracks_body(browser, serve):
    """The box a track gathers its blocks into is a reading region named by the track's
    id, so a neighbour never renames it. A revision that rewrites what the track holds,
    adding a block before the reader's and renaming theirs, writes it inside that box,
    which stays the one box the track holds and keeps the reader where they were. A
    revision that replaces the track gathers the replacement's blocks into a box of its
    own, standing beside the body, before the reader's place returns."""
    paragraphs = "".join(f"<p id='f{n}'>Follow-up {n} to check.</p>" for n in range(60))
    body = "<div id='body'>" + "<p>Body paragraph. " * 600 + "</p></div>"
    regions = """async () => (await window.__lfCheckApi())
      .readingRegions().map((region) => region.id)"""
    held = """(id) => {
      const track = document.getElementById(id);
      const held = track.querySelector(':scope > .layout-track');
      return { only: track.children.length === 1 && track.firstElementChild === held,
               kept: held?.dataset.probe === 'kept',
               blocks: [...(held?.children ?? [])].map((block) => block.id) };
    }"""

    def source(track, blocks):
        return leaf_page(
            "a sidebar page",
            f"<header><h1>Review</h1></header><aside id='{track}'><div class='layout-track' id='{track}-body'>{blocks}</div></aside>{body}",
            layout="sidebar",
        )

    page = open_page(
        browser, live_url(serve(source("track", f"<div id='block'>{paragraphs}</div>")))
    )
    resized(page, 900, 600)
    assert page.locator("#track > .layout-track").evaluate(
        "node => node.scrollHeight > node.clientHeight"
    )
    assert "lf-region:layout#track-body" in page.evaluate(regions)
    page.evaluate("scrollTo(0, 1500)")
    page.locator("#track > .layout-track").evaluate(
        "held => { held.dataset.probe = 'kept'; held.scrollTop = 1000; }"
    )
    scroll_settled(page)
    read = "() => document.getElementById('f30').getBoundingClientRect().top"
    before = page.evaluate(read)

    rewritten = f"<p id='lead'>Approve.</p><div id='checks'>{paragraphs}</div>"
    stamp_page(serve.page_dir, source("track", rewritten), "add a verdict")
    wait_for_revision(page, 2)
    scroll_settled(page)
    assert page.evaluate(held, "track") == {
        "only": True,
        "kept": True,
        "blocks": ["lead", "checks"],
    }
    assert "lf-region:layout#track-body" in page.evaluate(regions)
    assert page.evaluate(read) == pytest.approx(before, abs=2)

    stamp_page(serve.page_dir, source("new-track", rewritten), "rename the track")
    wait_for_revision(page, 3)
    assert page.locator("#new-track > .layout-track").evaluate(
        "node => node.scrollHeight > node.clientHeight"
    )
    assert page.evaluate(held, "new-track") == {
        "only": True,
        "kept": False,
        "blocks": ["lead", "checks"],
    }
    assert "lf-region:layout#new-track-body" in page.evaluate(regions)


def test_a_page_views_sidebar_uses_the_columns_margin(browser, serve):
    source = leaf_page(
        "View composition",
        '<h1>Release review</h1><lf-tabs id="topics" class="layout-flow">'
        '<lf-tab id="evidence-view" label="Evidence" class="layout-flow"><div class="layout-sidebar">'
        '<aside id="route"><div class="layout-track">Read the evidence.</div></aside>'
        '<div class="layout-column"><h2 id="evidence-title">Evidence</h2><p>Compare the counts.</p>'
        '<div id="wide" data-width="available">Evidence</div></div></div></lf-tab>'
        '<lf-tab id="decision-view" label="Decision" class="layout-flow"><h2>Decision</h2></lf-tab></lf-tabs>',
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    route, wide = (
        page.locator("#route").bounding_box(),
        page.locator("#wide").bounding_box(),
    )
    assert route["x"] + route["width"] <= wide["x"]
    page.get_by_role("tab", name="Decision", exact=True).click()
    expect(page.locator("#route")).not_to_be_visible()
    page.get_by_role("tab", name="Evidence", exact=True).click()
    expect(page.locator("#route")).to_be_visible()
    resized(page, 390, 844)
    route, heading = (
        page.locator("#route").bounding_box(),
        page.locator("#evidence-title").bounding_box(),
    )
    assert route["y"] + route["height"] <= heading["y"]


def test_each_part_of_a_page_of_parts_is_laid_out_as_a_page_of_its_own(browser, serve):
    """A page of parts stands its title and, under it, the list of parts in a column down
    the left, and lays the open part out beside them from the top of the page, as a page
    of its own with that part's Layout: a column part takes the column, margin content,
    contents map and breakouts a column page takes in a window as wide as the room beside
    the list, and a workspace part fills that room from the top of the window to the
    floating panel's row, so neither it nor a short part leaves the page anything to
    scroll. The row's room is the part's own end, so the part reaches the window's foot. On a phone
    the title, the list and the part stack."""
    column_body = """
<h1>Migration plan</h1>
<div class="layout-sidebar"><aside id="route"><div class="layout-track"><lf-toc id="contents"></lf-toc></div></aside><div class="layout-column layout-notes">
<div class="layout-note"><p>Support cadence.</p><aside class="note" id="frequency">Support runs this twice a month.</aside></div>
<h2 id="move">Move</h2>
<p>Shift one cohort at a time while keeping the old readers available.</p>
<div id="room" data-width="available">Available evidence.</div>
<div style="height: 1200px"></div></div></div>
"""
    parts = leaf_page(
        "parts",
        f"""<header id="title"><h1>Release review</h1></header>
<lf-parts id="parts">
<lf-part id="plan" label="Plan"><article id="box" class="layout-column">{column_body}</article></lf-part>
<lf-part id="queue" label="Queue"><div id="work" class="layout-workspace">
<header><h1>Queue</h1></header><div id="regions"><p>Work one item at a time.</p></div>
</div></lf-part>
<lf-part id="note" label="Note"><article class="layout-column"><p>One line.</p></article></lf-part>
</lf-parts>""",
        layout=None,
    )
    reading = """() => {
      const box = document.getElementById('box') ?? document.querySelector('main');
      const shell = box.parentElement;
      const origin = shell.getBoundingClientRect().left + shell.clientLeft;
      const rect = (node) => {
        const b = node.getBoundingClientRect();
        return [Math.round(b.left - origin), Math.round(b.right - origin)];
      };
      const measured = {
        width: shell.clientWidth,
        box: rect(box),
      };
      for (const id of ['route', 'frequency', 'room', 'contents']) {
        const node = document.getElementById(id);
        const style = getComputedStyle(node);
        measured[id] = [rect(node), style.float, style.position];
      }
      return measured;
    }"""
    page = open_page(browser, serve(parts))
    resized(page, 1600, 900)
    page.get_by_role("tab", name="Plan").click()
    in_part = page.evaluate(reading)
    list_box = page.locator("#parts > [role=tablist]").bounding_box()
    title_box = page.locator("#title h1").bounding_box()
    view_box = page.locator("#plan").bounding_box()
    assert title_box["y"] + title_box["height"] <= list_box["y"], (title_box, list_box)
    assert title_box["x"] + title_box["width"] <= view_box["x"], (title_box, view_box)
    assert list_box["x"] + list_box["width"] <= 1600 - in_part["width"], list_box
    assert root_overflow(page) == 0

    alone = open_page(browser, serve(leaf_page("parts", column_body, layout="column")))
    resized(alone, in_part["width"], 900)
    assert {**alone.evaluate(reading), "width": in_part["width"]} == in_part
    alone.close()

    fits = """() => {
      const scroller = document.scrollingElement;
      return scroller.scrollHeight - scroller.clientHeight;
    }"""
    page.get_by_role("tab", name="Queue").click()
    work = page.evaluate(
        """async () => {
          const {layoutBox} = await window.__lfCheckApi();
          const work = document.getElementById('work').getBoundingClientRect();
          const main = document.querySelector('main').getBoundingClientRect();
          const room = getComputedStyle(document.getElementById('queue')).paddingBlockEnd;
          return {width: Math.round(work.width), top: Math.round(work.top),
                  bottom: Math.round(work.bottom + parseFloat(room)),
                  mainBottom: Math.round(main.bottom), window: innerHeight,
                  box: layoutBox().id};
        }"""
    )
    assert work["box"] == "work", work
    assert work["width"] == in_part["width"], work
    assert work["top"] == round(view_box["y"]), work
    assert work["bottom"] == work["mainBottom"] == work["window"], work
    assert page.evaluate(fits) == 0
    page.get_by_role("tab", name="Note").click()
    assert page.evaluate(fits) == 0

    resized(page, 390, 800)
    stacked = page.evaluate(
        """() => ['#title', '#parts > [role=tablist]', '#work'].map(selector => {
          const box = document.querySelector(selector).getBoundingClientRect();
          return [Math.round(box.top), Math.round(box.bottom), Math.round(box.width)];
        })"""
    )
    (title, strip, view) = stacked
    assert title[1] <= strip[0] and strip[1] <= view[0], stacked
    assert view[2] == 390, stacked
    assert root_overflow(page) == 0


def test_the_handed_over_url_opens_the_latest_version(browser, serve):
    """The URL `server run` prints is the page root carrying the key, so every handover
    reads the latest version there while keeping the live address, and the key leaves
    the address bar on arrival. Three things only a real browser can say have to hold:
    the arrival sets the cookie used by the page's relative polling requests, the tab
    is left on the bare address, and a reload of that bare address is admitted. The
    link is followed from another site, as it is from a chat or an issue, since a
    `SameSite=Strict` cookie is withheld from requests another site starts: one
    withheld from the reload would land the user on a refusal."""
    url = serve(INLINE_PAGE)
    bare = url.rsplit("/versions/", 1)[0] + "/"
    handover = f"{bare}?t={TOKEN}"

    page = browser.new_page()
    page.route(
        "https://elsewhere.test/",
        lambda route: route.fulfill(
            content_type="text/html", body=f'<a href="{handover}">the page</a>'
        ),
    )
    page.goto("https://elsewhere.test/")
    page.click("a")
    page.wait_for_url(bare)
    wait_until_ready(page)
    expect(page.locator(".lf-floating-panel")).to_be_visible()
    # The poll is the page's own fetch, relative and query-less: it answers only if the
    # cookie rode along.
    assert page.evaluate("() => fetch('/api/state').then(r => r.status)") == 200

    page.reload()
    wait_until_ready(page)
    expect(page).to_have_url(bare)
    expect(page.locator(".lf-floating-panel")).to_be_visible()


def test_a_page_refuses_a_browser_that_never_had_the_link(browser, serve):
    url = serve(INLINE_PAGE)

    page = browser.new_page()
    page.goto(url.rsplit("?", 1)[0], wait_until="load")

    assert schema_model.NO_KEY in page.locator("body").inner_text()
    # The refusal is the subject: a user without the key is answered 401.
    consume_browser_errors(page, http_error_console(401))


@pytest.mark.parametrize(
    "notes,local_region",
    [(True, None), (False, None), (True, "bounded"), (True, "flow")],
)
def test_document_reading_survives_width_reflow(browser, serve, notes, local_region):
    """The implicit document keeps its passage as notes enter flow, just as panes do."""
    body = '<h1 id="title">Migration</h1><a href="#passage3">Read phase 3</a>'
    for number in range(1, 9):
        note = (
            f'<aside class="note" id="note{number}">Qualification {number}. '
            "Keep the old readers until the new cohort passes its checks.</aside>"
            if notes
            else ""
        )
        body += (
            f'<h2 id="heading{number}">Phase {number}</h2><div class="layout-note">'
            f'<p id="passage{number}">Phase {number} begins here. Advance one cohort at a time '
            f"and keep earlier readers available. The qualification explains this phase.</p>{note}</div>"
            "<p>The next phase follows a separate approval. Read the supporting material before deciding.</p>"
        )
        if number == 4 and local_region:
            body += (
                (
                    '<section id="local-region" style="height: 180px; overflow: auto">'
                    if local_region == "bounded"
                    else '<section id="local-region">'
                )
                + '<button id="local-control">Local control</button>'
                + (
                    "<p>Independent supporting material inside a local reading region.</p>"
                    * 12
                )
                + "</section>"
            )
    page = open_page(
        browser,
        serve(
            leaf_page("Reading through reflow", body).replace(
                '<main class="layout-column">',
                f'<main class="layout-column{" layout-notes" if notes else ""}">',
            )
        ),
    )
    if local_region:
        page.evaluate("""async () => {
          const {registerReadingRegion} = await window.__lfWidgetApi();
          const body = document.querySelector('#local-region');
          registerReadingRegion({id: body.id, host: body, body});
        }""")
    resized(page, 1440, 900)
    page.get_by_role("link", name="Read phase 3", exact=True).click()
    page.keyboard.press("Escape")
    page.mouse.wheel(0, 160)
    scroll_settled(page)
    reading = """async () => {
      const {capturePlace} = await window.__lfWidgetApi();
      return capturePlace();
    }"""
    if local_region == "bounded":
        page.get_by_role("button", name="Local control", exact=True).click()
        page.keyboard.press("Escape")
    before = page.evaluate(reading)
    assert before["quote"]
    for width in (390, 1440):
        resized(page, width, 900)
        after = page.evaluate(reading)
        assert after["quote"] == before["quote"]
        # Wrapping changes the line's height and its location within the passage.
        # Native anchoring keeps the reading, and a round trip restores its location.
        if width == 1440:
            assert after["quoteTop"] == pytest.approx(before["quoteTop"], abs=1)


@pytest.mark.parametrize("bad_write", ["restatement", "other-cycle", "priority-cycle"])
def test_the_write_gate_rejects_unchanged_authored_style_writes(
    browser, serve, bad_write
):
    source = leaf_page("Style gate", "<h1>Migration</h1>").replace(
        "<body", '<body style="--probe-stable: 1;"', 1
    )
    page = open_page(browser, serve(source))
    page.evaluate(
        """kind => {
      const body = document.body;
      if (kind === 'restatement') {
        body.setAttribute('style', body.getAttribute('style'));
        body.setAttribute('style', body.getAttribute('style'));
      } else if (kind === 'other-cycle') {
        body.style.setProperty('color', 'red');
        body.style.removeProperty('color');
      } else {
        body.style.setProperty('--probe-stable', '1', 'important');
        body.style.setProperty('--probe-stable', '1');
      }
    }""",
        bad_write,
    )
    failures = consume_browser_errors(page, {"code": "unchanged-write"})
    assert len(failures) == 1
    assert failures[0].values["what"] == "style", failures
    assert failures[0].values["node"][0].startswith("body"), failures


def test_a_control_the_page_writes_takes_leaf_type_and_yields_to_page_css(
    browser, serve
):
    """A bare button or field an author writes into the page reads in Leaf's type, as
    `.button` and `.field` do; left to the browser it drew 13.33px Arial beside the
    page's own type (#2559). The default weighs nothing, so a page rule of element
    selectors alone still sets its type."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Authored controls",
                """<h1>Authored controls</h1>
<p><button id="classed" class="button" type="button">Classed</button>
<button id="bare" type="button">Bare</button>
<input id="bare-field" type="text" aria-label="Bare field">
</p>
<section><button id="dressed" type="button">Dressed</button></section>""",
                head="<style>section button { font: 20px Georgia; }</style>",
            )
        ),
    )
    face = (
        "el => { const s = getComputedStyle(el); return [s.fontFamily, s.fontSize]; }"
    )
    leaf = page.locator("#classed").evaluate(face)
    assert page.locator("#bare").evaluate(face) == leaf
    assert page.locator("#bare-field").evaluate(face) == leaf
    assert page.locator("#dressed").evaluate(face) == ["Georgia", "20px"]


def test_a_reply_notice_survives_a_failed_state_and_keeps_its_agent(browser, serve):
    """A failed candidate owns neither the agent name nor the reply count.

    The first read reaches panel and version rendering before malformed projection data
    rejects it. That candidate does not announce the reply or leave a version behind;
    a complete retry announces the reply once, to the live region, with the agent
    recorded on the message.
    The rejected reply must also leave the visible thread until that retry.
    """
    url = serve(TWIN_V1)
    d = serve.page_dir
    root = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "which host answers?",
        },
    )
    page = open_page(browser, live_url(url))
    expect_open_threads(page, 1)
    field = page.locator(".lf-fp-field leaf-text")
    stamp_page(d, TWIN_V2, "a twin")
    wait_for_revision(page, 2)
    expect(field).not_to_have_attribute("placeholder", re.compile("this one does"))

    open_panel_thread(page, root["id"])
    write(panel_field(page), "keep this unfinished reply")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    broken = []

    def fail_after_rendering_the_panel(route):
        if broken:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        state["agent"] = "Rejected agent"
        rejected_version = {
            **state["versions"][-1],
            "version": state["versions"][-1]["version"] + 100,
        }
        state["versions"].append(rejected_version)
        state["browser"].setdefault("version_notes", {})[
            str(rejected_version["version"])
        ] = "Rejected version"
        view = state["browser"]["views"][str(state["active"]["revision"])]
        view["document"]["projection"]["entries"].append(None)
        broken.append(True)
        route.fulfill(status=response.status, json=state)

    page.route("**/api/state*", fail_after_rendering_the_panel)
    with page.expect_console_message(
        lambda message: "read failed" in message.text
    ) as fault:
        append_carried_log_record(
            d,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root["id"],
                "text": "this one does",
            },
        )
    assert (
        page.evaluate(
            "async () => (await window.__lfCheckApi()).readApplication().authoritative.agent"
        )
        == "Claude"
    )
    page.lf_errors.remove(console_finding(fault.value))

    view = open_panel_thread(page, root["id"])
    expect(view.locator(".lf-msg.agent .lf-msg-body")).to_have_count(0)
    expect(view.locator(".lf-msg.user .lf-msg-body")).to_have_text(
        "which host answers?"
    )
    expect(panel_field(page)).to_have_js_property("value", "keep this unfinished reply")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    expect(panel_menu(page, "versions")).not_to_contain_text("Rejected version")
    page.keyboard.press("Escape")

    assert "this one does" not in (field.get_attribute("placeholder") or "")
    assert "this one does" not in page.locator(".lf-live").text_content()

    page.unroute("**/api/state*")
    nudge(d)
    told(page)
    expect(page.locator(".lf-live")).to_have_text("this one does")
    expect(field).not_to_have_attribute("placeholder", re.compile("this one does"))
    view = open_panel_thread(page, root["id"])
    expect(view.locator(".lf-msg.agent .lf-msg-body")).to_have_text("this one does")
