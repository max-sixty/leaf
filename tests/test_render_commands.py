"""Render, shot, and browser-gate command tests."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import INTERACT_SCRIPT
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import render_checks as render_checks_model
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect
from render_support import (
    BADGE_CHROME,
    CARRIED_PAGE,
    EXAMPLE_MEDIA,
    INLINE_PAGE,
    LONG_PAGE,
    PAINTED_IN_SILENCE_PAGE,
    PRINT_LOSS_PAGE,
    REPLY_HOST_PAGE,
    SCROLL_SETTLE_MS,
    SCROLL_STILL,
    SETTLED_PAGE,
    SHORT_CHIP_PAGE,
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    SPECIMEN_MARKUP,
    SPECIMEN_TEXT,
    UNPARSABLE_DIAGRAM,
    author_test_widget,
    flip_point,
    key_line,
    open_page,
    page_registry,
    primed,
    resized,
    shown_frames,
    solid_png,
)

pytestmark = pytest.mark.nightly


def test_the_gate_passes_a_page_that_carries_a_comment(browser, serve):
    """The gate refuses words under `.lf-ui` inside a widget, because a widget reaching for
    that marker is how a user ends up unable to comment on a heading they can see. The
    line saying how many comments are on a passage wears the same marker and sits wherever
    the passage does — inside the widget, when that is where the comment was made. Unless
    the gate knows the difference, one comment on an option is a page nobody can hand over,
    and every page the sweep above renders is a page with no comments on it.

    The pass hunting words drawn on other words has to know the same difference, and
    knows it as a float the runtime hangs over the page. That line is clipped to nothing
    and checkVisibility answers for display, visibility and opacity, so it reads as drawn,
    and its characters fall down the document through the paragraphs under the passage.
    Holding it out is the only thing keeping this page clean, so the reading is taken
    twice: once as the gate runs it, and once with the hold defeated, where it has to
    report.

    The hold is the float predicate rather than a class named in the skip list, which is
    what the second reading has to reach for now: the line is out-of-flow chrome like a
    suggestion's controls, so one rule answers for both and a name beside it would be the
    same guarantee kept twice."""
    # The last option, because the unheld half below needs the line to land on words:
    # the note is the holder's last child, so its characters fall from the end of the
    # option's own prose, and from a mid-group option they fall through the whitespace
    # tails of the shorter cells below and are spent before any paragraph. From the
    # group's last option they cross straight into #p, whose full-width lines have a
    # word at any x the option's prose can end on.
    url = serve(INLINE_PAGE, anchored=[("opt-b", "quietly puts one back")])
    page, errors = open_page(browser, url)
    # Vacuous otherwise: the gate has to be looking at a page that has the line on it.
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-mark-note').length === 1"
    )
    # The same reading with the hold defeated, taken while the page is up.
    reported = render_checks_model.evaluate_probe(
        page, "coveredWords", {"holdFloating": False}
    )
    assert errors == []
    page.close()
    assert render_gate_model.render_version(browser, url) == []
    assert any("1 comment" in found for found in reported), (
        "the line falls on nobody, so a gate that never looked would pass this too"
    )


def test_the_gate_passes_a_page_whose_collapsed_cards_lie_on_each_other(browser, serve):
    """Words drawn on other words is a question about the screen, and a collapse is the
    page being asked to take words off it. The cards behind a settled row wear
    hidden="until-found" so find-in-page still reaches them, which is content-visibility
    rather than display, and checkVisibility answers for neither: they read as drawn, and
    each reports the box it last laid out in, so all three land on one another. That is
    the collapse working, and COVERED_WORDS says why it is held out.

    On a fresh load whether they report at all is a coin, which is no basis for a test.
    Opening the row and closing it again settles it: the cards lay out for real, and the
    boxes they keep afterwards are that layout."""
    url = serve(SETTLED_PAGE)
    page, errors = open_page(browser, url)
    row = page.locator("#transport .lf-settled")
    card = page.locator("#transport #opt-lax")

    row.click()
    expect(card).to_be_visible()
    row.click()
    expect(card).to_be_hidden()

    # The gate's own reading, taken here rather than left to render_version: that opens a
    # fresh page, which is the coin again, and this page is the one holding the layout the
    # cards kept. Then the same named reading with its collapsed-content hold disabled.
    held, reported = (
        render_checks_model.evaluate_probe(page, "coveredWords"),
        render_checks_model.evaluate_probe(page, "coveredWords", {"holdHidden": False}),
    )
    assert errors == []
    assert held == []
    assert any("opt-" in found for found in reported), (
        "the cards fell on nobody, so a gate that never looked would pass this too"
    )
    page.close()
    assert render_gate_model.render_version(browser, url) == []


def test_the_gate_measures_an_inline_widget_by_its_words(browser, serve):
    """A chip is set among the words around it, so its box is the words in it and there is
    no width it was ever going to reach. Held to the floor written for a widget that lays
    out a region, a chip saying `£9` reads as a collapse, and the gate refuses a page with
    nothing wrong with it — for a price, which is the shortest thing an author is likely to
    put in one. A suggestion swapping one short word is the same case in a second tag,
    there because the gate dispatches on the declaration: the day the wrapper took a box
    it stood in front of this floor, and only x-inline says whose floor is whose.

    The floor a chip does keep is the height, since a line of words is a line tall under
    any layout. Both halves are asserted, because a floor deleted outright passes the
    first on its own."""
    url = serve(SHORT_CHIP_PAGE)
    page, errors = open_page(browser, url)
    widths = page.locator("lf-chip").evaluate_all(
        "els => els.map(el => Math.round(el.getBoundingClientRect().width))"
    )
    assert errors == []
    assert widths and max(widths) < 40, (
        f"these chips are {widths}px, so they clear the floor and prove nothing"
    )
    sug_width = page.locator("#sug-flag").evaluate(
        "el => Math.round(el.getBoundingClientRect().width)"
    )
    assert sug_width < 40, (
        f"the suggestion is {sug_width}px, so it clears the floor and proves nothing"
    )

    # Asked without the declaration, the same floor flags it — so what passes the page
    # is the declaration, not a floor gone missing.
    undeclared = json.loads(json.dumps(page_registry(page)))
    del undeclared["lf-suggestion"]["x-inline"]
    assert [
        box
        for box in render_checks_model.evaluate_probe(page, "tinyBoxes", undeclared)
        if box["tag"] == "lf-suggestion"
    ], (
        "with x-inline stripped the gate stays quiet, so the floor is gone rather than declared"
    )

    # Flattened, the same chips are a collapse and the gate says so — the reading the
    # declaration narrows rather than switches off.
    page.add_style_tag(
        content="lf-chip { display: block; height: 2px; overflow: hidden; }"
    )
    flattened = render_checks_model.evaluate_probe(
        page, "tinyBoxes", page_registry(page)
    )
    page.close()
    assert [box for box in flattened if box["tag"] == "lf-chip"], (
        "a chip with no height left reports nothing, so the floor is gone rather than declared"
    )
    assert render_gate_model.render_version(browser, url) == []


def test_check_render_refuses_what_only_a_browser_can_see(serve):
    """`version check --render` end to end, as the agent runs it: the static lint
    passes both sources, and only one renders clean. The broken source is deliberately
    unstamped — refusing it before `version stamp` names it is the gate's whole job,
    so the preview server has to expose the exact candidate without activating it."""
    serve(LONG_PAGE)
    d = serve.page_dir

    def gate(*args):
        return subprocess.run(
            [
                sys.executable,
                str(INTERACT_SCRIPT),
                "version",
                "check",
                str(d),
                "--render",
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,  # both exit codes are the subject
        )

    ok = gate()
    assert ok.returncode == 0, ok.stderr
    assert "renders clean" in ok.stdout

    # A vw width slips the static lint (which counts only px) and overflows only
    # in a layout engine.
    (d / "index.html").write_text(
        LONG_PAGE.replace("</main>", "<div style='width:150vw'>wide</div>\n</main>")
    )
    broken = gate()
    assert broken.returncode == 1
    assert "scrolls sideways" in broken.stderr


def test_an_installed_payload_passes_its_real_browser_gate(tmp_path):
    """Exercise the copied artifact a host installs, never an import from this checkout."""
    root = Path(__file__).parent.parent
    installed = tmp_path / "host" / "plugins" / "leaf"
    shutil.copytree(root / "plugins" / "leaf", installed)
    launcher = installed / "bin" / "leaf"
    elsewhere = tmp_path / "unrelated-project"
    elsewhere.mkdir()
    page_dir = tmp_path / "state" / "page"

    init = subprocess.run(
        [launcher, "page", "init", page_dir],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    (page_dir / "index.html").write_text(
        (root / "examples" / "release-notes.html").read_text()
    )
    shutil.copytree(EXAMPLE_MEDIA, page_dir / "media", dirs_exist_ok=True)
    stamp = subprocess.run(
        [
            launcher,
            "version",
            "stamp",
            page_dir,
            "--text",
            "installed-payload smoke",
        ],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert stamp.returncode == 0, stamp.stderr

    rendered = subprocess.run(
        [launcher, "version", "check", page_dir, "--render"],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "renders clean" in rendered.stdout


def test_render_reports_a_word_the_printed_page_loses(browser, serve):
    """A user prints the page, or saves it to PDF for someone who wasn't in the
    loop, and whatever the screen said had better still be there. Ways it isn't, all
    silent: a control that is a statement as well as a thing to press (the pick mark,
    which is the only place a group says which option it carries) and a rule that
    hides page content in print, inside a widget or in plain prose. The gate reads
    the page in both media and reports what the second one drops.

    A control declared an offer is exempt, since paper has nothing to press: the same
    page's pick mark reads "chosen" and goes unreported either way."""
    assert render_gate_model.render_version(browser, serve(CARRIED_PAGE)) == [], (
        "a page whose print rendering keeps its words has nothing to report"
    )

    lost = render_gate_model.render_version(browser, serve(PRINT_LOSS_PAGE))
    assert [f for f in lost if f.startswith("[print]")] == [
        (
            '[print] <p id=lede> drops "Where the decision stands, for the recor", '
            "which it says on screen"
        ),
        '[print] <lf-option id=c-bearer> drops "Bearer header", which it says on screen',
        (
            '[print] <lf-option id=c-bearer> drops "Suits the mobile client;\\n  '
            'puts the id w", which it says on screen'
        ),
    ], lost


