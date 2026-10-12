"""Render, shot, and browser-gate command tests."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import LEAF_COMMAND
from interact_support import (
    append_carried_log_record,
    append_command,
    install_payload,
    state_json,
)
from leaf import render_checks as render_checks_model
from leaf.render_gate.page_code import run_page_code
from playwright.sync_api import expect
from render_cases_layout import (
    SHORT_CHIP_PAGE,
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    UNPARSABLE_DIAGRAM,
    shown_frames,
    solid_png,
)
from render_harness import (
    INLINE_PAGE,
    LONG_PAGE,
    example_media,
    leaf_page,
    open_page,
    page_registry,
    shortcut_bar_text,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_commands import FILM_DECLARATION, FILM_PAGE, unnamed_browser


def test_the_gate_passes_a_page_that_carries_a_comment(browser, serve):
    """A comment on a widget's option leaves a page the gate passes
    (`test_every_table_the_theme_sets_honestly_passes_the_gate` gates one): the mark
    and the note counting the comment are the runtime's, and none of it is words the
    widget wrote.

    The pass hunting words drawn on other words holds out a control the runtime hangs out
    of flow over the page (`floating` in words.js). A control planted over the option's
    words is held out by the normal reading and reported by the reading with that hold
    disabled, so the hold is what keeps such a control from failing the page."""
    url = serve(INLINE_PAGE, anchored=[("opt-b", "quietly puts one back")])
    page = open_page(browser, url)
    # Vacuous otherwise: the gate has to be looking at a page that carries the comment.
    expect(page.locator(".lf-mark-note")).to_have_count(1)
    page.evaluate(
        """() => {
          const text = document.querySelector('#opt-b strong').firstChild;
          const range = document.createRange();
          range.selectNodeContents(text);
          const word = range.getClientRects()[0];
          const float = Object.assign(document.createElement('span'), {
            className: 'lf-ui', textContent: 'planted float',
          });
          Object.assign(float.dataset, { lfGen: '1', lfOffer: 'button' });
          Object.assign(float.style, {
            position: 'absolute', whiteSpace: 'nowrap',
            left: `${word.left + scrollX}px`, top: `${word.top + scrollY}px`,
          });
          document.body.append(float);
        }"""
    )
    held = render_checks_model.evaluate_probe(page, "coveredWords")
    reported = render_checks_model.evaluate_probe(
        page, "coveredWords", {"holdFloating": False}
    )
    page.close()
    assert held == []
    assert any(
        "planted float" in (found["words"], found["covered"]) for found in reported
    ), "the planted control covers no words, so a gate that never looked would pass too"


def test_the_gate_passes_collapsed_words_that_overlap_when_visible(browser, serve):
    """Collapsing overlapping words removes them from the gate's screen reading."""
    url = serve(
        leaf_page(
            "collapsed words",
            '<h1>Collapsed words</h1><div id="collapsed" hidden="until-found">'
            '<p style="position:absolute;top:100px;left:100px;margin:0">First hidden line</p>'
            '<p style="position:absolute;top:100px;left:100px;margin:0">Second hidden line</p>'
            "</div>",
        )
    )
    page = open_page(browser, url)
    collapsed = page.locator("#collapsed")
    collapsed.evaluate("node => node.removeAttribute('hidden')")
    expect(collapsed.locator("p").first).to_be_visible()
    visible = render_checks_model.evaluate_probe(page, "coveredWords")
    assert any(
        {found["words"], found["covered"]}
        == {"First hidden line", "Second hidden line"}
        for found in visible
    ), (
        "the visible lines fell on nobody, so a gate that never looked would pass this too"
    )
    collapsed.evaluate("node => node.setAttribute('hidden', 'until-found')")
    expect(collapsed.locator("p").first).to_be_hidden()

    assert render_checks_model.evaluate_probe(page, "coveredWords") == []


