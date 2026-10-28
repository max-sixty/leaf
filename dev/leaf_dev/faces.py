"""Read what every press on screen looks like, group presses that look alike into
faces, and say which faces a candidate adds, drops or moves a press between.

`leaf-dev stills --faces` runs it in each catalogue state on both arms. Leaf's
controls should wear one face per kind (`ACTION_FACES` in browser/runtime/prepaint.js,
drawn in browser/styles/components/controls.css), and a scan of the source sees only
class names, while a press can take a stray look through the cascade, a shadow-tree
part or a family's own rules. So this reads the rendered press instead.

A press is a button in any spelling, a tab, a menu row, a disclosure's summary, or a
link laid out as a box rather than a run of prose, in the document or an open shadow
root, whose centre is in the viewport and takes the pointer there (faces.js, `PRESS`).
What paints it counts as one press, fills composited: the ancestors and parts whose
box is its own, and a host whose shadow tree draws nothing but the press, as a vendor
control's host draws the face around the button inside it.

A face is what makes two presses read as different kinds, at rest and again under
the pointer: the box's size (a symbol's width and height; a worded press's height and
side padding, since its width is its label's), its fill, border and radius, its
shadow, its ink (the words' colour, an icon's stroke or fill), a worded press's font,
underline, and opacity. Colours are resolved to sRGB and named to 8 bits and whole
percents of alpha, so two tokens that resolve alike compare equal and a report can
name a colour by the root token that holds it; sizes are whole pixels. Each face's
name is a hash of that reading, so the same face has the same name in every run.

The reading is per state, in that state's scheme and viewport, so a kind drawn in
light and dark is two faces. A press the state leaves focused, hovered, selected,
expanded or disabled reads as it is shown, and the report marks a face whose presses
all share one of those conditions. A press something the state hovers reveals, such
as a heading's Copy link, is reached by returning the pointer to the centre of the
innermost element the state left hovered, where Playwright's hover puts it. A state
under a finger has no pointer, so its presses have no hover reading.

What it can't see: presses outside the viewport, behind something else, inside an
iframe (a live sample) or a closed shadow root; a press that appears only once its
container is hovered, unless a state hovers there; anything a hover opens over the
next press, which then has no hover reading; focus, pressed and dragging faces
except where a state leaves a press in them; motion; and pseudo-element paint, such
as a focus ring or a badge drawn by `::after`.
"""

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from playwright.sync_api import Page

SCRIPT = Path(__file__).with_suffix(".js")
COLOUR = re.compile(r"#[0-9a-f]{6}(?: \d+%)?")
# How far a relabelled press's centre may sit from its old one and still be it.
NEARBY = 8


def read_faces(page: Page, *, hover: bool) -> dict:
    """Read every press on screen at rest and, when `hover`, under the pointer:
    `{"presses": [...], "tokens": {colour: [root custom properties]}}`.

    Moves the pointer, so read after anything that captures the state as left."""
    page.evaluate(SCRIPT.read_text())
    count = page.evaluate("() => leafDevFaces.collect()")
    resting = page.evaluate("() => leafDevFaces.resting()")
    if hover:
        for index in range(count):
            point = page.evaluate("i => leafDevFaces.point(i)", index)
            if point is None and resting:
                # Something the state hovered may have revealed it: hover that again.
                page.mouse.move(resting["x"], resting["y"])
                point = page.evaluate("i => leafDevFaces.point(i)", index)
            if point:
                page.mouse.move(point["x"], point["y"])
                page.evaluate("i => leafDevFaces.hovered(i)", index)
    return page.evaluate("() => leafDevFaces.finish()")


def signature(press: dict) -> str:
    return json.dumps(
        {"words": press["words"], "rest": press["rest"], "hover": press["hover"]},
        sort_keys=True,
    )


def name(face: str) -> str:
    return hashlib.sha1(face.encode()).hexdigest()[:6]