def test_a_shot_shows_one_frame_and_flips_between_them(browser, serve):
    """The comparison lf-shot makes is a flip: two registered frames in one grid cell,
    one of them showing. What the gate covers on the way past is the rest of the
    widget's bargain — the captions naming each frame are the page's words and stay
    selectable, the switch is chrome and takes no space in the user's reading, and
    a printed copy keeps both frames and both captions.

    The image is the target, so both presses land on one point and the pointer never
    moves: a comparison is many alternations, and the whole worth of a flip is that
    the eye can hold still through them. Pressing the switch instead would assert the
    state swaps while saying nothing about what it costs to swap it."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    assert render_gate_model.render_version(browser, url) == []

    page, errors = open_page(browser, url)
    assert shown_frames(page) == ["before"]
    at = flip_point(page)
    page.mouse.click(*at)
    expect(page.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()
    assert shown_frames(page) == ["after"]
    box = page.locator("lf-shot input[type=checkbox]")
    expect(box).to_be_focused()
    assert "show before" in key_line(page)
    # The native checkbox is the overlay itself. Hold it across two frames: focus and the
    # screenshot key line must remain stable for the whole human press.
    page.mouse.down()
    expect(box).to_be_focused()
    assert "show before" in key_line(page)
    page.mouse.up()
    expect(page.locator('.lf-shotframe[data-lf-state="before"]')).to_be_visible()
    assert shown_frames(page) == ["before"]
    # The visible instruction sits under the same native overlay. A repeated held press
    # there keeps both focus and the screenshot key line stable too.
    text_label = page.locator("lf-shot .lf-shotpick label")
    label_bounds = text_label.bounding_box()
    assert label_bounds is not None
    text_at = (
        label_bounds["x"] + label_bounds["width"] - 2,
        label_bounds["y"] + label_bounds["height"] / 2,
    )
    assert box.evaluate(
        "(control, point) => document.elementFromPoint(...point) === control",
        text_at,
    )
    page.mouse.move(*text_at)
    page.mouse.down()
    expect(box).to_be_focused()
    assert "show after" in key_line(page)
    page.mouse.up()
    expect(page.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()
    assert shown_frames(page) == ["after"]
    # The same full target is the keyboard's native handle.
    box.focus()
    page.keyboard.press(" ")
    expect(page.locator('.lf-shotframe[data-lf-state="before"]')).to_be_visible()
    assert errors == []
    page.close()


def test_a_tall_shot_flips_where_it_was_clicked_without_moving_the_page(browser, serve):
    """A tall comparison may put its instruction row more than a viewport below the
    point being inspected. Both the image and that row are the native checkbox itself,
    so a click changes state without label activation focusing some distant box and
    centring it in the viewport. The same causal gesture is checked on a desk and phone."""
    before = solid_png(390, 844, (232, 226, 213))
    after = solid_png(390, 844, (214, 226, 235))
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC["before"]: before, SHOT_SRC["after"]: after},
    )
    page, errors = open_page(browser, url)
    box = page.locator("lf-shot > input.lf-shotflip")
    expect(box).to_have_accessible_name(
        "flip — or click the image — the navigation rail"
    )
    frame = page.locator('lf-shot .lf-shotframe[data-lf-state="before"]')
    row = page.locator("lf-shot .lf-shotpick")

    for width in (1200, 390):
        resized(page, width, 900)
        page.evaluate(
            """() => { const r = document.querySelector('lf-shot .lf-shotframe')
                                  .getBoundingClientRect();
                       document.body.scrollBy(0, r.top - 140); }"""
        )
        image_point = frame.evaluate(
            "el => { const r = el.getBoundingClientRect();"
            "        return [r.left + r.width / 2, r.top + 80]; }"
        )
        assert page.evaluate(
            "([x, y]) => document.elementFromPoint(x, y) === "
            "document.querySelector('lf-shot > input.lf-shotflip')",
            image_point,
        )
        was_checked = box.is_checked()
        scroll_before = page.evaluate("document.body.scrollTop")
        page.mouse.click(*image_point)
        page.wait_for_function(SCROLL_STILL, arg=SCROLL_SETTLE_MS)
        assert box.is_checked() is not was_checked
        assert abs(page.evaluate("document.body.scrollTop") - scroll_before) <= 1

        # Put the instruction just inside the viewport, then remove the focus left by
        # the image gesture. An implementation covering only the image would route this
        # press through the label to a remote checkbox and reproduce the same jump.
        page.evaluate(
            """() => { document.activeElement.blur();
                       const r = document.querySelector('lf-shot .lf-shotpick')
                                         .getBoundingClientRect();
                       document.body.scrollBy(0, r.bottom - innerHeight + 60); }"""
        )
        row_point = row.evaluate(
            "el => { const r = el.getBoundingClientRect();"
            "        return [r.left + 10, r.top + r.height / 2]; }"
        )
        assert page.evaluate(
            "([x, y]) => document.elementFromPoint(x, y) === "
            "document.querySelector('lf-shot > input.lf-shotflip')",
            row_point,
        )
        was_checked = box.is_checked()
        scroll_before = page.evaluate("document.body.scrollTop")
        page.mouse.click(*row_point)
        page.wait_for_function(SCROLL_STILL, arg=SCROLL_SETTLE_MS)
        assert box.is_checked() is not was_checked
        assert abs(page.evaluate("document.body.scrollTop") - scroll_before) <= 1

    assert errors == []
    page.close()


def test_a_shot_still_flips_with_every_script_removed(browser, serve, tmp_path):
    """Which is the whole reason the target is a native checkbox. A copy is the
    rendered DOM with the scripts dropped and every press a handler answered taken out
    with them — the upgrade has already run, so the frames are there, and this switch
    survives that pass because the browser is what works it. A slider would have
    frozen at whatever the reader left it on; `:has(:checked)` is CSS, and the browser
    owns a checkbox's state, so its transparent box over the image goes on being the
    target in a file with nothing running.

    Through `version export` rather than a copy the test makes itself, which is what
    puts the widget's bargain in front of the code that could break it: a hand-rolled
    one dropped the script tags and nothing else, so it went on passing however the
    real export treated a control.

    What it pins is no longer that a state serializes. Setting `checked` as a property
    left no attribute behind, so the copy opened with neither frame chosen and both of
    them stacked in the one cell — a fault the frames' own default has since made
    unrepresentable, the after frame being hidden until something checks the box rather
    than until something checks the other box. So the state needs nothing serialized at
    all, and what is left to lose is the gesture: the direct native checkbox and its CSS
    target must survive. A copy that dropped either would keep every frame and every word
    and answer no click on the image."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )

    standalone = tmp_path / "standalone.html"
    standalone.write_text(exporting_model.export_page(browser, url, serve.page_dir))
    loose = browser.new_page(viewport={"width": 1200, "height": 900})
    loose.goto(standalone.as_uri(), wait_until="load")
    assert loose.evaluate("document.querySelectorAll('script').length") == 0
    assert shown_frames(loose) == ["before"]
    loose.mouse.click(*flip_point(loose))
    assert shown_frames(loose) == ["after"]
    loose.close()