def test_the_gate_measures_an_inline_widget_by_its_words(browser, serve):
    """A gloss is set among the words around it, so its box is the words in it and there is
    no width it was ever going to reach. Held to the floor written for a widget that lays
    out a region, a gloss saying `£9` reads as a collapse, and the gate refuses a page with
    nothing wrong with it — for a price, which is the shortest thing an author is likely to
    put in one. A suggestion swapping one short word is the same case in a second tag,
    there because the gate dispatches on the declaration: the day the wrapper took a box
    it stood in front of this floor, and only x-inline says whose floor is whose.

    The floor a gloss does keep is the height, since a line of words is a line tall under
    any layout. Both halves are asserted, because a floor deleted outright passes the
    first on its own."""
    url = serve(SHORT_CHIP_PAGE)
    page = open_page(browser, url)
    widths = page.locator("lf-gloss").evaluate_all(
        "els => els.map(el => Math.round(el.getBoundingClientRect().width))"
    )
    assert widths and max(widths) < 40, (
        f"these glosses are {widths}px, so they clear the floor and prove nothing"
    )
    sug_width = page.locator("#sug-flag").evaluate(
        "el => Math.round(el.getBoundingClientRect().width)"
    )
    assert sug_width < 40, (
        f"the suggestion is {sug_width}px, so it clears the floor and proves nothing"
    )

    assert (
        render_checks_model.evaluate_probe(page, "tinyBoxes", page_registry(page)) == []
    ), "the gate refuses glosses and a suggestion with nothing wrong with them"

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

    # Flattened, the same glosses are a collapse and the gate says so — the reading the
    # declaration narrows rather than switches off.
    page.add_style_tag(
        content="lf-gloss { display: block; height: 2px; overflow: hidden; }"
    )
    flattened = render_checks_model.evaluate_probe(
        page, "tinyBoxes", page_registry(page)
    )
    page.close()
    assert [box for box in flattened if box["tag"] == "lf-gloss"], (
        "a gloss with no height left reports nothing, so the floor is gone rather than declared"
    )


def test_check_render_refuses_what_only_a_browser_can_see(serve):
    """`page check --render` end to end, as the agent runs it: the static lint
    passes both sources, and only one renders clean. The broken source is deliberately
    unstamped — refusing it before `page stamp` names it is the gate's whole job,
    so the preview server has to expose the exact candidate without activating it.

    The clean source goes through the installed Chrome the default channel finds; the
    executable leaf's browser variable names is
    `test_an_installed_payload_passes_its_real_browser_gate`'s. This arm states every
    variable empty rather than inheriting whatever the developer or the job
    exported, since a set one would otherwise turn the channel this arm exists to
    cover into a run of the named one. A runner image really does export
    CHROME_BIN, so unnaming leaf's alone is not unnaming. The success line has to name
    the browser that drew the page: a clean gate telling a Chromium host that Chrome
    drew it is the same false claim on the way out that the failure messages stopped
    making."""
    serve(LONG_PAGE)
    d = serve.page_dir

    def gate(*flags):
        return subprocess.run(
            [*LEAF_COMMAND, "page", "check", str(d), "--render", *flags],
            capture_output=True,
            text=True,
            check=False,  # both exit codes are the subject
            env=unnamed_browser(),
        )

    ok = gate()
    assert ok.returncode == 0, ok.stderr
    assert "render checks passed in Chrome" in ok.stdout

    # A vw width slips the static lint (which counts only px) and overflows only
    # in a layout engine.
    (d / "index.html").write_text(
        LONG_PAGE.replace("</main>", "<div style='width:150vw'>wide</div>\n</main>")
    )
    broken = gate("--json")
    assert broken.returncode == 1, broken.stderr
    report = json.loads(broken.stdout)
    assert report["status"] == 1
    assert report["browser"]["asked"] == report["browser"]["ran"] == ["render check"]
    assert report["browser"]["browser"] == "Chrome"
    scrolls = [f for f in report["findings"] if f["code"] == "page-scrolls"]
    assert {f["scheme"] for f in scrolls} == {"light", "dark"}, report
    assert all(f["severity"] == "error" and f["values"]["past"] > 0 for f in scrolls)


