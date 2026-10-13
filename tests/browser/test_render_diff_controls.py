"""Diff controls share canonical fields and preserve the compact source reader."""

from html import escape

import pytest
from leaf import data as data_model
from leaf.render_checks import one_frame, rendered
from leaf_dev.example_data import patch_manifest
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    reported_browser_errors,
)


@pytest.mark.parametrize("bound", [False, True], ids=["inline", "bound"])
def test_a_patch_that_failed_stays_failed_when_its_diff_returns(browser, serve, bound):
    """A refusal stands while its patch is unchanged: a diff that leaves the page and
    returns, as document reconciliation moves it, renders its patch again only when
    the departure cut that rendering short, and does not tell the author twice. A bound
    patch returns through its data subscription, an inline one through the widget."""
    one = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n"
    diff = (
        '<lf-diff id="d-bad" source="bad-patch"><pre></pre></lf-diff>'
        if bound
        else f'<lf-diff id="d-bad"><pre>\n{one}{one}</pre></lf-diff>'
    )
    url = serve(leaf_page("bad diff", f'<h1 id="t">Bad</h1>\n{diff}'))
    if bound:
        data_model.cmd_data_set(serve.page_dir, "bad-patch", one + one)
    page = open_page(browser, url)
    expect(page.locator("#d-bad .lf-error")).to_contain_text("repeats file path")
    returned = page.evaluate("""async () => {
        const diff = document.getElementById('d-bad');
        const failure = diff.querySelector('.lf-error');
        const parent = diff.parentNode;
        const next = diff.nextSibling;
        diff.remove();
        await new Promise((resolve) => setTimeout(resolve));
        parent.insertBefore(diff, next);
        for (let i = 0; i < 3; i++) await new Promise(requestAnimationFrame);
        return diff.querySelector('.lf-error') === failure;
    }""")
    assert returned, "the returning diff rendered its refused patch again"
    errors = consume_browser_errors(page, '<lf-diff id="d-bad"> failed: ')
    assert len(errors) == 1, errors


