"""A page written as an ordinary web page gets the page its author wrote (`SOUL.md`,
"Primitives, not a template").

The corpus is `tests/fixtures/plain/`: standalone pages, each written as an author
writes for the open web and showing a pattern the others don't, whose one
Leaf-specific edit is that the body's content sits in one `main`. Each brings its own
design, so each takes no theme, as `page-authoring.md`, "Style the page", tells such
a page to: what the comparison holds is Leaf's core sheet and runtime, never the
reading look a page takes by default. A new ordinary pattern gets a page of its own,
as small as shows it. They stay out of the example
corpus (`examples/AGENTS.md`), whose sweeps also hold Leaf's own pages to the suite's
rules, such as writing nothing that changes nothing (`write_watch.js`), which an
author's script owes nobody.

For each page the test asks what `page check --render` asks, through the same
readings (`render_gate.command.browser_check`): the source check, the page's code and
the render gate refuse nothing. Then it serves the page twice, as a static site and as
the candidate the gate read, and compares what the author's CSS decides. Which
properties those are it reads from the standalone page through the DevTools protocol:
a property is the author's on an element when an author rule or the element's own
style declares it there, or, for an inherited property, when the nearest ancestor
declaring it does so in an author rule. On those properties (colour, type, spacing,
display and grid, position, size, motion) every page element, `html` and `body`
included, computes the same in both. A theme default showing through on a property
the author left alone is Leaf's documented offer (`page-authoring.md`, "Style the
page") and is not compared. Four readings beyond the properties follow the same rule:
a box the author positions (sticky, fixed or absolute) stands in the same place at
rest and after the page scrolls; the canvas around `body`, where it shows, keeps the
author's root background; an open `dialog` keeps its look; and the root keeps the
colour scheme the author left it at, since that decides every system colour under the
page. Leaf's chrome and what it generates (`.lf-ui`, `[data-lf-gen]`) are not the
page's; an element of the author's missing from the Leaf page, or one Leaf adds among
them, is a finding. Each page is read in two media, light with motion and dark with
reduced motion, so a dark palette and a reduced-motion guard are both the author's
to answer.

Every finding is against Leaf, never the page. Fix Leaf, or, where lifting the
obstacle needs the maintainer's decision, name it in `OBSTACLES` and pin what it
does to each page in `KNOWN`, each finding by its kind, property and elements: such a
page is reported as an expected failure, any finding not pinned still fails it, so an
override of the same kind reaching another property or element is caught, and a pin
that no longer occurs fails it until it goes. A failure prints each new finding's pin
first, ready to file; when an obstacle lifts, its entries go.
"""

import hashlib
import shutil
from contextlib import ExitStack, contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from interact_support import running_http_server
from render_harness import ROOT

from leaf.event_log import read_events
from leaf.render_checks import rendered, wait_until_ready
from leaf.render_gate.page_code import needs_browser, run_page_code
from leaf.render_gate.preview import preview_server
from leaf.render_gate.version import render_version
from leaf.validation.source import check_source

SOURCES = sorted((ROOT / "tests" / "fixtures" / "plain").glob("*.html"))
# The obstacles a decision has yet to lift, and below, each page's findings they
# explain, by pin (`differences`, `checked`).
OBSTACLES = {
    "scroll-clearance": (
        "Leaf makes a table or pre scroll inside itself rather than widen the page"
        " (reading.css), and keeps 8px under its last row for an overlay scrollbar,"
        " so a grid row holding a table is that much taller"
    ),
    "canvas": (
        "body is a size container (theme.css, container: lf-shell), the shell a Layout"
        " and a widget's 100cqi ask, and containment keeps its background off the"
        " canvas, so a page shorter than the window ends in the browser's canvas below"
        " the body the author coloured"
    ),
}
KNOWN = {
    "dashboard": {
        "scroll-clearance": {
            "dark overridden grid-template-rows on main #0d6e4079",
            "light overridden grid-template-rows on main #0d6e4079",
        },
    },
    "form": {"canvas": {"canvas around body"}},
    "module": {"canvas": {"canvas around body"}},
    "motion": {"canvas": {"canvas around body"}},
}

