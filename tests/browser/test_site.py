"""The published site: what the build assembles, and what a user gets.

The site is the repo's product pages, examples, and developer feature gallery as live
Leaf pages, so most of what could go wrong is a path that meant one thing in a checkout
and another on a host.
The build resolves every local link it wrote and stops on one that reaches
nothing, which is the failure a static host answers with a 404 and no other
signal; these tests hold the rest — that the theme a page links is the shipped
file, that an example served here is a working page rather than a picture of one,
and that a site claiming to ride the theme's tokens actually changes colour when
the theme's palette does.

Every page is reached over HTTP through its page-scoped vendored layer and the canonical
server.
"""

import pytest
from leaf.render_checks import wait_until_ready

# The suite's own page primitives, so a navigation here waits on what every other
# navigation waits on. tests/AGENTS.md, "Waits".
from render_harness import (
    holding,
)

# The module-scoped build and host are one shared setup, so they belong to one
# xdist work unit rather than being rebuilt independently on every worker.
pytestmark = [pytest.mark.shifts_unsurveyed, pytest.mark.xdist_group(name="site")]

from journeys.test_site import sample_address, sample_allocation


def test_a_sample_waits_for_slow_contained_page_state(serve, browser):
    """A healthy contained page may present after an arbitrarily slow state read."""
    url = serve("""<!doctype html><html><head><title>Slow sample</title></head><body><main>
      <lf-sample id="practice" label="practice page">
        <template id="practice-page" data-sample><p id="copy">Practice here.</p></template>
      </lf-sample>
    </main></body></html>""")
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    held = []
    held_once = False
    allocation = sample_allocation(page, url, "practice-page")

    def hold_first_contained_state(route):
        nonlocal held_once
        if (
            allocation["url"] is not None
            and route.request.url.startswith(allocation["url"])
            and not held_once
        ):
            held_once = True
            held.append(route)
            return
        route.continue_()

    page.route("**/api/state*", hold_first_contained_state)
    try:
        with page.expect_request(
            lambda request: (
                allocation["url"] is not None
                and request.url.startswith(allocation["url"])
                and "/api/state" in request.url
            )
        ):
            page.goto(url, wait_until="domcontentloaded")
        sample = page.locator("#practice")
        holding(page, held, 1, "the contained page's first state read")
        held.pop().continue_()
        page.wait_for_load_state("load")
        wait_until_ready(page)
        sample.evaluate("async sample => { await sample.ready; }")
        frame = sample.locator("iframe")
        assert not frame.get_attribute("srcdoc")
        contained_document = frame.content_frame.locator("html")
        assert contained_document.evaluate(
            "() => document.doctype?.name === 'html' && Boolean(document.scrollingElement)"
        )
        page.evaluate("sessionStorage.setItem('lf-view', 'outer reading')")
        storage = contained_document.evaluate(
            """async () => {
                const {readApplication} = await window.__lfCheckApi();
                const {PAGE_SCOPE, tabStore, draftStore, userStore} =
                    await window.__lfCheckApi();
                for (const [name, store] of Object.entries({tabStore, draftStore, userStore})) {
                    if (!store.set('isolation-test', name) || store.get('isolation-test') !== name)
                        throw new Error(`${name} did not retain sample working state`);
                    if (!store.keys().includes('isolation-test'))
                        throw new Error(`${name} did not enumerate its retained state`);
                    store.set('isolation-test', null);
                    if (store.get('isolation-test') !== null)
                        throw new Error(`${name} did not clear its retained state`);
                }
                return {liveRoot: readApplication().document.live, pageScope: PAGE_SCOPE};
            }"""
        )
        assert storage["liveRoot"] is True
        assert "/api/samples/" in storage["pageScope"]
        interaction_url = f"{sample_address(frame)}api/interaction"
        with page.expect_response(
            lambda response: (
                response.url == interaction_url
                and any(
                    entry["type"] == "pagehide"
                    for entry in response.request.post_data_json["entries"]
                )
            )
        ) as departure:
            contained_document.evaluate(
                "dispatchEvent(new PageTransitionEvent('pagehide'))"
            )
        assert departure.value.ok
        assert page.evaluate("sessionStorage.getItem('lf-view')") == "outer reading"
        assert (
            page.evaluate(
                "scope => sessionStorage.getItem(scope + 'lf-view')",
                storage["pageScope"],
            )
            is None
        )
    finally:
        for route in held:
            route.abort()
