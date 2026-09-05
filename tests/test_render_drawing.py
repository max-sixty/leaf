"""One-stroke drawing-comment browser journeys."""

import base64
import re

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    BOTH_STAMPS,
    CONVERSATION_DIFF_PAGE,
    EXAMPLE_MEDIA,
    FEATURE_GALLERY,
    TARGETS_PAGE,
    live_url,
    open_page,
    panel_settled,
    sending,
    told,
)

pytestmark = pytest.mark.nightly


def draw_over(
    page,
    locator,
    *,
    steps=8,
    points=((0.22, 0.62), (0.5, 0.25), (0.78, 0.62)),
):
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    start, middle, end = [
        (box["x"] + box["width"] * x, box["y"] + box["height"] * y) for x, y in points
    ]
    page.mouse.move(*start)
    page.keyboard.press("w")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-drawing\b"))
    assert locator.evaluate("el => getComputedStyle(el).cursor") == "crosshair"
    expect(page.locator(".lf-aim")).to_be_hidden()
    page.mouse.down()
    page.mouse.move(*middle, steps=steps)
    page.mouse.move(*end, steps=steps)
    page.mouse.up()


def mark_relation(mark, target):
    drawn = mark.bounding_box()
    anchored = target.bounding_box()
    return (
        drawn["x"] - anchored["x"],
        drawn["y"] - anchored["y"],
        drawn["width"],
        drawn["height"],
    )