# A page that builds content after it loads says it has finished as a page does to
# assistive technology: no region of it is still busy.
LOADED = "!document.querySelector('body > main [aria-busy=true]')"
VIEWPORT = {"width": 1200, "height": 900}
MEDIA = (
    {"color_scheme": "light", "reduced_motion": "no-preference"},
    {"color_scheme": "dark", "reduced_motion": "reduce"},
)
SCROLL_BY = 400
# The longhands that make a page's look, as `getComputedStyle` names them. Opacity,
# transforms and background positions are left out, since animations drive them; the
# animation properties say whether the author's motion runs.
SIDES = ("top", "right", "bottom", "left")
COMPARED = frozenset(
    {
        *("color", "background-color", "background-image", "color-scheme"),
        *("accent-color", "box-shadow"),
        *(
            f"border-{side}-{part}"
            for side in SIDES
            for part in ("width", "style", "color")
        ),
        *(
            f"border-{y}-{x}-radius"
            for y in ("top", "bottom")
            for x in ("left", "right")
        ),
        *("font-family", "font-size", "font-weight", "font-style", "line-height"),
        *("letter-spacing", "text-transform", "text-align", "text-decoration-line"),
        *("font-variant-numeric", "font-feature-settings", "white-space"),
        *(f"{box}-{side}" for box in ("margin", "padding") for side in SIDES),
        *("row-gap", "column-gap", "display", "grid-template-columns"),
        *("grid-template-rows", "grid-auto-flow", "grid-auto-columns"),
        *("grid-column-start", "grid-column-end", "grid-row-start", "grid-row-end"),
        *("flex-direction", "flex-wrap", "flex-grow", "flex-shrink", "flex-basis"),
        *("justify-content", "justify-items", "align-items", "align-content"),
        *("align-self", "list-style-type", "position", *SIDES, "z-index"),
        *("width", "height", "min-width", "min-height", "max-width", "max-height"),
        *("box-sizing", "overflow-x", "overflow-y"),
        *("animation-name", "animation-duration", "animation-iteration-count"),
        *("transition-property", "transition-duration"),
    }
)
# The inherited ones: an ancestor's declaration reaches an element declaring none.
INHERITED = frozenset(
    {
        *("color", "color-scheme", "accent-color", "font-family", "font-size"),
        *("font-weight", "font-style", "line-height", "letter-spacing"),
        *("text-transform", "text-align", "font-variant-numeric"),
        *("font-feature-settings", "white-space", "list-style-type"),
    }
)
POSITIONED = frozenset({"sticky", "fixed", "absolute"})

