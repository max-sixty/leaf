"""Diff controls share canonical fields and preserve the compact source reader."""

import re
from html import escape
from itertools import pairwise

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    reported_browser_errors,
    resized,
    scroll_settled,
    sending,
    told,
)

from leaf import data as data_model
from leaf.render_checks import one_frame, rendered, wait_until_ready
from leaf_dev.example_data import patch_manifest


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_worktree_summaries_share_columns_without_cramping_their_evidence(
    request, serve, engine, subtests
):
    """A list aligns unlike counts and statuses, whether or not a row has a status
    word; its narrow rows still wrap, and opening a worktree gives its evidence the
    whole row rather than one column."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Worktree columns",
                '<h1>Worktree columns</h1><lf-worktree-diffs id="trees">'
                '<lf-worktree id="short" label="Small change" path="/work/short" '
                'status="changed" files="1" additions="1" deletions="1">'
                '<p id="evidence">Evidence can use the complete worktree width.</p>'
                '</lf-worktree><lf-worktree id="long" label="A longer change" '
                'path="/work/long" status="changed" files="123" additions="12345" '
                'deletions="1234" binary-files="2"><p>More evidence.</p></lf-worktree>'
                '<lf-worktree id="unknown" label="Missing checkout" path="/work/missing" '
                'status="unavailable"><p>No snapshot.</p></lf-worktree>'
                '<lf-worktree id="clean" label="Clean checkout" path="/work/clean" '
                'status="clean" files="0" additions="0" deletions="0">'
                "<p>Nothing changed.</p></lf-worktree>"
                "</lf-worktree-diffs>",
            ),
            packages=("diff",),
        ),
    )
    for width in (1280, 720, 640, 390):
        with subtests.test(width=width):
            resized(page, width, 900)
            reading = page.locator("#trees").evaluate("""node => {
              const box = n => n && n.getBoundingClientRect().toJSON();
              return {width: node.clientWidth, viewport: innerWidth,
                rows: [...node.querySelectorAll(':scope > lf-worktree')]
                  .map(host => host.shadowRoot.querySelector('.lf-worktree-summary'))
                  .map(summary => ({
                  box: box(summary), label: box(summary.querySelector('.lf-worktree-identity')),
                  line: parseFloat(getComputedStyle(summary).lineHeight),
                  status: box(summary.querySelector('.lf-worktree-status')),
                  stats: [...summary.querySelector('.lf-worktree-stats').children]
                    .map(n => ({...box(n), content: n.scrollWidth}))
                }))};
            }""")
            rows = reading["rows"]
            assert len(rows) == 4
            # A changed row's counts say it changed; only Clean and Unavailable
            # carry a status word.
            assert [row["status"] is not None for row in rows] == [
                False,
                False,
                True,
                True,
            ]
            for row in rows:
                assert 0 <= row["box"]["left"] < row["box"]["right"] <= width
                if row["status"]:
                    assert row["label"]["right"] <= row["status"]["left"]
                assert all(
                    stat["right"] <= row["box"]["right"] for stat in row["stats"]
                )
                assert all(
                    stat["content"] <= stat["width"] + 1 for stat in row["stats"]
                ), [(stat["width"], stat["content"]) for stat in row["stats"]]
                assert all(
                    before["right"] < after["left"]
                    for before, after in pairwise(row["stats"])
                )
            if reading["width"] > 608:
                if width == 1280:
                    assert all(row["label"]["height"] <= row["line"] for row in rows)
                assert rows[2]["status"]["left"] == pytest.approx(
                    rows[3]["status"]["left"], abs=0.5
                )
                assert rows[0]["stats"][0]["left"] > rows[2]["status"]["right"]
                assert [stat["left"] for stat in rows[0]["stats"]] == pytest.approx(
                    [stat["left"] for stat in rows[1]["stats"][:3]], abs=0.5
                )
            else:
                assert rows[0]["stats"][0]["top"] >= rows[0]["label"]["bottom"]
            summary = page.locator("#short .lf-worktree-summary")
            summary.click()
            try:
                expect(page.locator("#evidence")).to_be_visible()
                evidence = page.locator("#short .lf-worktree-body").bounding_box()
                assert (
                    evidence["width"]
                    > page.locator("#short").bounding_box()["width"] * 0.8
                )
            finally:
                summary.click()


def test_worktree_disclosures_keep_diff_reading_state_and_unknown_totals(
    browser, serve
):
    """Several worktrees stay open independently, retaining each nested reader.

    Missing evidence remains visibly unknown beside known totals; neither an empty
    collection nor a fifth member needs a different browsing surface. A revision to a
    row's evidence edits it in place, and one that rebuilds the rows reopens each the
    reader opened.
    """
    head = "1234567890abcdef1234567890abcdef12345678"
    patch = "".join(
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        for path in ("app.py", "tests.py")
    )
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "Review worktrees",
                    '<h1>Review worktrees</h1><lf-worktree-diffs id="trees">'
                    '<lf-worktree id="drafts" label="retain-drafts" '
                    'branch="codex/retain-drafts" path="/workspace/leaf.retain-drafts" '
                    f'head="{head}" status="changed" files="2" additions="2" deletions="2" open>'
                    "<p>Keep reply drafts keyed by thread</p>"
                    "<aside>Drafts survive changing the selected thread.</aside>"
                    "<details><summary>Snapshot details</summary>"
                    f"<p>Current commit <code>{head}</code></p></details>"
                    f'<lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>'
                    '</lf-worktree><lf-worktree id="missing" label="missing checkout" '
                    'path="/workspace/missing" status="unavailable">'
                    "<p>The supplied checkout could not be read.</p></lf-worktree>"
                    + "".join(
                        f'<lf-worktree id="clean-{index}" label="clean {index}" '
                        f'path="/workspace/clean-{index}" status="clean" files="0" '
                        f'additions="0" deletions="0">'
                        "<p>No changes.</p></lf-worktree>"
                        for index in range(3)
                    )
                    + '</lf-worktree-diffs><lf-worktree-diffs id="empty"></lf-worktree-diffs>'
                    '<lf-file-tree id="files" for="patch"></lf-file-tree>',
                ),
                packages=("diff", "file-tree"),
            )
        ),
    )
    overview = page.locator("#trees .lf-worktree-overview")
    expect(overview).to_contain_text("5 worktrees")
    expect(overview).to_contain_text("2 files")
    expect(overview).to_contain_text("+2")
    expect(overview).to_contain_text("−2")
    expect(overview).to_contain_text("1 unavailable")
    expect(page.locator("#empty").get_by_text("No worktrees supplied")).to_be_visible()
    expect(
        page.locator("#empty").get_by_text("0 files", exact=True)
    ).not_to_be_visible()

    row = page.locator("#drafts .lf-worktree-disclosure")
    summary = row.locator(":scope > summary")
    expect(row).to_contain_text("/workspace/leaf.retain-drafts")
    expect(summary).to_contain_text(head[:8])
    # Counts say a row changed; a word names only what counts can't.
    expect(summary).not_to_contain_text("Changed")
    expect(page.locator("#clean-0 .lf-worktree-summary")).to_contain_text("Clean")
    snapshot = page.locator("#drafts").locator(
        "details", has=page.get_by_text("Snapshot details", exact=True)
    )
    snapshot.locator("summary").click()
    expect(snapshot.locator("code")).to_have_text(head)
    diff = page.locator("#patch")
    search = diff.get_by_label("Filter diff files")
    search.fill("app.py")
    file_summary = diff.locator("summary").filter(has_text="app.py")
    file_summary.click()
    expect(file_summary.locator("..")).not_to_have_attribute("open")

    summary.click()
    expect(search).not_to_be_visible()
    # Tab reaches the next worktree; Enter opens it independently of the first.
    page.keyboard.press("Tab")
    missing_summary = page.locator("#missing .lf-worktree-summary")
    expect(missing_summary).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_text("The supplied checkout could not be read.")).to_be_visible()
    expect(missing_summary).to_contain_text("Unavailable")
    expect(missing_summary).not_to_contain_text("0 files")
    expect(missing_summary).not_to_contain_text("+0")

    summary.click()
    expect(search).to_have_value("app.py")
    expect(file_summary.locator("..")).not_to_have_attribute("open")
    expect(snapshot.locator("code")).to_be_visible()
    expect(page.get_by_text("The supplied checkout could not be read.")).to_be_visible()
    # Editing both the active row and its sibling retains nested reading state, even
    # where the edit changes the evidence's own elements: the row reads none of them.
    source = serve.page_dir / "index.html"
    source.write_text(
        source.read_text()
        .replace(
            "The supplied checkout could not be read.",
            "The supplied checkout is temporarily unavailable.",
        )
        .replace(
            "Keep reply drafts keyed by thread",
            "Keep reply drafts safely keyed by thread",
        )
        .replace("<aside>", '<aside title="Agent commentary">')
    )
    told(page)
    expect(
        page.get_by_text("The supplied checkout is temporarily unavailable.")
    ).to_be_visible()
    expect(page.get_by_text("Keep reply drafts safely keyed by thread")).to_be_visible()
    expect(page.locator("#drafts > aside")).to_have_attribute(
        "title", "Agent commentary"
    )
    expect(search).to_have_value("app.py")
    expect(file_summary.locator("..")).not_to_have_attribute("open")
    expect(snapshot.locator("code")).to_be_visible()
    file_summary.click()
    expect(diff.locator("[data-line]:visible").filter(has_text="new")).to_be_visible()
    fifth_summary = page.locator("#clean-2 .lf-worktree-summary")
    fifth_summary.click()
    expect(page.locator("#clean-2").get_by_text("No changes.")).to_be_visible()
    # A related navigator must reveal the worktree around its destination too.
    summary.click()
    expect(row).not_to_have_attribute("open")
    page.locator("#files").get_by_role("treeitem", name="app.py", exact=True).click()
    expect(row).to_have_attribute("open", "")
    expect(diff.locator("[data-line]:visible").filter(has_text="new")).to_be_visible()
    # A changed snapshot attribute rebuilds the rows; each keeps the reader's choice,
    # whether it closed an authored-open row or opened a closed one.
    summary.click()
    expect(row).not_to_have_attribute("open")
    source.write_text(
        source.read_text().replace(
            'path="/workspace/missing"', 'path="/workspace/gone"'
        )
    )
    told(page)
    expect(page.locator("#missing")).to_contain_text("/workspace/gone")
    expect(row).not_to_have_attribute("open")
    expect(
        page.get_by_text("The supplied checkout is temporarily unavailable.")
    ).to_be_visible()
    expect(page.locator("#clean-2").get_by_text("No changes.")).to_be_visible()
    # A fresh shadow tree restores both an authored-open row the reader closed
    # and an authored-closed row they opened, after startup observation has ended.
    page.reload()
    wait_until_ready(page)
    expect(page.locator("#drafts .lf-worktree-disclosure")).not_to_have_attribute(
        "open"
    )
    expect(page.locator("#clean-2").get_by_text("No changes.")).to_be_visible()


def test_a_visible_datum_takes_over_pending_thread_motion(browser, serve):
    """Readable geometry before a glide starts is no promise of a final landing."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    url = serve(
        leaf_page(
            "Datum arrival",
            '<h1>Review</h1><lf-file-tree id="files" for="patch"></lf-file-tree>'
            f'<lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>'
            '<p style="min-height:2000px">Context</p><p id="far">Far thread.</p>',
        ),
        anchored=[("far", "Far thread.")],
    )
    page = open_page(browser, url)
    datum = page.locator('lf-diff [data-lf-datum=\'["app.py","new",1]\']')
    expect(datum).to_be_in_viewport()
    page.locator("h1").click()
    page.evaluate("""async () => {
      const {navigateToDatum} = await window.__lfWidgetApi();
      const scrollTo = Element.prototype.scrollTo;
      Element.prototype.scrollTo = function(options) {
        const result = scrollTo.call(this, options);
        if (this === document.scrollingElement && options.behavior === 'smooth') {
          Element.prototype.scrollTo = scrollTo;
          queueMicrotask(async () => {
            window.datumArrived = await navigateToDatum(document.querySelector('#files'),
              'for', '["app.py","new",1]');
          });
        }
        return result;
      };
    }""")
    page.keyboard.press("t")
    page.wait_for_function("window.datumArrived !== undefined")
    assert page.evaluate("datumArrived")
    scroll_settled(page)
    expect(datum).to_be_focused()
    box = datum.bounding_box()
    assert 0 <= box["y"] < box["y"] + box["height"] <= page.viewport_size["height"]