def by_label(reading: dict) -> dict[tuple[str, int], dict]:
    """A state's presses keyed by label and order among presses of that label, which
    stay put when an arm restyles them."""
    seen = Counter()
    keyed = {}
    for press in reading["presses"]:
        seen[press["label"]] += 1
        keyed[press["label"], seen[press["label"]]] = press
    return keyed


def pairs(base: dict[str, dict], head: dict[str, dict]):
    """Each press both arms show, as (state, base press, head press): matched by
    label, then a press one arm relabels by where it sits, its centre within
    `NEARBY` pixels of the other's."""
    for state, reading in base.items():
        before, after = by_label(reading), by_label(head[state])
        for key in before.keys() & after.keys():
            yield state, before[key], after[key]
        unmatched = [press for key, press in after.items() if key not in before]
        for press in (press for key, press in before.items() if key not in after):
            spaced = [
                (math.dist(other["at"], press["at"]), index)
                for index, other in enumerate(unmatched)
            ]
            if spaced and (closest := min(spaced))[0] <= NEARBY:
                yield state, press, unmatched.pop(closest[1])


def token_name(colour: str, tokens: dict[str, list[str]]) -> str:
    """The root token that holds `colour`, preferring the theme's own over Leaf's
    internal `--lf-` ones and the shortest of those, else the colour itself."""
    names = tokens.get(colour)
    return (
        min(names, key=lambda n: (n.startswith("--lf-"), len(n), n))
        if names
        else colour
    )


def words_for(field: str, value, words: bool, tokens: dict[str, list[str]]) -> str:
    def named(text: str) -> str:
        return COLOUR.sub(lambda colour: token_name(colour.group(), tokens), text)

    match field:
        case "size":
            if not words:
                return f"{value['width']}×{value['height']}"
            left, right = value["sides"]
            sides = left if left == right else f"{left}/{right}"
            return f"{value['height']} tall, sides {sides}"
        case "fill":
            return f"fill {named(value)}" if value else "no fill"
        case "image":
            return "background image" if value else "no background image"
        case "border":
            if not value:
                return "no border"
            if isinstance(value, str):
                return f"border {named(value)}"
            return ", ".join(f"{side} border {named(v)}" for side, v in value.items())
        case "radius":
            return (
                ""
                if value is None
                else "round"
                if value == "round"
                else f"radius {value}"
            )
        case "shadow":
            return f"shadow {named(value)}" if value else "no shadow"
        case "ink":
            return f"ink {named(value)}" if value else "no ink read"
        case "font":
            return f"{value[0]}px {value[1]} {value[2]}" if value else ""
        case "underline":
            return "underlined" if value else "not underlined"
        case "opacity":
            return "invisible" if value == 0 else f"opacity {value}"
    raise ValueError(field)


def describe(press: dict, tokens: dict[str, list[str]], *, touch: bool) -> list[str]:
    """A face in words a designer reads: at rest, then what the pointer changes."""
    rest, hover, words = press["rest"], press["hover"], press["words"]
    shown = ["size", "fill", "border", "radius", "ink", "font"]
    for field, quiet in (("image", False), ("shadow", None), ("underline", False)):
        if rest[field] != quiet:
            shown.append(field)
    if rest["opacity"] != 1:
        shown.append("opacity")
    lines = [
        ("worded " if words else "symbol ")
        + ", ".join(
            text
            for field in shown
            if (text := words_for(field, rest[field], words, tokens))
        )
    ]
    if hover is None:
        lines.append("no pointer (touch)" if touch else "the pointer couldn't reach it")
    else:
        changed = [
            text
            for field in rest
            if hover[field] != rest[field]
            and (text := words_for(field, hover[field], words, tokens))
        ]
        lines.append(
            "under the pointer: " + ", ".join(changed)
            if changed
            else "unchanged under the pointer"
        )
    return lines


