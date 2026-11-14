"""Data projected into widgets: comments that follow or outdate their datum, ordering of
overlapping readings, publication, rebinding, and drawing failures."""

import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import SUGGESTION_PAGE, executable_revision, live_url
from render_cases_navigation import (
    _publish,
    composer_quote,
    data_projection_page,
    source_revision,
)
from render_harness import (
    LONG_PAGE,
    compare_with,
    consume_browser_errors,
    leaf_page,
    nudge,
    open_page,
    open_threads,
    panel_settled,
    round_trip,
    said,
    select,
    select_words,
    sending,
    ticked,
    told,
    wait_for_revision,
    write,
)

from browser.threads import (
    open_panel_thread,
)
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import thread as thread_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_comment_on_external_data_stays_with_the_revision_the_user_saw(
    browser, serve
):
    """Runtime-supplied words are readable but are not authored prose.

    Their stable key identifies the fact within one source revision. Reconciliation
    replaces every row and leaves the old display text on another datum; the comment
    must become explicitly outdated instead of following either the key into new data
    or the equal text onto a different fact.
    """
    url = data_projection_page(serve)
    page = open_page(browser, url)

    readings = page.evaluate("""() => window.__lfWidgetApi().then(leaf => {
      const lede = document.querySelector('#lede');
      const datum = document.querySelector('[data-lf-datum="api"]');
      return {
        prose: [leaf.says(lede), leaf.wrote(lede)],
        datum: [leaf.says(datum), leaf.wrote(datum), datum.textContent],
      };
    })""")
    assert readings == {
        "prose": ["Live status follows.", "Live status follows."],
        "datum": ["Ready", "", "ReadyInspect"],
    }, "authored prose, projected data, and runtime apparatus became conflated"

    api = page.locator('[data-lf-datum="api"]')
    seen = source_revision(serve.page_dir, "deployments")
    origin = {
        "input": "rows",
        "source": "deployments",
        "contract": "deployment-rows",
        "revision": seen,
        "path": [0, "value"],
    }
    assert api.evaluate("node => JSON.parse(node.dataset.lfOrigin)") == origin
    api.click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Which readiness check is this?")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    comment = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    assert comment["anchor"] == {
        "section": "deployments",
        "datum": "api",
        "quote": "Ready",
        "source": "deployments",
        "source_revision": seen,
    }

    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [
            {"key": "worker", "value": "Ready"},
            {"key": "api", "value": "Running"},
        ],
    )
    replaced = source_revision(serve.page_dir, "deployments")
    assert replaced != seen
    expect(page.locator('[data-lf-datum="api"]')).to_have_attribute(
        "data-lf-source-revision", replaced
    )
    expect(page.locator('[data-lf-datum="api"]')).to_contain_text("Running")
    expect(page.locator('[data-lf-datum="api"]')).not_to_have_class(
        re.compile(r"\blf-mark-el\b")
    )
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0, (
        "the comment followed its old display text onto the other datum"
    )
    assert api.evaluate("node => JSON.parse(node.dataset.lfOrigin)") == {
        **origin,
        "revision": replaced,
        "path": [1, "value"],
    }, "the source coordinate must follow construction order, not the datum key"
    head = open_panel_thread(page, comment["id"]).locator(".lf-thread-quote-head")
    expect(head).to_contain_text("Ready")
    expect(head.locator(".lf-anchor-status")).to_have_text("Earlier data")
    expect(head).not_to_have_attribute("data-lf-detached", "")


