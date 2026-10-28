"""How a page dresses what it shows: authored paint before the runtime, link treatment
and reduced motion beyond light DOM, reading regions, and the effective colour
scheme."""

import re

import pytest
from interact_support import wait_for
from playwright.sync_api import expect
from render_cases_interaction import SHORT_SUGGESTION, live_url
from render_cases_navigation import DATA_PROJECTION_MODULE, data_projection_page
from render_harness import (
    PANEL,
    displayed,
    leaf_page,
    open_page,
    stamp_page,
    wait_for_revision,
    watched,
)

from leaf import data as data_model
from leaf import user_views as user_views_model
from leaf.render_checks import wait_until_ready
from leaf.schema import ELEMENT_ID

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize(
    ("width", "has_touch"), [(390, True), (740, True), (800, False), (1724, False)]
)
def test_authored_html_paints_while_runtime_startup_is_held(
    browser, serve, width, has_touch
):
    """Immediate authored paint is the contract for every page, not an example mode.
    No chrome stands over the window's head, so the page starts at its top."""
    boot = []
    context = browser.new_context(
        viewport={"width": width, "height": 900}, has_touch=has_touch
    )
    page = context.new_page()
    watched(page)
    page.route("**/leaf.js", lambda route: boot.append(route))

    try:
        with page.expect_request("**/leaf.js"):
            page.goto(
                serve(leaf_page("Startup", "<h1>Startup</h1>")),
                wait_until="commit",
            )
        displayed(page)
        expect(page.locator("h1")).to_be_visible()
        assert page.locator("h1").evaluate(
            "element => element.checkVisibility({"
            "opacityProperty: true, visibilityProperty: true})"
        ), "authored words occupied a box but did not paint"

        assert boot, "the positive control did not hold the preview boot module"
        expect(page.locator("html")).to_have_attribute("data-lf-live", "")
        expect(page.locator("body > main")).to_have_css("pointer-events", "auto")
        initial = page.locator("body > main").bounding_box()
        assert initial["y"] == pytest.approx(0, abs=1)
        assert page.locator("body").bounding_box()["height"] == pytest.approx(
            900, abs=1
        )
        assert (
            page.evaluate("() => getComputedStyle(document.body, '::after').content")
            == "none"
        ), "a startup sheet replaced the authored document before runtime arrived"

        boot.pop().continue_()
        wait_until_ready(page)
        presented = page.locator("body > main").bounding_box()
        assert {key: presented[key] for key in ("x", "y", "width")} == pytest.approx(
            {key: initial[key] for key in ("x", "y", "width")}, abs=1
        ), f"runtime startup moved the {width}px shell"
        assert page.locator("body").bounding_box()["height"] == pytest.approx(
            900, abs=1
        )
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_external_link_geometry_is_complete_before_runtime_startup(browser, serve):
    """The inline mark must not rewrap prose when the module graph arrives."""
    source = leaf_page(
        "External link",
        '<h1>Read the change</h1><p id="copy">'
        '<a id="link" href="https://example.com/change" target="_self" rel="author">'
        "Pull request with <strong>evidence</strong></a> "
        '<span id="after">adopted the boundary. The runner checkout remains stable, '
        "the supervisor owns the sandbox process tree, and bounded files cross back."
        "</span></p>",
    )
    boot = []
    page = browser.new_page(viewport={"width": 678, "height": 900})
    page.route("**/leaf.js", lambda route: boot.append(route))
    geometry = """() => {
      const range = document.createRange();
      range.selectNodeContents(document.querySelector('#after'));
      return [...range.getClientRects()].map(rect => rect.toJSON());
    }"""
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(serve(source), wait_until="commit")
        displayed(page)
        expect(page.locator("#copy")).to_be_visible()
        before = page.evaluate(geometry)
        assert before, "the authored words did not have visible geometry"
        assert boot, "the positive control did not hold the boot module"
        authored = page.locator("#link").evaluate(
            "link => document.documentElement.lfInitial.authoredCopy(link).outerHTML"
        )
        assert authored == (
            '<a id="link" href="https://example.com/change" target="_self" rel="author">'
            "Pull request with <strong>evidence</strong></a>"
        )
        boot.pop().continue_()
        wait_until_ready(page)
        expect(page.locator("#link > svg.lf-external-mark")).to_be_visible()
        expect(page.locator("#link")).to_have_attribute("target", "_blank")
        assert page.evaluate(geometry) == before
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_a_later_map_only_sidebar_keeps_its_flow_spacing_before_startup(browser, serve):
    source = leaf_page(
        "Later contents",
        """
<h1>Contents</h1>
<aside class="sidebar">First sidebar</aside>
<p>Before the later outline.</p>
<aside class="sidebar" id="later"><lf-toc id="contents"></lf-toc></aside>
<h2 id="after">After the outline</h2>
""",
    )
    boot = []
    page = browser.new_page(viewport={"width": 1724, "height": 900})
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(serve(source), wait_until="commit")
        displayed(page)
        assert boot, "the positive control did not hold the boot module"
        later = page.locator("#later")
        expect(later).to_have_css("display", "flow-root")
        expect(later).to_have_css("margin-top", "24px")
        expect(later).to_have_css("margin-bottom", "30px")

        boot.pop().continue_()
        wait_until_ready(page)
        expect(later).to_have_css("display", "flow-root")
        expect(later).to_have_css("margin-bottom", "30px")
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_a_sample_starts_without_its_host_s_saved_chrome(browser, serve):
    """The reader's chrome preference, the panel folded to the leaf, is saved for every
    page on the origin, but an isolated sample's child page starts without inheriting
    it: the child's panel stands at its row while its host's stays folded."""
    content = (
        '<lf-sample id="practice" label="Practice">'
        '<template id="practice-source" data-sample>'
        "<h1>Practice</h1><p>A sentence to practise on.</p>"
        "</template></lf-sample>"
    )
    url = serve(leaf_page("Folded host", content))
    context = browser.new_context(viewport={"width": 1600, "height": 900})
    priming = context.new_page()
    priming.goto(url, wait_until="load")
    priming.evaluate(
        "() => document.documentElement.lfStorage.userStore.set('lf-chrome-rest', 'mark')"
    )
    priming.close()

    host = context.new_page()
    host.goto(url, wait_until="load")
    wait_until_ready(host.locator("#practice iframe").element_handle().content_frame())
    expect(host.locator(PANEL)).to_have_attribute("data-rest", "mark")
    child = host.frame_locator("#practice iframe")
    expect(child.locator(PANEL)).to_have_attribute("data-rest", "row")


