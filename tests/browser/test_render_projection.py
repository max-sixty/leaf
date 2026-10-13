"""Live version, report, replay, and projection tests."""

import json
import re
from datetime import datetime, timedelta
from itertools import pairwise

import pytest
from click.testing import CliRunner
from interact_support import (
    COMMAND_HUB_PACKAGE,
    ROOT,
    add_test_widget,
    append_carried_log_record,
    append_command,
    declare_work,
    trial_family,
    wait_for,
)
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf import state as cleanup_model
from leaf.render_checks import one_frame, rendered, wait_until_ready
from leaf_dev.example_data import patch_manifest
from playwright.sync_api import expect
from render_cases_interaction import (
    ASKS_IN_ORDER,
    ASKS_PAGE,
    BOXLESS_SECTION_PAGE,
    COMMAND_HUB_EXAMPLE,
    COMMAND_HUB_PAGE,
    KEPT_SECTION_PAGE,
    LIVE_KEYS_APPARATUS,
    LIVE_KEYS_APPARATUS_REWRITTEN,
    LIVE_KEYS_ASK_REWRITTEN,
    LIVE_KEYS_ASK_WITHDRAWN,
    LIVE_KEYS_V1,
    LIVE_KEYS_V2,
    LIVE_KEYS_V3,
    LIVE_READING,
    LIVE_V1,
    LIVE_V2,
    LIVE_V3,
    MARKDOWN_REPLY,
    RELATIVE_WIDGET_PAGE,
    REPORT_PAGE,
    RETIRED_WIDGET_PAGE,
    RING,
    ROSTER_PAGE,
    SEATED_ASK_PAGE,
    SUGGESTION_PAGE,
    THREAD_ASKS,
    TRAVEL_PAGE,
    TWO_HOLDER_PAGE,
    WRAP_TOP,
    answered_comment,
    backdate_note,
    drifting_widget,
    executable_revision,
    live_url,
    stale_report,
)
from render_cases_layout import (
    banner_control,
    token_colour,
    unfolded_button,
)
from render_cases_navigation import (
    actions,
    address_code,
    composer_quote,
    go_to_address,
    painted,
    source_revision,
)
from render_harness import (
    CORPUS_SOURCES,
    EXAMPLE_PACKAGES,
    LANDING_TOP,
    RELEASE_FOCUS,
    REPLY_HOST_PAGE,
    SAMPLE_MARKUP,
    SAMPLE_TEXT,
    active_digit_bindings,
    compare_with,
    consume_browser_errors,
    draft_control,
    example_media,
    expect_asks_answered,
    expect_banner_control_offered,
    holding,
    is_problem,
    leaf_page,
    open_page,
    page_comment,
    pane_posture,
    panel_settled,
    post_event,
    refuse,
    regions_side_by_side,
    reported_browser_errors,
    resized,
    root_overflow,
    round_trip,
    said,
    scroll_settled,
    select,
    sending,
    shortcut_bar_text,
    stamp_page,
    suggestion_control,
    take_browser_errors,
    ticked,
    told,
    undo,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


VISUAL_REVIEW_GALLERY = next(
    path for path in CORPUS_SOURCES if path.stem == "visual-review-gallery"
)


def test_page_state_and_browser_share_the_decision_and_bound_sources(browser, serve):
    """The two clients read the same accepted decision and the same source revisions.

    A pin is a source id nothing rewrites: the reviewed copy keeps its revision while
    the current source moves on, and each widget's origin names its own file's digest,
    the file `page state` names for that source.
    """
    authored = leaf_page(
        "construction parity",
        '<h1 id="title">Review</h1>'
        '<lf-suggestion id="change"><lf-old>Retry twice.</lf-old>'
        "<lf-new>Retry three times.</lf-new></lf-suggestion>"
        '<lf-text-document id="current" source="instructions"></lf-text-document>'
        '<lf-text-document id="reviewed" source="reviewed-instructions" '
        'label="Reviewed"></lf-text-document>',
    )
    url = live_url(serve(authored))
    data_model.cmd_data_set(
        serve.page_dir, "reviewed-instructions", "Reviewed instructions.\n"
    )
    data_model.cmd_data_set(serve.page_dir, "instructions", "Earlier instructions.\n")
    data_model.cmd_data_set(serve.page_dir, "instructions", "Current instructions.\n")
    page = open_page(browser, url)
    suggestion_control(page, "change", "accept").click()
    round_trip(page)
    expect(page.locator("#change lf-old")).to_be_hidden()
    expect(page.locator("#change lf-new")).to_be_visible()

    result = CliRunner().invoke(cli_model.cli, ["page", "state", str(serve.page_dir)])
    assert result.exit_code == 0, result.output
    inspection = json.loads(result.output)
    [decision] = [entry for entry in inspection["state"] if entry["widget"] == "change"]
    assert (decision["action"], decision["detail"]) == ("decide", {"outcome": "accept"})
    for identity, source, value in (
        ("current", "instructions", "Current instructions.\n"),
        ("reviewed", "reviewed-instructions", "Reviewed instructions.\n"),
    ):
        [consumer] = inspection["data_bindings"][source]["consumers"]
        assert consumer["widget"] == identity
        stored = data_model.source_file(serve.page_dir, source)
        assert stored == serve.page_dir / inspection["data"]["dir"] / f"{source}.json"
        assert json.loads(stored.read_text())["value"] == value
        widget = page.locator(f"#{identity}")
        expect(widget.locator("code")).to_have_text(value)
        rendered = widget.locator("[data-lf-origin]").evaluate(
            "node => JSON.parse(node.dataset.lfOrigin)"
        )
        assert (rendered["source"], rendered["revision"]) == (
            source,
            source_revision(serve.page_dir, source),
        )
    expect(page.locator("#reviewed figcaption")).to_have_text("Reviewed")
    expect(page.locator("#current figcaption")).to_have_text("instructions")


def test_pr_review_package_keeps_the_authors_brief_distinct_and_stable(browser, serve):
    authored = leaf_page(
        "pull request brief",
        """
<h1 id="title">Review packet</h1>
<p id="agent-summary">The reviewer found one changed request path.</p>
<lf-pr-brief id="reviewed-pr" source="pr-1842"></lf-pr-brief>
""",
        head='<style>@import url("/page/theme.css");</style>',
    )
    url = serve(
        authored,
        packages=(ROOT / "examples/pr-walkthrough.page",),
        page_files={
            "theme.css": (ROOT / "examples/pr-walkthrough.page/theme.css").read_text()
        },
    )
    record = {
        "repository": "acme/leaf",
        "number": 1842,
        "title": "Preserve request identity through retries",
        "author": "mara",
        "base": "main",
        "head": "retry-ledger",
        "revision": "8f3b2cd",
        "status": "open",
        "description": (
            "**Retries** now retain the accepted request id.\n\n"
            "This keeps receipts attached after a lost response and preserves "
            "`Vec<T>` exactly; see the [retry notes](https://example.com/retry).\n\n"
            "> Reviewed against the retry ledger.\n\n"
            "Unsafe destinations stay words: [script](javascript:alert(1)), "
            "[inline data](data:text/html,boom), [local file](file:///tmp/secret), "
            "and [custom handler](editor://open/project).\n\n"
            '<span id="external-html">Raw HTML stays text.</span>'
        ),
        "observedAt": "2026-08-30T16:12:00-07:00",
        "diff": {"files": 4, "additions": 86, "deletions": 19, "commits": 3},
        "checks": {"Browser contract": "running", "Unit suite": "passed"},
    }
    data_model.cmd_data_set(serve.page_dir, "pr-1842", record)
    page = open_page(browser, url)
    widget = page.locator("#reviewed-pr")
    card = widget.locator(":scope > .pr-brief")

    expect(card).to_have_attribute("data-lf-projection", "reviewed-pr")
    expect(card).to_have_attribute("data-lf-datum", "acme/leaf#1842")
    expect(card).to_contain_text("acme/leaf · PR #1842")
    expect(card).to_contain_text("Preserve request identity through retries")
    expect(card).to_contain_text("Opened by mara")
    expect(card).to_contain_text("main → retry-ledger · revision 8f3b2cd")
    expect(card.locator(".pr-description h4")).to_have_text("Author's description")
    description = card.locator(".pr-description > div")
    paragraphs = description.locator(":scope > p")
    assert paragraphs.count() >= 2
    first, second = paragraphs.nth(0).bounding_box(), paragraphs.nth(1).bounding_box()
    assert second["y"] > first["y"] + first["height"]
    spacing = card.evaluate("""el => {
      const description = el.querySelector('.pr-description');
      const body = description.querySelector(':scope > div');
      return {
        heading: getComputedStyle(description.querySelector('h4')).marginBlockStart,
        observed: getComputedStyle(el.querySelector('.pr-observed')).marginBlockStart,
        first: getComputedStyle(body.firstElementChild).marginBlockStart,
        last: getComputedStyle(body.lastElementChild).marginBlockEnd,
      };
    }""")
    assert spacing == dict.fromkeys(("heading", "observed", "first", "last"), "0px")
    expect(description.locator("strong")).to_have_text("Retries")
    expect(description.locator("code")).to_have_text("Vec<T>")
    expect(description.get_by_role("link", name="retry notes")).to_have_attribute(
        "target",
        "_blank",
    )
    expect(description.locator("blockquote")).to_contain_text(
        "Reviewed against the retry ledger."
    )
    expect(description).to_contain_text(
        '<span id="external-html">Raw HTML stays text.</span>'
    )
    expect(description.locator("#external-html")).to_have_count(0)
    expect(
        description.locator(
            'a[href^="javascript:"], a[href^="data:"], '
            'a[href^="file:"], a[href^="editor:"]'
        )
    ).to_have_count(0)
    expect(description).to_contain_text(
        "Unsafe destinations stay words: script, inline data, local file, "
        "and custom handler."
    )
    expect(card.locator("table.pr-checks")).to_have_count(1)
    expect(
        card.locator(".pr-checks th", has_text="Browser contract")
    ).to_have_js_property(
        "scope",
        "row",
    )
    expect(card.locator(".pr-checks tr", has_text="Browser contract")).to_contain_text(
        "running"
    )
    expect(card.locator(".pr-checks tr", has_text="Unit suite")).to_contain_text(
        "passed"
    )
    expect(page.locator("#agent-summary")).to_have_text(
        "The reviewer found one changed request path."
    )

    selected = card.locator(".pr-description > div").evaluate(
        """body => {
          const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
          const phrase = 'accepted request id';
          let text = walker.nextNode();
          while (text && !text.data.includes(phrase)) text = walker.nextNode();
          if (!text) throw new Error(`missing ${phrase}`);
          const start = text.data.indexOf(phrase);
          const range = document.createRange();
          range.setStart(text, start);
          range.setEnd(text, start + phrase.length);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          body.closest('.pr-brief').__reviewIdentity = true;
          return selection.toString();
        }"""
    )
    assert selected == "accepted request id"

    changed = record | {
        "observedAt": "2026-08-30T16:18:00-07:00",
        "diff": {"files": 5, "additions": 91, "deletions": 19, "commits": 4},
        "checks": {"Browser contract": "passed", "Unit suite": "passed"},
    }
    data_model.cmd_data_set(serve.page_dir, "pr-1842", changed)
    told(page)
    expect(
        card.locator("dt", has_text="Files").locator("xpath=following-sibling::dd[1]")
    ).to_have_text("5")
    expect(card.locator(".pr-checks tr", has_text="Browser contract")).to_contain_text(
        "passed"
    )
    assert card.evaluate("el => el.__reviewIdentity") is True
    assert page.evaluate("() => getSelection().toString()") == selected
    page.get_by_role("button", name="Comment on selection").click()
    expect(page.locator("#lf-composer-quote")).to_contain_text(f"“{selected}”")
    expect(page.locator(".lf-fab-input")).to_be_focused()

    resized(page, 390, 900)
    assert root_overflow(page) == 0
    page.emulate_media(media="print")
    expect(card.locator(".pr-description > div")).to_be_visible()
    page.emulate_media(media="screen")


@pytest.mark.parametrize("returned", [False, True], ids=["stayed", "returned"])
def test_pr_review_observed_age_refreshes_without_a_data_change(
    browser, serve, returned
):
    """The observation time is rendered after Markdown loading, but still follows the
    shared clock when the source revision remains unchanged, including after the brief
    leaves the page and returns with its painting kept."""
    authored = leaf_page(
        "pull request clock",
        '<lf-pr-brief id="reviewed-pr" source="pr-1842"></lf-pr-brief>',
    )
    url = serve(
        authored,
        packages=(ROOT / "examples/pr-walkthrough.page",),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "pr-1842",
        {
            "repository": "acme/leaf",
            "number": 1842,
            "title": "Keep observed review evidence current",
            "author": "mara",
            "base": "main",
            "head": "clocked-render",
            "revision": "8f3b2cd",
            "status": "open",
            "description": "The description stays unchanged.",
            "observedAt": cleanup_model.now_iso(),
            "diff": {"files": 1, "additions": 1, "deletions": 0, "commits": 1},
            "checks": {"Unit suite": "passed"},
        },
    )
    page = open_page(browser, url)
    observed = page.locator(".pr-observed")
    expect(observed).to_have_text("Observed just now")
    if returned:
        page.locator("#reviewed-pr").evaluate(
            """async (element) => {
              const parent = element.parentNode;
              const next = element.nextSibling;
              element.remove();
              await new Promise((resolve) => setTimeout(resolve));
              parent.insertBefore(element, next);
              await new Promise((resolve) => setTimeout(resolve));
            }"""
        )

    # Only the browser's clock can be moved from here, and every state answer
    # recalibrates the page's one measured offset against the server's real `now`
    # (observeServerNow), which would put the three hours straight back. The page has
    # a standing reason to ask for one: a served page's status claims work, so its
    # activity carries a transition deadline the jump crosses, and the feed asks
    # rather than beats on that tick. Refusing the read is the arrangement the paint
    # under test needs — no data change, and no answer that could carry one.
    page.route("**/api/state*", refuse)
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=3))
    ticked(page)
    expect(observed).to_have_text("Observed 3h ago")


def test_pr_review_disconnect_during_markdown_load_is_safe(browser, serve):
    """A delayed paint leaves with its owner, while a same-batch move retains it: one
    brief is taken out of the page and another moved within it while the Markdown
    module they wait on is held."""
    authored = leaf_page(
        "pull request disconnect",
        '<lf-pr-brief id="reviewed-pr" source="pr-1842"></lf-pr-brief>'
        '<lf-pr-brief id="moved-pr" source="pr-1842"></lf-pr-brief>',
    )
    url = serve(
        authored,
        packages=(ROOT / "examples/pr-walkthrough.page",),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "pr-1842",
        {
            "repository": "acme/leaf",
            "number": 1842,
            "title": "Keep delayed rendering safe",
            "author": "mara",
            "base": "main",
            "head": "disconnect-safe",
            "revision": "8f3b2cd",
            "status": "open",
            "description": "The description waits for Markdown.",
            "observedAt": cleanup_model.now_iso(),
            "diff": {"files": 1, "additions": 1, "deletions": 0, "commits": 1},
            "checks": {"Unit suite": "passed"},
        },
    )
    page = browser.new_page(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )
    held = []
    page.route("**/vendor/markdown-it.esm.js", lambda route: held.append(route))
    try:
        with page.expect_request("**/vendor/markdown-it.esm.js"):
            page.goto(url, wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        assert held, "the positive control did not hold the lazy Markdown import"
        page.evaluate(
            """() => {
              const element = document.getElementById('reviewed-pr');
              window.detachedPr = element;
              window.detachedPrMarkup = element.innerHTML;
              element.remove();
              const moved = document.getElementById('moved-pr');
              const parent = moved.parentElement;
              moved.remove();
              parent.append(moved);
            }"""
        )
        held.pop(0).continue_()
        page.evaluate(
            """async () => {
              const {loadMarkdown} = await window.__lfRuntimeImport('/runtime/widget-api.js');
              await loadMarkdown();
            }"""
        )
        wait_until_ready(page)
        expect(page.locator("#moved-pr .pr-brief h3")).to_have_text(
            "Keep delayed rendering safe"
        )
        assert page.evaluate(
            "() => window.detachedPr.innerHTML === window.detachedPrMarkup"
        )
    finally:
        while held:
            held.pop(0).continue_()


def test_diff_coordinates_keep_identity_separate_from_source_navigation(browser, serve):
    """An analyzer's old-source fallback must never retarget a durable new address."""
    url = serve(
        leaf_page(
            "source coordinates",
            '<h1 id="title">Call locations</h1>'
            '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
            '<lf-diff id="patch" source="patch-data"><pre></pre></lf-diff>',
        ),
        packages=("diff",),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -5,4 +8,4 @@\n shifted()\n-removed()\n+added()\n next()\n last()\n",
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "calls-data",
        "calldiff diff main → feature\n  shifted()  app.py:8\n"
        "  absent_new()  app.py:6\n- removed()  app.py:6\n"
        "+ added()  app.py:9\n  last()  app.py:11",
    )
    page = open_page(browser, url)
    diff = page.locator("#patch")

    def resolved(key):
        return diff.evaluate(
            "(diff, key) => diff.lfDataDatum(JSON.stringify(key))?.dataset.lfDatum ?? null",
            key,
        )

    assert resolved(["app.py", "new", 5]) is None
    assert resolved(["app.py", "new", 6]) is None
    assert resolved(["app.py", "both", 5, 99]) is None
    assert resolved(["app.py", "both", 5, 8]) == '["app.py","both",5,8]'
    assert resolved(["app.py", "old", 8]) == '["app.py","both",8,11]'
    assert resolved(["app.py", "new", 8]) == '["app.py","both",5,8]'
    assert resolved(["app.py", "file", "extra"]) is None

    links = page.locator("#calls .lf-call-location:visible")
    for index, key in enumerate(
        [
            '["app.py","both",5,8]',
            None,
            '["app.py","old",6]',
            '["app.py","new",9]',
            '["app.py","both",8,11]',
        ]
    ):
        link = links.nth(index)
        location = link.inner_text()
        link.click()
        if key is None:
            expect(page.locator(".lf-live")).to_have_text(
                f"{location} is not present in the exact patch"
            )
            continue
        target = page.locator(f"#patch [data-lf-datum='{key}']")
        expect(target).to_be_focused()
        expect(target).to_be_in_viewport()
        expect(page.locator(".lf-live")).to_have_text(
            f"Opened {location} in the exact patch"
        )

    # A note describes its exact holder, including the side, rather than reconstructing
    # a section-only address that makes two different source lines sound identical.
    for side, number in [("old", 6), ("new", 9)]:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About the {side} line",
                "anchor": {
                    "section": "patch",
                    "datum": json.dumps(
                        ["app.py", side, number], separators=(",", ":")
                    ),
                },
            },
        )
    told(page)
    notes = page.locator(".lf-mark-note")
    expect(notes).to_have_count(2)
    names = notes.evaluate_all(
        "notes => notes.map(note => note.getAttribute('aria-label'))"
    )
    assert any("old line 6" in name and "app.py" in name for name in names), names
    assert any("new line 9" in name and "app.py" in name for name in names), names
    for key in ['["app.py","old",6]', '["app.py","new",9]']:
        assert page.locator(f"#patch [data-lf-datum='{key}']").evaluate(
            "line => line.ariaDetailsElements.some(note => note.matches('.lf-mark-note'))"
        )

    # Different exact context identities may share one old-side number in admitted
    # overlapping hunks. A source request must not choose among them by row order.
    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -5 +8 @@\n same()\n@@ -5 +20 @@\n same()\n",
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "calls-data",
        "calldiff diff main → feature\n- same()  app.py:5",
    )
    told(page)
    expect(links).to_have_count(1)
    links.first.click()
    expect(page.locator(".lf-live")).to_have_text(
        "app.py:5 is not present in the exact patch"
    )
    assert resolved(["app.py", "source", "old", 5]) is None
    assert resolved(["app.py", "old", 5]) is None
    assert resolved(["app.py", "both", 5, 8]) == '["app.py","both",5,8]'
    assert resolved(["app.py", "both", 5, 20]) == '["app.py","both",5,20]'
    assert resolved(["app.py", "new", 8]) == '["app.py","both",5,8]'
    assert resolved(["app.py", "new", 20]) == '["app.py","both",5,20]'


@pytest.mark.parametrize("manifest", [False, True])
def test_call_diff_source_paths_do_not_alias_durable_rename_coordinates(
    browser, serve, manifest
):
    """Old source b.py and durable destination b.py identify different rename rows."""
    url = serve(
        leaf_page(
            "renamed source paths",
            '<h1 id="title">Renamed calls</h1>'
            '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
            '<lf-diff id="patch" source="patch-data" collapsed><pre></pre></lf-diff>',
        ),
        packages=("diff",),
    )
    patch = ""
    for previous, current in [("a.py", "b.py"), ("b.py", "c.py")]:
        patch += (
            f"diff --git a/{previous} b/{current}\n"
            f"similarity index 50%\nrename from {previous}\nrename to {current}\n"
            f"--- a/{previous}\n+++ b/{current}\n"
            f"@@ -1,2 +1,2 @@\n context()\n-removed_{previous[0]}()\n+added_{current[0]}()\n"
        )
    patch += (
        "diff --git a/a.py b/a.py\nnew file mode 100644\n"
        "--- /dev/null\n+++ b/a.py\n@@ -0,0 +1 @@\n+new_a()\n"
    )
    data_model.cmd_data_set(
        serve.page_dir, "patch-data", patch_manifest(patch) if manifest else patch
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "calls-data",
        "calldiff diff main → feature\n- removed_b()  b.py:2\n"
        "- removed_a()  a.py:2\n+ new_a()  a.py:1\n+ added_b()  b.py:2",
    )
    page = open_page(browser, url)
    expect(page.locator("#patch .lf-diff-head").nth(0)).to_contain_text("a.py → b.py")
    expect(page.locator("#patch .lf-diff-head").nth(1)).to_contain_text("b.py → c.py")
    links = page.locator("#calls .lf-call-location:visible")
    for index, key in enumerate(
        [
            '["c.py","old",2]',
            '["b.py","old",2]',
            '["a.py","new",1]',
            '["b.py","new",2]',
        ]
    ):
        links.nth(index).click()
        line = page.locator(f"#patch [data-lf-datum='{key}']")
        expect(line).to_be_focused()
        expect(line).to_be_in_viewport()
        page.keyboard.press("c")
        expect(page.locator("#lf-composer-quote")).to_contain_text(json.loads(key)[0])
        expect(page.locator(".lf-fab-input")).to_be_focused()
        page.keyboard.press("Escape")
    # Source navigation never replaces the projection's destination identity.
    assert (
        page.locator("#patch").evaluate(
            'diff => diff.lfDataDatum(\'["b.py","old",2]\').textContent.trim()'
        )
        == "removed_a()"
    )

    # The parser and manifest producer admit repeated preimages even though a real
    # Git comparison ordinarily has only one rename per source. Such navigation has
    # no unique owner; canonical destination identities still name each file exactly.
    header = page.locator("#patch .lf-diff-head").nth(1)
    header.evaluate("node => { node.dataset.identityProbe = 'held'; node.focus(); }")
    stat_before = header.locator(".lf-diff-stat").bounding_box()
    long_preimage = (
        patch.replace("a/b.py b/c.py", "a/legacy/very/long/original.py b/c.py")
        .replace("rename from b.py", "rename from legacy/very/long/original.py")
        .replace("--- a/b.py", "--- a/legacy/very/long/original.py")
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        patch_manifest(long_preimage) if manifest else long_preimage,
    )
    told(page)
    expect(header).to_contain_text("legacy/very/long/original.py → c.py")
    stat_long = header.locator(".lf-diff-stat").bounding_box()
    assert stat_long["x"] == pytest.approx(stat_before["x"], abs=0.5)
    assert stat_long["y"] == pytest.approx(stat_before["y"], abs=0.5)
    ambiguous = (
        patch.replace("a/b.py b/c.py", "a/a.py b/c.py")
        .replace("rename from b.py", "rename from a.py")
        .replace("--- a/b.py", "--- a/a.py")
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        patch_manifest(ambiguous) if manifest else ambiguous,
    )
    told(page)
    expect(header).to_contain_text("a.py → c.py")
    expect(header).to_have_attribute("data-identity-probe", "held")
    expect(header).to_be_focused()
    stat_after = header.locator(".lf-diff-stat").bounding_box()
    assert stat_after["x"] == pytest.approx(stat_before["x"], abs=0.5)
    assert stat_after["y"] == pytest.approx(stat_before["y"], abs=0.5)
    links.nth(1).click()
    expect(page.locator(".lf-live")).to_have_text(
        "a.py:2 is not present in the exact patch"
    )
    assert page.locator("#patch").evaluate(
        "(diff, key) => diff.lfDataDatum(JSON.stringify(key)) === null",
        ["a.py", "source", "old", 2],
    )
    assert (
        page.locator("#patch").evaluate(
            "(diff, key) => diff.lfDataDatum(JSON.stringify(key)).textContent.trim()",
            ["c.py", "old", 2],
        )
        == "removed_b()"
    )

    # Copies share a preimage without owning its identity. A modified original and
    # two destinations cannot silently redirect an old-source link to the first copy.
    def copied(destination):
        return (
            f"diff --git a/a.py b/{destination}\n"
            f"similarity index 50%\ncopy from a.py\ncopy to {destination}\n"
            f"--- a/a.py\n+++ b/{destination}\n"
            f"@@ -1,2 +1,2 @@\n context()\n-removed_a()\n+copied_{destination[0]}()\n"
        )

    original = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
        "@@ -1,2 +1,2 @@\n context()\n-removed_a()\n+changed_a()\n"
    )
    for copy_patch in (original + copied("b.py"), copied("b.py") + copied("c.py")):
        data_model.cmd_data_set(
            serve.page_dir,
            "patch-data",
            patch_manifest(copy_patch) if manifest else copy_patch,
        )
        told(page)
        links.nth(1).click()
        expect(page.locator(".lf-live")).to_have_text(
            "a.py:2 is not present in the exact patch"
        )
        assert page.locator("#patch").evaluate(
            "(diff, key) => diff.lfDataDatum(JSON.stringify(key)) === null",
            ["a.py", "source", "old", 2],
        )
        assert (
            page.locator("#patch").evaluate(
                "(diff, key) => diff.lfDataDatum(JSON.stringify(key)).textContent.trim()",
                ["b.py", "old", 2],
            )
            == "removed_a()"
        )
        page.get_by_role("button", name="Comment on b.py", exact=True).click()
        expect(page.locator("#lf-composer-quote")).to_contain_text("§ b.py · file")
        page.keyboard.press("Escape")

    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        patch_manifest(copied("b.py")) if manifest else copied("b.py"),
    )
    told(page)
    links.nth(1).click()
    expect(page.locator('#patch [data-lf-datum=\'["b.py","old",2]\']')).to_be_focused()


def test_call_diff_keeps_the_user_on_a_row_a_new_capture_moves(browser, serve):
    """A capture that reorders the roots moves the group the user stands in, and one
    that reorders a root's calls moves the row: either way they stay on its location."""
    url = serve(
        leaf_page(
            "call diff order",
            '<h1 id="title">Request call change</h1>'
            '<lf-call-diff id="request-calls" source="request-call-diff" diff="patch">'
            '</lf-call-diff><lf-diff id="patch" source="review-patch"><pre></pre></lf-diff>',
        ),
        packages=("diff",),
    )
    header = "calldiff diff main → feature\n"
    first = "  Limiter.first(self)  gateway/limits.py:10\n+ ├─ one()  gateway/limits.py:11\n"
    calls = [
        "+ ├─ two()  gateway/limits.py:21\n",
        "+ ├─ three()  gateway/limits.py:22\n",
    ]
    second = "  Limiter.second(self)  gateway/limits.py:20\n"

    def capture(*roots):
        data_model.cmd_data_set(
            serve.page_dir, "request-call-diff", header + "".join(roots)
        )

    capture(first, second + "".join(calls))
    page = open_page(browser, url)
    widget = page.locator("#request-calls")
    groups = widget.locator(":scope > .lf-call-group")
    expect(groups).to_have_count(2)
    root = widget.locator(".lf-call-location", has_text="gateway/limits.py:20")
    root.focus()

    capture(second + "".join(calls), first)
    told(page)
    expect(groups.first.locator(".lf-call-group-summary .lf-call-body")).to_have_text(
        "Limiter.second(self)"
    )
    expect(root).to_be_focused()

    widget.locator(".lf-call-toggle").click()
    row = widget.locator(".lf-call-location", has_text="gateway/limits.py:22")
    row.focus()
    capture(second + "".join(reversed(calls)), first)
    told(page)
    expect(
        groups.first.locator(".lf-call-group-body .lf-call-body").first
    ).to_have_text("├─ three()")
    expect(row).to_be_focused()

    # Equal root names can share a stable call row while its group changes. The
    # closed destination may already exist or arrive in this capture; both expose
    # the user's focused row while a transfer without focus leaves its group closed.
    first_work = "  work()  app.py:1\n"
    second_work = "  work()  app.py:20\n"
    third_work = "  work()  app.py:60\n"
    unfocused = "  ├─ other_helper()  utils.py:3\n"
    shared = "  └─ helper()  utils.py:2\n"
    capture(first_work + unfocused + shared, second_work, third_work)
    told(page)
    expect(groups).to_have_count(3)
    expect(groups.nth(1)).not_to_have_attribute("open", "")
    location = widget.locator(".lf-call-location", has_text="utils.py:2")
    location.focus()
    for destination, roots in (
        ("app.py:20", (first_work, second_work + shared, third_work + unfocused)),
        (
            "app.py:40",
            (
                "  work()  app.py:30\n",
                "  work()  app.py:40\n" + shared,
                third_work + unfocused,
            ),
        ),
    ):
        capture(*roots)
        told(page)
        expect(
            location.locator("xpath=ancestor::details/preceding-sibling::*[1]").locator(
                ".lf-call-location"
            )
        ).to_have_text(destination)
        expect(location).to_be_visible()
        expect(location).to_be_focused()
        expect(groups.last).not_to_have_attribute("open", "")