def test_a_comment_on_an_identified_datum_follows_the_subject_across_replacements(
    browser, serve
):
    """The emitter's subject survives even when its rendering key changes."""
    authored = leaf_page(
        "keyed data projection",
        '<h1 id="title">Deployments</h1><lf-feed id="deployments" source="deployments"></lf-feed>',
    )
    feed = {
        "description": "A live deployment feed.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["id", "source"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-data": {
            "rows": {
                "contract": "deployment-rows",
                "source": "source",
                "property": "value",
            }
        },
        "x-example": '<lf-feed id="example-feed" source="deployments"></lf-feed>',
    }
    contract = {
        "description": "Deployment records with durable ids.",
        "schema": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "updated": {"type": "integer"},
                        },
                        "required": ["id", "label", "updated"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["rows"],
            "additionalProperties": False,
        },
    }
    module = """
import { nothing } from '/vendor/lit.js';
import { LeafElement, setChildren } from '/runtime/widget-api.js';
customElements.define('lf-feed', class extends LeafElement {
  render() {
    setChildren(this, (this.value?.rows ?? []).map(row => {
      const node = document.createElement('p');
      node.textContent = `${row.label} ${row.updated}`;
      node.dataset.lfDatum = `${row.id}-${row.updated}`;
      node.dataset.lfIdentity = row.id;
      return node;
    }));
    this.dispatchEvent(new CustomEvent('drawn', {detail: {value: this.value}}));
    return nothing;
  }
});
"""
    url = serve(
        authored,
        layer_registry={
            "lf-feed": feed,
            "$data": {"contracts": {"deployment-rows": contract}},
        },
        layer_widgets={"lf-feed.js": module},
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        {
            "rows": [
                {"id": "a", "label": "Alpha", "updated": 1},
                {"id": "b", "label": "Beta", "updated": 1},
            ]
        },
    )
    page = open_page(browser, url)
    page.locator('[data-lf-datum="a-1"]').click(click_count=3)
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Check this deployment.")
    with sending(page, "the keyed record comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    comment = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    assert comment["anchor"]["datum"] == "a-1"
    assert comment["anchor"]["source"] == "deployments"
    assert comment["anchor"]["identity"] == "a"
    seen = comment["anchor"]["source_revision"]

    page.locator('[data-lf-datum="a-1"]').click(modifiers=["Alt"])
    page.keyboard.press("Tab")
    reaction = page.locator('.lf-fab-bar .lf-react[data-lf-token="keep"]')
    expect(reaction).to_be_visible()
    with sending(page, "the record reaction"):
        reaction.click()
    marked = next(
        e for e in events_model.read_events(serve.page_dir) if e.get("token") == "keep"
    )
    assert marked["token"] == "keep"
    assert marked["anchor"]["identity"] == "a"
    assert "quote" not in marked["anchor"]

    page.locator('[data-lf-datum="a-1"]').click(click_count=3)
    draft = page.locator(".lf-fab-input")
    write(draft, "Keep this draft with the row.")
    expect(draft).to_be_focused()

    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        {
            "rows": [
                {"id": "b", "label": "Alpha", "updated": 1},
                {"id": "a", "label": "Alpha", "updated": 2},
            ]
        },
    )
    current = source_revision(serve.page_dir, "deployments")
    assert current != seen
    row = page.locator('[data-lf-datum="a-2"]')
    expect(row).to_have_attribute("data-lf-source-revision", current)
    expect(row).to_contain_text("Alpha 2")
    expect(row).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(draft).to_have_js_property("value", "Keep this draft with the row.")
    expect(draft).to_be_focused()
    expect(page.locator('[data-lf-datum="b-1"]')).not_to_have_class(
        re.compile(r"\blf-mark-el\b")
    )

    with sending(page, "the kept draft"):
        draft.press("ControlOrMeta+Enter")
    # The first comment's head says its row changed since the user commented.
    expect(
        open_panel_thread(page, comment["id"]).locator(".lf-anchor-status")
    ).to_have_text("Changed")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    drafted = next(
        e
        for e in events_model.read_events(serve.page_dir)
        if e.get("text") == "Keep this draft with the row."
    )
    assert drafted["anchor"]["source_revision"] == seen
    assert drafted["anchor"]["identity"] == "a"

    row.click(modifiers=["Alt"])
    page.keyboard.press("Tab")
    expect(reaction).to_have_attribute("aria-pressed", "true")
    with sending(page, "the record reaction withdrawal"):
        reaction.click()
    withdrawn = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "undo"
    )
    assert withdrawn["undoes"] == marked["id"]

    # A put-away draft follows the subject too: after selecting another passage opens
    # its empty box and a replacement re-mints the row's anchor, aiming at the row again
    # brings its stored words back.
    row.click(modifiers=["Alt"])
    expect(draft).to_be_focused()
    write(draft, "Hold this hidden draft.")
    page.keyboard.press("Escape")
    page.locator("#title").click(click_count=3)
    expect(draft).to_be_visible()
    expect(draft).to_have_js_property("value", "")
    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        {
            "rows": [
                {"id": "b", "label": "Beta", "updated": 1},
                {"id": "a", "label": "Alpha", "updated": 2},
            ]
        },
    )
    replaced = source_revision(serve.page_dir, "deployments")
    assert replaced != current
    expect(row).to_have_attribute("data-lf-source-revision", replaced)
    row.click(modifiers=["Alt"])
    expect(draft).to_be_focused()
    expect(draft).to_have_js_property("value", "Hold this hidden draft.")


# Where each margin entry shown beside the page stands.
ENTRY_TOPS = """() => {
  const entries = [];
  const walk = root => {
    for (const el of root.querySelectorAll('*')) {
      if (el.classList.contains('lf-margin-entry')) entries.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  return entries
    .filter(entry => entry.getBoundingClientRect().height > 0 &&
      getComputedStyle(entry).visibility !== 'hidden')
    .map(entry => entry.getBoundingClientRect().top);
}"""

# Whether a text document's `line` is marked, with a margin entry level with it.
# The rows of the text document `#log`, one a line, in order across its runs.
LOG_ROWS = "#log .lf-text-document-run > *"

ROW_COMMENT = f"""line => {{
  const row = document.querySelectorAll('{LOG_ROWS}')[line - 1];
  const box = row.getBoundingClientRect();
  const marked = [...(CSS.highlights.get('lf-mark') ?? [])].some(
    range => row.contains(range.startContainer) && range.toString().trim());
  return marked && ({ENTRY_TOPS})().some(top => Math.abs(top - box.top) < box.height);
}}"""