def test_a_shot_refuses_a_pair_shot_at_two_widths(browser, serve):
    """Both frames render at the frame's width, so a pair captured at two viewports is
    scaled by two different factors and every line in it lands somewhere new — the flip
    then reports that the whole page changed, convincingly and with nothing on screen
    to say otherwise. The one failure worth an error box rather than a caveat."""
    narrow = solid_png(400, 300, (235, 215, 205))
    page_html = SHOT_PAGE.replace(
        SHOT_SRC["after"], f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    )
    narrow_src = f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    url = serve(
        page_html,
        media={SHOT_SRC["before"]: SHOTS["before"], narrow_src: narrow},
    )

    assert [
        f
        for f in render_gate_model.render_version(browser, url)
        if "600px" in f and "400px" in f
    ], "the gate has to hear about a mismatch, since nobody else will"


def test_render_reports_words_a_widget_puts_out_of_reach(browser, serve):
    """The user's half of the gate. A user selected a draft's heading, tried to
    comment on it, and got nothing back — twice, months apart, on the same page. The
    heading was the page's word in a row its author had marked as the runtime's, and
    `.lf-ui` is a look rather than a permission, so the class alone can't be the answer:
    the declaration goes on the label (relabel), and an undeclared word under chrome is
    reported here.

    The second one no marker can fix, which is why it reads differently: a word inside a
    form control is unselectable in every engine, so a widget that reaches for <button>
    has put its label somewhere the user cannot go. `offer` builds a press as a span
    for exactly this reason, and this is what says so when a widget doesn't use it."""
    assert render_gate_model.render_version(browser, serve(CARRIED_PAGE)) == [], (
        "the same page without the two mistakes has nothing to report"
    )

    def put_native_link(page):
        page.add_init_script(
            """addEventListener('DOMContentLoaded', () => {
              const link = document.createElement('a');
              link.className = 'lf-ui';
              link.href = '#h';
              link.textContent = 'Read context';
              document.getElementById('c-lax').prepend(link);
            }, {once: true});"""
        )

    assert (
        render_gate_model.render_version(
            primed(browser, put_native_link), serve(CARRIED_PAGE)
        )
        == []
    ), "a native link's words label its browser-owned control rather than the page"

    def put_words_out_of_reach(page):
        page.add_init_script(
            """addEventListener('DOMContentLoaded', () => {
              const option = document.getElementById('c-lax');
              const row = document.createElement('div');
              row.className = 'lf-ui';
              row.innerHTML = '<strong>Session cookies</strong>';
              const button = document.createElement('button');
              button.setAttribute('data-lf-said', '');
              button.textContent = 'Lax, host-only';
              option.prepend(row, button);
            }, {once: true});"""
        )

    found = render_gate_model.render_version(
        primed(browser, put_words_out_of_reach), serve(CARRIED_PAGE)
    )
    assert sorted({f.split("] ", 1)[1] for f in found}) == [
        (
            '<lf-option id=c-lax> puts "Session cookies" under .lf-ui, where no comment '
            "can reach it"
        ),
        (
            '<lf-option id=c-lax> says "Lax, host-only" inside a form control, where no '
            "selection can reach it"
        ),
    ], found


