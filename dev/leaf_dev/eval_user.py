"""The harness as the user of an agent's page, in a browser.

An authored-task eval plays its user on whatever page the agent built, so nothing
here knows the page's structure. Two moves cover what the user does there:

- A comment on a passage (`comment_on_passage`), made as a reader makes one on a
  Leaf page: select the passage's rendered words, press the selection's comment
  action, type and send. The words are found in the text the browser draws, so a
  passage a script renders anchors as well as authored markup. Where none of the
  candidate words is drawn, a click on the `reveal` text opens what holds them, as
  a reader opens a ticket; where that fails, the comment goes on the page whole.
- A decision (`decide`), which no fixed script can make on a page it has never
  seen. A user agent (`MODELS["user"]`) makes it through the page's own controls
  with `playwright-cli`, attached to a tab this module opened, and reports what the
  page offered to copy. The tab records every clipboard write and copy, so what a
  copy button put on the clipboard is read exactly rather than from the agent.

`reveal` is shared with the screenshots, which open the commented item before the
judge sees the final version.
The simulated user's prompt lives in `evals/workflows/eval_user.yaml`.
"""

import json
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import click
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from leaf_dev.arms import (
    MODELS,
    claude_child,
    run_agent,
    scratch,
    trace_result,
    trace_summary,
)
from leaf_dev.browser import BESIDE, DESKTOP, chrome, load, settle, tab
from leaf_dev.eval_cases import definition

# Elements a reader clicks to open what a list or a disclosure holds.
OPENERS = (
    "a, button, summary, label, li, tr, [role=button], [role=tab], [role=option], "
    "[role=link], [role=row], [role=treeitem], [tabindex]"
)

# The words the browser draws, each mapped back to its text node, with runs of
# space collapsed as rendering collapses them; hidden and script text is skipped.
DRAWN = """() => {
  const chars = [], map = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let space = true;
  for (let node; (node = walker.nextNode()); ) {
    const parent = node.parentElement;
    if (!parent || parent.closest("script, style, template, noscript")) continue;
    if (!parent.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
      continue;
    for (let i = 0; i < node.data.length; i++) {
      const blank = /\\s/.test(node.data[i]);
      if (blank && space) continue;
      chars.push(blank ? " " : node.data[i]);
      map.push([node, i]);
      space = blank;
    }
  }
  return { text: chars.join(""), map };
}"""

SELECT = (
    """(quotes) => {
  const { text, map } = ("""
    + DRAWN
    + """)();
  for (const quote of quotes) {
    const at = text.indexOf(quote);
    if (at < 0) continue;
    const [start, from] = map[at], [end, to] = map[at + quote.length - 1];
    const range = document.createRange();
    range.setStart(start, from);
    range.setEnd(end, to + 1);
    if (!range.getClientRects().length) continue;
    start.parentElement.scrollIntoView({ block: "center", behavior: "instant" });
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    return quote;
  }
  return null;
}"""
)

SHOWS = """(pattern) => new RegExp(pattern).test(document.body.innerText)"""

# Whether an opener already says its item is open or selected, as ARIA and a
# disclosure's own state report it, so clicking it again would close it.
OPEN = """(element) =>
  element.getAttribute("aria-expanded") === "true"
  || element.getAttribute("aria-selected") === "true"
  || ![null, "false"].includes(element.getAttribute("aria-current"))
  || (element.matches("summary") && element.parentElement?.open === true)"""

# Records every write a page makes to the clipboard, and every copy of a selection.
COPY_SPY = """(() => {
  const copies = (globalThis.__leafEvalCopies = []);
  const clip = navigator.clipboard;
  if (clip?.writeText) {
    const writeText = clip.writeText.bind(clip);
    clip.writeText = (text) => (copies.push(String(text)), writeText(text));
  }
  if (clip?.write) {
    const write = clip.write.bind(clip);
    clip.write = async (items) => {
      for (const item of items)
        if (item.types.includes("text/plain"))
          copies.push(await (await item.getType("text/plain")).text());
      return write(items);
    };
  }
  const setData = DataTransfer.prototype.setData;
  DataTransfer.prototype.setData = function (type, data) {
    if (/^text(\\/plain)?$/i.test(type)) copies.push(String(data));
    return setData.call(this, type, data);
  };
  document.addEventListener("copy", () => {
    const field = document.activeElement;
    const text = field && "selectionStart" in field && field.value != null
      ? field.value.slice(field.selectionStart, field.selectionEnd)
      : String(getSelection() ?? "");
    if (text) copies.push(text);
  }, true);
})()"""


def shows(page: Page, pattern: str) -> bool:
    """Whether the page draws words matching `pattern`."""
    return page.evaluate(SHOWS, pattern)


def reveal(page: Page, target: str, pattern: str, settled=settle) -> str:
    """Open the item `target` names, as a reader opens a ticket from a queue: click
    the first drawn control naming it, the innermost where one holds another, as a
    reader presses the button rather than its row, unless the control says its
    item is already open, and the next ones until words matching `pattern` are
    drawn. The words may also be drawn elsewhere, such as in a summary, so the
    item is opened whether or not they are; a click that hides them is undone,
    since it closed an item that was open. Return `opened` once they are drawn,
    or `hidden`."""
    # The innermost drawn controls: those holding no other drawn control naming
    # the item. A click can draw new ones, so each round reads them again and
    # takes the first not yet pressed.
    drawn = page.locator(OPENERS).filter(has_text=target, visible=True)
    innermost = drawn.filter(has_not=drawn)
    pressed = []
    for _ in range(6):
        try:
            unpressed = [
                found
                for found in innermost.element_handles()
                if not found.evaluate("(el, pressed) => pressed.includes(el)", pressed)
            ]
        except PlaywrightError:
            # A press navigated: the controls pressed belong to the last document.
            pressed = []
            unpressed = innermost.element_handles()
        opener = next(iter(unpressed), None)
        if opener is None:
            break
        pressed.append(opener)
        if not opener.evaluate(OPEN):
            shown = shows(page, pattern)
            opener.click()
            settled(page)
            if shown and not shows(page, pattern):
                opener.click()
                settled(page)
                return "opened"
        if shows(page, pattern):
            return "opened"
    return "opened" if shows(page, pattern) else "hidden"