def test_an_expanded_diff_file_can_retry_its_failed_chunk_in_place(browser, serve):
    """A recovered network has a visible route to retry the expanded file."""
    url = serve(
        leaf_page(
            "Retry a file diff",
            '<h1>Retry a file diff</h1><lf-diff id="patch" source="review-patch" '
            'collapsed><pre></pre></lf-diff><button id="after" '
            'style="position:fixed;right:1rem;bottom:1rem">After diff</button>',
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        patch_manifest("""diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1 +1 @@
-enabled = False
+enabled = True
"""),
    )
    context = browser.new_context()
    attempts = []
    pending = []

    def fail_until_success(route):
        attempts.append(route.request.url)
        if len(attempts) == 1:
            route.abort("failed")
        elif len(attempts) < 4:
            pending.append(route)
        else:
            route.continue_()

    context.route("**/api/deferred*", fail_until_success)
    with context.expect_event(
        "requestfailed", lambda request: "/api/deferred" in request.url
    ) as failed:
        page = open_page(browser, url, context=context)
    summary = page.locator("lf-diff summary")
    summary.focus()
    assert failed.value.failure == "net::ERR_FAILED"
    expect(page.locator("lf-diff .lf-error")).to_contain_text(
        "That file's diff failed to load: Failed to fetch"
    )
    reported_browser_errors(page, "Failed to load resource: net::ERR_FAILED")
    assert len(attempts) == 1

    retry = page.get_by_role("button", name="Retry")
    assert retry.count() == 1, "the expanded file needs an in-place retry control"

    # A native Enter retry stays focused while in flight. Another Enter is ignored
    # until it resolves, so it cannot start a parallel deferred request.
    page.keyboard.press("Tab")
    expect(retry).to_be_focused()
    page.keyboard.press("Enter")
    holding(page, pending, 1, "the first deferred retry")
    assert len(attempts) == 2 and len(pending) == 1
    expect(retry).to_have_attribute("aria-disabled", "true")
    expect(retry).to_be_focused()
    page.keyboard.press("Enter")
    assert len(attempts) == 2 and len(pending) == 1
    with page.expect_event(
        "requestfailed", lambda request: "/api/deferred" in request.url
    ) as failed:
        pending.pop().abort("failed")
    assert failed.value.failure == "net::ERR_FAILED"
    reported_browser_errors(page, "Failed to load resource: net::ERR_FAILED")
    retry = page.get_by_role("button", name="Retry")
    # Network failure precedes the new error paint. The old pending button can
    # still hold focus, so wait for the replacement to accept another activation.
    expect(retry).not_to_have_attribute("aria-disabled", "true")
    expect(retry).to_be_focused()

    # If the user tabs away during another pending retry, its failure must leave
    # focus at the newer control instead of restoring the old Retry button.
    page.keyboard.press("Enter")
    holding(page, pending, 1, "the second deferred retry")
    assert len(attempts) == 3 and len(pending) == 1
    expect(retry).to_have_attribute("aria-disabled", "true")
    page.keyboard.press("Tab")
    after = page.get_by_role("button", name="After diff")
    expect(after).to_be_focused()
    with page.expect_event(
        "requestfailed", lambda request: "/api/deferred" in request.url
    ) as failed:
        pending.pop().abort("failed")
    assert failed.value.failure == "net::ERR_FAILED"
    reported_browser_errors(page, "Failed to load resource: net::ERR_FAILED")
    expect(page.get_by_role("button", name="Retry")).not_to_have_attribute(
        "aria-disabled", "true"
    )
    expect(after).to_be_focused()

    # A successful retry falls back to the file disclosure when its error control
    # is replaced by rendered source.
    retry = page.get_by_role("button", name="Retry")
    page.keyboard.press("Shift+Tab")
    expect(retry).to_be_focused()
    with page.expect_response(
        lambda response: "/api/deferred" in response.url and response.status == 200
    ):
        page.keyboard.press("Enter")
    expect(
        page.locator('lf-diff [data-lf-datum=\'["config.py","new",1]\']')
    ).to_contain_text("enabled = True")
    expect(page.locator("lf-diff summary")).to_be_focused()
    assert len(attempts) == 4


@pytest.mark.parametrize("defer_first", [False, True])
def test_phone_diff_headers_keep_distinguishing_parent_folder_readable(
    browser, serve, defer_first
):
    """Repeated basenames remain identifiable before tapping their source rows."""
    names = ("dispatch", "improving-instructions", "todos")
    patch = "".join(
        f"diff --git a/.claude/skills/{name}/CLAUDE.md b/.claude/skills/{name}/CLAUDE.md\n"
        f"--- a/.claude/skills/{name}/CLAUDE.md\n+++ b/.claude/skills/{name}/CLAUDE.md\n"
        "@@ -1 +1 @@\n-old = True\n+new = True\n"
        for name in names
    )
    url = serve(
        leaf_page(
            "Identify sources",
            "<h1>Identify sources</h1>"
            '<lf-diff id="patch" source="patch-data" collapsed><pre></pre></lf-diff>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    context = browser.new_context(
        viewport={"width": 360, "height": 800}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    page.evaluate("document.fonts.ready")
    if defer_first:
        # Hold the first file's preparation after the native disclosure opens.
        # This orders insertion after the tap's settled frame without a delay.
        page.evaluate("""() => {
      const diff = document.querySelector('#patch');
      const original = diff.prepareEntry;
      let release;
      window.lfDiffPreparation = {
        release: () => release(),
      };
      diff.prepareEntry = async function(...args) {
        if (args[1].path.endsWith('/dispatch/CLAUDE.md')) {
          const held = new Promise(resolve => { release = resolve; });
          window.lfDiffPreparationStarted = true;
          await held;
        }
        return original.apply(this, args);
      };
    }""")
    headers = page.locator("#patch .lf-diff-head")
    expect(headers).to_have_count(3)
    for head, name in zip(headers.all(), names, strict=True):
        reading = head.evaluate("""head => {
          const parent = head.querySelector('.lf-diff-dir-parent');
          const base = head.querySelector('.lf-diff-base');
          const prefix = new Range();
          prefix.setStart(parent.firstChild, 0);
          prefix.setEnd(parent.firstChild, Math.min(3, parent.textContent.length - 1));
          const ink = prefix.getBoundingClientRect();
          const box = parent.getBoundingClientRect();
          return {text: parent.textContent, shown: getComputedStyle(parent).opacity,
            prefix: ink.width + parseFloat(getComputedStyle(parent, '::before').width), room: box.width,
            base: base.textContent, baseCut: base.scrollWidth > base.clientWidth};
        }""")
        assert reading["text"] == name + "/"
        assert reading["shown"] == "1"
        assert reading["room"] >= reading["prefix"], reading
        assert reading["base"] == "CLAUDE.md" and not reading["baseCut"], reading
        head.tap()
        file = head.locator("..")
        expect(file).to_have_attribute("open", "")
        if defer_first and name == "dispatch":
            page.wait_for_function("window.lfDiffPreparationStarted === true")
            one_frame(page)
            page.evaluate("window.lfDiffPreparation.release()")
        expect(file.locator("[data-line]").last).to_contain_text("new = True")
        head.tap()
        expect(file).not_to_have_attribute("open", "")


def test_opening_diff_keeps_rendering_pending_until_lazy_source_arrives(browser, serve):
    """A disclosure's registered source preparation is part of its gesture's render."""
    patch = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-old
+new
diff --git a/other.md b/other.md
--- a/other.md
+++ b/other.md
@@ -1 +1 @@
-old
+new
"""
    url = serve(
        leaf_page(
            "Lazy source",
            '<lf-diff id="patch" source="patch-data" collapsed><pre></pre></lf-diff>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    page = open_page(browser, url)
    held = []
    page.route("**/vendor/syntax/markdown.js", lambda route: held.append(route))
    head = page.locator(".lf-diff-head").first
    head.click()
    holding(page, held, 1, "the lazy Markdown grammar")
    try:
        one_frame(page)
        assert not page.evaluate(
            "Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean)"
        ), "registered source preparation must keep rendering pending"
    finally:
        held[0].continue_()
    rendered(page)
    expect(head.locator("..").locator("[data-line]").last).to_contain_text("new")


PATH_PARTS = """head => {
  const path = head.querySelector('.lf-diff-path');
  const room = path.getBoundingClientRect();
  return [...path.querySelectorAll('.lf-diff-dir, .lf-diff-base')].map(part => {
    const words = new Range();
    words.selectNodeContents(part);
    const own = part.getBoundingClientRect();
    return {text: part.textContent, shown: getComputedStyle(part).opacity !== '0',
      whole: [...words.getClientRects()].every(ink =>
        ink.left >= Math.max(own.left, room.left) - 0.5
        && ink.right <= Math.min(own.right, room.right) + 0.5)};
  });
}"""


def test_printed_diff_rows_hold_their_whole_paths(browser, serve):
    """Paper gives no title, focus or press back to a cut path, so a printed file row
    wraps to show every folder and the whole name; the screen row still cuts them."""
    paths = (
        "plugins/worktrunk/skills/worktrunk/references/configuration/hooks/README.md",
        "src/picker/snapshots/wt__commands__picker__items__tests__unified_diff.snap",
    )
    patch = "".join(
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        for path in paths
    )
    url = serve(
        leaf_page(
            "Printed paths",
            f'<lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>',
        )
    )
    # A5's printable width under the print dialog's default margins.
    context = browser.new_context(viewport={"width": 483, "height": 800})
    page = open_page(browser, url, context=context)
    page.evaluate("document.fonts.ready")
    heads = page.locator("#patch .lf-diff-head")
    expect(heads).to_have_count(len(paths))
    screen = [head.evaluate(PATH_PARTS) for head in heads.all()]
    assert all(
        not all(part["shown"] and part["whole"] for part in parts) for parts in screen
    ), f"each path must be cut on screen, or print proves nothing: {screen}"
    page.emulate_media(media="print")
    one_frame(page)
    for head, path in zip(heads.all(), paths, strict=True):
        parts = head.evaluate(PATH_PARTS)
        assert "".join(part["text"] for part in parts) == path
        assert all(part["shown"] and part["whole"] for part in parts), (path, parts)


def test_closed_manifest_rows_judge_their_evidence_before_showing_metadata(
    browser, serve
):
    """Closed rows derive copy, mode and counts from checked Git evidence."""
    patch = """diff --git a/original.py b/copied.py
similarity index 75%
copy from original.py
copy to copied.py
old mode 100644
new mode 100755
--- a/original.py
+++ b/copied.py
@@ -1 +1 @@
-old = True
+new = True
"""
    corruptions = {
        "copy": patch.replace("copy from original.py", "copy from wrong.py"),
        "move": patch.replace("copy from original.py\n", ""),
        "mode": patch.replace("old mode 100644\n", ""),
        "hunk": patch.replace("@@ -1 +1 @@", "@@ -2 +2 @@").replace(
            "+new = True", "+new = True\n+lost"
        ),
    }
    ids = ["valid", *corruptions]
    url = serve(
        leaf_page(
            "Closed evidence",
            "<h1>Closed evidence</h1>"
            + "".join(
                f'<lf-diff id="{name.lower()}" source="source-{name.lower()}" collapsed><pre></pre></lf-diff>'
                for name in ids
            ),
        )
    )
    for name in ids:
        manifest = patch_manifest(patch)
        if name != "valid":
            manifest["files"][0]["patch"] = corruptions[name]
        data_model.cmd_data_set(serve.page_dir, f"source-{name.lower()}", manifest)
    page = open_page(browser, url)
    rendered(page)
    for name in corruptions:
        host = page.locator(f"#{name.lower()}")
        expect(host.locator(".lf-error")).to_contain_text("cannot be shown")
        expect(host.locator(".lf-diff-stat")).to_have_count(0)
        expect(host.locator(".lf-diff-evidence")).to_have_count(0)
        expect(host.locator(".lf-diff-source-path")).to_have_count(0)
    consume_browser_errors(
        page, *(f'<lf-diff id="{name.lower()}"> failed: ' for name in corruptions)
    )
    good = page.locator("#valid")
    expect(good.locator("summary")).to_contain_text("copied")
    expect(good.locator("summary")).to_contain_text("+1")
    expect(good.locator("details")).not_to_have_attribute("open", "")
    expect(good.locator("[data-line]")).to_have_count(0)
    assert not any(
        "pierre-diffs.esm.js" in resource["name"]
        for resource in page.evaluate(
            "performance.getEntriesByType('resource').map(({name}) => ({name}))"
        )
    ), "checking closed evidence must not load the textual renderer"
    good.locator("summary").click()
    expect(good.locator("[data-line]").last).to_contain_text("new = True")
