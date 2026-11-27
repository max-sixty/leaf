"Live version, report, replay, and projection tests."

import json
import re

import pytest
from interact_support import (
    append_carried_log_record,
)
from journeys import first_thread_head
from playwright.sync_api import expect
from render_cases_interaction import (
    COMMAND_HUB_EXAMPLE,
    COMMAND_HUB_PAGE,
    REF_PAGE,
    drifting_widget,
    live_url,
)
from render_cases_navigation import (
    call_diff,
    call_node,
    source_revision,
)
from render_harness import (
    EXAMPLE_PACKAGES,
    draft_control,
    expect_obligations_answered,
    leaf_page,
    names,
    open_page,
    press_draft_control,
    resized,
    root_overflow,
    round_trip,
    selection_field,
    sending,
    stamp_page,
    told,
    undo,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf.log import event_log as events_model
from leaf.pages.render_gate.readings import DevtoolsIssues
from leaf.records import page_data as page_data_model
from leaf.source import render_checks as render_checks_model
from leaf.source.render_checks import wait_until_ready
from leaf_dev.browser import text_field

pytestmark = pytest.mark.shifts_unsurveyed


def test_call_diff_projects_stable_commentable_rows(browser, serve):
    authored = leaf_page(
        "call diff",
        """
<h1 id="title">Request call change</h1>
<pre id="code-surface">reference code surface</pre>
<lf-call-diff id="request-calls" source="request-call-diff" diff="patch"></lf-call-diff>
<lf-diff id="patch" source="review-patch" collapsed></lf-diff>
""",
    )
    url = serve(authored, packages=("diff",))
    capture = call_diff(
        call_node(
            "Limiter.bucket_key(self, request)",
            "gateway/limits.py",
            38,
            children=[
                call_node(
                    "if request.token",
                    "gateway/limits.py",
                    40,
                    status="added",
                    kind="branch",
                )
            ],
        )
    )
    patch = """diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -38,3 +38,5 @@ class Limiter:
 class Limiter:
-    def bucket_key(self, request):
-        return request.remote_addr
+    def bucket_key(self, request):
+        if request.token:
+            return f"tok:{request.token.id}"
+        return f"ip:{request.remote_addr}"
"""
    page_data_model.cmd_data_set(serve.page_dir, "request-call-diff", capture)
    page_data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        {
            "files": [
                {
                    "path": "gateway/limits.py",
                    "patch": patch,
                },
                # A second file, so the diff draws the filter a reveal clears.
                {
                    "path": "gateway/README.md",
                    "patch": "diff --git a/gateway/README.md b/gateway/README.md\n"
                    "--- a/gateway/README.md\n+++ b/gateway/README.md\n"
                    "@@ -1 +1 @@\n-Limits by address.\n+Limits by token.\n",
                },
            ]
        },
    )
    page = open_page(browser, url)
    assert not DevtoolsIssues(page).findings()
    widget = page.locator("#request-calls")
    lines = widget.locator(".lf-call-line")

    expect(lines).to_have_count(3)
    expect(widget.locator(".lf-call-summary")).to_have_text(
        "1 changed root · 1 added · 0 removed · 2 items"
    )
    # The counts are this widget's account of the tree, not words the page holds:
    # data-lf-gen is what keeps them out of the version diff, which parses the base.
    expect(widget.locator(".lf-call-summary")).to_have_attribute("data-lf-gen", "1")
    expect(widget.locator(".lf-call-group-count")).to_have_attribute("data-lf-gen", "1")
    groups = widget.locator(":scope > .lf-call-group")
    expect(groups).to_have_count(1)
    group = groups.first
    summary = group.locator(":scope > summary")
    root_location = widget.locator(".lf-call-root-location .lf-call-location").first
    expect(root_location).to_have_text("gateway/limits.py:38")
    expect(root_location).to_be_visible()
    expect(summary.locator("a, button")).to_have_count(0)
    assert group.evaluate("el => getComputedStyle(el).backgroundColor") == page.locator(
        "#code-surface"
    ).evaluate("el => getComputedStyle(el).backgroundColor")
    expect(group.locator(":scope > summary")).to_have_count(1)
    expect(group).to_have_attribute("open", "")
    expect(widget.locator(".lf-call-toggle")).to_have_attribute(
        "aria-label", "Collapse all 1 call-tree root"
    )
    expect(lines.nth(0)).to_have_attribute("data-lf-meta", "")
    expect(lines.nth(0).locator(".lf-call-body")).to_have_text(
        "calldiff diff main → feature"
    )
    resized(page, 900, 900)
    assert lines.nth(0).evaluate("line => line.scrollWidth <= line.clientWidth")
    # Ordinary buttons keep the same ink on tinted document and shadow surfaces.
    colors = []
    for control in (".lf-call-toggle", ".lf-diff-file-comment"):
        colors.append(
            page.locator(control).first.evaluate("""button => {
            const parent = button.parentElement;
            const prior = parent.style.color;
            const before = getComputedStyle(button).color;
            parent.style.color = 'rgb(200, 0, 100)';
            const tinted = getComputedStyle(button).color;
            parent.style.color = prior;
            return [before, tinted];
        }""")
        )
    assert all(before == tinted for before, tinted in colors), colors
    widget.locator(".lf-call-toggle").click()
    expect(group).not_to_have_attribute("open", "")
    expect(widget.locator(".lf-call-toggle")).to_have_attribute(
        "aria-label", "Expand all 1 call-tree root"
    )
    widget.locator(".lf-call-toggle").click()
    expect(group).to_have_attribute("open", "")
    expect(widget.locator(".lf-call-toggle")).to_have_attribute(
        "aria-label", "Collapse all 1 call-tree root"
    )
    file_header = page.locator("#patch .lf-diff-file summary").first
    expect(file_header).to_have_attribute(
        "data-lf-datum", '["gateway/limits.py","file"]'
    )
    expect(file_header).to_have_attribute(
        "data-lf-datum-label", "gateway/limits.py · file"
    )
    expect(lines.nth(1)).to_have_attribute("data-lf-root", "")
    expect(lines.nth(1)).to_have_attribute("data-lf-projection", "request-calls")
    expect(lines.nth(1)).to_have_attribute("data-lf-datum", re.compile(r".+"))
    expect(lines.nth(2)).to_have_attribute("data-lf-status", "added")
    expect(lines.nth(2).locator(".lf-call-marker")).to_have_text("+")
    expect(lines.nth(2)).to_have_attribute(
        "data-lf-datum-label",
        "added call-tree item └─ if request.token at gateway/limits.py:40",
    )
    expect(lines.nth(2).locator(".lf-call-location")).to_have_text(
        "gateway/limits.py:40"
    )
    assert (
        lines.nth(2)
        .locator(".lf-call-marker")
        .evaluate("el => getComputedStyle(el).userSelect")
        == "none"
    )

    selected = (
        lines.nth(2)
        .locator(".lf-call-body")
        .evaluate(
            """body => {
          const range = document.createRange();
          range.selectNodeContents(body);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          body.closest('.lf-call-line').__callIdentity = true;
          return selection.toString();
        }"""
        )
    )
    assert selected == "└─ if request.token"
    expect(selection_field(page)).to_be_visible()

    updated = call_diff(
        capture["trees"][0]["tree"],
        call_node(
            "Limiter.secondary(self)",
            "gateway/limits.py",
            50,
            children=[
                call_node("return True", "gateway/limits.py", 51, status="added")
            ],
        ),
        to="feature-2",
    )
    page_data_model.cmd_data_set(serve.page_dir, "request-call-diff", updated)
    told(page)
    # A retained row carries the capture it now shows, at its place in the tree.
    expect(lines.nth(2)).to_have_attribute(
        "data-lf-source-revision", source_revision(serve.page_dir, "request-call-diff")
    )
    assert json.loads(lines.nth(2).get_attribute("data-lf-origin"))["path"] == [
        "trees",
        0,
        "tree",
        "children",
        0,
    ]
    expect(group).to_have_attribute("open", "")
    expect(groups).to_have_count(2)
    # A root the capture adds opens as it arrives, as the first did.
    expect(groups.nth(1)).to_have_attribute("open", "")
    expect(widget.locator(".lf-call-toggle")).to_have_attribute(
        "aria-label", "Collapse all 2 call-tree roots"
    )
    expect(lines.nth(2).locator(".lf-call-location")).to_have_text(
        "gateway/limits.py:40"
    )
    assert lines.nth(2).evaluate("el => el.__callIdentity") is True
    assert page.evaluate("() => getSelection().toString()") == selected
    selection_field(page).click()
    expect(page.locator("#lf-composer-quote")).to_contain_text(f"“{selected}”")
    expect(page.locator(".lf-fab-input")).to_be_focused()

    page.keyboard.press("Escape")
    expect(page.locator("#patch [data-line-type]")).to_have_count(0)
    entries = page.evaluate("history.length")
    summary.click()
    expect(group).not_to_have_attribute("open", "")
    expect(root_location).to_be_visible()
    root_location.click()
    expect(group).not_to_have_attribute("open", "")
    context = page.locator(
        'lf-diff [data-lf-datum=\'["gateway/limits.py","both",38,38]\']'
    )
    expect(context).to_be_in_viewport()
    expect(page.locator(".lf-live")).to_have_text(
        "Opened gateway/limits.py:38 in the exact patch"
    )
    expect(context).to_be_focused()
    summary.click()
    expect(group).to_have_attribute("open", "")

    search = page.locator("#patch .lf-diff-search input")
    search.fill("nothing-matches")
    expect(context).to_be_hidden()
    lines.nth(2).locator(".lf-call-location").click()
    expect(search).to_have_value("")
    added = page.locator('lf-diff [data-lf-datum=\'["gateway/limits.py","new",40]\']')
    expect(added).to_be_in_viewport()
    expect(page.locator(".lf-live")).to_have_text(
        "Opened gateway/limits.py:40 in the exact patch"
    )
    expect(added).to_be_focused()
    # Each trip lands the user on a line they weren't on, so each is a Back step, as a
    # followed link is, though the diff had already brought the line into the window.
    assert page.evaluate("history.length") == entries + 2

    page_data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        patch.replace(" class Limiter:", " class Limiter:  # raw source"),
    )
    told(page)
    expect(context).to_contain_text("class Limiter:  # raw source")
    root_location.click()
    expect(context).to_be_in_viewport()
    expect(page.locator(".lf-live")).to_have_text(
        "Opened gateway/limits.py:38 in the exact patch"
    )

    # Native tab order exposes source navigation even with the call tree closed.
    summary.click()
    expect(group).not_to_have_attribute("open", "")
    page.keyboard.press("Shift+Tab")
    expect(root_location).to_be_focused()
    assert root_location.evaluate("node => node.matches(':focus-visible')")
    page.keyboard.press("Enter")
    expect(context).to_be_focused()
    expect(group).not_to_have_attribute("open", "")
    expect(context).to_be_in_viewport()
    summary.click()
    expect(group).to_have_attribute("open", "")
    page.keyboard.press("Space")
    expect(group).not_to_have_attribute("open", "")
    page.keyboard.press("Enter")
    expect(group).to_have_attribute("open", "")

    page.evaluate("() => getSelection().removeAllRanges()")
    lines.nth(2).click(modifiers=["Alt"])
    expect(page.locator(".lf-fab-input")).to_be_focused()
    write(page.locator(".lf-composer leaf-text"), "Review this added call.")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    expect(first_thread_head(page, serve.page_dir)).to_have_text(
        "§ added call-tree item └─ if request.token at gateway/limits.py:40"
    )

    page_data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        """diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -100 +102 @@
 shifted_call()
""",
    )
    page_data_model.cmd_data_set(
        serve.page_dir,
        "request-call-diff",
        call_diff(call_node("shifted_call()", "gateway/limits.py", 102)),
    )
    told(page)
    shifted = page.locator(
        'lf-diff [data-lf-datum=\'["gateway/limits.py","both",100,102]\']'
    )
    root_location.click()
    expect(shifted).to_be_in_viewport()
    expect(page.locator(".lf-live")).to_have_text(
        "Opened gateway/limits.py:102 in the exact patch"
    )

    # Native trees can contain synthetic nodes without source coordinates.
    page_data_model.cmd_data_set(
        serve.page_dir, "request-call-diff", call_diff(call_node("synthetic()"))
    )
    told(page)
    expect(widget.locator(".lf-call-group-summary")).to_contain_text("synthetic()")
    expect(widget.locator(".lf-call-location:visible")).to_have_count(0)

    page_data_model.cmd_data_set(
        serve.page_dir,
        "request-call-diff",
        call_diff(message="No callstack changes for requested entrypoints."),
    )
    told(page)
    expect(widget.locator(".lf-call-line")).to_have_text(
        "No callstack changes for requested entrypoints."
    )
    expect(widget.locator(".lf-call-root-location, .lf-call-group")).to_have_count(0)

    resized(page, 390, 900)
    assert root_overflow(page) == 0


