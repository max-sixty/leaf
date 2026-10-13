"""Publication-owned renderers keep recorded decisions intelligible."""

import json
from copy import deepcopy

import pytest
from interact_support import ROOT, append_command, element_declaration
from leaf import thread
from leaf.event_log import read_events
from leaf.files import revision_path
from leaf.registry.storage import require_registry
from leaf.render_checks import rendered, wait_until_ready
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_layout import SHOT_SRC, SHOTS
from render_harness import (
    consume_browser_errors,
    expect_asks_answered,
    open_page,
    panel_settled,
    stamp_page,
    told,
)


def test_a_publication_stylesheet_failure_names_its_captured_resource(browser, serve):
    """A native load event must retain the publication and URL in the error report."""
    source = leaf_page("Publication failure", "<h1>Original publication</h1>")
    url = serve(source)
    directory = serve.page_dir
    root = "/revisions/" + revision_path(directory, 1).stem
    stamp_page(
        directory,
        source.replace("Original publication", "Current publication"),
        "Current publication",
    )
    page = open_page(browser, live_url(url))
    resource = root + "/widget-theme.css"
    page.route(
        "**" + resource,
        lambda route: route.fulfill(status=503, body="Stylesheet unavailable"),
    )
    reading = page.evaluate(
        """async root => {
          const {requireVocabulary} = await window.__lfCheckApi();
          const {exceptionText} = await window.__lfCheckApi();
          try { await requireVocabulary(1, root); return null; }
          catch (error) {
            return {name: error.name,
              report: exceptionText(error, 'Publication preparation failed').split('\\n')[0]};
          }
        }""",
        root,
    )
    assert reading == {
        "name": "Error",
        "report": "Publication preparation failed: "
        "Leaf vocabulary r1 stylesheet failed to load: "
        + url.split("/versions/")[0]
        + resource,
    }
    consume_browser_errors(
        page,
        {
            "code": "failed-load",
            "status": 503,
            "url": url.split("/versions/")[0] + resource,
        },
    )


