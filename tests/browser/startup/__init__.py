"""How a page starts, presents and keeps its state current in the browser, with the
helpers and page constants its modules share."""

from render_harness import leaf_page

HELD_KEYS_PAGE = leaf_page(
    "Held keys",
    "<h1>Held keys</h1><p id='said'>A sentence the user commented on.</p>",
)


def _hold_startup(page, stage):
    """Hold startup at `stage` — before the runtime loads, or after it loads and
    before the first state answer — and return the route release."""
    held, gate = [], {"open": False}
    pattern = "**/leaf.js" if stage == "module" else "**/api/state*"
    page.route(
        pattern,
        lambda route: route.continue_() if gate["open"] else held.append(route),
    )

    def release():
        gate["open"] = True
        for route in held:
            route.continue_()

    return held, release