@pytest.mark.parametrize("view", ["patch", "file"])
def test_file_tree_opens_current_diff_files_by_pointer_and_keyboard(
    browser, serve, view
):
    """A separately mounted navigator follows a diff's output and travels through
    the ordinary datum route, including reactivation and updated source evidence."""

    def patch(path, value):
        return (
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1 +1 @@\n-old\n+{value}\n"
        )

    url = serve(
        leaf_page(
            "Browse patch files",
            "<h1>Review the importer</h1>"
            '<lf-file-tree id="files" for="patch" data-height="250"></lf-file-tree>'
            f'<lf-diff id="patch" source="change" view="{view}" collapsed></lf-diff>',
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "change",
        patch_manifest(
            patch("src/importer.py", "keep_names = True")
            + patch("tests/importer.py", "assert keep_names")
        ),
    )
    page = open_page(browser, url)
    tree = page.locator("#files")
    row = tree.get_by_role("treeitem", name=re.compile(r"importer\.py")).first
    expect(row).to_be_visible()
    folds = page.locator("#patch .lf-diff-fold")
    if view == "patch":
        expect(folds.first).not_to_have_attribute("open", "")
    else:
        expect(page.locator("#patch .lf-diff-search")).to_have_count(0)
        expect(folds.first).to_have_attribute("open", "")
    # Search narrows the navigator until a file is opened.
    search = tree.get_by_role("textbox")
    search.fill("importer")
    row.click()
    expect(search).to_have_value("")
    expect(search).to_be_focused()
    expect(folds.first).to_have_attribute("open", "")
    expect(folds.first.locator("pre")).to_contain_text("keep_names = True")
    # The same selected file still has an activation route after its patch closes.
    folds.first.locator("summary").click()
    row.click()
    expect(folds.first).to_have_attribute("open", "")
    # A released pointer activation keeps this navigator's keyboard ownership.
    # The tree's folders remain part of its ordinary arrow-key traversal.
    expect(row).to_be_focused()
    search.fill("")
    search.press("Tab")
    expect(row).to_be_focused()
    folder = tree.get_by_role("treeitem", name="src", exact=True)
    page.keyboard.press("ArrowLeft")
    expect(folder).to_be_focused()
    page.keyboard.press("ArrowLeft")
    expect(folder).to_have_attribute("aria-expanded", "false")
    page.keyboard.press("ArrowRight")
    expect(folder).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowDown")
    expect(row).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(tree.get_by_role("treeitem", name="tests", exact=True)).to_be_focused()
    page.keyboard.press("ArrowDown")
    other = tree.get_by_role("treeitem", name=re.compile(r"importer\.py")).last
    expect(other).to_be_focused()
    page.keyboard.press("Enter")
    expect(folds.last).to_have_attribute("open", "")
    expect(folds.last.locator("pre")).to_contain_text("assert keep_names")
    expect(other).to_be_focused()
    if view == "file":
        expect(folds.first).not_to_be_visible()
        expect(folds.last).to_be_visible()
        expect(other).to_have_attribute("aria-selected", "true")
        # Trees confirms a search match onto its row; the row opens its file.
        for path, visible in [
            ("src/importer.py", folds.first),
            ("tests/importer.py", folds.last),
        ]:
            search.fill(path)
            search.press("ArrowDown")
            search.press("Enter")
            expect(search).to_have_value("")
            expect(tree.locator(f'[data-item-path="{path}"]')).to_be_focused()
            page.keyboard.press("Enter")
            expect(visible).to_be_visible()
        folds.last.locator("summary").press("{")
        expect(folds.first).to_be_visible()
        expect(folds.last).not_to_be_visible()
        expect(row).to_have_attribute("aria-selected", "true")
        expect(other).to_have_attribute("aria-selected", "false")
        # Reading new evidence does not take ownership of a selection made while
        # that read is in flight. Hold one boundary to make the ordering exact.
        page.evaluate("""() => {
          const diff = document.getElementById('patch');
          const readEntry = diff.readEntry.bind(diff);
          const held = new Promise(resolve => window.releaseEvidence = resolve);
          diff.readEntry = async (...args) => {
            window.evidenceHeld = true;
            await held;
            return readEntry(...args);
          };
        }""")
        data_model.cmd_data_set(
            serve.page_dir,
            "change",
            patch_manifest(
                patch("src/importer.py", "new_names = True")
                + patch("tests/importer.py", "assert new_names")
            ),
        )
        page.wait_for_function("window.evidenceHeld === true")
        folds.first.locator("summary").press("}")
        page.evaluate("window.releaseEvidence()")
        expect(folds.last.locator("pre")).to_contain_text("assert new_names")
        expect(folds.last).to_be_visible()
        expect(folds.first).not_to_be_visible()
        expect(other).to_have_attribute("aria-selected", "true")
        expect(row).to_have_attribute("aria-selected", "false")
    search.fill("")
    # A source update replaces the producer inventory, rather than leaving stale rows.
    data_model.cmd_data_set(
        serve.page_dir,
        "change",
        patch_manifest(patch("src/reader.py", "preserve_case = True")),
    )
    next_row = tree.get_by_role("treeitem", name=re.compile(r"reader\.py"))
    expect(next_row).to_be_visible()
    expect(
        tree.get_by_role("treeitem", name=re.compile(r"importer\.py"))
    ).to_have_count(0)
    next_row.click()
    expect(page.locator("#patch pre")).to_contain_text("preserve_case = True")
    # Clearing the input clears the derived inventory too.
    data_model.cmd_data_clear(serve.page_dir, "change")
    expect(tree.get_by_role("treeitem")).to_have_count(0)


@pytest.mark.parametrize("scroller", ["pane", "document"])
def test_file_tree_lands_at_the_file_start_after_reading_down(browser, serve, scroller):
    """File activation reveals its first line in document and nested scrollports,
    including a return to the current file after reading further down."""

    def patch(path, lines=100):
        return (
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,{lines} +1,{lines} @@\n"
            + "".join(f"-old line {line}\n+new line {line}\n" for line in range(lines))
        )

    pane = scroller == "pane"
    tree_markup = '<lf-file-tree id="files" for="patch"></lf-file-tree>'
    evidence_markup = (
        '<div id="evidence"><p>Inspect the changes in each file.</p>'
        '<lf-diff id="patch" source="change" view="file"></lf-diff>'
        "</div>"
    )
    regions = (
        '<lf-pane id="files-pane" label="Files"><header>Files</header>'
        + tree_markup
        + '</lf-pane><lf-pane id="patch-pane" label="Patch"><header>Patch</header>'
        + evidence_markup
        + "</lf-pane>"
        if pane
        else '<aside id="files-pane">' + tree_markup + "</aside>" + evidence_markup
    )
    url = serve(
        leaf_page(
            "Navigate a long patch",
            '<header><h1>Review files</h1></header><div id="regions">'
            + regions
            + "</div>"
            + ("" if pane else '<p style="min-height:1200px">Review context</p>'),
            head="""<style>
              #regions { display:grid; grid-template-columns:240px minmax(0,1fr); }
              #files { --lf-pane-top:0px; margin:0; padding:0; }
              #patch { margin:0; }
              aside#files-pane { position:sticky; top:var(--lf-top); align-self:start; }
              aside #files { --lf-file-tree-height:250px; }
            </style>""",
            layout="workspace" if pane else "column",
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "change",
        patch_manifest(
            patch("first.md")
            + patch("second.md")
            + patch("third.md", 3)
            + "diff --git a/z-mode.sh b/z-mode.sh\nold mode 100644\nnew mode 100755\n"
        ),
    )
    context = browser.new_context(viewport={"width": 810, "height": 990})
    page = open_page(browser, url, context=context)
    tree = page.locator("#files")
    evidence = page.locator("#evidence")
    visible = page.locator("#patch .lf-diff-fold:visible")
    expect(visible).to_contain_text("first.md")
    tree_box = tree.bounding_box()
    if pane:
        pane_box = page.locator("#files-pane").bounding_box()
        border = page.locator("#files-pane").evaluate(
            "node => parseFloat(getComputedStyle(node).borderBottomWidth)"
        )
        assert tree_box["y"] + tree_box["height"] == pytest.approx(
            pane_box["y"] + pane_box["height"] - border, abs=0.5
        ), "the navigator must fill the pane without an authored height override"
    second = tree.get_by_role("treeitem", name="second.md", exact=True)

    def scroll_into_file():
        evidence.hover()
        page.mouse.wheel(0, 900)
        page.wait_for_function(
            "document.getElementById('evidence').scrollTop > 400"
            if pane
            else "scrollY > 400"
        )
        scroll_settled(page)

    def starts_below_header():
        page.wait_for_function("""() => {
          const body = document.getElementById('evidence');
          const fold = [...document.getElementById('patch').shadowRoot
            .querySelectorAll('.lf-diff-fold')].find(node => node.checkVisibility());
          const summary = fold?.querySelector('summary');
          const firstLine = fold?.querySelector('.lf-diff-line > [data-line]');
          if (!summary || !firstLine?.textContent.includes('old line 0')) return false;
          const top = summary.getBoundingClientRect().top;
          const pane = body.closest('lf-pane');
          const edge = pane ? body.getBoundingClientRect().top + body.clientTop : 0;
          const bottom = pane ? body.getBoundingClientRect().bottom : innerHeight;
          const line = firstLine.getBoundingClientRect();
          return top >= edge - 1
            && line.top >= summary.getBoundingClientRect().bottom - 1
            && line.bottom <= bottom;
        }""")

    scroll_into_file()
    second.click()
    expect(visible).to_contain_text("second.md")
    starts_below_header()
    expect(second).to_be_focused()
    # A file already selected still has a route back to the start after reading down.
    scroll_into_file()
    second.click()
    starts_below_header()
    expect(second).to_be_focused()
    # Keyboard selection of a much shorter file must reveal its first line too;
    # its pinned heading alone is not evidence that the beginning is visible.
    scroll_into_file()
    second.press("ArrowDown")
    third = tree.get_by_role("treeitem", name="third.md", exact=True)
    expect(third).to_be_focused()
    page.keyboard.press("Enter")
    expect(visible).to_contain_text("third.md")
    starts_below_header()
    expect(third).to_be_focused()
    # A mode-only file has a commentable metadata row, without a textual body.
    third.press("ArrowDown")
    mode = tree.get_by_role("treeitem", name="z-mode.sh", exact=True)
    expect(mode).to_be_focused()
    page.keyboard.press("Enter")
    metadata = page.locator("#patch .lf-diff-metadata:visible")
    expect(metadata).to_contain_text("z-mode.sh")
    expect(metadata).to_be_in_viewport(ratio=1)
    expect(visible).to_have_count(0)
    expect(mode).to_be_focused()


@pytest.mark.parametrize("bound", [False, True], ids=["inline", "bound"])
def test_a_patch_that_failed_stays_failed_when_its_diff_returns(browser, serve, bound):
    """A refusal stands while its patch is unchanged: a diff that leaves the page and
    returns, as document reconciliation moves it, renders its patch again only when
    the departure cut that rendering short, and does not tell the author twice.
    Both inline and bound patches use the widget's render lifecycle."""
    one = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n"
    diff = (
        '<lf-diff id="d-bad" source="bad-patch"></lf-diff>'
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
    assert returned, "the returning diff cleared its completed refusal"
    errors = consume_browser_errors(page, '<lf-diff id="d-bad"> failed: ')
    assert len(errors) == 1, errors
    if bound:
        data_model.cmd_data_set(serve.page_dir, "bad-patch", one)
        expect(page.locator("#d-bad [data-line]").last).to_contain_text("y")
        expect(page.locator("#d-bad .lf-error")).to_have_count(0)


@pytest.mark.parametrize("bound", [False, True], ids=["inline", "bound"])
def test_a_patch_resumes_preparation_on_return_and_keeps_its_finished_rows(
    browser, serve, bound
):
    """A departure cuts short preparation, but a settled return keeps its native rows."""
    patch = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n"
    diff = (
        '<lf-diff id="patch" source="patch-data"></lf-diff>'
        if bound
        else f'<lf-diff id="patch"><pre>{patch}</pre></lf-diff>'
    )
    url = serve(leaf_page("Returning diff", diff))
    if bound:
        data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    page = browser.new_page()
    held = []
    page.route("**/vendor/pierre-parser.esm.js", lambda route: held.append(route))
    page.goto(url)
    holding(page, held, 1, "the inline patch parser")
    page.evaluate("""async () => {
        const diff = document.getElementById('patch');
        const parent = diff.parentNode;
        const next = diff.nextSibling;
        diff.remove();
        // Cross the departure task boundary; preparation stays held by the route.
        await new Promise((resolve) => setTimeout(resolve));
        parent.insertBefore(diff, next);
        // updateComplete includes the parser we are holding; let the arrival run
        // without waiting for that preparation before releasing its response.
        await new Promise((resolve) => setTimeout(resolve));
    }""")
    held[0].continue_()
    wait_until_ready(page)
    expect(page.locator("#patch [data-line]").last).to_contain_text("new")
    assert page.evaluate("""async () => {
        const diff = document.getElementById('patch');
        const row = diff.shadowRoot.querySelector('[data-line]');
        const parent = diff.parentNode;
        const next = diff.nextSibling;
        diff.remove();
        // A separate task makes this a departure and return, not an in-page move.
        await new Promise((resolve) => setTimeout(resolve));
        parent.insertBefore(diff, next);
        await diff.updateComplete;
        await diff.sourceRendering;
        return row !== null && row === diff.shadowRoot.querySelector('[data-line]');
    }"""), "a completed patch replaced its rows on return"


def test_an_expanded_diff_file_can_retry_its_failed_chunk_in_place(browser, serve):
    """A recovered network has a visible route to retry the expanded file."""
    url = serve(
        leaf_page(
            "Retry a file diff",
            '<h1>Retry a file diff</h1><lf-diff id="patch" source="review-patch" '
            'collapsed></lf-diff><button id="after" '
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
            '<lf-diff id="patch" source="patch-data" collapsed></lf-diff>',
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
            '<lf-diff id="patch" source="patch-data" collapsed></lf-diff>',
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


def test_one_press_folds_every_shown_file_and_the_page_shows_between_them(
    browser, serve
):
    """The filter's quiet press opens every file the filter shows while any is closed,
    and closes them once all are open. The diff keeps the page's paper and ink between
    its files after the first file brings the renderer's sheets, whose `:host` is one
    file's box where here it is the whole diff."""
    patch = "".join(
        f"diff --git a/src/f{index}.py b/src/f{index}.py\n"
        f"--- a/src/f{index}.py\n+++ b/src/f{index}.py\n@@ -1 +1 @@\n-old\n+new\n"
        for index in range(3)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Fold all",
                f'<h1>Fold all</h1><lf-diff id="patch" collapsed><pre>{escape(patch)}'
                "</pre></lf-diff>",
            )
        ),
    )
    diff = page.locator("#patch")
    folds = diff.locator("details.lf-diff-fold")
    editor = diff.locator(".lf-diff-search input")
    press = diff.locator(".lf-diff-fold-all")
    paints = """node => {
      const style = getComputedStyle(node);
      return [style.backgroundColor, style.color];
    }"""
    page_paint = diff.evaluate(paints)
    assert page_paint[0] == "rgba(0, 0, 0, 0)"
    folds.first.locator("summary").click()
    rendered(page)
    assert diff.evaluate(paints) == page_paint

    expect(press).to_have_accessible_name("Expand all files")
    press.click()
    for index in range(3):
        expect(folds.nth(index)).to_have_attribute("open", "")
    rendered(page)
    expect(folds.locator("[data-line]")).to_have_count(6)
    expect(press).to_have_accessible_name("Collapse all files")

    # Only what the filter shows, and the field's Tab order reaches the press.
    editor.fill("f1")
    expect(press).to_have_accessible_name("Collapse all files")
    editor.press("Tab")
    expect(press).to_be_focused()
    page.keyboard.press("Enter")
    expect(folds.nth(1)).not_to_have_attribute("open", "")
    expect(press).to_have_accessible_name("Expand all files")
    # A filter that shows nothing to open idles the press in its room, so the count
    # beside it does not move.
    count = diff.locator(".lf-diff-progress")
    place = count.bounding_box()
    editor.fill("none")
    expect(count).to_have_text("0 of 3")
    expect(press).to_have_attribute("inert", "")
    assert count.bounding_box() == place
    editor.fill("")
    expect(press).not_to_have_attribute("inert", "")
    expect(folds.nth(0)).to_have_attribute("open", "")
    expect(folds.nth(2)).to_have_attribute("open", "")
    expect(press).to_have_accessible_name("Expand all files")


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
                f'<lf-diff id="{name.lower()}" source="source-{name.lower()}" collapsed></lf-diff>'
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


def test_resolved_file_threads_share_the_file_disclosure_edge(browser, serve):
    """A resolved file conversation keeps its disclosure on the file's edge.

    The two disclosures use the same marker and inline inset at any width;
    expanded history puts Reopen beside the first message, like Resolve.
    """
    patch = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Resolved file conversations",
                f'<h1>Review app.py</h1><lf-diff id="patch" collapsed><pre>{escape(patch)}</pre></lf-diff>',
            )
        ),
    )
    diff = page.locator("#patch")
    diff.locator(".lf-diff-file-comment").click()
    field = diff.locator("leaf-text")
    field.press("A")
    with sending(page, "the file comment"):
        field.press("ControlOrMeta+Enter")
    thread = diff.locator(".lf-page-thread")
    thread.get_by_role("button", name="Resolve thread", exact=True).focus()
    with sending(page, "the resolution"):
        page.keyboard.press("Enter")
    summary = diff.locator(".lf-resolved-summary")
    expect(summary).to_have_text("Resolved · 1")
    for width in (1440, 390):
        resized(page, width, 900)
        rendered(page)
        geometry = summary.evaluate("""summary => {
          const file = summary.closest('.lf-diff-file').querySelector(':scope > details > summary');
          const marker = node => {
            const box = node.getBoundingClientRect(), style = getComputedStyle(node);
            const arrow = getComputedStyle(node, '::before');
            return {left: box.left + parseFloat(style.paddingLeft),
              size: arrow.fontSize, content: arrow.content};
          };
          return {file: marker(file), resolved: marker(summary)};
        }""")
        assert geometry["file"]["left"] == pytest.approx(
            geometry["resolved"]["left"], abs=0.5
        ), geometry
        assert geometry["file"]["size"] == geometry["resolved"]["size"], geometry
        assert geometry["file"]["content"] == geometry["resolved"]["content"], geometry
    # Paper has nothing to turn, so neither row draws its marker there.
    page.emulate_media(media="print")
    printed = summary.evaluate("""summary => [
      summary.closest('.lf-diff-file').querySelector(':scope > details > summary'),
      summary,
    ].map(node => {
      const arrow = getComputedStyle(node, '::before');
      return arrow.display === 'none' || arrow.visibility === 'hidden';
    })""")
    assert printed == [True, True], printed
    page.emulate_media(media="screen")
    summary.click()
    expect(thread).to_be_visible()
    reopen = thread.get_by_role("button", name="Reopen", exact=True)
    expect(reopen).to_be_visible()
    centers = reopen.evaluate("""button => {
      const head = button.closest('.lf-page-thread').querySelector('.lf-msg-head').getBoundingClientRect();
      const action = button.getBoundingClientRect();
      return [head.top + head.height / 2, action.top + action.height / 2];
    }""")
    assert centers[0] == pytest.approx(centers[1], abs=0.5), centers
    with sending(page, "the reopening"):
        reopen.click()
    expect(summary).to_have_count(0)
    expect(
        thread.get_by_role("button", name="Resolve thread", exact=True)
    ).to_be_visible()