def test_a_drawing_is_sent_and_replayed_as_an_ordinary_comment(browser, serve):
    """One pointer stroke starts on one semantic anchor, crosses the page beyond it,
    and the accepted comment keeps its context in the page instead of duplicating it."""
    url = serve(FEATURE_GALLERY)
    page, errors = open_page(browser, url)
    target = page.locator("#bg-choice-trail")
    target.evaluate("el => { el.style.position = 'relative'; el.style.zIndex = '1'; }")
    scroll_width = page.evaluate("document.documentElement.scrollWidth")

    draw_over(
        page,
        target,
        steps=300,
        points=((0.22, 0.62), (0.75, -1), (1.7, 1.8)),
    )

    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-drawing\b"))
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    expect(target).not_to_have_class(re.compile(r"\blf-mark-el\b|\blf-pending\b"))
    assert target.get_attribute("chosen") is None
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    field.fill("This bend is the part I mean.")
    with sending(page, "the drawing comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert event["anchor"] == {"section": "bg-choice-trail"}
    assert event["text"] == "This bend is the part I mean."
    drawing = event["drawing"]
    assert drawing["format"] == "leaf-drawing/1"
    assert 2 <= len(drawing["points"]) <= 256
    target_box = target.bounding_box()
    xs, ys = zip(*drawing["points"], strict=True)
    assert min(xs) / target_box["width"] == pytest.approx(0.22, abs=0.02)
    assert min(ys) / target_box["height"] == pytest.approx(-1, abs=0.02)
    assert max(xs) - min(xs) > target_box["width"]
    assert max(ys) - min(ys) > target_box["height"]
    assert all(
        -100000 <= coordinate <= 100000
        for point in drawing["points"]
        for coordinate in point
    )
    assert drawing["points"][-1][0] / target_box["width"] == pytest.approx(
        1.7, abs=0.02
    )
    assert drawing["points"][-1][1] / target_box["height"] == pytest.approx(
        1.8, abs=0.02
    )

    mark = page.locator(f'.lf-drawing-posted[data-thread="{event["id"]}"]')
    expect(mark).to_have_count(1)
    mark_box = mark.bounding_box()
    assert mark_box["x"] + mark_box["width"] > target_box["x"] + target_box["width"]
    assert mark_box["y"] < target_box["y"]
    assert page.evaluate("document.documentElement.scrollWidth") == scroll_width
    page.wait_for_timeout(100)
    stacking = page.locator(".lf-drawings").evaluate(
        "el => ({classes: el.getAttribute('class'), z: getComputedStyle(el).zIndex})"
    )
    assert stacking["z"] == "8890", stacking
    stable_mark = mark.element_handle()
    page.wait_for_timeout(100)
    assert stable_mark.evaluate("node => node.isConnected"), (
        "an idle drawing must not sustain a ResizeObserver repaint loop"
    )
    relation = mark_relation(mark, target)
    page.evaluate("scrollBy(0, 100)")
    page.wait_for_timeout(100)
    assert mark_relation(mark, target) == pytest.approx(relation, abs=0.02)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert mark_relation(mark, target) == pytest.approx(relation, abs=0.02)
    expect(target).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(page.locator(".lf-panel .lf-drawing-preview")).to_have_count(0)
    expect(page.locator(".lf-panel .lf-drawing-reference")).to_have_text(
        "Drawing comment"
    )

    returned, returned_errors = open_page(browser, url)
    replayed = returned.locator(f'.lf-drawing-posted[data-thread="{event["id"]}"]')
    expect(replayed).to_have_count(1)
    assert mark_relation(
        replayed, returned.locator("#bg-choice-trail")
    ) == pytest.approx(relation, abs=0.02)
    assert errors == []
    assert returned_errors == []
    page.close()
    returned.close()


def test_a_drawing_can_begin_on_page_whitespace(browser, serve):
    """Whitespace is part of the drawable page plane. With no semantic item under the
    starting point, the stroke opens a page comment and keeps document coordinates."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.evaluate("document.body.style.minHeight = '180000px'")
    page.evaluate("scrollTo(0, 120000)")
    point = page.evaluate(
        """() => {
          const x = innerWidth - 16;
          const y = Math.min(innerHeight - 80, 420);
          const hit = document.elementFromPoint(x, y);
          return {
            x, y,
            tag: hit?.tagName ?? "",
            chrome: Boolean(hit?.closest(".lf-chrome")),
            item: hit?.closest("main > *")?.id ?? "",
            scrollY,
          };
        }"""
    )
    assert point["tag"] in {"HTML", "BODY", "MAIN"}, point
    assert not point["chrome"] and not point["item"], point
    scroll_width = page.evaluate("document.documentElement.scrollWidth")

    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    assert (
        page.evaluate(
            "([x, y]) => getComputedStyle(document.elementFromPoint(x, y)).cursor",
            [point["x"], point["y"]],
        )
        == "crosshair"
    )
    expect(page.locator(".lf-aim")).to_be_hidden()
    page.mouse.down()
    page.mouse.move(point["x"] - 90, point["y"] - 55, steps=8)
    page.mouse.move(point["x"] - 150, point["y"] + 35, steps=8)
    page.mouse.up()

    page.wait_for_timeout(100)
    assert page.locator(".lf-drawing-pending").count() == 1, {
        "announcement": page.locator(".lf-live").text_content(),
        "body_class": page.locator("body").get_attribute("class"),
        "composer": page.locator(".lf-general textarea").is_visible(),
    }
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-general .primary")).to_have_attribute(
        "aria-disabled", "false"
    )

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    page.evaluate("document.body.style.minHeight = '180000px'")
    page.evaluate("y => scrollTo(0, y)", point["scrollY"])
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    field = page.locator(".lf-general textarea")
    expect(field).to_have_value("")
    field.focus()
    with sending(page, "the page drawing"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert "anchor" not in event and "text" not in event
    assert event["drawing"]["points"][0] == pytest.approx(
        [point["x"], point["y"] + point["scrollY"]], abs=0.1
    )
    mark = page.locator(f'.lf-drawing-posted[data-thread="{event["id"]}"]')
    expect(mark).to_have_count(1)
    page.wait_for_function(
        "selector => document.querySelector(selector)?.getBoundingClientRect().x > 0",
        arg=f'.lf-drawing-posted[data-thread="{event["id"]}"]',
    )
    reading = """el => {
      const box = el.getBoundingClientRect();
      return {x: box.x, y: box.y, scrollY};
    }"""
    before = mark.evaluate(reading)
    page.evaluate("scrollBy(0, 100)")
    page.wait_for_timeout(100)
    expect(mark).to_have_count(1)
    after = mark.evaluate(reading)
    assert after["x"] == pytest.approx(before["x"], abs=0.02)
    assert after["y"] == pytest.approx(
        before["y"] - (after["scrollY"] - before["scrollY"]), abs=0.02
    )
    assert page.evaluate("document.documentElement.scrollWidth") == scroll_width
    assert errors == []
    page.close()


def test_a_page_drawing_keeps_pasted_media_already_in_the_general_draft(browser, serve):
    """Adding a page drawing preserves the complete compound draft, including image
    Markdown projected out of the textarea as a thumbnail."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    field = page.locator(".lf-general textarea")
    pixels = (EXAMPLE_MEDIA / "051bee487bfb5d13.png").read_bytes()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        field.evaluate(
            """(textarea, encoded) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              transfer.items.add(new File([bytes], 'drawing.png', {type: 'image/png'}));
              textarea.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: transfer,
              }));
            }""",
            base64.b64encode(pixels).decode(),
        )
    expect(page.locator(".lf-general .lf-composer-media img")).to_be_visible()
    page.get_by_role("button", name="Close threads").click()

    page.evaluate("document.body.style.minHeight = '180000px'")
    page.evaluate("scrollTo(0, 120000)")
    point = page.evaluate(
        """() => {
          const x = innerWidth - 16;
          const y = Math.min(innerHeight - 80, 420);
          return {x, y};
        }"""
    )
    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    page.mouse.down()
    page.mouse.move(point["x"] - 90, point["y"] - 55, steps=8)
    page.mouse.up()

    expect(field).to_be_focused()
    expect(field).to_have_value("")
    expect(page.locator(".lf-general .lf-composer-media img")).to_be_visible()
    with sending(page, "the drawing and image comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["text"] == "![Pasted image](/media/051bee487bfb5d13.png)"
    assert event["drawing"]["format"] == "leaf-drawing/1"
    assert errors == []
    page.close()


def test_a_page_drawing_draft_repaints_in_another_tab(browser, serve, one_reader):
    """The drawing payload follows the general draft's cross-tab notification rather
    than waiting for a reload or an unrelated state poll to repaint."""
    url = serve(TARGETS_PAGE)
    local, local_errors = open_page(browser, url, context=one_reader)
    remote, remote_errors = open_page(browser, url, context=one_reader)
    local.evaluate("document.body.style.minHeight = '180000px'")
    local.evaluate("scrollTo(0, 120000)")
    point = local.evaluate(
        """() => ({
          x: innerWidth - 16,
          y: Math.min(innerHeight - 80, 420),
        })"""
    )
    local.mouse.move(point["x"], point["y"])
    local.keyboard.press("w")
    local.mouse.down()
    local.mouse.move(point["x"] - 100, point["y"] - 40, steps=8)
    local.mouse.up()

    expect(remote.locator(".lf-drawing-pending")).to_have_count(1)
    remote.locator(".lf-threads-toggle").click()
    panel_settled(remote)
    expect(remote.locator(".lf-general .primary")).to_have_attribute(
        "aria-disabled", "false"
    )
    assert local_errors == []
    assert remote_errors == []
    local.close()
    remote.close()


def test_an_anchored_drawing_draft_repaints_in_another_tab(browser, serve, one_reader):
    """The anchored composer's draft watcher repaints its stroke as well as its target
    when another tab adds drawing geometry to the shared draft."""
    url = serve(TARGETS_PAGE)
    local, local_errors = open_page(browser, url, context=one_reader)
    remote, remote_errors = open_page(browser, url, context=one_reader)
    draw_over(remote, remote.locator("#prose"))
    remote_path = remote.locator(".lf-drawing-pending path")
    before = remote_path.get_attribute("d")

    draw_over(
        local,
        local.locator("#prose"),
        points=((0.15, 0.2), (0.45, 0.8), (0.85, 0.2)),
    )

    expect(remote.locator(".lf-drawing-pending")).to_have_count(1)
    remote.wait_for_function(
        "before => document.querySelector('.lf-drawing-pending path')"
        "?.getAttribute('d') !== before",
        arg=before,
    )
    assert remote_path.get_attribute("d") == local.locator(
        ".lf-drawing-pending path"
    ).get_attribute("d")
    assert local_errors == []
    assert remote_errors == []
    local.close()
    remote.close()


def test_page_and_anchored_drawing_drafts_keep_their_own_ink(browser, serve):
    """The general and anchored composers are independent durable draft contexts, so
    a new anchored stroke must not visually replace a standing page stroke."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.evaluate("document.body.style.minHeight = '180000px'")
    page.evaluate("scrollTo(0, 120000)")
    point = page.evaluate(
        """() => ({x: innerWidth - 16, y: Math.min(innerHeight - 80, 420)})"""
    )
    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    page.mouse.down()
    page.mouse.move(point["x"] - 100, point["y"] - 40, steps=8)
    page.mouse.up()
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    page.get_by_role("button", name="Close threads").click()

    draw_over(page, page.locator("#prose"))

    expect(page.locator(".lf-drawing-pending")).to_have_count(2)
    page.locator(".lf-fab-input").fill("The anchored draft.")
    with sending(page, "the anchored drawing beside the page draft"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "prose"}
    expect(page.locator(".lf-drawing-posted")).to_have_count(1)
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_margin_start_uses_the_item_alongside_it_as_context(browser, serve):
    """Starting beside content keeps that horizontal item's semantic anchor, so opening
    its composer or reflowing the page cannot separate the ink from what it marks."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    target = page.locator("#prose")
    box = target.bounding_box()
    page.evaluate(
        """y => {
          const hidden = document.createElement('p');
          hidden.id = 'hidden-draw-target';
          hidden.dataset.lfProjection = 'prose';
          hidden.dataset.lfDatum = 'hidden';
          Object.assign(hidden.style, {
            position: 'fixed', left: `${innerWidth - 80}px`, top: `${y - 10}px`,
            width: '40px', height: '20px', visibility: 'hidden',
          });
          document.querySelector('main').append(hidden);
        }""",
        box["y"] + box["height"] / 2,
    )
    point = page.evaluate(
        """y => {
          const x = innerWidth - 16;
          const hit = document.elementFromPoint(x, y);
          return {
            x, y,
            tag: hit?.tagName ?? "",
            chrome: Boolean(hit?.closest(".lf-chrome")),
            item: hit?.closest("main > *")?.id ?? "",
          };
        }""",
        box["y"] + box["height"] / 2,
    )
    assert point["tag"] in {"HTML", "BODY", "MAIN"}, point
    assert not point["chrome"] and not point["item"], point

    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    expect(page.locator(".lf-aim")).to_be_hidden()
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.75, point["y"] - 30, steps=8)
    page.mouse.move(box["x"] + box["width"] * 0.35, point["y"] + 20, steps=8)
    page.mouse.up()

    expect(page.locator(".lf-fab-input")).to_be_focused()
    with sending(page, "the margin drawing"):
        page.locator(".lf-composer-row .primary").evaluate("button => button.click()")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "prose"}
    assert "text" not in event
    expect(
        page.locator(f'.lf-drawing-posted[data-thread="{event["id"]}"]')
    ).to_have_count(1)
    assert errors == []
    page.close()


