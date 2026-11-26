"""Press each page command and walk on a set of pages, and write a table of what Leaf's
panel says in passing and what a listener hears after each press.

    uv run leaf-dev words [--page NAME]... [--base [REF]] [--browser ENGINE]

The panel's field has one seat for words that pass: a notice, a walk's position, the
Go-to filter's word, and where the user stands before the agent's status
(panel/floating-panel.js, `fieldReading`). Each of those answers a press, so the survey reads
them press by press. On each page of `PAGES`, or each `--page`, it presses every page
command a key reaches at rest, twice, since a second press walks on or toggles back;
runs `JOURNEYS`, the sequences whose later presses mean something only after the first,
such as a search's next match or a comparison's changes; presses each key `g` leads to;
and Tabs through the page, pressing at the first stop in each kind of widget each key of
the walks the register offers there, or ArrowDown, ArrowRight and End where it offers
none. Undo runs last, since what it takes back stays taken back. Between commands it puts the page back at rest with
Escape, and reloads it where that leaves something behind.

After each press it reads the seat's words and the kind of reading they are
(`data-lf-says`), the press the field's end offers, the walk's position, what the live
region said since the last press, and where focus stands, and keeps a capture of the
window. It then runs the page's clock on past a notice's moment and reads the seat
again, since what stands after the moment is the other half of what a press leaves.
The clock is Playwright's, installed once the page has loaded, since the startup
reading reads the navigation's timings from the `performance` it replaces, so the wait
costs no time.

Each run writes, under `.tmp/words/run-*/`, `readings.jsonl`, one line per page and arm
with every row, the captures under `shots/`, and `index.html`, a Leaf page holding a
table per page, a row per press. With `--base` a cell where the arms differ says the
base's words struck through before this tree's, and the page's opening counts the rows
that differ. A row is matched across arms by its press and how many times that press
came before, so a command one arm lacks shows as a row on one side only.

    uv run leaf-dev preview --source .tmp/words/run-XXXX/index.html --slot words --user

The survey reads what the seat says, not whether it should say it. To judge that, read
the table beside the captures and ask of each row what it tells the reader that the
screen doesn't, by `browser/AGENTS.md`, "Leaf's interface", and the voice the
developing-leaf skill's `references/glossary.md` sets. News that arrives
without a press, such as an agent's reply or a new version, takes a page whose log
grows while it is open, which no case here holds yet.
"""

import json
import traceback
from collections import Counter
from collections.abc import Callable
from contextlib import contextmanager
from html import escape
from pathlib import Path

import click
from playwright.sync_api import Page

from leaf_dev import ROOT, gallery
from leaf_dev.arms import base_option, choose_arms, run_directory
from leaf_dev.browser import PANEL_SAYS, WINDOWS, engine_option, launch, settle
from leaf_dev.example_data import named_source
from leaf_dev.states import State
from leaf_dev.visits import said, visits

OUT = ROOT / ".tmp" / "words"

# Pages that between them hold every walk and notice the panel says: threads, On Me
# and two versions (review-a-plan), a tab strip of fourteen, question groups and charts
# (alert-review), a thread log of its own (ship-review), diffs and a table of contents
# (pr-walkthrough), a timeline (lost-update), a board (triage-board), a file editor
# (deploy-config), and a page of prose and diagrams alone (security-boundary).
PAGES = (
    "review-a-plan",
    "alert-review",
    "ship-review",
    "pr-walkthrough",
    "lost-update",
    "triage-board",
    "deploy-config",
    "security-boundary",
)

# Page commands the survey leaves to `JOURNEYS`, which press on inside what they open,
# and the scrolling ones, which say nothing in passing and only move the page.
OPENERS = {
    "comment.create",
    "page.search.open",
    "navigation.go-to.open",
    "command.reference.open",
    "target.picker.open",
}
SCROLLS = {"page.down", "page.up", "scroll.down", "scroll.up"}
# Undo takes back the page's latest gesture, which the log keeps, so it runs last: a
# thread it reopens would otherwise stand in every later row.
LAST = {"history.undo"}

