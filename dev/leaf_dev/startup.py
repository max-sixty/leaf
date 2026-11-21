"""Startup and layout observations shared by local probes and site verification.

Install before navigation. Startup includes presentation's two paint frames;
layout-shift evidence continues through interactions. Neither imposes a budget.
"""

from pathlib import Path

from playwright.sync_api import Page

SCRIPT = Path(__file__).with_suffix(".js")


def observe_startup(page: Page) -> None:
    """Record one document's startup milestones, resources, and native shifts."""
    page.add_init_script(path=SCRIPT)


def startup_reading(page: Page) -> dict:
    """Drain native evidence through the initial presentation's painted frames."""
    return page.evaluate("window.__leafStartup.reading")


def layout_shifts_reading(page: Page) -> dict:
    """Read this document's native shifts through a completed rendering frame.

    The caller waits for its action's result first; this checkpoint lets the browser
    paint that result. Sources name affected nodes, not the code that moved them.
    """
    return page.evaluate("""async () => {
      await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
      return window.__leafStartup.layoutShifts();
    }""")


def observed_time(value: float | None) -> str:
    """Render an optional browser milestone without inventing a zero reading."""
    return "not observed" if value is None else f"{value:.0f} ms"


def startup_profile(startup: dict) -> dict:
    """Return browser startup readings in a stable machine-readable shape."""
    presented = startup["presented"]
    return {
        "htmlFirstByteMs": startup["first_byte"],
        "htmlCompleteMs": startup["document"],
        "firstContentfulPaintMs": startup.get("paint", {}).get(
            "first-contentful-paint"
        ),
        "javascriptFetchedMs": presented["js_loaded"],
        "upgradedMs": startup["upgraded"]["at"],
        "stateAnsweredMs": presented["state_loaded"],
        "presentedMs": presented["at"],
        "requestsAtPresentation": presented["requests"],
        "bytesAtPresentation": presented["bytes"],
        "javascriptRequestsAtPresentation": presented["js_requests"],
        "javascriptBytesAtPresentation": presented["js_bytes"],
        "codeRequestsAtPresentation": presented["code_requests"],
        "codeBytesAtPresentation": presented["code_bytes"],
        "layoutShifts": startup["shifts"],
    }


def startup_line(path: str, startup: dict) -> str:
    """Render observed startup costs without turning machine speed into a gate."""
    profile = startup_profile(startup)
    line = (
        f"  {path} — HTML first byte {profile['htmlFirstByteMs']:.0f} ms, "
        f"complete {profile['htmlCompleteMs']:.0f} ms; "
        "first contentful paint "
        f"{observed_time(profile['firstContentfulPaintMs'])}; "
        f"JS fetched {observed_time(profile['javascriptFetchedMs'])}; "
        f"upgraded {profile['upgradedMs']:.0f} ms; "
        f"state answered {observed_time(profile['stateAnsweredMs'])}; "
        f"presented {profile['presentedMs']:.0f} ms; "
        f"by presentation {profile['javascriptRequestsAtPresentation']} JS / "
        f"{profile['javascriptBytesAtPresentation'] / 1024:.0f} KiB, "
        f"{profile['codeRequestsAtPresentation']} code / "
        f"{profile['codeBytesAtPresentation'] / 1024:.0f} KiB, "
        f"{profile['requestsAtPresentation']} total / "
        f"{profile['bytesAtPresentation'] / 1024:.0f} KiB; "
        f"{len(profile['layoutShifts'])} initial layout shifts (diagnostic)"
    )
    for shift in profile["layoutShifts"]:
        sources = []
        for source in shift["sources"]:
            before, after = source["previousRect"], source["currentRect"]
            sources.append(
                f"{source['node']} ({before['x']:g},{before['y']:g} "
                f"{before['width']:g}x{before['height']:g}) → "
                f"({after['x']:g},{after['y']:g} "
                f"{after['width']:g}x{after['height']:g})"
            )
        line += (
            f"\n    {shift['startTime']:.0f} ms {shift['phase']}, "
            f"value {shift['value']:.6g}, recent input {shift['hadRecentInput']}: "
            + "; ".join(sources)
        )
    return line