# Every element the page wrote or its scripts built, keyed by its path from `main`
# among the page's own siblings, so a box Leaf generates shifts no index. With `mark`,
# each is marked in document order, the order CDP's querySelectorAll returns them in.
# Animations are rewound and held and transitions finished, so a reading is the same
# whenever it is taken, and boxes are measured untransformed, as layout places them.
READ = """({props, within, mark}) => {
  const generated = '.lf-ui, [data-lf-gen]';
  const main = document.querySelector('body > main');
  const own = (el) => !el.closest(generated) && !el.localName.startsWith('lf-')
    && !['script', 'style', 'template'].includes(el.localName)
    && !el.parentElement.closest('svg');
  const key = (el) => {
    if (el === document.documentElement) return 'html';
    if (el === document.body) return 'body';
    const parts = [];
    for (let e = el; e !== main; e = e.parentElement) {
      const alike = [...e.parentElement.children]
        .filter((s) => s.localName === e.localName && own(s));
      parts.unshift(`${e.localName}:${alike.indexOf(e)}`);
    }
    return ['main', ...parts].join(' > ');
  };
  for (const animation of document.getAnimations()) {
    if (animation instanceof CSSTransition) animation.finish();
    else { animation.pause(); animation.currentTime = 0; }
  }
  const roots = within
    ? [...main.querySelectorAll(within)]
    : [document.documentElement, document.body, main];
  const elements = [...new Set([
    ...roots,
    ...roots.flatMap((el) => (within || el === main ? [...el.querySelectorAll('*')] : [])),
  ])].filter((el) => roots.includes(el) || own(el));
  if (mark) {
    for (const el of document.querySelectorAll('[data-plain-read]'))
      el.removeAttribute('data-plain-read');
    for (const el of elements) el.setAttribute('data-plain-read', '');
  }
  const cs = (el) => getComputedStyle(el);
  const [html, body] = [document.documentElement, document.body];
  const propagates = cs(body).containerType === 'normal' && cs(body).contain === 'none';
  const htmlPaints = cs(html).backgroundColor !== 'rgba(0, 0, 0, 0)'
    || cs(html).backgroundImage !== 'none';
  const canvas = cs(htmlPaints || !propagates ? html : body);
  const box = body.getBoundingClientRect();
  const styles = elements.map((el) => {
    const style = cs(el);
    return Object.fromEntries(props.map((p) => [p, style.getPropertyValue(p)]));
  });
  const untransformed = new CSSStyleSheet();
  untransformed.replaceSync('* { transform: none !important; translate: none !important; rotate: none !important; scale: none !important; }');
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, untransformed];
  const rects = elements.map((el) => {
    const r = el.getBoundingClientRect();
    return [r.x, r.y, r.width, r.height].map(Math.round);
  });
  document.adoptedStyleSheets = document.adoptedStyleSheets.filter((s) => s !== untransformed);
  return {
    elements: elements.map((el, at) => ({key: key(el), style: styles[at], rect: rects[at]})),
    canvas: `${canvas.backgroundColor} ${canvas.backgroundImage}`,
    canvasShows: box.top > 0.5 || box.left > 0.5 || box.right < innerWidth - 0.5
      || box.bottom < innerHeight - 0.5,
    scrollMax: document.scrollingElement.scrollHeight - innerHeight,
  };
}"""
SCROLL = "top => document.scrollingElement.scrollTo({top, behavior: 'instant'})"
# Scroll events and media listeners run in the next rendering update.
NEXT_FRAME = "() => new Promise((resolve) => requestAnimationFrame(resolve))"
OPEN_DIALOGS = """open => {
  const dialogs = [...document.querySelectorAll('body > main dialog')];
  for (const dialog of dialogs) open ? dialog.showModal() : dialog.close();
  return dialogs.length;
}"""
SCHEME = "scheme => { document.documentElement.style.colorScheme = scheme; }"


def _declared(styles) -> tuple[set[str], bool]:
    """The properties a list of CDP styles declares, and whether one says `all`."""
    found, everything = set(), False
    for style in styles:
        for prop in style["cssProperties"]:
            if prop.get("disabled") or prop.get("parsedOk") is False:
                continue
            everything |= prop["name"] == "all"
            found.add(prop["name"])
    return found, everything


def _origins(entry) -> tuple[set[str], bool, set[str]]:
    rules = [match["rule"] for match in entry.get("matchedCSSRules", [])]
    author = [rule["style"] for rule in rules if rule["origin"] == "regular"]
    author += [entry["inlineStyle"]] if entry.get("inlineStyle") else []
    agent = [rule["style"] for rule in rules if rule["origin"] == "user-agent"]
    declared, everything = _declared(author)
    return declared, everything, _declared(agent)[0]


