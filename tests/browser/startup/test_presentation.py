"""How a page dresses what it shows: immediate reading, link treatment
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
    holding,
    leaf_page,
    open_page,
    stamp_page,
    wait_for_revision,
    watched,
)

from browser.startup import _hold_startup
from leaf.records import page_data as page_data_model
from leaf.serving import user_views as user_views_model
from leaf.source.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize(
    ("width", "has_touch"), [(390, True), (740, True), (800, False), (1724, False)]
)
def test_the_document_is_readable_before_runtime_at_its_authored_position(
    browser, serve, width, has_touch
):
    """The page and the floating panel's row both stand from the first paint, before
    the runtime loads, and the runtime moves neither: the panel takes the row over
    with its field and leaf where the row's stood."""
    boot = []
    context = browser.new_context(
        viewport={"width": width, "height": 900}, has_touch=has_touch
    )
    page = context.new_page()
    watched(page)
    # Whether the row stood in the first frame the page drew.
    page.add_init_script("""requestAnimationFrame(() => {
      window.__rowAtFirstFrame = Boolean(
        document.querySelector('.lf-floating-panel[data-lf-served]'));
    })""")
    page.route("**/leaf.js", lambda route: boot.append(route))
    row = {part: f"{PANEL} .lf-fp-{part}" for part in ("card", "field", "leaf")}
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(
                serve(leaf_page("Startup", "<h1>Startup</h1>")), wait_until="commit"
            )
        expect(page.locator("h1")).to_be_visible()
        expect(page.locator(f"{PANEL}[data-lf-served]")).to_be_visible()
        page.wait_for_function("() => window.__rowAtFirstFrame !== undefined")
        assert page.evaluate("() => window.__rowAtFirstFrame"), "the row came late"
        initial = page.locator("body > main").bounding_box()
        served = {part: page.locator(at).bounding_box() for part, at in row.items()}
        assert boot, "the positive control did not hold the boot module"
        boot.pop().continue_()
        wait_until_ready(page)
        presented = page.locator("body > main").bounding_box()
        assert {key: presented[key] for key in ("x", "y", "width")} == pytest.approx(
            {key: initial[key] for key in ("x", "y", "width")}, abs=1
        ), "runtime startup moved the shell"
        expect(page.locator(PANEL)).to_have_count(1)
        assert {part: page.locator(at).bounding_box() for part, at in row.items()} == {
            part: pytest.approx(box, abs=1) for part, box in served.items()
        }, "the panel took the row over somewhere else"
        expect(page.locator("h1")).to_be_visible()
        assert page.locator("body > main").bounding_box()["y"] == pytest.approx(
            0, abs=1
        )
        assert page.locator("body").bounding_box()["height"] == pytest.approx(
            900, abs=1
        )
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