@pytest.mark.parametrize(
    "engine", ["browser", "firefox_browser", "webkit_browser", "sample"]
)
def test_historical_document_and_frozen_replies_keep_their_widget_vocabulary(
    request, serve, engine
):
    """Old decisions and new widgets keep their publications, including sample children."""
    url = serve(
        leaf_page(
            "Publication vocabularies",
            '<h1 id="topic">Decision</h1><lf-options id="choice" choose>'
            '<lf-option id="a">Alpha</lf-option><lf-option id="b">Beta</lf-option>'
            "</lf-options>",
        )
    )
    directory = serve.page_dir
    parent = append_command(
        directory,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Choose for each era",
        },
    )
    old = thread.post_reply(
        directory,
        {"to": parent["id"], "for": parent["id"]},
        "Old decision",
        '<lf-ask id="old-question"><h3>Old choice</h3><lf-options id="old" choose><lf-option id="old-a">Alpha</lf-option>'
        '<lf-option id="old-b">Beta</lf-option></lf-options></lf-ask>',
    )
    decision = append_command(
        directory,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "old",
            "action": "choose",
            "detail": {"value": ["old-b"]},
        },
    )
    append_command(
        directory,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["b"]},
        },
    )
    modules = ROOT / "skills/leaf/packages/default/widgets"
    renderer = (modules / "lf-options.js").read_text()
    renderer = (
        renderer.replace("state.choose", "state.pick")
        .replace('#available("choose")', '#available("pick")')
        .replace('#dispatch("choose",', '#dispatch("pick",')
    )
    declarations = deepcopy(require_registry(directory)["lf-options"])
    declarations["x-state"]["pick"] = declarations["x-state"].pop("choose")
    declarations["x-awaits"]["value"] = "pick"
    declarations["x-awaits"]["answered"]["pick"] = declarations["x-awaits"][
        "answered"
    ].pop("choose")
    declarations["properties"]["caption"] = {"type": "string"}
    declarations["x-says"] = {"caption": "before"}
    fresh = element_declaration("lf-fresh", upgrade=True)
    fresh["properties"]["caption"] = {"type": "string"}
    fresh["x-says"] = {"caption": "before"}
    local = directory / "page"
    (local / "widgets").mkdir(exist_ok=True)
    (local / "widgets/lf-options.js").write_text(renderer)
    for name in ("lf-options-addition.js", "lf-options-settled.js"):
        (local / "widgets" / name).write_bytes((modules / name).read_bytes())
    (local / "widgets/lf-fresh.js").write_text("""
      import Child from './lf-generated-child.js';
      import {once, createWidgetElement} from '/runtime/widget-api.js';
      export default class extends HTMLElement {
        connectedCallback() {
          if (once(this)) this.append(createWidgetElement(this, 'lf-generated-child', Child));
        }
      }
    """)
    (local / "widgets/lf-generated-child.js").write_text("""
      export default class extends HTMLElement {connectedCallback() {this.dataset.ready = 'yes'}}
    """)
    (local / "registry.json").write_text(
        json.dumps(
            {
                "lf-options": declarations,
                "lf-fresh": fresh,
                "lf-generated-child": element_declaration(
                    "lf-generated-child", upgrade=True
                ),
            }
        )
    )
    # Posting markup itself publishes the changed vocabulary, even with identical HTML.
    new = thread.post_reply(
        directory,
        {"to": parent["id"], "for": decision["id"]},
        "New decision",
        '<lf-ask id="new-question"><h3>New choice</h3><lf-options id="new" choose caption="New attribute">'
        '<lf-option id="new-a">Alpha</lf-option><lf-option id="new-b">Beta</lf-option>'
        '</lf-options></lf-ask><lf-fresh id="new-widget" caption="New widget">Current reply</lf-fresh>'
        '<lf-sample id="reply-practice"><template id="reply-practice-page" data-sample>'
        '<h1>New sample</h1><lf-fresh id="sample-widget" caption="New sample widget">'
        "Sample reply</lf-fresh></template></lf-sample>",
    )
    assert old["revision"] == 1 and new["revision"] == 2
    browser = request.getfixturevalue("browser" if engine == "sample" else engine)
    if engine == "sample":
        source = (directory / "index.html").read_text()
        sample = (
            '<lf-sample id="practice" window><template id="practice-page" '
            f'data-sample data-sample-threads="{parent["id"]}">'
            "<h1>Copied conversation</h1></template></lf-sample>"
        )
        stamp_page(
            directory, source.replace("</main>", sample + "</main>"), "Add sample"
        )
        parent_page = open_page(browser, url.replace("/versions/v1.html", "/"))
        frame = parent_page.locator("#practice iframe")
        expect(frame).to_be_visible()
        page = frame.element_handle().content_frame()
        wait_until_ready(page)
    else:
        page = open_page(browser, url, pin=True)
        expect(page.locator("#b .lf-pick")).to_have_attribute("aria-checked", "true")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator("#old-b .lf-pick")).to_have_attribute("aria-checked", "true")
    expect(page.locator('#new > [data-lf-said="caption"]')).to_have_text(
        "New attribute"
    )
    expect(page.locator('#new-widget > [data-lf-said="caption"]')).to_have_text(
        "New widget"
    )
    expect(page.locator("#new-widget")).to_be_visible()
    expect(page.locator("#new-widget lf-generated-child")).to_have_attribute(
        "data-ready", "yes"
    )
    assert page.locator("#new-widget").evaluate("""async node => {
      const {vocabularyFor} = await window.__lfCheckApi();
      const context = vocabularyFor(node);
      const child = node.querySelector('lf-generated-child');
      await context.load(node);
      let refused = false;
      try {context.register('lf-generated-child', class extends HTMLElement {})} catch {refused = true}
      return refused && child.constructor === context.registry.get('lf-generated-child');
    }""")
    page.locator("#reply-practice").evaluate("sample => sample.ready")
    child_frame = page.locator("#reply-practice iframe")
    child_page = child_frame.element_handle().content_frame()
    wait_until_ready(child_page)
    expect(
        child_page.locator('#sample-widget > [data-lf-said="caption"]')
    ).to_have_text("New sample widget")
    expect(child_page.locator("#sample-widget lf-generated-child")).to_have_attribute(
        "data-ready", "yes"
    )

    answered_before = "1/2" if engine == "sample" else "2/3"
    expect_asks_answered(page, answered_before)
    page.evaluate("""async () => {
      window.__vocabularyTestRead = (await window.__lfCheckApi()).readApplication;
    }""")
    page.locator("#new-b .lf-pick").click()
    expect(page.locator("#new-b .lf-pick")).to_have_attribute("aria-checked", "true")
    page.wait_for_function(
        "() => window.__vocabularyTestRead().authoritative.events.some(e => e.widget === 'new' && e.action === 'pick')"
    )
    if engine == "sample":
        events = page.evaluate(
            "async () => (await (await fetch(new URL('api/state', location.href))).json()).events"
        )
        # The sample owns the gesture; its copied parent history is immutable.
        assert not any(event.get("widget") == "new" for event in read_events(directory))
    else:
        events = read_events(directory)
    accepted = next(event for event in events if event.get("widget") == "new")
    assert accepted["revision"] == 2 and accepted["action"] == "pick"
    expect_asks_answered(page, "2/2" if engine == "sample" else "3/3")
    wait_until_ready(page)
    if engine == "sample":
        # The narrow panel owns its reading keys while covering the sample page.
        page.get_by_role("button", name="Close threads", exact=True).click()
        panel_settled(page, open=False)
    else:
        page.locator("#new-b .lf-pick").focus()
    (parent_page if engine == "sample" else page).keyboard.press("z")
    page.wait_for_function(
        "id => window.__vocabularyTestRead().authoritative.events.some(e => e.kind === 'undo' && e.undoes === id)",
        arg=accepted["id"],
    )
    if engine == "sample":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    expect(page.locator("#new-b .lf-pick")).to_have_attribute("aria-checked", "false")
    expect_asks_answered(page, answered_before)
    expect(page.locator("#old-b .lf-pick")).to_have_attribute("aria-checked", "true")