def test_visual_review_controls_keep_keyboard_navigation_local(browser, serve):
    """Radio arrows, opacity keys, and select typeahead do not also navigate the case."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    selector = widget.locator(".lf-vr-case-select")
    initial = selector.evaluate("node => node.value")
    assert widget.evaluate(
        """owner => {
          const parent = owner.parentNode;
          const next = owner.nextSibling;
          const nodes = [...owner.querySelectorAll('*')];
          owner.remove();
          parent.insertBefore(owner, next);
          return nodes.every((node, index) => owner.querySelectorAll('*')[index] === node);
        }"""
    )
    widget.get_by_text("Inspect comparison", exact=True).click()
    widget.get_by_role("radio", name="Compare").click()
    page.keyboard.press("ArrowDown")
    expect(widget).to_have_attribute("data-inspection-mode", "flip")
    expect(selector).to_have_js_property("value", initial)
    page.keyboard.press("ArrowDown")
    expect(widget).to_have_attribute("data-inspection-mode", "overlay")
    slider = widget.get_by_role("slider", name="Candidate opacity")
    slider.focus()
    page.keyboard.press("ArrowUp")
    expect(widget.locator(".lf-vr-opacity-value")).to_have_text("55%")
    page.keyboard.press("Shift+ArrowRight")
    expect(widget.locator(".lf-vr-opacity-value")).to_have_text("60%")
    expect(selector).to_have_js_property("value", initial)
    widget.get_by_role("radio", name="Compare").focus()
    page.keyboard.press("Enter")
    expect(widget).to_have_attribute("data-inspection-mode", "compare")
    selector.click()
    page.keyboard.press("2")
    expect(widget.get_by_role("option", name="2 of 3", exact=False)).to_be_focused()
    page.keyboard.press("ArrowUp")
    page.keyboard.press("g")
    expect(page.locator(".lf-go-to-hint")).to_have_count(0)
    expect(selector).to_have_js_property("value", initial)
    page.keyboard.press("Escape")
    expect(selector).to_have_js_property("open", False)
    expect(widget.get_by_role("combobox", name="Selected visual case")).to_be_focused()


def test_visual_review_empty_navigation_is_unavailable(browser, serve):
    url = live_url(
        serve(
            leaf_page(
                "empty visual review",
                '<lf-visual-review id="visual-run" source="missing-run"></lf-visual-review>',
            ),
            packages=("visual-review",),
        )
    )
    page = open_page(browser, url)
    widget = page.locator("#visual-run")
    expect(widget.get_by_role("button", name="Previous")).to_be_disabled()
    expect(widget.get_by_role("combobox", name="Selected visual case")).to_be_disabled()
    expect(widget.get_by_role("button", name="Next", exact=True)).to_be_disabled()
    expect(widget.get_by_text("Waiting for visual-run data.")).to_be_visible()


def test_visual_review_ignores_a_late_load_from_detached_evidence(browser, serve):
    authored = leaf_page(
        "visual review replacement",
        '<lf-visual-review id="visual-run" source="docs-run"></lf-visual-review>',
    )
    media = {
        "/media/3cf0e3efe80c6b01.png": (
            example_media() / "3cf0e3efe80c6b01.png"
        ).read_bytes(),
        "/media/4f465a0582ab00fe.png": (
            example_media() / "4f465a0582ab00fe.png"
        ).read_bytes(),
    }
    url = live_url(serve(authored, packages=("visual-review",), media=media))
    capture = {
        "observedAt": "2026-09-10T10:30:00-07:00",
        "browser": "Chrome",
        "browserVersion": "140",
        "viewport": {"width": 900, "height": 373},
        "deviceScaleFactor": 2,
        "colorScheme": "light",
        "locale": "en-US",
        "timezone": "America/Los_Angeles",
    }

    def run(before, after, *, viewport_width):
        return {
            "title": "Replacement run",
            "base": {"revision": "base", "url": "https://base.example/"},
            "candidate": {
                "revision": "candidate",
                "url": "https://candidate.example/",
            },
            "cases": [
                {
                    "id": "changed",
                    "title": "Changed surface",
                    "path": "/changed",
                    "action": "Open the surface.",
                    "result": "The evidence remains aligned.",
                    "classification": "changed",
                    "capture": capture
                    | {"viewport": capture["viewport"] | {"width": viewport_width}},
                    "focus": {"x": 20, "y": 80, "width": 300, "height": 150},
                    "before": before,
                    "after": after,
                }
            ],
        }

    data_model.cmd_data_set(
        serve.page_dir,
        "docs-run",
        run(
            "/media/3cf0e3efe80c6b01.png",
            "/media/4f465a0582ab00fe.png",
            viewport_width=900,
        ),
    )
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    held = []
    context.route("**/media/slow-*.svg", lambda route: held.append(route))
    page = None
    try:
        page = open_page(browser, url, context=context)
        data_model.cmd_data_set(
            serve.page_dir,
            "docs-run",
            run(
                "/media/slow-before.svg",
                "/media/slow-after.svg",
                viewport_width=900,
            ),
        )
        told(page)
        expect(page.locator("#visual-run lf-shot img")).to_have_count(2)
        page.evaluate(
            "window.oldVisualReviewImages = [...document.querySelectorAll('#visual-run lf-shot img')]"
        )
        expect(page.locator("#visual-run lf-shot img").first).to_have_js_property(
            "naturalWidth", 0
        )
        assert len(held) == 2

        data_model.cmd_data_set(
            serve.page_dir,
            "docs-run",
            run(
                "/media/3cf0e3efe80c6b01.png",
                "/media/4f465a0582ab00fe.png",
                viewport_width=900,
            ),
        )
        told(page)
        host = page.locator("#visual-run .lf-vr-shot-host")
        expect(host.locator("lf-shot img")).to_have_count(2)
        expect(host.locator("lf-shot img").first).to_have_js_property(
            "naturalWidth", 780
        )
        rendered(page, facts=("updatesSettled",))
        shown = host.locator("lf-shot").bounding_box()

        stale_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="746"/>'
        )
        while held:
            held.pop(0).fulfill(content_type="image/svg+xml", body=stale_svg)
        page.wait_for_function(
            "() => window.oldVisualReviewImages.every(image => image.naturalWidth === 1800)"
        )
        rendered(page)
        assert host.locator("lf-shot").bounding_box() == shown
    finally:
        while held:
            held.pop(0).abort()


def test_visual_review_gallery_gives_a_laptop_to_the_evidence(browser, serve):
    """A focused review is a workspace, not prose followed by a narrow widget.

    The case picker never taxes the evidence width, and disposition follows the
    pixels. The review fills the window; Fit shrinks a mobile pair to fit its pane
    when the captured text remains readable, otherwise the pane scrolls the pair.
    Capture facts follow the comparison rather than delaying it.
    """
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 1440, 900)
    widget = page.locator("#visual-review-run")
    fit_reading = """node => {
          const body = node.querySelector('.lf-vr-cases');
          const frames = [...node.querySelectorAll(
            '.lf-vr-case:not([hidden]) .lf-shotframe')];
          return {bodyBottom: body.getBoundingClientRect().bottom,
                  framesBottom: Math.max(...frames.map(
                    frame => frame.getBoundingClientRect().bottom)),
                  image: frames[0].querySelector('img').getBoundingClientRect().width,
                  page: document.scrollingElement.scrollHeight - innerHeight};
        }"""
    contained = widget.evaluate(fit_reading)
    assert contained["framesBottom"] <= contained["bodyBottom"] + 0.5, contained
    assert 0.7 * 350 < contained["image"] < 350, contained
    assert contained["page"] <= 0, contained
    widget.get_by_text("Inspect comparison", exact=True).click()
    page.wait_for_function(
        """node => {
          const body = node.querySelector('.lf-vr-cases').getBoundingClientRect();
          return [...node.querySelectorAll('.lf-vr-case:not([hidden]) .lf-shotframe')]
            .every(frame => frame.getBoundingClientRect().bottom <= body.bottom + 0.5);
        }""",
        arg=widget.element_handle(),
    )
    opened = widget.evaluate(fit_reading)
    assert opened["image"] < contained["image"], opened
    widget.get_by_text("Inspect comparison", exact=True).click()
    page.wait_for_function(
        "(args) => args.node.querySelector('.lf-vr-case:not([hidden]) img')"
        ".getBoundingClientRect().width === args.width",
        arg={"node": widget.element_handle(), "width": contained["image"]},
    )
    resized(page, 1366, 600)
    widget.get_by_text("Inspect comparison", exact=True).click()
    gallery_scope = widget.get_by_role("radiogroup", name="Scope")
    expect(gallery_scope).to_be_visible()
    expect(widget).to_have_attribute("data-inspection-scope", "focus")
    geometry = widget.evaluate(
        """node => {
          const box = selector => node.querySelector(selector).getBoundingClientRect();
          const frames = [...node.querySelectorAll(
            '.lf-vr-case:not([hidden]) .lf-shotframe')]
            .map(frame => frame.getBoundingClientRect());
          return {widget: node.getBoundingClientRect(), title: box('.lf-vr-case-title'),
                  decision: box('.lf-vr-dispositions'), evidence: box('.lf-vr-shot-host'),
                  capture: box('.lf-vr-shot-host lf-shot'),
                  support: box('.lf-vr-support'), frames};
        }"""
    )
    assert geometry["widget"]["width"] > 1000
    assert geometry["decision"]["top"] >= geometry["evidence"]["bottom"]
    assert geometry["capture"]["bottom"] <= geometry["evidence"]["bottom"] + 1, geometry
    # The capture opens at the stage's top edge, inside its border: the stage sets the
    # box of the lf-shot it holds over that widget's own block margin.
    assert geometry["capture"]["top"] - geometry["evidence"]["top"] <= 1.5, geometry
    assert widget.get_attribute("data-compare-layout") == "side", geometry
    assert geometry["frames"][1]["left"] >= geometry["frames"][0]["right"]
    case_image_width = widget.locator(
        ".lf-vr-case:not([hidden]) .lf-shotframe img"
    ).first.evaluate("node => node.getBoundingClientRect().width")
    assert case_image_width == pytest.approx(350, abs=1), geometry
    assert widget.locator(".lf-vr-case:not([hidden]) .lf-vr-shot-host").evaluate(
        "node => node.scrollHeight <= node.clientHeight + 1"
    )
    assert widget.locator(".lf-vr-cases").evaluate(
        "node => node.scrollHeight > node.clientHeight"
    )
    assert geometry["support"]["top"] >= geometry["evidence"]["bottom"]
    case = widget.locator(".lf-vr-case:not([hidden])")
    claim_geometry = case.evaluate(
        """node => {
          const box = selector => node.querySelector(selector).getBoundingClientRect();
          const style = selector => getComputedStyle(node.querySelector(selector));
          return {
            actionTerm: box('.lf-vr-action-term'), action: box('.lf-vr-action'),
            resultTerm: box('.lf-vr-result-term'), result: box('.lf-vr-result'),
            titleFamily: style('.lf-vr-case-title').fontFamily,
            labelFamily: style('.lf-vr-action-term').fontFamily,
            valueFamily: style('.lf-vr-action').fontFamily,
          };
        }"""
    )
    assert claim_geometry["titleFamily"] == claim_geometry["valueFamily"]
    assert claim_geometry["labelFamily"] == claim_geometry["valueFamily"]
    assert claim_geometry["actionTerm"]["left"] == pytest.approx(
        claim_geometry["action"]["left"], abs=1
    )
    assert claim_geometry["resultTerm"]["left"] == pytest.approx(
        claim_geometry["result"]["left"], abs=1
    )
    assert claim_geometry["actionTerm"]["bottom"] <= claim_geometry["action"]["top"]
    assert claim_geometry["resultTerm"]["bottom"] <= claim_geometry["result"]["top"]
    # Archived captures keep pinned revisions without advertising invented destinations.
    expect(case.locator(".lf-vr-links > a:visible")).to_have_count(0)
    expect(case.get_by_text("Capture details", exact=True)).to_be_visible()
    expect(case.locator(".lf-vr-provenance")).to_be_hidden()
    summary = case.get_by_text("Capture details", exact=True)
    summary.scroll_into_view_if_needed()
    scroll_settled(page)
    summary_box = summary.bounding_box()
    summary.click()
    expect(case.locator(".lf-vr-provenance")).to_be_visible()
    assert summary.bounding_box() == summary_box, (
        "opening capture facts moved their press"
    )

    revision = case.locator(".lf-vr-candidate-revision")
    assert revision.evaluate("node => node.getClientRects().length") == 1
    details_box = case.locator(".lf-vr-details").bounding_box()
    support_box = case.locator(".lf-vr-support").bounding_box()
    assert details_box and support_box
    assert details_box["x"] >= support_box["x"]
    assert (
        details_box["x"] + details_box["width"]
        <= support_box["x"] + support_box["width"] + 1
    )
    revision.evaluate("node => node.textContent = 'a'.repeat(40)")
    assert case.locator(".lf-vr-provenance").evaluate(
        "node => node.scrollWidth <= node.clientWidth"
    )
    resized(page, 560, 720)
    assert root_overflow(page) == 0
    resized(page, 390, 900)
    assert root_overflow(page) == 0
    resized(page, 1366, 768)
    shot_host = widget.locator(".lf-vr-case:not([hidden]) .lf-vr-shot-host")
    assert shot_host.evaluate("node => node.scrollWidth == node.clientWidth")
    expect(widget).to_have_attribute("data-compare-layout", "side")

    page.emulate_media(media="print")
    print_widths = widget.locator(".lf-vr-case lf-shot img").evaluate_all(
        "images => images.map(image => image.getBoundingClientRect().width)"
    )
    assert len(print_widths) == 6
    assert widget.locator(".lf-vr-case lf-shot img").evaluate_all(
        "images => images.every(image => image.getBoundingClientRect().width <= image.naturalWidth / 2 + 1)"
    )
    expect(widget.locator(".lf-vr-focus").first).to_be_visible()
    page.emulate_media(media="screen")

    selected = widget.locator(".lf-vr-case-select")
    with sending(page, "the intended responsive change disposition"):
        case.get_by_role("button", name="Looks right").click()
    page.keyboard.press("ArrowDown")
    expect(selected).to_have_js_property("value", "keep-mobile-destinations")
    expect(widget).to_have_attribute("data-compare-layout", "stack")
    expect(gallery_scope).to_be_visible()
    expect(widget).to_have_attribute("data-inspection-scope", "focus")
    with sending(page, "the seeded responsive regression disposition"):
        widget.locator(".lf-vr-case:not([hidden])").get_by_role(
            "button", name="Needs work"
        ).click()
    expect(widget.locator(".lf-vr-progress")).to_have_text("2 of 3 cases reviewed")
    page.keyboard.press("ArrowDown")
    expect(selected).to_have_js_property("value", "check-desktop-navigation")
    expect(widget).to_have_attribute("data-compare-layout", "stack")
    expect(gallery_scope).to_be_hidden()
    expect(widget).to_have_attribute("data-inspection-scope", "full")
    assert widget.locator(".lf-vr-case:not([hidden]) .lf-vr-shot-host").evaluate(
        "node => node.scrollHeight <= node.clientHeight + 1"
    )


def test_a_visual_review_inside_a_section_of_a_workspace_flows(browser, serve):
    """Only a review the workspace gives a height fills it. In a section of the body it is
    not told it has one (`--lf-full-height` does not inherit), so it takes its content's
    height with its pair at the stage's width, the body scrolls it, and it settles:
    sized from its own pane, it grew a little on each pass."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 1440, 900)
    widget = page.locator("#visual-review-run")
    expect(widget.locator(".lf-vr-case:not([hidden]) lf-shot")).to_be_visible()
    widget.evaluate(
        """review => {
          const section = document.createElement('section');
          const intro = document.createElement('p');
          intro.textContent = 'An intro paragraph before the review.';
          review.before(section);
          section.append(intro, review);
        }"""
    )
    reading = """review => ({
      image: review.querySelector('.lf-vr-case:not([hidden]) .lf-shotframe img')
        .getBoundingClientRect().width,
      paneScrolls: getComputedStyle(review.querySelector('.lf-vr-cases')).overflowY,
    })"""
    rendered(page)
    first = widget.evaluate(reading)
    page.wait_for_timeout(500)
    rendered(page)
    assert widget.evaluate(reading) == first == {"image": 350, "paneScrolls": "visible"}


def test_visual_review_fits_frames_using_the_authored_spacing(browser, serve):
    """Fitting and the painted frame tracks agree when spacing is authored in rem: the
    frames stand a rem apart, and where the page scrolls the review, in a window too
    short for the workspace to fill, the pair takes the stage's whole width."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    widget.locator(".lf-vr-shot-host").evaluate_all(
        "nodes => nodes.forEach(node => node.style.setProperty('--sp-2', '1rem'))"
    )
    for height in (800, 470):
        resized(page, 760, height)
        expect(widget).to_have_attribute("data-compare-layout", "side")
        geometry = widget.locator(
            ".lf-vr-case:not([hidden]) .lf-vr-shot-host"
        ).evaluate(
            """host => {
              const shot = host.querySelector('lf-shot');
              const frames = [...shot.querySelectorAll('.lf-shotframe')]
                .map(frame => frame.getBoundingClientRect());
              return {available: host.clientWidth,
                      width: shot.getBoundingClientRect().width,
                      gap: frames[1].left - frames[0].right,
                      rem: parseFloat(getComputedStyle(document.documentElement).fontSize),
                      overflow: host.scrollWidth - host.clientWidth};
            }"""
        )
        assert geometry["gap"] == pytest.approx(geometry["rem"], abs=0.1), geometry
        assert geometry["overflow"] == 0, geometry
    assert geometry["width"] == pytest.approx(geometry["available"], abs=0.1), geometry


def test_visual_review_discloses_focus_without_distorting_unsupported_browsers(
    browser, serve
):
    page = open_page(
        browser,
        serve(VISUAL_REVIEW_GALLERY),
        init_script="""
          const supports = CSS.supports.bind(CSS);
          CSS.supports = (property, value) =>
            property === 'object-view-box' ? false : supports(property, value);
        """,
    )
    widget = page.locator("#visual-review-run")
    case = widget.locator(".lf-vr-case:not([hidden])")
    host = case.locator(".lf-vr-shot-host")
    expect(widget).to_have_attribute("data-inspection-scope", "full")
    expect(widget.get_by_role("radiogroup", name="Scope")).to_be_hidden()
    scope = widget.locator(".lf-vr-scope-group")
    scope.evaluate("""group => {
      group.value = 'focus';
      group.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    expect(scope).to_have_js_property("value", "full")
    expect(host.locator("lf-shot")).to_have_attribute("data-lf-shot-focus", "true")
    expect(host.locator("lf-shot")).to_have_attribute("data-lf-shot-crop", "false")
    image = case.locator(".lf-shotframe img").first.evaluate(
        """node => ({
          renderedRatio: node.getBoundingClientRect().width / node.getBoundingClientRect().height,
          naturalRatio: node.naturalWidth / node.naturalHeight,
          objectViewBox: getComputedStyle(node).objectViewBox,
        })"""
    )
    assert image["renderedRatio"] == pytest.approx(image["naturalRatio"], rel=0.01)
    assert image["objectViewBox"] == "none"
    marker = case.locator(".lf-shotframe").first.evaluate(
        "frame => getComputedStyle(frame, '::after').getPropertyValue('content')"
    )
    assert marker == '""'
    expect(case.locator(".lf-vr-focus")).to_have_text("20, 100 · 350 × 640 CSS px")


@pytest.mark.parametrize("quote_anchor", [True, False], ids=["passage", "whole-datum"])
def test_a_source_replacement_preserves_the_focused_draft_and_its_original_anchor(
    browser, serve, quote_anchor
):
    url = serve(
        leaf_page(
            "source comment draft",
            '<div><h1 id="title">Review</h1>'
            '<lf-text-document id="source" source="document"></lf-text-document></div>',
            layout="sidebar",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "document", "Original source words.")
    original_revision = source_revision(serve.page_dir, "document")
    page = open_page(browser, url)
    resized(page, 900, 900)
    if quote_anchor:
        words = page.locator("#source code").evaluate(
            """code => {
              const range = document.createRange();
              range.selectNodeContents(code);
              return range.getBoundingClientRect().toJSON();
            }"""
        )
        y = words["top"] + words["height"] / 2
        select(page, (words["left"] + 1, y), (words["right"] - 1, y))
    else:
        page.locator("#source [data-lf-datum]").click(modifiers=["Alt"])
    quote = page.locator("#lf-composer-quote")
    # A whole datum is named as its widget is; only a quote carries its words.
    expect(quote).to_contain_text(
        "Original source words." if quote_anchor else "§ text-document"
    )
    draft = page.locator(".lf-fab-input")
    write(draft, "Keep this comment about the original source.")
    expect(draft).to_be_focused()
    assert (
        page.evaluate(
            "() => CSS.highlights.get('lf-pending').size + "
            "document.querySelectorAll('#source.lf-pending, #source .lf-pending').length"
        )
        > 0
    )
    original_bar = page.locator(".lf-fab-bar").bounding_box()

    data_model.cmd_data_set(serve.page_dir, "document", "Replacement source words.")
    told(page)
    expect(page.locator("#source code")).to_have_text("Replacement source words.")
    expect(draft).to_be_focused()
    expect(draft).to_have_js_property(
        "value", "Keep this comment about the original source."
    )
    expect(quote).to_contain_text(
        "“Original source words.”" if quote_anchor else "§ text-document"
    )
    assert page.evaluate("() => CSS.highlights.get('lf-pending').size") == 0
    expect(page.locator("#source.lf-pending, #source .lf-pending")).to_have_count(0)
    # Earlier data no longer supplies a passage fragment. The surviving datum
    # keeps the editor beside it; sending hands that position to the first card.
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_have_attribute("data-lf-placement", re.compile("(top|bottom)-start"))
    rendered(page)
    before = bar.bounding_box()
    datum = page.locator("#source [data-lf-datum]").bounding_box()
    assert before["x"] == pytest.approx(original_bar["x"], abs=1)

    with sending(page, "the draft about the replaced source"):
        draft.press("ControlOrMeta+Enter")
    comment = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    expected_anchor = {
        "section": "source",
        "datum": "document",
        "source": "document",
        "source_revision": original_revision,
    }
    if quote_anchor:
        expected_anchor["quote"] = "Original source words."
    assert comment["anchor"] == expected_anchor
    expect(page.locator(".lf-thread .lf-anchor-status")).to_have_text("Earlier data")
    assert (
        page.locator(".lf-thread .lf-anchor-status").evaluate(
            "el => getComputedStyle(el).borderTopWidth"
        )
        == "0px"
    )
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_css("opacity", "1")
    rendered(page)
    assert card.bounding_box()["x"] == pytest.approx(before["x"], abs=1)
    expect(card.locator(".lf-page-thread")).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(card).to_be_hidden()
    page.locator(".lf-margin-marker").click()
    expect(card).to_have_css("opacity", "1")
    rendered(page)
    # Reopening is a fresh placement on the datum's current full-width box; it
    # need not retain the old quote's inline start after its words disappeared.
    reopened = card.bounding_box()
    assert datum["x"] < reopened["x"] + reopened["width"]
    assert reopened["x"] < datum["x"] + datum["width"]
    assert reopened["y"] == pytest.approx(datum["y"] + datum["height"] + 8, abs=2)


def test_a_large_diff_filters_and_navigates_lazy_files(browser, serve):
    authored = leaf_page(
        "large diff review",
        '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch" '
        "collapsed><pre></pre></lf-diff>",
    )
    url = serve(authored)
    manifest = {
        "files": [
            {
                "path": path,
                "operation": "modify",
                "hunkCount": 1,
                "binary": False,
                "additions": 1,
                "deletions": 1,
                "patch": f"""diff --git a/{path} b/{path}
--- a/{path}
+++ b/{path}
@@ -1 +1 @@
-return "old"
+return "new"
""",
            }
            for path in ("src/first.py", "src/second file.py", "tests/third.py")
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "review-patch", manifest)
    page = open_page(browser, url)
    diff = page.locator("#patch")
    progress = diff.locator(".lf-diff-progress")
    summaries = diff.locator("summary")
    expect(progress).to_have_text("3 files")
    expect(summaries).to_have_count(3)
    expect(diff.locator("[data-line]")).to_have_count(0)

    # A source refresh rebuilds file shells; lazy rows inherit its new revision.
    refreshed = json.loads(json.dumps(manifest))
    refreshed["files"][0]["additions"] = 2
    refreshed["files"][0]["patch"] = (
        refreshed["files"][0]["patch"]
        .replace("@@ -1 +1 @@", "@@ -1 +1,2 @@")
        .replace('+return "new"', '+return "new"\n+return "newer"')
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", refreshed)
    refreshed_revision = source_revision(serve.page_dir, "review-patch")
    told(page)
    summaries.nth(1).click()
    summaries.nth(2).click()
    expect(diff.locator("[data-line]")).to_have_count(4)
    origins = diff.locator("[data-lf-origin]").evaluate_all(
        "nodes => nodes.map(node => JSON.parse(node.dataset.lfOrigin))"
    )
    assert {tuple(origin["path"]) for origin in origins} == {
        ("files", 0, "path"),
        ("files", 1, "path"),
        ("files", 1, "patch"),
        ("files", 2, "path"),
        ("files", 2, "patch"),
    }
    assert all(
        origin["source"] == "review-patch"
        and origin["input"] == "document"
        and origin["revision"] == refreshed_revision
        for origin in origins
    ), "file and lazy-line datums must retain the revision that built their manifest"

    summaries.nth(0).focus()
    page.keyboard.press("/")
    search = diff.locator(".lf-diff-search input")
    expect(search).to_be_focused()
    search.fill("second")
    expect(summaries.nth(0)).to_be_hidden()
    expect(summaries.nth(1)).to_be_visible()
    expect(summaries.nth(2)).to_be_hidden()
    expect(progress).to_have_text("1 of 3")

    # The frame belongs to the diff, not to the query value globally. Leaving the widget
    # retires it: Escape over page prose must not clear a hidden filter or pull focus back.
    page.locator("#title").click()
    expect(search).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(search).to_have_value("second")
    expect(search).not_to_be_focused()

    # The filter is a layer of the patch and the box is inside it: the first Escape
    # clears a live query, and the second leaves the box for the patch it filters, which
    # is the box's container rather than the file header the user pressed `/` from.
    summaries.nth(1).focus()
    page.keyboard.press("/")
    expect(search).to_be_focused()
    page.keyboard.press("Escape")
    expect(search).to_have_value("")
    expect(search).to_be_focused()
    expect(summaries).to_have_count(3)
    for index in range(3):
        expect(summaries.nth(index)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("lf-diff")).to_be_focused()

    page.keyboard.press("/")
    search.fill("second")
    expect(progress).to_have_text("1 of 3")

    summaries.nth(1).focus()
    page.keyboard.press("}")
    expect(summaries.nth(1)).to_be_focused()
    expect(diff.locator("details").nth(1)).to_have_attribute("open", "")
    expect(diff.locator("[data-line]")).to_have_count(4)

    resized(page, 390, 900)
    assert root_overflow(page) == 0
    printed_query = {
        "code": "words-left-screen",
        "words": "second",
        "place": search.evaluate("field => window.lfPlace(field)"),
    }
    page.emulate_media(media="print")
    # This fixture explicitly enters print rendering, where search tools disappear;
    # no native Print gesture is delivered by media emulation.
    page.evaluate("lfWordsJudged()")
    reported_browser_errors(page, printed_query)
    expect(diff.locator(".lf-diff-tools")).to_be_hidden()
    for index in range(3):
        expect(summaries.nth(index)).to_be_visible()
    page.emulate_media(media="screen")


def test_a_diff_counts_and_filters_inline_files(browser, serve):
    authored = leaf_page(
        "diff evidence",
        """
<h1>Changed files</h1>
<lf-diff id="single"><pre>
diff --git a/src/only.py b/src/only.py
--- a/src/only.py
+++ b/src/only.py
@@ -1 +1 @@
-return "old"
+return "new"
</pre></lf-diff>
<lf-diff id="patch"><pre>
diff --git a/src/first.py b/src/first.py
--- a/src/first.py
+++ b/src/first.py
@@ -1 +1 @@
-return "old"
+return "new"
diff --git a/tests/second.py b/tests/second.py
--- a/tests/second.py
+++ b/tests/second.py
@@ -1 +1 @@
-assert old
+assert new
</pre></lf-diff>
""",
    )
    page = open_page(browser, serve(authored))
    diff = page.locator("#patch")

    expect(page.locator("#single .lf-diff-progress")).to_have_text("1 file")
    expect(diff.locator(".lf-diff-progress")).to_have_text("2 files")
    search = diff.locator(".lf-diff-search input")
    search.fill("second")
    expect(diff.locator(".lf-diff-progress")).to_have_text("1 of 2")
    expect(diff.locator("summary").nth(0)).to_be_hidden()
    expect(diff.locator("summary").nth(1)).to_be_visible()


def test_the_live_page_adopts_a_revision_and_stamps_it_without_replacing_main(
    browser, serve
):
    """A valid save advances the live surface; stamping only changes its label.

    Nothing here is executable, so the user keeps this document: the next file is
    fetched while they read, then its authored markup is patched onto the page they
    are standing in. The URL, runtime identity, open chrome, `main` itself, and the
    passage's viewport coordinate therefore survive. Five paragraphs arrive above that
    passage so a raw scroll offset cannot satisfy the position assertion.
    """
    # Deliberately collide with a property the runtime owns after startup. Authored
    # replacement must remove source properties without erasing a live runtime override.
    first = LIVE_V1.replace(
        '<html lang="en">',
        '<html lang="en" style="--lf-thread-panel-width: 420px">',
    ).replace("<body>", '<body tabindex="0">')
    version_url = serve(first)
    page = open_page(browser, live_url(version_url))
    assert "/versions/" not in page.url, f"the live address redirected to {page.url}"

    page.locator("#live-reading").scroll_into_view_if_needed()
    page.evaluate(
        """() => { document.scrollingElement.scrollBy({
          top: document.getElementById('live-reading').getBoundingClientRect().top - 140,
          behavior: 'instant'
        }); window.__leafDocument = 'the same runtime';
          window.__leafMain = document.querySelector('main'); }"""
    )
    original_document = page.evaluate("performance.timeOrigin")
    before = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    runtime_panel_width = page.locator("html").evaluate(
        "el => el.style.getPropertyValue('--lf-thread-panel-width')"
    )
    assert runtime_panel_width == "420px"

    second = LIVE_V2.replace(
        '<html lang="fr" data-live-root="second">',
        '<html lang="fr" data-live-root="second" '
        'style="--lf-thread-panel-width: 1000px">',
    )
    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Live second")

    assert page.evaluate("performance.timeOrigin") == original_document, (
        "the revision replaced the browser document rather than its authored page"
    )
    assert page.evaluate("window.__leafDocument") == "the same runtime", (
        "the revision replaced the browser document rather than its authored page"
    )
    assert page.evaluate("window.__leafMain === document.querySelector('main')"), (
        "the revision replaced the authored main rather than patching it"
    )
    assert "/versions/" not in page.url, (
        f"the update changed the live address to {page.url}"
    )
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))
    assert (
        page.locator("html").evaluate(
            "el => el.style.getPropertyValue('--lf-thread-panel-width')"
        )
        == runtime_panel_width
    ), "authored style replacement erased a runtime-owned property"
    after = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(after - before) <= 4, (
        f"the passage moved from {before}px to {after}px in the viewport"
    )
    version = page.locator(".lf-version")
    expect(version).to_have_text("Showing Draft")
    expect(version).to_have_attribute("title", re.compile(r"^Draft after v1:"))
    expect(version).to_have_attribute("aria-label", "Draft after v1: open versions")
    banner_control(page, ".lf-version").click()
    expect(page.locator(".lf-version-menu")).to_contain_text("Current · Draft after v1")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-signoff")).to_have_count(1)
    expect(page.locator(".lf-signoff")).to_be_visible()
    expect(page.locator(".lf-signoff")).to_have_attribute("aria-disabled", "true")
    expect(page.locator(".lf-signoff")).to_have_attribute(
        "aria-description", "There is no stamped version to approve yet"
    )
    assert page.locator('meta[name="description"]').get_attribute("content") == "second"
    assert page.locator("html").get_attribute("lang") == "fr"
    assert page.locator("html").get_attribute("data-live-root") == "second"
    expect(page.locator("html")).to_have_attribute("data-lf-live", "")
    expect(page.locator("html")).to_have_attribute("data-lf-interactive", "")
    expect(page.locator("body")).to_have_class(re.compile(r"\blive-second\b"))
    assert page.locator("body").get_attribute("data-live-body") == "second"
    assert (
        page.locator("body").evaluate(
            "el => el.style.getPropertyValue('--live-body').trim()"
        )
        == "2"
    ), "the new version's authored root attributes did not activate"
    assert (
        page.locator("#live-reading").evaluate(
            "el => getComputedStyle(el).getPropertyValue('--live-cut').trim()"
        )
        == "2"
    ), "the new version's page-local style did not activate"

    # The revision owns authored body attributes, and the runtime's let-go still takes
    # the user off an element after the replacement.
    page.locator("#live-reading").evaluate(
        "el => { el.tabIndex = -1; el.focus({preventScroll: true}); }"
    )
    page.evaluate(RELEASE_FOCUS)
    assert page.evaluate("document.activeElement === document.body")

    page.evaluate("window.__leafMain = document.querySelector('main')")
    stamped = CliRunner().invoke(
        cli_model.cli,
        ["page", "stamp", str(serve.page_dir), "--text", "new findings"],
    )
    assert stamped.exit_code == 0, stamped.output
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    signoff = page.locator(".lf-signoff")
    expect(signoff).to_be_visible()
    assert signoff.evaluate(
        "el => parseFloat(el.style.getPropertyValue('--lf-reserved-width')) > 0"
    ), "approval was measured while its control was detached"
    assert page.evaluate("window.__leafMain === document.querySelector('main')"), (
        "stamping the displayed revision replaced its main"
    )

    write(page_comment(page), "This comment belongs to the live draft.")
    with sending(page, "the comment on the live draft"):
        page.locator(".lf-general .lf-compose-submit").click()
    assert events_model.read_events(serve.page_dir)[-1]["revision"] == 2


@pytest.mark.watch_shifts
def test_live_news_keeps_the_reading_draft_and_resting_target(browser, serve):
    """Live news keeps the user's simultaneous reading, editing, and pointer places.

    At a phone's width, where the tall reply grows the most, the following passage and
    editor are visible below the reply's insertion point.
    Status paints immediately and a tall reply waits behind its fixed-row notice.
    An unrelated source revision arrives while retaining the editor and restoring the
    page's reading position. Opening the reply proves the notice held genuine growth.
    """
    source = SEATED_ASK_PAGE.replace(
        "</main>",
        '<p id="reading">The next passage remains where I am reading.</p>'
        + "<p>Further context. "
        + "Context. " * 300
        + "</p></main>",
    )
    url = serve(source)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 390, 900)
    thread = page.locator("#jobs .lf-page-thread")
    editor = thread.locator("leaf-text")
    words = "  Keep the middle of this unsent thought.  "
    write(editor, words)
    editor.evaluate("box => box.setSelectionRange(7, 17, 'backward')")
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    reading = page.locator("#reading")
    expect(reading).to_be_in_viewport()
    target = resolve.bounding_box()
    assert target
    point = {
        "x": target["x"] + target["width"] / 2,
        "y": target["y"] + target["height"] / 2,
    }
    page.mouse.move(**point)
    rendered(page)
    # Keep Chrome's native clock and deliver news after its 500 ms input grace period.
    page.wait_for_timeout(600)
    place = reading.bounding_box()
    box = editor.bounding_box()
    assert place and box

    def kept():
        expect(editor).to_be_focused()
        assert editor.evaluate(
            "box => [box.value, box.selectionStart, box.selectionEnd, box.selectionDirection]"
        ) == [words, 7, 17, "backward"]
        assert reading.bounding_box() == pytest.approx(place, abs=0.5)
        assert editor.bounding_box() == pytest.approx(box, abs=0.5)
        assert resolve.bounding_box() == pytest.approx(target, abs=0.5)
        assert resolve.evaluate(
            "(node, p) => node.contains(document.elementFromPoint(p.x, p.y))", point
        ), "arriving news took the resting pointer off Resolve"

    declare_work(serve.page_dir, "Checking the order of these jobs", item=root["id"])
    told(page)
    expect(page.locator(".lf-status-detail")).to_contain_text("Checking the order")
    rendered(page)
    kept()

    reply = "\n\n".join(["The first job needs a careful explanation."] * 12)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "revision": 1,
            "text": reply,
        },
    )
    told(page)
    notice = thread.get_by_role("button", name="1 new reply", exact=True)
    expect(notice).to_be_visible()
    expect(thread.locator(".lf-msg")).to_have_count(1)
    rendered(page)
    kept()

    (serve.page_dir / "index.html").write_text(
        source.replace(
            "<title>seated question</title>", "<title>Jobs updated</title>"
        ).replace('<h1 id="h">', '<p id="new-context">New context.</p><h1 id="h">')
    )
    told(page)
    expect(page).to_have_title("Jobs updated")
    expect(page.locator("#new-context")).to_have_count(1)
    rendered(page)
    kept()

    # A press releases genuine growth; all preceding observations were made at rest.
    notice.click()
    expect(thread.locator(".lf-msg")).to_have_count(2)
    expect(thread.locator(".lf-msg").last).to_contain_text(
        "The first job needs a careful explanation."
    )
    rendered(page)
    assert reading.bounding_box()["y"] > place["y"] + 100


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("above", marks=pytest.mark.watch_shifts),
        # Unwatched: the revision rewrites the words of the text node the reader reads,
        # and the watch compares that node's lines by their order, so every line below
        # the rewrite reads as moved, though each holds other words than it did.
        "inside",
        pytest.param("figure", marks=pytest.mark.watch_shifts),
    ],
)
def test_live_revision_keeps_the_visible_semantic_reading(browser, serve, where):
    """A content revision keeps the reader on a page that still asks for approval.

    Native scroll anchoring is disabled by this page's layout, so it cannot conceal
    a broken semantic carry when five paragraphs arrive above the reader. Where the
    reader stands partway into a long paragraph, its start under the banner, and the
    revision also lengthens words of it above their line, the line they read stays
    where it was, not the paragraph's opening line. Where a figure taller than the
    window fills it, with no words on screen, the part of the figure at the edge stays
    there, not the old scroll offset, which now names the arriving paragraphs.
    """
    anchoring = "<style>html { overflow-anchor: none; }</style>"
    first = LIVE_V1.replace(
        "</head>",
        '<meta name="lf-review" content="sign-off">' + anchoring + "</head>",
    )
    second = LIVE_V2.replace("</head>", anchoring + "</head>")
    if where == "inside":
        words = " ".join(f"w{n:04d}" for n in range(1, 500))
        first = first.replace(LIVE_READING, words)
        second = second.replace(LIVE_READING, words).replace(
            " w0005 ", " " + "a longer phrase standing where one word stood " * 6
        )
    if where == "figure":
        figure = (
            '<svg id="live-reading" viewBox="0 0 100 300"'
            ' style="display:block;width:100%;height:auto">'
            + "".join(
                f'<rect x="0" y="{n * 10}" width="100" height="10"'
                f' fill="hsl({n * 12} 60% 60%)"/>'
                for n in range(30)
            )
            + "</svg>"
        )
        paragraph = f'<p id="live-reading">{LIVE_READING}</p>'
        first = first.replace(paragraph, figure)
        second = second.replace(paragraph, figure)
    page = open_page(browser, live_url(serve(first)))
    resized(page, 1200, 900)
    reading = page.locator("#live-reading")
    reading.scroll_into_view_if_needed()
    page.evaluate(
        """(where) => {
          const box = document.getElementById('live-reading').getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: box.top - {above: 140, inside: -300, figure: -0.4 * box.height}[where],
            behavior: 'instant'
          });
        }""",
        where,
    )
    scroll_settled(page)
    expect(reading).to_be_in_viewport()
    # The first word at or below the landing band, and where it stands; in a figure,
    # how far through its height the band cuts it.
    word_at_band = f"""async (word) => {{
      const band = {LANDING_TOP};
      const reading = document.getElementById('live-reading');
      if (reading.localName === 'svg') {{
        const box = reading.getBoundingClientRect();
        return {{top: (band - box.top) / box.height}};
      }}
      const text = reading.firstChild;
      const range = document.createRange();
      for (const match of text.data.matchAll(/\\S+/g)) {{
        if (word && match[0] !== word) continue;
        range.setStart(text, match.index);
        range.setEnd(text, match.index + match[0].length);
        const rect = range.getClientRects()[0];
        if (word || (rect.top + rect.bottom) / 2 >= band)
          return {{word: match[0], top: rect.top}};
      }}
    }}"""
    before = page.evaluate(word_at_band, None)
    page.wait_for_timeout(600)
    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Live second")
    expect(page.locator("#live-new-4")).to_contain_text("New finding 4")
    rendered(page)
    after = page.evaluate(word_at_band, before.get("word"))
    assert after["top"] == pytest.approx(
        before["top"], abs=0.01 if where == "figure" else 4
    ), (before, after)


