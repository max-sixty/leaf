"""Developer tooling checks; run explicitly from dev/tests."""

from contextlib import ExitStack

from interact_support import (
    COMPOSITE_TIMEOUT,
    wait_for,
)
from journeys.test_render_export import (  # noqa: F401 (fixtures)
    OFFLINE_REGISTRY,
    OFFLINE_WIDGET,
    PIXEL,
    POLICY_ATTEMPTS,
    ROOT,
    _reachable,
    requested_documents,
)
from playwright.sync_api import expect
from render_harness import (
    is_problem,
    open_page,
    restarting,
    sending,
)

from leaf import server as server_model
from leaf.render_checks import HANDOVER_DEADLINE_MS

from ..journeys.test_render_export import (  # noqa: F401
    preview_slot_fixture,
    served_preview_fixture,
    watched_preview_fixture,
)


def test_preview_watches_source_without_losing_user_state(browser, watched_preview):
    """The open tab follows source edits; rejected source never replaces its last good
    page. A runtime edit's restart is `test_every_tab_follows_a_runtime_edit`'s."""
    source, _, directory, _, url, log = watched_preview
    original = source.read_text(encoding="utf-8")
    page = open_page(browser, url)
    with sending(page, "the watched user option pick"):
        page.locator("#opt-shim .lf-pick").click()
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    feedback = (directory / "events.jsonl").read_bytes()
    assert b'"kind": "action"' in feedback
    inode = (directory / "events.jsonl").stat().st_ino

    # A source edit leaves the server up, so it is not a restart span: the tab takes
    # the new revision in place, and anything it complains about is a fault.
    revised = original.replace("Rollout", "A watched source revision", 1)
    source.write_text(revised, encoding="utf-8")
    expect(page.get_by_role("heading", name="A watched source revision")).to_be_visible(
        timeout=HANDOVER_DEADLINE_MS
    )
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    source.write_text("<p>invalid source</p>", encoding="utf-8")
    wait_for(
        log.read_text,
        lambda output: "Preview update refused" in output,
        failure="the invalid preview update was not refused",
    )
    expect(
        page.get_by_role("heading", name="A watched source revision")
    ).to_be_visible()
    assert (directory / "index.html").read_text() == revised
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    source.write_text(
        revised.replace("A watched source revision", "Recovered watched source"),
        encoding="utf-8",
    )
    expect(page.get_by_role("heading", name="Recovered watched source")).to_be_visible(
        timeout=HANDOVER_DEADLINE_MS
    )
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode


