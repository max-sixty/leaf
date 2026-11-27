"""Read each UI state for Leaf's boxes that neither meet their frame's edge nor stand
clear of it (`browser/AGENTS.md`, "A box inside a frame either meets its edge or
stands clear of it").

    uv run leaf-dev edges [--base [REF]] [--state NAME]... [--viewport WIDTHxHEIGHT|NAME]
        [--scheme dark] [--touch] [--browser ENGINE]

Each state of `leaf_dev.states` (all of them unless `--state` names some) is visited
through the loop `leaf-dev stills` and `probe` run (`leaf_dev.visits`), on this working
tree and, with `--base`, on the base too, and `edges.js` reads the settled tab: each
box Leaf draws, its frame, and the clearance on each side the frame shows. Its header
says what counts as a box, a frame and a finding.

The run writes `findings.json` under `.tmp/edges/run-*/`, every arm's findings by
state, and prints each distinct finding (kind, side, box, frame) once per arm with the
nearest clearance it read, the states that show it and a crop of its box where one
state shows it uncovered (`crops/ARM/`), so a finding a shared surface repeats on many
pages reads as one line. With `--base`, it then lists the findings each state gains
and loses on the head, which are the ones a change causes. A state that fails to open
is listed with its error; the rest still run.
"""

import json
import time
import traceback
from collections import defaultdict
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import base_option, choose_arms, describe, run_directory
from leaf_dev.browser import Window, chosen_window, engine_option, launch, tab_options
from leaf_dev.example_data import named_source
from leaf_dev.states import STATES
from leaf_dev.visits import Visit, said, visits

OUT = ROOT / ".tmp" / "edges"
# Device pixels to a CSS pixel in each crop, and the CSS pixels a crop keeps around
# its box, enough to show the frame's edge beside it.
SCALE = 3
CROP_ROOM = 24
READING = (Path(__file__).parent.parent / "edges.js").read_text()
# The `lf-` classes an author may write, which mark the author's boxes rather than
# Leaf's: the registry's class idioms (browser/AGENTS.md, "Leaf's elements wear only
# Leaf's names").
IDIOMS = sorted(
    {
        key.split(".", 1)[1].split(" ")[0].split("[")[0]
        for key in json.loads((ROOT / "browser" / "registry.json").read_text())
        if ".lf-" in key
    }
)


def key(finding: dict) -> tuple[str, str, str, str]:
    """A finding as it reads wherever a surface repeats it: kind, side, box, frame."""
    return finding["kind"], finding["side"], finding["box"], finding["frame"]


def read_edges(found: dict, crops: Path, state: str, arm: str, visit: Visit) -> None:
    """Read the settled tab `visit` reached for `state` into `found`, and crop the
    window around the box of each finding this arm hasn't shown yet, where the box is
    on screen and uncovered, at `SCALE`, into `crops`/ARM/, naming the crop in the
    finding."""
    page = visit.page
    reading = page.evaluate(READING, {"idioms": IDIOMS})
    found[arm][state] = reading
    shown = {
        key(f)
        for readings in found[arm].values()
        for f in readings.get("findings", [])
        if "crop" in f
    }
    window = page.viewport_size
    for finding in reading.get("findings", []):
        if key(finding) in shown or finding["covered"]:
            continue
        shown.add(key(finding))
        left, top, width, height = finding["at"]
        x, y = max(0, left - CROP_ROOM), max(0, top - CROP_ROOM)
        right = min(window["width"], left + width + CROP_ROOM)
        bottom = min(window["height"], top + height + CROP_ROOM)
        if right - x < 2 or bottom - y < 2:
            continue
        folder = crops / arm
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{len(list(folder.iterdir())):03}.png"
        page.screenshot(
            path=path, clip={"x": x, "y": y, "width": right - x, "height": bottom - y}
        )
        finding["crop"] = str(path)