def test_a_widget_current_location_out_of_place_is_a_page_the_gate_reports(
    browser, serve, tmp_path, monkeypatch
):
    """The premise the test below rests on, stated where it can fail on its own.

    With nothing in the log to settle it, <lf-drift> keeps the offset its markup
    states for as long as the page is open, and its words sit over the paragraphs
    under it. That is a page the covered-words reading reports — so the test below,
    which serves this same markup and expects nothing, is measuring the gate's
    patience rather than a page that was never broken."""
    url = serve(
        drifting_widget(tmp_path, monkeypatch), packages=(*EXAMPLE_PACKAGES, "./.leaf")
    )
    page = open_page(browser, url)
    covered = render_checks_model.evaluate_probe(page, "coveredWords")

    assert covered and all(names(f, "drift-note") for f in covered), covered


@pytest.mark.parametrize(
    "provided",
    ["ledger_id,amount\n7,42", "\nledger_id,amount\n7,42  \n"],
)
def test_command_hub_an_absorbed_input_stays_fulfilled(browser, serve, provided):
    """An input action discharges the request live; the honoring version removes its
    authored `required` condition and its obligation, so incorporating its state into source
    cannot turn the input back into a decision."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    draft = page.locator("#ledger-cargo")
    draft_control(page, "edit", "ledger-cargo").click()
    editor = draft.locator("leaf-text")
    if provided.startswith("\n"):
        # CodeMirror's bulk insertText reading drops an initial LF;
        # create that line through the editor's ordinary key route instead.
        write(editor, "")
        page.keyboard.press("Shift+Enter")
        page.keyboard.insert_text(provided[1:])
    else:
        write(editor, provided)
    expect(text_field(draft)).to_have_js_property("value", provided)
    press_draft_control(page, "save", "ledger-cargo")
    round_trip(page)
    expect_obligations_answered(page, "1/5")
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile(r"^On Me · [1-9]\d* waiting on me")
    )

    honoring = re.sub(
        r'<lf-draft id="ledger-cargo" required>.*?</lf-draft>',
        # The authoring contract adds only the opening LF consumed by HTML.
        f'<lf-draft id="ledger-cargo"><pre>\n{provided}</pre></lf-draft>',
        COMMAND_HUB_PAGE,
        flags=re.DOTALL,
    )
    # A draft without `required` is optional editing, not an obligation its group asks.
    honoring = re.sub(
        r'<section\s+id="decision-ledger-fixture-region"[^>]*>',
        '<div id="decision-ledger-fixture-region">',
        honoring,
    ).replace(
        "</lf-draft>\n              </section>",
        "</lf-draft>\n              </div>",
    )
    assert '<section id="decision-ledger-fixture-region"' not in honoring
    stamp_page(d, honoring, "input absorbed")
    wait_for_revision(page, 2)
    # The saved answer remains in the reviewable obligation inventory after the source
    # drops `required`; it is completed, not newly owed to the user.
    expect_obligations_answered(page, "1/5")
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile(r"^On Me · [1-9]\d* waiting on me")
    )
    expect(page.locator("#ledger-cargo")).not_to_have_attribute("required")
    expect(page.locator("#ledger-cargo")).not_to_have_attribute("data-lf-user-override")
    expect(page.locator("#ledger-fixture")).to_be_visible()
    draft_control(page, "edit", "ledger-cargo").click()
    expect(text_field(page.locator("#ledger-cargo"))).to_have_js_property(
        "value", provided
    )


def test_atlas_send_and_pause_is_one_thread_fold(browser, serve):
    """The stronger send has no companion pause action. Its unresolved thread is
    the hold, so a reply preserves it, resolution releases it, and undoing that
    resolution restores it with the same evidence and comment id."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page = open_page(browser, url)
    goal = page.locator("#goal-parser")
    seat = goal.locator(":scope > .atlas-task-threads")
    goal.locator(":scope > .atlas-task-comment").click()
    write(seat.locator(".lf-fab-input"), "Finish the current hunk, then park here.")
    with sending(page, "the held send"):
        seat.get_by_role("button", name="Send & pause", exact=True).click()
    # Leaf says what the press did beyond a comment, in words that hold for any widget.
    expect(page.locator(".lf-live")).to_have_text("Held until resolved")
    page.locator("#atlas-record .lf-activity-news").click()
    paused = page.locator("#atlas-record .lf-activity-row").first
    # The goal is named by its leading <strong>, not the words under it.
    expect(paused).to_contain_text("Me paused")
    expect(paused.locator(".lf-activity-target")).to_have_text("Replace the XML parser")
    expect(paused).to_contain_text("Finish the current hunk, then park here.")
    root = next(
        event
        for event in events_model.read_events(d)
        if event.get("holds") == "goal-parser"
    )

    text_field(seat, name="Reply", exact=True).scroll_into_view_if_needed()
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Relay",
            "parent": root["id"],
            "revision": 1,
            "text": "The hunk is **complete**; see [the run](https://example.com/run) and park.",
        },
    )
    told(page)
    # The reply landed where the user was looking, so it waits for them to open it.
    seat.get_by_role("button", name="1 new", exact=True).click()
    inline_link = seat.locator('a[href="https://example.com/run"]')
    expect(inline_link).to_have_attribute("target", "_blank")
    expect(inline_link).to_have_attribute("data-lf-external", "")
    # The record stands in the hub's track, which stays in view beside the goal, so
    # the reply waits behind its news as the pause did.
    page.locator("#atlas-record .lf-activity-news").click()
    replied = page.locator("#atlas-record .lf-activity-row").first
    expect(replied.locator(".lf-activity-line")).to_contain_text("Relay replied")
    expect(replied.locator(".lf-activity-excerpt")).to_have_text(
        "The hunk is complete; see the run and park."
    )

    open_panel_thread(page, root["id"])
    with sending(page, "the resolution"):
        page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)").click()
    page.locator("#atlas-record .lf-activity-news").click()
    released = page.locator("#atlas-record .lf-activity-row").first
    expect(released).to_contain_text(
        "Me resolved “Finish the current hunk, then park here.”"
    )

    undo(page)
    # Taking the resolution back leaves its row where it stood, marked undone, once
    # the record shows the change it holds.
    page.locator("#atlas-record .lf-activity-news").click()
    expect(released).to_have_attribute("data-lf-undone", "")
    expect(released).to_contain_text("undone")
    assert [
        event["kind"]
        for event in events_model.read_events(d)
        if event["kind"] in {"comment", "resolve", "undo"}
    ] == ["comment", "resolve", "undo"]