def test_a_file_conversation_ends_the_list_past_files_the_filter_hides(browser, serve):
    """The shown files are one bordered list, which a file's conversation box breaks.

    The next file the filter shows starts a new run 8px below that box, with its own
    corners, even when the files between are hidden; without a filter the hidden file
    starts it and the one after joins on.
    """
    patch = "".join(
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-old\n+new\n"
        for path in ("app/models.py", "app/views.py", "docs/guide.md")
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "File conversations in a filtered list",
                f'<h1>Review the change</h1><lf-diff id="patch" collapsed><pre>{escape(patch)}</pre></lf-diff>',
            )
        ),
    )
    diff = page.locator("#patch")
    diff.locator(".lf-diff-file-comment").first.click()
    field = diff.locator("leaf-text")
    field.press("A")
    with sending(page, "the file comment"):
        field.press("ControlOrMeta+Enter")
    expect(diff.locator(".lf-page-thread")).to_be_visible()
    read = """diff => {
      const box = node => node.getBoundingClientRect();
      const files = [...diff.shadowRoot.querySelectorAll('.lf-diff-file')];
      const head = file => file.querySelector(':scope > details');
      const outlet = box(files[0].querySelector('.lf-diff-file-thread-outlet'));
      return files.map(file => ({
        shown: !file.hidden,
        top: box(head(file)).top, bottom: box(head(file)).bottom, outlet: outlet.bottom,
        corner: getComputedStyle(head(file)).borderTopLeftRadius,
      }));
    }"""
    corner = diff.evaluate("d => getComputedStyle(d).getPropertyValue('--r').trim()")
    models, views, guide = diff.evaluate(read)
    assert views["top"] - views["outlet"] == pytest.approx(8, abs=0.5), views
    assert views["corner"] == corner, views
    assert guide["top"] == pytest.approx(views["bottom"] - 1, abs=0.5), guide
    assert guide["corner"] == "0px", guide

    diff.get_by_label("Filter diff files").fill("d")
    rendered(page)
    models, views, guide = diff.evaluate(read)
    assert (models["shown"], views["shown"], guide["shown"]) == (True, False, True)
    assert guide["top"] - guide["outlet"] == pytest.approx(8, abs=0.5), guide
    assert guide["corner"] == corner, guide


