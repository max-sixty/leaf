"""Seat comment pins on a catalogue of targets and show where each one stands.

    uv run leaf-dev placement pins [--base [REF]]

The catalogue's cases (`_pin_cases`) stand on one page, which is opened at each of
`VIEWPORTS`, each case scrolled into view, and its pins read against what they may not
cover (`faults`).

The command builds that page from this working tree, and with `--base` from the merge
base with `main` (or REF) too (`leaf_dev.arms.choose_arms`), opens it on each arm in
each window through `leaf_dev.visits`, the loop `placement cards`, `stills` and
`probe` share, and writes a Leaf page at
`.tmp/pins/report/pins.html` that shows each case's crop at every viewport, its targets
outlined in blue, beside the faults read there. With `--base` each crop is an `lf-shot`
pair whose Pixels view marks where the base drew a pin in red and this tree in blue. Both
arms' crops of a case cover the same rectangle, so the pair lines up. Each run rewrites
that one page, so a running `--user` preview of it shows the new run as a revision, with
the threads left on it where they were. It prints the command that starts that preview.
A full run takes about 10s, and 20s with `--base`.
"""

import json
import os
import shutil
import tempfile
from html import escape
from pathlib import Path

import click

from leaf_dev import ROOT, gallery
from leaf_dev.arms import Arm, base_option, choose_arms, run_directory
from leaf_dev.browser import (
    WINDOWS,
    headless_shell,
    linux_font_environment,
    screenshot,
)
from leaf_dev.commands.placement._pin_cases import (
    CASES,
    VIEWPORTS,
    Case,
    accepted,
    events,
    faults,
    read,
    source,
    unaccepted,
)
from leaf_dev.states import State
from leaf_dev.visits import Visit, visits

OUT = ROOT / ".tmp" / "pins"
# The report every run rewrites, so a preview of it follows each run as a revision of
# one page and keeps the threads on it; each run's captures stay in its own directory.
REPORT = OUT / "report"

# Device pixels captured per CSS pixel, so a phone's crop stays sharp when the report's
# column draws it wider than the phone.
SCALE = 2


def frame(readings: list[dict]) -> tuple[int, int, int, int]:
    """The rectangle around a case and its pins in every reading of it, so each arm's
    crop of one case at one viewport covers the same place on the page."""
    rects = [
        rect
        for reading in readings
        for rect in (
            reading["box"],
            *(entry for pin in reading["pins"] for entry in pin["entries"]),
        )
    ]
    left, top, right, bottom = gallery.frame(
        rects, 16, readings[0]["width"], readings[0]["height"]
    )
    return int(left), int(top), int(right), int(bottom)


def crop(seen: dict, rect: tuple[int, int, int, int], out: Path) -> Path:
    """Crop one arm's screenshot of a case to `rect`, in CSS pixels, outlining its
    targets, and write it to `out` at the capture's SCALE."""
    image = gallery.marked(
        seen["shot"],
        (40, 110, 230),
        outlined=[
            part for target in seen["reading"]["targets"] for part in target["parts"]
        ],
        scale=SCALE,
    )
    left, top, right, bottom = rect
    image.crop((SCALE * left, SCALE * top, SCALE * right, SCALE * bottom)).save(out)
    return out


def capture(
    browser, arms: dict[str, Arm], fixture: Path, scratch: Path, out: Path
) -> dict[str, tuple[str, dict]]:
    """Open `fixture` on each arm at each viewport (`leaf_dev.visits`), screenshot
    each case under `out`, and return each arm's commit and
    `{case: {viewport: {"faults", "unaccepted", "reading", "shot"}}}`."""
    result = {
        arm: (version.commit, {case.name: {} for case in CASES})
        for arm, version in arms.items()
    }
    for viewport in VIEWPORTS:
        window = WINDOWS[viewport]

        def seen(arm: str, visit: Visit, viewport: str = viewport) -> None:
            visit.doing = "read"
            for case in CASES:
                reading = read(visit.page, case)
                shot = out / arm / f"{case.name}-{viewport}-full.png"
                shot.write_bytes(screenshot(visit.page))
                result[arm][1][case.name][viewport] = {
                    "faults": faults(reading),
                    "unaccepted": unaccepted(case, reading, viewport),
                    "reading": reading,
                    "shot": shot,
                }

        with visits(
            browser,
            arms,
            State("pins", str(fixture), window=window),
            fixture,
            scratch / viewport,
            window=window,
            scheme="light",
            scale=SCALE,
            read=seen,
        ) as each:
            for _, visit in each:
                if visit.error:
                    raise visit.error
    return result