def test_every_tab_follows_a_runtime_edit(browser, watched_preview):
    """A runtime edit replaces the server, and every tab of the page follows it.

    An open tab takes the new layer with the user's state and log intact. A tab whose
    start failed hears the replacement too: supervision precedes the kernel and
    registry requests. One restart serves them all at the recorded port.
    """
    _, runtime, directory, _, url, _ = watched_preview
    open_tab = open_page(browser, url)
    with sending(open_tab, "the user option pick in force"):
        open_tab.locator("#opt-shim .lf-pick").click()
    expect(open_tab.locator("#opt-shim")).to_have_attribute("chosen", "")
    feedback = (directory / "events.jsonl").read_bytes()
    inode = (directory / "events.jsonl").stat().st_ino
    resources = ("leaf.js", "registry.json")
    pages = {}
    # The interruption and the replacement server between them are a restart, and
    # what the browser says inside one is the fetch that was in flight rather than
    # the condition: a refused resource, a connection to a server that has gone, a
    # decoding that stopped halfway. The span is bracketed rather than the wordings
    # listed (tests/AGENTS.md, "Test-made noise").
    with ExitStack() as restarts:
        restarts.enter_context(restarting(open_tab))
        for resource in resources:
            page = browser.new_page()
            failures = []
            documents = requested_documents(page)

            def interrupt_resource(route, resource=resource, failures=failures):
                if failures:
                    route.continue_()
                    return
                failures.append(True)
                route.abort()

            page.route("**/" + resource, interrupt_resource)
            restarts.enter_context(restarting(page))
            page.goto(url, wait_until="load")
            status = page.get_by_text(
                "Leaf couldn't start. Waiting for the server to update."
            )
            expect(status).to_be_visible()
            assert len(documents) == 1, resource
            pages[resource] = (page, status, documents)
        # A changed layer replaces the server. An invalid input is now refused
        # before that replacement, so change a valid theme to test recovery.
        theme = runtime / "browser" / "base.css"
        updated = runtime.parent / "base.css.next"
        updated.write_text(theme.read_text() + "\nh1 { color: navy; }\n")
        updated.replace(theme)
        expect(open_tab.locator("h1")).to_have_css(
            "color", "rgb(0, 0, 128)", timeout=HANDOVER_DEADLINE_MS
        )
        for page, status, _ in pages.values():
            expect(page.locator("body")).to_have_attribute(
                "data-lf-presented", "1", timeout=HANDOVER_DEADLINE_MS
            )
            # Rebuilding the installation can outlast the default browser wait.
            expect(status).not_to_be_visible(timeout=HANDOVER_DEADLINE_MS)
    for resource, (page, _, documents) in pages.items():
        assert len(documents) >= 2, resource
        expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    expect(open_tab.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode


def test_a_service_that_goes_away_mid_start_says_only_that_and_comes_back(
    browser, served_preview
):
    """A start the restart interrupts reports the vanished server and comes back.

    The other tests here reach this condition only when the machine is loaded enough to
    lose the race, so the ordering is arranged here rather than waited for. The
    interrupted fetch is the registry's; a widget's dynamic import reaches the same
    supervision with the module's name in its words.

    A runtime edit makes the preview replace its server. Abort the in-flight registry
    request as that replacement starts, then check that the page reports the lost
    request and follows the replacement at the same address.
    """
    _, runtime, directory, _, url, _ = served_preview
    page = browser.new_page()
    errors = page.lf_errors
    interrupted = []
    page.add_init_script(
        """(() => {
          const words = "Leaf couldn't start. Waiting for the server to update.";
          const check = () => {
            if (![...document.querySelectorAll('[role="status"]')]
                .some(node => node.textContent === words && node.checkVisibility())) return;
            observer.disconnect();
            sessionStorage.setItem('__lf-test-startup-notice', 'seen');
          };
          const observer = new MutationObserver(check);
          observer.observe(document, {childList: true, subtree: true});
          check();
        })();"""
    )

    def interrupt_start(route):
        # The registry is the runtime's own fetch. Once only: the reload the recovery
        # makes must find a server that answers.
        if not interrupted:
            interrupted.append(True)
            theme = runtime / "browser" / "base.css"
            updated = runtime.parent / "base.css.next"
            updated.write_text(theme.read_text() + "\nh1 { color: navy; }\n")
            updated.replace(theme)
            route.abort("failed")
        else:
            route.continue_()

    page.route("**/registry.json", interrupt_start)
    with restarting(page):
        vanished = "leaf: page failed to start: Failed to fetch"
        with page.expect_console_message(lambda message: vanished in message.text):
            page.goto(url, wait_until="commit")
        # Recovery may navigate after the failure. The observer records the notice
        # in this tab when it appears, before a later document replaces it.
        page.wait_for_function(
            "sessionStorage.getItem('__lf-test-startup-notice') === 'seen'"
        )
        # The reach: an interrupted start is a fetch the runtime made itself, which no
        # transport error names, and the words are the interrupted fetch's own.
        assert [error for error in errors if is_problem(error, vanished)], errors
        # The page's own recovery is bounded; the re-vendor ahead of it is not.
        wait_for(
            lambda: server_model.running_server(directory),
            bool,
            failure="the preview did not bring its service back",
            timeout=COMPOSITE_TIMEOUT,
        )
        expect(page.locator("h1")).to_have_css("color", "rgb(0, 0, 128)")
