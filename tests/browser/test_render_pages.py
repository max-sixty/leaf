"""File-authored anchors, drawings, width, and handover tests."""

import io
import json
import math
import re

import pytest
from click.testing import CliRunner
from interact_support import (
    add_test_widget,
    append_carried_log_record,
    record_claim,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import schema as schema_model
from leaf.render_checks import rendered, wait_until_ready
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_ASK_LAYER,
    SEATED_ASK_WIDGETS,
    live_url,
)
from render_cases_layout import banner_control, toggle_queue, with_one_ask
from render_cases_navigation import (
    composer_quote,
)
from render_cases_widgets import (
    AT_THE_HANDOVER,
    BROKEN_DIAGRAM_PAGE,
    CHROME_ROOM,
    CUT_BOXES_PAGE,
    DIAGRAM_AND_RAIL_PAGE,
    DIAGRAM_ROOM,
    DRAWING_PLACEMENT,
    DRAWN_PAST_A_RAIL_PAGE,
    FRAMED_WIDE_PAGE,
    LATE_MARGIN_PAGE,
    LATE_MARGIN_WIDGET,
    LONG_CHAIN_PAGE,
    NOTE_AND_WIDE_PAGE,
    NOTE_BAND,
    PICTURE_PAGE,
    RAIL_BAND_PAGE,
    RAIL_BANDS,
    RAIL_FIT,
    ROOM_GEOMETRY,
    TWIN_V1,
    TWIN_V2,
    TYPED_PARTS_PAGE,
    WIDE_AND_NARROW_PAGE,
    WIDE_DIAGRAM_PAGE,
)
from render_harness import (
    EXAMPLE_PACKAGES,
    EXAMPLES,
    INLINE_PAGE,
    LONG_PAGE,
    REPLY_HOST_PAGE,
    TOKEN,
    consume_browser_errors,
    held_frames,
    leaf_page,
    margins_laid_out,
    nudge,
    open_page,
    panel_settled,
    primed,
    refuse,
    resized,
    root_overflow,
    scroll_settled,
    sending,
    stamp_page,
    take_browser_errors,
    told,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_sort_source_follows_the_initial_step_when_code_arrives_later(browser, serve):
    """The film may paint its first step before the code's tokenizer returns."""
    example = next(path for path in EXAMPLES if path.stem == "rust-sort")
    context = browser.new_context(
        reduced_motion="reduce", viewport={"width": 1440, "height": 900}
    )
    held = []
    context.route("**/vendor/syntax.esm.js", lambda route: held.append(route))
    page = open_page(
        browser,
        serve(example),
        context=context,
        upgraded=False,
        wait_until="domcontentloaded",
    )
    expect(page.locator("#sort-film .sort-moment")).to_have_attribute(
        "data-part", "moment:random:7:0"
    )
    expect(page.locator("#sort-source [data-lf-indicated]")).to_have_count(0)
    assert held
    for route in held:
        route.continue_()
    context.unroute_all(behavior="wait")
    wait_until_ready(page)
    source = page.locator("#sort-source")
    indicated = source.locator("[data-lf-indicated]")
    expect(indicated).to_have_count(1)
    body = source.bounding_box()
    line = indicated.bounding_box()
    assert body["y"] + 40 <= line["y"]
    assert line["y"] + line["height"] <= body["y"] + body["height"] - 40
    expect(page.locator("#sort-film .sort-moment")).to_have_attribute(
        "data-part", "moment:random:7:0"
    )


def test_sort_film_readout_and_narration(browser, serve):
    """Changing step numbers hold their space, and narration renders inline Markdown."""
    example = next(path for path in EXAMPLES if path.stem == "rust-sort")
    page = open_page(browser, serve(example))
    readings = page.evaluate(
        """async () => {
          const widget = performance.getEntriesByType('resource')
            .find(resource => resource.name.endsWith('/page/widgets/lf-sort-film.js'));
          const source = new URL('../sort.js', widget.name);
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
            "open",
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
                "open",
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
    toggle = page.locator(".lf-threads-toggle")
    expect(toggle).to_have_text("Threads: 1")  # counted as open, like any other thread
    toggle.click()
    page.locator(".lf-thread-summary").first.click()
    thread = page.locator(".lf-thread").first
    expect(thread.locator(".lf-msg.agent")).to_have_count(1)
    expect(thread.locator(".lf-msg.agent > .lf-msg-head b")).to_have_text("Codex")
    expect(thread.locator(".lf-quote")).to_have_text("“Retries are capped at three”")

    write(thread.locator("leaf-text"), "three is the retry budget, not a guess")
    with sending(page, "the reply"):
        thread.get_by_role("button", name="Send", exact=True).click()
    expect(page.locator(".lf-msg.user")).to_have_count(1)
    with sending(page, "the resolve"):
        page.locator(".lf-thread").first.get_by_role(
            "button", name="Resolve thread", exact=True
        ).click()
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")

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
        layer_registry=SEATED_ASK_LAYER,
        layer_widgets=SEATED_ASK_WIDGETS,
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
    assert fault.value.text in page.lf_errors
    page.lf_errors.remove(fault.value.text)

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
        layer_registry=SEATED_ASK_LAYER,
        layer_widgets=SEATED_ASK_WIDGETS,
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
    assert fault.value.text in page.lf_errors
    page.lf_errors.remove(fault.value.text)

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
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    draft = page.locator(".lf-thread leaf-text")
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

    assert fault.value.text in page.lf_errors
    page.lf_errors.remove(fault.value.text)
    expect(page.locator(".lf-thread leaf-text")).to_have_js_property(
        "value", "keep this unfinished reply"
    )
    expect(page.locator(".lf-thread leaf-text")).to_be_focused()
    assert draft.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [5, 12, "backward"]

    page.unroute("**/api/state*")
    nudge(page_dir)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    # The card keeps the user's editing place and holds the remote resolution
    # behind a notice until they choose to show it.
    thread = page.locator(".lf-thread")
    expect(thread.locator(".lf-thread-news")).to_have_text("Resolved")
    expect(thread).to_have_attribute("data-resolved", "false")
    expect(page.locator(".lf-thread leaf-text")).to_have_js_property(
        "value", "keep this unfinished reply"
    )
    thread.locator(".lf-thread-news").click()
    expect(thread).to_have_attribute("data-resolved", "true")
    expect(thread.get_by_role("button", name="Reopen")).to_be_visible()


def test_a_failed_state_keeps_focus_in_the_open_versions_menu(browser, serve):
    """Rollback preserves an unchanged picker subtree and its focused row."""
    url = serve(TWIN_V1)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    stamp_page(d, TWIN_V2, "a twin")
    wait_for_revision(page, 2)
    banner_control(page, ".lf-version").click()
    menu = page.locator(".lf-version-menu")
    row = menu.locator('.lf-version-row[aria-current="true"]')
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
    assert fault.value.text in page.lf_errors
    page.lf_errors.remove(fault.value.text)

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
    registry = json.loads((serve.page_dir / "registry.json").read_text())
    assert registry["lf-diagram"]["x-visual"], "this test needs the shipped declaration"
    registry["lf-code"]["x-visual"] = "whole"  # a widget core has never heard of
    (serve.page_dir / "registry.json").write_text(json.dumps(registry))
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
        """el => { const style = getComputedStyle(el); return {
          background: style.backgroundImage,
          borders: [style.borderTopWidth, style.borderRightWidth,
                    style.borderBottomWidth, style.borderLeftWidth],
        }; }"""
    )
    assert look["background"] == "none", look
    assert len(set(look["borders"])) == 1 and look["borders"][0] != "0px", look
    page.keyboard.press("Escape")

    # And a paragraph is still text: the click reaches no picture and raises nothing.
    page.locator("#p").click()
    expect(
        page.locator(".lf-fab-input"),
        "a click on prose was read as a click on a picture",
    ).not_to_be_visible()


def _edge_ink_changes(quiet, painted, target, clip, ink):
    """Count newly painted target ink on each edge of a clipped screenshot."""
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
        "top": (
            math.floor(left) + 4,
            math.floor(top) - 1,
            math.ceil(right) - 4,
            math.ceil(top) + 2,
        ),
        "bottom": (
            math.floor(left) + 4,
            math.floor(bottom) - 2,
            math.ceil(right) - 4,
            math.ceil(bottom) + 1,
        ),
    }
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
    down both sides. The projected contour remains visible above all four edges.
    """
    example = next(path for path in EXAMPLES if path.stem == "release-notes")
    page = open_page(browser, serve(example))
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
    comparison = shot.locator("wa-comparison")
    comparison.click(modifiers=["Alt"], position={"x": box["width"] / 4, "y": 80})
    expect(comparison).to_have_attribute("position", "50")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(shot).to_have_class(re.compile(r"\blf-projected-mark\b"))
    overlay = page.locator(".lf-visual-mark-pending")
    expect(overlay).to_be_visible()
    ink = overlay.evaluate(
        """element => getComputedStyle(element).borderLeftColor
          .match(/[0-9.]+/g).slice(0, 3).map(Number)"""
    )
    marked = screenshot()

    changed, _ = _edge_ink_changes(quiet, marked, box, clip, ink)
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
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    panel_settled(page)
    page.locator(".lf-thread .lf-quote").click()

    card = page.locator("#lp-k-checks")
    mark = page.locator('.lf-visual-mark[data-for="lp-k-checks"].lf-visual-mark-here')
    expect(mark).to_be_visible()
    card.scroll_into_view_if_needed()
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


def test_a_screenshot_margin_trace_paints_one_complete_quiet_contour(browser, serve):
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
        await window.__lfRuntimeImport('/runtime/widget-api.js');
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
          context.fillStyle = getComputedStyle(element).borderLeftColor;
          context.fillRect(0, 0, 1, 1);
          return [...context.getImageData(0, 0, 1, 1).data.slice(0, 3)];
        }"""
    )
    traced = screenshot()

    changed, missing = _edge_ink_changes(quiet, traced, box, clip, ink)
    assert not missing, (
        f"the screenshot frame covered the trace's {missing} edge: {changed} ink pixels"
    )
    assert shot.evaluate("element => getComputedStyle(element).outlineStyle") == "none"
    shot.locator('.lf-shotcap[data-lf-state="after"]').click()
    expect(shot.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()


def test_a_diagram_follows_the_scheme_it_is_read_in(browser, serve):
    """The SVG keeps Leaf's theme variables, so a scheme flip repaints it live."""
    page = open_page(browser, serve(WIDE_DIAGRAM_PAGE))
    node = page.locator("#flow svg .node rect").first
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
    it lays its columns out into whatever it is given, so it takes that shared number and
    stops there on the same window that hands the diagram half as much again.

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
    """A focused visual paints one ring: its own, since its thread draws nothing at
    rest. Standing in that thread moves the contour into the projected mark."""
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
    expect(diagram).to_have_css("outline-style", "solid")
    expect(diagram).to_have_css("outline-width", "2px")
    mark = page.locator(".lf-visual-mark")
    expect(mark).to_have_count(0)

    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    panel_settled(page)
    page.locator(".lf-threads > .lf-thread .lf-quote").first.click()
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
        page.get_by_text("Leaf couldn't start. Waiting for the server to update.")
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
        page.get_by_text("Leaf couldn't start. Waiting for the server to update.")
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
    # Linux's DejaVu labels draw this graph at 1217px. Use a width where the drawing
    # fits the room after a classic scrollbar has been taken, with the rail standing.
    resized(page, 1920, 900)
    at = page.evaluate(DRAWING_PLACEMENT)

    assert at["place"] == "rail", (
        "the row is not in the rail, so nothing here shows a standing rail leaving the "
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

    resized(page, 1200, 900)
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


def test_available_space_uses_the_free_side_of_a_margin_resident(browser, serve):
    """A resident removes only the room it takes. The contents map rests as its spine,
    chrome fixed in the left margin that states the room it takes there
    (`--lf-taken-l`), and reveals its labels over the page; so an available surface
    grows left only to stop short of the spine, reaches the shell's right gutter, and
    takes what symmetry would otherwise strand."""
    source = leaf_page(
        "available beside a contents spine",
        """
<aside class="sidebar"><lf-toc id="space-toc"></lf-toc></aside>
<h1 id="t">Sessions</h1>
<h2 id="before">Before</h2><p>The drawing follows.</p>
<lf-diagram id="flow"><pre>
graph LR
  R[request] --> C{cookie valid?}
  C -->|yes| S[read session from Redis]
  S -->|hit| H[handle]
  S -->|miss/outage| F[verify signed fallback]
  F --> H
  C -->|no| L[login]
</pre></lf-diagram>
<h2 id="after">After</h2><p>The drawing precedes this section.</p>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1726, 900)
    at = page.evaluate("""() => {
      const main = document.querySelector('main');
      const ms = getComputedStyle(main), mb = main.getBoundingClientRect();
      const box = document.getElementById('flow').getBoundingClientRect();
      const toc = document.querySelector('lf-toc').getBoundingClientRect();
      const body = document.body.getBoundingClientRect();
      return {
        box: {left: box.left, right: box.right, width: box.width},
        column: {
          left: mb.left + parseFloat(ms.paddingLeft),
          right: mb.right - parseFloat(ms.paddingRight),
        },
        toc: {left: toc.left, right: toc.right, width: toc.width},
        taken: (() => {
          const probe = document.createElement('i');
          probe.style.cssText = 'position:fixed;visibility:hidden;width:var(--lf-taken-l)';
          main.append(probe);
          const width = probe.getBoundingClientRect().width;
          probe.remove();
          return width;
        })(),
        roomLeft: body.left + parseFloat(getComputedStyle(document.body).paddingLeft),
        roomRight: body.right - parseFloat(getComputedStyle(document.body).paddingRight),
      };
    }""")
    # The spine is the map's resting face, a strip at its left edge the width of its
    # own inset; the room it states covers that strip and a gutter beyond it.
    assert at["taken"] >= 24, at
    assert abs(at["box"]["left"] - (at["roomLeft"] + 24 + at["taken"])) <= 1, at
    assert at["box"]["left"] >= at["toc"]["left"] + 24, at
    assert abs(at["box"]["right"] - (at["roomRight"] - 24)) <= 1, at
    assert at["box"]["width"] > 1080, at
    assert at["box"]["left"] < at["column"]["left"] - 100, at
    assert root_overflow(page) == 0, at


def test_a_widget_that_declares_width_takes_the_room_and_the_column_stays_put(
    browser, serve
):
    """A board's columns are as wide as what they hold and prose is set to a measure, so
    a page carrying both used to be a cramped board or a page widened past its own
    measure for one exhibit. x-space declares the capacity a widget needs, and the theme spends
    the room the layout measured — so the exhibit grows, the prose does not move, and the
    axis they share is what keeps a page that mixes widths reading as one design.

    The diff is the half that says the declaration is doing this. It is a widget too, and
    its lines are written to a width source already fits, so it stays in the column: a
    rule that reached every widget, or one naming lf-board, would pass every other
    assertion here and fail this one."""
    page = open_page(browser, serve(WIDE_AND_NARROW_PAGE))

    wide = page.evaluate(ROOM_GEOMETRY)
    assert wide["board"]["width"] > wide["column"]["width"], (
        "a widget declaring width must take more than the column: board "
        f"{wide['board']['width']:.0f}px, column {wide['column']['width']:.0f}px"
    )
    # Room to spare at this viewport, so a board stopping short of it is the shared cap
    # binding rather than the window — one width for the vocabulary, not each widget's own.
    assert wide["board"]["width"] < wide["room"]["width"], (
        "the breakout must stop at one stated width, not fill whatever is there"
    )
    assert wide["board"]["left"] >= wide["room"]["left"] - 1, (
        "past the page on the left"
    )
    assert wide["board"]["right"] <= wide["room"]["right"] + 1, "past the page, right"
    assert abs(wide["board"]["centre"] - wide["column"]["centre"]) <= 1, (
        "an exhibit that grows off the column's axis reads as one that slipped: "
        f"board centre {wide['board']['centre']:.0f}, column {wide['column']['centre']:.0f}"
    )
    assert abs(wide["diff"]["width"] - wide["column"]["width"]) <= 1, (
        "a widget that declares nothing keeps the column: diff "
        f"{wide['diff']['width']:.0f}px against {wide['column']['width']:.0f}px"
    )
    assert abs(wide["prose"]["width"] - wide["column"]["width"]) <= 1, (
        "prose keeps its measure whatever the exhibits beside it do"
    )
    assert root_overflow(page) == 0, "the page must not scroll sideways"

    # Under the column's own width there is no room to take, and the rule has to come out
    # as the layout the page already had — the same edge, not an inset approximation of it.
    resized(page, 700, 900)
    narrow = page.evaluate(ROOM_GEOMETRY)
    assert narrow["column"]["width"] < 720, (
        "the narrow half proves nothing unless the window is under the column"
    )
    assert abs(narrow["board"]["left"] - narrow["column"]["left"]) <= 1, (
        "a board on a narrow window must start where the prose starts: board at "
        f"{narrow['board']['left']:.0f}, column at {narrow['column']['left']:.0f}"
    )
    assert abs(narrow["board"]["width"] - narrow["column"]["width"]) <= 1, (
        "and be the column exactly: board "
        f"{narrow['board']['width']:.0f}px, column {narrow['column']['width']:.0f}px"
    )
    assert root_overflow(page) == 0, "nor scroll sideways on a narrow window"


def test_authored_blocks_choose_wide_or_available_space(browser, serve):
    """One authored width contract applies to native and package blocks. Column remains
    the prose measure when nested in a wider section rather than inheriting its
    containing block's allocation: there a block declared the column by its widget
    (lf-options) starts at the section's edge as the section's text does, rather than
    centred in the room."""
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
    assert at["options"]["space"] == "column"
    assert at["wide"]["left"] < at["prose"]["left"]
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
    Narrow boards scroll their columns inside that allocation rather than the page.
    """
    sidebar = '<aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>'
    boards = "".join(
        f'<lf-board id="board-{count}">'
        + "".join(
            f'<lf-column id="col-{count}-{i}" label="Column {i}"></lf-column>'
            for i in range(count)
        )
        + "</lf-board>"
        for count in (4, 5, 6)
    )
    for resident in (sidebar, ""):
        page = open_page(
            browser,
            serve(
                leaf_page(
                    "Board beside contents",
                    resident
                    + '<h1>Board beside contents</h1><section id="boards"><h2>Boards</h2>'
                    + '<div id="wide" data-width="wide">Wide evidence.</div>'
                    + '<div id="room" data-width="available">Available evidence.</div>'
                    + boards
                    + "</section>",
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
                assert at["board-4"]["scrolls"] > 0, at
                assert at["board-5"]["scrolls"] > 0, at
            elif width == 1440:
                assert at["wide"]["width"] == pytest.approx(1080, abs=1), at
                assert at["room"]["width"] > at["wide"]["width"], at


def test_an_ask_and_a_callout_keep_the_column_and_widen_to_what_they_hold(
    browser, serve
):
    """On a sidebar page an Ask and a callout keep the prose's width and left edge, so
    the Ask's ring and pin stand beside what it asks, as on a column page. One granted
    `data-width`, or holding a block of its own that declares one, takes that room for
    the evidence. On a column page the Ask stays in the column and its wide block breaks
    out of it, as the block would from a section; the table's twelve columns need the
    room, since a table granted it takes only what its columns need."""
    cells = "<td>p95 latency</td>" * 12
    table = '<table id="{id}-t" data-width="wide"><tr>' + cells + "</tr></table>"
    ask = (
        '<lf-ask id="{id}"{width}><h3>Ship it?</h3>{table}<lf-options id="{id}-o" '
        'choose><lf-option id="{id}-yes">Yes</lf-option></lf-options></lf-ask>'
    )
    body = (
        '<p id="prose">Prose.</p>'
        + ask.format(id="ask", width="", table="")
        + ask.format(id="granted", width=' data-width="wide"', table="")
        + ask.format(id="holds", width="", table=table.format(id="holds"))
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
    # An option list keeps the measure whatever one option holds: only a box's own
    # blocks widen it.
    for boxed in ("ask", "callout", "list"):
        assert at[boxed] == {"width": 720, "left": edge}, (boxed, at)
    # A granted callout's padding and border fall inside the wide measure.
    for wide in ("granted", "granted-c", "holds"):
        assert at[wide] == {"width": 1080, "left": edge}, (wide, at)
    # The widened Ask frames its table, which stands wider than the measure.
    assert at["holds-t"]["width"] > 720, at

    column = open_page(browser, serve(leaf_page("Column", body)))
    resized(column, 1726, 900)
    at = column.evaluate(measure)
    assert at["holds"]["width"] == at["prose"]["width"] == 720, at
    assert at["holds-t"]["width"] == 1080, at
    assert at["holds-t"]["left"] < at["prose"]["left"], at


NOTE = '<aside class="sidenote" id="note"><p>A note that needs a sidenote.</p></aside>'


@pytest.mark.parametrize(
    ("resident", "posture", "engine"),
    [
        ("", "even", "browser"),
        ('<aside class="sidebar"><lf-toc id="toc"></lf-toc></aside>', "map", "browser"),
        (NOTE, "note", "browser"),
        (
            '<aside class="sidebar"><p>Owner: payments.</p></aside>',
            "sidebar",
            "browser",
        ),
        ("", "even", "firefox_browser"),
        ("", "even", "webkit_browser"),
    ],
)
@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_table_granted_room_stands_on_the_prose_axis(
    request, serve, resident, posture, engine, direction
):
    """A table given `data-width` keeps its columns' natural width and stands centred on
    the prose axis, however unevenly the margins share the room: a contents map's spine
    or a column moved over for a sidenote leaves one side narrower. One that fits the
    column keeps its natural width and starts where the prose starts. Where a sidebar
    stands in the left margin the room is all on the right, so the table starts at the
    prose's left edge and grows right. In a right-to-left page the same holds with the
    narrow table at the prose's right edge, where its text starts; the sidebar stands
    on the left there too.

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
        f"{resident}<h1>Tables</h1>"
        '<p id="prose">A paragraph at the measure, long enough to fill the column it '
        "stands in from one edge to the other.</p>"
        f'<table id="wide" data-width="available">{grid}</table>'
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
        margin: document.querySelector('main').getAttribute('data-lf-margin') ?? '',
        prose: edges(document.getElementById('prose')),
        wide: grid('wide'),
        narrow: grid('narrow'),
        turned: grid('turned'),
        celled: edges(document.getElementById('celled')),
        itemed: edges(document.getElementById('itemed')),
        beside: edges(document.getElementById('beside')),
        cell: edges(document.getElementById('cell')),
      };
    }""")
    if posture != "even":
        assert posture in at["margin"].split(), at
    prose = at["prose"]
    start = "left" if direction == "ltr" else "right"
    assert at["narrow"][start] == pytest.approx(prose[start], abs=1), at
    assert at["wide"]["right"] - at["wide"]["left"] > prose["right"] - prose["left"], at
    if posture == "sidebar":
        assert at["wide"]["left"] == pytest.approx(prose["left"], abs=1), at
    else:
        assert at["wide"]["centre"] == pytest.approx(prose["centre"], abs=1), at
    for edge in ("left", "right"):
        assert at["turned"][edge] == pytest.approx(at["wide"][edge], abs=1), at
        for kept in ("celled", "itemed"):
            assert at[kept][edge] == pytest.approx(at["cell"][edge], abs=1), (kept, at)
    width = lambda box: box["right"] - box["left"]
    assert width(at["beside"]) == pytest.approx(width(at["cell"]), abs=1), at
    assert root_overflow(page) == 0


@pytest.mark.parametrize("holder", ["flow", "list-item", "quotation"])
@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_scrolling_breakout_table_keeps_its_caption_in_its_scrollport(
    browser, serve, direction, holder
):
    """A table granted room sizes its box to its columns, so it is no longer the
    container its caption reads its width from; the caption is held to the box instead.
    On a phone, where the room is the column and an eight-column table scrolls, a long
    caption stays inside the scrollport at either end of the scroll: in the page's flow,
    in a list item, whose table is measured from the column as the bound is, and in a
    quotation, whose frame holds it."""
    cells = "".join(f"<td>measured value {i}</td>" for i in range(8))
    caption = "Services in the migration, by stage, with their owners and windows"
    table = (
        f'<table id="wide" data-width="available"><caption>{caption}</caption>'
        f"<tr>{cells}</tr></table>"
    )
    if holder == "list-item":
        table = f"<ol><li>An item holding the table.{table}</li></ol>"
    elif holder == "quotation":
        table = f"<blockquote><p>A quotation holding the table.</p>{table}</blockquote>"
    body = "<h1>Tables</h1><p>A paragraph at the measure.</p>" + table
    source = leaf_page("Caption", body).replace(
        '<html lang="en">', f'<html lang="en" dir="{direction}">', 1
    )
    page = open_page(browser, serve(source))
    resized(page, 390, 844)
    table = page.locator("#wide")
    assert table.evaluate("t => t.scrollWidth > t.clientWidth")
    reading = """t => {
      const box = t.getBoundingClientRect(), cap = t.querySelector('caption')
        .getBoundingClientRect();
      return {box: [box.left, box.right], caption: [cap.left, cap.right]};
    }"""
    for end in (0, -10_000 if direction == "rtl" else 10_000):
        table.evaluate("(t, x) => { t.scrollLeft = x; }", end)
        rendered(page)
        at = table.evaluate(reading)
        assert at["caption"][0] >= at["box"][0] - 1, (end, at)
        assert at["caption"][1] <= at["box"][1] + 1, (end, at)
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


@pytest.mark.parametrize(
    ("posture", "engine"),
    [(posture, "browser") for posture in ("even", "map", "sidebar", "phone")]
    + [
        (posture, engine)
        for engine in ("firefox_browser", "webkit_browser")
        for posture in ("even", "phone")
    ],
)
@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_breakout_in_an_indented_holder_measures_its_room_from_the_column(
    request, serve, direction, posture, engine
):
    """A holder that stands in from the column, however it got there, gives a block
    that breaks out of it the column's room: three nested list items, a step list whose
    items pad themselves, a list the page resets to no indent, and a page's own indented
    block. The runtime reads how far each holder stands in rather than each kind of
    holder declaring it, so a wide or available block in any of them takes the same box
    as one in the page's flow, on the prose axis, beside a contents map and with a
    sidebar in the margin as on a plain column, and on a phone. A table wider than its
    holder stands where one in the page's flow does: centred on the prose axis, or from
    the prose's left edge beside a margin sidebar. One that fits its holder stays with
    it, starting where the holder's text starts. Nothing the page scrolls sideways, in
    Chromium, Firefox and WebKit: Firefox had counted where a table stood before it was
    moved over, 10px past a phone's window.

    A box the page arranges itself is no holder of that kind, since the room beside it is
    the page's own: a block that is an item of the page's grid takes its track, one in a
    flex row takes its share of the row beside its sibling, a table in an inline
    block scrolls inside it, and a block in a holder's second column keeps to that
    column. A link or a span around a block is no such box: the browser sets the block
    in the column's flow, so it grows as one in the flow does."""
    browser = request.getfixturevalue(engine)
    source = INDENTED_PAGE
    if posture == "map":
        source = source.replace(
            '<main class="layout-column">',
            '<main class="layout-column"><aside class="sidebar">'
            '<lf-toc id="toc"></lf-toc></aside>',
            1,
        )
    elif posture == "sidebar":
        source = source.replace(
            '<main class="layout-column">',
            '<main class="layout-column"><aside class="sidebar">'
            "<p>Owner: payments. Window: Thursday.</p></aside>",
            1,
        )
    source = source.replace(
        '<html lang="en">', f'<html lang="en" dir="{direction}">', 1
    )
    page = open_page(browser, serve(source))
    if posture == "phone":
        resized(page, 390, 844)
    else:
        resized(page, 1440, 900)
    margins_laid_out(page)
    at = page.evaluate(
        """(direction) => {
      const edges = (el) => {
        const box = el.getBoundingClientRect();
        return {left: box.left, right: box.right, centre: (box.left + box.right) / 2};
      };
      const textStart = (el) => {
        const box = el.getBoundingClientRect(), style = getComputedStyle(el);
        return direction === 'rtl'
          ? box.right - parseFloat(style.paddingRight) - parseFloat(style.borderRightWidth)
          : box.left + parseFloat(style.paddingLeft) + parseFloat(style.borderLeftWidth);
      };
      const reading = {
        margin: document.querySelector('main').getAttribute('data-lf-margin') ?? '',
        prose: edges(document.getElementById('prose')),
      };
      for (const name of ['control', 'nested', 'steps', 'plain', 'inset'])
        reading[name] = {
          wide: edges(document.getElementById(`${name}-wide`)),
          available: edges(document.getElementById(`${name}-available`)),
          table: edges(document.querySelector(`#${name}-table tr`)),
          narrow: edges(document.querySelector(`#${name}-narrow tr`)),
          text: textStart(document.getElementById(`${name}-narrow`).parentElement),
        };
      reading.arranged = Object.fromEntries([
        'gridded-track', 'gridded-wide', 'gridded-available', 'flexed-beside',
        'flexed-wide', 'boxed', 'boxed-table', 'linked-wide', 'spanned-wide', 'cols',
        'cols-wide',
      ].map((id) => [id, edges(document.getElementById(id))]));
      return reading;
    }""",
        direction,
    )
    if posture in ("map", "sidebar"):
        assert posture in at["margin"].split(), at
    control, prose = at["control"], at["prose"]
    start = "left" if direction == "ltr" else "right"
    assert abs(at["nested"]["text"] - control["text"]) >= 70, at
    for name in ("nested", "steps", "plain", "inset"):
        holder = at[name]
        for block in ("wide", "available", "table"):
            for edge in ("left", "right"):
                assert holder[block][edge] == pytest.approx(
                    control[block][edge], abs=1
                ), (name, block, edge, at)
        assert holder["narrow"][start] == pytest.approx(holder["text"], abs=1), (
            name,
            at,
        )
    if posture in ("even", "map"):
        assert control["wide"]["centre"] == pytest.approx(prose["centre"], abs=1), at
        assert control["table"]["centre"] == pytest.approx(prose["centre"], abs=1), at
    elif posture == "sidebar":
        assert control["table"]["left"] == pytest.approx(prose["left"], abs=1), at
    arranged = at["arranged"]
    for block in ("gridded-wide", "gridded-available"):
        for edge in ("left", "right"):
            assert arranged[block][edge] == pytest.approx(
                arranged["gridded-track"][edge], abs=1
            ), (block, at)
    beside, wide = arranged["flexed-beside"], arranged["flexed-wide"]
    assert wide["right"] - wide["left"] == pytest.approx(
        beside["right"] - beside["left"], abs=1
    ), at
    assert wide["left"] >= beside["right"] or wide["right"] <= beside["left"], at
    assert arranged["boxed-table"]["left"] >= arranged["boxed"]["left"] - 1, at
    assert arranged["boxed-table"]["right"] <= arranged["boxed"]["right"] + 1, at
    for block in ("linked-wide", "spanned-wide"):
        for edge in ("left", "right"):
            assert arranged[block][edge] == pytest.approx(
                control["wide"][edge], abs=1
            ), (block, at)
    columns, in_column = arranged["cols"], arranged["cols-wide"]
    assert in_column["right"] - in_column["left"] == pytest.approx(
        (columns["right"] - columns["left"] - 16) / 2, abs=1
    ), at
    assert (
        columns["left"] - 1
        <= in_column["left"]
        < in_column["right"]
        <= (columns["right"] + 1)
    ), at
    assert root_overflow(page) == 0


RESTYLED = """async ([selector, how]) => {
  const holder = document.querySelector(selector);
  const edges = (id) => {
    const box = document.getElementById(id).getBoundingClientRect();
    return {left: box.left, right: box.right};
  };
  // The next rendering update, read in a ResizeObserver made after the runtime's: after
  // its frame callbacks, layout and the runtime's own observers, and before it paints.
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
  // Frame callbacks are held, so after one update and a task none the runtime asked for
  // before the change is left to run in the update that lays the change out.
  await update();
  await new Promise((resolve) => setTimeout(resolve));
  if (how === 'class') holder.classList.add('deeper');
  else if (how === 'style') holder.style.paddingInlineStart = '64px';
  else if (how === 'remove' || how === 'unhold') {
    // Unwatched by the removal itself, in the microtask it queues, before a rendering
    // update could report the removed box's size: the holder's list, or only the
    // breakouts it held, leaving the holder in place.
    if (how === 'remove') holder.closest('main > ul').remove();
    else for (const breakout of holder.querySelectorAll(':scope > [data-lf-space]'))
      breakout.remove();
    await null;
    return {replaced: window.lfWatchedHolder(holder)};
  }
  else {
    // As a revision replaces a passage: the list holding the holder, anew, with one
    // more list inside.
    const list = holder.closest('main > ul');
    const copy = list.cloneNode(true);
    copy.querySelector(selector).insertAdjacentHTML('beforeend', '<ul><li id="late">Four'
      + '<div id="late-wide" data-lf-space="wide">Wide.</div>'
      + '<table id="late-narrow" data-lf-space="available"><tr><th>Plan</th>'
      + '<td>60</td></tr></table></li></ul>');
    list.replaceWith(copy);
  }
  const watched = window.lfWatchedHolder;
  await update();
  const name = how === 'insert' ? 'late' : holder.id;
  return {
    moved: edges(`${name}-narrow`),
    wide: edges(`${name}-wide`),
    control: edges('control-wide'),
    replaced: watched(holder),
    current: watched(document.getElementById(name)),
  };
}"""


# Which elements some ResizeObserver watches, kept from before the runtime makes one.
WATCHED_HOLDERS = """(() => {
  const watched = new Map();
  const {observe, unobserve, disconnect} = ResizeObserver.prototype;
  ResizeObserver.prototype.observe = function (target, options) {
    if (!watched.has(this)) watched.set(this, new Set());
    watched.get(this).add(target);
    return observe.call(this, target, options);
  };
  ResizeObserver.prototype.unobserve = function (target) {
    watched.get(this)?.delete(target);
    return unobserve.call(this, target);
  };
  ResizeObserver.prototype.disconnect = function () {
    watched.delete(this);
    return disconnect.call(this);
  };
  window.lfWatchedHolder = (target) =>
    [...watched.values()].some((targets) => targets.has(target));
})();"""


@pytest.mark.parametrize("how", ["class", "style", "insert", "remove", "unhold"])
def test_a_breakout_moved_in_after_load_re_lands_before_it_paints(browser, serve, how):
    """A breakout whose holder stands further in after load stays on the prose axis
    from the first paint that shows it, without waiting for a frame's margin pass or
    the next resize: one a revision's replacement puts a list deeper, and a holder a
    class or an inline style pads anew, which inserts nothing. A holder a revision
    removes, with or without a replacement, or one whose breakouts a revision removes,
    is no longer watched. Each is read again in the rendering update
    that lays the change out, before that update paints."""
    source = INDENTED_PAGE.replace(
        " .inset { padding-left: 40px; }",
        " .inset { padding-left: 40px; } .inset.deeper { padding-left: 100px; }",
        1,
    )
    page = open_page(browser, serve(source), init_script=WATCHED_HOLDERS)
    resized(page, 1440, 900)
    margins_laid_out(page)
    holder = "#inset" if how == "class" else "#nested"
    before = page.evaluate(
        "(id) => document.getElementById(id).getBoundingClientRect().left",
        f"{holder[1:]}-narrow",
    )
    assert page.evaluate(
        "(selector) => lfWatchedHolder(document.querySelector(selector))", holder
    )
    with held_frames(page):
        at = page.evaluate(RESTYLED, [holder, how])
    # The holders watched for a change of width are the ones the reading measured: a
    # revision's replacement, or a removal alone, leaves a holder it removed, or one
    # that holds no breakout now, unwatched.
    assert at["replaced"] == (how in ("class", "style")), at
    if how in ("remove", "unhold"):
        return
    assert at["current"], at
    assert at["moved"]["left"] > before + 20, ("the holder was not padded", at)
    for edge in ("left", "right"):
        assert at["wide"][edge] == pytest.approx(at["control"][edge], abs=1), at
    if how != "insert":
        return
    # A holder a revision brings and then takes away again, with no reading after the
    # removal to replace one, is held by nothing the runtime keeps. An authored holder
    # is no test of this, since the authored copy of the document maps back to every
    # node the page was written with (prepaint.js, `origins`), nor is a table, which
    # other owners release on their next frame.
    with held_frames(page):
        page.evaluate("""async () => {
          // Let a frame requested before the hold run, so no reading follows below.
          await new Promise((resolve) => {
            const observer = new ResizeObserver(() => {
              observer.disconnect();
              setTimeout(resolve);
            });
            observer.observe(document.body);
          });
          const lf = document.documentElement.lfInitial;
          window.lfReadings = 0;
          for (const name of ['residency', 'indents']) {
            const read = lf[name];
            lf[name] = () => (window.lfReadings++, read());
          }
          const main = document.querySelector('main');
          main.insertAdjacentHTML('beforeend', '<ul><li id="gone">Gone'
            + '<div data-lf-space="wide">Wide.</div></li></ul>');
          const gone = document.getElementById('gone');
          await null;
          if (!window.lfWatchedHolder(gone)) throw new Error('never watched');
          window.lfRemovedHolder = new WeakRef(gone);
          gone.parentElement.remove();
        }""")
        page.context.new_cdp_session(page).send("HeapProfiler.collectGarbage")
        assert page.evaluate(
            "() => [window.lfReadings, window.lfRemovedHolder.deref() === undefined]"
        ) == [1, True]


MOVED_PAGE = leaf_page(
    "Moved holders",
    '<h1>Holders</h1><p id="prose">A paragraph at the measure, long enough to fill '
    "the column it stands in from one edge to the other.</p>"
    '<div id="control" data-width="wide">Wide.</div>'
    '<div class="fixed" id="shift"><p>A holder of its own width.</p>'
    '<div id="shift-wide" data-width="wide">Wide.</div></div>'
    '<div class="inset gone" id="reveal"><p>A holder the page shows later.</p>'
    '<div id="reveal-wide" data-width="wide">Wide.</div></div>',
    head="<style>.fixed { width: 600px; } .fixed.moved { margin-left: 80px; }"
    " .inset { padding-left: 60px; } .gone { display: none; }</style>",
)


@pytest.mark.parametrize("how", ["shift", "reveal"])
def test_a_breakout_whose_block_moves_re_lands(browser, serve, how):
    """A block can move with nothing inserted, no attribute Leaf knows changed and its
    holder no wider or narrower: a class gives a holder of fixed width a margin, which
    carries its breakout 80px across, or stops hiding a holder, which draws a breakout
    never read before. Either breakout stands back on the prose axis, beside one in the
    page's flow, with every frame callback held, so neither the margin pass nor a
    resize read it."""
    page = open_page(browser, serve(MOVED_PAGE))
    resized(page, 1440, 900)
    margins_laid_out(page)
    off = """(how) => {
      const box = document.getElementById(`${how}-wide`).getBoundingClientRect();
      const control = document.getElementById('control').getBoundingClientRect();
      return Math.max(Math.abs(box.left - control.left),
        Math.abs(box.right - control.right));
    }"""
    with held_frames(page):
        moved = page.evaluate(
            f"""async (how) => {{
          // Frame callbacks are held, so after one rendering update and a task none the
          // runtime asked for before the change is left to run after it.
          await new Promise((resolve) => {{
            const observer = new ResizeObserver(() => {{
              observer.disconnect();
              setTimeout(resolve);
            }});
            observer.observe(document.body);
          }});
          const lf = document.documentElement.lfInitial;
          const read = lf.residency;
          window.lfPasses = 0;
          lf.residency = () => (window.lfPasses++, read());
          if (how === 'shift') document.getElementById('shift').classList.add('moved');
          else document.getElementById('reveal').classList.remove('gone');
          return ({off})(how);
        }}""",
            how,
        )
        assert moved >= 20, ("the change did not move the breakout", moved)
        page.wait_for_function(f"(how) => ({off})(how) < 1", arg=how, polling=50)
        assert page.evaluate("window.lfPasses") == 0


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
    """The banner stands over the head of the document and the shortcut bar over its foot, so
    the document leaves each of them room. Neither bar is on a sheet — the runtime's whole
    layer is withheld from print — and the room went to paper anyway: written as body's
    own padding it printed as a blank strip at each end, the banner's height over the
    first line and the shortcut bar's under the last.

    The reservations now belong to the document box whose chrome they make room for,
    rather than to the scroll container. The same CSS disappears with the chrome in
    print, so paper cannot inherit an empty screen-only strip.

    The screen half is read as room rather than as a covered last line, which is where a
    user would meet it, because the column's own bottom padding is taller than the line:
    nothing is covered either way today, so an assertion about the last block would pass
    with the reservation deleted. The room is what the runtime answers for; the column's
    padding is the theme's to change."""
    page = open_page(browser, serve(LONG_PAGE))
    room = page.evaluate(CHROME_ROOM)
    assert room["banner"] > 0 and room["line"] > 0, (
        f"neither bar is standing, so there is nothing here to reserve for: {room}"
    )
    assert abs(room["head"] - room["banner"]) <= 1, (
        f"the document starts {room['head']:.0f}px down, under a "
        f"{room['banner']:.0f}px banner"
    )
    assert room["foot"] >= room["line"] - 1, (
        f"the document ends {room['foot']:.0f}px short of its own end, under a "
        f"{room['line']:.0f}px shortcut bar"
    )

    # The covering toolbar is taller than the desktop row. A user can cross that
    # breakpoint by rotating or resizing an already-open page, so the flow reservation
    # follows the rendered banner in both directions rather than keeping its startup
    # measurement and either covering the document or leaving a blank strip.
    for width in (390, 900):
        resized(page, width, 844)
        room = page.evaluate(CHROME_ROOM)
        assert abs(room["head"] - room["banner"]) <= 1, (
            f"after resizing to {width}px, the document reserved {room['head']:.0f}px "
            f"for a {room['banner']:.0f}px banner"
        )

    page.emulate_media(media="print")
    printed = page.evaluate(CHROME_ROOM)
    assert printed["head"] <= 1 and printed["foot"] <= 1, (
        f"a sheet held {printed['head']:.0f}px over the first line and "
        f"{printed['foot']:.0f}px under the last, for chrome it does not print"
    )


def test_the_room_follows_a_margin_taken_after_the_handover(
    browser, serve, tmp_path, monkeypatch
):
    """A wide widget spends the room free beside the column, and whatever stands in a
    margin states the room it takes there (`--lf-taken-r`, layouts.css) at any moment at
    all. The widget here states it after upgrade has handed over, and the exhibit must
    still keep out of it — a room too wide is a board drawn under the thing standing
    beside it, and nothing would say so.

    The free room is the stylesheet's reading (`--lf-free-r`, off the shell's
    container), so it follows whatever a widget states, and no list of the ways a widget
    may behave stands between them.

    What holds the fixture to the case is that the statement waits on a request this
    test answers, and answers only once the page has said it is done: one landing any
    earlier would stand before the handover, and on a fast machine that is where an
    unheld one would land."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-callout", upgrade=True)
    (tmp_path / ".leaf" / "widgets" / "lf-callout.js").write_text(LATE_MARGIN_WIDGET)

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.add_init_script(AT_THE_HANDOVER)
    answered = []

    def answer_after_the_handover(route):
        # Both stamps, not the first alone: what makes a claim late is not the handover
        # by itself but everything the page finishes around it. The second stamp is the
        # replay the panel's first render waits on.
        wait_until_ready(page)
        answered.append(True)
        route.fulfill(status=204)

    page.route("**/margin-width", answer_after_the_handover)
    page.goto(serve(LATE_MARGIN_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf")))
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")

    at_stamp = page.evaluate("() => window.__handover")
    assert at_stamp["taken"] == "0px", (
        "the page must start with nothing standing in its margin, or the post-handover "
        f"case is never reached: {at_stamp}"
    )
    assert at_stamp["past"] > 1 - 160, (
        "the board stood clear of the room the widget goes on to take before it took "
        f"it, so the statement moves nothing: {at_stamp}"
    )
    page.wait_for_function(
        "() => { const f = ("
        + RAIL_FIT
        + ")(); return f.taken === '160px' && f.past <= 1; }"
    )

    assert answered == [True], (
        "the widget never asked, so its claim rode nothing this test controls and the "
        f"moment it landed was the machine's: {answered}"
    )
    fit = page.evaluate(RAIL_FIT)
    assert fit["taken"] == "160px", (
        f"the widget never took its margin, so nothing here is tested: {fit}"
    )
    assert fit["right"] < at_stamp["right"] - 1, (
        f"the board kept the room the widget took: before {at_stamp}, after {fit}"
    )
    assert fit["past"] <= 1, (
        f"the board stands {fit['past']:.0f}px into the 160px the widget took after the "
        f"handover: {fit['widget']:.0f}px of widget, before {at_stamp}, after {fit}"
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


def test_a_contents_map_and_right_rail_leave_the_middle_room(browser, serve):
    """A surface grows into both margins between the contents map at the shell's left
    edge and the rail at its right. A comment on it stands on it as a pin rather than
    taking its right growth, and the map rests as its spine, which states the room it
    takes, so the band between the spine and the prose is the surface's on the left."""
    source = RAIL_BAND_PAGE.replace(
        '<h1 id="t">Release</h1>',
        '<aside class="sidebar"><lf-toc id="rail-toc"></lf-toc></aside>'
        '<h1 id="t">Release</h1><h2 id="change">Change</h2>',
    )
    page = open_page(browser, serve(source))
    resized(page, 1726, 900)
    margins_laid_out(page)
    at = page.evaluate(RAIL_BANDS)
    plan = at["plan"]
    toc = page.locator("#rail-toc").bounding_box()
    assert toc is not None
    taken = page.evaluate(
        """() => {
          const probe = document.createElement('i');
          probe.style.cssText = 'position:fixed;visibility:hidden;width:var(--lf-taken-l)';
          document.querySelector('main').append(probe);
          const width = probe.getBoundingClientRect().width;
          probe.remove();
          return width;
        }"""
    )
    assert plan["right"] > at["column"]["right"] + 1, at
    assert taken > 0 and toc["x"] + taken <= plan["left"], (taken, toc, plan)
    assert plan["left"] < at["column"]["left"] - 100, at
    card = next(r for r in at["rows"] if r["for"] == "sug-card")
    assert card["place"] == "pin" and card["right"] <= plan["right"] + 1, at
    assert all(r["pressable"] for r in at["rows"]), at
    assert root_overflow(page) == 0


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
    resized(page, 850, 900)
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
            const node = [...el.querySelectorAll('g.node')]
                .map((n) => n.getBoundingClientRect())
                .find((n) => n.left < x && n.right > x);
            return node && { x: r.left, y: r.top, width: r.width,
                             height: node.bottom - r.top, row: node.top + 3 - r.top };
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
        const node = el.querySelectorAll('g.node')[1].getBoundingClientRect();
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
    declared wide — so marked as one it would lay itself out to a 1080px page inside a
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
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    panel_settled(page)
    expect(page.locator("#fallback-flow svg")).to_be_visible()

    fit = page.evaluate("""() => {
        const el = document.getElementById('fallback-flow');
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
            '<section id="rp-room" data-width="wide"><p>Wide on a page.</p></section>',
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    panel_settled(page)
    expect(page.locator("#rp-quoted")).to_be_visible()

    marks = page.evaluate("""() => Object.fromEntries(
        [['sample', '#rp-quoted'], ['gloss', '#rp-quoted lf-gloss'], ['log', '#rp-log'],
         ['room', '#rp-room']].map(([name, selector]) => {
            const el = document.querySelector(selector);
            return [name, Object.fromEntries(
                ['data-lf-exhibit', 'data-lf-inline', 'data-lf-bound', 'data-lf-space']
                    .filter(attr => el.hasAttribute(attr))
                    .map(attr => [attr, el.getAttribute(attr)]))];
        }))""")
    assert marks == {
        "sample": {"data-lf-exhibit": ""},
        "gloss": {"data-lf-inline": ""},
        "log": {"data-lf-bound": "end"},
        "room": {},
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
    source = FRAMED_WIDE_PAGE.replace(
        '<h1 id="t">Framed</h1>',
        '<aside class="sidebar"><lf-toc id="frame-toc"></lf-toc></aside>'
        '<h1 id="t">Framed</h1>',
    )
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
        return { column: b.right - parseFloat(s.paddingRight)
                         - b.left - parseFloat(s.paddingLeft),
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
    """A sidenote claims nothing from the column: it hangs in the room beside it where
    the room either side of the column, together, holds the note's 384px, the column
    moving left by what the right side lacks, and stands in the flow as a small indented
    block where it doesn't. Where centring already leaves it the room, the column keeps
    the page's axis.

    Every reading is against the page's box rather than the window, the two being the
    same width only where a scrollbar takes no room."""
    source = NOTE_AND_WIDE_PAGE.replace("<html", f'<html dir="{direction}"', 1)
    page = open_page(browser, serve(source))
    for width, hangs, centred in (
        (1100, False, True),
        (1190, True, False),
        (1600, True, True),
    ):
        resized(page, width, 900)
        at = page.evaluate(ROOM_GEOMETRY)
        axis = at["pageBox"]["left"] + at["pageBox"]["width"] / 2
        assert (abs(at["column"]["centre"] - axis) <= 1) == centred, (
            f"at {width}px the column is centred at {at['column']['centre']:.0f}px of a "
            f"{at['pageBox']['width']:.0f}px page"
        )
        float_ = page.evaluate(
            "() => getComputedStyle(document.getElementById('note')).float"
        )
        assert float_ == ("right" if hangs else "none"), (width, float_)
        note = at["note"]
        assert note["width"] > 0, "the note must still stand on the page"
        if hangs:
            assert note["left"] >= at["column"]["right"] + 23, (width, at)
            assert note["right"] <= at["pageBox"]["right"], (
                f"the note is off the right edge of a {at['pageBox']['width']:.0f}px "
                f"page: {note['right']:.0f}px"
            )
        else:
            assert note["right"] <= at["column"]["right"] + 1, (width, at)
        assert root_overflow(page) == 0


def test_a_note_the_page_does_not_show_takes_no_room(browser, serve):
    """A note inside a closed disclosure is not on screen, so it needs no room beside
    the column and the column stays centred; opening the disclosure brings it into the
    margin, and closing it gives the room back."""
    source = leaf_page(
        "a note in a disclosure",
        """
<h1>Migration plan</h1>
<details id="more"><summary>Why twice a month</summary>
<aside class="sidenote" id="frequency">Support runs this twice a month.</aside>
<p>The cadence follows the support rota.</p>
</details>
<p>Shift one cohort at a time while keeping the old readers available.</p>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1200, 800)
    main = page.locator("main")
    expect(main).to_have_attribute("data-lf-margin", "rail")
    centred = main.evaluate("node => node.getBoundingClientRect().left")
    page.locator("#more > summary").click()
    expect(main).to_have_attribute("data-lf-margin", "rail note")
    expect(page.locator("#frequency")).to_have_css("float", "right")
    page.locator("#more > summary").click()
    expect(main).to_have_attribute("data-lf-margin", "rail")
    expect(page.locator("body")).not_to_have_attribute(
        "style", re.compile("--lf-column-shift")
    )
    assert main.evaluate("node => node.getBoundingClientRect().left") == centred


def test_a_sidebar_pages_track_is_its_aside_in_the_order_it_is_written(browser, serve):
    """A sidebar page's track is its `aside`, wherever it is written. One written before
    the body stands on the left and, stacked on a phone, comes first; one written after
    it stands on the right and comes last. Source order is the reading order at every
    width, so a summary a reader needs first never lands below the whole body."""
    body = "<div id='body'>" + "<p>Body paragraph. " * 40 + "</p></div>"
    track = "<aside id='track'><p>Summary and contents.</p></aside>"
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


@pytest.mark.parametrize("rail", [True, False])
def test_authored_residency_runs_without_annotation_geometry(browser, serve, rail):
    """Content residency imports inertly and admits authored residents independently
    of annotation selection. Its one document listener owns disclosure changes; RTL
    and a removed main still complete a reading without a second layout authority."""
    page = open_page(
        browser, serve(leaf_page("content owner", "<h1>Content owner</h1>"))
    )
    asset = page.evaluate("""new URL('runtime/content-layout.js', new URL(
      document.querySelector('script[data-lf-entry]').dataset.lfEntry, location)).href""")
    fixture = page.evaluate("new URL('content-owner-proof', location).href")
    page.route(
        fixture,
        lambda route: route.fulfill(
            content_type="text/html",
            body="""<!doctype html><html><head><style>
body { margin: 0 }
main { width: 720px; margin: auto; position: relative;
 --rail: 100px; --sidebar: 150px; --note: 80px }
aside { --lf-resident: sidebar }
aside.note { --lf-resident: note; display: none }
</style></head><body data-annotations="ANNOTATION_MODE"><main><h1>Neutral authored layout</h1>
<aside>Sidebar</aside><aside class="note">Hidden until resident note</aside>
<details><summary>More</summary><aside class="note">Disclosed note</aside></details>
</main></body></html>""".replace("ANNOTATION_MODE", "overlay" if rail else "page"),
        ),
    )
    page.set_viewport_size({"width": 950, "height": 800})
    loaded = []
    page.on("request", lambda request: loaded.append(request.url))
    page.goto(fixture)
    # Runtime modules read the storage and initial-drawing services installed by
    # the classic prepaint script before their module graph is imported.
    page.add_script_tag(url=asset.replace("content-layout.js", "prepaint.js"))
    reading = page.evaluate(
        """async ({asset, rail}) => {
      const owner = await import(asset);
      window.residency = owner; window.completed = [];
      owner.scheduleResidency();
      await new Promise(requestAnimationFrame);
      const main = document.querySelector('main');
      const inert = !owner.residencyStarted();
      owner.openResidency({onRead: changed => window.completed.push(changed)});
      return {inert, tokens: main.getAttribute('data-lf-margin'),
              shift: document.body.style.getPropertyValue('--lf-column-shift')};
    }""",
        {"asset": asset, "rail": rail},
    )
    expected = {
        "inert": True,
        "tokens": "rail note" if rail else "note",
        "shift": "",
    }
    assert reading == expected
    page.evaluate("document.documentElement.dir='rtl'; residency.scheduleResidency()")
    page.wait_for_function("completed.length >= 2")
    assert (
        page.locator("body").evaluate(
            "node => node.style.getPropertyValue('--lf-column-shift')"
        )
        == expected["shift"]
    )
    page.evaluate("document.querySelector('details').open = true")
    page.wait_for_function("completed.length >= 3")
    expect(page.locator("main")).to_have_attribute("data-lf-margin", expected["tokens"])
    page.evaluate(
        "document.querySelector('main').remove(); residency.scheduleResidency()"
    )
    page.wait_for_function("completed.length >= 4")
    assert page.evaluate("completed.at(-1)") is False
    assert not [
        url
        for url in loaded
        if any(
            name in url
            for name in (
                "margin-layout",
                "margin-projection",
                "annotation-layer",
                "page-map-dialog",
            )
        )
    ]


def test_margin_residents_stand_where_the_room_beside_the_column_holds_them(
    browser, serve
):
    """One measurement admits the margin's residents in order: the rail where the room
    right of the centred column holds it, then the sidebar, then the note, each where the
    room on both sides together holds what those admitted need on each side. The column
    moves over by what one side lacks, so a sidebar stands from the column box plus the
    rail and its own width, and a note beside it from the box plus both widths. Neither
    takes from the column: it keeps its measure at every width, and each resident stands
    inside the window.

    The second sidebar is the other composition case: only the first direct child of
    main may take the sticky page-level slot, so an accidental second one remains in
    flow rather than covering the first after a scroll."""
    source = leaf_page(
        "margin residents",
        """
<h1>Migration plan</h1>
<aside class="sidebar" id="route"><nav aria-label="Route"><a href="#move">Move</a></nav></aside>
<aside class="sidebar" id="extra">Secondary reference</aside>
<aside class="sidenote" id="frequency">Support runs this twice a month.</aside>
<h2 id="move">Move</h2>
<p>Shift one cohort at a time while keeping the old readers available.</p>
<div style="height: 1500px"></div>
""",
    )
    url = serve(with_one_ask(source))

    reading = """() => {
      const main = document.querySelector('main'), ms = getComputedStyle(main);
      const mb = main.getBoundingClientRect();
      const length = (name) => {
        const probe = document.createElement('i');
        probe.style.cssText = `position:fixed;visibility:hidden;height:0;padding:0;border:0;width:var(${name})`;
        main.append(probe);
        const width = probe.getBoundingClientRect().width;
        probe.remove();
        return width;
      };
      const box = (node) => {
        const s = getComputedStyle(node), b = node.getBoundingClientRect();
        return {float: s.float, position: s.position, left: b.left, right: b.right};
      };
      return {
        sidebars: [...document.querySelectorAll('aside.sidebar')].map(box),
        note: box(document.querySelector('aside.sidenote')),
        column: {
          left: mb.left + parseFloat(ms.paddingLeft),
          right: mb.right - parseFloat(ms.paddingRight),
          width: mb.width - parseFloat(ms.paddingLeft) - parseFloat(ms.paddingRight),
          box: mb.width,
        },
        taken: length('--lf-taken-l, 0px'),
        needs: {rail: length('--rail'), sidebar: length('--sidebar'),
                note: length('--note')},
        shell: document.body.clientWidth,
      };
    }"""

    page = open_page(browser, url)
    at = page.evaluate(reading)
    box, needs = at["column"]["box"], at["needs"]
    sidebar_from = round(box + needs["rail"] + needs["sidebar"])
    note_from = round(box + needs["sidebar"] + needs["note"])
    for width, standing in (
        (sidebar_from - 1, "rail"),
        (sidebar_from, "rail sidebar"),
        (note_from - 1, "rail sidebar"),
        (note_from, "rail sidebar note"),
    ):
        resized(page, width, 800)
        expect(page.locator("main")).to_have_attribute("data-lf-margin", standing)
        at = page.evaluate(reading)
        assert at["column"]["width"] == 720, (width, at)
        assert root_overflow(page) == 0, (width, at)
        first, second = at["sidebars"]
        assert (second["float"], second["position"]) == ("none", "static"), (width, at)
        if "sidebar" in standing:
            assert (first["float"], first["position"]) == ("left", "sticky"), (
                width,
                at,
            )
            # Sticky, the sidebar can stand level with any band, so it takes its side.
            assert at["taken"] > 0, (width, at)
            assert first["left"] >= 0, (width, at)
            assert first["right"] <= at["column"]["left"] - 23, (width, at)
        else:
            assert (first["float"], first["position"]) == ("none", "static"), (
                width,
                at,
            )
            centre = (at["column"]["left"] + at["column"]["right"]) / 2
            assert abs(centre - at["shell"] / 2) <= 1, (width, at)
        if "note" in standing:
            assert at["note"]["float"] == "right", (width, at)
            assert at["note"]["left"] >= at["column"]["right"] + 23, (width, at)
            assert at["note"]["right"] <= at["shell"], (width, at)
        else:
            assert at["note"]["float"] == "none", (width, at)

    # The Questions panel stands over the page and grants or withdraws no margin.
    toggle_queue(page)
    panelled = page.evaluate(reading)
    assert panelled["sidebars"] == at["sidebars"]
    assert panelled["taken"] == at["taken"]
    assert panelled["column"] == at["column"]


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
    expect(page.locator(".lf-banner")).to_be_visible()
    # The poll is the page's own fetch, relative and query-less: it answers only if the
    # cookie rode along.
    assert page.evaluate("() => fetch('/api/state').then(r => r.status)") == 200

    page.reload()
    wait_until_ready(page)
    expect(page).to_have_url(bare)
    expect(page.locator(".lf-banner")).to_be_visible()


def test_a_page_refuses_a_browser_that_never_had_the_link(browser, serve):
    url = serve(INLINE_PAGE)

    page = browser.new_page()
    page.goto(url.rsplit("?", 1)[0], wait_until="load")

    assert schema_model.NO_KEY in page.locator("body").inner_text()
    # The refusal is the subject: a user without the key is answered 401.
    consume_browser_errors(page, "401")


@pytest.mark.parametrize(
    "authored_css", ["", "main.layout-column { max-width: 600px; --note: 260px; }"]
)
def test_margin_residents_keep_their_first_painted_posture(
    browser, serve, authored_css
):
    """Delaying modules must not first paint notes inline and shift the reading axis."""
    source = leaf_page(
        "First-painted notes",
        '<h1 id="title">Migration</h1>'
        '<aside class="sidenote" id="note">Keep old readers until checks pass.</aside>'
        '<p id="passage">Advance one cohort at a time while keeping earlier readers available.</p>',
    )
    source = source.replace("</head>", f"<style>{authored_css}</style></head>")
    source = source.replace("<body", '<body style="--authored: initial"', 1)
    held = []
    controlled = primed(
        browser, lambda page: page.route("**/leaf.js", lambda route: held.append(route))
    )
    page = controlled.new_page(viewport={"width": 1440, "height": 900})
    # This boundary deliberately precedes the module-owned banner/readiness stamp.
    page.goto(live_url(serve(source)), wait_until="commit")
    expect(page.locator("#note")).to_have_css("float", "right")
    page.wait_for_function(
        "performance.getEntriesByType('paint').some(p => p.name === 'first-contentful-paint')"
    )
    before = page.locator("#passage").bounding_box()
    assert held
    assert not page.locator("body").get_attribute("data-lf-presented")
    for route in held:
        route.continue_()
    page.unroute("**/leaf.js")
    wait_until_ready(page)
    assert page.locator("#passage").bounding_box() == before
    initial_shift = page.evaluate(
        "document.body.style.getPropertyValue('--lf-column-shift')"
    )
    assert page.evaluate("""() => {
      const source = document.documentElement.lfInitial.authoredCopy(document.querySelector('main'));
      return [source.getAttribute('style'), source.getAttribute('data-lf-margin')];
    }""") == [None, None]
    assert page.evaluate("""() => {
      const source = document.documentElement.lfInitial.authoredShell(document.body);
      return [source.getAttribute('style'), source.hasAttribute('data-lf-column-shell')];
    }""") == ["--authored: initial", False]
    page.evaluate("window.originalPassage = document.querySelector('#passage')")
    stamp_page(
        serve.page_dir,
        source.replace("Advance one cohort", "Advance two cohorts"),
        "next cohort",
    )
    wait_for_revision(page, 2)
    expect(page.locator("#passage")).to_contain_text("Advance two cohorts")
    assert page.evaluate("originalPassage === document.querySelector('#passage')")
    for revision, resident in ((3, False), (4, True)):
        next_source = source.replace(
            "--authored: initial", f"--authored: revision{revision}"
        )
        if not resident:
            next_source = next_source.replace('class="sidenote"', 'class="ordinary"')
        stamp_page(serve.page_dir, next_source, f"resident {resident}")
        wait_for_revision(page, revision)
        expect(page.locator("#note")).to_have_css(
            "float", "right" if resident else "none"
        )
        assert (
            page.evaluate("document.body.style.getPropertyValue('--authored')")
            == f"revision{revision}"
        )
        assert page.evaluate(
            "document.body.style.getPropertyValue('--lf-column-shift')"
        ) == (initial_shift if resident else "")
    assert page.evaluate("""async () => {
      const {runtimeRootState} = await window.__lfRuntimeImport('/runtime/root-state.js');
      return runtimeRootState(document.body).attributes.has('data-lf-column-shell');
    }""")
    for revision, layout in ((5, "sidebar"), (6, "column")):
        next_source = source.replace(
            "--authored: initial", f"--authored: revision{revision}"
        )
        next_source = next_source.replace("layout-column", f"layout-{layout}")
        stamp_page(serve.page_dir, next_source, f"shell {layout}")
        wait_for_revision(page, revision)
        expect(page.locator("body")).to_have_css(
            "display", "grid" if layout == "column" else "block"
        )
        assert page.locator("body").get_attribute("data-lf-column-shell") == (
            "" if layout == "column" else None
        )
        assert (
            page.evaluate("document.body.style.getPropertyValue('--authored')")
            == f"revision{revision}"
        )
        assert page.evaluate(
            "document.body.style.getPropertyValue('--lf-column-shift')"
        ) == (initial_shift if layout == "column" else "")
    # Authored pages require one direct main. Its temporary absence while replacing
    # nodes must still withdraw the old shell before any missing-column early return.
    page.evaluate("""() => {
      window.column = document.querySelector('main');
      column.remove();
      document.documentElement.lfInitial.residency();
    }""")
    expect(page.locator("body")).to_have_css("display", "block")
    assert page.locator("body").get_attribute("data-lf-column-shell") is None
    assert (
        page.evaluate("document.body.style.getPropertyValue('--lf-column-shift')") == ""
    )
    page.evaluate("""() => {
      document.body.append(column);
      document.documentElement.lfInitial.residency();
    }""")
    expect(page.locator("body")).to_have_css("display", "grid")
    expect(page.locator("#note")).to_have_css("float", "right")
    assert (
        page.evaluate("document.body.style.getPropertyValue('--lf-column-shift')")
        == initial_shift
    )


@pytest.mark.parametrize(
    "notes,local_region",
    [(True, None), (False, None), (True, "bounded"), (True, "flow")],
)
def test_document_reading_survives_width_reflow(browser, serve, notes, local_region):
    """The implicit document keeps its passage as notes enter flow, just as panes do."""
    body = '<h1 id="title">Migration</h1><a href="#passage3">Read phase 3</a>'
    for number in range(1, 9):
        note = (
            f'<aside class="sidenote" id="note{number}">Qualification {number}. '
            "Keep the old readers until the new cohort passes its checks.</aside>"
            if notes
            else ""
        )
        body += (
            f'<h2 id="heading{number}">Phase {number}</h2>{note}'
            f'<p id="passage{number}">Phase {number} begins here. Advance one cohort at a time '
            "and keep earlier readers available. The qualification explains this phase.</p>"
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
    page = open_page(browser, serve(leaf_page("Reading through reflow", body)))
    if local_region:
        page.evaluate("""async () => {
          const {registerReadingRegion} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const body = document.querySelector('#local-region');
          registerReadingRegion({id: body.id, host: body, body});
        }""")
    resized(page, 1440, 900)
    page.get_by_role("link", name="Read phase 3", exact=True).click()
    page.keyboard.press("Escape")
    page.mouse.wheel(0, 160)
    scroll_settled(page)
    reading = """async () => {
      const entry = new URL(document.querySelector('script[data-lf-entry]').dataset.lfEntry, location);
      const {capturePlace} = await import(new URL('runtime/reading-place.js', entry));
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


@pytest.mark.parametrize("display", ["block", "flex"])
def test_an_authored_shell_admits_only_margin_room_it_can_supply(
    browser, serve, display
):
    source = leaf_page(
        "Authored shell",
        '<h1>Migration</h1><aside class="sidenote" id="note">Keep earlier readers.</aside>'
        '<p id="passage">Advance one cohort at a time.</p>',
    ).replace(
        "</head>",
        f"<style>body {{ display: {display}; flex-direction: column; }}"
        "main { position: relative; left: 60px; }</style></head>",
    )
    page = open_page(browser, serve(source))
    for width, hanging in ((1600, False), (1800, True), (1440, False)):
        resized(page, width, 900)
        expect(page.locator("#note")).to_have_css(
            "float", "right" if hanging else "none"
        )
        main = page.locator("main").bounding_box()
        assert main["x"] == pytest.approx((width - main["width"]) / 2 + 60, abs=1)
        assert root_overflow(page) == 0


@pytest.mark.parametrize("tracks", ["1fr 1fr", "0px 1fr 0px"])
def test_margin_residency_verifies_authored_tracks_and_retries_changed_css(
    browser, serve, tracks
):
    source = leaf_page(
        "Authored tracks",
        '<h1>Migration</h1><aside class="sidenote" id="note">Keep earlier readers.</aside>'
        "<p>Advance one cohort at a time.</p>",
    ).replace(
        "</head>",
        f'<style id="author-grid">body {{ grid-template-columns: {tracks}; }}</style></head>',
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    expect(page.locator("#note")).to_have_css("float", "none")
    assert root_overflow(page) == 0
    for active in (True, False, True, False):
        page.evaluate(
            """active => {
          const sheet = document.querySelector('#author-grid').sheet;
          sheet.disabled = active;
          document.documentElement.lfInitial.residency();
        }""",
            active,
        )
        expect(page.locator("#note")).to_have_css(
            "float", "right" if active else "none"
        )
        assert root_overflow(page) == 0
    assert page.evaluate("""async () => {
      let writes = 0;
      const observer = new MutationObserver(records => writes += records.length);
      observer.observe(document.body, {attributes: true, attributeFilter: ['style']});
      const owner = document.documentElement.lfInitial;
      const changed = owner.residency().changed || owner.residency().changed;
      await new Promise(requestAnimationFrame);
      observer.disconnect();
      return {changed, writes};
    }""") == {"changed": False, "writes": 0}


@pytest.mark.parametrize("bad_write", ["restatement", "other-cycle", "priority-cycle"])
def test_the_write_gate_allows_only_the_column_measurement_property(
    browser, serve, bad_write
):
    source = leaf_page("Style gate", "<h1>Migration</h1>").replace(
        "<body", '<body style="--probe-stable: 1;"', 1
    )
    page = open_page(browser, serve(source))
    page.evaluate("""() => {
      document.body.style.setProperty('--lf-column-shift', '1px');
      document.body.style.removeProperty('--lf-column-shift');
    }""")
    assert take_browser_errors(page) == []
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
    failures = consume_browser_errors(page, "unchanged write:")
    assert len(failures) == 1
    assert "style on body" in failures[0]


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
