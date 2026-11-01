"""What every widget shares: its fallback face before it renders, detaching and
reconnecting, the controls it offers, and the Web Awesome library they come from."""

import re

import pytest
from interact_support import append_command
from playwright.sync_api import expect
from render_cases_interaction import CHIP_PAGE
from render_cases_layout import rings_drawn
from render_harness import ROOT, displayed, leaf_page, open_page, told

from browser.widgets import (
    _bound_diff,
)
from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_source_widget_releases_its_fallback_face_when_it_renders(browser, serve):
    """A data package needs no rendered reset, in the document or a shadow stage."""
    source = {
        "description": "Source that a reader draws.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "data",
        "x-upgrade": True,
    }
    stage = {**source, "x-content": "markup", "x-shadow": True}
    url = serve(
        leaf_page(
            "Source states",
            '<h1>Source states</h1><p id="document-face">Document words.</p>'
            '<lf-source-view id="document"><pre>source data</pre></lf-source-view>'
            '<lf-source-stage id="stage"><p id="stage-face">Stage words.</p>'
            '<lf-source-view id="nested"><pre>source data</pre></lf-source-view>'
            "</lf-source-stage>"
            '<lf-code id="code" language="python"><pre>print(1)</pre></lf-code>'
            '<lf-diagram id="diagram"><pre>flowchart LR\nA --> B</pre></lf-diagram>'
            '<lf-diff id="diff"><pre>diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n'
            "@@ -1 +1 @@\n-old\n+new\n</pre></lf-diff>",
        ),
        layer_registry={"lf-source-view": source, "lf-source-stage": stage},
        layer_widgets={
            "lf-source-view.js": """
customElements.define('lf-source-view', class extends HTMLElement {
  connectedCallback() {
    if (this.querySelector('button')) return;
    const button = document.createElement('button');
    button.textContent = 'Draw source';
    button.addEventListener('click', () => {
      const drawing = document.createElement('span');
      drawing.textContent = 'Rendered evidence';
      this.replaceChildren(drawing);
      this.classList.add('lf-rendered');
    });
    this.querySelector('pre').append(button);
  }
});
""",
            "lf-source-stage.js": """
import {shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-source-stage', class extends HTMLElement {
  connectedCallback() {
    if (!this.shadowRoot) shadowStage(this, [...this.childNodes]);
  }
});
""",
        },
    )
    face = """el => {
      const style = getComputedStyle(el);
      return {font: style.fontFamily, size: style.fontSize,
        line: style.lineHeight, color: style.color, overflow: style.overflowX};
    }"""
    page = browser.new_page()
    boot = []
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(url, wait_until="commit")
        displayed(page)
        fallback = page.locator("#document").evaluate(face)
        typography = ("font", "size", "line", "color")
        for widget_id in ("code", "diagram", "diff"):
            widget = page.locator(f"#{widget_id}")
            expect(widget).not_to_have_class(re.compile("lf-rendered"))
            expect(widget.locator("pre")).to_be_visible()
            assert widget.locator("pre").evaluate(
                "el => el.checkVisibility({opacityProperty: true, visibilityProperty: true})"
            ), widget_id
            actual = widget.evaluate(face)
            # Packages own layout: an inline diff clips its reserved first-paint
            # box. The shared source primitive supplies the readable type.
            assert {key: actual[key] for key in typography} == {
                key: fallback[key] for key in typography
            }, widget_id
        assert len(boot) == 1, "the preview runtime was not held before widget upgrade"
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")
    wait_until_ready(page)
    expect(page.locator("#diff")).to_have_class(re.compile("lf-rendered"))
    expect(page.locator("#diff")).to_have_css("font-family", fallback["font"])
    for widget_id in ("code", "diagram"):
        assert (
            page.locator(f"#{widget_id}").evaluate(face)["font"]
            == page.locator("#document-face").evaluate(face)["font"]
        )
    drawings = {}
    references = {}
    for widget_id, reference_id in (
        ("document", "document-face"),
        ("nested", "stage-face"),
    ):
        widget = page.locator(f"#{widget_id}")
        reference = page.locator(f"#{reference_id}").evaluate(face)
        fallback = widget.evaluate(face)
        assert fallback["font"] != reference["font"], fallback
        assert fallback["color"] != reference["color"], fallback
        assert fallback["overflow"] == "auto", fallback
        widget.get_by_role("button", name="Draw source").click()
        expect(widget).to_have_class(re.compile(r"\blf-rendered\b"))
        drawings[widget_id] = widget.evaluate(face)
        references[widget_id] = reference
    assert drawings == references


