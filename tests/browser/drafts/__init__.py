"""Unsent words on a rendered page, in drafts, comments and replies, from editing
through sending, sharing and revisions, with the helpers their modules share."""

from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    leaf_page,
    open_latest,
    open_page,
    press_draft_control,
    round_trip,
    stamp_page,
    told,
    wait_for_revision,
    write,
)


def choose_comment_target(page, selector):
    """Choose the exact element through the user's target picker."""
    page.locator(selector).scroll_into_view_if_needed()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    page.locator(selector).click()
    expect(page.locator(".lf-fab-input")).to_be_focused()


def cancel_draft(page, draft_id="draft-ops"):
    """Discard stands beside Save in an open draft editor, for a pointer that comes
    to it after typing too."""
    press_draft_control(page, "cancel", draft_id)


# Generated editors carry native editing under their existing durable draft identity.
def editing_revision_source(mode, body=None):
    body = (
        body
        or '<h1 id="subject">Editor continuity</h1><p id="passage">A stable passage stays exact across the revision.</p><textarea id="authored-draft" aria-label="Authored draft" style="height:80px"></textarea><lf-draft id="draft-root"><pre>Current editable text.</pre></lf-draft><lf-group id="choice-root" label="Which choice?"><h2 id="choice-root-h">Which choice?</h2><lf-options id="options-root"><lf-option id="initial">Initial choice</lf-option></lf-options></lf-group><lf-test-plan id="command-root" label="Tasks"><lf-test-task id="seat-root" status="active" talk>What should we do?</lf-test-task></lf-test-plan>'
    )
    module = """<script type="module">
window.__rendererLifetime={birth:performance.timeOrigin,hits:0,version:'MODE'};
addEventListener('renderer-lifetime-probe',()=>window.__rendererLifetime.hits++);
</script>""".replace("MODE", mode)
    return leaf_page("Editor continuity", body).replace("</head>", module + "</head>")


def editing_reply_page(browser, serve, context=None):
    page = open_page(
        browser, live_url(serve(editing_revision_source("before"))), context=context
    )
    page.locator("#passage").click(click_count=3)
    page.keyboard.press("c")
    write(page.locator(".lf-composer leaf-text"), "An anchored root.")
    page.keyboard.press("Control+Enter")
    round_trip(page)
    page.keyboard.press("c")
    return page


def replace_editing_document(page, serve):
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(
        serve.page_dir,
        editing_revision_source("after"),
        "Change real inline module body",
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == birth:
        open_latest(page)
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") != birth