def authored(page) -> list[dict[str, str]]:
    """For each element the last marking READ returned, the compared properties the
    author's CSS decides there, each `own` where the element's rules declare it and
    `inherited` where an ancestor's reach it. `all` decides every property that does
    not inherit, and hands the inherited ones down from the parent."""
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
        root = cdp.send("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
        nodes = cdp.send(
            "DOM.querySelectorAll", {"nodeId": root, "selector": "[data-plain-read]"}
        )["nodeIds"]
        found = []
        for node in nodes:
            matched = cdp.send("CSS.getMatchedStylesForNode", {"nodeId": node})
            author, everything, agent = _origins(matched)
            if everything:
                author |= COMPARED - INHERITED
                agent -= INHERITED
            props = dict.fromkeys(author & COMPARED, "own")
            undecided = INHERITED - author - agent
            for ancestor in matched.get("inherited", []):
                author, everything, agent = _origins(ancestor)
                if everything:
                    author, agent = author - INHERITED, set()
                props |= dict.fromkeys(undecided & author, "inherited")
                undecided -= author | agent
            found.append(props)
        return found
    finally:
        cdp.detach()


class Arm:
    """One serving of a page: its readings in each medium, at rest and scrolled, and
    with its dialogs open."""

    def __init__(self, page, *, standalone: bool, scroll: int | None = None):
        self.page = page
        self.standalone = standalone
        self.media = []
        for medium in MEDIA:
            page.emulate_media(**medium)
            self.settle()
            self.media.append(self.read())
        page.emulate_media(**MEDIA[0])
        self.settle()
        self.scroll = (
            min(SCROLL_BY, self.media[0]["scrollMax"]) if scroll is None else scroll
        )
        page.evaluate(SCROLL, self.scroll)
        self.settle()
        self.scrolled = self.read(authored_too=False)
        page.evaluate(SCROLL, 0)
        self.settle()
        self.dialogs = None
        if page.evaluate(OPEN_DIALOGS, True):
            self.settle()
            self.dialogs = self.read(within="dialog")
            page.evaluate(OPEN_DIALOGS, False)
            self.settle()

    def dark_under(self, scheme: str) -> dict:
        """The dark medium's reading with the root's colour scheme set to `scheme`, so
        the browser's own colours resolve as they do under that scheme elsewhere."""
        dark = next(
            at for at, medium in enumerate(MEDIA) if medium["color_scheme"] == "dark"
        )
        self.page.emulate_media(**MEDIA[dark])
        self.page.evaluate(SCHEME, scheme)
        self.settle()
        reading = self.read()
        self.page.evaluate(SCHEME, "")
        self.page.emulate_media(**MEDIA[0])
        return reading

    def settle(self):
        if self.standalone:
            self.page.evaluate(NEXT_FRAME)
        else:
            rendered(self.page)

    def read(self, within=None, *, authored_too=True):
        mark = self.standalone and authored_too
        reading = self.page.evaluate(
            READ, {"props": sorted(COMPARED), "within": within, "mark": mark}
        )
        if mark:
            for element, props in zip(
                reading["elements"], authored(self.page), strict=True
            ):
                element["authored"] = props
        return reading


# Track lists resolve from what the grid holds, so a grid whose content changed has
# new tracks without any rule of Leaf's deciding them.
TRACKS = frozenset({"grid-template-columns", "grid-template-rows"})


def _parent(key: str) -> str | None:
    if key in ("html", "body", "main"):
        return {"html": None, "body": "html", "main": "body"}[key]
    return key.rsplit(" > ", 1)[0]


def _px(value: str) -> float | None:
    number = value.removesuffix("px")
    try:
        return float(number) if number != value else None
    except ValueError:
        return None


def _scaled(was: str, now: str, font: tuple[str, str] | None) -> bool:
    """Whether a length changed by exactly the ratio its font size did."""
    if font is None:
        return False
    lengths = [_px(value) for value in (was, now, *font)]
    if None in lengths or not lengths[0] or not lengths[2]:
        return False
    was, now, font_was, font_now = lengths
    return abs(now / was - font_now / font_was) < 0.005


def _styles(plain, served):
    """Each property the author decides that the Leaf page computes otherwise, as
    (kind, key, prop, leaf, plain), with the elements missing from and added to it.

    A value the author declared that resolves against something already reported
    follows from that finding and isn't another: the finding is reported, or is a
    default the author left alone. Two such resolutions are told apart here: a length
    in `em` or a unitless line height, which scales by exactly the ratio its font size
    did (a font size by its parent's), and a grid's tracks, which follow its changed
    content."""
    served_by_key = {element["key"]: element for element in served["elements"]}
    changed, missing, fonts = [], [], {}
    for element in plain["elements"]:
        other = served_by_key.get(element["key"])
        if other is None:
            missing.append(element["key"])
            continue
        fonts[element["key"]] = (
            element["style"]["font-size"],
            other["style"]["font-size"],
        )
        for prop, how in sorted(element["authored"].items()):
            if element["style"][prop] != other["style"][prop]:
                kind = "overridden" if how == "own" else "inherited"
                changed.append(
                    (
                        kind,
                        element["key"],
                        prop,
                        other["style"][prop],
                        element["style"][prop],
                    )
                )
    within = {key for _, key, *_ in changed}

    def follows(kind, key, prop, now, was):
        if kind != "overridden":
            return False
        if prop in TRACKS:
            return any(other.startswith(f"{key} > ") for other in within)
        return _scaled(
            was, now, fonts.get(_parent(key) if prop == "font-size" else key)
        )

    plain_keys = {element["key"] for element in plain["elements"]}
    added = [key for key in served_by_key if key not in plain_keys]
    return [change for change in changed if not follows(*change)], missing, added


def differences(alone: Arm, leaf: Arm) -> list[tuple[str, str, str]]:
    """Each way the Leaf page's look departs from the author's, as (kind, pin, words).
    The kinds: a property the author declared on the element (`overridden`) or that
    reached it from an ancestor (`inherited`), the `canvas`, a positioned box's
    `position`, an element `missing` from the Leaf page or `added` to it, and the root's
    `color-scheme`, where the author left it alone and Leaf's differs. A property that
    differs on several elements is one finding. Its pin names the reading, the
    property, and the complete set of elements by a digest, with the first and a count
    to read it by, and not the values, so `KNOWN` holds still while a theme's colours
    change but not while an override reaches any other element or property. The words
    list every element.

    The root's colour scheme decides what every system colour resolves to under the
    page, so where Leaf's differs, the dark medium is compared with the standalone page
    read under Leaf's scheme: what still differs there is Leaf's doing."""
    found = []

    def note(kind, pin, words):
        found.append((kind, pin, words))

    [root, *_], [served_root, *_] = (
        alone.media[0]["elements"],
        leaf.media[0]["elements"],
    )
    scheme, served_scheme = (
        root["style"]["color-scheme"],
        served_root["style"]["color-scheme"],
    )
    readings = list(alone.media)
    if "color-scheme" not in root["authored"] and scheme != served_scheme:
        note(
            "color-scheme",
            "color-scheme on the root",
            f"the root's color-scheme is {served_scheme!r}, not the {scheme!r} the"
            " page leaves it at, so in a dark medium the browser draws the page's"
            " own controls, dialogs and system colours dark",
        )
        dark = next(at for at, m in enumerate(MEDIA) if m["color_scheme"] == "dark")
        readings[dark] = alone.dark_under(served_scheme)

    def compare(label, plain, served, reading):
        changed, missing, added = _styles(plain, served)
        alike = {}
        for kind, key, prop, now, was in changed:
            alike.setdefault((kind, prop), []).append((key, now, was))
        for (kind, prop), where in alike.items():
            keys = [key for key, *_ in where]
            more = f" and {len(keys) - 1} more" if len(keys) > 1 else ""
            digest = hashlib.sha256("\n".join(sorted(keys)).encode()).hexdigest()[:8]
            values = {}
            for key, now, was in where:
                values.setdefault((now, was), []).append(key)
            note(
                kind,
                f"{reading} {kind} {prop} on {keys[0]}{more} #{digest}",
                f"{label}: {prop}, where the author's {kind} value gives "
                + "; ".join(
                    f"{was!r}, is {now!r} on {', '.join(on)}"
                    for (now, was), on in values.items()
                ),
            )
        for key in missing:
            note("missing", f"missing {key}", f"{label}: {key} is missing")
        for key in added:
            note("added", f"added {key}", f"{label}: Leaf adds {key}")
        backgrounds = {"background-color", "background-image"}
        if (
            (plain["canvasShows"] or served["canvasShows"])
            and any(
                backgrounds & set(e["authored"])
                for e in plain["elements"]
                if e["key"] in ("html", "body")
            )
            and plain["canvas"] != served["canvas"]
        ):
            note(
                "canvas",
                "canvas around body",
                f"{label}: the canvas around body is {served['canvas']!r},"
                f" not {plain['canvas']!r}",
            )

    for medium, plain, served in zip(MEDIA, readings, leaf.media, strict=True):
        compare(" and ".join(medium.values()), plain, served, medium["color_scheme"])
    if alone.dialogs:
        compare("dialog open", alone.dialogs, leaf.dialogs, "dialog")
    rest = alone.media[0]
    positioned = {
        element["key"]
        for element in rest["elements"]
        if "position" in element["authored"]
        and element["style"]["position"] in POSITIONED
    }
    for label, plain, served in (
        ("at rest", rest, leaf.media[0]),
        (f"scrolled {alone.scroll}px", alone.scrolled, leaf.scrolled),
    ):
        served_rects = {e["key"]: e["rect"] for e in served["elements"]}
        for element in plain["elements"]:
            other = served_rects.get(element["key"])
            if (
                element["key"] in positioned
                and other is not None
                and any(
                    abs(a - b) > 1 for a, b in zip(element["rect"], other, strict=True)
                )
            ):
                note(
                    "position",
                    f"position of {element['key']} {label.split()[0]}",
                    f"{label}: {element['key']} stands at {other},"
                    f" not {element['rect']}",
                )
    return found


@pytest.fixture
def static_site():
    """Serve a directory as a plain static web server does."""
    with ExitStack() as servers:

        def go(directory: Path) -> str:
            class Quiet(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(directory), **kwargs)

                def log_message(self, *args):
                    pass

            httpd = servers.enter_context(
                running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Quiet))
            )
            return f"http://127.0.0.1:{httpd.server_address[1]}/"

        yield go