def test_live_widget_subscription_releases_and_reconnects(browser, serve):
    """A detached widget ignores semantic news and catches up when reconnected."""
    source = leaf_page(
        "widget watcher lifecycle",
        """
<section id="watched">
  <lf-draft id="watched-draft"><pre>Draft words.</pre></lf-draft>
</section>
""",
    )
    page = open_page(browser, serve(source))
    before = page.locator("#watched-draft .lf-draft-body").get_attribute(
        "data-lf-source-words"
    )
    page.evaluate(
        """() => {
          window.__lfWatchedSection = document.querySelector('#watched');
          window.__lfWatchedSection.remove();
        }"""
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "watched-draft",
            "action": "edit",
            "detail": {"value": "Reconnected words."},
        },
    )
    told(page)
    assert (
        page.evaluate("""() => window.__lfWatchedSection
      .querySelector('#watched-draft .lf-draft-body')
      .getAttribute('data-lf-source-words')""")
        == before
    )

    page.evaluate("document.querySelector('main').append(window.__lfWatchedSection)")
    expect(page.locator("#watched-draft .lf-draft-body")).to_have_text(
        "Reconnected words."
    )


def library_select(browser, serve):
    """Exercise the optional library's select without depending on a consumer's UI."""
    page = _bound_diff(browser, serve)
    page.evaluate("""async () => {
      const {offer} = await window.__lfWidgetApi();
      const select = offer('wa-select', 'library-select');
      select.label = 'Choose file';
      for (const value of ['first', 'second', 'third']) {
        const option = offer('wa-option', '', value);
        option.value = value; select.append(option);
      }
      select.value = 'first';
      document.querySelector('main').prepend(select);
      await select.updateComplete;
    }""")
    return page


def open_library_select(page):
    control = page.locator(".library-select")
    control.evaluate("""node => {
      node.menuShown = new Promise(resolve => node.addEventListener(
        'wa-after-show', resolve, {once: true}));
    }""")
    control.get_by_role("combobox").click()
    control.evaluate("node => node.menuShown")
    page.mouse.move(0, 0)


def test_webawesome_chrome_loads_without_optional_controls(browser, serve):
    plain = open_page(browser, serve(leaf_page("Plain", "<h1>Plain page</h1>")))
    assert (
        plain.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--wa-space-scale').trim()"
        )
        == "1"
    )
    assert not any(
        entry.endswith("/vendor/webawesome.esm.js")
        for entry in plain.evaluate(
            "() => performance.getEntriesByType('resource').map(entry => entry.name)"
        )
    )

    assert plain.evaluate("() => customElements.get('wa-input') !== undefined")
    assert plain.evaluate("() => customElements.get('wa-slider') === undefined")

    page = library_select(browser, serve)
    control = page.locator(".library-select")
    # A page rule with no specificity at all can outrank
    # the shared theme's `:is(wa-select, …)` mapping.
    page.evaluate(
        """() => {
          const style = document.createElement('style');
          style.textContent = ':where(wa-select){--wa-color-text-quiet: rgb(1, 2, 3);}';
          document.head.append(style);
        }"""
    )
    assert (
        control.evaluate(
            "el => getComputedStyle(el).getPropertyValue('--wa-color-text-quiet')"
        ).strip()
        == "rgb(1, 2, 3)"
    ), "a page rule must outrank the lazy vendor defaults"