def test_a_live_line_reply_wraps_without_resize_observer_feedback(
    browser, serve, request
):
    """A streaming answer can wrap when Pierre sizes its sticky line conversation.

    The width write changes the observed code's height. It belongs in a frame,
    outside ResizeObserver delivery, and must leave the answer readable while the
    code scrolls. The browser fixture also refuses ResizeObserver window errors.
    """
    from interact_support import append_command

    from browser.threads import claim_for_codex, stream_reply

    patch = """diff --git a/uploader.py b/uploader.py
--- a/uploader.py
+++ b/uploader.py
@@ -1,4 +1,16 @@
-def upload(client, job, payload):
-    response = client.post("/objects", json=payload, timeout=10)
-    response.raise_for_status()
-    return response.json()["object_id"]
+import time
+
+def upload(client, job, payload, max_attempts=3):
+    key = f"upload:{job.tenant_id}:{job.id}"
+    for attempt in range(max_attempts):
+        try:
+            response = client.post(
+                "/objects", json=payload,
+                headers={"Idempotency-Key": key}, timeout=10,
+            )
+            response.raise_for_status()
+            return response.json()["object_id"]
+        except TimeoutError:
+            if attempt + 1 == max_attempts:
+                raise
+            time.sleep(0.5 * 2**attempt)
"""
    url = serve(
        leaf_page(
            "Live patch review",
            f'<h1>Review</h1><details id="review" open><summary>Patch review</summary>'
            f'<lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff></details>',
            head="<style>main { width: 492px; max-width: calc(100% - 48px); padding: 0; }</style>",
        )
    )
    comment = append_command(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Tenant-scoped key computed once before the loop looks right.",
            "anchor": {"section": "patch", "datum": '["uploader.py","new",4]'},
        },
    )
    claim_for_codex(serve.page_dir, request)
    reply = (
        "I’m recording the tenant-scoped key and two-attempt default as your final "
        "review decision. The selected code will lead the page, with the unrun "
        "tests and Thursday rollout conditions still clear."
    )
    stream_reply(serve.page_dir, comment["id"], reply)
    context = browser.new_context(viewport={"width": 540, "height": 720})
    page = open_page(browser, url, context=context)
    diff = page.locator("#patch")
    outlet = diff.locator(".lf-diff-thread-outlet")
    expect(outlet).to_contain_text(reply)
    code = diff.get_by_role("region", name="uploader.py", exact=True)
    before = outlet.bounding_box()
    code.focus()
    page.keyboard.press("ArrowRight")
    page.wait_for_function("""() => document.getElementById('patch')
      .shadowRoot.querySelector('code[data-code]').scrollLeft > 0""")
    rendered(page)
    after = outlet.bounding_box()
    assert abs(after["width"] - before["width"]) <= 1
    assert after["x"] >= code.bounding_box()["x"] - 1
    code_box = code.bounding_box()
    assert after["x"] + after["width"] <= code_box["x"] + code_box["width"] + 1
    # Retire a file with active geometry observations, then reopen its same source.
    summary = diff.locator("summary").first
    summary.focus()
    page.keyboard.press("Enter")
    expect(code).not_to_be_visible()
    page.keyboard.press("Enter")
    expect(outlet).to_contain_text(reply)
    resized(page, 390, 844)
    expect(outlet).to_be_visible()
    resized(page, 900, 600)
    expect(outlet).to_be_visible()
    rendered(page)

    # A retained diff can receive a reply while its native disclosure is closed.
    page.locator("#review > summary").click()
    expect(code).not_to_be_visible()
    hidden_reply = reply + " The review is ready."
    stream_reply(serve.page_dir, comment["id"], hidden_reply)
    expect(outlet).to_contain_text(hidden_reply)
    rendered(page)
    page.locator("#review > summary").click()
    expect(outlet).to_be_visible()
    rendered(page)
    assert outlet.bounding_box()["width"] <= code.bounding_box()["width"]