def test_a_passing_render_check_saves_the_screens_the_author_reads(
    serve, headless_shell
):
    """A clean `page check --render` saves screens and names them: the page top to
    bottom at the desktop viewport and on a phone, and one screen at each width where
    the page's own arrangement is at its tightest before it changes. A sidebar page with
    four tiles in its body changes twice there: its tiles wrap before its track stacks.
    Each open Ask, a suggestion as much as an lf-ask, gets the window `q` brings it
    into, as the user working the page meets it, including those `q` reaches past a
    page widget move handed back to the user, which is a stop of its own and no Ask."""
    tiles = "".join(
        f"<dl id='m{i}'><dt>metric {i}</dt><dd>{i}</dd></dl>" for i in range(4)
    )
    serve(
        leaf_page(
            "a sidebar page",
            "<header><h1>Rollout</h1></header>"
            "<div id='body'><lf-ask id='ship-ask'><h2>Ship now?</h2>"
            "<lf-options id='ship' choose><lf-option id='ship-now'>Now</lf-option>"
            "<lf-option id='ship-later'>Later</lf-option></lf-options></lf-ask>"
            f"<div class='layout-tiles' id='2026-numbers'>{tiles}</div>"
            + "".join(
                f"<p id='para-{i}'>{'Body paragraph. ' * 30}</p>" for i in range(60)
            )
            + "".join(
                f"<lf-ask id='ask-{i}'><h2>Ship part {i}?</h2>"
                f"<lf-options id='o-{i}' choose><lf-option id='o-{i}-y'>Yes</lf-option>"
                f"<lf-option id='o-{i}-n'>No</lf-option></lf-options></lf-ask>"
                for i in range(2)
            )
            + "<p id='note'>Keep this line.<lf-suggestion id='sug'><lf-old>"
            "Drop this one.</lf-old></lf-suggestion></p>"
            + "</div><aside id='checks'><p>Checks beside the body.</p></aside>",
            layout="sidebar",
        )
    )
    # The first Ask is answered, and the host gave up on picking the answer up, which
    # hands the move back: the walk's first stop is that widget, ahead of every Ask.
    moved = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "ship",
            "action": "choose",
            "detail": {"value": ["ship-now"]},
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "pickup",
            "author": "page",
            "attention": False,
            "events": [moved["id"]],
            "phase": "failed",
            "failure": "turn_failed",
            "session": "screens",
            "turn": "turn-1",
        },
    )
    questions = state_json(serve.page_dir)["queues"]["questions"]
    assert {"kind": "widget", "id": "ship"} in [item["subject"] for item in questions]

    ran = subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(serve.page_dir), "--render"],
        capture_output=True,
        text=True,
        check=True,
        env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
    )
    lines = ran.stdout.splitlines()
    heading = next(line for line in lines if "screens to read" in line)
    into = Path(heading.split(" in ", 1)[1].rstrip(":"))
    listed = lines[lines.index(heading) + 1 :]
    names = sorted(path.name for path in into.iterdir())
    assert {"1200px-1.png", "1920px-1.png", "390px-1.png"} <= set(names)
    assert {
        "1200px-question-1.png",
        "1200px-question-2.png",
        "1200px-question-3.png",
    } <= set(names)
    assert "1200px-question-4.png" not in names
    assert any("each press of `q`" in line for line in listed)
    assert any('"Pre-handover review"' in line for line in listed)
    stacks = next(line for line in listed if "<main> 1+2 → 1+1+1" in line)
    assert (into / stacks.split(":")[0].strip()).exists()
    assert any("<div id=2026-numbers> 4 → " in line for line in listed)
    # A page longer than its first screens says so rather than passing for read whole.
    assert "390px-9.png" not in names
    assert any("phone, the first 8 of the page's" in line for line in listed)