# Each journey runs where its first route stands at rest: its presses, `type:WORDS`
# typing words.
JOURNEYS = (
    ("comment.create", ("c",)),
    ("page.search.open", ("/", "type:the", "Enter", "n", "n", "Shift+n")),
    ("command.reference.open", ("?", "ArrowDown", "ArrowDown", "End")),
    ("target.picker.open", ("s", "ArrowDown", "ArrowDown")),
    # Versions' Compare of the version the user last saw, by its key, its changes
    # walked, and the same keys taking the marks off.
    (
        "navigation.go-to.open",
        ("g", "Shift+v", "v", "h", "h", "Shift+h", "g", "Shift+v", "v"),
    ),
    ("queue.next", ("m", "ArrowDown", "ArrowDown")),
    ("thread.next", ("t", "Escape", "t")),
)
# The keys pressed at the first Tab stop in each kind of widget that declares no walk
# of its own there, and how many Tab stops the survey goes through.
WALK_KEYS = ("ArrowDown", "ArrowRight", "End")
TAB_STOPS = 150

# How long a press is given to paint before the seat is read, in real time, and how far
# the page's clock then runs past a notice's moment (transport/notifications.js, `NOTICE_MS`).
SETTLE_MS = 300
LATER_MS = 4500

INSTALL = """async () => {
  if (window.__lfWords) return;
  const boot = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
  const api = await import(new URL('runtime/check-api.js', new URL(boot, location.href)).href);
  const heard = [];
  const live = document.querySelector('.lf-live');
  new MutationObserver(() => {
    const words = live.textContent.trim();
    if (words && words !== heard.at(-1)) heard.push(words);
  }).observe(live, {childList: true, characterData: true, subtree: true});
  window.__lfWords = {api, heard};
}"""

# The element focus stands on, through open shadow roots, named by its tag, its widget
# (the nearest custom element holding it, across shadow roots), and a few of its words.
FOCUS = """() => {
  let node = document.activeElement;
  while (node?.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
  if (!node || node === document.body) return {kind: 'body', name: 'the page', panel: false};
  let widget = null;
  for (let at = node; at; at = at.parentElement ?? at.getRootNode()?.host ?? null)
    if (at.localName?.includes('-') && at.localName !== 'leaf-text') { widget = at.localName; break; }
  const host = node.getRootNode()?.host;
  const panel = Boolean(node.closest?.('.lf-floating-panel') ?? host?.closest?.('.lf-floating-panel'));
  const words = (node.getAttribute('aria-label') ?? node.innerText ?? node.textContent ?? '').replace(/\\s+/g, ' ').trim();
  const kind = widget ?? node.getAttribute('role') ?? node.localName;
  return {kind, panel, name: `${kind}${words ? ` “${words.slice(0, 40)}”` : ''}`};
}"""

READ = f"""() => {{
  const {{api, heard}} = window.__lfWords;
  const box = document.querySelector('.lf-fp-field leaf-text');
  const press = document.querySelector('.lf-fp-field .lf-compose-press');
  return {{
    seat: ({PANEL_SAYS})(),
    says: box?.getAttribute('data-lf-says') ?? null,
    press: press?.checkVisibility()
      ? [press.querySelector('.lf-compose-press-word')?.textContent,
         press.querySelector('kbd')?.textContent].filter(Boolean).join(' ') : null,
    walk: api.walkPosition()?.text ?? null,
    typed: box?.value ?? '',
    heard: heard.splice(0),
    focus: ({FOCUS})().name,
    view: document.querySelector('.lf-floating-panel')?.getAttribute('data-lf-open') ?? null,
    scroll: Math.round(scrollY),
  }};
}}"""


def routes_at_rest(page: Page) -> list[tuple[str, str]]:
    """Each page command's route id with a key that reaches it now."""
    return page.evaluate("""async () => {
      const {api} = window.__lfWords;
      const found = [];
      for (const [row, bindings] of api.availableCommandRoutes())
        for (const entry of api.commandEntries(row, [...bindings]))
          if (entry.binding) found.push([entry.id, entry.binding]);
      return found;
    }""")