def test_a_revision_keeps_the_paragraph_under_a_focused_stuck_tab(browser, serve):
    """A stuck tab strip rides over every paragraph, so it names none of them.

    The reader focused a tab and scrolled the page with no other input, so focus is
    still their last word on where they are. The strip stays in view, stuck over the
    panel's paragraphs, and a revision adding paragraphs above keeps that paragraph
    where it stood rather than the strip, which stays in view by itself.
    """

    def source(added):
        paragraphs = "".join(
            f'<p id="{name}">{name}, long enough to stand as a landmark of its own.</p>'
            for name in [f"added-{n}" for n in range(added)]
            + [f"passage-{n}" for n in range(80)]
        )
        return leaf_page(
            f"Stuck tab {added}",
            "<style>html { overflow-anchor: none; }</style>"
            f'<lf-tabs id="views"><lf-tab id="first" label="First view">{paragraphs}'
            '</lf-tab><lf-tab id="second" label="Second view"><p>Other.</p></lf-tab>'
            "</lf-tabs>",
        )

    page = open_page(browser, live_url(serve(source(0))))
    resized(page, 1200, 700)
    tab = page.get_by_role("tab", name="First view")
    tab.focus()
    rendered(page)
    page.evaluate("document.scrollingElement.scrollTop = 2500")
    scroll_settled(page)
    rendered(page)
    expect(tab).to_be_focused()
    assert tab.evaluate("""async tab => {
        const {stuckBox, seenRect} = await window.__lfRuntimeImport('/runtime/geometry.js');
        return Boolean(stuckBox(tab) && seenRect(tab, new Map()));
    }"""), "the tab strip did not stick over the panel"
    landmark = page.evaluate("""() => [...document.querySelectorAll('#first p')].find(
        p => p.getBoundingClientRect().top >= 200).id""")
    reading = page.locator(f"#{landmark}")
    before = reading.evaluate("node => node.getBoundingClientRect().top")
    (serve.page_dir / "index.html").write_text(source(5))
    told(page)
    expect(page).to_have_title("Stuck tab 5")
    rendered(page)
    after = reading.evaluate("node => node.getBoundingClientRect().top")
    assert after == pytest.approx(before, abs=4), (before, after)


def test_a_revision_keeps_the_pane_read_over_a_pane_holding_offscreen_focus(
    browser, serve
):
    """Focus left in a pane the reader scrolled away from does not name their region.

    Two panes share the page scroller at a narrow width. The reader typed in the
    first, then scrolled on into the second; a revision adding paragraphs above keeps
    the paragraph they read in the second where it stood."""

    def source(added):
        notes = "".join(f"<p>Note {n}, kept with the draft.</p>" for n in range(12))
        log = "".join(
            f'<p id="{name}">{name}, long enough to stand as a landmark of its own.</p>'
            for name in [f"added-{n}" for n in range(added)]
            + [f"entry-{n}" for n in range(60)]
        )
        return leaf_page(
            f"Two panes {added}",
            "<style>html { overflow-anchor: none; }</style>"
            '<lf-pane id="notes" label="Notes"><div>'
            '<textarea aria-label="Working draft"></textarea>'
            f'{notes}</div></lf-pane><lf-pane id="log" label="Log"><div>{log}</div></lf-pane>',
            layout="workspace",
        )

    page = open_page(browser, live_url(serve(source(0))))
    resized(page, 390, 760)
    field = page.get_by_role("textbox", name="Working draft")
    field.click()
    page.keyboard.type("Words kept in the notes")
    rendered(page)
    page.locator("#entry-30").evaluate(
        "node => document.scrollingElement.scrollBy({top: node.getBoundingClientRect().top - 200, behavior: 'instant'})"
    )
    box = page.locator("#entry-30").bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 5)
    page.mouse.wheel(0, 40)
    scroll_settled(page)
    rendered(page)
    expect(field).to_be_focused()
    expect(field).not_to_be_in_viewport()
    landmark = page.evaluate("""() => [...document.querySelectorAll('#log p')].find(
        p => p.getBoundingClientRect().top >= 200).id""")
    reading = page.locator(f"#{landmark}")
    before = reading.evaluate("node => node.getBoundingClientRect().top")
    (serve.page_dir / "index.html").write_text(source(5))
    told(page)
    expect(page).to_have_title("Two panes 5")
    rendered(page)
    expect(field).to_be_focused()
    after = reading.evaluate("node => node.getBoundingClientRect().top")
    assert after == pytest.approx(before, abs=4), (landmark, before, after)


def test_a_revision_leaves_root_attributes_it_does_not_change_untouched(browser, serve):
    """Authored `html` and `body` attributes both revisions write stay where they are.

    A body class taken off and put back restyles the whole document, so a revision
    that changes only the page's words writes nothing to either root. An empty custom
    property reads back as "", and stays declared all the same."""
    empty = '<body class="live-second" data-live-body="second" style="--live-body: 2'
    page = open_page(
        browser, live_url(serve(LIVE_V2.replace(empty, f"{empty}; --live-empty: ")))
    )
    page.evaluate(
        """() => {
          window.__lfRootWrites = [];
          new MutationObserver((records) => {
            for (const r of records)
              if (!r.attributeName.startsWith("data-lf-"))
                window.__lfRootWrites.push(
                  `${r.target.localName} ${r.attributeName} ${r.oldValue}`,
                );
          }).observe(document.documentElement, { attributes: true, attributeOldValue: true });
        }"""
    )
    page.evaluate(
        """() => new MutationObserver((records) => {
          for (const r of records)
            if (["class", "style", "data-live-body"].includes(r.attributeName))
              window.__lfRootWrites.push(`body ${r.attributeName} ${r.oldValue}`);
        }).observe(document.body, { attributes: true, attributeOldValue: true })"""
    )
    (serve.page_dir / "index.html").write_text(
        LIVE_V2.replace(
            "<title>Live second</title>", "<title>Live again</title>"
        ).replace(empty, f"{empty}; --live-empty: ")
    )
    told(page)
    expect(page).to_have_title("Live again")
    assert page.evaluate("window.__lfRootWrites") == []
    assert page.evaluate("[...document.body.style].includes('--live-empty')")

    # A revision that newly declares an empty property puts it on.
    (serve.page_dir / "index.html").write_text(
        LIVE_V2.replace(
            "<title>Live second</title>", "<title>Live more</title>"
        ).replace(empty, f"{empty}; --live-empty: ; --live-added: ")
    )
    told(page)
    expect(page).to_have_title("Live more")
    assert page.evaluate("[...document.body.style].includes('--live-added')")


def test_a_stamped_live_draft_and_its_unstamped_view_keep_distinct_menu_rows(
    browser, serve
):
    """A newer held draft leaves two destinations on the prior revision."""
    version_url = serve(LIVE_V1)
    page = open_page(browser, live_url(version_url))

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    stamped = CliRunner().invoke(
        cli_model.cli,
        ["page", "stamp", str(serve.page_dir), "--text", "second"],
    )
    assert stamped.exit_code == 0, stamped.output
    told(page)

    # The hold has to outlast every press this test makes through it, and it takes both
    # of the following to get there. A composer the user opened is one of the gestures
    # a revision install defers to and does not end when focus moves; words in a box the
    # user merely has focus in do, and the draft store rather than a hold is what
    # carries those across the install (`skills/leaf/assets/AGENTS.md`, "Runtime
    # ownership").
    page.locator("#live-reading").click(click_count=3)
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Keep reading this revision.")
    (serve.page_dir / "index.html").write_text(LIVE_V3)
    told(page)
    # The fourth row is the one the third revision brings, so wait on the news that
    # revision lights rather than on the title, which already said this before the write
    # and so states no ordering at all.
    expect(page.locator(".lf-version")).to_have_attribute("data-lf-news", "")
    expect(page).to_have_title("Live second")

    # The picker stands behind More, and a mouse press anywhere outside the composer
    # stands the composer down (standDown) — so reaching the picker by mouse would end
    # the hold on the very gesture that opens the menu, and whether the page had followed
    # by then would come down to whether a state read landed between the two presses. The
    # keyboard route leaves the composer standing through both.
    page.locator(".lf-banner-more").press("Enter")
    expect(page.locator(".lf-banner-menu")).to_be_visible()
    page.locator(".lf-version").press("Enter")
    rows = page.locator(".lf-version-row")
    expect(rows).to_have_count(4)
    same_revision = page.locator('.lf-version-row[data-lf-revision="2"]')
    expect(same_revision).to_have_count(2)
    stamped_row = page.locator(
        '.lf-version-row[data-lf-revision="2"][data-lf-version="2"]'
    )
    draft_row = page.locator(
        '.lf-version-row[data-lf-revision="2"]:not([data-lf-version])'
    )
    expect(stamped_row).to_contain_text("v2")
    expect(draft_row).to_contain_text("This view · v2")
    stamped_row.evaluate("row => window.__lfStampedRow = row")
    draft_row.evaluate("row => window.__lfDraftRow = row")

    page.keyboard.press("v")
    expect(page).to_have_title("Live third")
    banner_control(page, ".lf-version").click()
    expect(rows).to_have_count(3)
    assert stamped_row.evaluate("row => row === window.__lfStampedRow")
    assert page.evaluate("() => !window.__lfDraftRow.isConnected")
    stamped_row.click()
    page.wait_for_url(re.compile(r"/versions/v2\.html\?pin=$"))


def test_a_revision_leaves_the_page_everything_it_did_not_write(browser, serve):
    """A patch applies the author's difference, not the difference from the page.

    Everything the browser, the runtime, a user, or a page module has done to a page
    since it loaded makes the page differ from any source, so a patch that reconciled
    the live tree against the arriving revision would take all of it back. Four owners,
    none of them the author, on one page: the user's open disclosure, the tokenizer's
    spans in a code block, a tab stop `focus.js` lends to land the keyboard somewhere,
    and what a page module built inside an authored container. The revision rewrites one
    paragraph and mentions none of them.

    The same revision rewrites two more paragraphs. One a page module relocated into
    its own box, which is the module's to do: the words change where it stands, the
    node is the same, and no second copy arrives where the source wrote it. Above the
    other it inserts a paragraph, the one shape the gap cannot decide: both are
    paragraphs, neither carries a name, and the words that would have paired them are
    the words that changed. The user's node survives either way, and the page is whole
    and in order whichever way the diff falls.
    """
    body = """
<h1 id="ow-title">Owners</h1>
<details id="ow-details"><summary>Evidence</summary><p>The measured run.</p></details>
<pre id="ow-code"><code class="language-python">def run(value):
    return value + 1
</code></pre>
<div id="ow-built"></div>
<p id="ow-land">A paragraph the keyboard can land on.</p>
<p id="ow-edited">The cutover has not started.</p>
<div id="mv-box"></div>
<p id="mv-moved">The move has not started.</p>
<p id="mv-kept">A paragraph that stays where it was written.</p>
<section id="tw"><p>The twins have not started.</p></section>
"""
    module = (
        '<script type="module">'
        "document.getElementById('ow-built')"
        ".append(Object.assign(document.createElement('span'),"
        " {id: 'ow-made', textContent: 'built by the page'}));"
        "document.getElementById('mv-box')"
        ".append(document.getElementById('mv-moved'));"
        "</script>"
    )
    first = leaf_page("Owners first", body, head=module)
    second = (
        first.replace("Owners first", "Owners second")
        .replace(
            "The cutover has not started.",
            "The cutover finished on the second attempt.",
        )
        .replace(
            "The move has not started.", "The move finished on the second attempt."
        )
        .replace(
            "<p>The twins have not started.</p>",
            "<p>A finding above it.</p><p>The twins finished on the second attempt.</p>",
        )
    )
    page = open_page(browser, live_url(serve(first)))
    expect(page.locator("#ow-made")).to_have_text("built by the page")
    expect(page.locator("#mv-box > #mv-moved")).to_have_count(1)
    page.evaluate(
        """() => {
          window.__mvMoved = document.getElementById('mv-moved');
          const paragraph = document.querySelector('#tw p');
          window.__twParagraph = paragraph;
          window.__twNode = paragraph.firstChild;
        }"""
    )
    page.locator("#ow-details > summary").click()
    expect(page.locator("#ow-details")).to_have_attribute("open", "")
    # The runtime lends a tab stop to land the keyboard on a paragraph. Taking that
    # attribute back is taking the focus with it.
    page.locator("#ow-land").evaluate(
        "el => { el.tabIndex = -1; el.focus({preventScroll: true}); }"
    )
    held = page.evaluate(
        """() => ({
          spans: document.querySelectorAll('#ow-code code span').length,
          made: document.getElementById('ow-made'),
        })"""
    )
    assert held["spans"] > 1, "the code block was never highlighted"
    page.evaluate(
        "() => { window.__owFirstSpan = document.querySelector('#ow-code code span'); }"
    )

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Owners second")
    expect(page.locator("#ow-edited")).to_have_text(
        "The cutover finished on the second attempt."
    )
    standing = page.evaluate(
        """() => ({
          open: document.getElementById('ow-details').hasAttribute('open'),
          spans: document.querySelectorAll('#ow-code code span').length,
          sameSpan:
            window.__owFirstSpan === document.querySelector('#ow-code code span'),
          made: Boolean(document.getElementById('ow-made')),
          landing: document.getElementById('ow-land').getAttribute('tabindex'),
          focused: document.activeElement === document.getElementById('ow-land'),
        })"""
    )
    assert standing == {
        "open": True,
        "spans": held["spans"],
        "sameSpan": True,
        "made": True,
        "landing": "-1",
        "focused": True,
    }, f"the revision took back what its author never wrote: {standing}"
    rewritten = page.evaluate(
        """() => {
          const paragraphs = [...document.querySelectorAll('#tw p')];
          return {
            moved: document.getElementById('mv-moved').textContent,
            sameNode: window.__mvMoved === document.getElementById('mv-moved'),
            inBox: document.getElementById('mv-moved').parentElement.id,
            copies: document.querySelectorAll('#mv-moved').length,
            twins: paragraphs.map((p) => p.textContent),
            twinKept: paragraphs.includes(window.__twParagraph),
            twinConnected: window.__twNode.isConnected,
          };
        }"""
    )
    assert rewritten == {
        "moved": "The move finished on the second attempt.",
        "sameNode": True,
        "inBox": "mv-box",
        "copies": 1,
        "twins": ["A finding above it.", "The twins finished on the second attempt."],
        "twinKept": True,
        "twinConnected": True,
    }, f"the revision did not reach what it rewrote in place: {rewritten}"


def test_a_revision_that_moves_the_block_the_user_types_in_keeps_them_there(
    browser, serve
):
    """A revision that reorders siblings moves the element the user is typing in.

    The patch keeps that element, so the carry leaves it alone. Native placement retains
    the browser's own state across the move: they stay in the box, caret included.
    """
    first = leaf_page(
        "Moved first",
        """
<h1 id="mv-title">Moved</h1>
<p id="mv-intro">The steps, in the order they ran.</p>
<p id="mv-late">The cutover ran second.</p>
<p id="mv-note"><label>Note <input id="mv-input" type="text"></label></p>
""",
    )
    late = '<p id="mv-late">The cutover ran second.</p>\n'
    second = (
        first.replace("Moved first", "Moved second")
        .replace(late, "")
        .replace("</label></p>\n", "</label></p>\n" + late)
    )
    assert second.index("mv-note") < second.index("mv-late")
    page = open_page(browser, live_url(serve(first)))
    box = page.locator("#mv-input")
    box.fill("needs a rollback")
    box.evaluate("input => input.setSelectionRange(6, 9, 'backward')")
    page.evaluate("() => { window.__mvInput = document.getElementById('mv-input'); }")

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Moved second")
    standing = page.evaluate(
        """() => {
          const input = document.getElementById('mv-input');
          return {
            order: [...document.querySelectorAll('main > p')].map((p) => p.id),
            same: input === window.__mvInput,
            focused: document.activeElement === input,
            caret: [input.selectionStart, input.selectionEnd, input.selectionDirection],
          };
        }"""
    )
    assert standing == {
        "order": ["mv-intro", "mv-note", "mv-late"],
        "same": True,
        "focused": True,
        "caret": [6, 9, "backward"],
    }, f"the revision's move took the user out of their box: {standing}"


def test_a_revision_reorders_a_live_sample_without_replacing_its_document(
    browser, serve
):
    """Moving a retained sample keeps its child document and focused unsent editor.

    A removal and reinsertion keeps the iframe element but reloads its document.
    Draft persistence can recover the words while still dropping the child's focus,
    so identity, words, and focus together establish that the child stayed live.
    """
    first = leaf_page(
        "Sample first",
        """
<h1 id="sample-title">Live sample revision</h1>
<p id="sample-before">This paragraph comes first.</p>
<lf-sample id="sample-held" label="Live draft" window>
  <template id="sample-source" data-sample>
    <h1>Practice draft</h1>
    <lf-draft id="sample-draft"><pre>Authored sample words.</pre></lf-draft>
  </template>
</lf-sample>
""",
    )
    paragraph = '<p id="sample-before">This paragraph comes first.</p>\n'
    second = (
        first.replace("Sample first", "Sample second")
        .replace(paragraph, "")
        .replace("</lf-sample>\n", "</lf-sample>\n" + paragraph)
    )
    page = open_page(browser, live_url(serve(first)))
    sample = page.locator("#sample-held")
    expect(sample.get_by_role("button", name="Reset", exact=True)).to_be_enabled()
    frame = sample.locator("iframe")
    frame.evaluate("frame => window.heldSampleDocument = frame.contentDocument")
    child = page.frame_locator("#sample-held iframe")
    child.locator(".lf-draft-body").click()
    editor = child.locator("#sample-draft leaf-text")
    write(editor, "Unsent sample words.")
    expect(editor).to_be_focused()

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Sample second")
    expect(page.locator("#sample-held + #sample-before")).to_be_attached()
    assert frame.evaluate(
        "frame => frame.contentDocument === window.heldSampleDocument"
    ), "the revision's retained sample move replaced its child document"
    expect(editor).to_have_js_property("value", "Unsent sample words.")
    expect(editor).to_be_focused()


def test_a_prose_revision_takes_only_the_words_it_rewrote(browser, serve):
    """The paragraph a revision rewrote is the only thing the user gives up.

    A native selection and the element a page was handed belong to nodes rather than
    markup. The selection still reads what it read over the same text node, the
    element is still the element, and the picker says the page moved. Focus follows
    the user's route through the page. An unrelated rewrite arrives automatically
    because the selected passage's complete authored scope remains unchanged.
    """
    first = leaf_page(
        "Prose first",
        """
<h1 id="pr-title">Prose</h1>
<p id="pr-kept">The account the user is halfway through, held across the revision.</p>
<p id="pr-edited">The cutover has not started.</p>
<button id="pr-control" type="button">Inspect</button>
""",
    )
    second = first.replace("Prose first", "Prose second").replace(
        "The cutover has not started.",
        "The cutover finished on the second attempt.",
    )
    page = open_page(browser, live_url(serve(first)))
    page.locator("#pr-control").focus()
    held = page.evaluate(
        """() => {
          const node = document.getElementById('pr-kept').firstChild;
          const range = document.createRange();
          range.setStart(node, 4);
          range.setEnd(node, 11);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          window.__prKept = document.getElementById('pr-kept');
          window.__prNode = node;
          return selection.toString();
        }"""
    )
    assert held == "account", f"the selection did not stand where it was put: {held!r}"

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Prose second")
    expect(page.locator("#pr-edited")).to_have_text(
        "The cutover finished on the second attempt."
    )
    standing = page.evaluate(
        """() => ({
          selection: getSelection().toString(),
          sameNode: getSelection().anchorNode === window.__prNode,
          sameElement: window.__prKept === document.getElementById('pr-kept'),
        })"""
    )
    assert standing == {
        "selection": "account",
        "sameNode": True,
        "sameElement": True,
    }, f"the revision took something the user was holding: {standing}"
    # The retained selection still names a commentable passage after the revision.
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("account")
    banner_control(page, ".lf-version").click()
    expect(page.locator(".lf-version-menu")).to_contain_text("Current · Draft after v1")


def test_a_revision_reaches_markup_wherever_its_source_holds_it(browser, serve):
    """A patch reads the source text, whitespace and all, and reaches markup wherever
    the source holds it, while what the revision never touched keeps its node. Six
    independent sections on one page, each revised or left alone by the same revision:

    - A template's tree is its content fragment, not its children. `childNodes` is
      empty on a template however much markup it holds, so a patch that read the
      element alone left every template frozen at the revision it arrived in —
      silently, because the element is there and its attributes even keep up.
    - A template written one line to a line holds a whitespace text node between every
      pair of lines and around both ends. Those nodes all read alike and outnumber the
      lines; one of them taking a line's pairing would put the rewrite in the wrong line
      or rebuild the fragment whole.
    - An unnamed widget is as much the user's as a named one. The digests each capture
      records key it by its tag and place among the others of that tag; without that
      key every revision would rebuild it, taking whatever the user had open in it.
    - A widget that arrives alone inside an exhibit is told the parent it will stand
      under, so it arrives quoted, its actions closed, rather than open to a decision
      against material the page declares as evidence.
    - An authored class written over two lines patches, since source text is the
      patch's input.
    - Delivery writes each revision's root into every media address, so the same picture
      is spelled differently in two revisions that never touched it. The page keeps the
      address it has, still served because revisions are immutable, and the picture is
      not fetched again.
    """
    first = leaf_page(
        "Patched first",
        '<h1 id="pt-title">Patched</h1>\n'
        '<template id="tm-held" data-sample>'
        '<p class="tm-line">The first account.</p></template>\n'
        '<template id="tl-held" data-sample>\n'
        '  <p class="tl-line">The first line.</p>\n'
        '  <p class="tl-line">The <lf-gloss tip="held inside">second</lf-gloss>'
        " line.</p>\n"
        '  <p class="tl-line">The third line.</p>\n'
        "</template>\n"
        '<p id="tl-after">A <lf-gloss tip="after the template">term</lf-gloss> the'
        " template does not hold.</p>\n"
        '<p id="nm-kept">A <lf-gloss tip="the cutover of the store">cutover</lf-gloss>'
        " the user is asking about.</p>\n"
        '<p id="nm-edited">The store has not moved.</p>\n'
        '<lf-sample id="qt-spec" label="an inert pick">\n'
        '  <lf-options id="qt-opts" choose>\n'
        '    <lf-option id="qt-a">Alpha</lf-option>\n'
        '    <lf-option id="qt-b">Beta</lf-option>\n'
        "  </lf-options>\n"
        "</lf-sample>\n"
        '<p id="cs-note" class="note\n    aside">The cutover has not started.</p>\n'
        '<img id="md-shot" src="/media/051bee487bfb5d13.png" alt="a shot">',
    )
    second = (
        first.replace("Patched first", "Patched second")
        .replace("The first account.", "The second account, rewritten.")
        .replace("second</lf-gloss> line.", "second</lf-gloss> line, rewritten.")
        .replace("The store has not moved.", "The store moved.")
        .replace(">Beta<", ">Beta, rewritten<")
        .replace(
            "The cutover has not started.",
            "The cutover finished on the second attempt.",
        )
    )
    page = open_page(browser, live_url(serve(first)))
    template = "() => document.getElementById('tm-held').content.textContent"
    assert page.evaluate(template) == "The first account."
    quoted = (
        "async () => { const api = await window.__lfRuntimeImport('/runtime/widget-api.js');"
        " const reading = api.widgetController(document.getElementById('qt-opts')).read();"
        " return { choose: reading.actions.choose.available,"
        " label: document.getElementById('qt-b').textContent.trim() }; }"
    )
    assert page.evaluate(quoted) == {"choose": False, "label": "Beta"}
    expect(page.locator("lf-gloss")).to_have_count(2)
    src = page.evaluate(
        """() => {
          window.__tlLines =
            [...document.getElementById('tl-held').content.querySelectorAll('p')];
          window.__tlAfter = document.querySelector('#tl-after > lf-gloss');
          window.__nmGloss = document.querySelector('#nm-kept > lf-gloss');
          window.__nmGloss.dataset.userHeld = 'open';
          const shot = document.getElementById('md-shot');
          window.__mdLoads = 0;
          shot.addEventListener('load', () => { window.__mdLoads += 1; });
          return shot.getAttribute('src');
        }"""
    )
    assert page.evaluate("() => window.__tlLines.length") == 3

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Patched second")
    expect(page.locator("#qt-b")).to_contain_text("Beta, rewritten")
    expect(page.locator("#cs-note")).to_have_text(
        "The cutover finished on the second attempt."
    )
    assert page.evaluate(template) == "The second account, rewritten.", (
        "the revision did not reach the markup inside the template"
    )
    standing = page.evaluate(
        """() => {
          const content = document.getElementById('tl-held').content;
          const lines = [...content.querySelectorAll('p')];
          return {
            words: lines.map((line) => line.textContent),
            kept: lines.map((line, at) => line === window.__tlLines[at]),
            nodes: content.childNodes.length,
            // The unnamed widget after the template is the second of its tag only
            // when the one held inside the template counts; keyed one short, its
            // digest names the wrong widget and the revision rebuilds it.
            afterKept:
              window.__tlAfter === document.querySelector('#tl-after > lf-gloss'),
            unnamedKept: window.__nmGloss === document.querySelector('#nm-kept > lf-gloss'),
            unnamedHeld: document.querySelector('#nm-kept > lf-gloss')?.dataset.userHeld,
            unnamedEdited: document.getElementById('nm-edited').textContent,
            classes: [...document.getElementById('cs-note').classList].sort(),
            src: document.getElementById('md-shot').getAttribute('src'),
            loads: window.__mdLoads,
          };
        }"""
    )
    assert standing == {
        "words": [
            "The first line.",
            "The second line, rewritten.",
            "The third line.",
        ],
        "kept": [True, True, True],
        "nodes": 7,
        "afterKept": True,
        "unnamedKept": True,
        "unnamedHeld": "open",
        "unnamedEdited": "The store moved.",
        "classes": ["aside", "note"],
        "src": src,
        "loads": 0,
    }, f"the revision missed what it rewrote or took what it left alone: {standing}"
    assert page.evaluate(quoted) == {
        "choose": False,
        "label": "Beta, rewritten",
    }, "the rewritten widget arrived unquoted"


def test_a_word_the_revision_adds_to_a_surviving_element_is_said(
    browser, serve, declared_reading_package
):
    """A newly authored label is readable and pointable on a surviving node."""
    first = leaf_page(
        "Said first",
        '<h1 id="sd-title">Said</h1>'
        '<lf-reading id="sd-reading"><p>Checks complete.</p></lf-reading>',
    )
    second = first.replace("Said first", "Said second").replace(
        'id="sd-reading"', 'id="sd-reading" label="Release checks"'
    )
    page = open_page(
        browser,
        live_url(serve(first, packages=(*EXAMPLE_PACKAGES, declared_reading_package))),
    )
    page.evaluate("window.__sample = document.getElementById('sd-reading')")

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Said second")
    expect(page.locator('#sd-reading [data-lf-said="label"]')).to_have_text(
        "Release checks"
    )
    assert page.evaluate("window.__sample === document.getElementById('sd-reading')")


def test_another_kind_of_sibling_above_an_edited_paragraph_keeps_the_user_on_it(
    browser, serve
):
    """The gap between pinned siblings is diffed, not walked in step.

    A stretch the revision edited also holds whatever it inserted, and a cursor meets an
    insertion in the way that costs the user their node: a heading above the paragraph
    they are reading is nothing the cursor can pair with, so it spends the cursor, and
    the paragraph is left with no partner and removed. Nothing is pinned here — the
    revision rewrote the only paragraph in the gap — so the whole answer comes from the
    gap's own diff.
    """
    first = leaf_page(
        "Kinds first",
        "<h1 id='kd-title'>Kinds</h1>\n<p>The cutover has not started.</p>",
    )
    second = first.replace("Kinds first", "Kinds second").replace(
        "<p>The cutover has not started.</p>",
        "<h2>Progress</h2>\n<p>The cutover finished on the second attempt.</p>",
    )
    page = open_page(browser, live_url(serve(first)))
    held = page.evaluate(
        """() => {
          const node = document.querySelector('main p').firstChild;
          const range = document.createRange();
          range.setStart(node, 4);
          range.setEnd(node, 11);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          window.__kdNode = node;
          window.__kdParagraph = node.parentElement;
          return selection.toString();
        }"""
    )
    assert held == "cutover", f"the selection did not land on the word: {held!r}"

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Kinds first")
    page.evaluate("() => { window.__kdFocus = document.activeElement; }")
    page.locator(".lf-latest-chip").evaluate("el => el.click()")
    expect(page).to_have_title("Kinds second")

    expect(page.locator("main h2")).to_have_text("Progress")
    standing = page.evaluate(
        """() => ({
          words: document.querySelector('main p').textContent,
          sameParagraph: window.__kdParagraph === document.querySelector('main p'),
          sameNode: getSelection().anchorNode === window.__kdNode,
          selection: getSelection().toString(),
        })"""
    )
    assert standing == {
        "words": "The cutover finished on the second attempt.",
        "sameParagraph": True,
        "sameNode": True,
        "selection": "cutover",
    }, f"the inserted heading took the user's paragraph with it: {standing}"


def test_a_paragraph_inserted_above_the_user_does_not_shift_the_ones_below(
    browser, serve
):
    """Unnamed siblings are matched by what they say, not by where they stand.

    Walking the two child lists in step is right until something is inserted, and then
    it is wrong in the way that costs a user most: every later paragraph pairs with
    its neighbour, so the one they are reading keeps its node while its words are
    overwritten with the next paragraph's, and the last paragraph goes for want of a
    partner. None of these paragraphs carries an id, which is the case a page of prose
    is made of.
    """
    body = "\n".join(
        f"<p>Paragraph {n}. " + "Settled words. " * 6 + "</p>" for n in range(1, 5)
    )
    first = leaf_page("Prose order first", f"<h1 id='po-title'>Order</h1>\n{body}")
    second = first.replace("Prose order first", "Prose order second").replace(
        "<p>Paragraph 1.",
        "<p>Paragraph 0. A finding the revision put above everything else.</p>\n"
        "<p>Paragraph 1.",
    )
    page = open_page(browser, live_url(serve(first)))
    held = page.evaluate(
        """() => {
          const second = [...document.querySelectorAll('main p')][1];
          const node = second.firstChild;
          const range = document.createRange();
          range.setStart(node, 0);
          range.setEnd(node, 11);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          window.__poNode = node;
          window.__poParagraph = second;
          return selection.toString();
        }"""
    )
    assert held == "Paragraph 2", f"the selection did not land on paragraph 2: {held!r}"

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Prose order first")
    page.evaluate("() => { window.__poFocus = document.activeElement; }")
    page.locator(".lf-latest-chip").evaluate("el => el.click()")
    expect(page).to_have_title("Prose order second")

    standing = page.evaluate(
        """() => {
          const paragraphs = [...document.querySelectorAll('main p')];
          return {
            words: paragraphs.map((p) => p.textContent.trim().split('.')[0]),
            selection: getSelection().toString(),
            sameNode: getSelection().anchorNode === window.__poNode,
            sameParagraph: window.__poParagraph === paragraphs[2],
          };
        }"""
    )
    assert standing == {
        "words": ["Paragraph 0", "Paragraph 1", "Paragraph 2", "Paragraph 3"]
        + ["Paragraph 4"],
        "selection": "Paragraph 2",
        "sameNode": True,
        "sameParagraph": True,
    }, f"the insertion shifted the paragraphs below it: {standing}"