def test_a_click_draws_nothing_and_escape_leaves_the_mode(browser, serve):
    """Drawing is a drag, not a new click meaning. A click is swallowed without
    opening a comment or activating the page, and Escape restores ordinary reading."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    target = page.locator("#prose")
    target.evaluate(
        "el => el.addEventListener('click', () => { el.dataset.activated = ''; })"
    )
    box = target.bounding_box()
    point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*point)
    page.keyboard.press("w")

    assert page.evaluate("getComputedStyle(document.body).touchAction") == "none"
    page.mouse.click(*point)

    expect(page.locator("body")).to_have_class(re.compile(r"\blf-drawing\b"))
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    assert target.get_attribute("data-activated") is None
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "note"
    page.mouse.move(*point)
    page.mouse.down()
    page.keyboard.press("Escape")
    page.mouse.up()
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-drawing\b"))
    expect(page.locator(".lf-live")).to_contain_text("Draw mode off")
    assert target.get_attribute("data-activated") is None
    assert errors == []
    page.close()


def test_draw_mode_leaves_chrome_controls_usable(browser, serve):
    """The document plane is drawable, but a press on Leaf's chrome remains the
    control's gesture rather than becoming a page drawing."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.press("w")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    expect(page.locator("body")).to_have_class(re.compile(r"\blf-drawing\b"))
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    assert errors == []
    page.close()