def walks_here(page: Page, page_routes: set[str]) -> list[tuple[str, str]]:
    """Each route a key reaches from where focus stands that travels, as a walk does,
    and that the page offers nowhere else: the walks of the widget focus is in."""
    return page.evaluate(
        """async (pageRoutes) => {
          const {api} = window.__lfWords;
          const found = [];
          for (const [row, bindings] of api.availableCommandRoutes()) {
            const travels = typeof row.travels === 'function' ? row.travels() : row.travels;
            if (!travels) continue;
            for (const entry of api.commandEntries(row, [...bindings]))
              if (entry.binding && !pageRoutes.includes(entry.id))
                found.push([entry.id, entry.binding]);
          }
          return found;
        }""",
        sorted(page_routes),
    )


def signature(reading: dict) -> tuple:
    """What tells one resting page from another: what the seat says, the walk, focus
    and the scroll."""
    return tuple(
        reading[key]
        for key in ("seat", "says", "walk", "focus", "view", "scroll", "press")
    )


class Survey:
    """One arm's survey of one page in one tab: the rows it read, in order."""

    def __init__(self, page: Page, shots: Path):
        self.page = page
        self.shots = shots
        self.rows: list[dict] = []
        self.rest: tuple = ()

    def press(self, key: str) -> None:
        if key.startswith("type:"):
            self.page.keyboard.type(key.removeprefix("type:"))
        else:
            # A binding's `Mod` is the platform's own modifier (bindings.js), which
            # Playwright spells ControlOrMeta.
            self.page.keyboard.press(key.replace("Mod+", "ControlOrMeta+"))

    def observe(self, step: str) -> dict:
        """Read the seat after `step`, then again once a notice's moment has passed."""
        page = self.page
        page.wait_for_timeout(SETTLE_MS)
        now = page.evaluate(READ)
        shot = self.shots / f"{len(self.rows):03d}.jpg"
        shot.write_bytes(page.screenshot(type="jpeg", quality=60))
        page.clock.run_for(LATER_MS)
        page.wait_for_timeout(50)
        later = page.evaluate(READ)
        row = {
            "step": step,
            **now,
            "later": later["seat"],
            "later_says": later["says"],
            "heard_later": later["heard"],
            "shot": str(shot.relative_to(self.shots.parents[2])),
        }
        self.rows.append(row)
        return row

    def settle_rest(self) -> None:
        """Put the page back at rest: Escape twice, and a reload where that leaves the
        seat, the walk, focus or the scroll unlike the page as it loaded."""
        page = self.page
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        page.clock.run_for(LATER_MS)
        if signature(page.evaluate(READ)) == self.rest:
            return
        page.reload()
        settle(page)
        page.evaluate(INSTALL)
        page.evaluate(READ)

    def sequence(self, route: str, keys: tuple[str, ...], first: int = 0) -> None:
        """Press `keys` in turn, reading after each, and put the page back at rest. The
        press at `first` names `route` in its row."""
        for at, key in enumerate(keys):
            self.press(key)
            self.observe(f"{key} ({route})" if at == first else key)
        self.settle_rest()

    def run(self) -> list[dict]:
        page = self.page
        page.evaluate(INSTALL)
        self.rest = signature(self.observe("at rest"))
        routes = routes_at_rest(page)
        available = {route for route, _ in routes}
        for route, key in routes:
            if route not in OPENERS | SCROLLS | LAST:
                self.sequence(route, (key, key))
        for route, keys in JOURNEYS:
            if route in available:
                self.sequence(route, keys)
        if "navigation.go-to.open" in available:
            self.go_to()
        self.tab_through(available)
        for route, key in routes:
            if route in LAST:
                self.sequence(route, (key, key))
        return self.rows

    def go_to(self) -> None:
        """Each second key of a Go-to sequence, after `g`, and the hints' first Tabs."""
        self.press("g")
        seconds = [
            (route, key)
            for route, key in routes_at_rest(self.page)
            if route
            not in {"navigation.go-to.back", "command.reference.open"} | SCROLLS
            and not key.startswith("Tab")
            and not key.startswith("Shift+Tab")
        ]
        self.settle_rest()
        for route, key in seconds:
            self.sequence(route, ("g", key), first=1)
        if any(route == "navigation.target" for route, _ in seconds):
            self.sequence("navigation.target", ("g", "a", "Tab", "Tab"), first=1)

    def tab_through(self, page_routes: set[str]) -> None:
        """Tab through the page, and at the first stop in each kind of widget press each
        key of the walks it declares there, or `WALK_KEYS` where it declares none, each
        from that stop."""
        page = self.page
        seen = set()
        for _ in range(TAB_STOPS):
            page.keyboard.press("Tab")
            page.wait_for_timeout(60)
            focus = page.evaluate(FOCUS)
            if focus["panel"] or focus["kind"] in seen:
                continue
            seen.add(focus["kind"])
            walks = walks_here(page, page_routes) or [(None, key) for key in WALK_KEYS]
            for route, key in walks:
                page.keyboard.press(key)
                self.observe(
                    f"Tab to {focus['name']}, {key}" + (f" ({route})" if route else "")
                )
                page.keyboard.press("Shift+Tab")
                page.keyboard.press("Tab")