SHOW_ROW = "row => row.scrollIntoView({block: 'center'})"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_text_document_keeps_comments_on_their_lines_across_updates(
    request, serve, engine
):
    """A text document is one document whatever its source holds, so a comment on its
    lines follows them across updates: while the lines read as they did, they stay
    marked and the thread's margin entry stands beside them. A line the document holds
    twice is told apart by the lines around each copy. Once an update rewrites a
    commented line, its comment stands nowhere on the page. Each comment used to come
    off its lines on the first update, every margin entry collecting at the document's
    top, and a comment on a repeated line stood there from the start."""
    lines = [f"line {i} " + "words " * (i % 9) for i in range(1, 401)]
    # Row 128 ends the listing's first run of rows; row 310 repeats row 300.
    lines[127] = "the last row of the first run"
    lines[299] = lines[309] = "the same line twice"
    url = serve(
        leaf_page(
            "Commented document",
            '<h1>Log</h1><lf-text-document id="log" source="log-text">'
            "</lf-text-document>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(lines) + "\n")
    page = open_page(request.getfixturevalue(engine), url)
    for row in (128, 310):
        select_words(page, f"{LOG_ROWS} >> nth={row - 1}")
        anchor = page.evaluate(
            "async () => (await window.__lfCheckApi()).selectionAnchor(getSelection())"
        )
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About row {row}",
                "anchor": anchor,
            },
        )
    told(page)
    offset = 0
    for added in (0, 1, 200):
        if added:
            offset += added
            lines = [f"added {added} {i}" for i in range(added)] + lines
            data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(lines) + "\n")
            told(page)
        for row in (128 + offset, 310 + offset):
            page.locator(LOG_ROWS).nth(row - 1).evaluate(SHOW_ROW)
            rendered(page)
            page.wait_for_function(ROW_COMMENT, arg=row)
    lines[127 + offset] = "a rewritten row"
    data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(lines) + "\n")
    told(page)
    page.locator(LOG_ROWS).nth(309 + offset).evaluate(SHOW_ROW)
    rendered(page)
    page.wait_for_function(ROW_COMMENT, arg=310 + offset)
    page.locator(LOG_ROWS).first.evaluate(SHOW_ROW)
    rendered(page)
    assert page.evaluate(ENTRY_TOPS) == [], "a margin entry stands at the top"


def test_a_comment_follows_an_unversioned_derived_datum_by_its_stable_key(
    browser, serve
):
    """A widget's own derived records have no external revision boundary.

    A widget whose input the markup leaves unbound draws words no source supplied.
    Their section and stable key remain the complete identity: replacing every node and
    changing the intended value outlines that same datum without following its old words
    onto an equal neighbor.
    """
    authored = leaf_page(
        "derived projection",
        '<h1 id="title">Deployments</h1><lf-derived id="deployments"></lf-derived>',
    )
    entry = {
        "description": "A project-supplied derived feed.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-data": {
            "rows": {
                "contract": "derived-rows",
                "source": "source",
                "property": "value",
            }
        },
        "x-example": '<lf-derived id="derived-example"></lf-derived>',
    }
    contract = {"description": "Readiness rows.", "schema": {"type": "array"}}
    module = """
import { nothing } from '/vendor/lit.js';
import { LeafElement, offer, setChildren } from '/runtime/widget-api.js';
customElements.define('lf-derived', class extends LeafElement {
  render() { return nothing; }
  firstUpdated() {
    window.lfDerived = this;
    this.show([{key: 'api', value: 'Ready'}, {key: 'worker', value: 'Ready'}]);
  }
  show(rows) {
    setChildren(this, rows.map(({key, value}) => {
      const row = document.createElement('p');
      row.append(value, offer('button', 'inspect', 'Inspect'));
      row.dataset.lfDatum = key;
      return row;
    }));
    this.dispatchEvent(new CustomEvent('drawn', {detail: {value: rows}}));
  }
});
"""
    page = open_page(
        browser,
        serve(
            authored,
            layer_registry={
                "lf-derived": entry,
                "$data": {"contracts": {"derived-rows": contract}},
            },
            layer_widgets={"lf-derived.js": module},
        ),
    )

    page.locator('[data-lf-datum="api"]').click(click_count=3)
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Which readiness check is this?")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    comment = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    assert comment["anchor"] == {
        "section": "deployments",
        "datum": "api",
        "quote": "Ready",
    }

    page.evaluate(
        """() => window.lfDerived.show([
          {key: 'worker', value: 'Ready'}, {key: 'api', value: 'Running'}
        ])"""
    )
    expect(page.locator('[data-lf-datum="api"]')).to_have_class(
        re.compile(r"\blf-mark-el\b")
    )
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    head = open_panel_thread(page, comment["id"]).locator(".lf-thread-quote-head")
    expect(head).to_contain_text("Ready")
    expect(head.locator(".lf-anchor-status")).to_have_text("Changed")


def test_a_text_document_is_never_drawn_before_its_text_arrives(browser, serve):
    """A document's source reads null until the page's first state answer brings its
    text, as it does for a source with nothing to read. Drawn then, it showed a one-row
    "no data" listing whose gutter widened when the text arrived, so no caption or
    listing appears before the text does."""
    source_page = leaf_page(
        "waiting document",
        """
<lf-text-document id="full" source="full-text" label="full.toml" language="toml"></lf-text-document>
""",
    )
    url = live_url(serve(source_page))
    full = "\n".join(f"line_{n} = {n}" for n in range(1, 21)) + "\n"
    data_model.cmd_data_set(serve.page_dir, "full-text", full)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.add_init_script(
        """
        window.documentDraws = [];
        new MutationObserver(() => {
          const view = document.querySelector('#full figure');
          if (view)
            window.documentDraws.push({
              caption: view.querySelector('figcaption').textContent,
              text: view.querySelector('code')?.textContent ?? '',
            });
        }).observe(document, {subtree: true, childList: true, characterData: true});
        """
    )
    page.goto(url, wait_until="load")
    expect(page.locator("#full code")).to_contain_text("line_20 = 20")
    draws = page.evaluate("window.documentDraws")
    assert draws, "the document was never observed drawn"
    assert all(
        draw["caption"] == "full.toml" and "line_20 = 20" in draw["text"]
        for draw in draws
    )