def test_draw_mode_keeps_the_separate_design_mode_binding(browser, serve):
    """Adding Draw on w does not move the existing layer-review mode off l."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))

    page.keyboard.press("l")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-drawing\b"))
    page.keyboard.press("l")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))

    assert errors == []
    page.close()


def test_draw_mode_leaves_inline_conversation_controls_usable(browser, serve):
    """A page-widget shadow root retargets document pointer events to its host. The
    inline conversation it contains remains Leaf chrome, not a drawable widget control."""
    url = serve(CONVERSATION_DIFF_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "cd-q"},
            "text": "Can we discuss this line?",
        },
    )
    page, errors = open_page(browser, live_url(url))
    reply = page.get_by_role("textbox", name="Reply", exact=True)
    reply.scroll_into_view_if_needed()

    page.keyboard.press("w")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-drawing\b"))
    assert reply.evaluate("el => getComputedStyle(el).cursor") != "crosshair"
    reply.click()

    expect(reply).to_be_focused()
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-drawing\b"))
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    assert errors == []
    page.close()


def test_draw_mode_cursor_matches_the_widget_controls_it_captures(browser, serve):
    """Generated controls remain part of the drawable page plane. Their cursor must
    promise the stroke that takes their pointer press instead of promising activation."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    option = page.locator("#bg-choice-trail")
    control = option.locator(".lf-pick")
    control.scroll_into_view_if_needed()
    box = control.bounding_box()
    point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*point)
    page.keyboard.press("w")

    assert control.evaluate("el => getComputedStyle(el).cursor") == "crosshair"
    page.mouse.click(*point)

    expect(page.locator("body")).to_have_class(re.compile(r"\blf-drawing\b"))
    assert option.get_attribute("chosen") is None
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)

    shadow_line = page.locator("#bg-review-diff [data-line]").first
    shadow_line.scroll_into_view_if_needed()
    assert shadow_line.evaluate("el => getComputedStyle(el).cursor") == "crosshair"
    page.evaluate(
        """() => document.querySelector('.lf-panel').append(
          document.querySelector('#bg-review-diff')
        )"""
    )
    assert shadow_line.evaluate("el => getComputedStyle(el).cursor") != "crosshair"
    assert errors == []
    page.close()