def test_a_revision_replaces_the_widget_it_rewrote_and_keeps_the_one_it_did_not(
    browser, serve
):
    """A widget renders from its authored markup, so a rewritten one cannot be put right
    from outside it: it leaves, and its replacement arrives through capture and upgrade
    like any new element. The question beside it that the revision did not touch is the
    same element it always was, still holding the user's focus."""
    first = leaf_page(
        "Widgets first",
        """
<lf-ask id="wd-store-ask"><h2>Which store?</h2>
<lf-options id="wd-store" choose>
  <lf-option id="wd-keep">Keep the store</lf-option>
  <lf-option id="wd-drop">Drop the store</lf-option>
</lf-options></lf-ask>
<lf-ask id="wd-when-ask"><h2>Which schedule?</h2>
<lf-options id="wd-when" choose>
  <lf-option id="wd-now">Start now</lf-option>
  <lf-option id="wd-later">Start later</lf-option>
</lf-options></lf-ask>
""",
    )
    second = first.replace("Widgets first", "Widgets second").replace(
        '<lf-option id="wd-later">Start later</lf-option>',
        '<lf-option id="wd-later">Start later</lf-option>\n'
        '  <lf-option id="wd-never">Do not start at all</lf-option>',
    )
    page = open_page(browser, live_url(serve(first)))
    mark = page.locator("#wd-keep .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()
    page.evaluate(
        "() => { window.__wdStore = document.getElementById('wd-store');"
        " window.__wdWhen = document.getElementById('wd-when'); }"
    )

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Widgets second")
    expect(page.locator("#wd-never")).to_contain_text("Do not start at all")
    expect(page.locator("#wd-never .lf-pick")).to_have_count(1)
    assert page.evaluate("window.__wdWhen !== document.getElementById('wd-when')"), (
        "the rewritten question kept an element rendering the markup it replaced"
    )
    assert page.evaluate("window.__wdStore === document.getElementById('wd-store')"), (
        "the untouched question was replaced along with its neighbour"
    )
    expect(page.locator("#wd-keep .lf-pick")).to_be_focused()
    page.keyboard.press("1")
    expect(page.locator("#wd-keep")).to_have_attribute("chosen", "")
    page.locator("#wd-never .lf-pick").click()
    round_trip(page)
    expect(page.locator("#wd-never")).to_have_attribute("chosen", "")


def test_a_revision_inside_one_tab_keeps_the_tab_set_and_every_other_tab(
    browser, serve
):
    """A tab set's module builds its strip beside the panels and reads only their labels
    (`x-patch: members`), so a revision that rewrites a sentence in one tab edits that
    sentence: the tab set, the tab the user has open and the question in the other tab
    are the elements they were. A revision that adds a tab changes what the strip was
    built from, and the set is rebuilt with a tab for it."""

    def tabs(lede, extra=""):
        return f"""<lf-tabs id="tp-views">
  <lf-tab id="tp-plan" label="Plan"><p id="tp-lede">{lede}</p></lf-tab>
  <lf-tab id="tp-ask-tab" label="Ask">
    <lf-ask id="tp-store-ask"><h2>Which store?</h2>
    <lf-options id="tp-store" choose>
      <lf-option id="tp-keep">Keep the store</lf-option>
      <lf-option id="tp-drop">Drop the store</lf-option>
    </lf-options></lf-ask>
  </lf-tab>{extra}
</lf-tabs>"""

    first = leaf_page("Tabs first", tabs("Ship on Monday."))
    second = leaf_page("Tabs second", tabs("Ship on Tuesday."))
    third = leaf_page(
        "Tabs third",
        tabs(
            "Ship on Tuesday.",
            '\n  <lf-tab id="tp-notes" label="Notes"><p>Later.</p></lf-tab>',
        ),
    )
    page = open_page(browser, live_url(serve(first)))
    page.get_by_role("tab", name="Ask").click()
    expect(page.locator("#tp-ask-tab")).to_be_visible()
    page.evaluate(
        "() => { window.__tpTabs = document.getElementById('tp-views');"
        " window.__tpStore = document.getElementById('tp-store'); }"
    )

    stamp_page(serve.page_dir, second, "move the ship date")
    wait_for_revision(page, 2)
    expect(page.locator("#tp-lede")).to_have_text("Ship on Tuesday.")
    assert page.evaluate(
        "window.__tpTabs === document.getElementById('tp-views')"
        " && window.__tpStore === document.getElementById('tp-store')"
    ), "a sentence in one tab rebuilt the tab set"
    expect(page.locator("#tp-ask-tab")).to_be_visible()
    expect(page.get_by_role("tab")).to_have_count(2)

    stamp_page(serve.page_dir, third, "add a notes tab")
    wait_for_revision(page, 3)
    expect(page.get_by_role("tab")).to_have_count(3)
    page.get_by_role("tab", name="Notes").click()
    expect(page.locator("#tp-notes")).to_be_visible()


@pytest.mark.parametrize("departure", ["focused", "link", "selection"])
def test_a_revision_releases_the_served_markup_it_removes(browser, serve, departure):
    """Markup the page was served with leaves memory once a revision removes it. The
    served baseline's source copy routes each copied node to the live node it came
    from, so holding that copy past the revision that replaced it kept every served
    node alive for the rest of the session. A host painted before modules run is
    included, since the first-paint coordinator copies it separately. Neither the
    dropped focus, before another input, nor a fragment trip's history checkpoint
    may keep removed markup alive."""
    first = leaf_page(
        "Served",
        '<h1>Served</h1><section id="served"><h2>Served section</h2>'
        '<lf-activity id="served-feed"></lf-activity><p>Served words, and'
        ' <a id="served-link" href="#destination">a link in them</a>.</p>'
        '<p id="served-selection">A passage with a saved caret.</p></section>'
        '<div style="height:1600px"></div>'
        '<h2 id="destination">Destination</h2>'
        '<lf-ask id="question"><h2>A decision?</h2>'
        '<lf-options id="answer" choose><lf-option id="yes">Yes</lf-option>'
        "</lf-options></lf-ask>",
    )
    second = leaf_page("Revised", "<h1>Revised</h1><p>Revised words.</p>")
    page = open_page(browser, live_url(serve(first)))
    page.locator("#served-link").focus()
    page.keyboard.press("Shift")
    entries = page.evaluate("history.length")
    if departure == "link":
        page.locator("#served-link").click()
        expect(page.locator("#destination")).to_be_focused()
    elif departure == "selection":
        page.locator("#served-selection").click()
        assert (
            page.evaluate("getSelection().anchorNode.parentElement.id")
            == "served-selection"
        )
        page.keyboard.press("q")
        expect(page.locator("#question")).to_be_focused()
    if departure != "focused":
        assert page.evaluate("history.length") == entries + 1
        scroll_settled(page)
    rendered(page)
    page.evaluate(
        """() => {
          window.__held = ['served', 'served-feed', 'served-link', 'served-selection'].map(
            (id) => new WeakRef(document.getElementById(id)));
          // The control: a removed node nothing else holds, so a collection that
          // clears it has run.
          const control = document.createElement('p');
          document.body.append(control);
          control.remove();
          window.__control = new WeakRef(control);
        }"""
    )
    stamp_page(serve.page_dir, second, "remove the served section")
    wait_for_revision(page, 2)
    rendered(page)
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("HeapProfiler.collectGarbage")
    finally:
        cdp.detach()
    assert page.evaluate("() => window.__control.deref() === undefined")
    held = page.evaluate(
        "() => window.__held.map((ref) => ref.deref()?.id).filter(Boolean)"
    )
    assert held == [], f"the revision left the served {held} in memory"


@pytest.mark.parametrize("subject", ["diff", "selection"])
def test_a_live_revision_updates_the_closed_questions_door(browser, serve, subject):
    """Unrelated questions arrive while an anchored comment keeps its native editor."""
    reading = (
        '<p id="reading">Work under discussion.</p>'
        if subject != "diff"
        else '<lf-diff id="reading"><pre>'
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1 @@\n-before()\n+after()\n</pre></lf-diff>"
    )
    first = leaf_page("Questions arriving", '<h1 id="h">Decisions</h1>' + reading)
    questions = "".join(
        f'<lf-ask id="question-{i}"><h2>Decision {i}?</h2>'
        f'<lf-options id="options-{i}" choose>'
        f'<lf-option id="yes-{i}">Yes</lf-option></lf-options></lf-ask>'
        for i in range(3)
    )
    second = first.replace(reading, questions + reading)
    page = open_page(browser, live_url(serve(first, packages=("diff",))))
    door = page.locator(".lf-queue")
    expect(door).to_have_text("Questions: 0")
    target = (
        page.locator("#reading")
        if subject != "diff"
        else page.locator("#reading [data-line]").last
    )
    if subject == "selection":
        target.click(click_count=3)
    else:
        target.click(modifiers=["Alt"])
    editor = page.locator(".lf-fab-input")
    if subject != "selection":
        expect(editor).to_be_focused()
    editor.evaluate("node => { window.heldComposer = node; }")

    # An empty but open composer was sufficient to hold the original report.
    (serve.page_dir / "index.html").write_text(second)
    expect(page.locator("lf-ask")).to_have_count(3)
    expect(door).to_have_text("Questions: 3")
    expect(door).to_have_attribute("aria-label", "Questions: 3 waiting on you")
    if subject == "selection":
        assert (
            page.evaluate("getSelection().toString().trim()")
            == "Work under discussion."
        )
    else:
        expect(editor).to_be_focused()
    expect(editor).to_be_in_viewport()
    assert editor.evaluate("node => node === window.heldComposer")

    write(editor, "Keep this comment while questions change.")
    editor.evaluate("node => node.setSelectionRange(5, 9)")
    (serve.page_dir / "index.html").write_text(first)
    expect(page.locator("lf-ask")).to_have_count(0)
    expect(door).to_have_text("Questions: 0")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property(
        "value", "Keep this comment while questions change."
    )
    assert editor.evaluate("node => node === window.heldComposer")
    assert editor.evaluate("node => [node.selectionStart, node.selectionEnd]") == [5, 9]


def test_a_live_revision_holds_a_changed_comment_anchor_scope(browser, serve):
    """A retained paragraph is insufficient if the quote becomes ambiguous."""
    paragraph = "<p>Work under discussion.</p>"
    first = leaf_page(
        "Comment scope",
        '<h1 id="h">Decisions</h1><section id="subject">' + paragraph + "</section>",
    )
    second = first.replace("</section>", paragraph + "</section>").replace(
        "</main>",
        '<lf-ask id="question"><h2>Decision?</h2>'
        '<lf-options id="options" choose><lf-option id="yes">Yes</lf-option>'
        "</lf-options></lf-ask></main>",
    )
    page = open_page(browser, live_url(serve(first)))
    page.locator("#subject p").click(click_count=3)
    editor = page.locator(".lf-fab-input")
    write(editor, "This occurrence matters.")

    (serve.page_dir / "index.html").write_text(second)
    expect_banner_control_offered(page.locator(".lf-latest-chip"))
    expect(page.locator("#subject p")).to_have_count(1)
    expect(page.locator(".lf-queue")).to_have_text("Questions: 0")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "This occurrence matters.")

    editor.press("Escape")
    expect(page.locator("#subject p")).to_have_count(2)
    expect(page.locator(".lf-queue")).to_have_text("Questions: 1")


def test_a_live_revision_preserves_an_unchanged_authored_editor(browser, serve):
    """The patch's native-node proof covers ordinary content controls too."""
    first = leaf_page(
        "Editor continuity",
        '<h1 id="h">Review</h1><label for="note">Review note</label>'
        '<textarea id="note"></textarea><p id="news">Original account.</p>',
    )
    page = open_page(browser, live_url(serve(first)))
    editor = page.locator("#note")
    write(editor, "Keep my words.")
    editor.evaluate("node => { window.heldNote = node; node.setSelectionRange(2, 7); }")
    second = first.replace("Original account.", "A revised account.")
    (serve.page_dir / "index.html").write_text(second)
    expect(page.locator("#news")).to_have_text("A revised account.")
    expect(editor).to_be_focused()
    expect(editor).to_have_value("Keep my words.")
    assert editor.evaluate("node => node === window.heldNote")
    assert editor.evaluate("node => [node.selectionStart, node.selectionEnd]") == [2, 7]

    third = second.replace('id="note"', 'id="note" placeholder="New instruction"')
    (serve.page_dir / "index.html").write_text(third)
    expect_banner_control_offered(page.locator(".lf-latest-chip"))
    expect(editor).not_to_have_attribute("placeholder", "New instruction")
    expect(editor).to_have_value("Keep my words.")
    editor.press("Tab")
    expect(editor).to_have_attribute("placeholder", "New instruction")


def test_a_live_revision_reorders_the_page_and_ask_inventory_together(browser, serve):
    """Retained Ask descriptors follow the incoming document's order, and plain declared
    elements a revision removes leave the semantic document with their upgraded owner."""

    def question(identity, label):
        return f"""<lf-ask id="{identity}-ask"><h2>{label}?</h2>
  <lf-options id="{identity}-options" choose>
    <lf-option id="{identity}-yes">Yes</lf-option>
  </lf-options>
</lf-ask>"""

    first_question = question("first", "First")
    second_question = question("second", "Second")
    first = leaf_page(
        "Ask order first",
        f"<h1>Two questions</h1>{first_question}{second_question}"
        + question("gone", "Gone"),
    )
    second = leaf_page(
        "Ask order second",
        f"<h1>Two questions</h1>{second_question}{first_question}"
        "<p>The third decision is gone.</p>",
    )
    page = open_page(browser, live_url(serve(first)))
    expect_asks_answered(page, "0/3")
    banner_control(page, ".lf-queue").click()
    rows = page.locator(".lf-queue-row")
    expect(rows).to_have_count(3)

    def identities(selector, attribute):
        return page.locator(selector).evaluate_all(
            "(nodes, attribute) => nodes.map(node => node.getAttribute(attribute))",
            attribute,
        )

    assert identities("main > lf-ask", "id") == ["first-ask", "second-ask", "gone-ask"]
    assert identities(".lf-queue-row", "data-lf-at") == [
        "widget:first-options",
        "widget:second-options",
        "widget:gone-options",
    ]

    stamp_page(serve.page_dir, second, "reverse the questions, remove the third")
    wait_for_revision(page, 2)

    assert identities("main > lf-ask", "id") == ["second-ask", "first-ask"]
    assert identities(".lf-queue-row", "data-lf-at") == [
        "widget:second-options",
        "widget:first-options",
    ]
    descriptors = page.evaluate(
        """async () => {
          const {readApplication} = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          return [...readApplication().document.descriptors.keys()];
        }"""
    )
    assert not {"gone-ask", "gone-options", "gone-yes"} & set(descriptors)


def test_a_projected_attribute_opens_an_ask_captured_from_authored_markup(
    browser, serve
):
    """Predicate operands survive upgrade even when the Ask starts closed."""
    entry = {
        "description": "A test-owned conditional Ask.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
            "phase": {"enum": ["closed", "open"]},
            "restated": {"type": "boolean"},
        },
        "required": ["id", "phase"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": True,
        "x-state": {
            "phase": {
                "unit": "widget",
                "record": {"kind": "value", "attr": "phase"},
            },
            "answer": {
                "detail": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                "unit": "widget",
            },
        },
        "x-awaits": {
            "when": {"phase": ["open"]},
            "value": "answer",
            "answered": {"answer": {}},
        },
        "x-example": '<lf-conditional id="example" phase="closed">Choose.</lf-conditional>',
    }
    module = """import { keeps, once, widgetController } from "/runtime/widget-api.js";
export default class extends HTMLElement {
  #controller = widgetController(this);
  #stop;
  connectedCallback() { once(this); this.#stop ??= this.#controller.subscribe(() => {}); }
  disconnectedCallback() { this.#stop?.(); this.#stop = null; }
  renderState(state) { keeps(this, "phase", state.phase.value); }
};
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Conditional Ask",
                '<lf-conditional id="question" phase="closed">Choose.</lf-conditional>',
            ),
            layer_registry={"lf-conditional": entry},
            layer_widgets={"lf-conditional.js": module},
        ),
    )
    expect(page.locator(".lf-queue")).to_have_text("Questions: 0")

    for phase, count in (("open", 1), ("closed", 0)):
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "question",
                "action": "phase",
                "detail": {"value": phase},
            },
        )
        told(page)
        if count:
            expect_asks_answered(page, "0/1")
            banner_control(page, ".lf-queue").click()
        # The phase move is the agent's to answer. The ask leaves the user's
        # queue when its condition closes, retaining its withdrawn inventory row.
        expect(
            page.locator("[data-lf-queue='you'] .lf-queue-row[data-lf-kind='ask']")
        ).to_have_count(count)
        withdrawn = page.locator(
            "[data-lf-queue='done'] .lf-queue-row[data-lf-kind='ask']"
        )
        expect(withdrawn).to_have_count(1 - count)
        if not count:
            expect(withdrawn).to_contain_text("Withdrawn")


def test_revision_changes_keep_the_complete_heading_below_user_chrome(browser, serve):
    """A partly covered title is the page opening, not a reading place to preserve.

    A revision change used the heading as its semantic landmark and restored its exact
    viewport coordinate. When the user had moved just far enough for the first title
    line to sit behind the fixed banner, both an arriving current revision and a chosen
    historical version faithfully restored that broken view: the later line looked like
    the whole heading. The scroller already declares its landable top through
    scroll-padding, so a heading landmark must honor that edge while ordinary passage
    landmarks retain their exact coordinate.
    """
    title = "The page instance should own the complete one-off playground"
    revised_title = "The complete one-off playground belongs to the page instance"
    first = leaf_page(
        "Heading continuity",
        f"""
<header id="summary">
  <p class="eyebrow">Playground replacement audit</p>
  <h1>{title}</h1>
  <p>The opening account is long enough to become the next reading landmark.</p>
</header>
<div style="height: 1200px"></div>
""",
    )
    version_url = serve(first)
    page = open_page(browser, live_url(version_url))
    resized(page, 668, 704)

    clip_heading = """() => {
          const heading = document.querySelector('#summary h1');
          const banner = document.querySelector('.lf-banner');
          const inset = parseFloat(
            getComputedStyle(document.scrollingElement).scrollPaddingTop
          );
          document.scrollingElement.scrollBy({
            top: heading.getBoundingClientRect().top - banner.getBoundingClientRect().bottom + 12,
            behavior: 'instant',
          });
          const title = heading.getBoundingClientRect();
          const chrome = banner.getBoundingClientRect();
          const summary = document.getElementById('summary').getBoundingClientRect();
          return {title: title.toJSON(), summary: summary.toJSON(),
                  chrome: chrome.toJSON(), inset};
        }"""
    heading_position = """() => {
          const title = document.querySelector('#summary h1').getBoundingClientRect();
          const chrome = document.querySelector('.lf-banner').getBoundingClientRect();
          const inset = parseFloat(
            getComputedStyle(document.scrollingElement).scrollPaddingTop
          );
          return {
            title: title.toJSON(),
            chrome: chrome.toJSON(),
            inset,
            live: document.documentElement.hasAttribute('data-lf-live'),
          };
        }"""

    clipped = page.evaluate(clip_heading)
    assert clipped["title"]["top"] < clipped["chrome"]["bottom"]
    assert clipped["title"]["bottom"] > clipped["chrome"]["bottom"]

    # The producer owns the invariant: a saved semantic heading coordinate is never
    # inside the chrome, so in-place activation and document travel consume the same
    # valid view rather than each repairing it independently.
    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    view = page.evaluate(
        """() => {
          for (const key of Object.keys(sessionStorage))
            if (key.endsWith('lf-view')) return JSON.parse(sessionStorage[key]);
          return null;
        }"""
    )
    assert view["quote"].startswith(title), view
    # A view measures its places from the top of the scroller's visible band, which
    # scroll-padding declares: a heading's is never above it.
    assert view["quoteTop"] >= 0, view
    assert view["section"] == "summary", view
    assert view["sectionTop"] > clipped["summary"]["top"] - clipped["inset"], view

    stamp_page(
        serve.page_dir,
        first.replace(title, revised_title).replace("1200px", "1201px"),
        "Changed evidence below the page heading",
    )
    wait_for_revision(page, 2)
    live_landed = page.evaluate(heading_position)
    assert live_landed["live"], "revision activation removed the live shell"
    assert live_landed["inset"] == clipped["inset"], live_landed
    assert live_landed["title"]["top"] >= live_landed["inset"], (
        f"the arriving revision left the heading under user chrome: {live_landed}"
    )
    assert live_landed["title"]["top"] > live_landed["chrome"]["bottom"], live_landed

    clipped = page.evaluate(clip_heading)
    assert clipped["title"]["top"] < clipped["chrome"]["bottom"]
    banner_control(page, ".lf-version").click()
    page.locator('.lf-version-row[data-lf-version="1"]').click()
    page.wait_for_url(re.compile(r"/versions/v1\.html"))
    wait_until_ready(page)

    landed = page.evaluate(heading_position)
    assert landed["title"]["top"] >= landed["inset"], (
        f"version travel left the heading under user chrome: {landed}"
    )
    assert landed["title"]["top"] > landed["chrome"]["bottom"], landed


def test_revision_changes_follow_authored_text_into_declared_shadow_trees(
    browser, serve, tmp_path, monkeypatch
):
    """The semantic reading walk and resolver share the composed page reading.

    A declared shadow root is allowed to render the page's authored words. If continuity
    searches only light-DOM blocks, it records a raw page offset even though the passage
    resolver can find the rendered words, so material inserted above the widget displaces
    the user on the next revision.
    """
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    add_test_widget(package, "lf-shadow-reading", upgrade=True)
    registry_path = package / "registry.json"
    declarations = json.loads(registry_path.read_text())
    declarations["lf-shadow-reading"]["x-shadow"] = True
    registry_path.write_text(json.dumps(declarations))
    (package / "widgets" / "lf-shadow-reading.js").write_text(
        """import { once } from "/runtime/widget-api.js";
export default class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const paragraph = document.createElement("p");
    paragraph.textContent = this.textContent.trim();
    this.attachShadow({mode: "open"}).append(paragraph);
  }
};
"""
    )
    reading = "The shadow-rendered passage is the user's stable semantic landmark."
    first = leaf_page(
        "Shadow reading continuity",
        f"""
<h1 id="title">Shadow reading continuity</h1>
<div style="height: 700px"></div>
<lf-shadow-reading id="shadow-reading">{reading}</lf-shadow-reading>
<div style="height: 1000px"></div>
""",
    )
    page = open_page(
        browser,
        live_url(serve(first, packages=(*EXAMPLE_PACKAGES, "./.leaf"))),
    )
    paragraph = page.locator("lf-shadow-reading").locator("p")
    paragraph.scroll_into_view_if_needed()
    page.evaluate(
        """() => document.scrollingElement.scrollBy({
          top: document.querySelector('lf-shadow-reading').shadowRoot
            .querySelector('p').getBoundingClientRect().top - 150,
          behavior: 'instant',
        })"""
    )
    before = paragraph.evaluate("el => el.getBoundingClientRect().top")

    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    view = page.evaluate(
        """() => {
          for (const key of Object.keys(sessionStorage))
            if (key.endsWith('lf-view')) return JSON.parse(sessionStorage[key]);
          return null;
        }"""
    )
    assert view["quote"].startswith(reading), view
    assert view["section"] == "shadow-reading", view

    revised = first.replace(
        '<lf-shadow-reading id="shadow-reading">',
        '<div style="height: 320px"></div><lf-shadow-reading id="shadow-reading">',
    )
    stamp_page(serve.page_dir, revised, "add context above the shadow reading")
    wait_for_revision(page, 2)
    after = paragraph.evaluate("el => el.getBoundingClientRect().top")
    assert abs(after - before) <= 4, (before, after)


def test_revision_remembers_the_active_region_when_a_workspace_reflows(browser, serve):
    """One active semantic reading wins when several regions begin sharing the page.

    The revision puts prose before the workspace, so it stops being the page and flows,
    and every pane's reading moves onto the one page scroll."""

    def pane(side):
        return f"""
    <lf-pane id="{side}-reading" label="{side.title()} reading"><div>
      <p id="{side}-start">{side.title()} start with enough words for a landmark.</p>
      <div style="height: 320px"></div>
      <p id="{side}-landmark">The current {side} reading has a stable semantic landmark.
        {'<button id="right-subject">Right subject</button>' if side == "right" else ""}
      </p>
      <div style="height: 700px"></div>
      <p>{side.title()} end.</p>
    </div></lf-pane>"""

    workspace_markup = f"""
<header><h1>Reading workspace</h1></header>
<div id="reading-split">
  {pane("left")}
  {pane("right")}
</div>
"""
    split = regions_side_by_side("reading-split")
    first = leaf_page(
        "Active region continuity", workspace_markup, head=split, layout="workspace"
    )
    page = open_page(browser, live_url(serve(first)))
    resized(page, 900, 760)
    right_pane = page.locator("#right-reading")
    pane_posture(page, right_pane, "bounded")
    left = page.locator("#left-reading > div")
    right = page.locator("#right-reading > div")
    left.evaluate("el => el.scrollTop = 180")
    right.evaluate("el => el.scrollTop = 360")
    page.locator("#right-subject").click()
    before = page.locator("#right-landmark").evaluate(
        """el => el.getBoundingClientRect().top -
          el.closest('lf-pane > div').getBoundingClientRect().top"""
    )

    revised = leaf_page(
        "Active region continuity",
        "<p>The revision adds context before the workspace.</p>" + workspace_markup,
        head=split,
    )
    stamp_page(serve.page_dir, revised, "put the workspace in the document")
    wait_for_revision(page, 2)
    pane_posture(page, right_pane, "flow")
    # The page's band starts below the banner, where scroll-padding says; the landmark
    # keeps its distance below the top of what the user can see.
    after = page.locator("#right-landmark").evaluate(
        """el => el.getBoundingClientRect().top -
          parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)"""
    )
    assert abs(after - before) <= 4, (before, after)


def test_revision_keeps_a_focused_control_visible_without_a_text_landmark(
    browser, serve
):
    """A focused control remains the place when its pane has no quotable text."""
    content = """
<header><h1>Control workspace</h1></header>
<div id="reading-split">
  <lf-pane id="left-reading" label="Left reading"><div>
    <p>Another pane's reading does not name the active control.</p>
  </div></lf-pane>
  <lf-pane id="right-reading" label="Right reading"><div>
    <div style="height: 1100px"></div>
    <button id="right-subject">Right subject</button>
    <div style="height: 500px"></div>
  </div></lf-pane>
</div>
"""
    split = regions_side_by_side("reading-split")
    first = leaf_page(
        "Focused control continuity", content, head=split, layout="workspace"
    )
    page = open_page(browser, live_url(serve(first)))
    resized(page, 900, 760)
    pane_posture(page, page.locator("#right-reading"), "bounded")
    page.locator("#right-subject").click()

    revised = leaf_page(
        "Focused control continuity",
        '<div style="height: 1000px"></div>' + content,
        head=split,
    )
    stamp_page(serve.page_dir, revised, "put the workspace in the document")
    wait_for_revision(page, 2)
    pane_posture(page, page.locator("#right-reading"), "flow")
    visible = page.locator("#right-subject").evaluate(
        """el => {
          const rect = el.getBoundingClientRect();
          return rect.top >= 0 && rect.bottom <= innerHeight;
        }"""
    )
    assert visible


def test_revision_reveals_a_page_landmark_around_an_empty_active_region(browser, serve):
    """An empty flow region does not displace the page reading that contains it."""
    content = """
<h1 id="reading-title">The page landmark surrounding these controls remains stable.</h1>
<lf-pane id="controls-pane" label="Controls">
  <button id="standing-control">Change setting</button>
</lf-pane>
<div style="height: 1000px"></div>
    """
    first = leaf_page("Empty active region continuity", content)
    page = open_page(browser, live_url(serve(first)))
    page.locator("#standing-control").focus()
    before = page.locator("#reading-title").evaluate(
        "heading => heading.getBoundingClientRect().top"
    )

    revised = leaf_page(
        "Empty active region continuity",
        f"""
<p>The arriving revision adds a result above the prior content.</p>
<details id="prior-controls">
  <summary>Prior controls</summary>
  {content}
</details>
""",
    )
    stamp_page(serve.page_dir, revised, "wrap the prior controls")
    wait_for_revision(page, 2)

    expect(page.locator("#prior-controls")).to_have_attribute("open", "")
    # The revision wrapped the control, so the element the user was on is gone and
    # focus went to the page with it. What the region still owes them is the way back
    # to it: revealed rather than shut inside a disclosure they never closed.
    expect(page.locator("#standing-control")).to_be_visible()
    after = page.locator("#reading-title").evaluate(
        "heading => heading.getBoundingClientRect().top"
    )
    assert abs(after - before) <= 4, (before, after)


def test_revision_reveals_an_active_region_without_any_reading_landmark(browser, serve):
    """A surviving active region remains reachable even when no passage names it."""
    content = """
<lf-pane id="controls-pane" label="Controls">
  <button id="standing-control">Change setting</button>
</lf-pane>
<div style="height: 1000px"></div>
    """
    first = leaf_page("Textless active region continuity", content)
    page = open_page(browser, live_url(serve(first)))
    page.locator("#standing-control").focus()

    revised = leaf_page(
        "Textless active region continuity",
        f"""
<details id="prior-controls">
  <summary>Prior controls</summary>
  {content}
</details>
""",
    )
    stamp_page(serve.page_dir, revised, "wrap the textless active region")
    wait_for_revision(page, 2)

    expect(page.locator("#prior-controls")).to_have_attribute("open", "")
    # Reachable, not focused: the revision wrapped the control, so the element the
    # user stood on is gone and the region owes them the way back to its replacement.
    expect(page.locator("#standing-control")).to_be_visible()


def test_ask_repaints_keep_the_queues_reading_until_an_explicit_arrival(browser, serve):
    """Ask repaint keeps the list's reading; explicit arrival reveals its row."""
    questions = "".join(
        f'<lf-ask id="ask-{index}"><h2>Question {index} about this project</h2>'
        f'<lf-options id="options-{index}" choose>'
        f'<lf-option id="yes-{index}">Proceed with this choice</lf-option>'
        f'<lf-option id="no-{index}">Leave this choice for now</lf-option>'
        "</lf-options></lf-ask>"
        for index in range(30)
    )
    page = open_page(
        browser, serve(leaf_page("Reading the Question inventory", questions))
    )
    resized(page, 1200, 900)
    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    page.locator('.lf-queue-row[data-lf-at="widget:options-0"]').click()
    expect(page.locator("#ask-0")).to_be_focused()
    list_selector = ".lf-queue-panel .lf-drawer-list"
    drawer = page.locator(list_selector)
    drawer.evaluate(
        """list => list.addEventListener('scroll', () => {
          if (list.scrollTop > 100) window.readLaterAsks = true;
        })"""
    )
    box = drawer.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 700)
    page.wait_for_function("() => window.readLaterAsks")
    scroll_settled(page, list_selector)
    reading = drawer.evaluate("list => list.scrollTop")
    assert reading > 100, "painting the standing row must not undo scrolling the list"

    resized(page, 1180, 900)
    scroll_settled(page, list_selector)
    assert drawer.evaluate("list => list.scrollTop") == reading
    expect(page.locator("#ask-0")).to_be_focused()

    page.keyboard.press("q")
    expect(page.locator("#ask-1")).to_be_focused()
    scroll_settled(page, list_selector)
    assert drawer.evaluate("list => list.scrollTop") < reading
    row = page.locator('.lf-queue-row[data-lf-at="widget:options-1"]')
    assert row.locator(".lf-queue-title").evaluate(
        "words => words.getBoundingClientRect().top >= "
        "words.closest('.lf-drawer-list').getBoundingClientRect().top"
    ), "explicit ask navigation still reveals its matching row"