def test_a_captured_source_stays_pointable_and_pinned(browser, serve):
    """A captured file reads under its authored label and follows its source. A
    revision that binds a source id nothing rewrites keeps the reviewed words through
    later writes to the first source."""
    long_label = "a-very-long-unbroken-source-label-" * 8 + "SKILL.md"
    source_page = leaf_page(
        "captured source",
        f"""
<h1 id="title">Leaf skill</h1>
<lf-text-document id="skill-source" source="leaf-skill" label="{long_label}" language="markdown"></lf-text-document>
<p id="latency-line">Import latency: <lf-num source="import-latency" run="a41f103e236c985b">10 ms</lf-num>.</p>
""",
    )
    url = live_url(serve(source_page))
    skill_text = "# Leaf\n\nOriginal instructions.\n"
    data_model.cmd_data_set(serve.page_dir, "leaf-skill", skill_text)

    page = open_page(browser, url)
    expect(page.locator("lf-text-document figcaption")).to_have_text(long_label)
    origin = {
        "input": "document",
        "source": "leaf-skill",
        "contract": "text-document",
        "revision": source_revision(serve.page_dir, "leaf-skill"),
    }
    datum = page.locator('[data-lf-datum="document"]')
    assert datum.evaluate("node => JSON.parse(node.dataset.lfOrigin)") == origin
    expect(page.locator("lf-text-document code")).to_have_text(
        "# Leaf\n\nOriginal instructions.\n"
    )
    page.set_viewport_size({"width": 320, "height": 720})
    assert page.locator("lf-text-document figcaption").evaluate(
        "node => node.scrollWidth <= node.clientWidth"
    )
    page.set_viewport_size({"width": 1280, "height": 720})

    data_model.cmd_data_set(serve.page_dir, "leaf-skill", "Current instructions.\n")
    expect(page.locator("lf-text-document code")).to_have_text(
        "Current instructions.\n"
    )
    assert datum.evaluate("node => JSON.parse(node.dataset.lfOrigin)") == {
        **origin,
        "revision": source_revision(serve.page_dir, "leaf-skill"),
    }
    current = (serve.page_dir / "index.html").read_text()
    _publish(
        serve.page_dir,
        2,
        current.replace('source="leaf-skill"', 'source="leaf-skill-reviewed"').replace(
            ">10 ms</lf-num>", ">11 ms</lf-num>"
        ),
        "pinned the reviewed source",
    )
    wait_for_revision(page, 2)
    data_model.cmd_data_set(serve.page_dir, "leaf-skill-reviewed", skill_text)
    expect(page.locator("lf-text-document figcaption")).to_have_text(long_label)
    expect(page.locator("lf-text-document code")).to_have_text(
        "# Leaf\n\nOriginal instructions.\n"
    )
    compare_with(page, 1)
    expect(page.locator("lf-text-document")).to_have_class(
        re.compile(r"\blf-ins-block\b")
    )
    expect(page.locator("#latency-line")).to_have_class(re.compile(r"\blf-ins-block\b"))
    compare_with(page, 1)

    bounds = page.locator("lf-text-document code").evaluate(
        """code => {
          const walker = document.createTreeWalker(code, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode())) {
            const at = node.data.indexOf('Original instructions.');
            if (at < 0) continue;
            const range = document.createRange();
            range.setStart(node, at);
            range.setEnd(node, at + 'Original instructions.'.length);
            const rect = range.getBoundingClientRect();
            return {left: rect.left, right: rect.right, y: rect.top + rect.height / 2};
          }
          return null;
        }"""
    )
    assert bounds is not None
    select(page, (bounds["left"] + 1, bounds["y"]), (bounds["right"] - 1, bounds["y"]))
    expect(page.locator("#lf-composer-quote")).to_have_text("“Original instructions.”")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert composer_quote(page)["text"].strip("“”") == "Original instructions."
    write(page.locator(".lf-composer leaf-text"), "Keep this exact source.")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    comment = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    assert comment["anchor"]["section"] == "skill-source"
    assert comment["anchor"]["datum"] == "document"

    data_model.cmd_data_set(serve.page_dir, "leaf-skill", "Changed again.\n")
    told(page)
    expect(page.locator("lf-text-document code")).to_have_text(
        "# Leaf\n\nOriginal instructions.\n"
    )


# The page's one read slot bounds the network, not the application: `askOnce` releases
# the slot as soon as a body is in hand and lets that reading apply on its own. Answering
# the trailing read from a queue the test filled first is what puts the next reading in
# the page while the previous one is still being applied, rather than waiting for a
# loaded machine to produce that overlap.
QUEUED_STATE_READS = """() => {
  window.__leafStateReads = [];
  window.__leafStateObligations = 0;
  const native = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const input = args[0];
    const url = typeof input === 'string' ? input : input.url;
    if (new URL(url, location.href).pathname !== '/api/state') return native(...args);
    window.__leafStateObligations += 1;
    while (!window.__leafStateReads.length)
      await new Promise((resolve) => setTimeout(resolve, 5));
    const [body, headers] = window.__leafStateReads.shift();
    return new Response(body, {status: 200, headers});
  };
}"""