@click.command()
@base_option()
@click.option(
    "--state",
    "names",
    type=click.Choice([state.name for state in STATES]),
    metavar="NAME",
    multiple=True,
    help="Read a state of leaf_dev.states; repeat for more. Defaults to them all.",
)
@tab_options
@engine_option
def edges(
    base: str | None,
    names: tuple[str, ...],
    viewport: Window | None,
    scheme: str,
    touch: bool | None,
    engine: str,
) -> None:
    """Read each UI state for Leaf's boxes that nearly meet, cross or are cut by their
    frame's edge, and round marks closer to it than --lf-clear, on this working tree
    and, with --base, the base too."""
    states = [state for state in STATES if not names or state.name in names]
    out = run_directory(OUT)
    found: dict[str, dict] = defaultdict(dict)
    failed: dict[str, list[str]] = {}
    took: dict[str, float] = {}
    started = time.monotonic()

    def write() -> None:
        """Write what has been read so far, so a run stopped partway keeps it."""
        (out / "findings.json").write_text(
            json.dumps(
                {
                    "arms": {name: arm.commit for name, arm in arms.items()},
                    "engine": engine,
                    "seconds": round(time.monotonic() - started),
                    "took": took,
                    "failed": failed,
                    "found": found,
                },
                indent=1,
            )
        )

    with launch(engine, scheme) as browser:
        scratch = out / "arms"
        arms = choose_arms(base, scratch)
        for state in states:
            began = time.monotonic()
            try:
                source = named_source(state.source)
                with visits(
                    browser,
                    arms,
                    state,
                    source,
                    scratch / state.name,
                    window=chosen_window(state.window, viewport, touch),
                    scheme=scheme,
                    scale=SCALE,
                    read=lambda arm, visit, name=state.name: read_edges(
                        found, out / "crops", name, arm, visit
                    ),
                ) as each:
                    for arm, visit in each:
                        if visit.error:
                            failed.setdefault(state.name, []).append(
                                f"{arm} on {visit.doing}: {said(visit.error)}"
                            )
                            (out / f"{state.name}-{arm}-error.txt").write_text(
                                "".join(traceback.format_exception(visit.error))
                            )
            except Exception as error:
                failed.setdefault(state.name, []).append(f"open: {said(error)}")
            took[state.name] = round(time.monotonic() - began, 1)
            write()
    click.echo(f"{describe(arms)} in {engine}, {len(states)} states")
    for arm in arms:
        distinct = defaultdict(list)
        for state, reading in found[arm].items():
            for finding in reading.get("findings", []):
                distinct[key(finding)].append(
                    (finding["gap"], state, finding.get("crop"))
                )
        click.echo(f"{arm}: {len(distinct)} distinct findings")
        for (kind, side, box, frame), seen in sorted(distinct.items()):
            gap = min(gap for gap, _, _ in seen)
            places = sorted({state for _, state, _ in seen})
            crop = next((crop for _, _, crop in seen if crop), "")
            click.echo(
                f"  {kind:8} {side:11} {gap:5}px  {box}\n"
                f"           in {frame}\n"
                f"           {len(places)} states: {', '.join(places[:4])}"
                + (" …" if len(places) > 4 else "")
                + (f"\n           {Path(crop).relative_to(out)}" if crop else "")
            )
    if "base" in arms:
        # What the head adds and clears, state by state, so a change reads only the
        # findings it causes.
        for arm, other, label in (
            ("head", "base", "new on head"),
            ("base", "head", "gone on head"),
        ):
            lines = [
                f"  {state}: {f['kind']} {f['side']} {f['gap']}px {f['box']} in {f['frame']}"
                for state, reading in found[arm].items()
                if state in found[other]
                for f in reading.get("findings", [])
                if key(f)
                not in {key(g) for g in found[other][state].get("findings", [])}
            ]
            click.echo(f"{label}: {len(lines)}")
            for line in lines:
                click.echo(line)
    for name, why in failed.items():
        click.echo(f"  failed  {name}: {'; '.join(why)}")
    click.echo(f"{round(time.monotonic() - started)} s; files in {out}")