def test_file_tree_reads_standalone_data_without_a_diff_package(browser, serve):
    """The optional tree consumes a path list on its own and retains its mounted
    navigation when an unrelated data value changes."""
    url = serve(
        leaf_page(
            "Explore project files",
            "<h1>Project files</h1>"
            '<a href="#project-files">Back to files</a>'
            '<lf-file-tree id="project-files" source="project" '
            'data-height="280"></lf-file-tree>',
            head="<style>#project-files { --lf-file-tree-height:280px; }</style>",
        ),
        packages=("file-tree",),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "project",
        {
            "files": [
                {"path": "README.md"},
                {"path": "src/main.py", "status": "added"},
            ],
        },
    )
    page = open_page(browser, url)
    tree = page.locator("#project-files")
    assert tree.bounding_box()["height"] == 280, "flow keeps the authored height"
    row = tree.get_by_role("treeitem", name=re.compile(r"README\.md"))
    expect(row).to_be_visible()
    row.click()
    expect(row).to_have_attribute("aria-selected", "true")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    data_model.cmd_data_set(
        serve.page_dir,
        "project",
        {
            "files": [
                {"path": "README.md", "status": "modified"},
                {"path": "src/main.py"},
            ],
        },
    )
    expect(row).to_have_attribute("aria-selected", "true")
    search = tree.get_by_role("textbox")
    page.get_by_role("link", name="Back to files").click()
    expect(search).to_be_focused()
    search.fill("main")
    expect(tree.get_by_role("treeitem", name=re.compile(r"README\.md"))).to_have_count(
        0
    )
    search.fill("no-such-file")
    expect(tree.get_by_role("treeitem")).to_have_count(0)
    expect(tree).to_contain_text("No matching files.")
    search.fill("")
    expect(row).to_be_visible()
    search.fill("main")
    search.press("Escape")
    expect(search).to_have_value("")