def test_a_projected_external_link_gets_the_pages_link_treatment(browser, serve):
    """A data renderer runs after the initial page dressing, but what it contributes
    is still part of the Leaf and should carry the same visible navigation contract."""
    url = data_projection_page(serve)
    # The page's own module for the family, which takes the package's place.
    module = serve.page_dir / "page" / "widgets" / "lf-feed.js"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(
        DATA_PROJECTION_MODULE.replace("{keeps,", "{keeps, keepsText,").replace(
            "const row = document.createElement('p');\n"
            "      row.append(words, offer('button', 'inspect', 'Inspect'));",
            """const prior = [...this.children].find(row => row.dataset.lfDatum === key);
      const row = prior ?? document.createElement('p');
      const link = row.querySelector('a') ?? document.createElement('a');
      keeps(link, 'href', words === 'Ready' ? 'https://example.com/status' : '#title');
      keepsText(link, words);
      if (!prior) {
        link.target = '_self';
        link.rel = 'author';
        row.append(link, offer('button', 'inspect', 'Inspect'));
      }""",
        )
    )
    stamp_page(
        serve.page_dir,
        (serve.page_dir / "index.html").read_text(),
        "capture the projected-link renderer",
    )

    page = open_page(browser, live_url(url))
    links = page.locator('#deployments a[href="https://example.com/status"]')
    expect(links).to_have_count(2)
    expect(links.first).to_have_attribute("target", "_blank")
    expect(links.first.locator(":scope > svg.lf-external-mark")).to_be_visible()
    api = page.locator('[data-lf-datum="api"] a')
    api.evaluate("link => { link.target = '_parent'; link.rel = 'author next'; }")
    expect(api).to_have_attribute("target", "_blank")
    expect(api).to_have_attribute(
        "rel", re.compile(r"(?=.*\bnext\b)(?=.*\bnoopener\b)")
    )

    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [
            {"key": "api", "value": "Running"},
            {"key": "worker", "value": "Ready"},
        ],
    )
    expect(api).to_have_attribute("href", "#title")
    expect(api).to_have_attribute("target", "_parent")
    expect(api).to_have_attribute("rel", "author next")
    expect(api).not_to_have_attribute("aria-describedby", re.compile(".+"))
    expect(api.locator(":scope > .lf-external-mark")).to_have_count(0)

    worker = page.locator('[data-lf-datum="worker"] a')
    detached_worker = worker.element_handle()
    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [{"key": "api", "value": "Running"}],
    )
    expect(worker).to_have_count(0)
    assert detached_worker.evaluate(
        """link => ({
          target: link.getAttribute('target'),
          rel: link.getAttribute('rel'),
          describedBy: link.getAttribute('aria-describedby'),
          mark: link.querySelector('.lf-external-mark'),
        })"""
    ) == {"target": "_self", "rel": "author", "describedBy": None, "mark": None}

    api.evaluate("link => { link.href = 'https://example.com/again'; }")
    expect(api).to_have_attribute("target", "_blank")
    detached_api = api.element_handle()
    detached_api.evaluate("link => { link.href = '#title'; link.remove(); }")
    assert detached_api.evaluate(
        """link => ({
          target: link.getAttribute('target'),
          rel: link.getAttribute('rel'),
          describedBy: link.getAttribute('aria-describedby'),
          mark: link.querySelector('.lf-external-mark'),
        })"""
    ) == {"target": "_parent", "rel": "author next", "describedBy": None, "mark": None}


