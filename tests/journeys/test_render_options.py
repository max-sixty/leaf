"""Options, samples, and decision presentation tests."""

import io
import math
import re

import pytest
from click.testing import CliRunner
from interact_support import (
    end_work_on,
    working,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_interaction import (
    ASK_PAGE,
    ASK_WITH_CONTEXT_PAGE,
    EXHIBIT_EXTENT,
    SAMPLE_EXAMPLES,
    live_url,
)
from render_harness import (
    CARRIED_PAGE,
    SAMPLE_PAGE,
    active_digit_bindings,
    compare_with,
    open_page,
    resized,
    round_trip,
    shortcut_bar_text,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_pick_the_page_only_reports_can_still_be_pointed_at(browser, serve):
    """An authored pick without a live control is a check with an accessible name.

    The selected state does not introduce a visible status caption or new page words,
    and the generated fallback remains outside the diff's authored-text reading.
    """
    url = serve(CARRIED_PAGE)
    page = open_page(browser, live_url(url))
    mark = page.locator("#c-lax .lf-pick")
    assert mark.get_attribute("role") == "img"
    assert mark.get_attribute("aria-label") == "selected: Lax cookie"
    assert mark.evaluate("el => getComputedStyle(el).fontSize") == "0px"
    assert mark.evaluate("el => getComputedStyle(el, '::before').content") == '"✓"'

    # The generated check is not authored text, so rewording another option marks only
    # that option in the version comparison.
    d = serve.page_dir
    stamp_page(
        d,
        CARRIED_PAGE.replace("Suits the mobile client", "Suits the mobile client best"),
        "two",
    )
    wait_for_revision(page, 2)
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["c-bearer"], "the diff read the mark as text the base version lacked"


def test_option_words_render_markdown_without_losing_the_user_draft(browser, serve):
    source = ASK_PAGE.replace(
        "Replace the <code>M8</code> mounts", "Ask the _widget_ to decide"
    )
    url = serve(source)
    page = open_page(browser, url)
    authored = page.locator("#job-mounts")
    expect(authored.locator(":scope > .lf-markdown-words em")).to_have_text("widget")
    expect(authored.locator(":scope > .lf-pick")).to_have_attribute(
        "aria-label", re.compile(r"Ask the widget to decide — option 1")
    )

    group = page.locator("#jobs")
    write(group.get_by_role("textbox", name="Another option"), "Keep **both** routes")
    group.get_by_role("button", name="Add and select option").click()
    added = group.locator(":scope > lf-option[data-lf-added]")
    expect(added.locator("strong")).to_have_text("both")
    round_trip(page)
    page.reload(wait_until="load")
    expect(added.locator("strong")).to_have_text("both")

    group.locator("#job-heater").click()
    round_trip(page)
    adds = [
        event["detail"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "action" and event.get("action") == "add"
    ]
    assert adds == [
        {"option": added.get_attribute("id"), "text": "Keep **both** routes"}
    ]
    expect(added.locator("strong")).to_have_text("both")


def test_a_selected_ask_keeps_one_action_context_while_tab_reaches_its_field(
    browser, serve
):
    """The Ask owns its numbered actions wherever focus stands inside it.

    Tab traverses the real controls without replacing that action map. Another option is
    the next numbered route into its shared text box rather than an Enter alias on a mark.
    """
    url = serve(ASK_WITH_CONTEXT_PAGE)
    page = open_page(browser, url)

    page.keyboard.press("q")
    mark = page.locator("#storage-evict .lf-pick")
    line = shortcut_bar_text(page)
    # The Ask's own numbered actions are what the line offers, under the one context the
    # question owns, with the way out of the standing ahead of them as it is anywhere
    # the user is holding something.
    assert active_digit_bindings(page) == "1–3", line
    assert "let go" in line, line
    option_hints = page.locator("#storage-options > lf-option > .lf-key-badge")
    expect(option_hints).to_have_text(["1", "2"])
    expect(option_hints.first).to_be_visible()
    write_hint = page.locator("#storage-options > .lf-another > .lf-key-badge")
    box = page.locator("#storage-options > .lf-another leaf-text")
    expect(write_hint).to_have_text("3")
    expect(write_hint).to_be_visible()

    # Enter has no invented meaning on the Ask or an option mark. Tab enters the real
    # controls, while the same Ask-owned numbers and binding badges remain standing there.
    page.keyboard.press("Enter")
    expect(page.locator("#storage-decision")).to_be_focused()
    page.keyboard.press("3")
    expect(box).to_be_focused()
    expect(write_hint).to_be_hidden()
    page.close()

    page = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    page.keyboard.press("q")
    mark = page.locator("#storage-evict .lf-pick")
    box = page.locator("#storage-options > .lf-another leaf-text")
    page.keyboard.press("Tab")
    expect(mark).to_be_focused()
    expect(mark).to_have_attribute("role", "checkbox")
    expect(mark).to_have_attribute("aria-checked", "false")
    expect(
        page.locator(
            "#storage-options > lf-option > .lf-key-badge[data-lf-binding-badge]"
        )
    ).to_have_text(["1", "2"])
    assert shortcut_bar_text(page) == line
    page.keyboard.press("Enter")
    expect(mark).to_be_focused()
    expect(box).not_to_be_focused()
    expect(page.locator("#storage-options > lf-option[chosen]")).to_have_count(0)

    # The controls remain in document order: the other mark, then the text box. It keeps
    # Shift+Enter keeps a native newline; Enter submits the option.
    page.keyboard.press("Tab")
    expect(page.locator("#storage-stop .lf-pick")).to_be_focused()
    page.keyboard.press("Tab")
    expect(box).to_be_focused()
    write(box, "Keep both layers")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("Keep them together")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("Preserve both histories")
    expect(box).to_have_js_property(
        "value", "Keep both layers\nKeep them together\nPreserve both histories"
    )
    expect(box).to_have_attribute("aria-keyshortcuts", "Enter Meta+Enter Control+Enter")
    expect(page.locator("#storage-options > lf-option[data-lf-added]")).to_have_count(0)
    assert "add and select option" in shortcut_bar_text(page)
    page.keyboard.press("Enter")
    added = page.locator("#storage-options > lf-option[data-lf-added]")
    expect(added).to_contain_text("Keep both layers")
    expect(added.locator(".lf-option-words")).to_have_css("white-space", "normal")
    expect(added.locator("br")).to_have_count(2)
    page.close()

    page = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    page.keyboard.press("q")
    page.keyboard.press("Tab")
    mark = page.locator("#storage-evict .lf-pick")
    expect(mark).to_be_focused()
    page.keyboard.press("2")
    expect(page.locator("#storage-stop")).to_have_attribute("chosen", "")
    chosen = page.locator("#storage-stop .lf-pick")
    # The digit acts within the Ask without turning binding selection into focus
    # navigation; the user remains on the control they tabbed to.
    expect(mark).to_be_focused()
    expect(chosen).to_have_attribute("role", "checkbox")
    expect(chosen).to_have_attribute("aria-checked", "true")
    expect(page.locator("#storage-options > .lf-another leaf-text")).not_to_be_focused()
    page.close()

    # Native focus scrolling reads the fixed shortcut bar as part of the root scrollport's
    # unavailable foot. In a phone window the field otherwise lands underneath that line:
    # geometrically in the viewport, but neither visible nor operable as the next stop.
    #
    # Short enough that the ask's own foot is under the line when the user arrives, which
    # is the only arrangement in which the claim can be read at all. With the whole ask on
    # screen a Tab stop is already where the browser would put it, nothing scrolls, and the
    # reading goes green over the travel it is about; the assertion before the presses says
    # so rather than leaving it to the window's height to be right. Chrome's focus
    # scroll moves a stop only when it stands wholly outside the padded band, so the
    # window is one where the arrival leaves the field wholly under the bottom bar.
    page = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    resized(page, 390, 600)
    clearance = """() => document.querySelector('.lf-shortcut-bar').getBoundingClientRect().top
      - document.querySelector('#storage-options > .lf-another')
        .getBoundingClientRect().bottom"""
    # An unframed page ask arrives in two document scrolls, an instant one to reveal it
    # and a glide onto its region, and a Tab pressed into the glide reads a position the
    # page is only passing through: it goes on to its own destination afterwards and takes
    # the measurement with it. Motion is not what this reads, so the arrival is asked to
    # make none — under reduced motion `scrollBehavior()` is `instant`, both scrolls land
    # inside the press, and there is no settling frame for the presses below to race.
    page.emulate_media(reduced_motion="reduce")
    page.keyboard.press("q")
    covered = page.evaluate(clearance)
    assert covered < 0, f"the arrival left the add field {covered}px clear of the line"
    for _ in range(3):
        page.keyboard.press("Tab")
    box = page.locator("#storage-options > .lf-another leaf-text")
    expect(box).to_be_focused()
    landed = page.evaluate(clearance)
    assert landed >= 20, f"the shortcut bar covers the add field by {-landed}px"


def test_a_widget_without_a_thread_says_what_the_agent_is_doing(browser, serve):
    """A page widget is a first-class work subject even before anybody comments.

    A board card declares a local work seat and receives its page-edge margin entry without
    inventing a comment thread. An options group deliberately has no such seat: adding
    an option changes decision state, and any discussion starts as a separate thread
    once that option exists. Unrelated versions leave the board claim in force, while
    a claim made on v2 does not leak backward into a pinned v1 tab.
    """
    work_page = ASK_PAGE.replace(
        '<h1 id="h">Three jobs</h1>',
        '<h1 id="h">Three jobs</h1>\n'
        '<lf-board id="work-board"><lf-column id="work-now" label="In flight">\n'
        '  <lf-card id="card-migration"><strong>Run the migration</strong> '
        "Check the shard before cutover.</lf-card>\n"
        '</lf-column><lf-column id="work-next" label="Next"></lf-column>\n'
        '<lf-column id="work-done" label="Done"></lf-column></lf-board>',
    )
    url = serve(work_page)
    page = open_page(browser, live_url(url))
    d = serve.page_dir

    def claim(subject, detail):
        working(d, detail, subject=subject)
        told(page)

    claim("card-migration", "checking the shard")
    unsupported = CliRunner().invoke(
        cli_model.cli,
        ["task", "open", str(d), "jobs", "Price the alternatives"],
    )
    assert unsupported.exit_code != 0
    assert "has no work seat" in unsupported.output

    card_button = page.locator(
        '[data-lf-margin-for="card-migration"] > .lf-margin-marker'
    )
    expect(card_button).to_have_attribute("data-lf-kinds", "activity")
    expect(card_button.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "activity"
    )
    expect(card_button).to_have_attribute(
        "aria-label", re.compile("checking the shard")
    )
    card_button.click()
    expect(page.locator(".lf-live")).to_contain_text("checking the shard")
    expect(page.locator(".lf-thread")).to_have_count(0)
    expect(page.locator(".lf-thread-panel .lf-msg-sending")).to_have_count(0)
    expect(page.locator("#card-migration > .lf-msg-sending")).to_have_count(0)
    expect(card_button).to_have_class(re.compile(r"\blf-margin-entry\b"))
    card_button.evaluate("node => { node.dataset.identityProbe = 'kept' }")

    # An unrelated version leaves the card coordinate in force.
    stamp_page(d, work_page, "Elsewhere")
    wait_for_revision(page, 2)
    expect(card_button).to_have_attribute("data-identity-probe", "kept")

    # A task opened on v2 belongs to v2 and does not appear in a pinned v1 page.
    end_work_on(d, "card-migration")
    claim("card-migration", "checking the fallback")
    expect(card_button).to_have_attribute(
        "aria-label", re.compile("checking the fallback")
    )
    pinned = open_page(browser, url, pin=True)
    expect(
        pinned.locator('[data-lf-margin-for="card-migration"] > .lf-margin-marker')
    ).to_have_count(0)
    pinned.close()

    stamp_page(
        d,
        work_page,
        "Local work complete",
        completes=("card-migration",),
    )
    wait_for_revision(page, 3)
    expect(page.locator(".lf-msg-sending")).to_have_count(0)


@pytest.mark.parametrize(
    "source",
    [SAMPLE_PAGE, *SAMPLE_EXAMPLES],
    ids=["fixture", *(p.stem for p in SAMPLE_EXAMPLES)],
)
def test_the_gutter_runs_beside_the_exhibit_and_no_further(source, browser, serve):
    """The gutter marks what is quoted and nothing else, at both ends, and two separate
    things had to be true for that. The "quoted ·" note over the bar is the theme's word
    *about* the region rather than a word in it, and the bar opened at the note, drawing
    the marking around a line the page never said. And a table cell is a margin barrier,
    so the room the exhibit's outermost blocks reserve against neighbours they haven't
    got could not collapse out and was painted as bar instead — sixteen pixels of it
    over the first card and under the last, on every sample shipped.

    Geometry can't answer the top. The element's own rect is the table wrapper's and
    takes in the caption, while the bar is painted on the table box inside it, which
    nothing in the DOM is a handle on — so a rect comparison passes exactly as well
    with the note back inside the marking. The pixels in the bar's own column are the
    reading, and each edge is read in a strip of its own with that edge brought to the
    middle of the window: a clip is the viewport's, so one strip over the whole bar
    would cap the sweep at the tallest exhibit a window can hold.

    Driven over every sample in the corpus rather than the fixture alone, because
    what the theme can reach is the sample's direct children and what it cannot is
    whichever widget hands its boxes to the flow instead. That gap is invisible in the
    stylesheet and shows only as a bar longer than what it marks, so the corpus is
    where the next one gets caught."""
    from PIL import Image  # a dev dependency already, for the demo recorder

    # Serve each example with its data and history: live samples can select
    # authored threads as part of the exhibit.
    page = open_page(browser, serve(source))
    scale = page.evaluate("() => devicePixelRatio")
    # Rendered, not merely present. A sample inside a tab panel the page is not
    # showing sits in skipped content, which still reports its last laid-out rect — a
    # position the page cannot be scrolled to, since the room it names is not in the
    # document's height. `checkVisibility` is the question `lf-suggestion` already asks
    # for the same reason.
    samples = page.locator("lf-sample").evaluate_all(
        """elements => elements.map(sample => {
            const path = [];
            for (let tab = sample.closest('lf-tab'); tab;
                 tab = tab.parentElement.closest('lf-tab')) {
                path.push({set: tab.parentElement.id, label: tab.getAttribute('label')});
            }
            return {id: sample.id, path: path.reverse()};
        })"""
    )
    assert samples, "this page declares no sample: the reading below asserts nothing"

    for sample in samples:
        for owner in sample["path"]:
            page.locator(f"#{owner['set']}").get_by_role(
                "tab", name=owner["label"], exact=True
            ).click()
        spec = sample["id"]
        assert page.locator(f"#{spec}").evaluate("el => el.checkVisibility()"), (
            f"{spec} remained hidden after opening its tabs"
        )
        # A live sample paints its gutter on the exhibit around its frame, since its
        # host controls cannot be the table's second caption.
        painter = page.locator(f"#{spec}").evaluate(
            "el => el.querySelector(':scope > .lf-sample-view > .lf-sample-exhibit')"
            " ? `#${el.id} .lf-sample-exhibit` : `#${el.id}`"
        )
        ink = tuple(
            int(n)
            for n in re.findall(
                r"\d+",
                page.locator(painter).evaluate(
                    "el => getComputedStyle(el).borderLeftColor"
                ),
            )[:3]
        )
        found = {}
        for edge in ("top", "bottom"):
            # `instant`, because the page asks for smooth scrolling and a read taken
            # while one is still gliding is of wherever it had got to — which passes on
            # a short page, where the glide is over before the next call lands, and
            # failed on the corpus, where the same delta is thousands of pixels.
            page.evaluate(
                """([id, edge]) => {
                    const r = document.getElementById(id).getBoundingClientRect();
                    document.scrollingElement.scrollBy({
                        top: (edge === 'top' ? r.top : r.bottom) - innerHeight / 2,
                        behavior: 'instant',
                    });
                }""",
                [spec, edge],
            )
            box = page.locator(f"#{spec}").bounding_box()
            exhibit = page.evaluate(EXHIBIT_EXTENT, spec)

            # A column one pixel wide inside the 3px bar, running from outside the
            # marking to well inside it, and read from the inside out: stopping at the
            # first pixel that isn't the bar's keeps a glyph of the note's that happens
            # to antialias through this colour from being a bar the run can reach.
            #
            # The clip's top is floored first and the reading counts from the floored
            # value, because a clip is asked for in CSS pixels and Chrome truncates the
            # rect before it scales — a pixel of unmodelled bias, against a gap of four.
            REACH = 40  # far enough inside the bar to start in it, and to give a number
            near, far = (
                (box["y"], exhibit["top"] + REACH)
                if edge == "top"
                else (exhibit["bottom"] - REACH, box["y"] + box["height"] + REACH)
            )
            clip = {
                "x": box["x"] + 1,
                "y": math.floor(near),
                "width": 1,
                "height": math.ceil(far) - math.floor(near),
            }
            on_screen = page.evaluate(
                "([y, h]) => y >= 0 && y + h <= innerHeight",
                [clip["y"], clip["height"]],
            )
            assert on_screen, (
                f"#{spec}'s {edge} strip is not wholly on screen ({clip}): a "
                f"screenshot clip is the viewport's, so the scan would read a "
                f"truncated image"
            )
            strip = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
            assert strip.height == clip["height"] * scale, (
                f"the clip asked for {clip['height']} CSS px at dpr {scale} and came "
                f"back {strip.height} device px: the arithmetic below no longer "
                f"locates its edge"
            )
            rows = [strip.getpixel((0, y)) for y in range(strip.height)]
            if edge == "bottom":
                rows.reverse()  # both edges read from the far end of the strip inward
            painted = 0
            while painted < len(rows) and all(
                abs(a - b) <= 6 for a, b in zip(rows[-1 - painted], ink)
            ):
                painted += 1
            assert painted, (
                f"#{spec}: no gutter painted in the column beside the exhibit at the "
                f"{edge} ({rows[-1]}) — the bar is unpainted, or it is more than "
                f"{REACH}px away from the exhibit it marks"
            )
            found[edge] = (
                clip["y"] + (len(rows) - painted) / scale
                if edge == "top"
                else clip["y"] + painted / scale
            )
            found[f"{edge}-exhibit"] = exhibit[edge]
            if edge == "top":
                found["note"] = exhibit["note"]

        assert abs(found["top"] - found["top-exhibit"]) <= 1, (
            f"#{spec}'s marking begins at {found['top']} and the exhibit at "
            f"{found['top-exhibit']}: the bar runs beside something the page did not "
            f"say, or begins after what it marks"
        )
        assert abs(found["bottom"] - found["bottom-exhibit"]) <= 1, (
            f"#{spec}'s marking ends at {found['bottom']} and the exhibit at "
            f"{found['bottom-exhibit']}: the bar outlives what it marks — most likely "
            f"a trailing margin inside a child that generates no box, which the "
            f"theme's rule for the sample's last child cannot reach"
        )
        if found["note"] is not None:
            assert found["note"] <= found["top"] + 1, (
                f"#{spec}'s marking begins at {found['top']}, above the foot of the "
                f"note at {found['note']}: the marking takes in a line the page never "
                f"said"
            )
