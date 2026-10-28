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
box is its own, a host whose shadow tree draws nothing but the press, as a vendor
control's host draws the face around the button inside it, and a `::before` that
frames the press's words or symbol and paints at rest or under the pointer, which is
then the face's box (its size, fill, border and radius) while the press keeps the
ink, as Send, Dictate, Resolve and the response trigger draw their faces inside a
larger hit box (response.css). A smaller `::before`, such as a row's dot, is
decoration and not read.

A face is what makes two presses read as different kinds, at rest and again under
the pointer: its fill, border and corner radii, its shadow, its ink (the words'
colour, an input's value's, an icon's stroke or fill), a worded press's font,
underline, and opacity. Size is not
part of it, since a symbol is sized to the surface it sits on
(`--lf-icon-action-face`): a face lists the sizes its presses come in (a symbol's
width and height; a worded press's height and side padding, since its width is its
label's), at rest and under the pointer, and a press that changes size but not face
is reported as resized. Colours compare as sRGB at 8 bits and whole percents of
alpha; a dark state's colours compare as the light colours of the root tokens that
hold them (`light`), so a press drawn from the same tokens in both schemes is one
face. Token names only label a report, one name per colour across both arms
(`token_name`), so renaming or aliasing a token changes no face. Each face's name is
a hash of that look, so the same face has the same name in every run.

The reading is per state, in that state's scheme and viewport; a face only dark
states show is marked as dark. A press reads at rest with the pointer off the page,
wherever the state left it; a press something the state hovers reveals, such as a
heading's Copy link, reads with the pointer back at the centre of the innermost
element the state left hovered, where Playwright's hover puts it, and is marked as
revealed by hover. A press the state leaves focused, selected, expanded or disabled
reads as it is shown, and the report marks a face whose presses all share one of
those conditions. A state under a finger has no pointer, so its presses read as the
state leaves them and have no hover reading.

What it can't see: presses outside the viewport, behind something else, inside an
iframe (a live sample) or a closed shadow root; a press that appears only once its
container is hovered, unless a state hovers there; anything a hover opens over the
next press, which then has no hover reading; focus, pressed and dragging faces
except where a state leaves a press in them; motion; focus rings; and `::after`
paint, such as a badge or an unread dot.
"""

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

SCRIPT = Path(__file__).with_suffix(".js")
COLOUR = re.compile(r"#[0-9a-f]{6}(?: \d+%)?")
# How far a relabelled press's centre may sit from its old one and still be it.
NEARBY = 8


def read_faces(page: Page, *, hover: bool) -> dict:
    """Read every press the state shows at rest and, when `hover`, under the pointer:
    `{"presses": [...], "tokens": {colour: [root custom properties]}}`, and in a dark
    page `"light tokens"`, the same properties as the light scheme resolves them.

    Moves the pointer and turns the page light, so read once the state is captured."""
    page.evaluate(SCRIPT.read_text())
    count = page.evaluate("() => leafDevFaces.collect()")
    resting = page.evaluate("() => leafDevFaces.resting()")
    if hover:
        # At rest is under no pointer, wherever the state left it.
        page.mouse.move(-1, -1)
    page.evaluate("() => leafDevFaces.rest(false)")
    if hover and resting:
        page.mouse.move(resting["x"], resting["y"])
        page.evaluate("() => leafDevFaces.rest(true)")
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
    found = page.evaluate("() => leafDevFaces.finish()")
    if page.evaluate("() => matchMedia('(prefers-color-scheme: dark)').matches"):
        page.emulate_media(color_scheme="light")
        found["light tokens"] = page.evaluate("() => leafDevFaces.tokens()")
    return found


def light(reading: dict) -> Callable[[str], str]:
    """How a colour in `reading`'s state compares: as itself in a light page, and in a
    dark one as the light colour of the tokens that hold it (a translucent colour no
    token holds through its opaque colour's), so a press drawn from the same tokens in
    both schemes is one face whatever the tokens are called. A dark colour whose
    tokens name no one light colour compares as itself, marked `dark:`."""
    if "light tokens" not in reading:
        return lambda colour: colour
    shades = {
        name: colour
        for colour, names in reading["light tokens"].items()
        for name in names
    }

    def translate(colour: str) -> str:
        opaque, _, alpha = colour.partition(" ")
        names, suffix = reading["tokens"].get(colour), ""
        if not names and alpha:
            names, suffix = reading["tokens"].get(opaque), f" {alpha}"
        found = {shades[name] for name in names or () if name in shades}
        if len(found) == 1:
            (shade,) = found
            if not (suffix and " " in shade):
                return shade + suffix
        return f"dark:{colour.removeprefix('#')}"

    return translate


def held(*censuses: dict[str, dict]) -> dict[str, set[str]]:
    """Every root token by the light colour it holds, across both arms, so a colour
    has one name throughout a report."""
    found = defaultdict(set)
    for census in censuses:
        for reading in census.values():
            for colour, names in reading.get("light tokens", reading["tokens"]).items():
                found[colour].update(names)
    return found


def token_name(colour: str, tokens: dict[str, set[str]]) -> str:
    """The token that holds `colour`, preferring the theme's own over Leaf's internal
    `--lf-` ones and the shortest of those. A translucent colour no token holds is its
    opaque colour's token at its alpha (`--ink 72%`), as a mix with transparent draws
    it; any other is itself."""

    def preferred(names: set[str]) -> str:
        return min(names, key=lambda n: (n.startswith("--lf-"), len(n), n))

    if names := tokens.get(colour):
        return preferred(names)
    opaque, _, alpha = colour.partition(" ")
    if alpha and (names := tokens.get(opaque)):
        return f"{preferred(names)} {alpha}"
    return colour


def look(face: dict | None, translate: Callable[[str], str]) -> dict | None:
    """A face's reading as a kind of face: its colours as they compare (`light`), and
    its size left out, since a symbol is sized to its surface."""
    if face is None:
        return None
    compared = COLOUR.sub(lambda colour: translate(colour.group()), json.dumps(face))
    return {
        field: value for field, value in json.loads(compared).items() if field != "size"
    }


def signature(press: dict, translate: Callable[[str], str]) -> str:
    return json.dumps(
        {
            "words": press["words"],
            "rest": look(press["rest"], translate),
            "hover": look(press["hover"], translate),
        },
        sort_keys=True,
    )


def name(face: str) -> str:
    return hashlib.sha1(face.encode()).hexdigest()[:6]


# What pairs a press across arms, in order: its own id or key, its label within its
# nearest keyed ancestor, its label. Each pairs only presses it names once on each side.
STAGES = (
    lambda press: press.get("key"),
    lambda press: press.get("scope") and (press["scope"], press["label"]),
    lambda press: press["label"] or None,
)


def once(presses: list[dict], stage: Callable[[dict], object]) -> dict:
    counted = Counter(stage(press) for press in presses)
    return {
        stage(press): press
        for press in presses
        if stage(press) is not None and counted[stage(press)] == 1
    }


def pairs(base: dict[str, dict], head: dict[str, dict]):
    """Each press both arms show, as (state, base press, head press): paired by the
    first of `STAGES` that names it once on each side, then a press left over, such
    as one of two that share a label, by where it sits, its centre within `NEARBY`
    pixels of the other's."""
    for state, reading in base.items():
        before, after = list(reading["presses"]), list(head[state]["presses"])
        for stage in STAGES:
            mine, theirs = once(before, stage), once(after, stage)
            matched = mine.keys() & theirs.keys()
            for value in matched:
                yield state, mine[value], theirs[value]
            taken = {id(mine[value]) for value in matched}
            taken |= {id(theirs[value]) for value in matched}
            before = [press for press in before if id(press) not in taken]
            after = [press for press in after if id(press) not in taken]
        for press in before:
            spaced = [
                (math.dist(other["at"], press["at"]), index)
                for index, other in enumerate(after)
            ]
            if spaced and (closest := min(spaced))[0] <= NEARBY:
                yield state, press, after.pop(closest[1])


def words_for(field: str, value, words: bool) -> str:
    match field:
        case "size":
            if not words:
                return f"{value['width']}×{value['height']}"
            left, right = value["sides"]
            sides = left if left == right else f"{left}/{right}"
            return f"{value['height']} tall (sides {sides})"
        case "fill":
            return f"fill {value}" if value else "no fill"
        case "image":
            return "background image" if value else "no background image"
        case "border":
            if not value:
                return "no border"
            if isinstance(value, str):
                return f"border {value}"
            return ", ".join(f"{side} border {v}" for side, v in value.items())
        case "radius":
            return (
                ""
                if value is None
                else "round"
                if value == "round"
                else f"radius {value}"
            )
        case "shadow":
            return f"shadow {value}" if value else "no shadow"
        case "ink":
            return f"ink {value}" if value else "no ink read"
        case "font":
            return f"{value[0]}px {value[1]} {value[2]}" if value else ""
        case "underline":
            return "underlined" if value else "not underlined"
        case "opacity":
            return "invisible" if value == 0 else f"opacity {value}"
    raise ValueError(field)


def describe(
    rest: dict, hover: dict | None, words: bool, sizes: str, *, touch: bool
) -> list[str]:
    """A face's look in words a designer reads, at its `sizes`: at rest, then what
    the pointer changes."""
    shown = ["fill", "border", "radius", "ink", "font"]
    for field, quiet in (("image", False), ("shadow", None), ("underline", False)):
        if rest[field] != quiet:
            shown.append(field)
    if rest["opacity"] != 1:
        shown.append("opacity")
    lines = [
        f"{'worded' if words else 'symbol'} {sizes}, "
        + ", ".join(
            text for field in shown if (text := words_for(field, rest[field], words))
        )
    ]
    if hover is None:
        lines.append("no pointer (touch)" if touch else "the pointer couldn't reach it")
    else:
        changed = [
            text
            for field in rest
            if hover[field] != rest[field]
            and (text := words_for(field, hover[field], words))
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
        translate = light(reading)
        for press in reading["presses"]:
            found[signature(press, translate)].append((state, press))
    return dict(sorted(found.items(), key=lambda item: -len(item[1])))


def size_words(press: dict) -> str:
    """A press's size at rest, and under the pointer where that differs."""
    rest = words_for("size", press["rest"]["size"], press["words"])
    hover = press["hover"] and words_for("size", press["hover"]["size"], press["words"])
    return rest if hover in (None, rest) else f"{rest}, {hover} under the pointer"


def sizes(members: list[tuple[str, dict]]) -> str:
    """The sizes a face's presses come in, at rest and under the pointer, smallest
    first."""
    ordered = sorted(
        (
            press[when]["size"]
            for _, press in members
            for when in ("rest", "hover")
            if press[when]
        ),
        key=lambda size: (size["height"], size.get("width", 0), size.get("sides", [])),
    )
    words = members[0][1]["words"]
    return ", ".join(dict.fromkeys(words_for("size", size, words) for size in ordered))


def example(state: str, press: dict) -> str:
    label = press["label"] if len(press["label"]) <= 40 else press["label"][:39] + "…"
    return f'{state} "{label}" {press["element"]}'


def face_lines(
    face: str,
    members: list[tuple[str, dict]],
    census: dict[str, dict],
    conditions: dict[str, set[str]],
    tokens: dict[str, set[str]],
) -> list[str]:
    state, first = members[0]
    translate = light(census[state])
    states = {member_state for member_state, _ in members}
    # What every press shares, its state's scheme and pointer included: a face drawn
    # in both schemes from the same tokens is one face, and one only dark says so.
    shared = set.intersection(
        *(set(press["flags"]) | conditions[s] for s, press in members)
    )
    what = [
        COLOUR.sub(lambda colour: token_name(colour.group(), tokens), line)
        for line in describe(
            look(first["rest"], translate),
            look(first["hover"], translate),
            first["words"],
            sizes(members),
            touch="touch" in conditions[state],
        )
    ]
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
    tokens = held(base, head)
    new = [face for face in head_faces if face not in base_faces]
    gone = [face for face in base_faces if face not in head_faces]
    moves, resized = defaultdict(list), defaultdict(list)
    for state, before, after in pairs(base, head):
        was = signature(before, light(base[state]))
        now = signature(after, light(head[state]))
        label = (
            f'"{before["label"]}" → "{after["label"]}"'
            if before["label"] != after["label"]
            else f'"{after["label"]}"'
        )
        if was != now:
            moves[name(was), name(now)].append(f"{state} {label}")
        elif (old := size_words(before)) != (size := size_words(after)):
            resized[name(now)].append(f"{state} {label} {old} → {size}")
    count = sum(len(reading["presses"]) for reading in head.values())
    moved = sum(len(presses) for presses in moves.values())
    lines = [
        (
            f"Press faces in {len(states)} states: HEAD draws {len(head_faces)} faces "
            f"over {count} presses, the base {len(base_faces)}; {len(new)} new, "
            f"{len(gone)} gone, {moved} presses moved to another face."
        ),
        "",
    ]
    for face, members in head_faces.items():
        lines += face_lines(face, members, head, conditions, tokens)
    lines += ["", f"New in HEAD ({len(new)}):"]
    for face in new:
        lines += face_lines(face, head_faces[face], head, conditions, tokens)
    lines += ["", f"Gone from the base ({len(gone)}):"]
    for face in gone:
        lines += face_lines(face, base_faces[face], base, conditions, tokens)
    lines += ["", f"Moved to another face ({moved} presses):"]
    for (was, now), presses in sorted(moves.items(), key=lambda item: -len(item[1])):
        presses.sort()
        more = f" (+{len(presses) - 4})" if len(presses) > 4 else ""
        lines.append(
            f"  {was} → {now}  {len(presses):>3}  {'; '.join(presses[:4])}{more}"
        )
    total = sum(len(presses) for presses in resized.values())
    lines += ["", f"Resized within their face ({total} presses):"]
    for face, presses in sorted(resized.items()):
        lines += [f"  {face}  {press}" for press in sorted(presses)]
    return "\n".join(lines), len(new)