@pytest.mark.shifts_unsurveyed  # The test explicitly scrubs native CSS transitions.
@pytest.mark.parametrize("kind", ["call", "file"])
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_evidence_close_folds_room_but_retires_controls_immediately(
    request, serve, kind, engine
):
    """Closed evidence retires controls at once; every reopening reaches full size."""
    from render_cases_navigation import call_diff, call_node

    tag = "lf-call-diff" if kind == "call" else "lf-diff"
    attributes = 'diff="patch"' if kind == "call" else ""
    extra = (
        '<lf-diff id="patch" source="patch-data" collapsed></lf-diff>'
        if kind == "call"
        else ""
    )
    url = serve(
        leaf_page(
            "Fold evidence",
            f'<h1>Review</h1><div style="height:1100px"></div><{tag} id="evidence" source="change" {attributes}></{tag}>'
            '<button id="after">Continue review</button>' + extra,
        ),
        packages=("diff",),
    )
    content = (
        call_diff(
            call_node("root", children=[call_node(f"step {i}") for i in range(12)])
        )
        if kind == "call"
        else patch_manifest(
            "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,12 +1,12 @@\n"
            + "".join(f"-old{i}\n+new{i}\n" for i in range(12))
        )
    )
    data_model.cmd_data_set(serve.page_dir, "change", content)
    if kind == "call":
        data_model.cmd_data_set(
            serve.page_dir,
            "patch-data",
            patch_manifest(
                "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
            ),
        )
    page = open_page(request.getfixturevalue(engine), url)
    page.emulate_media(reduced_motion="no-preference")
    details = page.locator("#evidence details").first
    summary = details.locator("summary")
    expect(summary).to_be_visible()
    # Interactive evidence can be supplied by another package. Keep a positive
    # focus control before proving that the closing boundary retires it.
    details.evaluate("""d => {
      const b = document.createElement('button');
      b.textContent = 'Inspect evidence';
      d.append(b);
      d.style.setProperty('--lf-motion-fold', '1000000s');
      d.classList.add('held-evidence');
      const style = document.createElement('style');
      style.textContent = '.held-evidence:not([open])::details-content {transition-delay:-500000s}';
      const root = d.getRootNode();
      (root.head || root).append(style);
    }""")
    inside = details.locator("button", has_text="Inspect evidence")
    inside.focus()
    expect(inside).to_be_focused()

    def height():
        return details.evaluate("d=>d.getBoundingClientRect().height")

    page.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
    scroll_settled(page)
    full = height()
    animated = page.evaluate("""() =>
      CSS.supports('block-size', 'calc-size(auto, size)') &&
      CSS.supports('interactivity', 'inert')""")
    summary.click()
    expect(details).not_to_have_attribute("open")
    # Native details transitions live in the UA shadow tree, outside getAnimations.
    # Stretch their real CSS timeline around its halfway point to inspect a stable
    # intermediate frame without intercepting or rebuilding the animation.
    page.evaluate("() => new Promise(requestAnimationFrame)")
    middle = height()
    assert middle < full
    # A painted closing body is already outside focus and Tab access.
    inside.evaluate("b => b.focus()")
    expect(inside).not_to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#after")).to_be_focused()
    # Reopening a partially folded body snaps to its ordinary complete geometry.
    summary.click()
    assert details.evaluate("d=>d.open")
    assert height() == pytest.approx(full, abs=1)
    summary.press("Enter")
    assert not details.evaluate("d=>d.open")
    closed = height()
    assert closed < full
    if animated:
        assert middle > closed + 1
    assert (
        details.evaluate(
            "d => getComputedStyle(d, '::details-content').contentVisibility"
        )
        == "hidden"
    )
    summary.press("Enter")
    assert height() == pytest.approx(full, abs=1)
    page.emulate_media(reduced_motion="reduce")
    summary.click()
    assert not details.evaluate("d=>d.open")
    assert height() < full
    assert (
        details.evaluate(
            "d => getComputedStyle(d, '::details-content').contentVisibility"
        )
        == "hidden"
    )
    details.evaluate("d => d.open = true")
    assert height() == pytest.approx(full, abs=1)