def test_a_named_browser_that_is_not_one_names_the_variable(serve, tmp_path):
    """A browser variable is the whole of what a host says about its browser, so a
    value naming no browser has to come back as that variable and that value rather
    than as Chrome, which the host never asked for.

    Whichever variable the host set is the one the message names. Reporting a
    CHROME_PATH browser as LEAF_BROWSER_EXECUTABLE's would be a false statement about
    the host's own configuration, and it points the reader at a variable they never
    set — so the second half checks the other two by their own names."""
    serve(LONG_PAGE)
    d = serve.page_dir
    missing = tmp_path / "not-a-browser"
    named = unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": str(missing)}

    checked = subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(d), "--render"],
        capture_output=True,
        text=True,
        check=False,
        env=named,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "· render check: not run, no browser launched: " in checked.stderr
    assert (
        "LEAF_BROWSER_EXECUTABLE" in checked.stderr and str(missing) in checked.stderr
    )
    assert "Chrome did not launch" not in checked.stderr

    for variable in ("CHROME_PATH", "CHROME_BIN"):
        answered = subprocess.run(
            [*LEAF_COMMAND, "page", "check", str(d), "--render"],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | {variable: str(missing)},
        )
        assert answered.returncode == 0, answered.stdout + answered.stderr
        assert variable in answered.stderr and str(missing) in answered.stderr
        assert "LEAF_BROWSER_EXECUTABLE" not in answered.stderr