def survey_page(browser, arms, name: str, out: Path, scratch: Path) -> dict[str, dict]:
    """Survey page `name` on each arm, returning each arm's line for readings.jsonl."""
    source = named_source(name)
    lines: dict[str, dict] = {}
    current: dict[str, str] = {}

    @contextmanager
    def armed(page: Page, arm: str):
        current["arm"] = arm
        yield

    def journey(page: Page) -> list[dict]:
        # Installed once the page has loaded, since the startup reading reads the
        # navigation's timings from `performance`, which the clock replaces.
        page.clock.install()
        shots = out / "shots" / name / current["arm"]
        shots.mkdir(parents=True, exist_ok=True)
        return Survey(page, shots).run()

    window = WINDOWS["macbook"]
    with visits(
        browser,
        arms,
        State(name, str(source), window=window),
        source,
        scratch / name,
        window=window,
        scheme="light",
        read=lambda arm, visit: None,
        run=journey,
        record=armed,
    ) as each:
        for arm, visit in each:
            line: dict = {"page": name, "arm": arm, "commit": visit.commit}
            if visit.error:
                (out / f"{name}-{arm}-error.txt").write_text(
                    "".join(traceback.format_exception(visit.error))
                )
                line["failed"] = f"{visit.doing}: {said(visit.error)}"
            line["rows"] = visit.reading.get("result") or []
            lines[arm] = line
    return lines


def keyed(rows: list[dict]) -> dict[tuple[str, int], dict]:
    """Each row under its step and how many rows with that step came before it."""
    count: Counter = Counter()
    found = {}
    for row in rows:
        found[(row["step"], count[row["step"]])] = row
        count[row["step"]] += 1
    return found


# A row's cells: its seat, whose words end in the press the field's end offers, with
# the kind of reading it is; the seat once a notice's moment has passed; and what the
# live region said.
CELLS: tuple[tuple[str, Callable[[dict], str]], ...] = (
    (
        "Seat",
        lambda row: (
            (f"[typed “{row['typed']}”] " if row["typed"] else "")
            + row["seat"]
            + (f" ({row['says']})" if row["says"] else "")
        ),
    ),
    ("After 4 s", lambda row: row["later"] if row["later"] != row["seat"] else "="),
    ("Heard", lambda row: " | ".join(row["heard"] + row["heard_later"])),
)


def cell(before: dict | None, after: dict | None, read: Callable[[dict], str]) -> str:
    """One cell: this tree's words, after the base's struck through where they differ."""
    now = escape(read(after)) if after else "—"
    if before is None:
        return f"<td>{now}</td>"
    was = escape(read(before))
    if after is None:
        return f"<td><del>{was}</del></td>"
    if was == now:
        return f"<td>{now}</td>"
    return f'<td data-differs=""><del>{was}</del> {now}</td>'