def test_webawesome_menu_text_stays_readable_as_the_current_option_moves(
    browser, serve
):
    """Component-owned menu states remain readable through the shared theme, in both
    schemes, read in turn on one open menu.

    The shared menu theme must keep contrasting text on a solid active row.
    """
    page = library_select(browser, serve)
    open_library_select(page)
    control = page.locator(".library-select")
    options = control.locator("wa-option")

    def contrast(option):
        colors = option.evaluate("""async node => {
          await Promise.all(node.getAnimations().map(animation => animation.finished));
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 1;
          const ctx = canvas.getContext('2d', {willReadFrequently: true});
          const rgb = color => {
            ctx.clearRect(0, 0, 1, 1);
            ctx.fillStyle = color;
            ctx.fillRect(0, 0, 1, 1);
            return [...ctx.getImageData(0, 0, 1, 1).data];
          };
          const style = getComputedStyle(node);
          return [rgb(style.color), rgb(style.backgroundColor)];
        }""")
        assert all(color[3] == 255 for color in colors), colors
        luminances = [
            sum(
                (v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) * weight
                for v, weight in zip(
                    (channel / 255 for channel in color[:3]),
                    (0.2126, 0.7152, 0.0722),
                    strict=True,
                )
            )
            for color in colors
        ]
        assert (max(luminances) + 0.05) / (min(luminances) + 0.05) >= 4.5, colors

    current = control.locator("wa-option:state(current)")
    expect(current).to_be_visible()
    contrast(current)
    initial = current.get_attribute("value")
    page.keyboard.press("ArrowDown")
    expect(current).not_to_have_attribute("value", initial)
    contrast(current)
    options.first.hover()
    contrast(options.first)
    page.emulate_media(color_scheme="dark")
    contrast(current)
    contrast(options.first)
    # Generated apparatus identity must not replace a component's state ink. This
    # catches both a generic host face and upstream root color promoted to the host;
    # merely choosing a pale menu background would let either defect survive.
    for generated in (False, True):
        current.evaluate(
            """(node, generated) => {
          node.classList.toggle('lf-ui', generated);
          node.style.setProperty('--wa-color-brand-on-loud', 'rgb(11, 22, 33)');
        }""",
            generated,
        )
        assert (
            current.evaluate("node => getComputedStyle(node).color")
            == "rgb(11, 22, 33)"
        )


def test_webawesome_typography_is_independent_of_surrounding_prose(browser, serve):
    """Shared controls keep UI text in both document and declared shadow stages.

    Reset inherited typography without taking over component sizing or state ink.
    The same inheritance also reaches an input inside the monospace diff reader.
    """
    page = _bound_diff(browser, serve)
    readings = page.evaluate("""async () => {
      const {offer} = await window.__lfWidgetApi();
      const properties = ['fontFamily', 'fontStyle', 'fontVariant', 'fontStretch',
        'fontFeatureSettings', 'fontVariationSettings', 'letterSpacing',
        'wordSpacing', 'textTransform'];
      const read = node => Object.fromEntries(
        properties.map(key => [key, getComputedStyle(node)[key]]));
      const reference = document.createElement('span');
      reference.style.fontFamily = 'var(--sans)';
      document.body.append(reference);
      const expected = read(reference);
      reference.remove();
      const readings = [];
      for (const root of [document.querySelector('main'),
        document.querySelector('lf-diff').shadowRoot]) {
        const holder = document.createElement('div');
        const input = offer('wa-input', ''); input.label = 'Find files';
        const select = offer('wa-select', ''); select.label = 'Choose file';
        const option = offer('wa-option', '', 'First file');
        option.value = 'first'; select.append(option); select.value = 'first';
        const radio = offer('wa-radio', '', 'First file'); radio.value = 'first';
        const prose = document.createElement('span'); prose.textContent = 'Source text';
        holder.append(input, select, radio, prose); root.append(holder);
        await Promise.all([input.updateComplete, select.updateComplete, radio.updateComplete]);
        holder.style.cssText = `font-family:monospace; font-style:italic;
          font-variant:small-caps; font-stretch:condensed;
          font-feature-settings:"liga" 0; font-variation-settings:"wght" 650;
          letter-spacing:3px; word-spacing:5px; text-transform:uppercase`;
        readings.push({expected, actual: [read(input.shadowRoot.querySelector('input')),
          read(select.shadowRoot.querySelector('[part~="combobox"]')), read(radio)],
          prose: read(prose)});
      }
      return readings;
    }""")
    for reading in readings:
        for actual in reading["actual"]:
            assert actual == reading["expected"]
        assert reading["prose"]["fontFamily"] == "monospace"
        assert reading["prose"]["fontStyle"] == "italic"
        assert reading["prose"]["textTransform"] == "uppercase"