def test_a_source_that_returns_under_an_unfinished_reading_stays_current(
    browser, serve
):
    """A source revision is a digest, so a source can return to the one on screen.

    Two readings reach the page while the first is still being applied: the source moved
    away and then back. The delivery staged for the first names a revision the page no
    longer holds, and the reading behind it names the revision the page is already
    showing, so nothing but the newer publication says which of them to paint.
    """
    url = serve(
        leaf_page(
            "returning source",
            '<h1>Notes</h1><lf-text-document id="notes" source="notes">'
            "</lf-text-document>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "notes", "First.\n")
    page = open_page(browser, url)
    expect(page.locator("#notes code")).to_have_text("First.\n")
    told(page)
    page.evaluate(QUEUED_STATE_READS)

    # The reading that moves the source also brings a message, so applying it has
    # document work to finish; the reading behind it lands while that work is unfinished.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "arriving",
            "author": "agent",
            "revision": 1,
            "text": "A message arriving with the reading.",
        },
    )
    data_model.cmd_data_set(serve.page_dir, "notes", "Second.\n")
    away = page.request.get(urljoin(page.url, "/api/state"))
    # The page is inside that read before the source returns, so the reading it takes is
    # the one that moved the source and the trailing read is answered at once.
    page.wait_for_function("() => window.__leafStateObligations >= 1")
    data_model.cmd_data_set(serve.page_dir, "notes", "First.\n")
    back = page.request.get(urljoin(page.url, "/api/state"))
    assert away.json()["data"]["version"] != back.json()["data"]["version"]
    page.evaluate(
        "readings => window.__leafStateReads.push(...readings)",
        [
            [
                response.text(),
                {
                    name: value
                    for name, value in response.headers.items()
                    if name not in ("content-length", "content-encoding")
                },
            ]
            for response in (away, back)
        ],
    )

    # The page presents the reading that returned the source, so it is waiting on none;
    # what it shows is that reading's value rather than the one it overtook.
    wait_until_ready(page, back.json())
    expect(page.locator("#notes code")).to_have_text("First.\n")
    open_threads(page)
    expect(page.locator(".lf-fp-thread", has_text="A message arriving")).to_have_count(
        1
    )


def test_new_data_in_a_stale_event_response_is_still_accepted(browser, serve):
    """Event sequence and source revision are independent coordinates.

    A crossed response may be behind the rendered log while carrying the latest source.
    Dropping the whole response at the event gate would make live data depend on an
    unrelated comment arriving first.
    """
    page = open_page(browser, data_projection_page(serve))
    older = page.evaluate("async () => await (await fetch('/api/state')).json()")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "newer-event",
            "author": "user",
            "revision": 1,
            "text": "This event must not disappear.",
        },
    )
    told(page)
    open_threads(page)
    expect(
        page.locator(".lf-fp-thread", has_text="This event must not disappear")
    ).to_have_count(1)

    crossed = []

    def older_events_with_new_data(route):
        response = route.fetch()
        state = response.json()
        if state["data"]["version"] == older["data"]["version"]:
            route.fulfill(status=response.status, json=state)
            return
        state["events"] = older["events"]
        state["browser"] = older["browser"]
        crossed.append(True)
        route.fulfill(status=response.status, json=state)

    page.route("**/api/state*", older_events_with_new_data)
    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [
            {"key": "api", "value": "Running"},
            {"key": "worker", "value": "Ready"},
        ],
    )
    expect(page.locator('[data-lf-datum="api"]')).to_contain_text("Running")
    assert crossed, "the new data never arrived beside the stale event tail"
    expect(
        page.locator(".lf-fp-thread", has_text="This event must not disappear")
    ).to_have_count(1)


def test_a_stale_response_cannot_rewind_timestamp_aging(browser, serve):
    """A completed crossed state read must not recalibrate the displayed clock.

    Keep freshness unchanged: an origin that advertises new state but returns an
    old reading forever asks for repair on every tick rather than aging paints.
    """
    url = serve(LONG_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "earlier",
            "author": "user",
            "revision": 1,
            "text": "An earlier question.",
            "ts": (datetime.now().astimezone() - timedelta(hours=1)).isoformat(),
        },
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, "earlier")
    timestamp = view.locator(".lf-msg-head time").first
    expect(timestamp).to_have_text("1h ago")
    stale = page.evaluate("async () => (await fetch('/api/state')).json()")
    stale["taken"] = 0
    stale["now"] = (datetime.now().astimezone() - timedelta(hours=3)).isoformat()
    crossed = []

    def crossed_state(route):
        crossed.append(route.request.url)
        route.fulfill(json=stale)

    # One transient freshness observation asks for the crossed read. Then the
    # origin again advertises the reading the page holds, so the heartbeat ages
    # the accepted state rather than repeatedly repairing a freshness mismatch.
    page.route("**/api/state*", crossed_state)
    with page.expect_response("**/api/state*"):
        page.route(
            "**/api/news*",
            lambda route: route.fulfill(
                body=stale["reading"] if crossed else "crossed-state-reading"
            ),
        )
    ticked(page)
    assert len(crossed) == 1
    expect(timestamp).to_have_text("1h ago")
    # With no newer state at all, the panel's thread still ages by the clock.
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=3))
    ticked(page)
    expect(timestamp).to_have_text("4h ago")


