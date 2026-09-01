"""Standalone export of a fully rendered page."""

import base64
import re
import sys
from pathlib import Path

from leaf.data import read_data
from leaf.event_log import read_events
from leaf.files import published_versions, version_name
from leaf.render_checks import RENDER_VIEWPORT, evaluate_probe, wait_for_probe
from leaf.render_gate.preview import preview_server
from leaf.schema import _DIR_FILES, MEDIA_DIR, MEDIA_TYPES
from leaf.structure import parse_structure


def _inline_media(text: str, page_dir: Path, refs: set[str]) -> str:
    """Replace declared page-media references in one serialized payload."""
    for src in sorted(refs):
        file = page_dir / src.lstrip("/")
        data = base64.b64encode(file.read_bytes()).decode()
        uri = f"data:{MEDIA_TYPES[file.suffix]};base64,{data}"
        text = text.replace(f'="{src}"', f'="{uri}"').replace(
            f"url({src})", f"url({uri})"
        )
    return text


def inline_css_assets(css: str, page_dir: Path) -> str:
    """Make page-local CSS independent of Leaf's media endpoint."""
    refs = set(re.findall(rf"url\((/{MEDIA_DIR}/{_DIR_FILES[MEDIA_DIR]})\)", css))
    return _inline_media(css, page_dir, refs)


def inline_assets(html: str, page_dir: Path) -> str:
    """Fold the served assets into the markup. The theme's link becomes the stylesheet
    itself and each image becomes its own bytes, which is everything the document still
    reaches the server for: the runtime's stylesheet arrived as a `<style>` in the DOM,
    the widget modules were imports rather than elements, and a `lf-ref`'s link was
    always somewhere else."""
    theme = (page_dir / "theme.css").read_text(encoding="utf-8")
    html, n = re.subn(
        r'<link[^>]+href="/theme\.css"[^>]*>',
        lambda _: f"<style>{theme}</style>",
        html,
        count=1,
    )
    if not n:
        sys.exit(
            "the rendered page carried no /theme.css link — it would open unstyled"
        )
    # References from the parsed reading, never a scan of the text: a path standing
    # in prose is the reader's words — the lesson `media_refs` itself carries — and
    # a text scan crashed the export on a documented path no file answers. The
    # attribute harvest is media_refs; a page <style>'s url(/media/…) is the one
    # reference an attribute harvest can't see, so it is read from the parsed css.
    # The substitution then rewrites only the two serialized forms a reference
    # takes (`="…"`, `url(…)`); prose quoting the exact string of a path the page
    # also really uses is the residual, and it is the author quoting live markup.
    parsed = parse_structure(html)
    css_refs = set(
        re.findall(rf"url\((/{MEDIA_DIR}/{_DIR_FILES[MEDIA_DIR]})\)", parsed.css)
    )
    return _inline_media(html, page_dir, set(parsed.media_refs) | css_refs)


def export_page(browser, url: str, page_dir: Path) -> str:
    """The served version at `url`, copied as one self-contained document.

    One implementation has two callers, as `render_version` does: `version export`
    supplies installed Chrome, while the suite drives this over the shipped
    examples with its Chromium headless shell. That keeps the export behavior in
    one function without claiming that the two browser launch paths are identical.

    The user's decisions come with it. Replay is what puts them on the page, so
    this waits for the runtime's caught-up stamp exactly as the gate does, and a page
    whose board was rearranged copies rearranged."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page = browser.new_page(viewport=RENDER_VIEWPORT)
    try:
        # See the gate: a page listening for news is never network-idle. The
        # stamps below are the arrival signal, and they are the precise one.
        page.goto(url, wait_until="load")
        try:
            wait_for_probe(page, "upgraded")
            wait_for_probe(page, "dataApplied", read_data(page_dir)["revision"])
            # Both replayed kinds, as the render gate counts them: the caught-up
            # stamp counts reports beside actions, and a page whose only recorded
            # state is a worker's report would otherwise copy before it painted.
            n_replayed = len(
                [e for e in read_events(page_dir) if e["kind"] in ("action", "report")]
            )
            if n_replayed:
                wait_for_probe(page, "logApplied", n_replayed)
            return inline_assets(evaluate_probe(page, "bake"), page_dir)
        except PlaywrightTimeout:
            sys.exit(
                f"{url.rsplit('/', 1)[-1]} never finished applying its live state in "
                "the browser, so a copy would be half-drawn. `leaf version check "
                "<page> --render` says what is wrong with it."
            )
        except PlaywrightError as error:
            sys.exit(
                f"{url.rsplit('/', 1)[-1]} could not load its browser probe module "
                f"({str(error).strip().splitlines()[0]}), so Leaf could not make a "
                "trustworthy copy."
            )
    finally:
        page.close()


def cmd_export(page_dir: Path, out: Path, version, *, preview=None) -> int:
    """One stamped version as a standalone HTML file.

    The copy is the page as the browser finished drawing it, which is the only way to
    get one: half the document is written by the widget layer at runtime, a mermaid
    diagram becomes an SVG only once mermaid has drawn it, and a code block is colored
    by the vendored tokenizer in the page rather than by anything that can read the
    file. So Chrome is not an optimisation here and no `x-` key exempts a widget from
    it; without a browser there is nothing to copy at all."""
    preview = preview_server if preview is None else preview
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "export needs Playwright; run it as\n"
            "  leaf version export <page> -o <file>\n"
            "or, from a checkout,\n"
            "  bin/leaf version export <page> -o <file>"
        )
    published = published_versions(page_dir, read_events(page_dir))
    if not published:
        sys.exit(
            f"{page_dir} has no stamped version to export; "
            "run `leaf version stamp` first"
        )
    version = version if version else published[-1]
    if version not in published:
        sys.exit(
            f"v{version} is not stamped — stamped: "
            + ", ".join(f"v{v}" for v in published)
        )
    name = version_name(version)

    with preview(page_dir, version) as url, sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")
        except PlaywrightError as e:
            sys.exit(
                f"export needs Chrome, and it didn't launch ({str(e).strip().splitlines()[0]}). "
                "A copy is the drawn page, so there is nothing to write without one."
            )
        try:
            html = export_page(browser, url, page_dir)
        finally:
            browser.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✓ {name} → {out} ({out.stat().st_size // 1024} KB, opens with no server)")
    return 0