@pytest.mark.parametrize("motion", ["no-preference", "reduce"])
def test_reopening_a_library_select_keeps_its_options_visible(browser, serve, motion):
    """Enter then Space reopens the menu while its close animation is running.

    Upstream 3.14.0 otherwise lets that close hide the already reopened menu.
    """
    page = library_select(browser, serve)
    page.emulate_media(reduced_motion=motion)
    open_library_select(page)
    select = page.locator(".library-select")
    select.evaluate(
        "n => { n.reopened = new Promise(r => n.addEventListener('wa-after-show', r, {once:true})); }"
    )
    page.keyboard.press("Enter")
    page.keyboard.press("Space")
    select.evaluate("n => n.reopened.then(() => true)")
    expect(select.locator("wa-option:state(current)")).to_be_visible()
    assert select.evaluate("n => n.open && n.popup.active && !n.listbox.hidden")
    page.keyboard.press("Escape")


def test_library_copy_feedback_finishes_after_its_tooltip_reopens(browser, serve):
    """The copy button consumes the tooltip's completion to release its copy lock."""
    source = ROOT / "examples" / "developer" / "visual-review-gallery.html"
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion="no-preference")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("""async () => {
      const {offer} = await window.__lfWidgetApi();
      const copy = offer('wa-copy-button', 'copy-feedback');
      copy.id = 'copy-feedback'; copy.value = 'copied value';
      copy.tooltip = 'copy'; copy.feedbackDuration = 80;
      document.body.append(copy); await copy.updateComplete;
      copy.activeTooltip.addEventListener('wa-hide', () => copy.activeTooltip.show(), {once:true});
      copy.copied = 0;
      copy.addEventListener('wa-copy', () => copy.copied++);
    }""")
    copy = page.locator("#copy-feedback")
    for copies in (1, 2):
        copy.get_by_role("button").click()
        page.wait_for_function(
            "count => document.querySelector('#copy-feedback').copied === count",
            arg=copies,
        )
        page.wait_for_function("!document.querySelector('#copy-feedback').isCopying")
        assert copy.evaluate("n => n.status === 'rest' && !n.copyIcon.hidden")