@pytest.mark.parametrize("initial_motion", ["no-preference", "reduce"])
def test_reduced_motion_reaches_declared_shadow_stages(
    browser, serve, tmp_path, initial_motion
):
    """Package CSS has the same motion guard in the document and a declared tree.

    The ordinary-motion control proves the package's animation and transition really
    run. Both a preference held at navigation and one changed in the live document
    must finish the animation once and make the next state change immediate.
    """
    entry = {
        "description": "A package motion control.",
        "type": "object",
        "properties": {"id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
    }
    registry = {
        tag: {
            **entry,
            **({"x-shadow": True} if tree == "shadow" else {}),
            "x-example": f'<{tag} id="{tree}-example"></{tag}>',
        }
        for tree, tag in (("light", "lf-motion-light"), ("shadow", "lf-motion-shadow"))
    }
    package = tmp_path / ".leaf"
    package.mkdir()
    # The sheet reaches both trees and names each widget it styles: by tag in the
    # document, by its host in the shadow tree.
    (package / "widget-shadow.css").write_text("""
lf-motion-light .pulse, :host(lf-motion-shadow) .pulse {
  animation: package-pulse 30s linear infinite;
}
lf-motion-light .pulse::before, :host(lf-motion-shadow) .pulse::before {
  content: 'Activity'; animation: package-pulse 30s linear infinite;
}
@keyframes package-pulse { from { opacity: .25; } to { opacity: 1; } }
lf-motion-light button, :host(lf-motion-shadow) button {
  transition: background-color 30s linear; background-color: rgb(10, 20, 30);
}
lf-motion-light button.chosen, :host(lf-motion-shadow) button.chosen {
  background-color: rgb(40, 50, 60);
}
""")
    modules = {}
    for tag, declaration in registry.items():
        stage = (
            "shadowStage(this, nodes)"
            if declaration.get("x-shadow")
            else "this.replaceChildren(...nodes)"
        )
        modules[f"{tag}.js"] = f"""
import {{ once, shadowStage }} from '/runtime/widget-api.js';
customElements.define('{tag}', class extends HTMLElement {{
  connectedCallback() {{
    if (!once(this)) return;
    const pulse = document.createElement('span'); pulse.className = 'pulse';
    pulse.textContent = 'Working';
    pulse.ends = [];
    pulse.addEventListener('animationend', event => pulse.ends.push(event.pseudoElement));
    const button = document.createElement('button'); button.textContent = 'Choose';
    button.onclick = () => button.classList.toggle('chosen');
    const nodes = [pulse, button];
    {stage};
  }}
}});
"""
    url = serve(
        leaf_page(
            "Package motion",
            '<h1>Package motion</h1><lf-motion-light id="light"></lf-motion-light>'
            '<lf-motion-shadow id="shadow"></lf-motion-shadow>',
        ),
        layer_registry=registry,
        layer_widgets=modules,
    )
    page = open_page(
        browser, url, context=browser.new_context(reduced_motion=initial_motion)
    )
    if initial_motion == "no-preference":
        for tree in ("light", "shadow"):
            pulse = page.locator(f"#{tree} .pulse")
            expect(pulse).to_have_css("animation-iteration-count", "infinite")
            assert (
                pulse.evaluate("node => node.getAnimations({subtree: true}).length")
                == 2
            )
            button = page.locator(f"#{tree} button")
            expect(button).to_have_css("transition-duration", "30s")
            button.click()
            assert button.evaluate("node => node.getAnimations().length") == 1
            button.click()
        page.emulate_media(reduced_motion="reduce")
    for tree in ("light", "shadow"):
        pulse = page.locator(f"#{tree} .pulse")
        button = page.locator(f"#{tree} button")
        button.click()
        reading = button.evaluate("""node => ({
            transition: getComputedStyle(node).transitionProperty,
            colour: getComputedStyle(node).backgroundColor,
            animations: node.getAnimations().length,
        })""")
        assert reading == {
            "transition": "none",
            "colour": "rgb(40, 50, 60)",
            "animations": 0,
        }
        expect(pulse).to_have_css("animation-iteration-count", "1")
        page.wait_for_function(
            "tree => { const host = document.getElementById(tree); "
            "return (host.shadowRoot ?? host).querySelector('.pulse').ends.length === 2; }",
            arg=tree,
        )
        assert pulse.evaluate("node => node.getAnimations({subtree: true}).length") == 0
    page.emulate_media(reduced_motion="no-preference")
    for tree in ("light", "shadow"):
        pulse = page.locator(f"#{tree} .pulse")
        expect(pulse).to_have_css("animation-iteration-count", "infinite")
        assert pulse.evaluate("node => node.getAnimations({subtree: true}).length") == 2
        expect(page.locator(f"#{tree} button")).to_have_css(
            "transition-duration", "30s"
        )


def test_settled_and_shadow_links_get_the_pages_link_treatment(browser, serve):
    """The widget lifecycle has two presentation boundaries outside authored light DOM:
    async work finishes after the first dress, and declared shadow words live beyond it."""
    entry = {
        "description": "A project-supplied link.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
    }
    settled = {**entry, "x-example": '<lf-settled-link id="settled"></lf-settled-link>'}
    shadow = {
        **entry,
        "x-shadow": True,
        "x-example": '<lf-shadow-link id="shadow"></lf-shadow-link>',
    }
    authored = leaf_page(
        "late links",
        """
<h1>Late links</h1>
<lf-settled-link id="settled"></lf-settled-link>
<lf-shadow-link id="shadow"></lf-shadow-link>
""",
    )
    url = live_url(
        serve(
            authored,
            layer_registry={"lf-settled-link": settled, "lf-shadow-link": shadow},
            layer_widgets={
                "lf-settled-link.js": """
import {once, widgetController} from '/runtime/widget-api.js';
customElements.define('lf-settled-link', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    widgetController(this).present(new Promise(resolve => setTimeout(() => {
      const link = document.createElement('a');
      link.id = 'settled-link';
      link.href = 'https://example.com/settled';
      link.textContent = 'settled destination';
      this.replaceChildren(link);
      resolve();
    }, 25)));
  }
});
""",
                "lf-shadow-link.js": """
import {once, shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-shadow-link', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const button = document.createElement('button');
    button.textContent = 'Show shadow link';
    button.onclick = () => {
      const link = document.createElement('a');
      link.id = 'shadow-link';
      link.href = 'https://example.com/shadow';
      link.textContent = 'shadow destination';
      this.shadowRoot.append(link);
    };
    shadowStage(this, [button]);
  }
});
""",
            },
        )
    )

    page = open_page(browser, url)
    settled_link = page.locator("#settled-link")
    page.get_by_role("button", name="Show shadow link").click()
    shadow_link = page.locator("#shadow-link")
    for link, name in (
        (settled_link, "settled destination"),
        (shadow_link, "shadow destination"),
    ):
        expect(link).to_have_attribute("target", "_blank")
        expect(link).to_have_accessible_name(name)
        expect(link).to_have_accessible_description("opens in a new tab")
        expect(link.locator(":scope > svg.lf-external-mark")).to_be_visible()
    expect(shadow_link.locator(":scope > .lf-external-mark")).to_have_css(
        "display", "inline-block"
    )

    stamp_page(serve.page_dir, authored.replace("Late links", "Later links"), "later")
    wait_for_revision(page, 2)
    expect(page.locator("#settled-link")).to_have_accessible_name("settled destination")
    expect(page.locator("#settled-link")).to_have_accessible_description(
        "opens in a new tab"
    )


def test_reading_regions_read_scroll_behavior_from_the_stylesheet_and_announce_a_shift(
    browser, serve
):
    """A region is bounded exactly when the stylesheet makes its body scroll, a flowing
    region is carried by the one containing it, and a scroller change is announced once
    the new geometry exists. Nothing is told the scroll behavior: a class stands in for the
    container query that decides it on a page."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    readings = page.evaluate(
        """async () => {
          const leaf = await Promise.all([window.__lfWidgetApi(),window.__lfCheckApi()]).then(parts=>Object.assign({},...parts));
          const frames = () => new Promise(resolve =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)));
          const main = document.querySelector('main');
          const outer = document.createElement('section');
          outer.id = 'outer-host';
          outer.innerHTML = `
            <header><button id="pane-heading">Pane heading</button></header>
            <div id="outer-body"><section id="preview-host">
              <div id="preview-body">${'<p>Preview body</p>'.repeat(20)}</div>
            </section>${'<p>Outer body</p>'.repeat(20)}</div>`;
          main.append(outer);
          const outerBody = outer.querySelector('#outer-body');
          const previewHost = outer.querySelector('#preview-host');
          const previewBody = outer.querySelector('#preview-body');
          const style = document.createElement('style');
          style.textContent = `
            .held #outer-body { height: 280px; overflow: auto; }
            .held #preview-body { height: 120px; overflow: auto; }
            .held.preview-flows #preview-body { height: auto; overflow: visible; }`;
          document.head.append(style);

          const previewId = leaf.compoundReadingRegionId(outer, 'preview');
          const scrollerName = (scroller) =>
            scroller === document.scrollingElement ? 'document' : scroller.id;
          const shifts = [];
          let shifted = () => {};
          const unwatch = leaf.watchReadingRegionTransitions((event) => {
            if (event.phase !== 'shift') return;
            shifts.push(event.shifted.map(({region, from, to}) =>
              [region.id, scrollerName(from), scrollerName(to)]).sort());
            shifted();
          });
          const nextShift = () => new Promise(resolve => { shifted = resolve; });
          const stopOuter = leaf.registerReadingRegion(
            {id: 'outer-pane', host: outer, body: outerBody});
          const stopPreview = leaf.registerReadingRegion(
            {id: previewId, host: previewHost, body: previewBody});
          await frames();
          const flow = {
            outer: scrollerName(leaf.effectiveScroller('outer-pane')),
            preview: scrollerName(leaf.effectiveScroller(previewId)),
            scroll_behavior: leaf.regionScrollBehavior(previewId),
          };

          // Each change waits out the frame its shift was announced in, so the next
          // resize is not one the observer's own delivery is still settling.
          let shift = nextShift();
          outer.classList.add('held');
          await shift;
          await frames();
          const held = {
            outer: scrollerName(leaf.effectiveScroller('outer-pane')),
            preview: scrollerName(leaf.effectiveScroller(previewId)),
            scroll_behavior: leaf.regionScrollBehavior(previewId),
            focusRegion: leaf.readingRegionFor(outer.querySelector('#pane-heading')).id,
          };

          shift = nextShift();
          outer.classList.add('preview-flows');
          await shift;
          await frames();
          const previewFlows = {
            preview: scrollerName(leaf.effectiveScroller(previewId)),
            scroll_behavior: leaf.regionScrollBehavior(previewId),
          };

          // Hidden until it is removed below.
          previewHost.hidden = true;
          const { shownRegionBounds } = await window.__lfCheckApi();
          const hiddenBounds = shownRegionBounds(previewId);

          let refused;
          try {
            leaf.registerReadingRegion({id: previewId, host: outer, body: outerBody});
          } catch (error) {
            refused = error.message;
          }
          previewHost.remove();
          const replacement = document.createElement('section');
          replacement.innerHTML = '<div>Replacement</div>';
          outerBody.append(replacement);
          const reclaim = leaf.registerReadingRegion({
            id: previewId,
            host: replacement,
            body: replacement.firstElementChild,
          });
          const reclaimed = leaf.readingRegion(previewId).host === replacement;

          // A second composition change supersedes an unfinished first: both announce
          // their start, and only the newer one reports where it ended.
          const phases = [];
          const unwatchPhases = leaf.watchReadingRegionTransitions((event) => {
            if (event.phase !== 'shift') phases.push([event.phase, !!event.retained]);
          });
          let release;
          const first = leaf.preserveReadingRegions(
            outer, () => new Promise(resolve => { release = resolve; }));
          const second = leaf.preserveReadingRegions(outer, async () => {});
          await second;
          release();
          await first;

          unwatchPhases();
          reclaim();
          stopPreview();
          stopOuter();
          unwatch();
          outer.remove();
          style.remove();
          return {flow, held, previewFlows, shifts, hiddenBounds, refused, reclaimed,
                  phases};
        }"""
    )
    assert readings["flow"] == {
        "outer": "document",
        "preview": "document",
        "scroll_behavior": "flow",
    }
    assert readings["held"] == {
        "outer": "outer-body",
        "preview": "preview-body",
        "scroll_behavior": "bounded",
        "focusRegion": "outer-pane",
    }
    assert readings["previewFlows"] == {
        "preview": "outer-body",
        "scroll_behavior": "flow",
    }
    preview = "lf-region:outer-host:preview"
    assert readings["shifts"] == [
        [
            [preview, "document", "preview-body"],
            ["outer-pane", "document", "outer-body"],
        ],
        [[preview, "preview-body", "outer-body"]],
    ]
    assert readings["hiddenBounds"] is None
    assert readings["refused"] == f"leaf: reading region {preview} is already live"
    assert readings["reclaimed"] is True
    assert readings["phases"] == [
        ["before", False],
        ["before", True],
        ["after", False],
    ]


def test_a_pane_registers_the_body_it_holds_across_moves_and_revisions(browser, serve):
    """A pane's region is its one body element: replacing the body re-registers the same
    id, leaving the document retires it, and returning restores it with the user's
    draft untouched, since no wrapper is built around what the author wrote."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "a pane that moves",
                """
<h1>Moving pane</h1>
<lf-pane id="moving-pane" label="Moving pane"><header>Heading</header><div id="first-body"><input value="Authored"></div></lf-pane>
""",
            )
        ),
    )
    result = page.evaluate(
        """async () => {
          const leaf = await Promise.all([window.__lfWidgetApi(),window.__lfCheckApi()]).then(parts=>Object.assign({},...parts));
          const main = document.querySelector('main');
          const pane = document.querySelector('#moving-pane');
          const first = leaf.readingRegion('moving-pane')?.body.id;
          const authored = [...pane.childNodes];

          const next = document.createElement('div');
          next.id = 'second-body';
          next.innerHTML = '<input value="Authored">';
          pane.querySelector('#first-body').replaceWith(next);
          await new Promise(resolve => setTimeout(resolve));
          const replaced = leaf.readingRegion('moving-pane')?.body.id;

          pane.querySelector('input').value = 'User draft';
          pane.remove();
          const retired = leaf.readingRegion('moving-pane') === undefined;
          main.append(pane);
          const restored = leaf.readingRegion('moving-pane')?.body.id;
          const value = pane.querySelector('input').value;
          const label = pane.getAttribute('aria-label');
          pane.remove();
          return {first, replaced, retired, restored, value, label,
                  unwrapped: authored[0] === pane.firstChild};
        }"""
    )
    assert result == {
        "first": "first-body",
        "replaced": "second-body",
        "retired": True,
        "restored": "second-body",
        "value": "User draft",
        "label": "Moving pane",
        "unwrapped": True,
    }


def test_user_view_context_reads_the_documents_forced_scheme(browser, serve):
    """The effective document scheme can override the user's OS preference."""
    source = leaf_page(
        "Forced scheme",
        '<h1 id="heading">A dark document</h1>',
        head="<style>:root { color-scheme: only dark; }</style>",
    )
    context = browser.new_context(color_scheme="light")
    open_page(browser, serve(source), context=context)
    observed = wait_for(
        lambda: user_views_model.read_user_views(serve.page_dir, 1)["sessions"],
        lambda records: bool(records) and records[0]["checks"] is not None,
        failure="the forced document scheme never reached the agent view",
    )[0]
    assert observed["color_scheme"] == "dark"
    assert observed["checks"]["color_scheme"] == "dark"
