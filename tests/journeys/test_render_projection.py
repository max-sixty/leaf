"""Live version, report, replay, and projection tests."""

import json
import re
import threading

import pytest
from click.testing import CliRunner
from interact_support import (
    ROOT,
    add_test_widget,
    append_carried_log_record,
    append_command,
    running_http_server,
    trial_family,
    working,
)
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import render_checks as render_checks_model
from leaf import structure as structure_model
from leaf.registry import storage as registry_storage
from leaf.render_checks import rendered, wait_until_ready
from leaf.render_gate import version as render_gate_model
from leaf.render_gate.preview import preview_server
from leaf.render_gate.readings import DevtoolsIssues
from playwright.sync_api import expect
from render_cases_interaction import (
    ACTIONS_IN_FORCE,
    COMMAND_HUB_EXAMPLE,
    COMMAND_HUB_PAGE,
    IN_FORCE_PAGE,
    LIVE_V1,
    LIVE_V2,
    LIVE_V3,
    REF_PAGE,
    RELATIVE_WIDGET_MODULE,
    RELATIVE_WIDGET_PAGE,
    THREAD_ASKS,
    TWO_HOLDER_PAGE,
    TWO_HOLDER_SPARE_PAGE,
    drifting_widget,
    executable_revision,
    live_url,
)
from render_cases_layout import (
    banner_control,
)
from render_cases_navigation import (
    painted,
    source_revision,
)
from render_harness import (
    EXAMPLE_PACKAGES,
    IMPORTER_CARD,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    TOKEN,
    consume_browser_errors,
    draft_control,
    example_media,
    expect_asks_answered,
    expect_banner_control_offered,
    holding,
    leaf_page,
    names,
    open_page,
    opened_tab,
    page_comment,
    page_registry,
    panel_settled,
    resized,
    root_overflow,
    round_trip,
    sending,
    stamp_page,
    ticked,
    told,
    undo,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_call_diff_projects_stable_commentable_rows(browser, serve):
    authored = leaf_page(
        "call diff",
        """
<h1 id="title">Request call change</h1>
<pre id="code-surface">reference code surface</pre>
<lf-call-diff id="request-calls" source="request-call-diff" diff="patch"></lf-call-diff>
<lf-diff id="patch" source="review-patch" collapsed><pre></pre></lf-diff>
""",
    )
    url = serve(authored, packages=("diff",))
    call_diff = """calldiff diff main → feature

  Limiter.bucket_key(self, request)  gateway/limits.py:38
+ └─ if request.token  gateway/limits.py:40
"""
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
    data_model.cmd_data_set(serve.page_dir, "request-call-diff", call_diff)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        {
            "files": [
                {
                    "path": "gateway/limits.py",
                    "operation": "modify",
                    "hunkCount": 1,
                    "binary": False,
                    "additions": 4,
                    "deletions": 2,
                    "patch": patch,
                }
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
    expect(widget.locator(".lf-call-toggle")).to_have_text("Collapse all")
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
    expect(widget.locator(".lf-call-toggle")).to_have_text("Expand all")
    widget.locator(".lf-call-toggle").click()
    expect(group).to_have_attribute("open", "")
    expect(widget.locator(".lf-call-toggle")).to_have_text("Collapse all")
    file_row = page.locator("#patch .lf-diff-file").first
    expect(file_row).to_have_attribute("data-lf-datum", '["gateway/limits.py","file"]')
    expect(file_row).to_have_attribute(
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
    expect(page.get_by_role("button", name="Comment on selection")).to_be_visible()

    updated = (
        call_diff.replace(
            "calldiff diff main → feature", "calldiff diff main → feature-2"
        )
        + """
  Limiter.secondary(self)  gateway/limits.py:50
+ └─ return True  gateway/limits.py:51
"""
    )
    data_model.cmd_data_set(serve.page_dir, "request-call-diff", updated)
    told(page)
    expect(group).to_have_attribute("open", "")
    expect(groups).to_have_count(2)
    expect(groups.nth(1)).not_to_have_attribute("open", "")
    expect(widget.locator(".lf-call-toggle")).to_have_text("Expand all")
    expect(lines.nth(2).locator(".lf-call-location")).to_have_text(
        "gateway/limits.py:40"
    )
    assert lines.nth(2).evaluate("el => el.__callIdentity") is True
    assert page.evaluate("() => getSelection().toString()") == selected
    page.get_by_role("button", name="Comment on selection").click()
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
    expect(page.locator(".lf-thread .lf-quote").first).to_have_text(
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
        "calldiff diff main → shifted\n  shifted_call()  gateway/limits.py:102",
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

    data_model.cmd_data_set(serve.page_dir, "request-call-diff", "not CallDiff output")
    told(page)
    expect(widget.locator(":scope > .lf-call-invalid")).to_contain_text(
        "the first line must be a CallDiff diff header"
    )

    data_model.cmd_data_set(
        serve.page_dir,
        "request-call-diff",
        "calldiff diff main → feature\n+ └─ orphan()  gateway/limits.py:40",
    )
    told(page)
    expect(widget.locator(":scope > .lf-call-invalid")).to_contain_text(
        "line 2 appears before a changed root"
    )

    data_model.cmd_data_set(
        serve.page_dir,
        "request-call-diff",
        "calldiff diff main → feature\n  missing_location()",
    )
    told(page)
    expect(widget.locator(":scope > .lf-call-invalid")).to_contain_text(
        "line 2 has no source location; capture --locs output"
    )
    expect(widget.locator(".lf-call-root-location, .lf-call-group")).to_have_count(0)

    resized(page, 390, 900)
    assert root_overflow(page) == 0


def test_visual_review_guides_one_typed_still_run(browser, serve):
    authored = leaf_page(
        "visual review run",
        """
<h1 id="title">Visual review</h1>
<p id="claim">The candidate makes run status visible without changing navigation.</p>
<lf-visual-review id="visual-run" source="docs-run"></lf-visual-review>
""",
    )
    media = {
        "/media/051bee487bfb5d13.png": (
            example_media() / "051bee487bfb5d13.png"
        ).read_bytes(),
        "/media/a99a1b63048502d0.png": (
            example_media() / "a99a1b63048502d0.png"
        ).read_bytes(),
        "/media/3cf0e3efe80c6b01.png": (
            example_media() / "3cf0e3efe80c6b01.png"
        ).read_bytes(),
    }
    url = live_url(serve(authored, packages=("visual-review",), media=media))
    capture = {
        "observedAt": "2026-09-10T10:30:00-07:00",
        "browser": "Chrome",
        "browserVersion": "140.0.7339.80",
        "viewport": {"width": 900, "height": 373},
        "deviceScaleFactor": 2,
        "colorScheme": "light",
        "locale": "en-US",
        "timezone": "America/Los_Angeles",
    }
    record = {
        "title": "Docs navigation · candidate 7b921ac",
        "base": {"revision": "4c118aa", "url": "https://base.example/rev/"},
        "candidate": {
            "revision": "7b921ac",
            "url": "https://candidate.example/rev",
        },
        "cases": [
            {
                "id": "run-list",
                "title": "Run list status",
                "path": "/runs?owner=max",
                "action": "Open the run list.",
                "result": "Each row exposes its current status.",
                "classification": "changed",
                "capture": capture,
                "focus": {"x": 120, "y": 80, "width": 640, "height": 220},
                "before": "/media/051bee487bfb5d13.png",
                "after": "/media/a99a1b63048502d0.png",
                "traceUrl": "https://trace.example/runs/17",
            },
            {
                "id": "run-detail",
                "title": "Run detail navigation",
                "path": "/runs/17",
                "action": "Open the first run.",
                "result": "The detail link and surrounding layout stay stable.",
                "classification": "clean",
                "capture": capture,
                "before": "/media/051bee487bfb5d13.png",
                "after": "/media/a99a1b63048502d0.png",
            },
        ],
    }
    data_model.cmd_data_set(serve.page_dir, "docs-run", record)
    source = serve.page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</main>",
            '<lf-visual-review id="visual-pinned" source="docs-run-reviewed">'
            "</lf-visual-review></main>",
        )
    )
    # The pinned run is a second source that nothing rewrites.
    data_model.cmd_data_set(serve.page_dir, "docs-run-reviewed", record)
    page = open_page(browser, url)
    case_thread = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 2,
            "text": "Keep this note beside the run-list evidence.",
            "anchor": {
                "section": "visual-run",
                "datum": "run-list",
                "source": "docs-run",
                "source_revision": source_revision(serve.page_dir, "docs-run"),
            },
        },
    )
    told(page)
    widget = page.locator("#visual-run")
    cases = widget.locator(".lf-vr-case")
    first = cases.filter(has=page.locator(".lf-vr-case-title", has_text="Run list"))
    second = cases.filter(has=page.locator(".lf-vr-case-title", has_text="Run detail"))

    expect(widget.locator(".lf-vr-title")).to_have_text(record["title"])
    case_select = widget.locator(".lf-vr-case-select")
    expect(case_select.locator("wa-option")).to_have_count(2)
    expect(first).to_be_visible()
    expect(second).to_be_hidden()
    expect(first).to_have_attribute("data-lf-projection", "visual-run")
    expect(first).to_have_attribute("data-lf-datum", "run-list")
    origin = first.evaluate("node => JSON.parse(node.dataset.lfOrigin)")
    assert origin["source"] == "docs-run"
    assert origin["path"] == ["cases", 0]
    expect(first.locator("lf-shot")).to_have_attribute(
        "before", "/media/051bee487bfb5d13.png"
    )
    expect(first.locator("lf-shot")).to_have_attribute(
        "after", "/media/a99a1b63048502d0.png"
    )
    expect(first.locator("lf-shot img")).to_have_count(2)
    expect(
        first.locator(f'.lf-page-thread[data-thread="{case_thread["id"]}"]')
    ).to_have_count(1)
    expect(first.get_by_role("link", name="Open base")).to_have_attribute(
        "href", "https://base.example/rev/runs?owner=max"
    )
    expect(first.get_by_role("link", name="Open candidate")).to_have_attribute(
        "href", "https://candidate.example/rev/runs?owner=max"
    )
    expect(first.get_by_role("link", name="Open trace")).to_have_attribute(
        "href", "https://trace.example/runs/17"
    )
    expect(first.locator(".lf-vr-browser")).to_have_text("Chrome 140.0.7339.80")
    expect(first.locator(".lf-vr-viewport")).to_have_text("900 × 373 · 2×")
    expect(first.locator(".lf-vr-appearance")).to_have_text(
        "light · en-US · America/Los_Angeles"
    )
    expect(first.locator(".lf-vr-focus")).to_have_text("120, 80 · 640 × 220 CSS px")

    expect(widget).to_have_attribute("data-inspection-mode", "compare")
    expect(widget).to_have_attribute("data-inspection-scale", "fit")
    expect(widget).to_have_attribute("data-inspection-scope", "focus")
    widget.get_by_text("Inspect comparison", exact=True).click()
    scope = widget.get_by_role("radiogroup", name="Scope")
    expect(scope).to_be_visible()
    expect(widget.get_by_role("radio", name="Focus change")).to_be_checked()
    expect(widget.get_by_role("radio", name="Compare")).to_be_checked()
    expect(widget.get_by_role("radio", name="Compare")).to_have_css(
        "box-shadow", "none"
    )
    opacity = first.locator(".lf-vr-opacity").get_by_role("slider", include_hidden=True)
    expect(opacity).to_be_disabled()
    expect(opacity).to_be_hidden()

    expect(widget).to_have_attribute("data-compare-layout", "stack")
    assert first.locator(".lf-shot-frame-label").evaluate_all(
        "nodes => nodes.map(node => node.dataset.label)"
    ) == ["Base · Candidate below", "Candidate"]
    expect(first.locator("lf-shot")).to_have_attribute("data-lf-shot-controls", "off")
    expect(first.locator(".lf-shotflip")).to_be_hidden()
    expect(first.locator(".lf-shotcap[aria-keyshortcuts]")).to_have_count(0)
    expect(first.locator(".lf-shotflip[aria-keyshortcuts]")).to_have_count(0)
    frames = first.locator(".lf-shotframe")
    before_box, after_box = frames.evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect())"
    )
    assert after_box["top"] >= before_box["bottom"]

    shot_host = first.locator(".lf-vr-shot-host")
    expect(first.locator("lf-shot")).to_have_attribute("data-lf-shot-crop", "true")
    crop = frames.first.evaluate(
        """frame => {
          const box = frame.getBoundingClientRect();
          const label = frame.querySelector('.lf-shot-frame-label').getBoundingClientRect();
          const imageNode = frame.querySelector('img');
          const image = imageNode.getBoundingClientRect();
          const labelHit = document.elementFromPoint(
            label.left + label.width / 2,
            label.top + label.height / 2,
          );
          return {
            box,
            label,
            image,
            objectViewBox: getComputedStyle(imageNode).objectViewBox,
            transform: getComputedStyle(imageNode).transform,
            labelVisible: labelHit?.closest('.lf-shot-frame-label') === frame.querySelector('.lf-shot-frame-label'),
          };
        }"""
    )
    assert crop["labelVisible"]
    assert crop["image"]["top"] == pytest.approx(crop["label"]["bottom"], abs=1)
    assert crop["objectViewBox"] == "inset(160px 280px 146px 240px)"
    assert crop["transform"] == "none"
    resized(page, 1200, 480)
    expect(widget).to_have_attribute("data-compare-layout", "stack")
    before_box, after_box = frames.evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect())"
    )
    assert after_box["top"] >= before_box["bottom"]
    resized(page, 1200, 900)
    expect(widget).to_have_attribute("data-compare-layout", "stack")

    # In flow the stage is as tall as the view it shows, whatever part of the page
    # the window shows.
    def stage_height():
        return shot_host.evaluate("node => node.getBoundingClientRect().height")

    def scrolled(top):
        page.evaluate(f"() => document.scrollingElement.scrollTo(0, {top})")

    compare_height = stage_height()
    scrolled("document.scrollingElement.scrollHeight")
    assert stage_height() == pytest.approx(compare_height, abs=1)
    widget.get_by_role("radio", name="Flip").evaluate("node => node.click()")
    expect(widget).to_have_attribute("data-inspection-mode", "flip")
    flip_height = stage_height()
    assert flip_height < compare_height
    scrolled(0)
    assert stage_height() == pytest.approx(flip_height, abs=1)
    widget.get_by_role("radio", name="Compare").evaluate("node => node.click()")
    assert stage_height() == pytest.approx(compare_height, abs=1)

    widget.get_by_role("radio", name="Full frame").click()
    expect(widget).to_have_attribute("data-inspection-scope", "full")
    expect(first.locator("lf-shot")).to_have_attribute("data-lf-shot-crop", "false")
    marker = frames.first.evaluate(
        "frame => getComputedStyle(frame, '::after').getPropertyValue('content')"
    )
    assert marker == '""'

    widget.get_by_role("radio", name="100%").click()
    expect(widget).to_have_attribute("data-inspection-scale", "actual")
    assert shot_host.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    captured_width = first.locator("lf-shot img").first.evaluate(
        "image => image.getBoundingClientRect().width"
    )
    assert captured_width == pytest.approx(900, abs=1), (
        "100% is the captured CSS viewport width, not the retina bitmap width: "
        f"{captured_width}px"
    )

    focus_button = widget.get_by_role("radio", name="Focus change")
    focus_button.focus()
    focus_button.press("Enter")
    expect(focus_button).to_be_focused()
    expect(widget).to_have_attribute("data-inspection-scope", "focus")
    expect(first.locator("lf-shot")).to_have_attribute("data-lf-shot-crop", "true")
    focused_width = frames.first.evaluate(
        "frame => frame.getBoundingClientRect().width"
    )
    assert focused_width == pytest.approx(642, abs=1)

    widget.get_by_role("radio", name="Fit").click()
    widget.get_by_role("radio", name="Flip").click()
    expect(first.locator("lf-shot[data-lf-shot-controls]")).to_have_count(0)
    expect(first.locator(".lf-shot-frame-label")).to_have_count(0)
    widget.get_by_role("radio", name="Overlay").click()
    expect(widget).to_have_attribute("data-inspection-mode", "overlay")
    expect(opacity).to_be_enabled()
    expect(opacity).to_be_visible()
    expect(first.locator(".lf-vr-opacity-control")).to_contain_text("Candidate opacity")
    expect(first.locator(".lf-vr-opacity-value")).to_have_css("white-space", "nowrap")
    opacity.press("ArrowLeft")
    opacity.press("ArrowLeft")
    opacity.press("ArrowLeft")
    expect(widget.locator(".lf-vr-opacity-value")).to_have_text("35%")
    expect(widget.locator(".lf-vr-opacity-value")).not_to_have_attribute(
        "data-lf-said", ""
    )
    before_box, after_box = frames.evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect())"
    )
    assert abs(before_box["left"] - after_box["left"]) < 1
    assert abs(before_box["width"] - after_box["width"]) < 1
    expect(first.locator('.lf-shotframe[data-lf-state="after"]')).to_have_css(
        "opacity", "0.35"
    )

    with sending(page, "the first visual disposition"):
        first.get_by_role("button", name="Looks right").click()
    expect(first).to_have_attribute("data-disposition", "looks-right")
    expect(widget.locator(".lf-vr-progress")).to_have_text("1 of 2 cases reviewed")

    next_button = widget.get_by_role("button", name="Next", exact=True)
    page.keyboard.press("g")
    next_box = next_button.bounding_box()
    assert next_box
    go_to_hints = page.locator(".lf-go-to-hint[data-lf-hint-code]")
    expect(go_to_hints).not_to_have_count(0)
    next_code = go_to_hints.evaluate_all(
        """(hints, target) => hints.map(hint => {
          const box = hint.getBoundingClientRect();
          const dx = box.x + box.width / 2 - (target.x + target.width / 2);
          const dy = box.y + box.height / 2 - (target.y + target.height / 2);
          return {code: hint.dataset.lfHintCode, distance: dx * dx + dy * dy};
        }).sort((left, right) => left.distance - right.distance)[0].code""",
        next_box,
    )
    page.keyboard.type(next_code)
    expect(first).to_be_hidden()
    expect(second).to_be_visible()
    expect(second.locator(".lf-vr-trace-link")).to_be_hidden()
    expect(scope).to_be_hidden()
    second.get_by_text("Capture details", exact=True).click()
    expect(second.locator(".lf-vr-detail:has(.lf-vr-focus)")).to_have_count(0)
    second.get_by_text("Capture details", exact=True).click()
    expect(widget).to_have_attribute("data-inspection-scope", "full")
    expect(case_select).to_have_js_property("value", "run-detail")
    expect(case_select).not_to_be_focused()
    page.keyboard.press("g")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    page.keyboard.press("Escape")

    inserted_case = record["cases"][1] | {
        "id": "run-middle",
        "title": "Inserted run case",
        "path": "/runs/middle",
    }
    changed = record | {
        "base": {"revision": record["base"]["revision"]},
        "cases": [
            record["cases"][0],
            inserted_case,
            record["cases"][1]
            | {
                "result": "The detail route remains stable after the rerun.",
                "capture": capture | {"observedAt": "2026-10-08T10:00:00-07:00"},
            },
        ],
    }
    original = second.element_handle()
    data_model.cmd_data_set(serve.page_dir, "docs-run", changed)
    told(page)
    expect(second.locator(".lf-vr-observed")).to_have_attribute(
        "datetime", "2026-10-08T10:00:00-07:00"
    )
    expect(first.locator(".lf-vr-observed")).to_have_attribute(
        "datetime", "2026-09-10T10:30:00-07:00"
    )
    expect(second.locator(".lf-vr-base-link")).to_be_hidden()
    expect(second.locator(".lf-vr-base-link")).not_to_have_attribute("href")
    expect(second.get_by_role("link", name="Open candidate")).to_have_attribute(
        "href", "https://candidate.example/rev/runs/17"
    )
    expect(page.locator("#visual-pinned .lf-vr-base-link").first).to_be_visible()

    expect(second.locator(".lf-vr-result")).to_have_text(
        "The detail route remains stable after the rerun."
    )
    expect(
        page.locator("#visual-pinned .lf-vr-result").filter(
            has_text="The detail link and surrounding layout stay stable."
        )
    ).to_have_count(1)
    assert original.evaluate(
        "node => node === document.querySelector('.lf-vr-case[data-lf-datum=\"run-detail\"]')"
    )
    expect(second).to_be_visible()
    expect(first).to_have_attribute("data-disposition", "looks-right")
    expect(widget).to_have_attribute("data-inspection-mode", "overlay")
    expect(widget.locator(".lf-vr-opacity")).to_have_js_property("value", 35)
    case_select.click()
    widget.get_by_role("option", name="Run list", exact=False).click()
    next_button.click()
    expect(case_select).to_have_js_property("value", "run-middle")
    expect(next_button).to_be_focused()

    resized(page, 390, 900)
    assert root_overflow(page) == 0
    widget.get_by_role("radio", name="Compare").click()
    expect(
        widget.locator(".lf-vr-case:not([hidden]) .lf-shot-frame-label").first
    ).to_be_visible()
    page.emulate_media(media="print")
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    expect(widget.locator(".lf-vr-queue-region")).to_be_hidden()
    expect(widget.locator(".lf-vr-dispositions").first).to_be_hidden()
    expect(widget.locator(".lf-vr-inspector")).to_be_hidden()
    expect(widget.locator(".lf-shot-frame-label").first).to_be_hidden()
    before_box, after_box = first.locator(".lf-shotframe").evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect())"
    )
    assert after_box["top"] >= before_box["bottom"]
    page.emulate_media(media="screen")

    invalid_focus = changed | {
        "cases": [
            changed["cases"][0]
            | {"focus": {"x": 120, "y": 300, "width": 640, "height": 220}},
            *changed["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "docs-run", invalid_focus)
    told(page)
    case_select.click()
    widget.get_by_role("option", name="Run list", exact=False).click()
    expect(widget.locator(".lf-error")).to_contain_text(
        "focus 120,300 640×220 CSS px falls outside its captured images"
    )
    consume_browser_errors(
        page,
        "focus 120,300 640×220 CSS px falls outside its captured images",
    )
    expect(case_select).to_be_visible()
    unequal_pair = changed | {
        "cases": [
            changed["cases"][0]
            | {
                "focus": {"x": 20, "y": 80, "width": 300, "height": 150},
                "after": "/media/3cf0e3efe80c6b01.png",
            },
            *changed["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "docs-run", unequal_pair)
    told(page)
    expect(widget.locator(".lf-error")).to_contain_text(
        "before is 1800px wide and after is 780px"
    )
    consume_browser_errors(page, "before is 1800px wide and after is 780px")
    corrected = changed | {
        "cases": [
            changed["cases"][0]
            | {
                "capture": capture | {"viewport": capture["viewport"] | {"width": 1000}}
            },
            *changed["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "docs-run", corrected)
    told(page)
    expect(widget.locator(".lf-error")).to_have_count(0)
    expect(first.locator("lf-shot img")).to_have_count(2)
    widget.get_by_role("radio", name="Full frame").click()
    widget.get_by_role("radio", name="100%").click()
    decoded_css_width = first.locator("lf-shot img").first.evaluate(
        "image => image.naturalWidth / 2"
    )
    # The widget lays out a scale change in a rendering callback after the click.
    rendered(page)
    assert first.locator("lf-shot img").first.evaluate(
        "image => image.getBoundingClientRect().width"
    ) == pytest.approx(decoded_css_width, abs=1), (
        "captured CSS coordinates must render against the decoded image, not stale viewport metadata"
    )
    assert (
        first.locator("lf-shot").evaluate(
            "shot => shot.captureGeometry.images[0].width / 2"
        )
        == decoded_css_width
    )
    with sending(page, "a corrected visual disposition"):
        first.get_by_role("button", name="Needs work").click()
    expect(first).to_have_attribute("data-disposition", "needs-work")


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
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    editor = page.get_by_role("textbox", name="Reply", exact=True)
    words = "Keep my reply while questions arrive."
    write(editor, words)
    editor.evaluate(
        "node => { window.heldReply = node; node.setSelectionRange(5, 9); }"
    )
    editor.press("Tab")
    send = page.locator(".lf-thread-send").filter(visible=True)
    expect(send).to_be_focused()

    (serve.page_dir / "index.html").write_text(second)
    expect(page.locator(".lf-queue")).to_have_text("Questions: 1")
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
    expect_banner_control_offered(page.locator(".lf-latest-chip"))
    assert editor.evaluate("node => node === window.heldReply")
    send.press("Shift+Tab")
    expect(editor).to_be_focused()
    editor.press("Escape")
    page.wait_for_function("window.heldReply === undefined")
    expect(page.locator(".lf-queue")).to_have_text("Questions: 1")


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
    # route available through the latest-version chip.
    (serve.page_dir / "index.html").write_text(executable_revision(LIVE_V2, "two"))
    told(page)
    expect(page).to_have_title("Live first")
    expect_banner_control_offered(page.locator(".lf-latest-chip"))

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

        # The chip's own read remains independent of the background read held above. It
        # moves the page to the second revision, then the third revision is written
        # before the held request is released.
        # Opening More to reach the chip puts the card away, keeping its words.
        chip = banner_control(page, ".lf-latest-chip")
        chip.click()
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
        generation = json.loads((serve.page_dir / "registry.json").read_text())[
            "$layer"
        ]["generation"]
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


def test_the_render_gate_reports_a_server_that_stops_answering(
    browser, tmp_path, monkeypatch
):
    """A read that never comes back is a sentence, not a hang.

    Every document the gate reads used to be fetched inside the page, and
    `page.evaluate` sends the driver no timeout at all — measured, an evaluate
    awaiting a fetch that never answers is still running at 200s. So a server that
    accepted a request and then went quiet left `page check --render` running with
    nothing printed, which is the one failure a user cannot tell from slowness: the
    gate stopping is loud, and the gate never stopping looks like a slow machine.

    Stall the gate's second read of this version, after its first read delivered the
    page. Stalling that first read would wedge navigation instead and report the
    banner the gate never saw. The deadline is shortened here because the number is
    not the subject, the bound is.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(render_gate_model, "SERVED_TIMEOUT_MS", 1500)
    d = tmp_path / "page"
    assert CliRunner().invoke(cli_model.cli, ["page", "init", str(d)]).exit_code == 0
    for _ in (1, 2):
        stamp_page(d, REPLY_HOST_PAGE, "t")

    delivered = threading.Event()
    asked = threading.Event()
    release = threading.Event()

    class Stalls(http_model.PageEndpoint):
        """Delivers the document, then accepts and drops the gate's file read."""

        def _get(self):
            if self.path.startswith("/versions/v2.html"):
                if not delivered.is_set():
                    delivered.set()
                elif not asked.is_set():
                    asked.set()
                    release.wait()
                    return None
                else:
                    # The next render attempt begins after the bounded read timed out.
                    release.set()
            return super()._get()

    httpd = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0), http_model.page_endpoint(d, TOKEN, endpoint=Stalls)
    )
    with running_http_server(httpd):
        try:
            failures = render_gate_model.render_version(
                browser,
                f"http://127.0.0.1:{httpd.server_address[1]}/versions/v2.html?t={TOKEN}",
            ).failures
        finally:
            release.set()

    assert asked.is_set(), "nothing ever asked for the stalled file, so nothing stalled"
    assert failures and all(f.code == "server-stopped" for f in failures), (
        f"a wedged server has to come back as a failure, and this came back as {failures}"
    )


def test_render_allows_authored_state_the_log_replays_over(browser, serve):
    """A revision may change its baseline while the recorded decision still paints.

    Historical state is a complete-state fold, not permission to edit. Placement
    belongs to the new authored container when its contents change.
    """
    url = serve(REPLAYED_PAGE)
    d = serve.page_dir
    for widget, action, detail in [
        ("approach", "choose", {"value": ["opt-shim"]}),
        ("work", "move", {"unit": "card-importer", "value": "col-done", "rank": "0i"}),
    ]:
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )

    # v2 changes the baseline pick and the card's column order. Rendering remains
    # valid: the user's choice paints over the baseline; the new order is authored.
    # A version that honors either decision, or says nothing of one, is the weaker
    # case of the same rule.
    contradicted = REPLAYED_PAGE.replace(
        'id="opt-stage"', 'id="opt-stage" chosen'
    ).replace(IMPORTER_CARD, "")
    contradicted = contradicted.replace(
        "</lf-card></lf-column>", f"</lf-card>{IMPORTER_CARD}</lf-column>"
    )
    document = structure_model.SourceDocument(contradicted)
    with preview_server(d, document, files_model.latest_revision(d) + 1) as at:
        assert render_gate_model.render_version(browser, at).failures == []
    stamp_page(d, contradicted, "t")
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    expect(page.locator("#opt-stage")).not_to_have_attribute("chosen", "")


def test_the_render_gate_applies_every_action_in_force_a_second_time(
    browser, serve, tmp_path, monkeypatch
):
    """Absoluteness is what makes a fold a fold, and it is the one thing about a widget
    module no reading of a rendered page can see: a relative implementation renders
    perfectly and costs the user their gesture later, on the poll that replays it. So
    the gate applies each action in force again and asks what moved, and the page's
    composed vocabulary has nothing to do — a card placed where it already is, a pick set to
    what it already holds, a body assigned the words it already reads.

    The corpus cannot say this on its own: `test_page_fixture_renders` serves every page
    under a log holding one note, so the fold is empty there and the reading passes
    without applying anything. This page is the log the examples haven't got, and the
    floor is that the state in force covers every verb the registry declares — a verb
    added without an event here fails rather than going unexercised.

    Beside that clean vocabulary stands the bug-back for the module contract's first
    state rule, and for both readings the gate takes of it: a project widget that steps
    its count from the count it reads and appends its caption to the caption it reads,
    right once and wrong every time after. Its findings name the widget, both verbs, and
    what moved, and they are the only findings. Two verbs on one unit exercise the two
    readings that catch different things: the count is markup, so `shallowSigs` sees
    it; the caption is text, which that signature excludes on purpose, so only the
    verb's declared record form reaches it."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-tally", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    declarations["lf-tally"]["properties"]["count"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    declarations["lf-tally"].setdefault("required", []).append("count")
    declarations["lf-tally"]["x-content"] = "data"
    declarations["lf-tally"]["x-example"] = (
        '<lf-tally id="tally-example" count="0"><pre>Nothing yet.</pre></lf-tally>'
    )
    # The registry holds a widget-unit verb to the attribute a version retracts a
    # decision with, so a state channel arrives with its way out of one.
    declarations["lf-tally"]["properties"]["restated"] = {"type": "boolean"}
    declarations["lf-tally"]["x-state"] = {
        "step": {
            "unit": "widget",
            "record": {"kind": "value", "attr": "count"},
        },
        "caption": {
            "unit": "widget",
            "record": {"kind": "body"},
        },
    }
    registry_path.write_text(json.dumps(declarations, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-tally.js").write_text(RELATIVE_WIDGET_MODULE)
    tallies = RELATIVE_WIDGET_PAGE[
        RELATIVE_WIDGET_PAGE.index(
            '<lf-tally id="tally-fitted"'
        ) : RELATIVE_WIDGET_PAGE.rindex("</lf-tally>") + len("</lf-tally>")
    ]
    url = serve(
        IN_FORCE_PAGE.replace("</main>", tallies + "</main>"),
        packages=(*EXAMPLE_PACKAGES, ROOT / "tests/fixtures/packages/work", "./.leaf"),
    )
    relative_actions = [
        ("tally-fitted", "step", {"value": "3"}),
        ("tally-fitted", "caption", {"value": "Two greys at the north feeder."}),
    ]
    for widget, action, detail in [*ACTIONS_IN_FORCE, *relative_actions]:
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )
    # The agent channel through its own door, which is the only way a report is
    # written: both channels replay, so both rest on the same contract. A roster row
    # carries recorded state and a generated clause under one verb, so re-applying has
    # to leave both where they stand. Splitting the clause into another verb would make
    # the two reports compete for one fold key.
    for widget, verb, fields in [
        ("ab-baffles", "status", ["value=done"]),
        ("ab-wren", "state", ["value=blocked", "text=waiting on the fixture"]),
    ]:
        sent = CliRunner().invoke(
            cli_model.cli,
            ["page", "report", str(serve.page_dir), widget, verb, *fields],
        )
        assert sent.exit_code == 0, sent.output

    page = open_page(browser, url)
    in_force_ids = sorted(
        {widget for widget, _action, _detail in [*ACTIONS_IN_FORCE, *relative_actions]}
        | {"ab-baffles", "ab-wren"}
    )
    in_force = page.evaluate(
        """async ids => {
          const {widgetController} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          return ids.flatMap(id => {
            const widget = document.getElementById(id);
            const state = widgetController(widget).read().state;
            return Object.entries(state).flatMap(([verb, value]) =>
              (value.units ? Object.values(value.units) : [value])
                .filter(({action}) => action)
                .map(({action}) => [widget.id, widget.localName, verb, action]));
          });
        }""",
        in_force_ids,
    )
    page.close()
    registry = registry_storage.load_registry(serve.page_dir)
    declared = {
        (tag, verb)
        for tag, entry in registry.items()
        if tag.startswith("lf-")
        for verb in entry.get("x-state", {})
    }
    assert {(tag, verb) for _id, tag, _key, verb in in_force} == declared, (
        "the gate applies the state in force, so a declared verb missing from it is a "
        f"verb nothing here re-applies: page holds {in_force}, registry declares "
        f"{sorted(declared)}"
    )
    assert {
        (key, action) for widget, _tag, key, action in in_force if widget == "ab-pick"
    } == {("choose", "choose"), ("answer", "answer"), ("add", "add")}
    failures = render_gate_model.render_version(browser, url).failures
    assert [
        (f.scheme, f.at, f.values["changed"])
        for f in failures
        if f.code == "relative-render"
    ] == [
        ("light", "<lf-tally id=tally-fitted>", ["tally-fitted", "body text"]),
        ("light", "<lf-tally id=tally-seen>", ["body text"]),
    ], failures
    # The relative widget's appended caption is its own fault in other readings too;
    # the current vocabulary beside it leaves the gate nothing to say.
    assert all(names(f, "lf-tally") for f in failures), failures


def test_a_widget_standing_out_of_place_is_a_page_the_gate_reports(
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


def test_the_render_gate_reads_a_page_that_has_finished_arriving(
    browser, serve, tmp_path, monkeypatch
):
    """A page finishes twice, and the second ending arrives moving.

    `lf-upgraded` is the first: every widget upgraded, the geometry final. The first
    read starts earlier but its answer cannot apply before that boundary, so a gate
    reading there can still read the authored page — here, a widget standing 120px
    out of place with its words over the paragraphs below it.
    `lf-applied` is the second, and the frame it lands in is the first frame of the
    move it describes: a read that brings nothing presents the authored page
    deliberately, so the replay after it crosses the presentation boundary and moves
    rather than teleports.

    Both windows are load-shaped — a busy server, a few hundred milliseconds — which
    is how this page passed at a desk and reported words drawn over words under a
    full suite. Holding the action back until the page's first read has answered, and
    the gate's own read until the action is in, makes the window the same every run:
    the page reads as broken for about three seconds, and the gate must have nothing
    to say about it. Either wait on its own leaves this failing."""
    # For the page directory and its vendored layer; this test serves it itself.
    serve(
        drifting_widget(tmp_path, monkeypatch), packages=(*EXAMPLE_PACKAGES, "./.leaf")
    )
    landed = []
    # The action is in the log and the gate may read it. Both halves of the window are
    # this one fact, so the hold below and the append are the same statement made twice.
    arrived = threading.Event()
    expired = []
    settle = {
        "kind": "action",
        "author": "user",
        "revision": 1,
        "widget": "drift-note",
        "action": "settle",
        "detail": {"value": "0"},
    }

    class TheLogArrivesLate(http_model.PageEndpoint):
        """The action reaches the log between the page's first read and the gate's.

        A page whose first read brings nothing is presented on the authored markup
        deliberately, so the replay that follows is past the presentation boundary
        and moves rather than teleports. The page's read is told from the gate's own
        reading of the same document by the Referer a page fetch carries and an
        APIRequestContext does not: the action goes in behind the page's read, and
        the gate's is held until it has, so the gate always sees a log with the action
        in it and always has a caught-up stamp to wait for.

        Holding it is the whole arrangement rather than a margin. The page stamps
        itself upgraded without awaiting its first read, so the gate is free to reach
        `/api/state` while that read is still in flight — and under a busy server it
        does, whereupon it counts an empty log, waits for nothing, and reads the page
        mid-move. That is this test's own failure and not the gate's."""

        def _get(self):
            state_read = self.path.startswith("/api/state")
            page_read = state_read and self.headers.get("Referer")
            # Bounded, and inside the gate's own deadline for a served document: a
            # runtime that stopped reading state at startup is named by the assertion
            # below rather than by a gate whose server appeared to stop answering.
            held_for = render_checks_model.SERVED_TIMEOUT_MS / 2000
            if state_read and not page_read and not arrived.wait(held_for):
                expired.append(self.path)
            answer = super()._get()
            if page_read and not landed:
                landed.append(self.headers["Referer"])
                append_command(serve.page_dir, settle)
                arrived.set()
            return answer

    httpd = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0),
        http_model.page_endpoint(serve.page_dir, TOKEN, endpoint=TheLogArrivesLate),
    )
    with running_http_server(httpd):
        late = f"http://127.0.0.1:{httpd.server_address[1]}/versions/v1.html?t={TOKEN}"
        failures = render_gate_model.render_version(browser, late).failures
    # The window first, because the gate's verdict on a window that never opened says
    # nothing: an empty log is a page with nothing to replay and nothing to report.
    assert landed and "/versions/v1.html" in landed[0], (
        "the action never went in behind the page's first read, so the window this "
        f"rests on never opened: {landed}"
    )
    assert not expired, (
        "the gate's read was released by the 10s bound rather than by the append, so "
        f"it read a log with nothing in it to wait for: {expired}"
    )
    assert failures == []


def test_a_moved_card_identifies_its_user_origin_across_tabs(browser, serve):
    """A move outlives its notice: the card the user moved stays explicitly
    identified as overriding authored placement in the tab that moved it and in a fresh
    replay alike, because the runtime compares the page's state against the version's
    own snapshot rather than remembering who wrote what. The runtime's quiet word and
    Page Map row carry that origin while the grip names the move and its destination.
    The card the move displaced stays unmarked — the log named one card, not its
    neighbours. The honoring version says the state itself, so on it the
    disagreement and both renderings are gone."""
    url = serve(REPLAYED_PAGE)
    page = open_page(browser, url)

    # The keyboard gesture takes the same #send path as a drag. The sender's own
    # replay is a no-op, which is exactly the case the version snapshot covers.
    page.get_by_role("button", name="Move: Wire the importer — Doing").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(page.locator("#card-importer")).to_have_attribute(
        "data-lf-user-override", "1"
    )
    expect(page.locator("#card-notes")).not_to_have_attribute(
        "data-lf-user-override", "1"
    )
    expect(
        page.get_by_role(
            "button",
            name="Move: Wire the importer — Done",
            exact=True,
        )
    ).to_be_visible()

    # A fresh tab reads the same fact from replay alone, and paints both its Page Map
    # reading and its durable spoken state.
    second = open_page(browser, url)
    expect(second.locator("#card-importer")).to_have_attribute(
        "data-lf-user-override", "1"
    )
    expect(second.locator("#card-importer > .lf-quiet")).to_have_text("my change")
    expect(
        second.get_by_role(
            "button",
            name="Move: Wire the importer — Done",
            exact=True,
        )
    ).to_be_visible()
    # The Page Map names the move once: while the agent owes it an answer, under the
    # row saying the move was sent, which is the user's change as much as its own row.
    second.keyboard.press("g")
    second.keyboard.press("Shift+m")
    expect(
        second.get_by_role("button", name=re.compile(r"^Open sent: Sent"))
    ).to_be_visible()
    expect(
        second.get_by_role("button", name=re.compile(r"^Open my change"))
    ).to_have_count(0)
    second.keyboard.press("Escape")
    assert (
        second.locator("#card-importer").evaluate(
            "el => getComputedStyle(el).outlineStyle"
        )
        == "none"
    )
    second.evaluate("""() => {
        window.__originWrites = [];
        new MutationObserver(records => {
            window.__originWrites.push(...records.map(record => record.target.id));
        }).observe(document.getElementById('work'), {
            subtree: true, attributes: true, attributeFilter: ['data-lf-user-override'],
        });
    }""")
    ticked(second)
    assert second.evaluate("() => window.__originWrites") == [], (
        "an unchanged heartbeat rewrote the origin marks and woke the board's "
        "card-name observer"
    )

    # The honoring version authors the card where the user put it; replay
    # no-ops against it and the mark has nothing left to say.
    d = serve.page_dir
    honored = REPLAYED_PAGE.replace(IMPORTER_CARD, "").replace(
        'label="Done">', f'label="Done">{IMPORTER_CARD}'
    )
    stamp_page(d, honored, "t")
    third = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(third.locator("#col-done #card-importer")).to_be_visible()
    # Absence only counts once replay has decided every action.
    third.wait_for_function("() => document.body.dataset.lfApplied === '1'")
    expect(third.locator("#card-importer")).not_to_have_attribute(
        "data-lf-user-override", "1"
    )
    expect(third.locator("#card-importer > .lf-quiet")).to_have_count(0)
    expect(
        third.get_by_role("button", name="Move: Wire the importer — Done", exact=True)
    ).to_be_visible()


def test_a_settled_third_party_holder_wears_the_layers_mark(
    browser, serve, tmp_path, monkeypatch
):
    """A settlement is the layer's rendering of the log's decision, never a module
    obligation: the trial's module is the product's starter, which only defines the
    element — it never subscribes to its controller and supplies no renderState — and
    once its decision replays the holder wears
    data-lf-state, the retired slot is marked and hidden by the theme's one generic
    rule, and the quote anchored in it detaches instead of pointing at words the
    page's reading has dropped. The mark and the hide used to be each holder
    module's own duty, stated in the module contract and the key table and enforced
    nowhere, and the first family that forgot would have split the page's reading
    from the file's in silence. Later the layer painted them only through a
    controller the module subscribed to, which left the same duty under another
    name. The second half drives it all back out: the fold
    keeps the last surviving action per verb and unit, so a decision on an outcome
    that settles nothing displaces the one before it, and the mark, the marker and
    the hide follow it."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    module = (tmp_path / ".leaf" / "widgets" / "lf-trial.js").read_text()
    assert "subscribe" not in module, "the holder's module must leave the mark to Leaf"

    url = serve(
        TWO_HOLDER_PAGE,
        anchored=[("th-next", "warmed on the first request")],
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
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
    expect(page.locator("#th-cache lf-proposed")).to_be_hidden()
    expect(page.locator(".lf-thread .lf-quote").first).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "the quote matched inside a slot the logged decision retired: nothing wrote "
        "the settlement mark for a module that doesn't"
    )
    assert not any(
        event["kind"] == "reanchor"
        for event in events_model.read_events(serve.page_dir)
    ), (
        "reading an unchanged revision must not persist a temporary decision's detachment"
    )
    page.close()

    # The mark follows the fold out as well as in: the file's current state is the
    # last surviving action per verb and unit, so a decision on an outcome that
    # settles nothing displaces the one before it, and a mark left in place would
    # silence a slot the log has handed back.
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "decide",
            "detail": {"outcome": "pause"},
        },
    )
    page = open_page(browser, url)
    assert page.locator("#th-cache").get_attribute("data-lf-state") is None
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()
    expect(page.locator(".lf-thread .lf-quote").first).not_to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") != "", (
        "the displaced decision's slot is back on the page, so its quote must "
        "anchor again"
    )


def test_the_render_gate_holds_a_settled_slot_to_the_logs_decision(
    browser, serve, tmp_path, monkeypatch
):
    """Bug-back for the settlement reading, in both directions. The bare family first
    proves the gate accepts a holder that brings nothing of its own — the layer's
    default hide is the whole of its disappearance. Then two independent faults go in
    together. The one generic hide rule is stripped from the vendored theme, standing
    in for whatever re-shows a retired slot (a later layer's rule outranking the
    default, a module re-showing what it folded): the words stay on screen where the
    user can select what no comment can anchor to, and the gate must say so. And the
    vendored module marks every trial after the controller publishes: on the undecided
    spare that is a settlement the log never decided, styling as settled words the
    page still reads, and the gate must say that too. Both failures render perfectly, which
    is why each is put back deliberately."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)

    url = serve(TWO_HOLDER_SPARE_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
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
    assert render_gate_model.render_version(browser, url).failures == []

    hide = "[data-lf-retired] { display: none; }"
    vendored = serve.page_dir / "theme.css"
    css = vendored.read_text()
    assert css.count(hide) == 1
    vendored.write_text(css.replace(hide, ""))
    module = serve.page_dir / "widgets" / "lf-trial.js"
    module.write_text(
        """import {keeps, once, widgetController} from "/runtime/widget-api.js";
export default class extends HTMLElement {
  #controller;
  #presented;
  #stop;
  connectedCallback() {
    this.#controller ??= widgetController(this);
    if (!once(this)) {
      this.#subscribe();
      return;
    }
    this.#subscribe();
  }
  disconnectedCallback() {
    this.#stop?.();
    this.#stop = undefined;
    this.#presented?.disconnect();
    this.#presented = undefined;
  }
  #subscribe() {
    this.#stop ??= this.#controller.subscribe(reading => this.#markAfterPresentation(reading));
    this.#markAfterPresentation(this.#controller.read());
  }
  #markAfterPresentation(reading) {
    if (!reading.state) return;
    if (document.body.dataset.lfPresented === "1") {
      keeps(this, "data-lf-state", "shelve");
      return;
    }
    this.#presented ??= new MutationObserver(() => {
      if (document.body.dataset.lfPresented !== "1") return;
      this.#presented.disconnect();
      this.#presented = undefined;
      if (this.isConnected) keeps(this, "data-lf-state", "shelve");
    });
    this.#presented.observe(document.body, {
      attributes: true, attributeFilter: ["data-lf-presented"],
    });
  }
};
"""
    )
    stamp_page(
        serve.page_dir,
        (serve.page_dir / "index.html").read_text(),
        "capture the visible settled slot and the false settlement mark",
    )
    failures = render_gate_model.render_version(browser, live_url(url)).failures
    assert any(
        failure.code == "retired-slot"
        and failure.at == "<lf-trial id=th-cache>"
        and (failure.values["outcome"], failure.values["slot"])
        == ("shelve", "lf-proposed")
        for failure in failures
    ), failures
    assert any(
        failure.code == "settlement-mark"
        and failure.at == "<lf-trial id=th-spare>"
        and (failure.values["mark"], failure.values["outcome"]) == ("shelve", None)
        for failure in failures
    ), failures


def test_a_message_reference_travels_or_says_it_cant(browser, serve, one_user):
    """A message can point at the page with a fragment link, and following it is a trip
    to the element it names: the tab holding the target opens, and where Threads
    covers a narrow window, the panel the link was pressed in gives the page back,
    as a press on the thread's own quote does. Left to the browser, the page moved
    behind the panel and the user was left looking at the reply.

    The half the browser has no answer for is an id this version hasn't got, which
    needs nobody to have erred: a comment outlives the version it was written on.
    Unmarked it reads live, moves nothing, and leaves a fragment nobody holds in the
    URL for the next load to honor. So it wears the detached face a stranded quote
    wears and its press is refused — asserted from a real press, since that refusal
    is the whole of what the runtime does here."""
    url = serve(REF_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-ref",
            "author": "user",
            "revision": 1,
            "text": "See [the bath](#p-bath), [the end](#tail-end), "
            "not [the old note](#gone).",
        },
    )
    page = open_page(browser, url, context=one_user)
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()

    live = page.locator('.lf-msg-body a[href="#p-bath"]')
    expect(live).to_have_attribute("title", "Jump to § p-bath")
    # Collapsed behind the inactive tab until the jump asks for it.
    hidden = re.compile(".*")
    expect(page.locator("#tab-bath")).to_have_attribute("hidden", hidden)
    live.click()
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", hidden)
    page.wait_for_function(
        """() => { const r = document.getElementById('p-bath').getBoundingClientRect();
                   return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""
    )

    # The other half of a link: opened in its own tab it is an arrival, which the
    # browser answers before any widget has upgraded — so the runtime is what aims it
    # (aimArrival). Nothing of this tab travels with it; the new one starts empty.
    # Which sequence opens that tab is the platform's answer rather than one this suite
    # holds — ⌘ where it was written, ⌃ where CI runs it — so the press names the
    # gesture and the browser's target record proves where it opened.
    destination = live.evaluate("link => link.href")
    tab = opened_tab(
        page,
        destination,
        lambda: live.click(modifiers=["ControlOrMeta"]),
    )
    wait_until_ready(tab)
    tab.wait_for_function(
        """() => { const r = document.getElementById('p-bath').getBoundingClientRect();
                   return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""
    )
    tab.close()

    dead = page.locator('.lf-msg-body a[href="#gone"]')
    expect(dead).to_have_class("detached")
    expect(dead).to_have_attribute("aria-disabled", "true")
    expect(dead).to_have_attribute("title", "§ gone isn't in the version shown")
    # force, because locator.click refuses aria-disabled controls and that refusal is
    # the state under test. Nothing will happen, so there is no fact to consume: the
    # press is the edge, and the hash the browser would write is synchronous with it.
    at = page.evaluate("() => document.scrollingElement.scrollTop")
    was = page.url  # the live jump left its own fragment, as a fragment jump does
    dead.click(force=True)
    assert page.url == was, page.url
    assert page.evaluate("() => document.scrollingElement.scrollTop") == at

    # A window too narrow to hold the page beside Threads: the panel covers the page,
    # and the reference is pressed from inside it.
    resized(page, 600, 800)
    panel = page.locator(".lf-thread-panel")
    expect(panel).to_be_visible()
    page.locator('.lf-msg-body a[href="#tail-end"]').click()
    expect(panel).to_be_hidden()
    page.wait_for_function(
        """() => { const r = document.getElementById('tail-end').getBoundingClientRect();
                   const at = document.elementFromPoint(r.left + 4, r.top + r.height / 2);
                   return r.top >= 0 && r.bottom <= innerHeight
                     && document.getElementById('tail-end').contains(at); }"""
    )


def test_a_followed_link_arrives_as_a_fresh_load_of_it_does(browser, serve):
    """A link followed on the page and the same URL opened in a new tab are one
    destination, so they arrive alike: the worker's worktree sits in a disclosure
    the command hub keeps shut, and the browser's own jump landed on nothing where
    the fresh load revealed it. Back then returns the user to where they pressed,
    and Forward to the link's entry after the disclosure is shut again arrives
    there as well: the offset that entry was left at was read over the open
    disclosure, and restoring it over the shut one landed further down the page
    with the worktree still hidden."""
    url = live_url(serve(COMMAND_HUB_EXAMPLE))
    shown = """(id) => { const t = document.getElementById(id);
                         const r = t.getBoundingClientRect();
                         return t.checkVisibility() && r.top >= 0 && r.bottom <= innerHeight
                           && r.top < 150; }"""

    fresh = open_page(browser, f"{url}#tree-w-5")
    fresh.wait_for_function(shown, arg="tree-w-5")
    fresh.close()

    page = open_page(browser, url)
    assert not page.evaluate(shown, "tree-w-5")
    link = page.locator('a[href="#tree-w-5"]')
    link.scroll_into_view_if_needed()
    pressed_at = page.evaluate("() => document.scrollingElement.scrollTop")
    link.click()
    page.wait_for_function(shown, arg="tree-w-5")

    # Shut again and followed again: a press on a link to the fragment the page already
    # shows is still a trip there.
    page.locator("#w-5 > details > summary").click()
    expect(page.locator("#tree-w-5")).to_be_hidden()
    link.click()
    page.wait_for_function(shown, arg="tree-w-5")

    page.go_back()
    page.wait_for_function(
        "(at) => Math.abs(document.scrollingElement.scrollTop - at) <= 1",
        arg=pressed_at,
    )

    page.locator("#w-5 > details > summary").click()
    expect(page.locator("#tree-w-5")).to_be_hidden()
    page.go_forward()
    page.wait_for_function(shown, arg="tree-w-5")


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


def test_a_thread_ask_waits_until_answered(browser, serve):
    """A question in a thread is one of the page's asks — an obligation for the user
        wherever it stands — and `q` reaches it. A single-answer group
    is answered by its pick, as on the page; a `multiple` group's toggles each
    reach the agent live, so only its Done press closes it, as an `answer` action
    x-awaits.answered names for a `multiple` group. The thread's own reply box is the words'
        home, so the group brings no box of its own. `g T` leaves option-digit scope for
    Threads, while `t` reaches a particular thread and `c` reaches its reply box.

    The answer is said once, when the log takes it. The log is where it is recorded,
    and the group's own markup stays the author's: a module writes there only where the
    registry declares the attribute as a record form, which a thread verb can never
    have, no version being able to carry a thread's markup."""
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_ASKS:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    expect_asks_answered(page, "0/2")

    page.keyboard.press("q")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    # The arrival stands on the question's own region; its picks are the next Tab stops.
    expect(page.locator("#tq-one-decision")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#tq-one .lf-pick").first).to_be_focused()
    expect(page.locator(".lf-thread .lf-say")).to_have_count(0)
    reply = page.locator(".lf-thread:has(#tq-one) > .lf-thread-reply leaf-text")
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    expect(page.locator("#tq-one > lf-option[chosen]")).to_have_count(0)
    # The box hands the user back to the thread it belongs to, which is the
    # container it is part of rather than the pick they pressed Enter from.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread:has(#tq-one) > .lf-thread-summary")).to_be_focused()

    page.locator("#tq-redis").click()
    expect_asks_answered(page, "1/2")

    page.locator(".lf-thread:has(#tq-set) .lf-thread-summary").click()
    expect(page.locator("#tq-set .lf-done")).to_be_visible()

    # The group's hairline belongs to the upper neighbour, so the Done press keeps its
    # own frame whole. Drawn by the lower neighbour instead, the divider recolored the
    # press's top edge and left the seam above it to nothing.
    assert page.locator("#tq-set .lf-done").evaluate(
        """el => { const s = getComputedStyle(el);
                   return s.borderTopColor === s.borderBottomColor
                       && s.borderTopWidth === s.borderBottomWidth; }"""
    ), "the group's divider recolors the Done press's own frame"

    # And it butts that hairline, like every other cell of the control. This is the one
    # place the reading is asked at all: the joined-cell readings in the render gate see
    # a served version, and a thread group lives in the panel the runtime builds, so the
    # gate never reaches it. The press was written as a control floating inside the
    # group on a margin of its own, and the theme comment said so — but the group is a
    # grid and had been stretching it to the full column all along, so what the 8px
    # actually drew was a hairline with dead ground under it, on every thread the agent
    # asked a set question in.
    seam = page.locator("#tq-set").evaluate(
        """el => { const done = el.querySelector('.lf-done');
                   const last = done.parentElement.previousElementSibling;
                   const a = last.getBoundingClientRect();
                   const b = done.getBoundingClientRect();
                   return {gap: Math.round((b.top - a.bottom) * 10) / 10,
                           stretched: Math.abs(a.width - b.width) < 1}; }"""
    )
    assert seam["stretched"], (
        "the Done press no longer fills the column, so what follows is about a shape "
        "this test no longer describes"
    )
    assert seam["gap"] < 0.5, (
        f"the hairline above the Done press floats {seam['gap']}px above it"
    )

    page.locator("#tq-logs").click()
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect_asks_answered(page, "1/2")
    with sending(page, "the answer"):
        page.locator("#tq-set .lf-done").click()
    expect_asks_answered(page, "2/2")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-notice")).to_have_text("Marked answered — sent")
    # Said once, by the log's answer. An `answered` attribute on the group said it
    # again in the author's namespace, where the entry admits nothing undeclared and no
    # version could ever have carried a record of a thread verb — invisible to every
    # consumer but shallowSigs, which reads what no version can assert as state one
    # authored.
    assert (
        render_checks_model.evaluate_probe(page, "undeclaredAttrs", page_registry(page))
        == []
    ), "the Done press left an attribute on a widget its entry never declared"
    actions = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert actions[-1]["widget"] == "tq-set" and actions[-1]["action"] == "answer"
    assert actions[-1]["detail"] == {}

    # And a second tab reads it off the log, which is the only place it is written.
    # A user who made no gesture gets the same pressed press and the same closed
    # decision — replay is what puts it there, and the one representation is what replay
    # writes, so there is nothing for a version or a markup copy to fall behind.
    other = open_page(browser, url)
    expect(other.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    expect_asks_answered(other, "2/2")
    assert (
        render_checks_model.evaluate_probe(
            other, "undeclaredAttrs", page_registry(other)
        )
        == []
    ), "replaying the answer left an attribute the entry never declared"
    other.close()

    # Taking back a recordless chrome answer rebuilds its authored controls at once —
    # the withdrawal is the user's own gesture on their own widget. The selection is
    # another verb, so it survives that rebuild. Whether the decision is open again is
    # the log's reading, so the count moves when the withdrawal reaches it and not while
    # it is held at the wire. In particular, the surviving `choose` action cannot answer
    # a `multiple` set, whose x-awaits.answered condition is an `answer` in force.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.keyboard.press("z")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(page.locator("#tq-set-decision > h3")).to_have_text("Which extras apply?")
    expect_asks_answered(page, "2/2")
    holding(page, held, 1, "the thread answer's withdrawal")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect_asks_answered(page, "1/2")

    # The sequence's promise holds from a mark: g T leaves the option's digit scope and
    # reaches Threads, on the title of the thread it shows open. A stray digit there
    # neither travels nor picks; t then c makes the repeatable category walk and the
    # thread-local reply route explicit.
    page.locator(".lf-thread:has(#tq-one) .lf-thread-summary").click()
    page.locator("#tq-one .lf-pick").first.focus()
    # The address toggles the panel it names, so from the panel `q` opened the first
    # completion closes it and the second is the arrival on the open thread.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    title = page.locator(".lf-thread:has(#tq-one) > .lf-thread-summary")
    expect(title).to_be_focused()
    page.keyboard.press("1")
    expect(title).to_be_focused()
    page.keyboard.press("t")
    page.keyboard.press("c")
    expect(page.locator(".lf-thread:has(#tq-set) leaf-text")).to_be_focused()
    sent = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert sent[-1]["action"] == "answer", "the sequence's digit must not pick"


@pytest.mark.parametrize(
    "provided",
    ["ledger_id,amount\n7,42", "\nledger_id,amount\n7,42  \n"],
)
def test_command_hub_an_absorbed_input_stays_fulfilled(browser, serve, provided):
    """An input action discharges the request live; the honoring version removes its
    authored `needed` condition and its Ask, so incorporating its state into source
    cannot turn the input back into a decision."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    draft = page.locator("#ledger-cargo")
    draft_control(page, "edit", "ledger-cargo").click()
    editor = draft.get_by_role("textbox", name="Edit ledger-cargo")
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
    expect_asks_answered(page, "1/5")
    expect(page.locator(".lf-queue")).not_to_have_text("Questions: 0")

    honoring = re.sub(
        r'<lf-draft id="ledger-cargo" needed>.*?</lf-draft>',
        # The authoring contract adds only the opening LF consumed by HTML.
        f'<lf-draft id="ledger-cargo"><pre>\n{provided}</pre></lf-draft>',
        COMMAND_HUB_PAGE,
        flags=re.DOTALL,
    )
    # A draft without `needed` is optional editing, not an ask framed by an `lf-ask`.
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
    # The saved answer remains in the reviewable ask inventory after the source
    # drops `needed`; it is completed, not newly owed to the user.
    expect_asks_answered(page, "1/5")
    expect(page.locator(".lf-queue")).not_to_have_text("Questions: 0")
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
    expect(inline_link.locator(":scope > svg.lf-external-mark")).to_be_visible()
    replied = page.locator("#atlas-record .lf-activity-row").first
    expect(replied.locator(".lf-activity-line")).to_contain_text("Relay replied")
    expect(replied.locator(".lf-activity-excerpt")).to_have_text(
        "The hunk is complete; see the run and park."
    )

    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread[data-id="{root["id"]}"]')
    thread.locator(".lf-thread-summary").click()
    with sending(page, "the resolution"):
        thread.get_by_role("button", name="Resolve thread", exact=True).click()
    expect(goal).not_to_have_attribute("data-lf-held")
    released = page.locator("#atlas-record .lf-activity-row").first
    expect(released).to_contain_text(
        "Me resolved “Finish the current hunk, then park here.”"
    )

    undo(page)
    # Taking the resolution back leaves its row where it stood, marked undone.
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