STYLE = """<style>
.words td, .words th { vertical-align: top; font-size: 0.85em; }
.words td[data-differs] { background: color-mix(in oklch, var(--lf-accent, orange) 12%, transparent); }
.words del { opacity: 0.6; }
</style>"""


def table(name: str, lines: dict[str, dict]) -> tuple[str, int, int]:
    """Page `name`'s section, with its count of rows and of rows the arms differ in."""
    head = keyed(lines["head"]["rows"])
    base = keyed(lines["base"]["rows"]) if "base" in lines else None
    # Each row under its key, head's where both arms have one, the base's where only it does.
    rows = dict(head)
    if base is not None:
        rows |= {key: row for key, row in base.items() if key not in head}
    differ = 0
    body = []
    for key, row in rows.items():
        after = head.get(key)
        before = base.get(key) if base is not None else None
        cells = [cell(before, after, read) for _, read in CELLS]
        differ += any("data-differs" in each or "<del>" in each for each in cells)
        shot = row["shot"]
        body.append(
            f'<tr><th scope="row"><a href="{escape(shot)}">{escape(key[0])}</a></th>'
            + "".join(cells)
            + "</tr>"
        )
    failed = [
        f"<p>{escape(arm)} failed at {escape(line['failed'])}</p>"
        for arm, line in lines.items()
        if line.get("failed")
    ]
    section = (
        f'<section id="{escape(name)}"><h2>{escape(name)}</h2>{"".join(failed)}'
        '<table class="words"><thead><tr><th scope="col">Press</th>'
        + "".join(f'<th scope="col">{title}</th>' for title, _ in CELLS)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></section>"
    )
    return section, len(rows), differ


def report(pages: dict[str, dict[str, dict]], out: Path) -> Path:
    sections, counts = [], []
    for name, lines in pages.items():
        section, rows, differ = table(name, lines)
        sections.append(section)
        counts.append((name, rows, differ))
    arms = next(iter(pages.values()))
    commits = ", ".join(f"{arm} at {line['commit'][:9]}" for arm, line in arms.items())
    differing = ""
    if "base" in arms:
        differing = (
            "<p>Rows the arms differ in: "
            + ", ".join(
                f'<a href="#{escape(name)}">{escape(name)}</a> {differ} of {rows}'
                for name, rows, differ in counts
            )
            + ".</p>"
        )
    page = out / "index.html"
    page.write_text(
        gallery.page(
            "Passing words",
            "What Leaf's panel says in passing, and what a listener hears, after each "
            "press on a set of pages.",
            f"""<h1>Passing words</h1>
<p>What the panel's seat says after each press ({commits}), ending in the press its
field's end offers, with the kind of reading in parentheses; what it says once a notice's
moment has passed, = where nothing changed; and what the live region said. A press
links to its capture. Regenerate with <code>uv run leaf-dev words</code>.</p>
{differing}
{"".join(sections)}""",
            head=STYLE,
        ),
        encoding="utf-8",
    )
    return page


@click.command("words")
@click.option(
    "--page",
    "names",
    multiple=True,
    help="Survey only this page (an example or fixture name); repeat for more.",
)
@engine_option
@base_option()
def words(names, engine, base) -> None:
    """Press each page command and walk on a set of pages, and write a table of what the
    panel says in passing after each press (this module's header says what it reads)."""
    out = run_directory(OUT)
    scratch = out / "scratch"
    scratch.mkdir()
    pages: dict[str, dict[str, dict]] = {}
    with launch(engine) as browser:
        arms = choose_arms(base, scratch)
        with (out / "readings.jsonl").open("w") as readings:
            for name in names or PAGES:
                lines = survey_page(browser, arms, name, out, scratch)
                pages[name] = lines
                for arm, line in lines.items():
                    readings.write(json.dumps(line) + "\n")
                    readings.flush()
                    click.echo(
                        f"{name} {arm}: "
                        + (line.get("failed") or f"{len(line['rows'])} rows")
                    )
    click.echo(report(pages, out))
    if any(line.get("failed") for lines in pages.values() for line in lines.values()):
        raise click.ClickException("a page failed; see its line in readings.jsonl")