@pytest.mark.parametrize("kind", ["popover", "modal"])
def test_a_native_surface_opened_before_modules_stays_above_leaf(browser, serve, kind):
    """Native controls work while the runtime loads. Its arrival doesn't cover their
    surface, and geometry reads the surface above Leaf."""
    if kind == "popover":
        control = '<button id="open" popovertarget="early">Open menu</button>'
        surface = '<div id="early" popover><button popovertarget="early" popovertargetaction="hide">Close surface</button></div>'
    else:
        control = '<button id="open" commandfor="early" command="show-modal">Open dialog</button>'
        surface = '<dialog id="early"><button commandfor="early" command="close">Close surface</button></dialog>'
    source = leaf_page("Early native surface", control + surface)
    source = source.replace(
        "</head>",
        "<style>#early {position:fixed; inset:0; margin:0; width:100vw; height:100vh; max-width:none; max-height:none; background:rgb(200 20 20); border:0}</style></head>",
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    watched(page)
    held, release = _hold_startup(page, "module")
    try:
        page.goto(serve(source), wait_until="commit")
        holding(page, held, 1, "the runtime module")
        page.locator("#open").click()
        expect(page.locator("#early")).to_be_visible()
        release()
        held.clear()
        wait_until_ready(page)
        assert page.evaluate("""async () => {
          const {stackLevel} = await window.__lfCheckApi();
          const surface = document.querySelector('#early');
          const panel = document.querySelector('.lf-floating-panel');
          const rect = panel.getBoundingClientRect();
          return stackLevel(surface) > stackLevel(panel) && surface.contains(
            document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2));
        }""")
        # Its authored control stays reachable after runtime activation.
        page.get_by_role("button", name="Close surface").click()
        expect(page.locator("#early")).not_to_be_visible()
        expect(page.locator(PANEL)).to_be_visible()
    finally:
        release()
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
    priming.evaluate("() => window.lfStorage.userStore.set('lf-chrome-rest', 'mark')")
    priming.close()

    host = context.new_page()
    host.goto(url, wait_until="load")
    wait_until_ready(host.locator("#practice iframe").element_handle().content_frame())
    expect(host.locator(PANEL)).to_have_attribute("data-lf-rest", "mark")
    child = host.frame_locator("#practice iframe")
    expect(child.locator(PANEL)).to_have_attribute("data-lf-rest", "row")


def test_a_projected_external_link_wears_the_mark_its_href_earns(browser, serve):
    """A data renderer runs after the initial page dressing, and a link it draws wears
    the mark after a link that leaves the page while its href leaves it, as the page's
    own links do. The target and rel the renderer wrote stand as written."""
    url = data_projection_page(serve)
    # The page's own module for the family, which takes the package's place.
    module = serve.page_dir / "page" / "widgets" / "lf-feed.js"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(
        DATA_PROJECTION_MODULE.replace("{ keeps }", "{ keeps, keepsText }").replace(
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
    expect(links.first).to_have_attribute("data-lf-external", "")
    expect(links.first).to_have_attribute("target", "_self")
    expect(links.first).to_have_attribute("rel", "author")
    api = page.locator('[data-lf-datum="api"] a')

    page_data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [
            {"key": "api", "value": "Running"},
            {"key": "worker", "value": "Ready"},
        ],
    )
    expect(api).to_have_attribute("href", "#title")
    expect(api).not_to_have_attribute("data-lf-external", "")
    api.evaluate("link => { link.href = 'https://example.com/again'; }")
    expect(api).to_have_attribute("data-lf-external", "")
    expect(api).to_have_attribute("target", "_self")


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
        "attributes": {
            "properties": {},
            "required": ["id"],
        },
        "content": "empty",
    }
    registry = {
        tag: {
            **entry,
            **(
                {
                    "shadow": True,
                }
                if tree == "shadow"
                else {}
            ),
            "example": f'<{tag} id="{tree}-example"></{tag}>',
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
            if declaration.get("shadow")
            else "this.replaceChildren(...nodes)"
        )
        modules[f"{tag}.js"] = f"""
import {{ shadowStage }} from '/runtime/widget-api.js';
import {{ once }} from '/runtime/lib/once.js';
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


def test_settled_and_shadow_links_wear_the_pages_external_mark(browser, serve):
    """The widget lifecycle has two presentation boundaries outside authored light DOM:
    async work finishes after the first dress, and declared shadow words live beyond it."""
    entry = {
        "description": "A project-supplied link.",
        "attributes": {
            "properties": {},
            "required": ["id"],
        },
        "content": "empty",
    }
    settled = {
        **entry,
        "example": '<lf-settled-link id="settled"></lf-settled-link>',
    }
    shadow = {
        **entry,
        "shadow": True,
        "example": '<lf-shadow-link id="shadow"></lf-shadow-link>',
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
import {PendingTaskEvent} from '/runtime/lib/pending-task.js';
import {once} from '/runtime/lib/once.js';
customElements.define('lf-settled-link', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    this.dispatchEvent(new PendingTaskEvent(new Promise(resolve => setTimeout(() => {
      const link = document.createElement('a');
      link.id = 'settled-link';
      link.href = 'https://example.com/settled';
      link.textContent = 'settled destination';
      this.replaceChildren(link);
      resolve();
    }, 25))));
  }
});
""",
                "lf-shadow-link.js": """
import {shadowStage} from '/runtime/widget-api.js';
import {once} from '/runtime/lib/once.js';
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
        expect(link).to_have_accessible_name(name)
        expect(link).to_have_attribute("data-lf-external", "")
    # The mark reaches the shadow stage, where it is drawn the em wide its gap and icon
    # take, and at every width that holds the link's last word and the mark, it stays
    # on that word's line.
    assert shadow_link.evaluate(
        """link => {
          const host = link.getRootNode().host;
          const text = link.firstChild;
          const last = document.createRange();
          last.setStart(text, text.length - 1);
          last.setEnd(text, text.length);
          host.style.display = 'block';
          const apart = [];
          for (let width = 120; width <= 300; width++) {
            host.style.width = `${width}px`;
            const word = last.getBoundingClientRect();
            const mark = [...link.getClientRects()].at(-1);
            if (Math.abs(mark.top - word.top) > word.height / 2) apart.push(width);
          }
          const em = parseFloat(getComputedStyle(link).fontSize);
          const width = [...link.getClientRects()].at(-1).right - last.getBoundingClientRect().right;
          const drawn = getComputedStyle(link, '::after').maskImage !== 'none';
          return {drawn, em: Math.round(width / em * 10) / 10, apart};
        }"""
    ) == {"drawn": True, "em": 1.0, "apart": []}

    stamp_page(serve.page_dir, authored.replace("Late links", "Later links"), "later")
    wait_for_revision(page, 2)
    expect(page.locator("#settled-link")).to_have_attribute("data-lf-external", "")
    expect(page.locator("#settled-link")).to_have_accessible_name("settled destination")


def test_reading_regions_read_scroll_behavior_from_the_stylesheet_and_announce_a_shift(
    browser, serve
):
    """A box marked `data-lf-scroll="name"` is a region from the task that marks it. It
    is bounded exactly when the stylesheet makes its body scroll, a flowing region is
    carried by the one containing it, and a scroller change is announced once the new
    geometry exists. Nothing is told the scroll behavior: a class stands in for the
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
          outer.setAttribute('data-lf-scroll-host', 'pane');
          outer.innerHTML = `
            <header><button id="pane-heading">Pane heading</button></header>
            <div id="outer-body" data-lf-scroll="pane">
              <section id="preview-host" data-lf-scroll-host="preview">
                <div id="preview-body" data-lf-scroll="preview">
                  ${'<p>Preview body</p>'.repeat(20)}</div>
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
          // Each region is known in the task that put its marked box in the page, and
          // is named after its host.
          const outerId = leaf.readingRegionFor(outerBody).id;
          const previewId = leaf.readingRegionFor(previewBody).id;
          await frames();
          const flow = {
            outer: scrollerName(leaf.effectiveScroller(outerId)),
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
            outer: scrollerName(leaf.effectiveScroller(outerId)),
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

          // A second box the same host names alike is a region too, under an id of
          // this document alone: the first keeps the name.
          const twin = document.createElement('div');
          twin.setAttribute('data-lf-scroll', 'pane');
          outer.querySelector('header').append(twin);
          const twinId = leaf.readingRegions().find(({body}) => body === twin)?.id;
          const kept = leaf.readingRegion(outerId).body === outerBody;
          twin.remove();

          // A box that replaces another takes the id the other held, in one task.
          previewHost.remove();
          const replacement = document.createElement('section');
          replacement.id = 'preview-host';
          replacement.setAttribute('data-lf-scroll-host', 'preview');
          replacement.innerHTML = '<div data-lf-scroll="preview">Replacement</div>';
          outerBody.append(replacement);
          const reclaimed = leaf.readingRegion(previewId).host === replacement;

          // A host marked after its body's region was read becomes that region's host.
          const late = document.createElement('section');
          late.id = 'late-host';
          late.innerHTML = '<header><button>Late heading</button></header>'
            + '<div data-lf-scroll="late">Late body</div>';
          main.append(late);
          const unhosted = leaf.readingRegionFor(late.querySelector('button'))?.id;
          late.setAttribute('data-lf-scroll-host', 'late');
          const hosted = leaf.readingRegionFor(late.querySelector('button'))?.id;
          late.remove();

          // A region is named after the nearest element with an id, one in a shadow
          // tree included, and a region in a message by this document alone, where a
          // box that is bounded too holds two regions.
          const idOf = (box) => leaf.readingRegions().find(({body}) => body === box)?.id;
          const staged = document.createElement('section');
          staged.id = 'stage-host';
          staged.attachShadow({mode: 'open'}).innerHTML = ['first', 'second'].map(id =>
            `<div id="${id}"><div data-lf-scroll="list"></div></div>`).join('');
          const message = document.createElement('div');
          message.className = 'lf-msg-body';
          message.innerHTML =
            '<section id="in-message" data-lf-scroll="list" data-lf-bound></section>';
          main.append(staged, message);
          staged.dispatchEvent(new CustomEvent('lf-connect',
            {bubbles: true, composed: true, cancelable: true}));
          const stagedIds = [...staged.shadowRoot.querySelectorAll('[data-lf-scroll]')]
            .map(idOf);
          const messageId = idOf(message.firstElementChild);
          await frames();
          const messageRegions = leaf.readingRegions()
            .filter(({body}) => body === message.firstElementChild).length;
          staged.remove();
          message.remove();

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
          unwatch();
          outer.remove();
          style.remove();
          return {outerId, previewId, flow, held, previewFlows, shifts, hiddenBounds,
                  kept, twinId, reclaimed, unhosted, hosted, stagedIds, messageId,
                  messageRegions, phases};
        }"""
    )
    outer, preview = "lf-region:outer-host:pane", "lf-region:preview-host:preview"
    assert (readings["outerId"], readings["previewId"]) == (outer, preview)
    assert readings["flow"] == {
        "outer": "document",
        "preview": "document",
        "scroll_behavior": "flow",
    }
    assert readings["held"] == {
        "outer": "outer-body",
        "preview": "preview-body",
        "scroll_behavior": "bounded",
        "focusRegion": outer,
    }
    assert readings["previewFlows"] == {
        "preview": "outer-body",
        "scroll_behavior": "flow",
    }
    assert readings["shifts"] == [
        [
            [outer, "document", "outer-body"],
            [preview, "document", "preview-body"],
        ],
        [[preview, "preview-body", "outer-body"]],
    ]
    assert readings["hiddenBounds"] is None
    assert readings["kept"] is True
    this_document = r"lf-region:[\d.]+:\d+"
    assert re.fullmatch(this_document, readings["twinId"]), readings
    assert readings["reclaimed"] is True
    assert (readings["unhosted"], readings["hosted"]) == (
        None,
        "lf-region:late-host:late",
    )
    assert readings["stagedIds"] == ["lf-region:first:list", "lf-region:second:list"]
    assert re.fullmatch(this_document, readings["messageId"]), readings
    assert readings["messageRegions"] == 2
    assert readings["phases"] == [
        ["before", False],
        ["before", True],
        ["after", False],
    ]


def test_a_pane_registers_the_body_it_holds_across_moves_and_revisions(browser, serve):
    """A pane's region is its one body element, named after the pane: a body that
    replaces it takes the same id, leaving the document retires it, and returning
    restores it with the user's draft untouched, since no wrapper is built around what
    the author wrote."""
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
          const first = leaf.readingRegion('lf-region:moving-pane:body')?.body.id;
          const authored = [...pane.childNodes];

          const next = document.createElement('div');
          next.id = 'second-body';
          next.innerHTML = '<input value="Authored">';
          pane.querySelector('#first-body').replaceWith(next);
          await new Promise(resolve => setTimeout(resolve));
          const replaced = leaf.readingRegion('lf-region:moving-pane:body')?.body.id;

          pane.querySelector('input').value = 'User draft';
          pane.remove();
          const retired = leaf.readingRegion('lf-region:moving-pane:body') === undefined;
          main.append(pane);
          const restored = leaf.readingRegion('lf-region:moving-pane:body')?.body.id;
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