@pytest.mark.parametrize("newer_reading", [False, True])
def test_a_panes_posture_change_keeps_the_reading_after_scrolling_past_focus(
    browser, serve, newer_reading
):
    """An automatic scroll-container change preserves reading rather than stale focus."""
    paragraphs = "".join(
        f'<p id="line-{index}">Reading paragraph {index}. '
        + "Words holding the current reading. " * 10
        + "</p>"
        for index in range(30)
    )
    source = leaf_page(
        "Reading beyond the focused control",
        '<lf-pane id="reading" label="Reading"><div id="reading-body">'
        '<button id="control">Earlier focused control</button>'
        f"{paragraphs}</div></lf-pane>",
        head="""<style>
#reading-body { height: 400px; overflow: auto; }
@media (width < 720px) { #reading-body { height: auto; overflow: visible; } }
</style>""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1200, 900)
    body = page.locator("#reading-body")
    control = page.locator("#control")
    control.focus()
    body.evaluate("body => body.scrollTop = 900")
    scroll_settled(page, "#reading-body")
    assert control.evaluate("control => control.getBoundingClientRect().bottom") < 0
    landmark_id = body.evaluate(
        """body => [...body.querySelectorAll('p')].find(paragraph =>
          paragraph.getBoundingClientRect().top >= body.getBoundingClientRect().top).id"""
    )
    if newer_reading:
        # Interleave at the announced handover, before its deferred restoration. The
        # platform input supersedes that restoration just as a trackpad gesture does.
        page.evaluate("""async () => {
          const regions = await window.__lfRuntimeImport('/runtime/reading-regions.js');
          const stop = regions.watchReadingRegionTransitions(({phase, shifted}) => {
            if (phase !== 'shift' || !shifted.some(({region}) => region.id === 'reading'))
              return;
            stop();
            document.body.dispatchEvent(new WheelEvent('wheel', {deltaY: 500, bubbles: true}));
            scrollTo({top: 1900, behavior: 'instant'});
            window.laterReading = scrollY;
          });
        }""")

    resized(page, 520, 900)
    pane_posture(page, page.locator("#reading"), "flow")
    scroll_settled(page)

    expect(control).to_be_focused()
    if newer_reading:
        assert page.evaluate("() => window.laterReading") > 1000
        assert page.evaluate("() => scrollY === window.laterReading"), (
            "a queued posture restore must yield to the user's later reading"
        )
        return
    landmark = page.locator(f"#{landmark_id}")
    assert landmark.evaluate(
        "paragraph => paragraph.getBoundingClientRect().top < innerHeight"
    ), "changing posture must keep the passage being read on screen"
    assert control.evaluate("control => control.getBoundingClientRect().bottom") < 0


def test_revision_does_not_move_a_page_offset_into_a_new_bounded_region(browser, serve):
    """A raw offset belongs to the scrollport that supplied it.

    The workspace flows under prose in the first version and is the page in the second,
    so the scroll the user left on the page has no place in the pane that now scrolls.
    """

    def pane(name, *, standing=False):
        control = (
            '<button id="standing-control">Change setting</button>' if standing else ""
        )
        return f"""
<lf-pane id="{name}-pane" label="{name.title()}">
  <div>{control}<div style="height: 1100px"></div></div>
</lf-pane>
"""

    workspace_markup = f"""
<div id="all-panes">
  {pane("active", standing=True)}
  {pane("second")}
</div>
"""
    split = regions_side_by_side("all-panes")
    first = leaf_page(
        "Changing offset ownership",
        "<p>Context before the workspace.</p>" + workspace_markup,
        head=split,
    )
    page = open_page(browser, live_url(serve(first)))
    resized(page, 900, 760)
    active = page.locator("#active-pane")
    pane_posture(page, active, "flow")
    page.locator("#standing-control").evaluate(
        "control => control.focus({preventScroll: true})"
    )
    page.evaluate("document.scrollingElement.scrollTop = 300")
    before = page.evaluate("document.scrollingElement.scrollTop")
    assert before == 300

    revised = leaf_page(
        "Changing offset ownership", workspace_markup, head=split, layout="workspace"
    )
    stamp_page(serve.page_dir, revised, "make the workspace the page")
    wait_for_revision(page, 2)

    pane_posture(page, active, "bounded")
    assert page.locator("#active-pane > div").evaluate("pane => pane.scrollTop") == 0


def test_revision_does_not_move_an_offset_between_bounded_region_owners(browser, serve):
    """A nested flow region cannot carry one parent's offset into another parent."""
    entry = {
        "description": "A test-owned reading scroller.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": True,
        "x-example": (
            '<lf-owned-scroll id="example">'
            "<div data-scroll-body><button>Control</button></div>"
            "</lf-owned-scroll>"
        ),
    }
    module = """
import {registerReadingRegion} from '/runtime/widget-api.js';
export default class extends HTMLElement {
  #stop = null;
  connectedCallback() {
    const body = this.querySelector(':scope > [data-scroll-body]');
    this.#stop = registerReadingRegion({id: this.id, host: this, body});
  }
  disconnectedCallback() {
    this.#stop?.();
    this.#stop = null;
  }
};
"""
    active = """
<div style="height: 250px"></div>
<lf-owned-scroll id="active-region">
  <div data-scroll-body>
    <section id="removed-landmark">
      <p>The nested region landmark disappears in the arriving revision.</p>
    </section>
    <button id="standing-control">Change setting</button>
  </div>
</lf-owned-scroll>
"""
    active_without_landmark = active.replace(
        """    <section id="removed-landmark">
      <p>The nested region landmark disappears in the arriving revision.</p>
    </section>
""",
        "",
    )

    def parent(name, content=""):
        return f"""
<lf-owned-scroll id="{name}-region">
  <div data-scroll-body style="height: 240px; overflow: auto">
    {content}<div style="height: 700px"></div>
  </div>
</lf-owned-scroll>
"""

    first = leaf_page(
        "Nested offset ownership",
        parent("left", active) + parent("right"),
    )
    page = open_page(
        browser,
        live_url(
            serve(
                first,
                layer_registry={"lf-owned-scroll": entry},
                layer_widgets={"lf-owned-scroll.js": module},
            )
        ),
    )
    left = page.locator("#left-region > [data-scroll-body]")
    right = page.locator("#right-region > [data-scroll-body]")
    left.evaluate("scroller => scroller.scrollTop = 150")
    page.locator("#standing-control").evaluate(
        "control => control.focus({preventScroll: true})"
    )
    assert left.evaluate("scroller => scroller.scrollTop") == 150
    assert right.evaluate("scroller => scroller.scrollTop") == 0

    revised = leaf_page(
        "Nested offset ownership",
        parent("left") + parent("right", active_without_landmark),
    )
    stamp_page(serve.page_dir, revised, "move the active region")
    wait_for_revision(page, 2)

    assert right.evaluate("scroller => scroller.scrollTop") == 0
    # The region moved parents, so its control is a new element under the other one.
    expect(page.locator("#right-region #standing-control")).to_be_visible()


def test_a_live_revision_with_new_authored_code_reloads_the_document(browser, serve):
    """A new constructor and its listeners run once, with fresh local state. The
    browser here has no view transition API, since fresh-document activation does not
    depend on same-document animation; the other fresh-document journeys keep it."""
    module = """<script type="module">
customElements.define('page-counter', class extends HTMLElement {
  connectedCallback() {
    let count = 0;
    const button = document.createElement('button');
    const label = () => { button.textContent = `Count ${count}`; };
    button.addEventListener('click', () => { count += 1; label(); });
    label();
    this.append(button);
  }
});
document.querySelector('#counter').append(document.createElement('page-counter'));
</script>"""
    first = LIVE_V1.replace("</head>", module + "</head>").replace(
        "</main>", '<div id="counter"></div></main>'
    )
    second = LIVE_V2.replace(
        "</head>", module.replace("count += 1", "count += 10") + "</head>"
    ).replace("</main>", '<div id="counter"></div></main>')
    page = open_page(browser, live_url(serve(first)))
    page.get_by_role("button", name="Count 0", exact=True).click()
    expect(page.get_by_role("button", name="Count 1", exact=True)).to_be_visible()
    original_document = page.evaluate("performance.timeOrigin")
    page.evaluate("document.startViewTransition = undefined")

    (serve.page_dir / "index.html").write_text(second)
    told(page)

    expect(page).to_have_title("Live second")
    page.get_by_role("button", name="Count 0", exact=True).click()
    expect(page.get_by_role("button", name="Count 10", exact=True)).to_be_visible()
    assert page.evaluate("performance.timeOrigin") != original_document
    assert "/versions/" not in page.url
    assert "_leaf-revision" not in page.url


def test_a_stamped_url_stays_pinned_while_the_live_root_follows_a_draft(browser, serve):
    version_url = serve(LIVE_V1)
    pinned = open_page(browser, version_url)
    live = open_page(browser, live_url(version_url))

    (serve.page_dir / "index.html").write_text(LIVE_V2.replace("</main>", ""))
    told(live)
    told(pinned)
    expect(live.locator(".lf-latest-chip")).to_contain_text(
        "Latest edit couldn't be shown"
    )
    expect(pinned.locator(".lf-latest-chip")).not_to_contain_text(
        "Latest edit couldn't be shown"
    )
    expect(live).to_have_title("Live first")

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(live)
    told(pinned)

    expect(live).to_have_title("Live second")
    expect(live.locator(".lf-version")).to_have_text("Showing Draft")
    expect(live.locator(".lf-version")).to_have_attribute(
        "title", re.compile(r"^Draft after v1:")
    )
    expect(pinned).to_have_title("Live first")
    expect(pinned).to_have_url(re.compile(r"/versions/v1\.html"))
    expect(pinned.locator(".lf-version")).to_contain_text("v1")


def test_the_live_page_retains_a_page_comment_while_adopting_revisions(browser, serve):
    """A page comment editor belongs to runtime chrome, so an authored patch can
    arrive while it holds unsent words. The draft and focus survive each revision."""
    version_url = serve(LIVE_V1)
    page = open_page(browser, live_url(version_url))
    general = page_comment(page)
    write(general, "Do not replace the page under these words.")

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    expect(page).to_have_title("Live second")
    expect(general).to_be_focused()
    expect(general).to_have_js_property(
        "value", "Do not replace the page under these words."
    )

    # Leaving the text box preserves its durable draft on the live address.
    page.keyboard.press("Escape")
    expect(general).not_to_be_focused()
    assert "/versions/" not in page.url
    expect(general).to_have_js_property(
        "value", "Do not replace the page under these words."
    )
    approval = page.locator(".lf-signoff")
    expect(approval).to_have_count(1)
    page.evaluate(
        "control => { window.__lfApprovalControl = control; }",
        approval.element_handle(),
    )

    # Continue editing after the first release, then adopt v3 while the field stands.
    page_comment(page)
    (serve.page_dir / "index.html").write_text(LIVE_V3)
    told(page)
    expect(page).to_have_title("Live third")
    expect(general).to_be_focused()
    expect(general).to_have_js_property(
        "value", "Do not replace the page under these words."
    )

    write(general, "")
    page.locator("#live-reading").click()
    told(page)
    expect(page).to_have_title("Live third")
    assert "/versions/" not in page.url
    expect(approval).to_be_hidden()
    assert approval.evaluate("control => control === window.__lfApprovalControl")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blive-second\b"))
    assert page.locator("body").get_attribute("data-live-body") is None
    assert (
        page.locator("body").evaluate(
            "el => el.style.getPropertyValue('--live-body').trim()"
        )
        == ""
    ), "the retired version's authored inline property survived"
    assert page.locator("html").evaluate(
        "el => el.style.getPropertyValue('--lf-thread-panel-width').trim()"
    ), "activation erased a runtime-owned root property"
    assert page.locator('meta[name="description"]').get_attribute("content") == "third"


def test_the_presses_a_user_is_mid_way_through_survive_the_page_following(
    browser, serve
):
    """A revision arriving under a user mid-press keeps their next press live.

    Two kinds of pending input meet an activation. A sequence is the runtime's: bare `g`
    names the visible targets, and the chips are read off whichever document is standing,
    so the window holds through the revision and the hints land on the new page — minus
    the hint for a link the revision took away, which is the honest reading. The user's
    standing is the document's: the Ask's actions remain live over a focused pick mark,
    and a revision that leaves that widget's markup alone leaves the mark itself alone,
    so the digit still picks and the bottom status acknowledges it. One revision arrives
    as a draft and the next as a stamped version, since both bring the page to the user
    by the same door."""
    version_url = serve(LIVE_KEYS_V1)
    page = open_page(browser, live_url(version_url))
    chips = page.locator(".lf-go-to-hint")
    link_chips = page.locator('.lf-go-to-hint[data-lf-go-to-kind="Link"]')

    page.keyboard.press("g")
    expect(link_chips).to_have_count(3)
    (serve.page_dir / "index.html").write_text(LIVE_KEYS_V2)
    told(page)
    expect(page).to_have_title("Live keys second")
    expect(link_chips).to_have_count(2)
    assert "visible target" in shortcut_bar_text(page), (
        "the sequence did not follow the new document"
    )
    page.keyboard.type(address_code(page, "Link", "lk-link-three"))
    expect(page.locator("#lk-para")).to_be_focused()
    expect(chips).to_have_count(0)

    mark = page.locator("#lk-one .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()
    assert active_digit_bindings(page) == "1–3"
    # A stamped version this time, which is the other way a page moves under a user.
    # Its announcement arrives immediately; the bottom status may queue it behind the
    # earlier draft notice, so that line need not change before the next press.
    stamp_page(serve.page_dir, LIVE_KEYS_V3, "third")
    told(page)
    expect(page).to_have_title("Live keys third")
    expect(page.locator(".lf-live")).to_have_text("Updated to v2")
    assert page.locator(".lf-toast").count() == 0
    # The same mark, still holding the focus the user put on it: the revision rewrote
    # nothing in this widget, so nothing replaced it.
    expect(page.locator("#lk-one .lf-pick")).to_be_focused()
    assert active_digit_bindings(page) == "1–3", (
        "the revision took the user's keys down"
    )
    page.keyboard.press("2")
    expect(page.locator("#lk-two")).to_have_attribute("chosen", "")
    expect(page.locator(".lf-bottom-status .lf-notice")).to_have_text(
        "Chose “Two” — sent"
    )
    round_trip(page)


def test_a_revision_that_restates_an_ask_leaves_the_user_standing_in_it(browser, serve):
    """The Ask a user is working survives the revision that rewrites it.

    A patch keeps every node the revision did not rewrite, so an untouched control is
    still holding the focus the user put on it. The question they are answering is the
    one thing a revision is most likely to rewrite, and rewriting it replaced every node
    inside — which used to drop the user onto `body` in the same breath as "Updated
    to …". An Ask is named by a declared id rather than by a control's shape, so the
    standing is a lookup: the user is put back on the Ask, or on the control that
    answers it, according to which of the two they held. A revision that withdraws the
    Ask has nowhere to put them back, which the tests below cover along with the user
    who was holding one of its controls.
    """
    version_url = serve(LIVE_KEYS_V1)
    page = open_page(browser, live_url(version_url))
    decision = page.locator("#lk-decision")

    page.keyboard.press("q")
    expect(decision).to_be_focused()
    (serve.page_dir / "index.html").write_text(LIVE_KEYS_ASK_REWRITTEN)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    expect(page.locator(".lf-bottom-status .lf-notice")).to_have_text(
        "Updated to Draft after v1"
    )
    expect(decision).to_be_focused()
    # Standing, not a bare tab stop: the Ask's own action routes are live over the user
    # again, and the third option the revision brought is among them.
    assert active_digit_bindings(page) == "1–4"
    page.keyboard.press("3")
    expect(page.locator("#lk-three")).to_have_attribute("chosen", "")


def test_a_restated_ask_returns_a_user_to_the_question_not_to_a_control(browser, serve):
    """A user inside the Ask comes back to its opening, never to a guessed control.

    Which control they were holding is not a thing the Ask can answer: the controls are
    the widget's, most carry no id, and the first one that answers the Ask is the walk's
    landing rule rather than a restore. Handing that back is the failure version.js names
    — a user holding the second option would be given the first, and their next press
    would choose it. The Ask's opening holds a lent tab stop rather than a decision, so
    the digits still reach the option they meant and Space decides nothing. Where the
    revision withdraws the question there is nothing to come back to, and `body` is the
    honest answer.
    """
    version_url = serve(LIVE_KEYS_V1)
    page = open_page(browser, live_url(version_url))
    mark = page.locator("#lk-two .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()

    (serve.page_dir / "index.html").write_text(LIVE_KEYS_ASK_REWRITTEN)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    expect(page.locator("#lk-decision")).to_be_focused()
    # The press they had lined up decides nothing on its own, and the option they were
    # holding is still the one their own digit reaches.
    page.keyboard.press("Space")
    expect(page.locator("lf-option[chosen]")).to_have_count(0)
    page.keyboard.press("2")
    expect(page.locator("#lk-two")).to_have_attribute("chosen", "")


def test_a_revision_gives_back_the_apparatus_the_user_was_working_with(browser, serve):
    """What the author named survives the widget the revision replaced whole.

    A patch keeps the nodes a revision did not rewrite, and a widget is never one of
    them: a controller owns its children, so restating the question replaces the field
    the user was writing in, the box they had opened and the box they had scrolled.
    None of that is in the log, so no projection puts it back. The authored id is what
    makes it recoverable — the same identity the patch matches nodes on — so the carry
    is a lookup, and an element the author left unnamed still keeps nothing.
    """
    version_url = serve(LIVE_KEYS_APPARATUS)
    page = open_page(browser, live_url(version_url))
    note = page.locator("#lk-note")
    note.click()
    note.type("half a thought")
    page.locator("#lk-why").evaluate("el => { el.open = true; }")
    page.locator("#lk-evidence").evaluate("el => { el.scrollTop = 40; }")
    # Put the caret back inside the words rather than at their end, so a restore that
    # merely refills the field is not mistaken for one that puts the user back in it.
    note.evaluate("el => el.setSelectionRange(4, 4)")
    expect(note).to_be_focused()

    (serve.page_dir / "index.html").write_text(LIVE_KEYS_APPARATUS_REWRITTEN)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    # The widget did go whole: the heading is the revision's.
    expect(page.locator("#lk-decision h2")).to_have_text(
        "Which one, now the costs are in?"
    )
    expect(page.locator("#lk-note")).to_have_value("half a thought")
    expect(page.locator("#lk-note")).to_be_focused()
    assert page.locator("#lk-note").evaluate("el => el.selectionStart") == 4
    assert page.locator("#lk-why").evaluate("el => el.open") is True
    assert page.locator("#lk-evidence").evaluate("el => el.scrollTop") == 40
    # Standing in the Ask is where the user already is, so the Ask restore has nothing
    # to do and does not pull them out of the field onto the question.
    assert page.locator("#lk-note").evaluate("el => el === document.activeElement")


def test_a_revision_gives_values_to_controls_the_user_never_touched(browser, serve):
    """An untouched control is the author's to set, whatever kind of control it is.

    A tick the author gave no value of its own answers `"on"`, and a range answers its
    midpoint, both against a `defaultValue` the author left empty. Ask the platform's
    default and every such control reads as user state on the way out, and arrives
    written over whatever the next revision authored. The authored node answers the same
    way the live one does, so asking it instead finds nothing to carry.

    The other side of that: a control the user did move is theirs, whatever its kind.
    The authored range still reads its midpoint, so a range the user dragged disagrees
    with it and crosses into the widget the revision replaced. A rule keyed on the kind
    of control instead — words carry, the rest do not — keeps the untouched tick and
    range from crossing only by leaving every range behind, the user's drag included.

    A disclosure has no `defaultOpen` to answer with, so the state the carry reads off
    the live box is the author's own until the user moves it: reading the box alone
    would carry the outgoing revision's shut over an arriving revision that opens it.
    The baseline is the authored markup of the revision the user stands in, so an
    untouched box is left to the arriving revision.
    """
    moved = (
        ' <label for="lk-moved">How far</label>'
        ' <input id="lk-moved" name="lk-moved" type="range"></p>'
    )
    unvalued = (
        '<p><label for="lk-tick">Also</label>'
        ' <input id="lk-tick" name="lk-tick" type="checkbox">'
        ' <label for="lk-dial">How much</label>'
        ' <input id="lk-dial" name="lk-dial" type="range"></p>'
    )
    valued = unvalued.replace('type="checkbox"', 'type="checkbox" value="yes"').replace(
        'type="range"', 'type="range" value="80"'
    )
    unvalued = unvalued.replace("</p>", moved)
    valued = valued.replace("</p>", moved)
    first = LIVE_KEYS_APPARATUS.replace(
        '<details id="lk-why">', unvalued + '<details id="lk-why">'
    )
    second = LIVE_KEYS_APPARATUS_REWRITTEN.replace(
        '<details id="lk-why">', valued + '<details id="lk-why" open>'
    )

    version_url = serve(first)
    page = open_page(browser, live_url(version_url))
    # The platform's own answers, standing against the empty default the author wrote.
    assert page.locator("#lk-tick").evaluate("el => [el.value, el.defaultValue]") == [
        "on",
        "",
    ]
    assert page.locator("#lk-dial").evaluate("el => [el.value, el.defaultValue]") == [
        "50",
        "",
    ]
    # The user works the field and one range, and leaves the other two alone.
    note = page.locator("#lk-note")
    note.click()
    note.type("half a thought")
    page.locator("#lk-moved").fill("17")
    assert page.locator("#lk-moved").evaluate("el => el.value") == "17"
    assert page.locator("#lk-why").evaluate("el => el.open") is False

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    # The widget did go whole, so the carry is what decides these controls.
    expect(page.locator("#lk-decision h2")).to_have_text(
        "Which one, now the costs are in?"
    )
    assert page.locator("#lk-tick").evaluate("el => el.value") == "yes"
    assert page.locator("#lk-dial").evaluate("el => el.value") == "80"
    # While the field whose value is the user's own words still crosses, and the range
    # the user moved.
    expect(page.locator("#lk-note")).to_have_value("half a thought")
    assert page.locator("#lk-moved").evaluate("el => el.value") == "17"
    assert page.locator("#lk-why").evaluate("el => el.open") is True


def test_a_revision_that_rewrites_a_draft_leaves_the_user_where_they_stand(
    browser, serve
):
    """A draft's open editor comes back with it, and does not take the user with it.

    The draft reads an open editor's words back from its own store whenever it
    connects — which a revision rewriting the draft makes it do. Getting the words back
    is right. The editor taking the focus is not, when the user had left the editor
    open and gone to stand on something else: the revision is news, and news with no
    gesture behind it moves nobody.
    """
    draft = '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft>'
    first = LIVE_KEYS_V1.replace('<p id="lk-para">', draft + '\n<p id="lk-para">')
    second = first.replace(
        "<title>Live keys first</title>", "<title>Live keys rewritten</title>"
    ).replace("<pre>Ship it.</pre>", "<pre>Ship it on Friday.</pre>")

    page = open_page(browser, live_url(serve(first)))
    draft_control(page, "edit", "plan").click()
    editor = page.locator("lf-draft leaf-text")
    expect(editor).to_be_focused()
    write(editor, "Ship it, but louder.")
    # The user leaves the editor open and goes to stand on the question instead.
    pick = page.locator("#lk-one .lf-pick")
    pick.focus()
    expect(pick).to_be_focused()

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    # The rewritten draft has connected and read its edit back: the words are kept.
    expect(editor).to_have_js_property("value", "Ship it, but louder.")
    expect(pick).to_be_focused()


def test_the_replacing_install_gives_back_the_same_apparatus(browser, serve):
    """A revision that opens a fresh document carries the same named state across.

    Nothing of the old document survives here, so every record in the handoff names
    something the user would otherwise have lost — there is no held node to skip. The
    user was told the same "Updated to …" either way and cannot tell the two installs
    apart, so neither may answer differently.
    """
    module = """<script type="module">
customElements.define('page-counter', class extends HTMLElement {
  connectedCallback() { this.textContent = 'count 0'; }
});
</script>"""
    first = LIVE_KEYS_APPARATUS.replace("</head>", module + "</head>")
    second = LIVE_KEYS_APPARATUS_REWRITTEN.replace(
        "</head>", module.replace("count 0", "count 10") + "</head>"
    )
    page = open_page(browser, live_url(serve(first)))
    note = page.locator("#lk-note")
    note.click()
    note.type("half a thought")
    page.locator("#lk-why").evaluate("el => { el.open = true; }")
    page.locator("#lk-evidence").evaluate("el => { el.scrollTop = 40; }")
    original_document = page.evaluate("performance.timeOrigin")

    (serve.page_dir / "index.html").write_text(second)
    told(page)

    expect(page).to_have_title("Live keys rewritten")
    assert page.evaluate("performance.timeOrigin") != original_document, (
        "the revision was patched in, so this proves nothing about the other install"
    )
    expect(page.locator("#lk-note")).to_have_value("half a thought")
    expect(page.locator("#lk-note")).to_be_focused()
    assert page.locator("#lk-why").evaluate("el => el.open") is True
    assert page.locator("#lk-evidence").evaluate("el => el.scrollTop") == 40


@pytest.mark.parametrize("start", ["generated", "authored"])
def test_replacing_document_yields_to_input_before_runtime_loads(browser, serve, start):
    """The fresh page belongs to its reader before its module graph arrives: the
    field the reader clicks keeps its focus and the words typed into it."""
    html = leaf_page(
        "Arrival",
        '<h1>Arrival</h1><lf-activity id="feed"></lf-activity>'
        '<section id="notes"><h2>Notes</h2>'
        '<input id="first" type="text" aria-label="First">'
        '<input id="second" type="text" aria-label="Second"></section>',
    )
    page = open_page(browser, live_url(serve(html)))
    panel = page.locator(".lf-threads-toggle")
    panel.click()
    expect(panel).to_have_attribute("aria-expanded", "true")
    first = page.locator(
        "#feed .lf-activity-news" if start == "generated" else "#first"
    )
    first.focus()
    expect(first).to_be_focused()
    original_document = page.evaluate("performance.timeOrigin")
    blocked = []
    page.route("**/leaf.js", lambda route: blocked.append(route))
    stamp_page(
        serve.page_dir,
        html.replace("</head>", '<script type="module">void 0;</script></head>'),
        "Replace executable inputs",
    )
    page.wait_for_function(
        "old => performance.timeOrigin !== old", arg=original_document
    )
    page.wait_for_function("document.readyState !== 'loading'")
    assert blocked, "the runtime module must still be withheld"
    second = page.locator("#second")
    second.click()
    page.keyboard.type("Keep this input")
    expect(second).to_be_focused()
    page.unroute("**/leaf.js")
    for route in blocked:
        route.continue_()
    wait_for_revision(page, 2)
    wait_until_ready(page)
    expect(panel).to_have_attribute("aria-expanded", "true")
    expect(second).to_be_focused()
    expect(second).to_have_value("Keep this input")


def test_replacing_document_keeps_typing_while_presentation_is_held(browser, serve):
    """An authored field receives real keys before the fresh state answer arrives."""
    module = '<script type="module">void 0;</script>'
    first = LIVE_KEYS_APPARATUS.replace("</head>", module + "</head>")
    second = LIVE_KEYS_APPARATUS_REWRITTEN.replace(
        "</head>", module.replace("void 0", "void 1") + "</head>"
    )
    page = open_page(browser, live_url(serve(first)))
    note = page.locator("#lk-note")
    note.click()
    note.type("half a thought")
    original_document = page.evaluate("performance.timeOrigin")
    replaced = False
    blocked = []

    def navigated(frame):
        nonlocal replaced
        if frame == page.main_frame:
            replaced = True

    def state_answer(route):
        if replaced:
            blocked.append(route)
        else:
            route.continue_()

    page.on("framenavigated", navigated)
    page.route("**/api/state*", state_answer)
    (serve.page_dir / "index.html").write_text(second)
    # Deliberately test the startup interval: final readiness is held at the HTTP
    # boundary, while the replacement owes the field its focus and native keys.
    page.wait_for_function(
        "old => performance.timeOrigin !== old", arg=original_document
    )
    expect(page).to_have_title("Live keys rewritten")
    expect(note).to_be_focused()
    assert page.locator("body").get_attribute("data-lf-presented") is None
    page.keyboard.type(" continued")
    expect(note).to_have_value("half a thought continued")
    assert blocked
    page.unroute("**/api/state*", state_answer)
    for route in blocked:
        route.continue_()
    wait_until_ready(page)
    expect(note).to_have_value("half a thought continued")
    expect(note).to_be_focused()


def test_a_withdrawn_ask_leaves_the_user_on_the_page(browser, serve):
    """A revision that takes the question away has nowhere to put the user back."""
    version_url = serve(LIVE_KEYS_V1)
    page = open_page(browser, live_url(version_url))
    mark = page.locator("#lk-two .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()

    (serve.page_dir / "index.html").write_text(LIVE_KEYS_ASK_WITHDRAWN)
    told(page)
    expect(page).to_have_title("Live keys without it")
    expect(page.locator("body")).to_be_focused()


def test_a_user_working_an_ask_keeps_it_across_a_replacing_document(browser, serve):
    """The fresh-document install hands back the same standing the patch does.

    A revision whose executable identity differs cannot be patched in, so the user
    arrives in a new document where nothing they held exists. They were told the same
    "Updated to …" either way and cannot tell the two installs apart, so the Ask rides
    across in the one-use handoff beside their reading position.
    """
    module = """<script type="module">
customElements.define('page-counter', class extends HTMLElement {
  connectedCallback() { this.textContent = 'count 0'; }
});
</script>"""
    first = LIVE_KEYS_V1.replace("</head>", module + "</head>")
    second = LIVE_KEYS_ASK_REWRITTEN.replace(
        "</head>", module.replace("count 0", "count 10") + "</head>"
    )
    page = open_page(browser, live_url(serve(first)))
    page.keyboard.press("q")
    expect(page.locator("#lk-decision")).to_be_focused()
    original_document = page.evaluate("performance.timeOrigin")

    (serve.page_dir / "index.html").write_text(second)
    told(page)

    expect(page).to_have_title("Live keys rewritten")
    assert page.evaluate("performance.timeOrigin") != original_document, (
        "the revision was patched in, so this proves nothing about the other install"
    )
    expect(page.locator("#lk-decision")).to_be_focused()
    assert active_digit_bindings(page) == "1–4"


def test_a_generated_shadow_editor_follows_an_arriving_live_version(browser, serve):
    """A retained generated shadow control follows unrelated authored changes."""
    version_url = serve(LIVE_V1)
    page = open_page(browser, live_url(version_url))
    page.evaluate(
        """() => {
          const host = document.createElement('section');
          host.id = 'shadow-editor';
          const root = host.attachShadow({mode: 'open'});
          const box = document.createElement('textarea');
          box.dataset.lfOffer = '';
          root.append(box);
          document.querySelector('main').append(host);
          box.focus();
        }"""
    )

    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    expect(page).to_have_title("Live second")
    assert (
        page.evaluate(
            "() => document.querySelector('#shadow-editor').shadowRoot.activeElement?.tagName"
        )
        == "TEXTAREA"
    )


def test_a_pending_navigation_prevents_another_live_activation(browser, serve):
    """The departing document stops applying state after its navigation starts.

    Each revision changes the page's own code, so each is followed into a fresh
    document and there is a navigation to hold.
    """
    page = open_page(browser, live_url(serve(executable_revision(LIVE_V1, "one"))))
    held = []

    def hold_navigation(route):
        if route.request.is_navigation_request():
            held.append(route)
        else:
            route.continue_()

    page.route("**/*", hold_navigation)
    try:
        (serve.page_dir / "index.html").write_text(executable_revision(LIVE_V2, "two"))
        holding(page, held, 1, "the fresh revision document")
        # A newer save overtakes this navigation. The same live root response owns
        # the final revision; the old realm cannot launch another activation.
        (serve.page_dir / "index.html").write_text(
            executable_revision(LIVE_V3, "three")
        )
        held[0].continue_()
        told(page)
        expect(page).to_have_title("Live third")
        assert len(held) == 1
    finally:
        page.unroute("**/*", hold_navigation)


def test_a_revision_the_page_has_to_refuse_leaves_the_beat_beating(browser, serve):
    """A refusal is an answer the beat has to be able to read.

    A page can adopt a newer revision without installing it. The fetch for its document
    can fail, which is reported and left for the version chip to retry, so the user
    stands on the older revision with the newer one named in the state the page applied.
    Every beat from then on asks the same preparation whether it would activate now. When
    a later fetch answers from a layer re-vendored under the page, the preparation refuses
    instead: this page is already reloading, and the revision belongs to the layer it is
    leaving. An answer only the install path knew how to read made the beat's question
    throw, and the beat carries the clock, the deferred corrections, and this retry, so a
    refusal stopped all three and reported a page failure on the way out of a document
    nobody had complained about. A re-vendor rewrites the whole page directory, so the
    registry the page probes names the new generation as well; that is what tells the
    page a reload has a different document to land on.
    """
    first = leaf_page(
        "Beat first",
        '<h1 id="bt-title">Beat</h1>\n<p id="bt-line">The cutover has not started.</p>',
    )
    second = first.replace("Beat first", "Beat second").replace(
        "The cutover has not started.", "The cutover finished."
    )
    page = open_page(browser, live_url(serve(first)))
    asked = []
    # The state applies the first refusal and adopts the revision anyway; the two after
    # it are beats, which is what puts the beat on the answer the fourth ask brings back.
    REFUSALS = 3

    def answer(route):
        asked.append(route)
        if len(asked) <= REFUSALS:
            refuse(route)
            return
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Layer": "re-vendored"},
        )

    # The page probes its own source before reloading, because only a source that has
    # moved has another document to give. A re-vendor moves the whole page directory, so
    # that one probe answers for the new generation; the document it brings back is the
    # re-vendored page, which this fixture leaves as the directory it really is.
    probes = []

    def revendored(route):
        probes.append(route)
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={
                **response.headers,
                **({"Leaf-Layer": "re-vendored"} if len(probes) == 1 else {}),
            },
        )

    page.route("**/revisions/*", answer)
    try:
        (serve.page_dir / "index.html").write_text(second)
        page.route("**/registry.json", revendored)
        holding(page, asked, REFUSALS + 1, "the asks the beats made for the revision")
        # The refusal reloads, and the page that comes back is on the layer it was told
        # about, holding the revision it could not be given in place.
        expect(page).to_have_title(
            "Beat second", timeout=render_checks_model.HANDOVER_DEADLINE_MS
        )
        wait_until_ready(page)
        problems = take_browser_errors(page)
        assert len(problems) >= 2 and all(
            is_problem(p, "failed to load") for p in problems
        ), (
            "the beats did not come through with only their own refused asks behind "
            f"them: {problems}"
        )
    finally:
        page.unroute("**/revisions/*", answer)
        page.unroute("**/registry.json", revendored)


def test_the_ask_walk_keeps_its_place_when_a_version_lands(browser, serve):
    """A stamped version follows by navigation, and the user's place rides across.
    The passage they were reading did; where the walk had got to was a variable in a
    module the navigation threw away, so it did not, and the user was demoted without
    a word from the most exact reading of where they stand to the coarsest. Standing on
    the third of four Asks when v2 landed, they pressed `q` and were handed the third
    again — after looking slightly back above that Ask, the block at the top of the
    window is somewhere they had already walked past.

    So the walk's place travels in the same record as the passage, and the press after
    the version lands is the press they would have made before it. The ring is not owed a
    record of its own: it is painted from the focus, and the activation hands the user
    back the control they were standing on, so the Ask they were in wears it still."""
    url = serve(ASKS_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    # Short enough that an Ask in the middle of the window has page text above it,
    # which is the whole of what makes the coarse reading the wrong one.
    resized(page, 900, 400)

    for ask in ASKS_IN_ORDER[:3]:
        page.keyboard.press("q")
        expect(page.locator(f"#{ask}")).to_have_attribute("data-lf-ask", "1")
    scroll_settled(page)

    # Ask travel now starts at the Ask's opening, which normally makes the coarse
    # reading agree with the saved landing. Look back just far enough to make the two
    # meanings diverge: the scroll position says the preceding change, while the walk's
    # exact record still says the third Ask.
    page.evaluate("""() => {
        const earlier = document.getElementById('refill-now').getBoundingClientRect();
        document.scrollingElement.scrollBy({top: earlier.bottom - 220, behavior: 'instant'});
    }""")

    stamp_page(d, ASKS_PAGE, "two")
    wait_for_revision(page, 2)

    expect(page.locator("#t-baffles-decision")).to_have_attribute("data-lf-ask", "1")
    expect(page.locator("[data-lf-ask]")).to_have_count(1)
    # The condition the restore is for, stated rather than assumed: an earlier Ask's own
    # prose is on screen above the one the user was standing on, so a walk reading the
    # page alone starts behind them and steps forward onto the Ask they just left.
    position = page.evaluate("""() => {
            const decision = document.getElementById('t-baffles-decision').getBoundingClientRect();
        const earlier = document.getElementById('refill-now').getBoundingClientRect();
        return {earlierBottom: earlier.bottom, decisionTop: decision.top,
                scrollTop: document.scrollingElement.scrollTop};
    }""")
    assert 42 < position["earlierBottom"] <= position["decisionTop"], position
    page.keyboard.press("q")
    expect(page.locator("#t-bath-decision")).to_have_attribute("data-lf-ask", "1")


def test_the_reading_position_restores_onto_a_section_that_draws_no_box(browser, serve):
    """The landmark a reading position falls back to is an element like any other, and
    an element that generates no box measures (0,0) at the document's origin.

    Read raw, that answer arrives on both sides of the subtraction — once when the
    place is written down and once when it is put back — so the correction came out 0
    and a restore that had somewhere to land did nothing at all. The user was left at
    the top of a page they had been thirty paragraphs into. It is quiet twice over: only
    a user whose quote the new version rewrote reaches this branch, and a page whose
    sections all draw boxes never sees it."""
    url = serve(BOXLESS_SECTION_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    resized(page, 900, 600)

    # Read from inside the wrapper, so every block on screen is one of its own and the
    # nearest id above them is the wrapper.
    page.evaluate("""() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('wrap'));
      document.scrollingElement.scrollTop += r.getBoundingClientRect().top + 50; }""")
    before = page.evaluate(WRAP_TOP)

    # The branch under test, stated rather than assumed. In-place activation carries this
    # object directly; pagehide stores the same capture for document travel, which gives
    # the test a view of it without adding a second diagnostic representation.
    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    view = page.evaluate("""() => {
      for (const k of Object.keys(sessionStorage))
        if (k.endsWith('lf-view')) return JSON.parse(sessionStorage[k]);
      return null; }""")
    assert view and view["section"] == "wrap", (
        f"the landmark was not the boxless wrapper: {view}"
    )
    assert view["quote"].startswith("Held"), (
        f"v2 still holds this quote, so the section branch never ran: {view}"
    )

    stamp_page(d, KEPT_SECTION_PAGE, "two")
    wait_for_revision(page, 2)

    after = page.evaluate(WRAP_TOP)
    assert abs(after - before) <= 4, (
        f"the user left the wrapper's words {before}px from the top of the window and "
        f"was put back at {after}px"
    )


def test_the_ring_says_where_the_user_is_standing(browser, serve):
    """One ring, meaning one thing: this is where the user is standing. It is painted
    from the focus, so every way into a decision paints it and leaving takes it off.

    The walk used to write it, and nothing ever took it off. So it said where the walk
    had left them rather than where they were: press `d`, click away, work in the panel
    for ten minutes, and a decision nobody was standing in went on wearing "you are here" —
    while a user who had reached the same decision by Tab or by clicking one of its
    controls got no ring at all. The same place, marked or not by how they arrived.

    The chrome wears the same band, because a user who has backed out of the panel is
    standing on a button and that is the same fact about them. It wore the browser's own
    ring there, in the browser's blue, a few inches from a decision ringed in the page's
    accent, with nothing saying the two rectangles meant one thing.

    A joined options control is the one shape that draws the band somewhere else: it is
    already a framed box, so a ring around the decision *and* one inside it would read as
    a second border that comes and goes, and while the user is in the control the exact
    row the keyboard is on carries the band alone. Which row, in the same band — one ring
    still meaning one thing. An arrival is the other side of that: it stands the user on
    the decision rather than in the control, so there the decision's own ring is the one."""
    page = open_page(browser, serve(ASKS_PAGE))
    question = page.locator("#live-question-decision")
    page.keyboard.press("q")
    expect(question).to_have_attribute("data-lf-ask", "1")
    arrival_ring = question.evaluate(RING)
    assert arrival_ring == [
        "solid",
        "2px",
        token_colour(page, "--accent"),
    ], f"the decision the walk stood the user on is not ringed: {arrival_ring}"

    # One press in, and the band moves to the row rather than doubling: the frame is the
    # control, and a ring around it as well would come and go with the question.
    page.keyboard.press("Tab")
    assert question.evaluate(RING)[0] == "none", (
        "the decision drew its own ring around a control that is already a frame: "
        f"{question.evaluate(RING)}"
    )
    row_ring = page.locator("#lq-keep").evaluate(RING)
    assert row_ring == [
        "solid",
        "2px",
        token_colour(page, "--accent"),
    ], f"the row the user is on is not ringed in the page's own band: {row_ring}"

    # A suggestion hangs its ✓ Accept out in the page margin, so a user working one has
    # two marks for one fact — the ring on the change, the focus band on the margin entry deciding
    # it — and they had better be one band. The margin entry's comes from the runtime's own
    # shared rule, which every press in that margin wears: the suggestion family spelled
    # its own once, which is a family stating a fact about a shape the runtime owns.
    #
    # Real presses verify the keyboard route as well as its focus treatment.
    page.keyboard.press("q")
    suggestion = page.locator("#sug-refill")
    expect(suggestion).to_have_attribute("data-lf-ask", "1")
    accept = suggestion_control(page, "sug-refill", "accept")
    accept.focus()
    # Tab inside the margin reaches the same suggestion's ✗ Reject, rendered from the
    # same contribution in the options group. The user is still deciding this change,
    # so the ring stays on it. It did not: the secondary control stood nowhere, the band
    # came off the suggestion for as long as the user held that control, and returning
    # to ✓ Accept brought it back a frame later — which is also how the read below came
    # to be taken while nothing on the page was ringed at all.
    #
    # Read after the frame the focus move's repaint is coalesced into, so this states the
    # band the page settles on rather than whichever side of that frame the read lands on.
    page.keyboard.press("Tab")
    rendered(page)
    decision_ring = suggestion.evaluate(RING)
    assert decision_ring == row_ring, (
        "the decision lost its ring while the user held one of its own margin "
        f"controls: {decision_ring} against {row_ring}"
    )
    # Stable identity is the contribution owner plus entry key, independent of which
    # projection surface currently presents it.
    assert accept.count() == 1, (
        "the suggestion has more than one presented Accept control"
    )
    page.keyboard.press("Shift+Tab")
    expect(accept).to_be_focused()
    # A decision that is not a joined control wears the ring itself, and it is the band
    # the row above wore: the two shapes say one thing about the user.
    decision_ring = suggestion.evaluate(RING)
    assert decision_ring == row_ring, (
        "a decision and an options row are drawn in two different bands for the one "
        f"fact: {decision_ring} against {row_ring}"
    )
    assert accept.evaluate(RING) == decision_ring, (
        "the control in the margin is drawn in some other band than the decision it decides: "
        f"{accept.evaluate(RING)} against {decision_ring}"
    )

    # Standing somewhere that asks nothing takes it off, rather than leaving it behind.
    page.locator("#h").click()
    expect(page.locator("[data-lf-ask]")).to_have_count(0)

    # A pointer landing inside an open decision is standing in it, though no walk brought
    # them there: the ring renders the focus rather than remembering a press.
    page.locator("#live-question .lf-another leaf-text").click()
    expect(question).to_have_attribute("data-lf-ask", "1")

    # Answering takes it off with the focus still inside: the ring is for the question
    # the user is working, and an answered one is no longer a question.
    page.locator("#lq-token .lf-pick").click()
    expect_asks_answered(page, "2/5")
    expect(page.locator("[data-lf-ask]")).to_have_count(0)
    expect(page.locator("#lq-token .lf-pick")).to_be_focused()

    # The chrome's own control, which the user reaches by Tab or by the banner's own
    # keys rather than by backing out of the panel — a surface lands them on the page,
    # never on the control that reopens it. What is asserted here is the band the ring
    # is drawn in while they stand there.
    toggle = page.locator(".lf-threads-toggle")
    toggle.focus()
    # Return by keyboard to exercise the same focus band through sequential navigation.
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(toggle).to_be_focused()
    assert toggle.evaluate(RING) == decision_ring, (
        "the user standing in the chrome is drawn in some other band than the "
        f"one a decision uses: {toggle.evaluate(RING)} against {decision_ring}"
    )


def test_escape_lets_go_of_the_ask_the_user_is_standing_on(browser, serve):
    """Escape closes the command reference, then lets go of the Ask and focuses body.
    The next Ask walk reads the visible page place, returning to the first Ask before
    advancing. Letting go also works on a page with no scroll range and after a Page
    Map action leaves focus in a margin cluster."""
    url = serve(ASKS_PAGE)
    # A third action puts the suggestion's cluster beyond its two resting controls.
    answered_comment(
        serve.page_dir,
        "Check this wording before accepting it.",
        {"section": "sug-refill"},
    )
    page = open_page(browser, url)
    page.keyboard.press("q")
    expect(page.locator("#live-question-decision[data-lf-ask]")).to_have_count(1)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("let go")
    # And the reference says the same press in its own words. It said "Back out one
    # layer" for every rung, which was true while every rung took a layer of chrome off
    # the page: standing on a decision is the user holding something, with no layer over
    # the page at all, so the two surfaces named one press two ways.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_contain_text(
        "Let go of what you are standing on"
    )
    page.keyboard.press("Escape")  # the reference's own rung, which hands focus back
    expect(page.locator(".lf-command-reference")).not_to_have_class(re.compile("open"))
    expect(page.locator("#live-question-decision[data-lf-ask]")).to_have_count(1)

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator("[data-lf-ask]")).to_have_count(0)
    assert page.evaluate("() => document.activeElement === document.body")
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("let go")

    # The directional walk reads the user's current visible place after Escape.
    # Reenter the first Ask from there, then move to the next one.
    page.keyboard.press("q")
    expect(page.locator("#live-question-decision")).to_be_focused()
    page.keyboard.press("q")
    expect(page.locator("#sug-refill[data-lf-ask]")).to_have_count(1)
    walked_item = page.locator('[data-lf-margin-for="sug-refill"]')
    expect(walked_item.locator(":scope > .lf-margin-more")).to_be_visible()
    expect(walked_item.locator(":scope > .lf-margin-options")).to_be_hidden()

    # A walk out of an unfolded cluster folds the old destination while suppressing
    # only the new destination's Tab-style arrival. The two halves share one native
    # focus transition, whose focusout and focusin both fire inside focus().
    walked_item.locator(":scope > .lf-margin-more").click()
    expect(walked_item.locator(":scope > .lf-margin-options")).to_be_visible()
    page.keyboard.press("q")
    expect(page.locator("#t-baffles-decision[data-lf-ask]")).to_have_count(1)
    expect(walked_item.locator(":scope > .lf-margin-more")).to_be_visible()
    expect(walked_item.locator(":scope > .lf-margin-options")).to_be_hidden()

    # A window tall enough to hold the whole page, so the root has no scroll range and the
    # browser will not focus body as a scrolling affordance.
    resized(page, 1200, 2400)
    assert not page.evaluate(
        "() => document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight"
    ), "the page still scrolls, so this proves nothing about a short one"
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body"), (
        "letting go left the user holding the control on a page that fits the window"
    )

    # A generated Page Map hint arrives the way the walk does and then presses the exact
    # Accept margin entry it names. What unfolds there is that press's own result rather than
    # the arrival's, and the ladder still owes one Escape to let go of where the press
    # left the user.
    with sending(page, "the addressed suggestion's acceptance"):
        go_to_address(page, "Margin entry", "sug-refill", "accept")
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate(
        """() => Boolean(document.activeElement.closest(
             '[data-lf-margin-for="sug-refill"]'))"""
    ), "the address left the user outside the cluster it pressed"
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")


def test_travelling_to_an_element_lands_where_it_was_aimed(browser, serve):
    """Clicking a quoteless thread's § label brings its element to the middle — the
    promise made by callers that travel to a document anchor.

    It was 27px short of the middle in every one of them, and invisibly so: the
    scroller declares `scroll-padding-top` to keep a native fragment jump clear of
    the banner, and scrollIntoView's own "center" measures against the padded box
    rather than the viewport. So the arithmetic is the painted-range branch's, which
    never went through scrollIntoView and never drifted.

    A section taller than the viewport is the case centring cannot serve at all:
    put its middle in the middle and the heading the user was sent to is above
    the top edge. It takes the banner clearance instead — read from the same
    declaration, so the number lives in one place — and the user starts at the
    start."""
    url = serve(TRAVEL_PAGE)
    thread = {
        section: append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About {section}.",
                "anchor": {"section": section},
            },
        )["id"]
        for section in ("flow", "long-part")
    }
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()

    def quote(section):
        card = page.locator(f'.lf-thread[data-id="{thread[section]}"]')
        card.locator(".lf-thread-summary").click()
        return card.locator(".lf-quote")

    # Centred: the destination the travel computed, which a glide toward it passes
    # through no earlier position that could be mistaken for. Put it wholly out of sight
    # first: a readable destination now keeps the user's place.
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    assert page.locator("#flow").evaluate(
        "el => el.getBoundingClientRect().bottom <= 0"
    )
    quote("flow").click()
    page.wait_for_function(
        """() => { const r = document.getElementById('flow').getBoundingClientRect();
                   return r.height > 0
                       && Math.abs(r.top + r.height / 2 - innerHeight / 2) < 2; }"""
    )

    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    assert page.locator("#long-part").evaluate(
        "el => el.getBoundingClientRect().top >= innerHeight"
    )
    quote("long-part").click()
    page.wait_for_function(
        """() => { const r = document.getElementById('long-part').getBoundingClientRect();
                   const clear = parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop);
                   return r.height > innerHeight && Math.abs(r.top - clear) < 2; }"""
    )