def test_an_arrival_lands_where_the_url_aimed(browser, serve):
    """A URL naming an element is answered once the page is done becoming itself.

    The browser answers it at parse time, when no widget has upgraded and nothing is
    collapsed yet — so the tab holding the target is still open, the document is
    still its unupgraded height, and both facts stop being true a moment later. Leaf
    therefore re-aims a fresh fragment after upgrades, while a reload or a history
    traversal keeps the offset the browser restores.

    Arriving somewhere named is what a fragment is for, and an older semantic landmark
    from another revision must not paint over it. On reload the fragment is left over
    from a reference followed earlier, so the browser's own restored reading position is
    the answer."""
    url = serve(REF_PAGE)
    hidden = re.compile(".*")
    onscreen = """(id) => { const r = document.getElementById(id).getBoundingClientRect();
                            return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""

    # A fresh tab: nothing saved, nothing to outrank. The target is behind a tab that
    # does not exist until the upgrade runs, which is after the browser has jumped.
    page = open_page(browser, f"{url}#p-bath")
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", hidden)
    page.wait_for_function(onscreen, arg="p-bath")

    # Read to the end and leave: the position is written down on the way out and the
    # tab keeps it. Coming back at a named place is what the ranking is for — that
    # position is real and recent, and still not what this URL asked for.
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})"
    )
    page.goto("about:blank")
    page.goto(f"{url}#p-bath")
    wait_until_ready(page)
    page.wait_for_function(onscreen, arg="p-bath")

    # The user moves on, so the fragment is stale by the reload that carries it. The
    # bath tab stays open across that reload and says nothing about this — a tab
    # remembers its own panel, the same way the position is remembered here.
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})"
    )
    page.reload()
    wait_until_ready(page)
    page.wait_for_function(onscreen, arg="tail-end")