def test_a_data_widget_draws_each_publication_and_recovers(browser, serve):
    """A same-value rerun reaches a package as a new value at the same revision.

    Repeated reads stay quiet; corruption and clearing remove the reading, and a
    later valid publication draws again in the same widget.
    """
    page = open_page(browser, data_projection_page(serve))
    page.evaluate("""() => {
      const feed = document.querySelector('lf-feed');
      const show = feed.show;
      window.publications = [feed.value];
      feed.show = function (value) {
        if (value !== window.publications.at(-1)) window.publications.push(value);
        return show.call(this, value);
      };
    }""")

    def read():
        nudge(serve.page_dir)
        told(page)
        return page.evaluate("window.publications")

    publication_file = data_model.source_file(serve.page_dir, "deployments")
    original = json.loads(publication_file.read_text())
    first = page.evaluate("window.publications")[0]
    datum = page.locator('[data-lf-datum="api"]')
    revision = datum.get_attribute("data-lf-source-revision")

    data_model.cmd_data_set(serve.page_dir, "deployments", original["value"])
    deliveries = read()
    assert deliveries == [first, original["value"]], deliveries
    assert json.loads(publication_file.read_text())["run"] != original["run"]
    expect(datum).to_have_attribute("data-lf-source-revision", revision)
    assert len(read()) == 2

    publication_file.write_text("{}")
    deliveries = read()
    assert len(deliveries) == 3 and deliveries[-1] is None, deliveries
    assert len(read()) == 3

    data_model.cmd_data_set(serve.page_dir, "deployments", original["value"])
    deliveries = read()
    assert len(deliveries) == 4 and deliveries[-1] == first, deliveries
    expect(datum).to_have_attribute("data-lf-source-revision", revision)

    data_model.cmd_data_clear(serve.page_dir, "deployments")
    deliveries = read()
    assert len(deliveries) == 5 and deliveries[-1] is None, deliveries
    assert len(read()) == 5

    data_model.cmd_data_set(serve.page_dir, "deployments", original["value"])
    deliveries = read()
    assert len(deliveries) == 6 and deliveries[-1] == first, deliveries
    expect(datum).to_have_attribute("data-lf-source-revision", revision)


def test_data_consumers_clear_and_recover_across_contract_only_rebindings(
    browser, serve
):
    """Active and frozen consumers keep their declarations as a source is rebound.

    A changed contract must reach the browser even with identical value bytes, clear
    the incompatible consumer, and leave it able to recover.
    """

    def entry(tag, contract):
        return {
            "description": "An instrumented data reader.",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["id", "source"],
            "additionalProperties": False,
            "x-content": "empty",
            "x-data": {
                "data": {"contract": contract, "source": "source", "property": "value"}
            },
            "x-example": f'<{tag} id="example-{contract}" source="shared"></{tag}>',
        }

    def module(tag):
        return """import { nothing } from '/vendor/lit.js';
        import { LeafElement } from '/runtime/widget-api.js';
customElements.define(TAG, class extends LeafElement {
  render() {
    window.dataDeliveries ??= [];
    window.dataDeliveries.push({id: this.id, value: this.value});
    const text = JSON.stringify(this.value ?? null);
    if (this.textContent !== text) this.textContent = text;
    return nothing;
  }
});""".replace("TAG", json.dumps(tag))

    authored = leaf_page(
        "Different contracts",
        '<h1 id="title">Feeds</h1>'
        '<lf-array-feed id="page-feed" source="shared"></lf-array-feed>',
    )
    url = serve(
        authored,
        layer_registry={
            "lf-array-feed": entry("lf-array-feed", "rows"),
            "lf-object-feed": entry("lf-object-feed", "other-rows"),
            "$data": {
                "contracts": {
                    "rows": {"description": "Rows.", "schema": {"type": "array"}},
                    "other-rows": {
                        "description": "Another contract.",
                        "schema": {"type": ["array", "object"]},
                    },
                }
            },
        },
        layer_widgets={
            "lf-array-feed.js": module("lf-array-feed"),
            "lf-object-feed.js": module("lf-object-feed"),
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "question",
            "author": "user",
            "revision": 1,
            "text": "Another feed.",
        },
    )
    thread_model.post_reply(
        serve.page_dir,
        {"responds": "question"},
        "Frozen feed.",
        '<lf-object-feed id="thread-feed" source="shared"></lf-object-feed>',
    )
    data_model.cmd_data_set(serve.page_dir, "shared", ["same bytes"])
    page = open_page(browser, url)
    open_panel_thread(page, "question")
    expect(page.locator("#page-feed")).to_have_text('["same bytes"]')
    expect(page.locator("#thread-feed")).to_have_text("null")
    consume_browser_errors(page, "<lf-object-feed> input data requires other-rows")

    def read():
        nudge(serve.page_dir)
        told(page)

    wire = "async () => (await (await fetch('/api/state')).json()).data"

    def rebind(contract, value):
        (serve.page_dir / "index.html").write_text(
            authored
            if contract == "rows"
            else authored.replace("lf-array-feed", "lf-object-feed")
        )
        data_model.cmd_data_set(serve.page_dir, "shared", value)
        read()
        return page.evaluate(wire)

    original = page.evaluate(wire)
    rebound = rebind("other-rows", ["same bytes"])
    expect(page.locator("#page-feed")).to_have_text("null")
    expect(page.locator("#thread-feed")).to_have_text('["same bytes"]')
    assert (
        original["sources"]["shared"]["revision"]
        == rebound["sources"]["shared"]["revision"]
    )
    assert original["version"] != rebound["version"]
    consume_browser_errors(page, "<lf-array-feed> input data requires rows")

    calls = page.evaluate("window.dataDeliveries.length")
    read()
    read()
    assert page.evaluate("window.dataDeliveries.length") == calls
    assert page.lf_errors == []

    rebind("rows", ["same bytes"])
    expect(page.locator("#page-feed")).to_have_text('["same bytes"]')
    expect(page.locator("#thread-feed")).to_have_text("null")
    consume_browser_errors(page, "<lf-object-feed> input data requires other-rows")

    rebind("other-rows", {"new": "object meaning"})
    expect(page.locator("#page-feed")).to_have_text("null")
    expect(page.locator("#thread-feed")).to_have_text('{"new":"object meaning"}')
    consume_browser_errors(page, "<lf-array-feed> input data requires rows")