def _fault_list(case: Case, viewport: str, found: list[tuple[str, str]]) -> str:
    if not found:
        return "none"
    return ", ".join(
        f"{kind} ({target}){' — accepted' if accepted(case, kind, viewport) else ''}"
        for kind, target in found
    )


PAIRS = (
    " Choose Pixels for changed pixels: red where the base drew something, such as"
    " a pin it has moved, and blue where this tree draws it. Slider shows the two"
    " images under a divider."
)


def report(arms: dict[str, tuple[str, dict]], out: Path) -> Path:
    """Write the Leaf page that shows every case's crops into REPORT, replacing the
    last run's, and return its path. Crops are cut into the run directory `out`."""
    media = REPORT / "media"
    shutil.rmtree(media, ignore_errors=True)
    media.mkdir(parents=True)
    head = arms["head"][1]
    base = arms.get("base")
    failing = [
        case
        for case in CASES
        if any(seen["unaccepted"] for seen in head[case.name].values())
    ]
    against = f" against the base, {base[0][:10]}" if base else ""
    summary = (
        "<p>No case has a fault its <code>allow</code> does not accept.</p>"
        if not failing
        else "<p>Cases with a fault their <code>allow</code> does not accept:</p><ul>"
        + "".join(
            f'<li><a href="#{case.name}">{case.name}</a></li>' for case in failing
        )
        + "</ul>"
    )
    sections = []
    for case in CASES:
        rows = []
        for viewport in VIEWPORTS:
            seen = head[case.name][viewport]
            before = base[1][case.name][viewport] if base else None
            rect = frame([seen["reading"], *([before["reading"]] if before else [])])
            stem = out / f"{case.name}-{viewport}"
            after = crop(seen, rect, stem.with_suffix(".head.png"))
            before_image = None
            line = f"<p><strong>{viewport}</strong>: faults {_fault_list(case, viewport, seen['faults'])}"
            if before:
                line += (
                    f"; on the base, {_fault_list(case, viewport, before['faults'])}"
                )
                base_crop = crop(before, rect, stem.with_suffix(".base.png"))
                before_image = gallery.media(media, base_crop.read_bytes())
            picture = gallery.shot(
                f"{case.name}-{viewport}-shot",
                f"the {case.name} case at {viewport} width",
                before_image,
                gallery.media(media, after.read_bytes()),
            )
            rows.append(f"{line}</p>\n{picture}")
        sections.append(
            f'<section id="{case.name}">\n<h2>{case.name}</h2>\n'
            f"<p>{escape(case.says)}</p>\n"
            + (f"<p>Accepted: {escape(case.why)}</p>\n" if case.why else "")
            + "\n".join(rows)
            + "\n</section>"
        )
    page = REPORT / "pins.html"
    page.write_text(
        gallery.page(
            "Pin cases",
            "Where Leaf seats a comment's pin on each of a catalogue of targets.",
            f"""<header id="intro">
<h1>Pin cases</h1>
<p>{len(CASES)} cases on this working tree{against}, at
{" and ".join(f"{v} ({WINDOWS[v].size[0]}px)" for v in VIEWPORTS)}. Targets are
outlined in blue.{PAIRS if base else ""}</p>
<p>These are few, and not chosen to flatter the placement: they are the shapes that
came to mind for a pin to sit on. Where a page shows a placement that looks wrong,
add its shape here as a case.</p>
{summary}
</header>
{chr(10).join(sections)}""",
        ),
        encoding="utf-8",
    )
    return page


@click.command()
@base_option()
def pins(base) -> None:
    """Seat every pin case on this working tree, and write a Leaf page of crops."""
    os.environ.update(linux_font_environment())
    OUT.mkdir(parents=True, exist_ok=True)
    out = run_directory(OUT)
    with tempfile.TemporaryDirectory(prefix="leaf-pins-") as built:
        scratch = Path(built)
        fixture = scratch / "cases.html"
        fixture.write_text(source(), encoding="utf-8")
        fixture.with_suffix(".jsonl").write_text(
            "".join(
                json.dumps(
                    {**event, "id": f"pin{index:04d}", "ts": "2026-10-13T00:00:00Z"}
                )
                + "\n"
                for index, event in enumerate(events())
            ),
            encoding="utf-8",
        )
        arms = choose_arms(base, scratch)
        for arm in arms:
            (out / arm).mkdir()
        with headless_shell() as browser:
            readings = capture(browser, arms, fixture, scratch, out)
    page = report(readings, out)
    click.echo(page)
    click.echo(f"uv run leaf-dev preview --source {page} --slot pins --user")