def test_initial_drawings_belong_to_their_publication(browser, serve):
    """Classic first-paint producers remain distinct in later frozen replies."""
    entry = element_declaration("lf-initial-probe", upgrade=True)
    entry["x-initial"] = "/page/initial.js"
    module = """
      import {once, initialRender} from '/runtime/widget-api.js';
      export default class extends HTMLElement {
        connectedCallback() {
          if (!once(this)) return;
          this.dataset.drawn = initialRender(this).era;
        }
      }
    """

    def producer(era):
        return f"""document.documentElement.lfInitial.register('lf-initial-probe', host => {{
          host.textContent = '{era} drawing'; return {{era: '{era}'}};
        }});"""

    url = serve(
        leaf_page(
            "Initial vocabularies",
            '<h1>Initial</h1><lf-initial-probe id="page-probe"></lf-initial-probe>',
        ),
        layer_registry={"lf-initial-probe": entry},
        layer_widgets={"lf-initial-probe.js": module},
        page_files={"initial.js": producer("old")},
    )
    directory = serve.page_dir
    parent = append_command(
        directory,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Compare drawings",
        },
    )
    thread.post_reply(
        directory,
        {"to": parent["id"], "for": parent["id"]},
        "Old",
        '<lf-initial-probe id="old-probe"></lf-initial-probe>',
    )
    (directory / "page/initial.js").write_text(producer("new"))
    thread.post_reply(
        directory,
        {"to": parent["id"]},
        "New",
        '<lf-initial-probe id="new-probe"></lf-initial-probe>',
    )
    page = open_page(browser, url, pin=True)
    expect(page.locator("#page-probe")).to_have_attribute("data-drawn", "old")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator("#old-probe")).to_have_attribute("data-drawn", "old")
    expect(page.locator("#new-probe")).to_have_attribute("data-drawn", "new")


_RETIREMENT_WIDGET = """import { widgetController, offer } from '/runtime/widget-api.js';
export default class extends HTMLElement {
 connectedCallback() {
  if (this.controller) return;
  this.controller = widgetController(this);
  const button=offer('button', 'review-decide', 'Accept revision');
  button.addEventListener('click', () => this.controller.dispatch({kind:'action',verb:'decide',detail:{outcome:'accept'}}));
  this.append(button);
 }
}"""


def test_historical_decisions_keep_their_retired_passages(browser, serve):
    """An old publication keeps its text reading after current tags disappear."""
    url = serve(leaf_page("Retirement publication", '<h1 id="topic">Topic</h1>'))
    directory = serve.page_dir
    base = require_registry(directory)
    proposal = deepcopy(base["lf-suggestion"])
    proposal["x-face"] = [":scope > lf-before", ":scope > lf-after"]
    before = deepcopy(base["lf-old"])
    before["x-owners"] = ["lf-proposal"]
    after = deepcopy(base["lf-new"])
    after["x-owners"] = ["lf-proposal"]
    local = directory / "page"
    (local / "widgets").mkdir(exist_ok=True)
    (local / "registry.json").write_text(
        json.dumps({"lf-proposal": proposal, "lf-before": before, "lf-after": after})
    )
    (local / "widgets/lf-proposal.js").write_text(_RETIREMENT_WIDGET)
    stamp_page(
        directory,
        leaf_page(
            "Older proposal",
            '<lf-proposal id="new-proposal"><lf-before id="before">Original phrase</lf-before><lf-after id="after">Replacement phrase</lf-after></lf-proposal>',
        ),
        "Add proposal",
    )
    (local / "registry.json").write_text("{}")
    stamp_page(
        directory,
        leaf_page("Current page", '<h1 id="topic">Current</h1>'),
        "Remove proposal vocabulary",
    )
    page = open_page(
        browser, url.replace("/versions/v1.html", "/versions/v2.html"), pin=True
    )
    expect(page.locator("#before")).to_be_visible()
    page.get_by_role("button", name="Accept revision").click()
    expect(page.locator("#before")).to_be_hidden()
    actual = page.evaluate(
        """async () => {const p={...await window.__lfCheckApi(),...await window.__lfWidgetApi()};return {says:p.says(document.querySelector('#new-proposal')), settledAway:p.settledAway(document.querySelector('#before'))}}"""
    )
    assert actual == {"says": "Replacement phrase", "settledAway": True}