def test_render_reports_a_painted_fact_whose_word_was_drawn_nowhere(browser, serve):
    """The x-paints half of the same gate, and the line it draws between two silences.

    A widget may paint a fact — `recommended` is a corner mark and no text node —
    and it owes a reader who is listening the same fact in words. The runtime
    writes that word, so what is left to check is whether anything drew it. Asking
    is asking for a box, and only an element that is being laid out has one to give:
    a disclosure nobody opened, a tab nobody switched to and a shut comment panel
    all lay out nothing, and their emptiness is the ancestor's answer rather than
    the widget's.

    So the two silences part here, and this holds one of them: a word drawn nowhere
    on a page that is on screen is reported, and the same widget behind a fold is
    not, there being nothing to measure and the fold being the reader's to open.
    That exemption is what lets a widget riding a message out, in
    `test_render_leaves_a_widget_riding_a_reply_out_of_that_reading`.

    The other silence — a word the runtime never wrote, which is a fault wherever
    the element stands — no fixture can stage: `quietFacts` returns the attribute's
    own value or its name, so a declared paint always gets its word, and the branch
    is reachable only by a regression in `renderQuiet` itself. What holds it is the
    corpus with that regression put back: silence `renderQuiet` and every painted
    option in the examples is reported, a `parallel-workstreams` option in a tab
    nobody opened among them. Skipping the unrendered element before asking whether
    a word exists is what drops that one, so the order of the two questions here is
    the contract, and this test does not pin it."""
    found = [
        f.split("] ", 1)[1]
        for f in render_gate_model.render_version(
            browser, serve(PAINTED_IN_SILENCE_PAGE)
        )
    ]
    assert sorted(set(found)) == [
        (
            '<lf-option id=p-seen> paints recommended="" and says nothing a reader '
            "listening can hear"
        )
    ], found