def test_a_returning_projection_subscriber_repaints_to_restore_subscriptions(
    browser, serve
):
    """A returning watcher paints once to restore subscriptions, including after a
    failed paint or one the departure cut short."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    result = page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          const settle = () => new Promise((resolve) => setTimeout(resolve));
          customElements.define('lf-projection-probe', class extends api.LeafElement {
            render() {
              this.work = undefined;
              return this.paint?.() ?? api.noChange;
            }
            async getUpdateComplete() {
              const result = await super.getUpdateComplete();
              await this.work;
              return result;
            }
          });
          const owned = (id, paint) => {
            const owner = document.createElement('lf-projection-probe');
            owner.id = id;
            owner.paint = paint;
            document.body.append(owner);
            return owner;
          };
          const leaveAndReturn = async (owner) => {
            owner.remove();
            await settle();
            document.body.append(owner);
            await settle();
          };
          const failed = {};
          const owners = [];
          for (const name of ['throwing', 'rejecting']) {
            failed[name] = 0;
            const owner = owned(`failing-${name}`, () => {
              failed[name] += 1;
              api.readObligations();
              if (name === 'rejecting') {
                owner.work = Promise.reject(new Error(`${name} paint failed`));
                owner.work.catch(() => {});
                return api.noChange;
              }
              throw new Error(`${name} paint failed`);
            });
            owners.push(owner);
            await settle();
            await leaveAndReturn(owner);
          }
          let paints = 0;
          let finish;
          const finished = new Promise((resolve) => { finish = resolve; });
          const owner = owned('pending-paint', () => {
            paints += 1;
            api.readObligations();
            owner.work = finished;
            return api.noChange;
          });
          owners.push(owner);
          await settle();
          await leaveAndReturn(owner);
          const interrupted = paints;
          finish();
          await finished;
          await leaveAndReturn(owner);
          const kept = paints;
          for (const owner of owners) owner.remove();
          return {failed, interrupted, kept};
        }"""
    )
    assert result == {
        "failed": {"throwing": 2, "rejecting": 2},
        "interrupted": 2,
        "kept": 3,
    }
    errors = consume_browser_errors(page, "paint failed")
    reported = sorted(said(error) for error in errors)
    assert reported == sorted(
        f'leaf: <lf-projection-probe id="failing-{name}"> failed: {name} paint failed'
        for name in ["throwing", "throwing", "rejecting", "rejecting"]
    )


def test_a_held_reading_shows_once_unseen_after_its_owner_returns(browser, serve):
    """A widget's held reading waits for its growth to go unseen across a departure
    and return, though the return draws nothing again."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    result = page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          const settle = () => new Promise((resolve) => setTimeout(resolve));
          customElements.define('lf-held-probe', class extends api.LeafElement {
            render() {
              shown = held.hold(current);
              return api.noChange;
            }
          });
          const owner = document.createElement('lf-held-probe');
          const region = document.createElement('p');
          region.textContent = 'Rows';
          owner.append(region);
          let current = 'first';
          let shown = null;
          const refresh = () => { owner.requestUpdate(); owner.performUpdate(); };
          const held = new api.HeldReading(owner, () => [region], refresh);
          document.body.prepend(owner);
          await settle();
          current = 'second';
          refresh();
          const waiting = shown;
          owner.remove();
          await settle();
          document.body.prepend(owner);
          await settle();
          region.hidden = true;
          for (let i = 0; i < 3; i++) await new Promise(requestAnimationFrame);
          await settle();
          owner.remove();
          return {waiting, shown};
        }"""
    )
    assert result == {"waiting": "first", "shown": "second"}