def test_lazy_global_library_keeps_one_instance_across_live_revisions(browser, serve):
    """A revised comparison still upgrades and answers without global redefinition."""
    source = leaf_page(
        "Shot revision",
        f'''<h1>Review</h1><lf-shot id="comparison" alt="Original comparison" before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>''',
    )
    page = open_page(
        browser,
        live_url(serve(source, media={SHOT_SRC[n]: data for n, data in SHOTS.items()})),
    )
    expect(page.locator("lf-shot#comparison wa-comparison")).to_be_attached()
    initial_document = page.evaluate("performance.timeOrigin")
    expect(page.locator("lf-shot#comparison .lf-shotcap")).to_have_count(2)
    page.locator('.lf-shotcap[data-lf-state="after"]').click()
    expect(page.locator("wa-comparison")).to_have_attribute("position", "0")
    stamp_page(
        serve.page_dir,
        source.replace("Original comparison", "Revised comparison"),
        "Revise description",
    )
    told(page)
    expect(page.locator("lf-shot#comparison")).to_have_attribute(
        "alt", "Revised comparison"
    )
    rendered(page)
    expect(page.locator("lf-shot#comparison wa-comparison")).to_be_attached()
    assert page.evaluate("performance.timeOrigin") == initial_document
    expect(page.locator("lf-shot#comparison .lf-shotcap")).to_have_count(2)
    page.locator('.lf-shotcap[data-lf-state="before"]').click()
    expect(page.locator("wa-comparison")).to_have_attribute("position", "100")


def test_publications_share_pure_layer_libraries_and_keep_private_module_values(
    browser, serve
):
    """Sharing is module ownership, not detection of a library's global effects."""
    source = leaf_page("Dependency ownership", "<h1>Dependency ownership</h1>")
    url = serve(source)
    directory = serve.page_dir
    (directory / "vendor/publication-library.js").write_text(
        'export const token = {meaning: "shared layer library"};'
    )
    (directory / "widgets/publication-probe.js").write_text(
        'export {token} from "../vendor/publication-library.js";'
        'export {value} from "./publication-private.js";'
    )
    (directory / "widgets/publication-private.js").write_text(
        'export const value = "original package helper";'
    )
    private = directory / "page"
    private.mkdir(exist_ok=True)
    (private / "app.js").write_text('export {value} from "./private.js";')
    (private / "private.js").write_text('export const value = "original page data";')
    source = source.replace(
        "</head>", '<script type="module" src="/page/app.js"></script></head>'
    )
    old = stamp_page(directory, source, "Original dependencies")["revision"]
    (directory / "widgets/publication-private.js").write_text(
        'export const value = "revised package helper";'
    )
    (private / "private.js").write_text('export const value = "revised page data";')
    new = stamp_page(directory, source, "Revised private dependencies")["revision"]
    page = open_page(browser, live_url(url))
    roots = ["/revisions/" + revision_path(directory, n).stem for n in (old, new)]
    assert not page.evaluate(
        "performance.getEntriesByType('resource').some(entry => "
        "entry.name.endsWith('/vendor/publication-library.js'))"
    )
    reading = page.evaluate(
        """async roots => {
          const [oldWidget, newWidget] = await Promise.all(roots.map(
            root => import(root + '/widgets/publication-probe.js')));
          const [oldPage, newPage] = await Promise.all(roots.map(
            root => import(root + '/page/app.js')));
          return {shared: oldWidget.token === newWidget.token,
            helpers: [oldWidget.value, newWidget.value],
            pages: [oldPage.value, newPage.value]};
        }""",
        roots,
    )
    assert reading == {
        "shared": True,
        "helpers": ["original package helper", "revised package helper"],
        "pages": ["original page data", "revised page data"],
    }
