"""The PR review package, diffs, call diffs and text-document sources: their identities,
navigation, filtering, and the drafts kept when a source changes."""

import json
import re
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from interact_support import ROOT, append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_navigation import call_diff, call_node, source_revision
from render_harness import (
    leaf_page,
    open_page,
    panel_field,
    panel_settled,
    refuse,
    reported_browser_errors,
    resized,
    root_overflow,
    round_trip,
    select,
    selection_field,
    sending,
    suggestion_control,
    ticked,
    told,
    write,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import state as cleanup_model
from leaf.render_checks import rendered, wait_until_ready
from leaf_dev.browser import scroll_settled
from leaf_dev.example_data import patch_manifest

pytestmark = pytest.mark.shifts_unsurveyed


def comment_id(page_dir, text):
    """The id of the thread whose root comment says `text`."""
    return next(
        event["id"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment" and event["text"] == text
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
    selection_field(page).click()
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
    # a lasting reason to ask for one: a served page's status claims work, so its
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
            """() => lfUnwatched(() => {
              const element = document.getElementById('reviewed-pr');
              window.detachedPr = element;
              window.detachedPrMarkup = element.innerHTML;
              element.remove();
              const moved = document.getElementById('moved-pr');
              const parent = moved.parentElement;
              moved.remove();
              parent.append(moved);
            })"""
        )
        held.pop(0).continue_()
        page.evaluate(
            """async () => {
              const {loadMarkdown} = await window.__lfWidgetApi();
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


def test_native_call_diff_json_keeps_spaced_paths_and_exact_patch_destinations(
    browser, serve
):
    """Unedited calldiff@0.5.0 --format json: each whitespace path reaches its own
    old/new line. Capture: two exported TypeScript roots changing before() to after()."""
    url = serve(
        leaf_page(
            "native CallDiff",
            '<h1 id="title">Calls</h1>'
            '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
            '<lf-diff id="patch" source="patch-data" collapsed></lf-diff>',
        ),
        packages=("diff",),
    )
    capture = json.loads((ROOT / "tests/fixtures/calldiff-spaces.json").read_text())
    patch = json.loads((ROOT / "tests/fixtures/calldiff-spaces.patch.json").read_text())
    data_model.cmd_data_set(serve.page_dir, "calls-data", capture)
    data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    page = open_page(browser, url)
    widget = page.locator("#calls")
    expect(widget.locator(".lf-call-summary")).to_have_text(
        "2 changed roots · 2 added · 2 removed · 6 items"
    )
    paths = [entry["tree"]["file"] for entry in capture["trees"]]
    assert page.locator("#patch .lf-diff-head .lf-diff-base").all_inner_texts() == [
        path.rsplit("/", 1)[-1] for path in paths
    ]
    assert page.locator("#patch .lf-diff-metadata .lf-diff-base").all_inner_texts() == [
        "label name.txt",
        "label  name.txt",
    ]
    assert widget.locator(".lf-call-root-location a").all_inner_texts() == [
        f"{path}:1" for path in paths
    ]
    widget.get_by_role("button", name="Expand all 2 call-tree roots").click()
    for tree in capture["trees"]:
        for node in [tree["tree"], *tree["tree"]["children"]]:
            path, number = node["file"], node["line"]
            side = "old" if node["status"] == "removed" else "new"
            status = "unchanged" if node["status"] == "same" else node["status"]
            selector = (
                ".lf-call-root-location a"
                if status == "unchanged"
                else f'.lf-call-line[data-status="{status}"] a'
            )
            # Playwright's text filters collapse whitespace; the source coordinates
            # intentionally distinguish these two names.
            link = widget.locator(selector).filter(
                has_text=re.compile(r"^" + re.escape(f"{path}:{number}") + r"$")
            )
            link.click()
            expected = [path, "both", 1, 1] if number == 1 else [path, side, number]
            target = page.locator(
                f"#patch [data-lf-datum='{json.dumps(expected, separators=(',', ':'))}']"
            )
            expect(target).to_be_focused()
            expect(target).to_be_in_viewport()
            expect(page.locator(".lf-live")).to_have_text(
                f"Opened {path}:{number} in the exact patch"
            )


@pytest.mark.parametrize("touch", [False, True])
def test_missing_call_location_keeps_the_reader_at_the_source(browser, serve, touch):
    """An unavailable line explains itself without navigating to an unrelated file."""
    url = serve(
        leaf_page(
            "source navigation",
            '<h1 id="title">Calls</h1>'
            '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
            '<div style="height: 1600px"></div>'
            '<lf-diff id="patch" source="patch-data" collapsed></lf-diff>',
        ),
        packages=("diff",),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -8 +8 @@\n-before()\n+after()\n",
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "calls-data",
        call_diff(
            call_node("outside_patch()", "app.py", 1),
            call_node("after()", "app.py", 8, status="added"),
        ),
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}
        if touch
        else {"width": 900, "height": 600},
        has_touch=touch,
    )
    page = open_page(browser, url, context=context)
    missing = page.get_by_role("link", name="app.py:1", exact=True)

    def read_place():
        return page.evaluate(
            "({scroll: scrollY, url: location.href, history: history.length})"
        )

    def visit_missing():
        missing.scroll_into_view_if_needed()
        missing.focus()
        scroll_settled(page)
        before = read_place()
        if touch:
            missing.tap()
        else:
            missing.press("Enter")
        message = "app.py:1 is not present in the exact patch"
        expect(panel_field(page)).to_have_attribute("placeholder", message)
        expect(page.locator(".lf-live")).to_have_text(message)
        expect(missing).to_be_focused()
        assert read_place() == before

    visit_missing()
    available = page.get_by_role("link", name="app.py:8", exact=True)
    available.click()
    expect(
        page.get_by_role("button", name="Comment on app.py · new line 8")
    ).to_be_in_viewport()
    page.go_back()
    expect(available).to_be_in_viewport()
    visit_missing()
    # The same failed-navigation contract holds if the target leaves the document.
    page.locator("#patch").evaluate("node => lfUnwatched(() => node.remove())")
    visit_missing()


def test_diff_coordinates_keep_identity_separate_from_source_navigation(browser, serve):
    """An analyzer's old-source fallback must never retarget a durable new address."""
    url = serve(
        leaf_page(
            "source coordinates",
            '<h1 id="title">Call locations</h1>'
            '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
            '<lf-diff id="patch" source="patch-data"></lf-diff>',
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
        call_diff(
            call_node("shifted()", "app.py", 8),
            call_node("absent_new()", "app.py", 6),
            call_node("removed()", "app.py", 6, status="removed"),
            call_node("added()", "app.py", 9, status="added"),
            call_node("last()", "app.py", 11),
        ),
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
        call_diff(call_node("same()", "app.py", 5, status="removed")),
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
            '<lf-diff id="patch" source="patch-data" collapsed></lf-diff>',
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
        call_diff(
            call_node("removed_b()", "b.py", 2, status="removed"),
            call_node("removed_a()", "a.py", 2, status="removed"),
            call_node("new_a()", "a.py", 1, status="added"),
            call_node("added_b()", "b.py", 2, status="added"),
        ),
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
    """A capture that reorders the roots moves the group the user is located in, and one
    that reorders a root's calls moves the row: either way they stay on its location."""
    url = serve(
        leaf_page(
            "call diff order",
            '<h1 id="title">Request call change</h1>'
            '<lf-call-diff id="request-calls" source="request-call-diff" diff="patch">'
            '</lf-call-diff><lf-diff id="patch" source="review-patch"></lf-diff>',
        ),
        packages=("diff",),
    )
    first = call_node(
        "Limiter.first(self)",
        "gateway/limits.py",
        10,
        children=[call_node("one()", "gateway/limits.py", 11, status="added")],
    )
    calls = [
        call_node("two()", "gateway/limits.py", 21, status="added"),
        call_node("three()", "gateway/limits.py", 22, status="added"),
    ]
    second = call_node("Limiter.second(self)", "gateway/limits.py", 20)

    def capture(*roots):
        data_model.cmd_data_set(serve.page_dir, "request-call-diff", call_diff(*roots))

    capture(first, dict(second, children=calls))
    page = open_page(browser, url)
    widget = page.locator("#request-calls")
    groups = widget.locator(":scope > .lf-call-group")
    expect(groups).to_have_count(2)
    root = widget.locator(".lf-call-location", has_text="gateway/limits.py:20")
    root.focus()

    capture(dict(second, children=calls), first)
    told(page)
    expect(groups.first.locator(".lf-call-group-summary .lf-call-body")).to_have_text(
        "Limiter.second(self)"
    )
    expect(root).to_be_focused()

    widget.locator(".lf-call-toggle").click()
    row = widget.locator(".lf-call-location", has_text="gateway/limits.py:22")
    row.focus()
    capture(dict(second, children=list(reversed(calls))), first)
    told(page)
    expect(
        groups.first.locator(".lf-call-group-body .lf-call-body").first
    ).to_have_text("├─ three()")
    expect(row).to_be_focused()

    # Equal root names can share a stable call row while its group changes. The
    # closed destination may already exist or arrive in this capture; both expose
    # the user's focused row while a transfer without focus leaves its group closed.
    first_work = call_node("work()", "app.py", 1)
    second_work = call_node("work()", "app.py", 20)
    third_work = call_node("work()", "app.py", 60)
    unfocused = call_node("other_helper()", "utils.py", 3)
    shared = call_node("helper()", "utils.py", 2)
    capture(dict(first_work, children=[unfocused, shared]), second_work, third_work)
    told(page)
    expect(groups).to_have_count(3)
    expect(groups.nth(1)).not_to_have_attribute("open", "")
    location = widget.locator(".lf-call-location", has_text="utils.py:2")
    location.focus()
    for destination, roots in (
        (
            "app.py:20",
            (
                first_work,
                dict(second_work, children=[shared]),
                dict(third_work, children=[unfocused]),
            ),
        ),
        (
            "app.py:40",
            (
                call_node("work()", "app.py", 30),
                call_node("work()", "app.py", 40, children=[shared]),
                dict(third_work, children=[unfocused]),
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

    # Native callee keys do not identify persistent invocation instances. Source
    # replacements honestly mark the original comment as earlier data.
    page.keyboard.press("c")
    draft = page.locator(".lf-fab-input")
    write(draft, "Keep this helper")
    with sending(page, "the call comment"):
        draft.press("ControlOrMeta+Enter")
    helper = comment_id(serve.page_dir, "Keep this helper")
    expect(open_panel_thread(page, helper).locator(".lf-anchor-status")).to_have_count(
        0
    )
    capture(
        call_node("work()", "app.py", 31),
        call_node("work()", "app.py", 41, children=[dict(shared, line=9)]),
        dict(third_work, line=61, children=[dict(unfocused, line=10)]),
    )
    told(page)
    expect(open_panel_thread(page, helper).locator(".lf-anchor-status")).to_have_text(
        "Earlier data"
    )

    # Removing one duplicate must not transfer its comment to the surviving call,
    # even when that survivor becomes occurrence zero in the next capture.
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    log = call_node("log()", "app.py", 10)
    capture(
        call_node(
            "run()",
            "app.py",
            1,
            children=[log, call_node("save()", "app.py", 15), dict(log, line=20)],
        )
    )
    told(page)
    first_log = widget.locator(".lf-call-location", has_text="app.py:10")
    first_log.focus()
    page.keyboard.press("c")
    write(draft, "Remove this log")
    with sending(page, "the duplicate call comment"):
        draft.press("ControlOrMeta+Enter")
    capture(
        call_node(
            "run()",
            "app.py",
            1,
            children=[
                dict(log, status="removed"),
                call_node("save()", "app.py", 14),
                dict(log, line=19),
            ],
        )
    )
    told(page)
    removed = comment_id(serve.page_dir, "Remove this log")
    expect(open_panel_thread(page, removed).locator(".lf-anchor-status")).to_have_text(
        "Earlier data"
    )


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
    resized(page, 1024, 900)
    if quote_anchor:
        # The code box also spans the gutter and blank column; drag on its words.
        words = page.locator("#source [data-content] [data-line] span").evaluate(
            """span => {
              const range = document.createRange();
              range.selectNodeContents(span);
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
    # need not retain the old quote's inline start after its words disappeared. The
    # document scrolls inside its box, so the card may open over that box or under it.
    reopened = card.bounding_box()
    assert datum["x"] < reopened["x"] + reopened["width"]
    assert reopened["x"] < datum["x"] + datum["width"]
    assert datum["y"] < reopened["y"] < datum["y"] + datum["height"] + 10
    # The thread's own head says the words it quotes are earlier data, as a plain word
    # rather than a boxed badge.
    status = open_panel_thread(page, comment["id"]).locator(".lf-anchor-status")
    expect(status).to_have_text("Earlier data")
    assert status.evaluate("el => getComputedStyle(el).borderTopWidth") == "0px"


def test_a_large_diff_filters_and_navigates_lazy_files(browser, serve):
    authored = leaf_page(
        "large diff review",
        '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch" '
        "collapsed></lf-diff>",
    )
    url = serve(authored)
    manifest = {
        "files": [
            {
                "path": path,
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

    # One file has nothing to filter, and its header already names it.
    expect(page.locator("#single .lf-diff-search")).to_have_count(0)
    expect(diff.locator(".lf-diff-progress")).to_have_text("2 files")
    search = diff.locator(".lf-diff-search input")
    search.fill("second")
    expect(diff.locator(".lf-diff-progress")).to_have_text("1 of 2")
    expect(diff.locator("summary").nth(0)).to_be_hidden()
    expect(diff.locator("summary").nth(1)).to_be_visible()


def test_datum_travel_resolves_the_destination_after_reveal(browser, serve):
    """A reveal may rebuild the destination row, and travel lands on the rebuilt one;
    a later reveal that removes it says the row is not there."""
    url = serve(
        leaf_page(
            "reveal replaces projection",
            '<h1 id="title">Call change</h1>'
            '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
            '<div id="holder"><lf-diff id="patch" source="patch-data"></lf-diff></div>',
        ),
        packages=("diff",),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "calls-data",
        call_diff(
            call_node(
                "changed()",
                "app.py",
                1,
                children=[call_node("added()", "app.py", 2, status="added")],
            )
        ),
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
    # Each reveal reaches the patch through a holder hidden until found.
    hide = "() => { document.querySelector('#holder').hidden = 'until-found'; }"
    page.locator("#patch").evaluate(
        """source => {
          let revealed = false;
          source.parentElement.addEventListener('beforematch', () => {
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
    page.evaluate(hide)
    page.locator("#calls .lf-call-location").last.click()
    expect(page.locator(".lf-live")).to_have_text("Opened app.py:2 in the exact patch")
    expect(
        page.locator('lf-diff [data-lf-datum=\'["app.py","new",2]\'][data-rebuilt]')
    ).to_be_in_viewport()
    page.evaluate(hide)
    page.locator("#calls .lf-call-location").last.click()
    expect(page.locator(".lf-live")).to_have_text(
        "app.py:2 is not present in the exact patch"
    )