def test_the_ask_walk_follows_registry_declarations(browser, serve):
    """Removing a standing-request declaration removes that widget from every Ask
    surface without changing the runtime, banner, or keyboard walk."""
    url = serve(ASKS_PAGE)
    registry = json.loads((serve.page_dir / "registry.json").read_text())
    del registry["lf-suggestion"]["x-awaits"]
    del registry["lf-suggestion"]["properties"]["resolves"]
    (serve.page_dir / "registry.json").write_text(json.dumps(registry))
    stamp_page(
        serve.page_dir,
        (serve.page_dir / "index.html").read_text(),
        "capture the declaration change",
    )

    page = open_page(browser, live_url(url))
    expect_asks_answered(page, "1/4")
    # The blanket answer went with the declaration that named its verb.
    expect(page.locator(".lf-answer-all")).to_have_count(0)
    for expected in [
        "live-question-decision",
        "t-baffles-decision",
        "t-bath-decision",
    ]:
        page.keyboard.press("q")
        expect(page.locator(f"#{expected}")).to_have_attribute("data-lf-ask", "1")


def test_a_workers_report_paints_live_and_ends_at_the_version_that_answers_it(
    browser, serve
):
    """The agent channel, end to end in the browser: a `leaf page report`
    reaches the open page on the next poll and paints as provisional news — the status
    attribute moves, the parent's done-fraction recounts, and Page Map identifies a
    Reported state rather than the user's change. Task status remains work
    state and never creates a user request. Then the version that answers the report
    by id takes the page back: replay skips a report the note named, so the overruling
    version's own state is what renders, with no provisional mark left on it. Last, the
    diff against the base version reads the base's state as the user saw it — report
    included — so the overrule marks as a change even though the two files spell the
    same status."""
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    fraction = page.locator("#t-feeders > .work-progress")
    expect(fraction).to_contain_text("1/2 done")
    # Nothing waits on the user.
    expect(page.locator(".lf-queue")).to_have_text("Questions: 0")

    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(d), "t-parser", "status", "value=review"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    task = page.locator("#t-parser")
    expect(task).to_have_attribute("status", "review")
    expect(task).to_have_attribute("data-lf-reported", "1")
    expect(task).not_to_have_attribute("data-lf-user-override", "1")
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    report_reading = page.get_by_role(
        "button", name=re.compile(r"^Open reported state: Reported state")
    )
    expect(report_reading).to_be_visible()
    page.keyboard.press("Escape")
    assert task.evaluate("el => getComputedStyle(el).outlineStyle") == "none"
    # The visible status line follows the reported attribute, so a user listening
    # hears the current state too.
    assert "review" in task.aria_snapshot()
    expect(page.locator(".lf-queue")).to_have_text("Questions: 0")

    # A second report supersedes the first — absolute values fold — and the
    # progress fraction recounts across the tree.
    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(d), "t-parser", "status", "value=done"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(task).to_have_attribute("status", "done")
    said = task.aria_snapshot()
    assert "done" in said and "review" not in said, said
    expect(fraction).to_contain_text("2/2 done")
    expect(page.locator(".lf-queue")).to_have_text("Questions: 0")

    # The overruling version: its markup keeps `active` and publishes typed report
    # settlements resolved from `overruled`, so replay stops them
    # and the document speaks again.
    v2 = REPORT_PAGE.replace(
        '<lf-test-task id="t-parser" status="active">',
        '<lf-test-task id="t-parser" status="active" overruled>',
    )
    stamp_page(d, v2, "not done yet")
    assert len(events_model.read_events(d)[-1]["settles"]) == 2
    wait_for_revision(page, 2)
    task = page.locator("#t-parser")
    expect(task).to_have_attribute("status", "active")
    expect(task).not_to_have_attribute("data-lf-reported", "1")
    expect(page.locator("#t-feeders > .work-progress")).to_contain_text("1/2 done")

    # The diff's state half, mirror-image: v1's markup also said `active`, but
    # the user last saw v1 wearing the report's `done`, so the overrule is a
    # change since the base — the report-layered base state is what says so.
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["t-parser"]


def test_a_comparison_retries_when_the_live_projection_advances(browser, serve):
    """The mapped revision and its state must describe the DOM in one reading.

    Hold the first projected base after the server has answered it, advance the open
    page with a report, and then deliver that stale base. The comparison asks again at
    the new sequence before painting; otherwise it marks the task as changed even though
    the same report stands on both the base and current documents.
    """
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    stamp_page(
        d,
        REPORT_PAGE.replace("</main>", '<p id="new-copy">A new prose line.</p></main>'),
        "added prose",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    held = []
    requests = []

    def hold_first_view(route):
        requests.append(route.request.url)
        if not held:
            held.append([route, None, False])
        else:
            route.continue_()

    page.route("**/api/view*", hold_first_view)
    try:
        banner_control(page, ".lf-version").click()
        with page.expect_request("**/api/view*"):
            page.locator('.lf-version-diff[data-lf-version="1"]').click()
        holding(page, held, 1, "the first comparison view")
        assert held, "the first comparison view was not held"
        held[0][1] = held[0][0].fetch()

        append_command(
            d,
            {
                "kind": "report",
                "author": "agent",
                "revision": 1,
                "widget": "t-parser",
                "action": "status",
                "detail": {"value": "done"},
            },
        )
        told(page)
        expect(page.locator("#t-parser")).to_have_attribute("status", "done")

        with page.expect_request("**/api/view*"):
            held[0][0].fulfill(response=held[0][1])
            held[0][2] = True
        holding(page, requests, 2, "the retried comparison view")
        assert len(requests) >= 2, "the stale comparison view was not retried"
        expect(page.locator(".lf-version")).to_have_text("Showing v2")
        expect(page.locator(".lf-version")).to_have_class(re.compile(r"\bon\b"))
        expect(page.locator("#new-copy")).to_have_class(re.compile(r"lf-ins-block"))
        expect(page.locator("#t-parser")).not_to_have_class(re.compile(r"lf-ins-block"))
    finally:
        if held and not held[0][2]:
            held[0][0].fulfill(response=held[0][1])
        page.unroute("**/api/view*")


def test_a_comparison_reaches_a_version_stamped_before_a_re_vendor(browser, serve):
    """A revision keeps the layer it captured, and comparing to it is not a re-vendor.

    `/api/view` and an immutable document are stamped with the captured generation of
    the revision they name, so after a re-vendor the base of a comparison legitimately
    answers for a layer the live page is no longer on. Running that answer through the
    delivery gate reads it as the page being re-vendored underneath the user, which it
    is not: the page refuses its own comparison, and the user is told the server is
    updating.
    """
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    # The whole premise is that this second init really re-vendors. Were it ever refused,
    # the base of the comparison would not be foreign and the case would pass against the
    # runtime it exists to pin.
    revendored = CliRunner().invoke(
        cli_model.cli, ["page", "init", str(d)], catch_exceptions=False
    )
    assert revendored.exit_code == 0, revendored.output
    stamp_page(
        d,
        REPORT_PAGE.replace("</main>", '<p id="new-copy">A new prose line.</p></main>'),
        "added prose",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))

    banner_control(page, ".lf-version").click()
    page.locator('.lf-version-diff[data-lf-version="1"]').click()

    expect(page.locator("#new-copy")).to_have_class(re.compile(r"lf-ins-block"))
    expect(page.locator(".lf-notice")).not_to_have_text(
        "Waiting for the server to finish updating."
    )


def test_a_rosters_row_says_when_the_log_last_heard_from_that_worker(browser, serve):
    """The half of a roster no version can write down. A standing report states what
    each worker is doing; only the log knows when it last said so, and a page that keeps
    a fleet is at its least trustworthy exactly when the user has been away longest.
    So the row renders elapsed time from the newest report and re-renders on every poll.

    Then the case the line exists for: a claim of work nobody has refreshed. It is
    called out in words rather than in the tint alone, on the rope the banner already
    gives a page's one agent (quietSince), and only against a claim — an idle worker
    that has said nothing all day is idle, which is what it said."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    wren, finch = page.locator("#ag-wren"), page.locator("#ag-finch")
    # Before any worker has spoken, the row dates from the version that asserted it —
    # not from nothing, which would leave a fleet dead since last night reading exactly
    # like one published a minute ago.
    expect(wren.locator(".lf-heard")).to_contain_text("last heard")
    # The state is a word this module writes rather than paint the runtime speaks, so
    # a user listening gets it from the row itself.
    assert "working" in wren.aria_snapshot()

    sent = CliRunner().invoke(
        cli_model.cli,
        # A state the markup does not already hold, or there is no news to paint: a
        # report saying what the page says is blessed silence, not provisional state.
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=waiting",
            "text=rebasing onto main",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(wren.locator(".lf-doing")).to_have_text("rebasing onto main")
    expect(wren).not_to_have_attribute("doing", "rebasing onto main")
    expect(wren).to_have_attribute("data-lf-reported", "1")
    expect(wren.locator(".lf-heard")).to_have_text("last heard just now")
    expect(wren.locator(".lf-cold")).to_have_count(0)

    stale_report(d, "ag-wren", "still rebasing", 3)
    told(page)
    expect(wren.locator(".lf-doing")).to_have_text("still rebasing")
    expect(wren.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(wren.locator(".lf-cold")).to_have_text("quiet")

    # The same silence against no claim of work says nothing beyond its own age.
    stale_report(d, "ag-finch", "nothing", 3, state="idle")
    told(page)
    expect(finch.locator(".lf-doing")).to_have_text("nothing")
    expect(finch.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(finch.locator(".lf-cold")).to_have_count(0)

    # And it survives the version that answers the report, which is the case the whole
    # line exists for and the one an earlier build could never reach. Publishing absorbs
    # a report by id, so a roster reading standing reports blanked every row at every
    # publish — and the user most needs this exactly where that left nothing: a worker
    # that claimed work, had the claim written into the document, and then died. The
    # provisional mark goes, because the document speaks again; the log's memory of who
    # last said anything does not, because no version can speak for that.
    stamp_page(d, ROSTER_PAGE, "absorbing")
    wait_for_revision(page, 2)
    wren = page.locator("#ag-wren")
    expect(wren).not_to_have_attribute("data-lf-reported", "1")
    expect(wren.locator(".lf-doing")).to_have_count(0)
    expect(wren.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(wren.locator(".lf-cold")).to_have_text("quiet")


def test_the_report_feed_reads_reports_by_typed_target(browser, serve):
    """Worker reports reach widgets through one typed reading. The work the agent has
    in hand is no report: it is the workflows' Working stage and the tasks' starts."""
    page = open_page(browser, live_url(serve(ROSTER_PAGE)))
    d = serve.page_dir
    # Event ids and authored element ids belong to different identity spaces. Give
    # the thread and widget the same spelling so only the typed target can separate
    # their reports; a bare id or target lookup by store would merge them.
    thread = append_carried_log_record(
        d,
        {
            "id": "ag-wren",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "ag-wren"},
            "text": "Can you check this worker's mount price?",
        },
    )
    told(page)

    report = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=working",
            "text=checking the mount prices",
        ],
    )
    assert report.exit_code == 0, report.output
    started = CliRunner().invoke(
        cli_model.cli,
        ["task", "start", str(d), thread["id"], "checking the user's question"],
    )
    assert started.exit_code == 0, started.output
    told(page)

    reports = page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/widget-api.js')).reportSequence()"
    )
    by_source = {report["source"]: report for report in reports}
    assert set(by_source) == {"report"}
    assert by_source["report"] == {
        "id": by_source["report"]["id"],
        "target": {"kind": "widget", "id": "ag-wren"},
        "source": "report",
        "action": "state",
        "detail": {"value": "working", "text": "checking the mount prices"},
        "text": "checking the mount prices",
        "ts": by_source["report"]["ts"],
        "revision": 1,
        "seq": by_source["report"]["seq"],
        "agent": "Claude",
        "session": by_source["report"]["session"],
        "disposition": "effective",
    }
    assert by_source["report"]["session"]
    targeted = page.evaluate(
        """async () => {
            const feed = await window.__lfRuntimeImport('/runtime/widget-api.js');
            return {
                widget: feed.reportSequence(document.querySelector('#ag-wren')),
                thread: feed.reportSequence({kind: 'thread', id: 'ag-wren'}),
                bare: (() => {
                    try { feed.reportSequence('ag-wren'); }
                    catch (error) { return `${error.name}: ${error.message}`; }
                })(),
            };
        }"""
    )
    assert [report["source"] for report in targeted["widget"]] == ["report"]
    assert targeted["thread"] == []
    assert targeted["bare"].startswith("TypeError: report target must be")
    expect(page.locator("#ag-wren .lf-doing")).to_have_text("checking the mount prices")

    # A version note settles the report.
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": thread["id"],
            "revision": 1,
            "text": "The mount price is in the attached quote.",
        },
    )
    stamp_page(d, ROSTER_PAGE, "recorded")
    wait_for_revision(page, 2)

    reports = page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/widget-api.js')).reportSequence()"
    )
    by_source = {report["source"]: report for report in reports}
    assert by_source["report"]["disposition"] == "settled"
    expect(page.locator("#ag-wren .lf-doing")).to_have_count(0)


def test_report_words_and_widget_state_wait_together_for_a_drag(browser, serve):
    """The page-wide drag gate withholds widget views and projection coverage."""
    page = open_page(browser, serve(ROSTER_PAGE))
    d = serve.page_dir
    row = page.locator("#ag-wren")

    first = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=working",
            "text=checking the first mount",
        ],
    )
    assert first.exit_code == 0, first.output
    told(page)
    expect(row).to_have_attribute("state", "working")
    expect(row.locator(".lf-doing")).to_have_text("checking the first mount")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "1")

    page.evaluate(
        """async () => {
          const {dragging} = await window.__lfRuntimeImport(
            '/runtime/widget-elements.js');
          dragging(document.body, true);
        }"""
    )
    second = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=idle",
            "text=checking the second mount",
        ],
    )
    assert second.exit_code == 0, second.output
    told(page)
    expect(row).to_have_attribute("state", "working")
    expect(row.locator(".lf-doing")).to_have_text("checking the first mount")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "1")

    page.evaluate(
        """async () => {
          const {dragging} = await window.__lfRuntimeImport(
            '/runtime/widget-elements.js');
          dragging(document.body, false);
        }"""
    )
    expect(row).to_have_attribute("state", "idle")
    expect(row.locator(".lf-doing")).to_have_text("checking the second mount")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "2")


@pytest.mark.parametrize("holding", ["defer", "preparation"])
def test_report_narration_and_coverage_wait_for_the_widgets_own_presentation(
    browser, serve, holding
):
    """Report prose, coverage, and clocks consume the widget's canonical proof.

    A local editing hold and an asynchronous preparation are distinct owners of
    completion. Each holds only its widget; report narration cannot jump ahead by
    inferring that the coordinate was committed because its DOM node still exists.
    """
    page = open_page(browser, serve(ROSTER_PAGE))
    d = serve.page_dir
    row = page.locator("#ag-wren")
    first = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=working",
            "text=first report",
        ],
    )
    assert first.exit_code == 0, first.output
    told(page)
    expect(row.locator(".lf-doing")).to_have_text("first report")
    page.evaluate(
        """async holding => {
          const api = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const {clockValue, tickClock} = await window.__lfRuntimeImport('/runtime/presence.js');
          const {readApplicationPresentation} = await window.__lfRuntimeImport('/runtime/semantic-state.js');
          const owner = document.getElementById('ag-wren');
          window.__proofClock = 0;
          window.__proofReads = [];
          window.__proofWatching = api.watchReports(owner, reports => {
            clockValue(() => window.__proofClock);
            window.__proofReads.push(reports.map(report => report.text));
          });
          window.__proofTick = async () => {
            window.__proofClock += 1;
            await tickClock(message => { throw new Error(message); });
          };
          window.__proofPending = () => {
            const proof = readApplicationPresentation();
            return api.reportSequence(owner).some(report => report.text === 'held report') &&
              proof.pending.some(region => region.startsWith('widget:ag-wren:')) &&
              !proof.pending.includes('projection:chrome');
          };
          // The watcher gets its first clock reading before the held publication.
          await Promise.resolve();
          const other = api.widgetController(document.getElementById('ag-finch'));
          other.present(new Promise(resolve => { window.__proofOtherResume = resolve; }));
          window.__proofOtherPending = () =>
            readApplicationPresentation().pending.includes('widget:ag-finch:preparation');
          const controller = api.widgetController(owner);
          if (holding === 'defer') {
            window.__proofResume = controller.defer();
          } else {
            let resolve;
            controller.present(new Promise(done => { resolve = done; }));
            window.__proofResume = resolve;
          }
        }""",
        holding,
    )
    if holding == "preparation":
        # A same-epoch reopen has no semantic notification. The next clock paint
        # must still check proof rather than bypassing its readiness guard.
        reads = page.evaluate("window.__proofReads.length")
        page.evaluate("window.__proofWatching.refresh()")
        assert page.evaluate("window.__proofReads.length") == reads
        page.evaluate("window.__proofTick()")
        assert page.evaluate("window.__proofReads.length") == reads
    second = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=idle",
            "text=held report",
        ],
    )
    assert second.exit_code == 0, second.output
    page.wait_for_function("window.__proofPending()")
    page.evaluate("window.__proofTick()")
    assert not page.evaluate(
        "window.__proofReads.some(read => read.includes('held report'))"
    )
    expect(row.locator(".lf-doing")).to_have_text("first report")
    expect(page.locator("body")).not_to_have_attribute("data-lf-applied", "2")
    if holding == "defer":
        expect(row).to_have_attribute("state", "working")
    page.evaluate("window.__proofResume()")
    expect(row).to_have_attribute("state", "idle")
    expect(row.locator(".lf-doing")).to_have_text("held report")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "2")
    assert page.evaluate("window.__proofOtherPending()"), (
        "an unrelated widget's preparation must not block the report or coverage"
    )
    page.evaluate("window.__proofOtherResume()")


def test_a_worker_that_has_never_reported_dates_from_its_version(browser, serve):
    """The direction a freshness line must never fail in. A row nobody has reported on
    is not of unknown age: its words were asserted when the version landed, and are
    exactly that old. Rendering nothing there was the first build's answer, and it hides
    the case the user is most exposed to — a fleet published at six in the evening,
    every worker dead by seven, read at eight the next morning. Every row claims work,
    and with no report behind any of them there is no elapsed line to contradict it and
    no call-out: a dead fleet drawn exactly like a fresh one, one section under a banner
    whose whole design is that a claim nobody revises must not be repeated as fact."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page = open_page(browser, url)
    siskin = page.locator("#ag-siskin")
    expect(siskin.locator(".lf-heard")).to_have_text("last heard just now")
    expect(siskin.locator(".lf-cold")).to_have_count(0)

    backdate_note(d, 1, 3)
    told(page)
    expect(siskin.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(siskin.locator(".lf-cold")).to_have_text("quiet")
    # An idle worker is not called out for the same silence: it claimed nothing.
    expect(page.locator("#ag-finch .lf-heard")).to_have_text("last heard 3h ago")
    expect(page.locator("#ag-finch .lf-cold")).to_have_count(0)


def test_a_rosters_clock_keeps_moving_when_the_server_stops_answering(browser, serve):
    """A clock advances held state even without a new state response."""
    page = open_page(browser, serve(ROSTER_PAGE))
    page.route("**/api/state*", refuse)
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=3))
    expect(page.locator("#ag-wren .lf-heard")).to_have_text("last heard 3h ago")
    expect(page.locator("#ag-wren .lf-cold")).to_have_text("quiet")