def site_of(source: Path, into: Path) -> Path:
    """The page's files as its author ships them: the document, with its companion
    directory at the `page/` its scripts name."""
    into.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, into / "index.html")
    if (companion := source.with_suffix(".page")).is_dir():
        shutil.copytree(companion, into / "page", dirs_exist_ok=True)
    return into


@contextmanager
def checked(browser, page_dir: Path):
    """What `page check --render` refuses the page for, as (code, pin, words), with the URL
    the candidate it read is served at while the block runs, or None where the source
    check refused it."""
    result = check_source(page_dir, read_events(page_dir))
    if result.errors:
        yield [(e.code, f"{e.code} {e.at}", str(e)) for e in result.errors], None
        return
    with preview_server(
        page_dir,
        result.document,
        result.revision.candidate,
        transition_held=True,
        artifact=result.artifact,
    ) as url:
        found = (
            run_page_code(browser, url)
            if needs_browser(result.document, result.artifact)
            else []
        )
        if not found:
            found = render_version(
                browser,
                url,
                implementations=result.artifact.implementations,
                declaration_sources=result.artifact.declaration_sources,
            ).failures
        yield [(f.code, f"{f.code} {f.at}", str(f)) for f in found], url


@pytest.mark.parametrize("source", SOURCES, ids=lambda path: path.stem)
def test_an_ordinary_page_is_drawn_as_written(
    browser, initialized_page, static_site, tmp_path, source
):
    plain = browser.unwatched.new_page(viewport=VIEWPORT)
    plain.goto(static_site(site_of(source, tmp_path / "site")))
    plain.wait_for_function(f"document.fonts.status === 'loaded' && {LOADED}")
    alone = Arm(plain, standalone=True)

    page_dir = site_of(source, initialized_page(tmp_path / "page", (), theme=False))
    with checked(browser.unwatched, page_dir) as (found, url):
        if url is not None:
            page = browser.unwatched.new_page(viewport=VIEWPORT, color_scheme="light")
            page.goto(url)
            wait_until_ready(page)
            page.wait_for_function(LOADED)
            found += differences(
                alone, Arm(page, standalone=False, scroll=alone.scroll)
            )

    known = KNOWN.get(source.stem, {})
    pinned = {pin for pins in known.values() for pin in pins}
    unexplained = [f"{pin}: {words}" for _, pin, words in found if pin not in pinned]
    assert not unexplained, "\n".join(unexplained)
    lifted = pinned - {pin for _, pin, _ in found}
    assert not lifted, f"no longer found, so remove from KNOWN: {sorted(lifted)}"
    if known:
        pytest.xfail("; ".join(OBSTACLES[obstacle] for obstacle in sorted(known)))