def test_a_draw_press_uses_the_exact_target_under_its_start(browser, serve):
    """Joined option seams use the target under the pointer when the stroke starts."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    trail = page.locator("#bg-choice-trail")
    trail.scroll_into_view_if_needed()
    box = trail.bounding_box()
    point = (box["x"] + box["width"] * 0.5, box["y"])
    target = page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y)?.closest('lf-option')?.id",
        point,
    )
    assert target in {"bg-choice-street", "bg-choice-trail"}
    page.mouse.move(*point)
    page.keyboard.press("w")
    expect(page.locator(".lf-aim")).to_be_hidden()

    page.mouse.down()
    page.mouse.move(point[0] + 80, point[1], steps=8)
    page.mouse.up()
    page.locator(".lf-fab-input").fill("The seam I pointed at.")
    with sending(page, "the seam drawing"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": target}
    assert page.locator("#bg-choice-street").get_attribute("chosen") is None
    assert page.locator("#bg-choice-trail").get_attribute("chosen") is None
    assert errors == []
    page.close()


def test_an_active_stroke_re_resolves_a_replaced_target(browser, serve):
    """Projection may replace an anchored element during pointer capture; the stroke
    follows the same semantic target without minting invalid geometry."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    target = page.locator("#prose")
    box = target.bounding_box()
    start = (box["x"] + 30, box["y"] + box["height"] / 2)
    page.mouse.move(*start)
    page.keyboard.press("w")
    page.mouse.down()
    target.evaluate("el => el.replaceWith(el.cloneNode(true))")
    page.mouse.move(start[0] + 120, start[1], steps=8)
    page.mouse.up()

    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    page.locator(".lf-fab-input").fill("The replaced target still owns this.")
    with sending(page, "the replacement drawing"):
        page.keyboard.press("ControlOrMeta+Enter")
    drawing = events_model.read_events(serve.page_dir)[-1]["drawing"]
    assert all(
        coordinate is not None for point in drawing["points"] for coordinate in point
    )
    assert len(drawing["points"]) >= 2
    assert errors == []
    page.close()