def groups(census: dict[str, dict]) -> dict[str, list[tuple[str, dict]]]:
    """Each face's presses as (state, press), largest face first."""
    found = defaultdict(list)
    for state, reading in census.items():
        for press in reading["presses"]:
            found[signature(press)].append((state, press))
    return dict(sorted(found.items(), key=lambda item: -len(item[1])))


def example(state: str, press: dict) -> str:
    label = press["label"] if len(press["label"]) <= 40 else press["label"][:39] + "…"
    return f'{state} "{label}" {press["element"]}'


def face_lines(
    face: str,
    members: list[tuple[str, dict]],
    census: dict[str, dict],
    conditions: dict[str, set[str]],
) -> list[str]:
    state, first = members[0]
    states = {member_state for member_state, _ in members}
    # What every press shares, its state's scheme and pointer included, since tokens
    # name a dark face's colours as they name a light one's.
    shared = set.intersection(
        *(set(press["flags"]) | conditions[s] for s, press in members)
    )
    what = describe(first, census[state]["tokens"], touch="touch" in conditions[state])
    if shared:
        what[0] += f" ({', '.join(sorted(shared))})"
    head = f"{name(face)}  {len(members):>3} in {len(states)} state{'s' * (len(states) > 1)}"
    pad = " " * 8
    # One press from each of the first states, then more from those if they're few.
    first_in_state = {}
    for member in members:
        first_in_state.setdefault(member[0], member)
    shown = list(first_in_state.values())[:3]
    shown += [member for member in members if member not in shown][: 3 - len(shown)]
    more = f" (+{len(members) - len(shown)})" if len(members) > len(shown) else ""
    return [
        f"{head}  {what[0]}",
        f"{pad}{what[1]}",
        f"{pad}e.g. {'; '.join(example(s, p) for s, p in shown)}{more}",
    ]


def report(
    base: dict[str, dict], head: dict[str, dict], conditions: dict[str, set[str]]
) -> tuple[str, int]:
    """The faces HEAD draws, then those it adds and drops against the base and the
    presses that moved between faces, over the states both arms read; `conditions`
    holds each state's "dark" and "touch". Returns the report and the number of faces
    HEAD adds."""
    states = sorted(base.keys() & head.keys())
    base = {state: base[state] for state in states}
    head = {state: head[state] for state in states}
    head_faces, base_faces = groups(head), groups(base)
    count = sum(len(reading["presses"]) for reading in head.values())
    lines = [
        (
            f"Press faces in {len(states)} states: HEAD draws {len(head_faces)} faces "
            f"over {count} presses; the base drew {len(base_faces)}."
        ),
        "",
    ]
    for face, members in head_faces.items():
        lines += face_lines(face, members, head, conditions)
    new = [face for face in head_faces if face not in base_faces]
    gone = [face for face in base_faces if face not in head_faces]
    lines += ["", f"New in HEAD ({len(new)}):"]
    for face in new:
        lines += face_lines(face, head_faces[face], head, conditions)
    lines += ["", f"Gone from the base ({len(gone)}):"]
    for face in gone:
        lines += face_lines(face, base_faces[face], base, conditions)
    moves = defaultdict(list)
    for state, before, after in pairs(base, head):
        was, now = signature(before), signature(after)
        if was != now:
            relabelled = before["label"] != after["label"]
            label = (
                f'"{before["label"]}" → "{after["label"]}"'
                if relabelled
                else f'"{after["label"]}"'
            )
            moves[name(was), name(now)].append(f"{state} {label}")
    total = sum(len(moved) for moved in moves.values())
    lines += ["", f"Moved to another face ({total} presses):"]
    for (was, now), moved in sorted(moves.items(), key=lambda item: -len(item[1])):
        moved.sort()
        more = f" (+{len(moved) - 4})" if len(moved) > 4 else ""
        lines.append(f"  {was} → {now}  {len(moved):>3}  {'; '.join(moved[:4])}{more}")
    return "\n".join(lines), len(new)