def test_an_installed_payload_passes_its_real_browser_gate(tmp_path, headless_shell):
    """Exercise the copied artifact a harness installs, never an import from this checkout.

    Its browser gate runs on a named Chromium, since the install is where a host with
    a Chromium and no Chrome meets it, and its success line names that executable
    rather than Chrome; the default channel's Chrome is
    `test_check_render_refuses_what_only_a_browser_can_see`'s."""
    root = Path(__file__).parents[2]
    installed = install_payload(tmp_path / "host" / "leaf")
    launcher = installed / "bin" / "leaf"
    elsewhere = tmp_path / "unrelated-project"
    elsewhere.mkdir()
    page_dir = tmp_path / "state" / "page"

    init = subprocess.run(
        [launcher, "page", "init", "--package", "diagram", page_dir],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    installed_registry = json.loads((page_dir / "registry.json").read_text())
    assert "lf-diagram" in installed_registry
    assert installed_registry["$layer"]["packages"] == ["diagram"]
    (page_dir / "index.html").write_text(
        (root / "examples" / "release-notes.html").read_text()
    )
    shutil.copytree(example_media(), page_dir / "media", dirs_exist_ok=True)
    stamp = subprocess.run(
        [
            launcher,
            "page",
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
        [launcher, "page", "check", page_dir, "--render"],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
        env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
    )
    assert rendered.returncode == 0, rendered.stderr
    assert f"render checks passed in {headless_shell}" in rendered.stdout


def test_a_shot_compares_its_frames_with_a_direct_divider(browser, serve):
    """The live pair is continuously comparable, with direct endpoint alternatives.

    Pointer drag and the component's complete keyboard pattern move one divider. The
    rail jumps to the named endpoints, while print keeps the two complete frames
    and their order. The gate's pass over the pair is
    `test_render_reads_painted_facts_and_widget_chrome_where_they_stand`'s."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.add_init_script(
        """new MutationObserver(() => {
          if (document.body?.hasAttribute('data-lf-presented') &&
              window.__lfPresentedAt === undefined)
            window.__lfPresentedAt = performance.now();
        }).observe(document, {attributes: true, subtree: true});
        new PerformanceObserver(list => {
          for (const entry of list.getEntries())
            if (entry.name.endsWith('/vendor/webawesome.esm.js'))
              window.__lfComparisonRequestedAt = entry.startTime;
        }).observe({type: 'resource', buffered: true});"""
    )
    page.goto(url)
    page.wait_for_function(
        "document.body.hasAttribute('data-lf-presented') && "
        "document.querySelector('lf-shot wa-comparison')"
    )
    comparison = page.locator("lf-shot wa-comparison")
    handle = comparison.get_by_role("scrollbar")
    expect(handle).to_be_visible()
    page.wait_for_function("window.__lfComparisonRequestedAt !== undefined")
    timing = page.evaluate(
        """() => ({
          presented: window.__lfPresentedAt,
          requested: window.__lfComparisonRequestedAt,
        })"""
    )
    assert timing["requested"] >= timing["presented"]
    rail = page.locator("lf-shot .lf-shotrail")
    expect(rail).to_have_count(1)
    expect(rail.locator(".lf-shotcap")).to_have_text(["before", "after"])
    before_bounds = rail.locator('[data-lf-state="before"]').bounding_box()
    after_bounds = rail.locator('[data-lf-state="after"]').bounding_box()
    assert before_bounds is not None and after_bounds is not None
    expect(comparison).to_have_attribute("position", "50")
    glyph = comparison.locator('[slot="handle"].lf-shot-handle')
    expect(glyph).to_have_count(1)
    assert glyph.evaluate(
        "node => [getComputedStyle(node).borderStyle, "
        "getComputedStyle(node).borderRadius]"
    ) == ["solid", "50%"]
    expect(handle).to_have_accessible_name("Before and after — the navigation rail")
    expect(handle).to_have_attribute("aria-valuetext", "Before 50%, after 50%")
    # Each half of the split shows the frame its rail caption names: the image the
    # user hits below a caption is that caption's own. Web Awesome's `after` slot is
    # the inline-start side, so wiring the frames to their same-named slots put the
    # after image under BEFORE.
    comparison.scroll_into_view_if_needed()
    under_captions = page.evaluate(
        """() => {
          const box = document.querySelector('lf-shot wa-comparison')
            .getBoundingClientRect();
          return [...document.querySelectorAll('lf-shot .lf-shotcap')].map(cap => {
            const x = cap.getBoundingClientRect().left + cap.offsetWidth / 2;
            const hit = document.elementFromPoint(x, box.top + box.height / 2);
            return [cap.dataset.lfState, hit?.closest('.lf-shotframe')?.dataset.lfState];
          });
        }"""
    )
    assert under_captions == [["before", "before"], ["after", "after"]]
    page.emulate_media(media="print")
    assert shown_frames(page) == ["before", "after"]
    printed_tops = [
        page.locator(f'lf-shot .lf-shotframe[data-lf-state="{state}"]').bounding_box()[
            "y"
        ]
        for state in ("before", "after")
    ]
    assert printed_tops[0] < printed_tops[1], "paper put the after frame on top"
    assert (
        rail.locator('[data-lf-state="before"]').evaluate(
            "cap => getComputedStyle(cap, '::after').content"
        )
        == '" · top"'
    )
    assert (
        rail.locator('[data-lf-state="after"]').evaluate(
            "cap => getComputedStyle(cap, '::after').content"
        )
        == '" · bottom"'
    )
    page.emulate_media(media="screen")
    expect(comparison).to_be_visible()
    page.mouse.move(0, 0)
    divider_face = comparison.evaluate(
        """async node => {
          const divider = node.shadowRoot.querySelector('[part~="divider"]');
          const handle = node.shadowRoot.querySelector('[part~="handle"]');
          await Promise.all(handle.getAnimations().map(animation => animation.finished));
          return {
            divider: getComputedStyle(divider).backgroundColor,
            handle: getComputedStyle(handle).backgroundColor,
            opacity: parseFloat(getComputedStyle(handle).opacity),
          };
        }"""
    )
    assert divider_face["divider"] != divider_face["handle"]
    assert 0.45 < divider_face["opacity"] < 0.6

    comparison.scroll_into_view_if_needed()
    bounds = comparison.bounding_box()
    assert bounds is not None
    image_point = (bounds["x"] + bounds["width"] / 4, bounds["y"] + 80)
    page.mouse.move(*image_point)
    active_midpoint = comparison.evaluate(
        """async node => {
          const handle = node.shadowRoot.querySelector('[part~="handle"]');
          await Promise.all(handle.getAnimations().map(animation => animation.finished));
          return parseFloat(getComputedStyle(handle).opacity);
        }"""
    )
    assert active_midpoint == 1
    page.mouse.down()
    page.mouse.up()
    expect(comparison).to_have_attribute("position", "0")
    page.mouse.move(0, 0)
    quiet_handle = comparison.evaluate(
        """async node => {
          const handle = node.shadowRoot.querySelector('[part~="handle"]');
          await Promise.all(handle.getAnimations().map(animation => animation.finished));
          return parseFloat(getComputedStyle(handle).opacity);
        }"""
    )
    assert quiet_handle < 0.25
    handle.focus()
    active_handle = comparison.evaluate(
        """async node => {
          const handle = node.shadowRoot.querySelector('[part~="handle"]');
          await Promise.all(handle.getAnimations().map(animation => animation.finished));
          return parseFloat(getComputedStyle(handle).opacity);
        }"""
    )
    assert active_handle == 1
    page.mouse.click(*image_point)
    expect(comparison).to_have_attribute("position", "100")
    comparison.evaluate("node => { node.position = 50; }")
    before_caption = page.get_by_role(
        "button", name="before — the navigation rail", exact=True
    )
    # A second finger does not replace the primary contact's input destination.
    before_caption.focus()
    handle.evaluate("""handle => handle.dispatchEvent(new PointerEvent('pointerdown', {
      bubbles: true, composed: true, pointerId: 98, pointerType: 'touch',
      isPrimary: false, button: 0
    }))""")
    expect(before_caption).to_be_focused()
    handle.click()
    expect(handle).to_be_focused()
    expect(comparison).to_have_attribute("position", "50")
    page.keyboard.press("ArrowRight")
    expect(comparison).to_have_attribute("position", "51")

    after_caption = page.get_by_role(
        "button", name="after — the navigation rail", exact=True
    )
    expect(before_caption).to_have_attribute("aria-pressed", "false")
    expect(after_caption).to_have_attribute("aria-pressed", "false")
    before_caption.focus()
    assert "show before" in shortcut_bar_text(page)
    after_caption.focus()
    assert "show after" in shortcut_bar_text(page)
    after_caption.click()
    expect(comparison).to_have_attribute("position", "0")
    expect(before_caption).to_have_attribute("aria-pressed", "false")
    expect(after_caption).to_have_attribute("aria-pressed", "true")
    page.mouse.move(0, 0)
    assert after_caption.evaluate("node => getComputedStyle(node).backgroundColor") != (
        before_caption.evaluate("node => getComputedStyle(node).backgroundColor")
    )
    # A selectable caption owns Space even at its current endpoint so it cannot
    # fall through to browser scrolling (the widget's existing command contract).
    assert "show after" in shortcut_bar_text(page)
    after_caption.focus()
    page.evaluate("() => { document.scrollingElement.scrollTop -= 120; }")
    expect(after_caption).to_be_in_viewport()
    selected_scroll = page.evaluate("() => document.scrollingElement.scrollTop")
    assert (
        page.evaluate(
            "() => document.scrollingElement.scrollHeight - innerHeight - "
            "document.scrollingElement.scrollTop"
        )
        >= 100
    )
    page.keyboard.press("Space")
    expect(comparison).to_have_attribute("position", "0")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == selected_scroll
    after_caption.click()
    expect(comparison).to_have_attribute("position", "0")
    before_caption.click()
    expect(comparison).to_have_attribute("position", "100")
    after_caption.focus()
    page.keyboard.press("Enter")
    expect(comparison).to_have_attribute("position", "0")
    before_caption.focus()
    page.keyboard.press("Space")
    expect(comparison).to_have_attribute("position", "100")
    for locator, bounds in (
        (rail.locator('[data-lf-state="before"]'), before_bounds),
        (rail.locator('[data-lf-state="after"]'), after_bounds),
    ):
        flipped_bounds = locator.bounding_box()
        assert flipped_bounds is not None
        assert {key: flipped_bounds[key] for key in ("x", "width", "height")} == {
            key: bounds[key] for key in ("x", "width", "height")
        }

    handle.focus()
    expect(handle).to_be_focused()
    assert "adjust the comparison" in shortcut_bar_text(page)
    page.keyboard.press("ArrowLeft")
    expect(comparison).to_have_attribute("position", "99")
    expect(handle).to_have_attribute("aria-valuetext", "Before 99%, after 1%")
    page.keyboard.press("Shift+ArrowLeft")
    expect(comparison).to_have_attribute("position", "89")
    page.keyboard.press("End")
    expect(comparison).to_have_attribute("position", "100")
    page.keyboard.press("Home")
    expect(comparison).to_have_attribute("position", "0")

    comparison.evaluate("node => { node.position = 50; }")
    expect(comparison).to_have_attribute("position", "50")
    bounds = comparison.bounding_box()
    handle_bounds = handle.bounding_box()
    assert bounds is not None and handle_bounds is not None
    at = (
        handle_bounds["x"] + handle_bounds["width"] / 2,
        handle_bounds["y"] + handle_bounds["height"] / 2,
    )
    page.mouse.move(*at)
    page.mouse.down()
    page.mouse.move(at[0] + bounds["width"] / 4, at[1], steps=4)
    page.mouse.up()
    dragged = float(comparison.get_attribute("position"))
    assert 70 <= dragged <= 80
    expect(handle).to_have_attribute(
        "aria-valuetext", f"Before {dragged:g}%, after {100 - dragged:g}%"
    )

    comparison.evaluate("node => { node.position = 100; }")
    expect(comparison).to_have_attribute("position", "100")
    # The existing rail owns endpoint actions and retains focus after each press.
    for state, position in (("after", "0"), ("before", "100")):
        caption = page.locator(f'.lf-shotcap[data-lf-state="{state}"]')
        caption.focus()
        expect(caption).to_be_focused()
        page.keyboard.press("Enter" if state == "after" else "Space")
        expect(comparison).to_have_attribute("position", position)
        expect(caption).to_be_focused()

    handle.focus()
    ring = handle.evaluate(
        """node => { const cs = getComputedStyle(node); return {
          name: cs.getPropertyValue('--lf-focus-ring').trim(),
          width: cs.outlineStyle === 'none' ? 0 : parseFloat(cs.outlineWidth),
        }}"""
    )
    assert ring["name"] == "comparison-handle" and ring["width"] > 0


def test_the_shim_runs_the_gate_from_anywhere(serve, tmp_path, headless_shell):
    """`leaf` is what the skill hands an agent, so the shim's own resolution
    is load-bearing: it names the payload project from its own location rather
    than letting uv find whatever project the cwd sits in. Running it from an
    unrelated directory exercises that.

    The version under it carries a diagram body the renderer refuses — a shape the
    static lint cannot reach, since it validates the element and never the
    notation inside it. The widget fails soft and reports it, and a data body is
    what sends plain `page check` to the browser to hear that report, which is why
    the check is worth its couple of seconds."""
    serve(UNPARSABLE_DIAGRAM)
    d = serve.page_dir

    shim = Path(__file__).parents[2] / "bin" / "leaf"
    for executable in ("", headless_shell):
        run = subprocess.run(
            [str(shim), "page", "check", str(d)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"LEAF_BROWSER_EXECUTABLE": executable},
        )
        assert run.returncode == 1, run.stdout + run.stderr
        # "needs Playwright" here would mean the shim dispatched the plain `uv run`.
        # The report names the widget and gives the renderer's reason.
        assert "Error: page code reported 1 error" in run.stderr
        assert '<lf-diagram id="d-broken"> failed:' in run.stderr
        assert "No diagram type detected" in run.stderr
        assert "/widgets/lf-diagram.js:" not in run.stderr
        assert "leaf-unsupported" not in run.stderr
        assert "Ada,Review,3" not in run.stderr


def test_plain_check_reports_page_request_failures_but_ignores_optional_assets(
    browser, serve
):
    url = serve(
        FILM_PAGE.replace("</main>", '<img src="/page/missing-image.png"></main>'),
        page_files={
            "registry.json": json.dumps(FILM_DECLARATION),
            "film.js": 'import { label } from "./helper.js";\n'
            "export const paint = el => (el.textContent = label);\n",
            "helper.js": 'export const label = "loaded";\n',
            "widgets/lf-film.js": 'import { paint } from "../film.js";\n'
            "customElements.define('lf-film', class extends HTMLElement {\n"
            "  connectedCallback() { paint(this); }\n"
            "});\n",
            "widgets/lf-loader.js": "customElements.define('lf-loader', class extends HTMLElement {\n"
            "  connectedCallback() { this.textContent = 'loaded'; }\n"
            "});\n",
        },
        media={"page/missing-image.png": solid_png(1, 1, (0, 0, 0))},
    )

    class RoutedBrowser:
        def __init__(self, *, fail_helper):
            self.fail_helper = fail_helper

        def new_page(self, **kwargs):
            page = browser.unwatched.new_page(**kwargs)
            page.route(
                "**/page/helper.js",
                lambda route: (
                    route.abort("failed") if self.fail_helper else route.continue_()
                ),
            )
            page.route(
                "**/page/missing-image.png", lambda route: route.fulfill(status=404)
            )
            return page

    failed = run_page_code(RoutedBrowser(fail_helper=True), url)
    # The runtime's own report carries the error's stack; the check's refusal quotes
    # only the reason the page shows.
    assert any(
        report.startswith("page failed to start:") and "TypeError" in report
        for report in failed
    ), failed
    assert any(report.startswith("the runtime could not start:") for report in failed)
    assert any(
        "Browser request failed (Script, net::ERR_FAILED)" in report
        and f"in {url}:" in report
        and "/page/helper.js" in report
        for report in failed
    ), failed
    assert any(
        "Browser request returned HTTP 404 (Image)" in report
        and "/page/missing-image.png" in report
        for report in failed
    ), failed

    assert run_page_code(RoutedBrowser(fail_helper=False), url) == []


def test_plain_check_runs_the_code_a_page_authored(serve, tmp_path, headless_shell):
    """A quick page takes plain `page check` and nothing else, so that is the check
    that has to run the page's own code: a widget that throws on its first paint, or
    a load that rejects, is otherwise heard of only once the user's browser reports
    it to the watcher. The check fails on those reports, worded as the watcher gets
    them — the painter's throw names the module under `page/` that threw, not the
    widget that called it — and passes the same page once its modules run clean.

    A page without code of its own is still checked without a browser: the missing
    executable named below is never launched. A host with no browser at all, as
    leaf.page's container is, skips the run with a note rather than refusing the page,
    since the same errors reach the author as `error` events once a browser draws it."""
    serve(
        LONG_PAGE,
        page_files={
            "registry.json": json.dumps(FILM_DECLARATION),
            "film.js": "export const paint = (el, step) =>\n"
            "  (el.textContent = (step.cmp ?? []).map(String).join());\n",
            "widgets/lf-film.js": 'import { paint } from "../film.js";\n'
            "customElements.define('lf-film', class extends HTMLElement {\n"
            "  connectedCallback() { paint(this, { cmp: 3 }); }\n"
            "});\n",
            "widgets/lf-loader.js": "customElements.define('lf-loader', class extends HTMLElement {\n"
            "  connectedCallback() { this.load(); }\n"
            "  async load() { await null; throw new Error('the trace never loaded'); }\n"
            "});\n",
        },
    )
    d = serve.page_dir

    def check(**env):
        return subprocess.run(
            [*LEAF_COMMAND, "page", "check", str(d)],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | env,
        )

    no_browser = check(LEAF_BROWSER_EXECUTABLE=str(tmp_path / "not-a-browser"))
    assert no_browser.returncode == 0, no_browser.stdout + no_browser.stderr
    assert "page code" not in no_browser.stdout + no_browser.stderr

    (d / "index.html").write_text(FILM_PAGE)
    broken = check(LEAF_BROWSER_EXECUTABLE=headless_shell)
    assert broken.returncode == 1, broken.stdout + broken.stderr
    assert "Error: page code reported 2 errors" in broken.stderr
    assert "map is not a function" in broken.stderr
    assert "at paint (" in broken.stderr
    assert "/page/film.js:2:" in broken.stderr
    assert "Error: the trace never loaded" in broken.stderr
    assert "/page/widgets/lf-loader.js:3" in broken.stderr

    unrun = check(LEAF_BROWSER_EXECUTABLE=str(tmp_path / "not-a-browser"))
    assert unrun.returncode == 0, unrun.stdout + unrun.stderr
    assert "· page code: not run, no browser launched: " in unrun.stderr

    (d / "page" / "film.js").write_text(
        "export const paint = (el, step) =>\n"
        "  (el.textContent = [step.cmp].flat().map(String).join());\n"
    )
    (d / "page" / "widgets" / "lf-loader.js").write_text(
        "customElements.define('lf-loader', class extends HTMLElement {\n"
        "  connectedCallback() { this.textContent = 'loaded'; }\n"
        "});\n"
    )
    clean = check(LEAF_BROWSER_EXECUTABLE=headless_shell)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert f"✓ page code: no errors in {headless_shell}" in (clean.stdout)