def test_an_unsent_drawing_survives_reload_before_it_has_words(browser, serve):
    """The stroke is part of the comment draft. It persists as soon as it is captured,
    even when the optional explanatory text is still empty."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))

    draw_over(page, page.locator("#prose"))
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_have_value("")

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)

    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_value("")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "note"
    assert errors == []
    page.close()


def test_a_malformed_page_drawing_draft_keeps_its_words_without_the_mark(
    browser, serve
):
    """Persisted draft payload is an external boundary. Invalid drawing geometry is
    ignored while the independently valid words remain sendable."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.evaluate(
        """record => localStorage.setItem('lf-draft:general', JSON.stringify(record))""",
        {
            "text": "Keep these words.",
            "attempt": "a" * 32,
            "base": None,
            "payload": {
                "drawing": {"format": "leaf-drawing/1", "points": "not-points"}
            },
        },
    )

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    field = page.locator(".lf-general textarea")
    expect(field).to_have_value("Keep these words.")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    with sending(page, "the text-only recovered draft"):
        page.locator(".lf-general .primary").click()

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["text"] == "Keep these words."
    assert "drawing" not in event
    assert errors == []
    page.close()


def test_a_malformed_anchored_drawing_draft_keeps_its_words_without_the_mark(
    browser, serve
):
    """The selection draft has its own serialized envelope and applies the same
    drawing validation before page presentation or submission."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.evaluate(
        """record => {
          const anchor = {section: 'prose'};
          const ctx = 'composer:' + JSON.stringify([['section', 'prose']]);
          localStorage.setItem('lf-draft:' + ctx, JSON.stringify({
            text: JSON.stringify({
              text: 'Keep these anchored words.',
              anchor,
              suggest: false,
              about: null,
              drawing: {format: 'leaf-drawing/1', points: [[0, 0]]},
              touched: Date.now(),
            }),
            attempt: record.attempt,
            base: null,
          }));
        }""",
        {"attempt": "b" * 32},
    )

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    expect(field).to_have_value("Keep these anchored words.")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    with sending(page, "the text-only recovered anchored draft"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "prose"}
    assert event["text"] == "Keep these anchored words."
    assert "drawing" not in event
    assert errors == []
    page.close()


def test_a_drawing_can_be_sent_without_words(browser, serve):
    """The ink is the comment's content, so its normal send action works while the
    accompanying text field is empty. Its thread does not repeat contextless ink."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))

    draw_over(page, page.locator("#prose"))
    field = page.locator(".lf-fab-input")
    expect(field).to_have_value("")
    expect(page.locator(".lf-composer-row .primary")).to_have_attribute(
        "aria-disabled", "false"
    )
    with sending(page, "the drawing-only comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert "text" not in event
    assert event["drawing"]["format"] == "leaf-drawing/1"
    thread = page.get_by_role("dialog", name=re.compile("Thread for"))
    expect(thread).to_be_visible()
    expect(page.locator(".lf-drawing-preview")).to_have_count(0)
    expect(thread.locator(".lf-drawing-reference")).to_have_text("Drawing comment")
    expect(page.locator("#prose")).not_to_have_class(
        re.compile(r"\blf-mark-el\b|\blf-margin-target\b")
    )
    assert errors == []
    page.close()


def test_an_inline_conversation_keeps_drawing_context_on_the_page(browser, serve):
    """A widget-owned conversation leaves the drawing over its page target instead of
    showing the detached stroke again inside the conversation."""
    url = serve(CONVERSATION_DIFF_PAGE)
    drawing = {
        "format": "leaf-drawing/1",
        "points": [[-20, 74], [50, 10], [120, 74]],
    }
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "cd-q"},
            "drawing": drawing,
        },
    )

    page, errors = open_page(browser, live_url(url))
    expect(
        page.locator("#cd-q .lf-conversation-body .lf-drawing-preview")
    ).to_have_count(0)
    expect(page.locator("#cd-q .lf-drawing-reference")).to_have_text("Drawing comment")
    expect(page.locator(".lf-drawing-posted")).to_have_count(1)
    expect(page.locator("#cd-q")).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    assert errors == []
    page.close()


