"Live version, report, replay, and projection tests."

import json
import re

import pytest
from interact_support import (
    append_carried_log_record,
    working,
)
from journeys import first_thread_quote
from playwright.sync_api import expect
from render_cases_interaction import (
    COMMAND_HUB_EXAMPLE,
    COMMAND_HUB_PAGE,
    LIVE_V1,
    LIVE_V2,
    LIVE_V3,
    REF_PAGE,
    drifting_widget,
    executable_revision,
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
    expect_on_me,
    expect_panel_offers,
    holding,
    leaf_page,
    names,
    nudge,
    open_page,
    page_comment,
    panel_control,
    panel_field,
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
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf.registry.storage import layer_record
from leaf.render_checks import wait_until_ready
from leaf.render_gate.readings import DevtoolsIssues

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
    data_model.cmd_data_set(serve.page_dir, "request-call-diff", capture)
    data_model.cmd_data_set(
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
    expect(lines.nth(0)).to_have_attribute("data-meta", "")
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
    expect(lines.nth(1)).to_have_attribute("data-root", "")
    expect(lines.nth(1)).to_have_attribute("data-lf-projection", "request-calls")
    expect(lines.nth(1)).to_have_attribute("data-lf-datum", re.compile(r".+"))
    expect(lines.nth(2)).to_have_attribute("data-status", "added")
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
    data_model.cmd_data_set(serve.page_dir, "request-call-diff", updated)
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
    expect(groups.nth(1)).not_to_have_attribute("open", "")
    expect(widget.locator(".lf-call-toggle")).to_have_attribute(
        "aria-label", "Expand all 2 call-tree roots"
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
    # Each line already stood in the window once the diff revealed it, so neither
    # trip departed: no history entry, and the address kept no fragment.
    assert page.evaluate("history.length") == entries
    expect(page).not_to_have_url(re.compile(r"#patch$"))

    data_model.cmd_data_set(
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
    expect(first_thread_quote(page, serve.page_dir)).to_have_text(
        "§ added call-tree item └─ if request.token at gateway/limits.py:40"
    )

    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        """diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -100 +102 @@
 shifted_call()
""",
    )
    data_model.cmd_data_set(
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
    data_model.cmd_data_set(
        serve.page_dir, "request-call-diff", call_diff(call_node("synthetic()"))
    )
    told(page)
    expect(widget.locator(".lf-call-group-summary")).to_contain_text("synthetic()")
    expect(widget.locator(".lf-call-location:visible")).to_have_count(0)

    data_model.cmd_data_set(
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


def test_a_live_revision_preserves_a_reply_after_native_tab(browser, serve):
    """Thread editing follows its log identity, independently of page-source changes."""
    first = leaf_page(
        "Reply continuity",
        '<h1 id="h">Review</h1><p id="subject">Work under discussion.</p>',
    )
    question = (
        '<lf-ask id="question"><h2>Decision?</h2><lf-options id="options" choose>'
        '<lf-option id="yes">Yes</lf-option></lf-options></lf-ask>'
    )
    second = first.replace("</main>", question + "</main>")
    url = serve(first)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Please review this.",
            "anchor": {"section": "subject"},
        },
    )
    page = open_page(browser, live_url(url))
    thread = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    open_panel_thread(page, thread)
    editor = panel_field(page)
    words = "Keep my reply while questions arrive."
    write(editor, words)
    editor.evaluate(
        "node => { window.heldReply = node; node.setSelectionRange(5, 9); }"
    )
    editor.press("Tab")
    send = page.locator(".lf-fp-field .lf-compose-submit")
    expect(send).to_be_focused()

    (serve.page_dir / "index.html").write_text(second)
    expect_on_me(page, 1)
    expect(send).to_be_focused()

    third = second.replace('<p id="subject">Work under discussion.</p>', "")
    (serve.page_dir / "index.html").write_text(third)
    expect(page.locator("#subject")).to_have_count(0)
    expect(send).to_be_focused()
    assert editor.evaluate("node => node === window.heldReply")
    expect(editor).to_have_js_property("value", words)
    assert editor.evaluate("node => [node.selectionStart, node.selectionEnd]") == [5, 9]

    # A fresh document cannot claim native retention and still waits for composition.
    (serve.page_dir / "index.html").write_text(executable_revision(third, "reload"))
    # The page has heard of it once the row, beside the open thread, says it shows an
    # older version and offers the latest. A state read after that asks again whether
    # the page may follow, and the composition still says no.
    told(page)
    expect(page.locator(".lf-fp-row-notice button")).to_be_enabled()
    nudge(serve.page_dir)
    told(page)
    assert editor.evaluate("node => node === window.heldReply")
    send.press("Shift+Tab")
    expect(editor).to_be_focused()
    editor.press("Escape")
    page.wait_for_function("window.heldReply === undefined")
    expect_on_me(page, 1)


def test_an_old_document_state_request_cannot_update_the_new_revision(browser, serve):
    """A request started by the old realm cannot apply a later response in the new one."""

    # A new executable identity requires the fresh-document path. An in-place patch
    # can retain the page-comment editor and no longer waits for this draft.
    version_url = serve(executable_revision(LIVE_V1, "one"))
    page = open_page(browser, live_url(version_url))
    general = page_comment(page)
    write(general, "Do not replace the page under these words.")

    # Let the page learn that the second revision exists before holding a read. The
    # open draft keeps the first revision shown and leaves the direct activation
    # route available through the leaf's menu row for the latest version.
    (serve.page_dir / "index.html").write_text(executable_revision(LIVE_V2, "two"))
    told(page)
    expect(page).to_have_title("Live first")
    expect_panel_offers(page, "latest")

    # One read, held open while it still names the first revision. Releasing it below is
    # what sends it, so the server answers it against the log and versions of that
    # moment while the request still asks for the revision the page has since left.
    held = []
    sent = []

    def hold_the_first_read(route):
        if held:
            route.continue_()
        else:
            held.append(route)

    def release_the_held_read():
        # Released, not popped: the list is the record and the armed flag both, so
        # emptying it would arm the route again and hold the page's next read for good.
        # `sent` is what lets the cleanup below run this after a failed assertion
        # without answering the same route twice.
        if held and not sent:
            sent.append(True)
            held[0].continue_()

    page.route("**/api/state*", hold_the_first_read)
    try:
        working(serve.page_dir, "exercising the held state request")
        holding(page, held, 1, "the read from revision 1")

        # The row's own read remains independent of the background read held above.
        # It moves the page to the second revision, then the third revision is
        # written before the held request is released.
        panel_control(page, "latest").click()
        expect(page).to_have_title("Live second")
        page_comment(page)
        (serve.page_dir / "index.html").write_text(
            executable_revision(LIVE_V3, "three")
        )

        # The premise of the whole reading arrangement, stated rather than inferred: a read the
        # page took while it still stood on the first revision. Held after the press it
        # would name the second, and the answer would carry the view the page wants.
        assert held[0].request.headers.get("leaf-view-revision") == "1", (
            "the held read was not the one taken on the first revision"
        )
        layer = layer_record(serve.page_dir)
        assert layer is not None
        generation = layer["generation"]
        assert held[0].request.headers.get("leaf-layer") == generation
        release_the_held_read()
        told(page)
        expect(page).to_have_title("Live second")
        assert [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "error"
        ] == [], "the page reported a stale answer as a fault"

        # Nothing about the drop cost the page the version it was holding.
        write(general, "")
        page.locator("#live-reading").click()
        told(page)
        expect(page).to_have_title("Live third")
        assert "/versions/" not in page.url
    finally:
        # A route handler is a live browser resource after the verdict stops depending
        # on it, and an abandoned one hangs context teardown even when every assertion
        # passed.
        release_the_held_read()
        page.unroute("**/api/state*")


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
    authored `needed` condition and its obligation, so incorporating its state into source
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
    expect(draft.get_by_role("textbox")).to_have_js_property("value", provided)
    draft_control(page, "save", "ledger-cargo").click()
    round_trip(page)
    expect_obligations_answered(page, "1/5")
    expect(page.locator(".lf-fp-on-user")).to_have_attribute(
        "aria-label", re.compile(r"^On me: [1-9]")
    )

    honoring = re.sub(
        r'<lf-draft id="ledger-cargo" needed>.*?</lf-draft>',
        # The authoring contract adds only the opening LF consumed by HTML.
        f'<lf-draft id="ledger-cargo"><pre>\n{provided}</pre></lf-draft>',
        COMMAND_HUB_PAGE,
        flags=re.DOTALL,
    )
    # A draft without `needed` is optional editing, not an obligation framed by an `lf-ask`.
    honoring = honoring.replace(
        '<lf-ask id="decision-ledger-fixture-region">',
        '<div id="decision-ledger-fixture-region">',
    ).replace(
        "</lf-draft>\n              </lf-ask>",
        "</lf-draft>\n              </div>",
    )
    assert '<lf-ask id="decision-ledger-fixture-region">' not in honoring
    stamp_page(d, honoring, "input absorbed")
    wait_for_revision(page, 2)
    # The saved answer remains in the reviewable obligation inventory after the source
    # drops `needed`; it is completed, not newly owed to the user.
    expect_obligations_answered(page, "1/5")
    expect(page.locator(".lf-fp-on-user")).to_have_attribute(
        "aria-label", re.compile(r"^On me: [1-9]")
    )
    expect(page.locator("#ledger-cargo")).not_to_have_attribute("needed")
    expect(page.locator("#ledger-cargo")).not_to_have_attribute("data-lf-user-override")
    expect(page.locator("#ledger-fixture")).to_be_visible()
    draft_control(page, "edit", "ledger-cargo").click()
    expect(page.locator("#ledger-cargo").get_by_role("textbox")).to_have_js_property(
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
    seat = goal.locator(":scope > .lf-thread-seat")
    write(seat.get_by_role("textbox"), "Finish the current hunk, then park here.")
    with sending(page, "the held send"):
        seat.get_by_role("button", name="Send & pause", exact=True).click()
    expect(goal).to_have_attribute("data-lf-held")
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

    seat.get_by_role("textbox", name="Reply", exact=True).scroll_into_view_if_needed()
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
    expect(goal).to_have_attribute("data-lf-held", root["id"])
    # The reply landed where the user was looking, so it waits for them to open it.
    seat.get_by_role("button", name="1 new reply").click()
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
        page.locator(".lf-fp-settle").click()
    expect(goal).not_to_have_attribute("data-lf-held")
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
    expect(goal).to_have_attribute("data-lf-held", root["id"])
    assert [
        event["kind"]
        for event in events_model.read_events(d)
        if event["kind"] in {"comment", "resolve", "undo"}
    ] == ["comment", "resolve", "undo"]


@pytest.mark.parametrize("fresh", [False, True], ids=["patched", "fresh"])
def test_activity_held_targets_follow_the_current_document(browser, serve, fresh):
    """Held history keeps its words and seat, but never a departed destination."""

    def source(destination, executable=""):
        return leaf_page(
            "Route",
            '<h1>Route history</h1><lf-activity id="feed"></lf-activity>' + destination,
        ).replace("</head>", executable + "</head>")

    route = """<lf-ask id="route-ask"><h2>Which route?</h2>
      <lf-options id="route" choose>
        <lf-option id="route-fast">Fast path</lf-option>
        <lf-option id="route-slow">Slow path</lf-option>
      </lf-options></lf-ask>"""
    url = live_url(serve(source(route)))
    page = open_page(browser, url)
    page.locator("#route-fast .lf-pick").click()
    round_trip(page)
    page.locator("#feed .lf-activity-news").click()
    row = page.locator("#feed .lf-activity-row", has_text="chose")
    target = row.locator(".lf-activity-target")
    expect(target).to_have_attribute("href", "#route")
    page.keyboard.press("Tab")
    expect(target).to_be_focused()
    before = row.bounding_box()
    what = row.locator(".lf-activity-what").text_content()
    label = target.text_content()
    fragment = page.evaluate("location.hash")
    executable = '<script type="module">void 0;</script>' if fresh else ""
    if fresh:
        page.add_init_script("""
          window.activityTargetFrames = [];
          let remaining = 180;
          function readTarget() {
            const target = document.querySelector('#feed a.lf-activity-target');
            if (target) window.activityTargetFrames.push({
              href: target.getAttribute('href'), label: target.textContent,
              parsed: document.readyState !== 'loading'
            });
            if (--remaining) requestAnimationFrame(readTarget);
          }
          requestAnimationFrame(readTarget);
        """)

    stamp_page(serve.page_dir, source("", executable), "Remove the route")
    wait_for_revision(page, 2)
    wait_until_ready(page)
    expect(row.locator(".lf-activity-what")).to_have_text(what)
    expect(target).to_have_text(label)
    expect(target).not_to_have_attribute("href", "#route")
    expect(row.get_by_role("link")).to_have_count(0)
    expect(target).to_be_focused()
    assert row.bounding_box() == before
    target.press("Enter")
    assert page.evaluate("location.hash") == fragment
    target.click()
    assert page.evaluate("location.hash") == fragment
    if fresh:
        frames = page.evaluate("window.activityTargetFrames")
        assert frames
        assert all(
            frame["href"] is None and frame["label"] == label for frame in frames
        )

    # A destination returning is current capability too; held labels stay historical.
    restored = '<section id="route"><h2>A different route heading</h2></section>'
    restored_executable = '<script type="module">void 1;</script>' if fresh else ""
    blocked = []
    if fresh:
        page.route("**/leaf.js", lambda route: blocked.append(route))
    stamp_page(
        serve.page_dir, source(restored, restored_executable), "Restore a destination"
    )
    if fresh:
        page.wait_for_function("""() => document.readyState === 'interactive' &&
          document.querySelector('#feed a.lf-activity-target')?.getAttribute('href') === '#route'""")
        assert blocked, "startup module must remain pending during the parsed drawing"
        assert page.locator("body").get_attribute("data-lf-presented") is None
        page.unroute("**/leaf.js")
        for route in blocked:
            route.continue_()
    wait_for_revision(page, 3)
    expect(target).to_have_attribute("href", "#route")
    expect(row.locator(".lf-activity-what")).to_have_text(what)
    expect(target).to_have_text(label)
    expect(target).to_be_focused()
    assert row.bounding_box() == before
    if fresh:
        frames = page.evaluate(
            "window.activityTargetFrames.filter(frame => frame.parsed)"
        )
        assert frames
        assert all(
            frame["href"] == "#route" and frame["label"] == label for frame in frames
        )
    target.press("Enter")
    expect(page).to_have_url(re.compile(r"#route$"))
    expect(page.locator("#route")).to_be_in_viewport()


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