def test_a_rosters_row_survives_the_polls_that_keep_it_fresh(browser, serve):
    """A row is a thing the user is invited to select and point at, and it is also
    the one widget with a reason to touch itself every two seconds. Those pull against
    each other, and the first build lost: the clock re-rendered the whole row, so the
    words under a pointer were a different node on every poll — a selection collapsing
    mid-drag, focus dropped off the reference beside it, a click that straddles the
    swap landing on nothing. It is "Paint; don't wrap" reached by rebuilding instead of
    by wrapping, and it fails the same way: nothing errors, the page just stops taking
    the gesture.

    So the clock touches one text node and the structure is rebuilt only when a
    report moves that row. Asserted as node identity rather than as a selection, because
    identity is the property the rendering owes and a selection is one thing that rests
    on it."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page = open_page(browser, url)
    page.evaluate(
        "() => { window.__kept = [...document.querySelectorAll('#ag-wren .lf-doing,"
        " #ag-wren .lf-branch, #ag-wren .lf-state')].map(e => e.firstChild); }"
    )
    sent = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-finch",
            "state",
            "value=idle",
            "text=picking up",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    ticked(page)
    # wren heard nothing in the read or the tick after it, so nothing of wren's may
    # have moved.
    assert page.evaluate(
        "() => window.__kept.every((n, i) => n === [...document.querySelectorAll("
        "'#ag-wren .lf-doing, #ag-wren .lf-branch, #ag-wren .lf-state')][i]?.firstChild)"
    )
    # And a report for this row does rebuild it, or the row would never move at all.
    sent = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=working",
            "text=on to the baffles",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(page.locator("#ag-wren .lf-doing")).to_have_text("on to the baffles")


def test_a_recounted_fraction_holds_the_width_it_had(browser, serve):
    """A number the page rewrites unasked must not resize as it does.

    The done-fraction is the page's most-moved quantity: a worker reports a leaf
    and the parent recounts, on a poll, with nothing the user did to account
    for the shift. It is apparatus, so it is set in the sans — and the sans gives
    each digit its own width where the serif carrying the prose gives them all
    one, which is why the figures are stated for the apparatus voice and not for
    the page. The chip is a filled pill, so its own box is what a user watches
    twitch; where apparatus leads something else, that something moves with it —
    a metric's delta sits directly after the value it follows.

    Measured across the recount rather than a redraw, per tests/AGENTS.md: the
    transition has to be one the figures actually decide. "1/2 done" to
    "2/2 done" stands 1.61px apart with proportional figures and identical with
    tabular, so deleting the declaration fails this. "0/3 done" to "3/3 done"
    would have been the vacuous choice — those two measure 0.03px apart either
    way, and the check would pass with the rule gone.
    """
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    page = open_page(browser, url)
    # The fraction is the last chip its parent builds, after owner and when.
    fraction = page.locator("#t-feeders > .work-progress").last
    expect(fraction).to_have_text("1/2 done")
    before = fraction.bounding_box()["width"]

    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(d), "t-parser", "status", "value=done"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    # The recount is the edge; the geometry is read once behind it.
    expect(fraction).to_have_text("2/2 done")
    after = fraction.bounding_box()["width"]

    assert abs(before - after) < 0.05, (
        f"the fraction resized as it recounted, {before}px to {after}px — a box "
        "the user was given no gesture to explain"
    )


def test_a_user_verb_and_an_agent_verb_stand_side_by_side(
    browser, serve, tmp_path, monkeypatch
):
    """A verb has one writer, so a user's action and a worker's report on one widget
    fold on coordinates of their own: each paints its own record, every log record is
    ready once its coordinate is committed, and undoing the user's action restores
    the authored value without replacing the node."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-tally", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    declarations["lf-tally"]["properties"]["count"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    declarations["lf-tally"]["x-example"] = (
        '<lf-tally id="tally-example" count="0"><pre>Nothing yet.</pre></lf-tally>'
    )
    declarations["lf-tally"]["properties"]["restated"] = {"type": "boolean"}
    declarations["lf-tally"]["properties"]["overruled"] = {"type": "boolean"}
    declarations["lf-tally"]["properties"]["seen"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    record = {"kind": "value", "attr": "count"}
    declarations["lf-tally"]["x-state"] = {
        "set": {
            "unit": "widget",
            "record": record,
        },
        "observe": {
            "writer": "agent",
            "unit": "widget",
            "record": {"kind": "value", "attr": "seen"},
        },
    }
    registry_path.write_text(json.dumps(declarations, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-tally.js").write_text(
        """import { keeps, once, widgetController } from "/runtime/widget-api.js";
export default class extends HTMLElement {
  #controller = widgetController(this);
  #stop;
  connectedCallback() { once(this); this.#stop ??= this.#controller.subscribe(() => {}); }
  disconnectedCallback() { this.#stop?.(); this.#stop = null; }
  renderState(state) {
    if (state.set.value === null) this.removeAttribute("count");
    else keeps(this, "count", state.set.value);
    if (state.observe.value === null) this.removeAttribute("seen");
    else keeps(this, "seen", state.observe.value);
  }
};
"""
    )
    url = serve(RELATIVE_WIDGET_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    for kind, author, widget, action, count in [
        ("action", "user", "tally-fitted", "set", "7"),
        ("report", "agent", "tally-fitted", "observe", "9"),
        ("action", "user", "tally-seen", "set", "5"),
    ]:
        append_command(
            serve.page_dir,
            {
                "kind": kind,
                "author": author,
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": {"value": count},
            },
        )

    page = open_page(browser, url)
    expect(page.locator("#tally-fitted")).to_have_attribute("count", "7")
    expect(page.locator("#tally-fitted")).to_have_attribute("seen", "9")
    expect(page.locator("#tally-seen")).to_have_attribute("count", "5")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "3")
    standing = page.evaluate(
        """async () => {
          const {state} = (await window.__lfRuntimeImport('/runtime/widget-api.js'))
            .widgetController(document.getElementById('tally-fitted')).read();
          return [state.set.value, state.observe.value];
        }"""
    )
    assert standing == ["7", "9"]

    original = page.locator("#tally-seen").element_handle()
    page.keyboard.press("z")
    round_trip(page)
    assert page.locator("#tally-seen").get_attribute("count") == "0"
    assert original.evaluate("node => node === document.getElementById('tally-seen')")


def test_a_part_and_its_own_widget_keep_same_named_verbs_independent(
    browser, serve, tmp_path, monkeypatch
):
    """Verbs are local to their owning widget contract. A container's `move` of part
    `piece` and that element's own `move` therefore coexist even though unit and verb
    text are identical; both owners reconcile."""
    monkeypatch.chdir(tmp_path)
    for tag, upgrade in (
        ("lf-owner", True),
        ("lf-zone", False),
        ("lf-piece", True),
    ):
        add_test_widget(tmp_path / ".leaf", tag, upgrade=upgrade)

    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    owner = declarations["lf-owner"]
    owner["x-content"] = "members"
    owner["x-state"] = {
        "move": {
            "unit": "unit",
            "record": {
                "kind": "position",
                "within": "lf-zone",
            },
        }
    }
    owner["x-example"] = (
        '<lf-owner id="sample-owner"><lf-zone id="sample-zone">'
        '<lf-piece id="sample-piece" pinned="no">Piece</lf-piece>'
        "</lf-zone></lf-owner>"
    )
    zone = declarations["lf-zone"]
    zone["x-owners"] = ["lf-owner"]
    zone["x-content"] = "members"
    zone.pop("x-example", None)
    piece = declarations["lf-piece"]
    piece["x-owners"] = ["lf-zone"]
    piece["properties"] |= {
        "pinned": {"type": "string"},
        "restated": {"type": "boolean"},
    }
    piece.setdefault("required", []).append("pinned")
    piece["x-state"] = {
        "move": {
            "unit": "widget",
            "record": {"kind": "value", "attr": "pinned"},
        }
    }
    piece.pop("x-example", None)
    registry_path.write_text(json.dumps(declarations, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-owner.js").write_text(
        """import { once, widgetController } from "/runtime/widget-api.js";
export default class extends HTMLElement {
  #controller = widgetController(this);
  #stop;
  connectedCallback() { once(this); this.#stop ??= this.#controller.subscribe(() => {}); }
  disconnectedCallback() { this.#stop?.(); this.#stop = null; }
  renderState(state) {
    for (const [id, order] of Object.entries(state.move.value)) {
      const zone = document.getElementById(id);
      for (const child of order) zone.append(document.getElementById(child));
    }
  }
};
"""
    )
    (tmp_path / ".leaf" / "widgets" / "lf-piece.js").write_text(
        """import { keeps, once, widgetController } from "/runtime/widget-api.js";
export default class extends HTMLElement {
  #controller = widgetController(this);
  #stop;
  connectedCallback() { once(this); this.#stop ??= this.#controller.subscribe(() => {}); }
  disconnectedCallback() { this.#stop?.(); this.#stop = null; }
  renderState(state) { keeps(this, "pinned", state.move.value); }
};
"""
    )
    html = leaf_page(
        "owned coordinates",
        """<h1>Owned coordinates</h1><lf-owner id="owner">
<lf-zone id="zone-a"><lf-piece id="piece" pinned="no">Piece</lf-piece></lf-zone>
<lf-zone id="zone-b"></lf-zone></lf-owner>""",
    )
    url = serve(html, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    for event in (
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "owner",
            "action": "move",
            "detail": {"unit": "piece", "value": "zone-b", "rank": "0i"},
        },
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "piece",
            "action": "move",
            "detail": {"value": "yes"},
        },
    ):
        append_command(serve.page_dir, event)

    page = open_page(browser, url)
    expect(page.locator("#zone-b > #piece")).to_have_count(1)
    expect(page.locator("#piece")).to_have_attribute("pinned", "yes")
    standing = page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          return ['owner', 'piece'].map(id => {
            const widget = document.getElementById(id);
            const {state} = widgetController(widget).read();
            return [id, (state.move.units?.piece ?? state.move).action];
          });
        }"""
    )
    assert standing == [["owner", "move"], ["piece", "move"]]
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "2")
    # A data renderer can remount a part while retaining its owner. Both owning
    # coordinates must render onto the new node even when no winning event changed.
    page.evaluate("""async () => {
      const {createWidgetElement} = await window.__lfRuntimeImport('/runtime/widget-api.js');
      const piece = createWidgetElement(document.getElementById('piece'), 'lf-piece', document.getElementById('piece').constructor);
      piece.id = 'piece';
      piece.setAttribute('pinned', 'no');
      document.getElementById('piece').replaceWith(piece);
      document.getElementById('zone-a').append(piece);
    }""")
    response = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "Check the refreshed piece",
        },
    )
    assert response.ok, response.text()
    told(page)
    expect(page.locator("#zone-b > #piece")).to_have_count(1)
    expect(page.locator("#piece")).to_have_attribute("pinned", "yes")


def test_a_page_at_rest_is_read_across_a_widgets_own_root(
    browser, serve, tmp_path, monkeypatch
):
    """Whether the page is still moving is asked of every tree the page is in.

    A document answers for its own tree alone: `document.getAnimations()` returns
    nothing for an element inside a widget's shadow root, and `{subtree: true}` on
    the root element returns nothing either. A widget drawing itself into place in
    there grows the host box the gate's own readings measure, so a reading that
    asked the document would call that page still and read it mid-move — the fault
    the wait exists to prevent, surviving inside the one place a widget is most
    likely to draw."""
    url = serve(
        drifting_widget(tmp_path, monkeypatch, deep=True),
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
    page = open_page(browser, url)
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")

    # The banner's dot pulses forever and is deliberately not the page moving, so the
    # control asks after a finite end rather than after an empty list.
    assert (
        page.evaluate(
            "() => document.getAnimations().filter(a => Number.isFinite("
            "  a.effect?.getComputedTiming().endTime)).length"
        )
        == 0
    ), "the document tree already answers for this one, so the reading proves nothing"
    # The mover is the widget's own box inside its root, and the reading names it
    # under the nearest element the author can address it by (`render-checks/locate.js`).
    assert render_checks_model.evaluate_probe(page, "moving") == [
        "<div> in <lf-drift id=drift-note>"
    ]


def test_a_module_that_stages_bare_text_is_refused_in_its_own_name(
    browser, serve, tmp_path, monkeypatch
):
    """The one text these walks reach with no element over it, and the page says whose.

    A widget may render the page's words into its own shadow root, and the passage walk
    crosses in after them. What it cannot take is a text node put straight on the root:
    `parentElement` is null there, so those words have no block to sit in, no cell to be
    fenced by and nothing for a mark to hang on, and admitting them would split the
    page's reading from the file's. The page refuses to present at all, which is the
    loud direction — but the refusal used to arrive as `Cannot read properties of null
    (reading 'closest')` over a blank page, naming neither the widget nor the mistake,
    which is a bug report against leaf rather than against the module that caused it.

    The refusal is also final. It used to be raised again by every later reader of the
    page's words: each repaint frame, key and selection threw it, so a wheel, a resize
    and three presses took one page from 6 errors to 25, while the notice waited for a
    server update that cannot fix a module's mistake. Now the first refusal declares
    the page failed: its widgets fall back at once, the notice says the page itself has
    a problem, and later readers read past the refused words, so the agent and the
    console hear it once."""
    url = serve(
        drifting_widget(tmp_path, monkeypatch, bare=True),
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
    page = browser.new_page(
        viewport=render_checks_model.RENDER_VIEWPORT, color_scheme="light"
    )
    # The first thing the page says in anger, whatever that turns out to be: waiting
    # for the wording under test would make a page that says something else read as a
    # page that says nothing, and the message is the whole subject here.
    with page.expect_console_message(lambda message: message.type == "error") as caught:
        page.goto(url, wait_until="commit")
    refusal = caught.value.text

    assert '<lf-drift id="drift-note">' in refusal, refusal
    assert "They came over the fence" in refusal, refusal
    assert "closest" not in refusal, (
        "the refusal is still a property name, which reads as leaf being broken: "
        + refusal
    )
    notice = page.get_by_role("status").filter(has_text="Leaf couldn't start")
    expect(notice).to_have_text(
        "Leaf couldn't start: this page has a problem its author needs to fix."
    )
    assert not page.evaluate(
        "() => document.documentElement.hasAttribute('data-lf-interactive')"
    ), "the page kept its widgets' upgraded boxes rather than its readable fallback"

    page.mouse.wheel(0, 300)
    page.set_viewport_size({"width": 900, "height": 700})
    page.keyboard.press("j")
    page.mouse.click(200, 200)
    page.keyboard.press("k")
    # A selection is read by the composing surface rather than a frame or a key, and
    # reads across the widget into the paragraphs after it.
    start = page.locator("#drift-title").bounding_box()
    end = page.locator("#drift-week").bounding_box()
    page.mouse.move(start["x"] + 2, start["y"] + start["height"] / 2)
    page.mouse.down()
    page.mouse.move(end["x"] + 40, end["y"] + end["height"] / 2, steps=5)
    page.mouse.up()
    page.locator("#drift-four").dblclick()
    rendered(page)
    assert page.evaluate("() => document.body.dataset.lfPresented") is None, (
        "the page presented anyway, so the words with nothing over them are in it"
    )
    errors = consume_browser_errors(page, '<lf-drift id="drift-note">')
    assert len(errors) == 1, errors
    reports = wait_for(
        lambda: [
            event["text"].splitlines()[0]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "error"
        ],
        bool,
        failure="the agent never heard the refusal",
    )
    assert reports == [said(errors[0]).removeprefix("leaf: ")], reports


def test_replay_signatures_exclude_settlement_and_other_runtime_paint(browser, serve):
    """A rendered settlement cannot become authored state through a DOM signature.

    The application snapshot owns the outcome; data-lf-state and the other runtime
    attributes only make that publication visible and must not replace a retained node.
    """
    url = serve(SUGGESTION_PAGE)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")

    signatures = page.evaluate("""async () => {
        const { shallowSigs } = await window.__lfRuntimeImport("/runtime/check-api.js");
        const widget = document.getElementById("sug-refill");
        const read = () => shallowSigs(document.body).get(widget.id);
        const decided = read();
        widget.setAttribute("data-lf-user-override", "probe");
        const painted = read();
        widget.setAttribute("data-lf-space", "wide");
        const marked = read();
        widget.removeAttribute("data-lf-state");
        const undecided = read();
        return { decided, painted, marked, undecided };
    }""")
    assert signatures["decided"] == signatures["painted"], (
        "runtime-owned pending paint became authored state in the replay signature"
    )
    assert signatures["decided"] == signatures["marked"], (
        "a declared mark's paint became authored state in the replay signature"
    )
    assert signatures["decided"] == signatures["undecided"], (
        "rendered settlement paint became authored state in the replay signature"
    )
    positions = page.evaluate("""async () => {
        const { shallowSigs } = await window.__lfRuntimeImport("/runtime/check-api.js");
        const root = document.createElement("div");
        root.id = "signature-root";
        root.innerHTML = '<i></i><div id="first"><b id="nested"></b></div>' +
            '<div class="lf-ui" id="runtime-control"></div>' +
            '<div class="lf-ui" id="runtime-parent">' +
                '<lf-options id="thread-widget"></lf-options></div>' +
            '<i></i><div id="second"></div>';
        const before = Object.fromEntries(shallowSigs(root));
        root.insertBefore(document.createElement("i"), root.firstElementChild);
        root.querySelector("#runtime-parent").id = "replacement-runtime-parent";
        root.querySelector("#runtime-control").replaceWith(
            Object.assign(document.createElement("div"), {
                className: "lf-ui",
                id: "replacement-runtime-control",
            }),
        );
        const painted = Object.fromEntries(shallowSigs(root));
        root.prepend(root.lastElementChild);
        const moved = Object.fromEntries(shallowSigs(root));
        return { before, painted, moved };
    }""")
    assert positions["before"] == positions["painted"]
    assert set(positions["before"]) == {
        "signature-root",
        "first",
        "nested",
        "thread-widget",
        "second",
    }
    assert {
        identity
        for identity, signature in positions["before"].items()
        if positions["moved"][identity] != signature
    } == {"first", "second"}
    assert json.loads(positions["before"]["nested"])["parent"] == "first"
    assert json.loads(positions["before"]["thread-widget"])["parent"] == ""


def test_a_pending_suggestion_can_be_discussed_instead_of_decided(browser, serve):
    """✓ and ✗ are the visible affordances, but a proposal a user half-agrees
    with wants a sentence, not a verdict: the proposed words are ordinary page
    text, so selecting them and commenting works like anywhere else. Then the
    decision they eventually take has to reach the thread — rejecting retires the
    text the comment was made on, and a comment pointing into markup nobody can
    see has to read as detached rather than as a live mark that jumps nowhere."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    resized(page, 1920, 900)
    page.evaluate("""() => {
        const range = document.createRange();
        range.selectNodeContents(document.querySelector('#sug-refill lf-new'));
        getSelection().removeAllRanges();
        getSelection().addRange(range);
    }""")
    page.keyboard.press("c")
    page.wait_for_selector(".lf-fab-input", state="visible")
    page.locator(".lf-fab-input").click()
    page.wait_for_selector(".lf-composer", state="visible")
    quoted = composer_quote(page)["text"]
    assert quoted.strip("“”") == "Refill a feeder when its camera shows it half-empty."
    write(page.locator(".lf-composer leaf-text"), "Half-empty by whose reading?")
    page.keyboard.press("ControlOrMeta+Enter")

    inline = page.locator(".lf-margin-thread")
    expect(inline.locator(".lf-msg-body")).to_have_text("Half-empty by whose reading?")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).to_be_visible()
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    assert (
        painted(page, "lf-mark")
        == "Refill a feeder when its camera shows it half-empty."
    )

    unfolded_button(
        suggestion_control(page, "sug-refill", "reject", visible=False)
    ).click()
    expect(thread).to_have_class(re.compile(r"\bdetached\b"))
    assert painted(page, "lf-mark") == "", (
        "a mark stayed painted on text the user's own decision removed"
    )


def test_a_decision_already_in_the_log_retires_its_slot_at_load(browser, serve):
    """The test above takes the decision in front of the user, on a page that has
    been up long enough for everything to have arrived. Here the log holds it before
    the page opens, which is what puts the anchor pass's skip list on the clock: the
    registry names the slot a decision retires (x-retired-when), and the registry
    arrives over the network, after the module that reads it has evaluated. Replay
    settles the suggestion on the first poll, so the pass that runs with it has to be
    skipping lf-old already — or the page opens with a live mark on words the user
    accepted away."""
    url = serve(
        SUGGESTION_PAGE, anchored=[("replace", "Refill every feeder each morning.")]
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator(".lf-thread .lf-quote").first).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "the first pass anchored inside a slot the user's decision had retired"
    )


def test_a_slot_naming_two_holders_retires_under_neither_until_decided(
    browser, serve, tmp_path, monkeypatch
):
    """`x-owners` is a list, and the retired-slot selector is built from it. Written
    `${entry["x-owners"]}` the list interpolates comma-joined, so a slot naming two
    owners wrote a selector *list* whose first member was the bare owner tag: every
    instance of it read as a retired slot however the log stood, its words silenced
    from the anchor pass, while the pair that was meant matched nothing at all.

    Unreachable until this layer's licensing opened `x-retired-when` past the
    suggestion family, which is why the shipped vocabulary — every slot of it naming
    one holder — could never have said so. The page holds an undecided trial, so
    nothing here is retired and a quote inside it must anchor like any other."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)

    url = serve(
        TWO_HOLDER_PAGE,
        anchored=[("th-now", "warmed on every deploy")],
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
    page = open_page(browser, url)
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()
    expect(page.locator(".lf-thread .lf-quote").first).not_to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") != "", (
        "the quote found nothing to paint: an undecided holder read as a retired slot, "
        "so the anchor pass skipped every word inside it"
    )


def test_a_settled_holder_in_a_reply_joins_the_panel_wearing_its_mark(
    browser, serve, tmp_path, monkeypatch
):
    """The same mark on a holder an agent sent in a reply. Its markup is frozen and
    the thread mounts it after the projection has painted the page, so a paint that
    looks the holder up in the document finds nothing and the reply opens with both
    slots showing. The holder's node exists before either pass, so the mark is on it
    when the thread places it."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    url = serve(REPLY_HOST_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-trial",
            "author": "agent",
            "revision": 1,
            "text": "Should the cache warm lazily?",
            "markup": (
                '<lf-trial id="rq-cache">'
                '<lf-current><p id="rq-now">Warm on deploy.</p></lf-current>'
                '<lf-proposed><p id="rq-next">Warm on first request.</p></lf-proposed>'
                "</lf-trial>"
            ),
        },
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "rq-cache",
            "action": "decide",
            "detail": {"outcome": "shelve"},
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    expect(page.locator("#rq-now")).to_be_visible()
    expect(page.locator("#rq-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#rq-next")).to_be_hidden()


@pytest.mark.parametrize("shadow", [False, True])
def test_withdrawing_a_custom_settlement_clears_the_layers_mark(
    browser, serve, tmp_path, monkeypatch, shadow
):
    """A custom deciding payload can drive a widget's presentation alongside the
    layer's retirement. Undo clears both its presentation and the retired slot."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    holder = declarations["lf-trial"]
    if shadow:
        holder["x-shadow"] = True
    holder["properties"]["decision"] = {"enum": ["open", "shelved"]}
    holder.setdefault("required", []).append("decision")
    holder["x-example"] = holder["x-example"].replace(
        'id="trial-cache"', 'id="trial-cache" decision="open"'
    )
    decide = holder["x-state"]["decide"]
    decide["detail"]["properties"]["decision"] = {"enum": ["open", "shelved"]}
    decide["detail"]["required"].append("decision")
    registry_path.write_text(json.dumps(declarations))
    stage = (
        "if (once(this)) shadowStage(this, [...this.children]);"
        if shadow
        else "once(this);"
    )
    if shadow:
        (tmp_path / ".leaf" / "shadow.css").write_text(
            "lf-current, lf-proposed { display: block; }"
        )
    (tmp_path / ".leaf" / "widgets" / "lf-trial.js").write_text(
        """import { keeps, once, shadowStage, widgetController } from "/runtime/widget-api.js";
export default class extends HTMLElement {
  #controller = widgetController(this);
  #stop;
  connectedCallback() { STAGE this.#stop ??= this.#controller.subscribe(() => {}); }
  disconnectedCallback() { this.#stop?.(); this.#stop = null; }
  renderState(state) { keeps(this, "decision", state.decide.detail.decision ?? "open"); }
};
""".replace("STAGE", stage)
    )
    page_html = TWO_HOLDER_PAGE.replace(
        '<lf-trial id="th-cache">', '<lf-trial id="th-cache" decision="open">'
    )
    url = serve(page_html, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    decision = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "decide",
            "detail": {"outcome": "shelve", "decision": "shelved"},
        },
    )
    page = open_page(browser, url)
    assert page.locator("#th-cache").evaluate("el => Boolean(el.shadowRoot)") is shadow
    expect(page.locator("#th-cache")).to_have_attribute("decision", "shelved")
    expect(page.locator("#th-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#th-cache lf-proposed")).to_have_attribute(
        "data-lf-retired", ""
    )
    expect(page.locator("#th-cache lf-proposed")).to_be_hidden()

    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": decision["id"]},
    )
    told(page)
    expect(page.locator("#th-cache")).to_have_attribute("decision", "open")
    expect(page.locator("#th-cache")).not_to_have_attribute(
        "data-lf-state", re.compile(r".+")
    )
    expect(page.locator("#th-cache lf-proposed")).not_to_have_attribute(
        "data-lf-retired", ""
    )
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()


def test_a_throwing_settlement_still_reaches_the_layers_terminal_state(
    browser, serve, tmp_path, monkeypatch
):
    """A module failure is terminal rather than an endless replay retry, and the
    layer's generic settlement contract still applies: readiness, the holder mark,
    and the visible fail-soft box must agree on that one consumed action."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    (tmp_path / ".leaf" / "widgets" / "lf-trial.js").write_text(
        """import {widgetController} from "/runtime/widget-api.js";
export default class extends HTMLElement {
  #controller = widgetController(this);
  #stop;
  connectedCallback() { this.#stop ??= this.#controller.subscribe(() => {}); }
  disconnectedCallback() { this.#stop?.(); this.#stop = null; }
  renderState() { throw new Error("trial replay broke"); }
};
"""
    )
    url = serve(TWO_HOLDER_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "decide",
            "detail": {"outcome": "shelve"},
        },
    )

    page = open_page(browser, url)
    expect(page.locator("#th-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#th-cache .lf-error")).to_contain_text("trial replay broke")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "1")
    consume_browser_errors(page, "<lf-trial> renderState threw: trial replay broke")


def test_a_label_in_a_retired_slot_leaves_the_page_with_the_slot(browser, serve):
    """A decided suggestion's losing slot is off the page, and a label inside it goes
    too. The label is the one thing that reads back over chrome — a settled group's
    summary says "Settled: …" and declares those words the page's, which is what lets a
    user point at it anywhere else — so the rule has to stop at the slot: a marker that
    outranks a look must not outrank a decision, or a quote lands in the half the user
    removed."""
    url = serve(RETIRED_WIDGET_PAGE, anchored=[("sug-swap", "Settled: Lax cookie")])
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-swap",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#sug-swap lf-old")).to_be_hidden()
    assert (
        page.locator("#old-group .lf-settled [data-lf-said]").evaluate(
            "el => el.textContent"
        )
        == "Settled: Lax cookie"
    ), "fixture is not exercising the case — the label the slot hides never rendered"
    expect(page.locator(".lf-thread .lf-quote").first).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "a quote matched inside the half the user accepted away, because the "
        "label there declared itself the page speaking"
    )


def test_a_decision_that_empties_its_widget_detaches_the_element_anchor(browser, serve):
    """An element anchor asks whether its section is still on the user's page,
    and for a suggestion that settles to nothing — an insertion refused — the
    markup's presence is the wrong answer: the thread read as attached while its
    outline drew nothing. Pending, the wrapper is a thing to point at; refused, the
    thread detaches like any passage the decision removed."""
    url = serve(SUGGESTION_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Is thistle worth a feeder?",
            "anchor": {"section": "sug-thistle"},
        },
    )
    page = open_page(browser, url)
    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    # Pending, the outline hangs on a box the user can see, and it is read as a box
    # rather than as a class: the class sat on the wrapper while the wrapper was
    # display: contents and painted no outline, so the half of this docstring about
    # drawing nothing was true of the attached case too. The wrapper draws its own box
    # now, so the mark is the wrapper itself rather than the slot it showed through.
    shown = page.locator("#sug-thistle.lf-mark-el")
    expect(shown).to_have_count(1)
    box = shown.evaluate("el => el.getBoundingClientRect().toJSON()")
    assert box["width"] > 0 and box["height"] > 0, (
        f"the attached thread's outline hangs on a box of no size: {box}"
    )

    unfolded_button(
        suggestion_control(page, "sug-thistle", "reject", visible=False)
    ).click()
    expect(thread).to_have_class(re.compile(r"\bdetached\b"))
    expect(page.locator("#sug-thistle.lf-mark-el")).to_have_count(0)


def test_a_reply_renders_the_markdown_it_was_written_in(browser, serve):
    """A message's text is Markdown, rendered here by the page's own vendored layer —
    the wire carries the log's words and nothing else. Every raw tag renders as the
    characters it was written in, a block of tags as much as prose saying Vec<T>, and
    swallowing it into an element would lose the words in front of the user with nothing saying so. What the
    panel adds is the page's own dress: the theme's element rules are at document level
    and reach in, a fenced block colors from the tokenizer a version's <pre><code>
    uses, and a bare URL arrives as the link the user will want to follow."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "which one wins?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-decision",
            "revision": 1,
            "text": MARKDOWN_REPLY,
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    body = page.locator(".lf-msg.agent .lf-msg-body")
    expect(body.locator("li")).to_have_count(2)
    expect(body.locator("strong")).to_have_text("behind")
    expect(body.locator("blockquote")).to_have_text("which one wins?")
    expect(body.locator("pre code [data-lf-syn]").first).to_have_text("def")
    # Tags are text in this dialect, a block of them as much as one in a sentence, so
    # markup shown without a fence keeps the lines it was written in.
    markup = body.locator("p", has_text="<lf-callout>")
    assert markup.inner_text() == "<lf-callout>\n<div>a tile</div>\n</lf-callout>"
    link = body.locator('a[href="https://example.com/notes"]')
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", re.compile(r"(?:^| )noopener(?: |$)"))
    expect(link.locator(":scope > svg.lf-external-mark")).to_be_visible()
    expect(
        body.locator(
            'a[href^="javascript:"], a[href^="data:"], '
            'a[href^="file:"], a[href^="editor:"]'
        )
    ).to_have_count(0)
    expect(body).to_contain_text(
        "Unsafe destinations stay words: script, inline data, local file, "
        "and custom handler."
    )
    # The paragraph's asterisks are gone from the words, not merely hidden, and the
    # raw tag's characters are still among them: what the user can select is what
    # the message says.
    text = body.inner_text()
    assert "**" not in text and "Vec<T>" in text


def test_an_arrival_keeps_a_readable_native_fragment_where_the_browser_landed_it(
    browser, serve
):
    """Startup does not centre a static fragment that is already wholly readable."""
    url = serve(
        leaf_page(
            "native fragment arrival",
            """
<h1>Native fragment arrival</h1>
<div style="height: 900px"></div>
<section id="arrival"><h2>Arrival</h2><p>The whole destination is visible.</p></section>
<div style="height: 900px"></div>
""",
        )
    )
    page = open_page(browser, f"{url}#arrival")
    arrival = page.locator("#arrival")
    position = arrival.evaluate(
        """element => ({
          top: element.getBoundingClientRect().top,
          clear: parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop),
        })"""
    )
    assert abs(position["top"] - position["clear"]) < 2, position


def test_a_suggestion_shows_the_characters_it_proposes(browser, serve):
    """A suggestion's words are bound for the page verbatim, so the panel shows them
    as typed. Rendering them would promise the user an italic where the next
    version carries the asterisks they wrote."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "s1",
            "author": "user",
            "revision": 1,
            "suggestion": True,
            "text": "Retry up to *five* times.",
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    body = page.locator(".lf-msg-body.lf-suggest-body")
    expect(body).to_have_text("Retry up to *five* times.")
    expect(body.locator("em")).to_have_count(0)