def test_a_control_a_widget_built_is_told_from_a_label_it_wrote(browser, serve):
    """One rule, read off the marker `offer` already writes, rather than each widget
    deciding for itself whether the user can press what it drew.

    The measured fault was that they could not tell: on the command hub a chip that
    opened a section and a badge that counted something computed the same ground, the
    same ink, the same 999px corner and the same 11.5px size, so the only way to learn
    which was which was to press one. That is not a fact about chips — it is what happens
    when "this is pressable" has no owner, and every widget that draws a small filled
    shape has to remember to say it again.

    So the layer says it once, against `data-lf-offer`, and the value is what it reads:
    `offer` writes the tag, input type, or role for a thing to press and the empty string
    for the rest of the chrome it builds — a controls row, a history disclosure, an edit
    box. A badge
    the page wrote carries no marker at all and needs no exclusion, which is the half
    worth pinning: the rule stays off it because the marker means what it says, not
    because a list of static classes is kept beside the rule.

    Three registers, because a pointer, a hand and a keyboard arrive by different routes
    and only one of them is on screen at rest. The hand is the resting answer, and a
    control with nothing left to do gives it up along with the face it wore while it was
    live. The face is read as that change and not as the layer's own `.55`, for the
    reason the ring below is: a control is free to dress its own spent state and outrank
    the floor, and the composer's submit does — an empty Send trades an accent disc for a
    muted ring on paper at full opacity, so that a field with nothing in it reads as
    quiet rather than as broken. Pinning the number would pin whichever of the two
    happened to be on this page. The badges are
    read outside a choose group on purpose: a card group makes the whole option the
    press, so a chip inside one inherits the hand from the control it is sitting in and
    would be answering this question about its parent. The wash is the aim, read as a
    change against each control's own resting shadow rather than against a constant: a
    control is free to wear a drop shadow of its own, and several here do, so an
    absolute reading would pin the theme's current furniture instead of the rule. The
    ring is the keyboard's, and this is the half of it a shared rule has to get right by
    losing: a control with a ring of its own keeps it and keeps its name, so what is
    asserted here is that a named ring is drawn and not which rule drew it. Which box
    wears it is a separate question from which one holds the focus - a joined option group
    draws it on the row its picks give up, and getComputedStyle(activeElement) reports
    'no ring' for a control whose ring is perfectly fine. Where nothing else claims one,
    the shared rule is what draws it, and that case is asserted on a request press in
    projection/test_current_location.py, which is where the layer has a control no widget rings."""
    page = open_page(browser, serve(CHIP_PAGE))
    state = """() => lfUnwatched(() => {
      // Whatever a control spends on saying it is live: the layer's wash, its own ink
      // and ground, and the disc a compose submit paints in its ::before.
      const face = (el) => [getComputedStyle(el), getComputedStyle(el, '::before')]
        .map((cs) => [cs.opacity, cs.color, cs.backgroundColor, cs.borderTopColor,
                      cs.filter].join(' '))
        .join(' / ');
      // The same control with the fact of being spent lifted off it, and put straight
      // back: the comparison is against what this control would wear with something
      // left to do, not against a number. The lift is the test's own write, outside
      // what the page is held to (`lfUnwatched`).
      const armed = (el) => {
        const native = el.disabled;
        const declared = el.getAttribute('aria-disabled');
        if (native) el.disabled = false;
        if (declared !== null) el.removeAttribute('aria-disabled');
        const reading = face(el);
        if (native) el.disabled = true;
        if (declared !== null) el.setAttribute('aria-disabled', declared);
        return reading;
      };
      const kind = (el) => {
        const cs = getComputedStyle(el);
        const off = el.matches('[aria-disabled="true"], :disabled');
        return {cursor: cs.cursor, opacity: cs.opacity, off,
                face: face(el), armed: off ? armed(el) : null};
      };
      const presses = [...document.querySelectorAll('[data-lf-offer]')]
        .filter((el) => el.dataset.lfOffer !== '');
      const said = [document.querySelector('#intro > .tag'),
                    document.querySelector('#owner-fact > .tag')];
      return {
        presses: presses.map(kind), said: said.map(kind),
        saidMarked: said.map((el) => el.hasAttribute('data-lf-offer')),
      };
    })"""
    rest = page.evaluate(state)
    live = [p for p in rest["presses"] if not p["off"]]
    spent = [p for p in rest["presses"] if p["off"]]
    assert live and spent and len(rest["said"]) == 2, (
        f"the page is missing one of the three populations this compares: {rest}"
    )
    assert all(p["cursor"] == "pointer" for p in live), (
        f"a control a widget built does not take the hand: {live}"
    )
    assert all(p["cursor"] == "default" and p["face"] != p["armed"] for p in spent), (
        f"a control with nothing left to do still offers itself: {spent}"
    )
    assert not any(s["cursor"] == "pointer" for s in rest["said"]), (
        "a label the page wrote takes the hand, so the user is invited to press words"
    )
    assert rest["saidMarked"] == [False, False], (
        "a static label carries the control marker, so the rule is being kept off it by "
        "an exclusion rather than by the marker meaning what it says"
    )
    # The aim. The wash is an inset shadow so that it deepens whatever fill the control
    # already wears instead of contesting the `background` its own widget wrote, which is
    # what lets it be read as an addition to whatever the control had at rest.
    shadow = "el => getComputedStyle(el).boxShadow"
    mark = page.locator("#p-keep .lf-pick")
    before = mark.evaluate(shadow)
    mark.hover()
    washed = mark.evaluate(shadow)
    assert washed != before and "inset" in washed, (
        f"the control under the pointer says nothing about being pressed: "
        f"{before!r} -> {washed!r}"
    )
    tag = page.locator("#intro > .tag")
    tag_rest = tag.evaluate(shadow)
    tag.hover()
    assert tag.evaluate(shadow) == tag_rest, (
        "a label the page wrote answers the pointer as though it were a control"
    )

    # A real Tab verifies the keyboard route as well as the shared focus treatment.
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    drawn = rings_drawn(page)
    assert any(ring["here"] and ring["sample"] and ring["rule"] for ring in drawn), (
        f"no ring rule draws a focus ring at the current keyboard location: {drawn}"
    )