def test_an_unsent_drawing_stands_down_when_its_data_revision_changes(browser, serve):
    """Draft ink consumes the anchor pass's outdated reading instead of stretching
    itself over the source widget after its original datum version disappears."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    target = page.locator(
        "lf-diff [data-line-type='change-deletion'][data-lf-datum]"
    ).first

    draw_over(page, target)
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    data_model.cmd_data_set(
        serve.page_dir,
        "gallery-patch",
        """diff --git a/gallery/review.py b/gallery/review.py
--- a/gallery/review.py
+++ b/gallery/review.py
@@ -1,2 +1,2 @@
 def route():
-    return "courtyard"
+    return "garden room"
""",
    )
    told(page)

    expect(page.locator(".lf-drawing-pending")).to_have_count(0)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    assert errors == []
    page.close()


def test_a_posted_drawing_stands_down_without_a_false_page_reference(browser, serve):
    """When a data revision detaches a drawing target, its thread still names the
    drawing without claiming that the suppressed stroke is visible on the page."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    target = page.locator(
        "lf-diff [data-line-type='change-deletion'][data-lf-datum]"
    ).first

    draw_over(page, target)
    with sending(page, "the data-anchored drawing"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-drawing-posted")).to_have_count(1)

    data_model.cmd_data_set(
        serve.page_dir,
        "gallery-patch",
        """diff --git a/gallery/review.py b/gallery/review.py
--- a/gallery/review.py
+++ b/gallery/review.py
@@ -1,2 +1,2 @@
 def route():
-    return "courtyard"
+    return "garden room"
""",
    )
    told(page)

    expect(page.locator(".lf-drawing-posted")).to_have_count(0)
    references = page.locator(".lf-drawing-reference")
    expect(references.first).to_have_text("Drawing comment")
    assert set(references.all_text_contents()) == {"Drawing comment"}
    assert errors == []
    page.close()