def test_data_readiness_settles_and_reports_failed_drawings(browser, serve):
    """The data stamp proves that every drawing a delivery holds has settled.

    A rejected drawing at mount, a rejected drawing on a later delivery, and a draw
    that throws are each reported once. None turns every subsequent poll into the same
    page-wide read failure or prevents the accepted revision becoming ready.
    """
    page = open_page(browser, data_projection_page(serve))
    page.evaluate("""async () => {
      const {nothing} = await window.__lfWidgetApi();
      const widget = document.querySelector('lf-feed');
      window.beforeDataVersion = document.body.dataset.lfDataVersion;
      window.mountDeliveries = 0;
      // The drawing that follows each render, which `updateComplete` waits for.
      const complete = widget.getUpdateComplete.bind(widget);
      widget.getUpdateComplete = async () => {
        const result = await complete();
        await widget.work;
        return result;
      };
      const failing = (error) => {
        const work = Promise.reject(error);
        work.catch(() => {});
        return work;
      };
      window.failing = failing;
      widget.render = () => {
        mountDeliveries += 1;
        widget.work = failing(new Error('mount projection failed'));
        return nothing;
      };
      widget.requestUpdate();
    }""")
    for _ in range(2):
        nudge(serve.page_dir)
        told(page)

    def deliver(value, failure):
        page.evaluate(
            """async (failure) => {
              const {nothing} = await window.__lfWidgetApi();
              const widget = document.querySelector('lf-feed');
              window.afterMountDataVersion ??= document.body.dataset.lfDataVersion;
              window.draws ??= {};
              widget.render = () => {
                draws[failure] = (draws[failure] ?? 0) + 1;
                const error = new Error(`${failure} projection failed`);
                widget.work = undefined;
                if (failure === 'update') widget.work = failing(error);
                else throw error;
                return nothing;
              };
            }""",
            failure,
        )
        data_model.cmd_data_set(
            serve.page_dir, "deployments", [{"key": "api", "value": value}]
        )
        told(page)

    deliver("Updated", "update")
    deliver("Updated again", "synchronous update")
    nudge(serve.page_dir)
    told(page)
    result = page.evaluate("""() => ({
      before: beforeDataVersion, mountDeliveries, draws,
      afterMount: afterMountDataVersion, afterUpdate: document.body.dataset.lfDataVersion,
    })""")
    result["version"] = page.request.get(urljoin(page.url, "/api/state")).json()[
        "data"
    ]["version"]
    assert result["mountDeliveries"] == 1, result
    assert result["draws"] == {"update": 1, "synchronous update": 1}, result
    assert result["afterMount"] == result["before"], result
    assert result["afterUpdate"] == result["version"], result
    errors = consume_browser_errors(page, "projection failed")
    assert {said(error) for error in errors} == {
        'leaf: <lf-feed id="deployments"> failed: mount projection failed',
        'leaf: <lf-feed id="deployments"> failed: update projection failed',
        'leaf: <lf-feed id="deployments"> failed: synchronous update projection failed',
    }
    texts = [error.values["text"] for error in errors]
    assert len(texts) == 3 and all("\n" in text for text in texts), texts
    told(page)
    agent_errors = [
        event["text"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "error"
    ]
    assert set(agent_errors) == {text.removeprefix("leaf: ") for text in texts}


def test_widget_errors_keep_exception_evidence(browser, serve):
    """A failed paint recovers at the widget's next draw; the agent retains the actual
    throw site."""
    page = open_page(browser, data_projection_page(serve))
    page.evaluate(
        """async () => {
          const {failSoft} = await window.__lfWidgetApi();
          const widget = document.querySelector('lf-feed');
          function widgetProjection() { throw new TypeError('projection rejected'); }
          let error;
          try { widgetProjection(); } catch (caught) { error = caught; }
          failSoft(widget, error);
        }"""
    )
    expect(page.locator("lf-feed .lf-error")).to_have_text(
        "<lf-feed> failed: projection rejected"
    )
    errors = consume_browser_errors(page, "projection rejected")
    assert len(errors) == 1, errors
    assert any(
        said(error).startswith(
            'leaf: <lf-feed id="deployments"> failed: projection rejected'
        )
        and "widgetProjection" in error.values["text"]
        for error in errors
    ), errors
    told(page)
    agent_errors = [
        event["text"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "error"
    ]
    assert any("widgetProjection" in error for error in agent_errors), agent_errors
    data_model.cmd_data_set(
        serve.page_dir, "deployments", [{"key": "api", "value": "Recovered reading"}]
    )
    told(page)
    expect(page.locator("lf-feed")).to_contain_text("Recovered reading")
    expect(page.locator("lf-feed .lf-error")).to_have_count(0)


def test_data_written_while_a_fresh_revision_starts_shows_once_it_has_started(
    browser, serve
):
    """Data written while a fresh revision document starts shows once it has started.

    The revision published below changes the page's own code, which is the one thing
    the current document cannot take on, so it is followed into a fresh document and
    there is a startup to write data during. Nothing can paint the update before then:
    the test holds the revision's registry, and widgets import their modules only after
    it arrives (widget-loader.js).
    """
    activation_probe = """
      window.__lfRevisionRegistryBlocked = false;
      const nativeFetch = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        const path = new URL(url, location.href).pathname;
        if (path.startsWith('/revisions/r2-') && path.endsWith('/registry.json')) {
          window.__lfRevisionRegistryBlocked = true;
          return new Promise(resolve => {
            window.__lfReleaseRevisionRegistry = () => resolve(nativeFetch(...args));
          });
        }
        return nativeFetch(...args);
      };
    """
    page = open_page(
        browser, live_url(data_projection_page(serve)), init_script=activation_probe
    )
    d = serve.page_dir
    original_document = page.evaluate("performance.timeOrigin")
    current = (d / "index.html").read_text()
    _publish(
        d,
        2,
        executable_revision(
            current.replace("Live status follows.", "Live status follows now."), "two"
        ),
        "refreshed the page",
    )
    page.wait_for_function("() => window.__lfRevisionRegistryBlocked === true")
    assert page.evaluate("performance.timeOrigin") != original_document

    data_model.cmd_data_set(
        d,
        "deployments",
        [
            {"key": "api", "value": "Running"},
            {"key": "worker", "value": "Ready"},
        ],
    )
    page.evaluate("() => window.__lfReleaseRevisionRegistry()")
    wait_until_ready(page)
    nudge(d)
    expect(page.locator('[data-lf-datum="api"]')).to_contain_text("Running")
    expect(page.locator("#lede")).to_have_text("Live status follows now.")