def test_render_reads_a_reply_widgets_own_chrome_and_not_the_panel_around_it(
    browser, serve, tmp_path, monkeypatch
):
    """The same reading, asked where the nesting turns over.

    A widget's chrome is a `.lf-ui` the widget put inside itself. A widget in a
    message is the other way up: the runtime's own layer is above it and the
    widget has none of its own, so every word it holds sits under a `.lf-ui`
    with nothing wrong. Asking whether the *words* stand in a widget cannot tell
    those apart and accuses the second. Asking whose the `.lf-ui` is can.

    Both halves, because either alone is half a claim. One reply carries three
    widgets: a question, an exhibit beside it, and a badge whose module injects
    unmarked words under the chrome face. The panel around all three says
    nothing; the badge's own chrome is read exactly as it would be on a page.

    Nothing here had ever been rendered. No example shipped a widget in its log
    until one did, and every fixture that put one in a reply asked about the
    panel rather than about the gate — while the gate walks text nodes rather
    than boxes, so it had been reading the panel all along with the panel shut.
    It would have refused the first page that carried a question in a reply,
    which is a shape the vocabulary describes and `leaf reply --markup` posts."""
    monkeypatch.chdir(tmp_path)
    package = author_test_widget(tmp_path, "lf-badge", upgrade=True)
    module = package / "widgets" / "lf-badge.js"
    module.write_text(
        module.read_text().replace(
            "      if (!once(this)) return;",
            "      if (!once(this)) return;\n" + BADGE_CHROME,
        )
    )

    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-ask",
            "author": "user",
            "revision": 1,
            "text": "What would the alternative look like?",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "revision": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP + '<lf-badge id="rp-badge">Weighed.</lf-badge>',
        },
    )
    found = sorted(
        {f.split("] ", 1)[1] for f in render_gate_model.render_version(browser, url)}
    )
    assert found == [
        (
            '<lf-badge id=rp-badge> puts "Sent by the reviewer" under .lf-ui, where no '
            "comment can reach it"
        )
    ], found


def test_the_shim_runs_the_gate_from_anywhere(serve, tmp_path):
    """`leaf` is what the skill hands an agent, so the shim's own resolution
    is load-bearing: it finds the script from its location rather than the cwd,
    and on `--render` it supplies the Playwright the PEP 723 header deliberately
    omits. Running it from an unrelated directory exercises both.

    The version under it carries a mermaid body that doesn't parse — a shape the
    static lint cannot reach, since it validates the element and never the
    notation inside it. The widget fails soft and the browser half is what sees
    the error box, which is why the gate is worth its couple of seconds."""
    serve(UNPARSABLE_DIAGRAM)
    d = serve.page_dir
    assert (
        CliRunner().invoke(cli_model.cli, ["version", "check", str(d)]).exit_code == 0
    )

    shim = Path(__file__).parent.parent / "plugins" / "leaf" / "bin" / "leaf"
    run = subprocess.run(
        [str(shim), "version", "check", str(d), "--render"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 1, run.stdout + run.stderr
    # "needs Playwright" here would mean the shim dispatched the plain `uv run`.
    assert "failed soft" in run.stderr and "Parse error" in run.stderr