def comment_on_passage(
    url: str, quotes: tuple[str, ...], text: str, fallback: str, target: str = ""
) -> dict:
    """Comment as the reader of the Leaf page at `url`: on the first drawn
    occurrence of the first of `quotes` the page draws, which the selection's own
    context anchors, opening `target` first where none is drawn, or otherwise
    on the page whole with `fallback`. Return the route, the quote, and the
    `attempt` key that finds the admitted comment in the log."""
    with chrome() as browser, tab(browser, viewport=DESKTOP) as view:
        load(view, url)
        quote = view.evaluate(SELECT, list(quotes))
        opened = None
        if quote is None and target:
            opened = reveal(view, target, "|".join(map(re.escape, quotes)))
            quote = view.evaluate(SELECT, list(quotes))
        with view.expect_response(
            lambda response: (
                response.url.split("?")[0].endswith("/api/event")
                and response.request.method == "POST"
            )
        ) as answer:
            if quote is not None:
                view.dispatch_event("body", "mouseup")
                view.get_by_role("button", name="Comment on selection").click()
                box = view.locator(".lf-composer leaf-text")
            else:
                view.locator(".lf-banner-actions > .lf-page-comment").click()
                box = view.locator(".lf-page-comment-card leaf-text")
            box.focus()
            view.keyboard.insert_text(text if quote is not None else fallback)
            box.press("ControlOrMeta+Enter")
        posted = answer.value
        if not posted.ok:
            raise click.ClickException(f"{url} refused the comment: {posted.status}")
        return {
            "route": "selection" if quote is not None else "page",
            "quote": quote,
            "revealed": opened,
            "attempt": posted.request.post_data_json["attempt"],
        }


# A user who has not decided in this long is stuck, and one browser command that
# takes this long has hung; either ends the round rather than the session.
DECIDING_LIMIT = 30 * 60
COMMAND_LIMIT = 120

USER = definition("eval_user")["prompt"]


def cli() -> list[str]:
    """The browser CLI supplied by Leaf's pinned Playwright development dependency."""
    from leaf_dev import ROOT

    node = shutil.which("node")
    script = ROOT / "node_modules/playwright/cli.js"
    if node is None or not script.is_file():
        raise click.ClickException(
            "Browser agents need Node and eval dependencies; run pnpm install --frozen-lockfile"
        )
    return [str(Path(node).resolve()), str(script), "cli"]


def decide(url: str, task: str, evidence: Path) -> dict:
    """Have the user agent make the decision `task` on the page at `url`, in a
    900px tab, and return what it reported (`made`, `copied`, `notes`), what the
    page put on the clipboard (`copies`), and what the agent spent (`trace`)."""
    evidence.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with (
        chrome(args=[f"--remote-debugging-port={port}"]) as browser,
        tab(browser, viewport=BESIDE, motion="no-preference") as view,
        scratch() as cwd,
        tempfile.TemporaryDirectory(prefix="leaf-pw-", dir="/tmp") as sockets,
    ):
        view.context.grant_permissions(["clipboard-read", "clipboard-write"])
        view.context.add_init_script(COPY_SPY)
        view.goto(url, wait_until="load")
        session = f"leaf-user-{cwd.parent.name}"
        # The daemon keeps its socket in `sockets`, whose path is short enough for
        # one, under the user agent's own home, so it must run in the agent's
        # environment.
        env = claude_child(cwd, "", env={"PWTEST_SOCKETS_DIR": sockets})["env"]

        def playwright(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                [*cli(), f"-s={session}", *args],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=COMMAND_LIMIT,
            )

        attached = playwright("attach", f"--cdp=http://127.0.0.1:{port}")
        if attached.returncode:
            raise click.ClickException(
                f"playwright-cli could not attach: {attached.stdout}{attached.stderr}"
            )
        prompt = USER.format(cli=shlex.join(cli()), session=session, task=task)
        (evidence / "prompt.txt").write_text(prompt)
        try:
            trace = run_agent(
                cwd,
                prompt,
                "--tools",
                "Bash",
                out=evidence / "stream.jsonl",
                err=evidence / "err.txt",
                env={"PWTEST_SOCKETS_DIR": sockets},
                model=MODELS["user"],
                sandbox=False,
                limit=DECIDING_LIMIT,
            )
            copies = view.evaluate("() => globalThis.__leafEvalCopies ?? []")
        finally:
            playwright("detach")
    match = re.search(r"\{.*\}", trace_result(trace).get("result", ""), re.DOTALL)
    try:
        reported = json.loads(match[0]) if match else {}
    except json.JSONDecodeError:
        reported = {}
    return {
        "made": reported.get("made") is True,
        "copied": reported.get("copied") or None,
        "notes": reported.get("notes") or "",
        "copies": copies,
        "trace": trace_summary(trace),
    }