@pytest.mark.parametrize("asynchronous", [False, True], ids=["draft", "async-body"])
def test_thread_body_initial_state_comes_from_source_before_upgrade(
    browser, serve, asynchronous
):
    """Frozen widgets undo to source even when presentation rewrites its body."""
    tag = "lf-delayed-body" if asynchronous else "lf-draft"
    layer = {}
    if asynchronous:
        layer = {
            "layer_registry": {
                tag: {
                    "description": "A body normalized by an asynchronous renderer.",
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "restated": {"type": "boolean"},
                    },
                    "required": ["id"],
                    "additionalProperties": False,
                    "x-content": "data",
                    "x-upgrade": True,
                    "x-verbatim": True,
                    "x-state": {
                        "edit": {
                            "unit": "widget",
                            "record": {"kind": "body"},
                        }
                    },
                    "x-example": '<lf-delayed-body id="example"><pre>Text</pre></lf-delayed-body>',
                },
            },
            "layer_widgets": {
                f"{tag}.js": """
import {once, widgetController, keepsText} from '/runtime/widget-api.js';
export default class extends HTMLElement {
  #controller = widgetController(this);
  #stop;
  connectedCallback() {
    if (once(this)) {
      this.#controller.present(new Promise(resolve => requestAnimationFrame(() => {
        this.querySelector('pre').textContent = 'Presentation-only rewrite.';
        resolve();
      })));
    }
    this.#stop ??= this.#controller.subscribe(() => {});
  }
  disconnectedCallback() { this.#stop?.(); this.#stop = null; }
  renderState(state) { keepsText(this.querySelector('pre'), state.edit.value); }
};
"""
            },
        }
    url = serve(REPLY_HOST_PAGE, **layer)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "body-question",
            "author": "user",
            "revision": 1,
            "text": "Please draft it.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "body-question",
            "text": "Edit these words.",
            "markup": f'<{tag} id="reply-body"><pre>\n    First line.\n    Second line.\n</pre></{tag}>',
        },
    )
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    widget = page.locator("#reply-body")
    original = widget.element_handle()
    body = widget.locator("pre" if asynchronous else ".lf-draft-body")
    expect(body).to_have_text(
        "Presentation-only rewrite." if asynchronous else "First line. Second line."
    )
    response = post_event(
        page,
        live_url(url).split("?")[0] + "api/event",
        data={
            "kind": "action",
            "widget": "reply-body",
            "action": "edit",
            "detail": {"value": "User's exact words.\n"},
            "revision": 1,
        },
    )
    assert response.ok, response.text()
    told(page)
    assert body.text_content() == "User's exact words.\n"
    undo(page)
    expect(body).to_have_text("First line. Second line.")
    if asynchronous:
        assert body.text_content() == "    First line.\n    Second line.\n"
    else:
        expect(body).to_have_attribute(
            "data-lf-source-words", "    First line.\n    Second line.\n"
        )
    assert original.evaluate("node => node === document.getElementById('reply-body')")


def test_live_revision_drafts_wait_for_the_complete_controller_publication(
    browser, serve
):
    """Replacement drafts recover only after the arriving document is complete."""
    first = leaf_page(
        "Drafts first",
        """<h1>Drafts</h1>
<lf-draft id="revised-draft"><pre>
    The first revision's existing body.
</pre></lf-draft>""",
    )
    second = leaf_page(
        "Drafts second",
        """<h1>Drafts</h1>
<lf-draft id="revised-draft"><pre>
    The second revision's replacement body.
</pre></lf-draft>
<lf-draft id="arriving-draft"><pre>
    The second revision's newly inserted body.
</pre></lf-draft>""",
    )
    page = open_page(browser, live_url(serve(first)))
    revised = page.locator("#revised-draft")
    expect(revised.locator(".lf-draft-body")).to_have_text(
        "The first revision's existing body."
    )
    revised.locator(".lf-draft-body").click()
    editor = revised.get_by_role("textbox", name="Edit revised-draft")
    write(editor, "The user's unsent replacement.\n")
    # The user leaves the editor open and steps back to the page.
    page.locator("h1").click()
    expect(editor).not_to_be_focused()
    assert take_browser_errors(page) == []

    stamp_page(serve.page_dir, second, "replace and insert drafts")
    wait_for_revision(page, 2)

    expect(revised.locator(".lf-draft-body")).to_have_text(
        "The second revision's replacement body."
    )
    expect(page.locator("#arriving-draft .lf-draft-body")).to_have_text(
        "The second revision's newly inserted body."
    )
    expect(
        revised.get_by_role("textbox", name="Edit revised-draft")
    ).to_have_js_property("value", "The user's unsent replacement.\n")
    assert take_browser_errors(page) == []


def test_crossed_responses_wait_for_the_same_frozen_widget_module(browser, serve):
    """A later POST must join the reply's import before mounting or capturing it."""
    host = REPLY_HOST_PAGE.replace(
        "</main>",
        """
<lf-ask id="delivery"><h2>Which delivery?</h2>
  <lf-options id="delivery-choice" choose>
    <lf-option id="delivery-now">Now</lf-option>
    <lf-option id="delivery-later">Later</lf-option>
  </lf-options>
</lf-ask></main>""",
    )
    url = serve(host)
    page = open_page(browser, live_url(url))
    held = []
    page.route("**/widgets/lf-draft.js", lambda route: held.append(route))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "draft-question",
            "author": "user",
            "revision": 1,
            "text": "Please draft this.",
        },
    )
    with page.expect_request("**/widgets/lf-draft.js"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "parent": "draft-question",
                "author": "agent",
                "revision": 1,
                "text": "Edit this draft.",
                "markup": '<lf-draft id="crossed-draft"><pre>\n    First line.\n    Second line.\n</pre></lf-draft>',
            },
        )
    holding(page, held, 1, "the frozen draft module")
    assert len(held) == 1
    frozen_reading = """async () => {
      const {readApplication} = await window.__lfRuntimeImport(
        '/runtime/semantic-state.js');
      const root = readApplication();
      return {
        descriptor: root.document.descriptors.has('crossed-draft'),
        authored: root.document.authored.has('crossed-draft'),
        body: root.effective.widgets.get('crossed-draft')?.state.edit?.value ?? null,
        mounted: Boolean(document.getElementById('crossed-draft')),
      };
    }"""
    assert page.evaluate(frozen_reading) == {
        "descriptor": False,
        "authored": False,
        "body": None,
        "mounted": False,
    }
    with page.expect_response("**/api/event") as newer:
        page.locator("#delivery-now").click()
    assert newer.value.ok
    newer.value.finished()
    one_frame(page)
    assert page.locator("#crossed-draft").count() == 0
    held[0].continue_()
    page.unroute("**/widgets/lf-draft.js")
    told(page)
    assert page.evaluate(frozen_reading) == {
        "descriptor": True,
        "authored": True,
        "body": "    First line.\n    Second line.\n",
        "mounted": True,
    }
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    widget = page.locator("#crossed-draft")
    original = widget.element_handle()
    body = widget.locator(".lf-draft-body")
    expect(body).to_have_text("First line. Second line.")
    expect(body).to_have_attribute(
        "data-lf-source-words", "    First line.\n    Second line.\n"
    )
    widget.locator(".lf-draft-body").click()
    write(widget.locator("leaf-text"), "A user's exact words.\n")
    draft_control(page, "save", "crossed-draft").click()
    round_trip(page)
    assert body.text_content() == "A user's exact words.\n"
    undo(page)
    expect(body).to_have_text("First line. Second line.")
    expect(body).to_have_attribute(
        "data-lf-source-words", "    First line.\n    Second line.\n"
    )
    assert original.evaluate(
        "node => node === document.getElementById('crossed-draft')"
    )
    expect(page.locator("#delivery-now")).to_have_attribute("chosen", "")


def test_a_reply_widget_replays_and_withdraws_its_action(browser, serve):
    """A widget inside a reply exists only once the panel has rendered the log,
    which is later than everything on the page — so the replay runs at the end of
    a poll, after that render, and an action naming a widget it doesn't find is
    one no version will ever hold (an honored suggestion, whose id the honoring
    version dropped) rather than one to look for again on the next poll. Its authored
    record is captured from frozen source before the reply is admitted, so withdrawing
    the action restores that baseline without authored version markup for the chrome
    widget."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "Which of these?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-decision",
            "revision": 1,
            "text": SAMPLE_TEXT,
            "markup": SAMPLE_MARKUP,
        },
    )
    decision = append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "rp-live",
            "action": "choose",
            "detail": {"value": ["rp-shim"]},
        },
    )
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    expect(page.locator("#rp-shim")).to_have_attribute("chosen", "")
    assert page.locator("#rp-live lf-option[chosen]").count() == 1

    # Chrome belongs to the thread rather than the page version. Its action therefore
    # still stands, and is still the user's newest undoable gesture, after the page
    # advances around the thread.
    stamp_page(d, REPLY_HOST_PAGE, "v2")
    wait_for_revision(page, 2)
    if not page.locator(".lf-thread-panel").is_visible():
        page.locator(".lf-threads-toggle").click()
    expect(page.locator("#rp-shim")).to_have_attribute("chosen", "")

    undo(page)
    assert [
        event["undoes"]
        for event in events_model.read_events(d)
        if event["kind"] == "undo"
    ] == [decision["id"]]
    expect(page.locator("#rp-live lf-option[chosen]")).to_have_count(0)


def test_z_takes_back_a_decision_carried_into_a_later_revision(browser, serve):
    """A decision the next revision keeps standing is still the user's newest gesture
    there, so `z` takes it back as the widget's own Undo would."""
    first = leaf_page(
        "Carried decision",
        """<h1>Plan</h1>
<lf-ask id="cz-ask"><h2>Which comes first?</h2>
  <lf-options id="cz-options" choose>
    <lf-option id="cz-flag">Flag</lf-option>
    <lf-option id="cz-backfill">Backfill</lf-option>
  </lf-options>
</lf-ask>""",
    )
    page = open_page(browser, live_url(serve(first)))
    page.locator("#cz-flag .lf-pick").click()
    round_trip(page)
    expect(page.locator("#cz-flag")).to_have_attribute("chosen", "")

    stamp_page(
        serve.page_dir,
        first.replace("<h1>Plan</h1>", "<h1>Plan</h1><p>Context added.</p>"),
        "add context",
    )
    wait_for_revision(page, 2)
    expect(page.locator("#cz-flag")).to_have_attribute("chosen", "")

    undo(page)
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    expect(page.locator("#cz-options lf-option[chosen]")).to_have_count(0)


def _gesture_request(request):
    return "/api/event" in request.url and bool(request.post_data_json.get("attempt"))


def _hold_gesture(route, held):
    if _gesture_request(route.request):
        held.append(route)
    else:
        route.continue_()


def test_a_thread_answer_is_not_repainted_after_its_undo_arrives_with_it(
    browser, serve
):
    """The Done press paints only from replay. If one read first reveals both the
    answer and its undo, the send continuation must not overwrite that authoritative
    authored state after replay has accounted for the action."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(serve.page_dir, THREAD_ASKS[1])
    page = open_page(browser, url)
    page.keyboard.press("q")
    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    done = page.locator("#tq-set .lf-done")
    with page.expect_request(_gesture_request):
        done.click()
    holding(page, held, 1, "the thread answer")
    accepted_answer = held[0].fetch()
    attempt = held[0].request.post_data_json["attempt"]
    accepted = next(
        event
        for event in accepted_answer.json()["state"]["events"]
        if event.get("attempt") == attempt
    )
    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": accepted["id"]},
    )

    told(page)
    page.route("**/api/state*", refuse)
    expect(done).not_to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "false")
    assert [
        (event["widget"], event["action"]) for event in actions(serve.page_dir)
    ] == [("tq-set", "answer")]
    held[0].fulfill(response=accepted_answer)
    page.unroute("**/api/event")


def test_a_refused_thread_choice_replays_recorded_and_recordless_history(
    browser, serve
):
    """Thread widgets arrive after page startup, but their comment markup is still
    their authored baseline: a definitive refusal with no history removes the
    optimistic choice from that baseline instead of leaving a decision the log never
    took. A recordless accepted action then belongs to the widget's history too.
    Reconstructing after a later refusal must replay both the recorded selection and
    the separate `answer` verb, retaining both visible facts."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(serve.page_dir, THREAD_ASKS[1])
    page = open_page(browser, url)
    page.keyboard.press("q")
    expect(page.locator(".lf-thread-panel")).to_be_visible()

    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    with page.expect_request(_gesture_request):
        page.locator("#tq-logs").click()
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator("#tq-logs")).not_to_have_attribute("chosen", "")
    assert actions(serve.page_dir) == []
    consume_browser_errors(page, {"code": "failed-load", "status": 400})
    page.unroute("**/api/event")

    page.locator("#tq-logs").click()
    round_trip(page)
    page.locator("#tq-set .lf-done").click()
    round_trip(page)
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")

    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    with page.expect_request(_gesture_request):
        page.locator("#tq-metrics").click()
    expect(page.locator("#tq-metrics")).to_have_attribute("chosen", "")
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(page.locator("#tq-metrics")).not_to_have_attribute("chosen", "")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    assert [
        (event["action"], event["detail"]) for event in actions(serve.page_dir)
    ] == [
        ("choose", {"value": ["tq-logs"]}),
        ("answer", {}),
    ]
    consume_browser_errors(page, {"code": "failed-load", "status": 400})


def test_refusal_restores_queued_recordless_thread_actions_in_order(browser, serve):
    """A queued recordless action paints immediately and each refusal removes only
    the local outcome belonging to that attempt."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(serve.page_dir, THREAD_ASKS[1])
    page = open_page(browser, url)
    page.keyboard.press("q")
    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    with page.expect_request(_gesture_request):
        page.locator("#tq-logs").click()
    done = page.locator("#tq-set .lf-done")
    done.click()
    expect(done).to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "true")

    first_attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            _gesture_request(request)
            and request.post_data_json.get("attempt") != first_attempt
        )
    ):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": first_attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#tq-logs")).not_to_have_attribute("chosen", "")
    expect(done).to_have_attribute("aria-pressed", "true")
    second_attempt = held[1].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[1].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": second_attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(done).not_to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "false")
    assert actions(serve.page_dir) == []
    consume_browser_errors(page, {"code": "failed-load", "status": 400})


def test_a_done_press_answers_optimistically_and_only_once(browser, serve):
    """Done paints its semantic result while delivery is held, and repeated presses
    still produce one action."""
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_ASKS:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    page.keyboard.press("q")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    page.keyboard.press("q")
    expect(page.locator("#tq-set-decision")).to_be_focused()
    done = page.locator("#tq-set .lf-done")
    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    done.click()
    holding(page, held, 1, "the answer")

    expect(done).to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "true")
    done.click()
    done.click()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(done).to_have_attribute("aria-pressed", "true")
    expect(done).not_to_have_attribute("aria-busy", "true")
    assert [
        (e["widget"], e["action"])
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [("tq-set", "answer")]


def test_closing_a_thread_withdraws_the_ask_in_it(browser, serve):
    """A question in a thread is the thread's, so closing the thread takes the decision
    with it. The group is still there to read in the Resolved state, and still holds no
    answer — what went is the page's claim on the user, who would otherwise carry a
    standing decision for the life of the page and have `d` step them into a closed
    hidden thread to reach it."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(serve.page_dir, THREAD_ASKS[0])
    page = open_page(browser, url)
    expect_asks_answered(page, "0/1")

    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "agent", "parent": "c-which"}
    )
    told(page)
    expect(page.locator(".lf-queue")).to_have_text("Questions: 0")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    expect(page.locator(".lf-thread:not([hidden]) #tq-one")).to_have_count(1)
    expect(page.locator("#tq-redis")).not_to_have_attribute("chosen", "")


def test_worktree_identity_does_not_follow_the_missing_evidence_placeholder(
    browser, serve
):
    source = leaf_page(
        "worktree identity",
        '<lf-test-roster id="team"><lf-test-worker id="worker" state="working">'
        '<strong>Worker</strong><lf-test-tree id="proof" source="atlas-worktrees">'
        "</lf-test-tree></lf-test-worker></lf-test-roster>",
    )
    url = serve(source)
    record = {
        "branch": "proof",
        "base": "main",
        "head": "abc123",
        "ahead": 1,
        "behind": 0,
        "additions": 3,
        "deletions": 1,
        "commits": 1,
        "tests": "passing",
        "observedAt": "2026-09-25T10:00:00-07:00",
    }
    data_model.cmd_data_set(serve.page_dir, "atlas-worktrees", {"proof": record})
    page = open_page(browser, url)
    datum = page.locator('#proof > [data-lf-datum="proof"]')
    seen = source_revision(serve.page_dir, "atlas-worktrees")
    anchor = {
        "section": "proof",
        "datum": "proof",
        "source": "atlas-worktrees",
        "source_revision": seen,
        "identity": "proof",
    }

    def status():
        return page.evaluate(
            """anchor => window.__lfRuntimeImport('/runtime/anchor-resolution.js')
              .then(({resolveAnchor}) => resolveAnchor(anchor)?.status)""",
            anchor,
        )

    expect(datum).to_have_attribute("data-lf-identity", "proof")
    assert status() == "exact"
    data_model.cmd_data_set(serve.page_dir, "atlas-worktrees", {})
    expect(datum).not_to_have_attribute("data-lf-identity")
    assert status() == "outdated"
    data_model.cmd_data_set(
        serve.page_dir, "atlas-worktrees", {"proof": {**record, "head": "def456"}}
    )
    expect(datum).to_have_attribute("data-lf-identity", "proof")
    assert status() == "exact"


def test_native_worktree_disclosure_owns_keyboard_and_touch(browser, serve):
    source = leaf_page(
        "native evidence",
        '<lf-test-roster id="team"><lf-test-worker id="worker" state="working"><strong>Worker</strong><lf-test-tree id="proof" source="facts"></lf-test-tree></lf-test-worker></lf-test-roster>',
    )
    page = open_page(browser, serve(source))
    summary = page.locator("#proof summary")
    summary.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#proof details")).to_have_attribute("open", "")
    page.keyboard.press(" ")
    expect(page.locator("#proof details")).not_to_have_attribute("open")
    summary.click()
    expect(page.locator("#proof details")).to_have_attribute("open", "")


def test_command_goal_can_pause_after_an_ordinary_thread_started(browser, serve):
    """A normal note does not consume the goal's stronger pause door. The user
    can start a later held thread, whose root remains the one atomic hold fact."""
    page = open_page(browser, serve(COMMAND_HUB_EXAMPLE))
    d = serve.page_dir
    goal = page.locator("#goal-parser")
    seat = goal.locator(":scope > .lf-thread-seat")
    first = seat.locator(":scope > .lf-say")
    write(first.get_by_role("textbox"), "Keep parsing; this is only a note.")
    with sending(page, "the note"):
        first.get_by_role("button", name="Send", exact=True).click()

    expect(first).to_be_visible()
    write(first.get_by_role("textbox"), "Finish the hunk, then park.")
    with sending(page, "the held send"):
        first.get_by_role("button", name="Send & pause", exact=True).click()

    expect(goal).to_have_attribute("data-lf-held")
    roots = [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]
    assert [(event["text"], event.get("holds")) for event in roots] == [
        ("Keep parsing; this is only a note.", None),
        ("Finish the hunk, then park.", "goal-parser"),
    ]


def test_command_goal_thread_follows_its_declaration_not_talk(
    browser, serve, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    registry = json.loads((COMMAND_HUB_PACKAGE / "registry.json").read_text())
    task = registry["lf-test-task"]
    task["properties"]["consult"] = {"type": "boolean"}
    task["x-thread-seat"] = {
        "when": {"consult": [True]},
        "hold": "pause",
    }
    command = leaf_page(
        "custom goal",
        """<lf-test-plan id="hub">
  <lf-test-task id="goal" status="active" consult><strong>Custom goal</strong></lf-test-task>
</lf-test-plan>""",
    )
    url = serve(command, layer_registry={"lf-test-task": task})
    page = open_page(browser, url)
    seat = page.locator("#goal > .lf-thread-seat")
    expect(seat.get_by_role("textbox", name="Say something here")).to_be_visible()
    expect(seat.get_by_role("button", name="pause", exact=True)).to_be_visible()


@pytest.mark.parametrize(
    ("markup", "path", "leaf_id"),
    [
        (
            COMMAND_HUB_PAGE,
            [
                "One clean shadow week",
                "Replace the XML parser",
                "Declarations and entities",
                "CDATA edge cases",
            ],
            "parser-cdata",
        ),
        (
            REPORT_PAGE,
            ["Tasks", "Rebuild the feeders", "Fit squirrel baffles"],
            "t-parser",
        ),
    ],
)
def test_task_hierarchy_is_accessible_through_reports_and_revisions(
    browser, serve, markup, path, leaf_id
):
    """The listening reader gets the same parents as the visible task nesting.

    Read Chrome's native accessibility tree: Playwright's DOM-based name calculator
    does not yet read ariaLabelledByElements, although Chrome exposes those names to
    assistive technology. A report repaints row metadata; a revision changes titles.
    Neither may flatten the groups or retain the previous title as their name.
    """
    page = open_page(
        browser,
        live_url(serve(COMMAND_HUB_EXAMPLE if markup == COMMAND_HUB_PAGE else markup)),
    )
    session = page.context.new_cdp_session(page)

    def hierarchy(expected):
        nodes = session.send("Accessibility.getFullAXTree")["nodes"]
        by_id = {node["nodeId"]: node for node in nodes}
        groups = {
            node.get("name", {}).get("value"): node
            for node in nodes
            if node.get("role", {}).get("value") == "group"
        }
        assert all(name in groups for name in expected), groups.keys()
        for parent, child in pairwise(expected):
            ancestor = by_id[groups[child]["parentId"]]
            while ancestor.get("role", {}).get("value") != "group":
                ancestor = by_id[ancestor["parentId"]]
            assert ancestor["nodeId"] == groups[parent]["nodeId"]
        return groups

    hierarchy(path)
    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(serve.page_dir), leaf_id, "status", "value=done"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    leaf = page.locator(f"#{leaf_id}")
    expect(leaf).to_have_attribute("status", "done")
    hierarchy(path)
    assert "done" in leaf.aria_snapshot()

    # Naming references the title node, so a revision's replacement title is what
    # the group says. The command root also reads its current label after patching.
    changed = markup.replace(path[-1], "Verify the final corpus")
    changed_path = [*path[:-1], "Verify the final corpus"]
    if markup == COMMAND_HUB_PAGE:
        changed = changed.replace(path[0], "Ready for the shadow week")
        changed_path[0] = "Ready for the shadow week"
    stamp_page(serve.page_dir, changed, "Clarify the plan's current titles")
    wait_for_revision(page, 2)
    groups = hierarchy(changed_path)
    assert path[-1] not in groups
    if markup == COMMAND_HUB_PAGE:
        assert path[0] not in groups
        summary = page.locator("#w-1 > details > summary")
        summary.click()
        expect(page.locator("#w-1 > details")).to_have_attribute("open", "")
        hierarchy(changed_path)


def test_atlas_input_is_trimmed_before_it_enters_the_record(browser, serve):
    """The replica cargo is visible in the real editor before Save. Trimming it
    changes the one payload that enters the log, leaves a receipt naming the input,
    and releases that input row without claiming the dependent work completed."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page = open_page(browser, url)
    draft = page.locator("#ledger-cargo")
    draft_control(page, "edit", "ledger-cargo").click()
    editor = draft.get_by_role("textbox", name="Edit ledger-cargo")
    write(
        editor,
        "ledger_id,customer_name,billing_email,amount\n7,Alice,a@example.test,42",
    )
    assert not [
        event
        for event in events_model.read_events(d)
        if event.get("widget") == "ledger-cargo"
    ]
    write(
        editor,
        "ledger_id,customer_name,billing_email,amount\n7,[redacted],[redacted],42",
    )
    with sending(page, "the saved edit"):
        draft_control(page, "save", "ledger-cargo").click()

    edit = next(
        event
        for event in reversed(events_model.read_events(d))
        if event.get("widget") == "ledger-cargo"
    )
    assert "Alice" not in edit["detail"]["value"]
    assert "a@example.test" not in edit["detail"]["value"]
    assert edit["detail"]["value"].count("[redacted]") == 2
    page.locator("#atlas-record .lf-activity-news").click()
    saved = page.locator("#atlas-record .lf-activity-row").first
    expect(saved).to_contain_text("You edited")
    expect(saved.locator('a[href="#ledger-cargo"]')).to_have_count(1)
    expect(page.locator('[data-atlas-count="stopped"]')).to_have_text("4")
    expect(page.locator("#ledger-variance")).to_have_attribute("status", "planned")


def test_datum_travel_resolves_the_destination_after_reveal(browser, serve):
    """A reveal may rebuild the destination row, and travel lands on the rebuilt one;
    a later reveal that removes it says the row is not there."""
    url = serve(
        leaf_page(
            "reveal replaces projection",
            '<h1 id="title">Call change</h1>'
            '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
            '<lf-diff id="patch" source="patch-data"><pre></pre></lf-diff>',
        ),
        packages=("diff",),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "calls-data",
        "calldiff diff main → feature\n  changed()  app.py:1\n+ └─ added()  app.py:2",
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1,2 @@\n changed()\n+added()\n",
    )
    page = open_page(browser, url)
    expect(page.locator("#calls .lf-call-group")).to_have_attribute("open", "")
    # A container may synchronously rebuild its projection while revealing it.
    # Repeat that lifecycle on every reveal so a second reveal after resolution
    # cannot hide a stale-node scroll behind the first successful re-query.
    page.locator("#patch").evaluate(
        """source => {
          let revealed = false;
          source.addEventListener('lf-reveal', () => {
            const row = source.shadowRoot.querySelector(
              `[data-lf-datum='["app.py","new",2]']`);
            if (!row) return;
            if (revealed) {
              row.remove();
            } else {
              // Marked, so the rebuild is a different row and not the same one
              // written again.
              const next = row.cloneNode(true);
              next.dataset.rebuilt = '';
              row.replaceWith(next);
              revealed = true;
            }
          });
        }"""
    )
    page.locator("#calls .lf-call-location").last.click()
    expect(page.locator(".lf-live")).to_have_text("Opened app.py:2 in the exact patch")
    expect(
        page.locator('lf-diff [data-lf-datum=\'["app.py","new",2]\'][data-rebuilt]')
    ).to_be_in_viewport()
    page.locator("#calls .lf-call-location").last.click()
    expect(page.locator(".lf-live")).to_have_text(
        "app.py:2 is not present in the exact patch"
    )


def test_the_activity_feed_words_a_pick_in_the_document_it_was_made_in(browser, serve):
    """A later version rewording or removing an option leaves the feed's row as made."""

    def page_with(question):
        return leaf_page(
            "Route",
            f"<h1>Route</h1>{question}"
            '<section id="recent"><h2>Recent</h2>'
            '<lf-activity id="feed"></lf-activity></section>',
        )

    def ask(fast, restated=""):
        return f"""<lf-ask id="route-ask"><h2>Which route?</h2>
  <lf-options id="route" choose>
    <lf-option id="route-fast"{restated}>{fast}</lf-option>
    <lf-option id="route-slow">Slow path</lf-option>
  </lf-options>
</lf-ask>"""

    page = open_page(browser, live_url(serve(page_with(ask("Fast path")))))
    page.locator("#route-fast .lf-pick").click()
    round_trip(page)
    page.locator("#feed .lf-activity-news").click()
    row = page.locator("#feed .lf-activity-row", has_text="chose")
    expect(row).to_contain_text("chose “Fast path” in")

    reworded = page_with(ask("Quick route", " restated"))
    stamp_page(serve.page_dir, reworded, "reword the option")
    wait_for_revision(page, 2)
    expect(row).to_contain_text("chose “Fast path” in")

    stamp_page(serve.page_dir, page_with(""), "drop the question")
    wait_for_revision(page, 3)
    expect(row).to_contain_text("chose “Fast path” in")


def test_activity_holds_arrivals_until_the_reader_reveals_them(browser, serve):
    """News above a visible passage waits; its fixed control never dodges activation.
    The control is a button, worked here by the keyboard; a tap activates the same
    button."""
    html = leaf_page(
        "History",
        '<h1>History</h1><section id="recent"><h2>Recent</h2>'
        '<lf-activity id="feed"></lf-activity></section><section id="policy">'
        '<h2>Policy</h2><p id="reading">Keep this visible line where it stands.</p></section>',
    )
    url = live_url(serve(html))
    page = open_page(browser, url)
    control = page.locator("#feed .lf-activity-news")
    line = page.locator("#reading")
    expect(control).to_have_text("Show activity")
    before = line.bounding_box()
    first = append_command(
        serve.page_dir,
        {
            "revision": 1,
            "kind": "comment",
            "author": "user",
            "anchor": {"section": "policy"},
            "text": "First incoming update",
        },
    )
    told(page)
    expect(control).to_have_text("Show activity · 1 new")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)
    assert line.bounding_box()["y"] == pytest.approx(before["y"], abs=0.5)
    control.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(control).to_be_focused()
    control.press("Enter")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(2)
    expect(control).to_have_text("Hide activity")
    focused_row = page.locator("#feed .lf-activity-row").first.locator(
        ".lf-activity-target"
    )
    page.keyboard.press("Tab")
    expect(focused_row).to_be_focused()
    before = line.bounding_box()
    trigger = control.bounding_box()
    append_command(
        serve.page_dir,
        {
            "revision": 1,
            "kind": "reply",
            "author": "agent",
            "parent": first["id"],
            "text": "A second arrival with enough words to visibly grow the feed.",
        },
    )
    told(page)
    expect(control).to_have_text("Show 1 new")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(2)
    assert line.bounding_box()["y"] == pytest.approx(before["y"], abs=0.5)
    assert control.bounding_box() == trigger
    expect(focused_row).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(control).to_be_focused()
    control.press("Space")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(3)
    expect(page.locator("#feed .lf-activity-row").first).to_contain_text(
        "A second arrival"
    )
    assert control.bounding_box() == trigger
    expect(control).to_be_focused()

    # An existing row changing shape is news too, even with no newly added row.
    before = line.bounding_box()
    resolution = append_command(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": first["id"]}
    )
    told(page)
    control.click()
    before = line.bounding_box()
    append_command(
        serve.page_dir, {"kind": "undo", "author": "user", "undoes": resolution["id"]}
    )
    told(page)
    expect(control).to_have_text("Activity changed")
    assert line.bounding_box()["y"] == pytest.approx(before["y"], abs=0.5)
    control.click()
    expect(
        page.locator("#feed .lf-activity-row", has_text="You resolved")
    ).to_have_attribute("data-lf-undone", "")
    assert control.bounding_box() == trigger
    before_revision = line.bounding_box()
    stamp_page(
        serve.page_dir,
        html.replace("Keep this visible", "Still keep this visible"),
        "Revise the policy",
    )
    wait_for_revision(page, 2)
    expect(control).to_have_attribute("aria-expanded", "true")
    expect(control).to_have_text("Show 1 new")
    assert line.bounding_box()["y"] == pytest.approx(before_revision["y"], abs=0.5)
    # Changing executable inputs replaces the document, rather than patching it.
    page.add_init_script("""
      window.activityFrames = [];
      let remaining = 180;
      function readFrame() {
        const line = document.getElementById("reading");
        const control = document.querySelector("#feed .lf-activity-news");
        if (line && control) window.activityFrames.push({
          line: line.getBoundingClientRect().y,
          open: control.getAttribute("aria-expanded")
        });
        if (--remaining) requestAnimationFrame(readFrame);
      }
      requestAnimationFrame(readFrame);
    """)
    before_replacement = line.bounding_box()
    original_document = page.evaluate("performance.timeOrigin")
    expect(control).to_be_focused()
    fresh = html.replace("Keep this visible", "Still keep this visible").replace(
        "</head>", '<script type="module">void 0;</script></head>'
    )
    stamp_page(serve.page_dir, fresh, "Replace executable inputs")
    wait_for_revision(page, 3)
    wait_until_ready(page)
    expect(control).to_have_attribute("aria-expanded", "true")
    assert page.evaluate("performance.timeOrigin") != original_document
    assert line.bounding_box()["y"] == pytest.approx(before_replacement["y"], abs=0.5)
    expect(control).to_be_focused()
    frames = page.evaluate("window.activityFrames")
    assert frames
    assert all(frame["open"] == "true" for frame in frames)
    assert all(
        frame["line"] == pytest.approx(before_replacement["y"], abs=0.5)
        for frame in frames
    )
    # Generated row targets use the same keyed handoff as the notice.
    target = page.locator("#feed .lf-activity-row button.lf-activity-target").first
    control.press("Tab")
    expect(target).to_be_focused()
    stamp_page(serve.page_dir, fresh.replace("void 0", "void 1"), "Replace again")
    wait_for_revision(page, 4)
    wait_until_ready(page)
    expect(target).to_be_focused()
    assert line.bounding_box()["y"] == pytest.approx(before_replacement["y"], abs=0.5)


def test_activity_prints_complete_history_even_when_closed_or_held(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "History", '<h1>History</h1><lf-activity id="feed"></lf-activity>'
            )
        ),
    )
    control = page.locator("#feed .lf-activity-news")
    expect(control).to_have_attribute("aria-expanded", "false")
    page.emulate_media(media="print")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)
    expect(page.locator("#feed .lf-activity-row")).to_be_visible()
    expect(control).to_be_hidden()
    page.emulate_media(media="screen")
    expect(control).to_be_visible()
    expect(control).to_have_attribute("aria-expanded", "false")
    control.click()
    comment = append_command(
        serve.page_dir,
        {
            "revision": 1,
            "kind": "comment",
            "author": "user",
            "text": "A held record for paper.",
        },
    )
    told(page)
    expect(control).to_have_text("Show 1 new")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)
    page.emulate_media(media="print")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(2)
    expect(page.locator("#feed .lf-activity-row").first).to_contain_text(
        "A held record for paper."
    )
    page.emulate_media(media="screen")
    expect(control).to_have_text("Show 1 new")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)

    control.click()
    resolution = append_command(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": comment["id"]}
    )
    told(page)
    control.click()
    target = page.locator("#feed .lf-activity-row").first.locator("button")
    control.press("Tab")
    expect(target).to_be_focused()
    append_command(
        serve.page_dir, {"kind": "undo", "author": "user", "undoes": resolution["id"]}
    )
    told(page)
    expect(control).to_have_text("Activity changed")
    page.emulate_media(media="print")
    expect(page.locator("#feed .lf-activity-row").first).to_have_attribute(
        "data-lf-undone", ""
    )
    page.emulate_media(media="screen")
    expect(control).to_have_text("Activity changed")
    expect(target).to_be_focused()
