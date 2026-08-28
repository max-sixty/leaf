"""Browser-backed render checks and standalone page export."""

import base64
import contextlib
import json
import re
import secrets
import sys
import threading
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from leaf.data import read_data
from leaf.event_log import flocked, now_iso, read_events
from leaf.files import published_versions, revision_label, version_name, version_num
from leaf.hosting import LeafHTTPServer
from leaf.http import handler_for
from leaf.passages import EMPTY, spoken
from leaf.projection import decisions, page_projection, retirement_holders
from leaf.registry import retirement_slots
from leaf.render_checks import (
    RENDER_VIEWPORT,
    SERVED_TIMEOUT_MS,
    evaluate_probe,
    install_window_errors,
    wait_for_probe,
)
from leaf.schema import _DIR_FILES, MEDIA_DIR, MEDIA_TYPES
from leaf.service import transition_lock
from leaf.structure import parse_structure
from leaf.validation import thread_universe

# ---------- check --render: the browser half of the gate ----------


def served(page, url: str, path: str, timeout_ms: int | None = None):
    """A document this page's own server holds, read from out here.

    The one reader in the render gate that can be given a deadline. `page.evaluate`
    sends the driver no timeout at all — measured on playwright 1.62, an evaluate
    awaiting a fetch that never answers is still running at 200s — so a reading
    taken inside the page is a hang with nothing printed and no way to bound it
    from Python. `page.request` takes one, and shares the browser context's cookie
    jar, so it reads as the same authorized client the page is: the handover key
    rides in the URL and becomes a cookie on the first navigation."""
    timeout_ms = SERVED_TIMEOUT_MS if timeout_ms is None else timeout_ms
    return page.request.get(urljoin(url, path), timeout=timeout_ms)


def previous_stamp(revision: int, versions: list[dict]) -> dict | None:
    """The newest stamped revision before ``revision``, if one exists."""
    earlier = [version for version in versions if version["revision"] < revision]
    return max(earlier, key=lambda version: version["revision"]) if earlier else None


def rendered_revision(url: str, state: dict) -> int:
    """Resolve the immutable revision shown at ``url`` from the public state."""
    name = Path(urlsplit(url).path).name
    if not name:
        return state["active"]["revision"]
    version = version_num(name)
    return next(
        stamped["revision"]
        for stamped in state["versions"]
        if stamped["version"] == version
    )


RESIZE_OBSERVER_ERROR = "window error: ResizeObserver loop"


def resize_observer_error(text: str) -> bool:
    return text.startswith(RESIZE_OBSERVER_ERROR)


def recurring_resize_observer_error(unit: str) -> str:
    return f"{RESIZE_OBSERVER_ERROR} notice recurred on the confirming {unit}"


def _render_version_attempt(
    browser, url: str, served_timeout_ms: int | None = None
) -> tuple[list, list, bool]:
    """Everything wrong with a served version that only a browser can see: a
    console or page error, a request that 404s, a fail-soft error box, an upgrade
    module that never defines its declared element, an x-conversation whose module
    placed no matching page host, a widget upgraded into a box of no usable size,
    an element showing words with no box for a mark to hang on, so a comment anchored
    there would outline nothing and the ask walk would travel to the top of the page,
    the page scrolling sideways, content set past the column and out into the margin,
    a drawing scrolling beside an empty margin the page had room in,
    a table that scrolls sideways with a cell in it wrapped,
    words the user can read and can't select, words drawn on top of other words, code
    coloured in an ink the reader cannot tell from the code around it — each
    in both color schemes, because the dark theme is real CSS nobody otherwise
    renders — plus, in one scheme, a word the registry promised that never reached
    the page (a declaration is scheme-blind), an attribute a module left standing on a
    widget that its entry never declared (a file's reading sees one writer, and this is
    the other), a version that authors widget state the log replays over, a widget whose
    applyAction is relative, so a read's replay of the sender's own gesture moves the
    page again (none of the three is CSS), a settled holder whose mark or still-showing
    slot words disagree with the log's decision (read once, on the premise the
    trapped-margin reading shares: the palettes carry no geometry between them), a box
    drawing one inset and showing another, and, on paper, words the page drops that
    it says on screen, or draws over each other (print is scheme-blind). Returns human-readable failures; [] is a pass.

    One implementation with two callers — `version check --render` on the page an agent
    just wrote, and the render suite on the shipped examples
    (the tests/test_render_*.py modules) — so the gate and the suite hold one set of
    invariants. Returns ordinary failures, ResizeObserver notices, and whether every
    reading completed. `browser` is a live Playwright browser; nothing here imports
    playwright at module level, so the module stays importable without it."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    served_timeout_ms = (
        SERVED_TIMEOUT_MS if served_timeout_ms is None else served_timeout_ms
    )
    opened_pages = []

    def in_scheme(scheme):
        page = browser.new_page(viewport=RENDER_VIEWPORT, color_scheme=scheme)
        opened_pages.append(page)
        page._leaf_probe_timeout_ms = served_timeout_ms
        errors = []
        resize_notices = []

        def served_here(path):
            return served(page, url, path, timeout_ms=served_timeout_ms)

        def console_message(message):
            if message.type != "error":
                return
            (resize_notices if resize_observer_error(message.text) else errors).append(
                message.text
            )

        def probe_failure(error):
            page.close()
            return (
                [
                    (
                        f"[{scheme}] the browser probe module failed: "
                        f"{str(error).strip().splitlines()[0]}"
                    )
                ],
                [],
                False,
            )

        page.on("console", console_message)
        page.on("pageerror", lambda e: errors.append(str(e)))
        # The console's own word for a bad response is "Failed to load resource",
        # which names nothing; carry the status and URL so a failure says what
        # went missing.
        page.on(
            "response",
            lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
        )
        install_window_errors(page)
        try:
            # `load`, not `networkidle`: the page holds a request open to hear
            # about news, so the network is never idle and never will be. The
            # wait that matters is the next line, which asks the runtime itself.
            page.goto(url, wait_until="load")
            wait_for_probe(page, "runtimeStarted")
        except PlaywrightTimeout:
            page.close()
            explanations = [*errors, *resize_notices]
            return (
                [
                    f"[{scheme}] the runtime never injected its banner — "
                    + ("; ".join(explanations) or "and no console error explains why")
                ],
                [],
                False,
            )
        except PlaywrightError as error:
            return probe_failure(error)
        # Every reading below is of a settled page. The widget layer writes half the
        # document, so a box measured while it is still drawing belongs to no version of
        # the page — which is the stamp `version export` waits on for the same reason.
        try:
            wait_for_probe(page, "upgraded")
        except PlaywrightTimeout:
            page.close()
            explanations = [*errors, *resize_notices]
            return (
                [
                    f"[{scheme}] the widget layer never finished upgrading — "
                    + ("; ".join(explanations) or "and no console error explains why")
                ],
                [],
                False,
            )
        except PlaywrightError as error:
            return probe_failure(error)
        # The served documents every reading below is asked against, read once each
        # (`served` says why they are read from out here rather than fetched inside
        # the page). The registry alone used to be fetched seven times a scheme, to
        # answer seven questions about one document. What the readings get now is
        # data, so most of them are plain synchronous DOM walks with nothing left in
        # them to await, let alone hang in.
        try:
            registry = served_here("/registry.json").json()
            # The readings in the page mean widgets, so they are handed only those:
            # $keys spells its members in the x- keys' own names, and a sweep over
            # every entry took it for a widget called $keys.
            widgets = {tag: e for tag, e in registry.items() if tag.startswith("lf-")}
            state = served_here("/api/state").json()
            markup = served_here(urlsplit(url).path).text()
            # Every replay and conflict check is bounded by immutable revision.
            # A stamped URL resolves through the stamp map; an exact source preview
            # uses the synthetic active revision exposed only by its preview server.
            here = rendered_revision(url, state)
            before = previous_stamp(here, state["versions"])
            earlier = served_here(before["url"]).text() if before else None
        except PlaywrightTimeout as e:
            page.close()
            # The first line only: the rest is playwright's call log, which says
            # nothing about the page that a reader of this failure needs.
            return (
                [
                    *[f"[{scheme}] console: {error}" for error in errors],
                    *[f"[{scheme}] console: {notice}" for notice in resize_notices],
                    (
                        f"[{scheme}] the server stopped answering: "
                        f"{str(e).splitlines()[0]}"
                    ),
                ],
                [],
                False,
            )
        # The widgets the log has moved, in the log's order. Both replayed kinds,
        # once: the caught-up stamp counts reports beside actions, so the wait below
        # counts what this holds, and the verbatim reading excuses exactly these.
        touched = [
            e["widget"] for e in state["events"] if e["kind"] in ("action", "report")
        ]
        # Every reading below is of a page at rest, and the upgrade stamp above is
        # one third of that. The stamp is written without awaiting the first read, so
        # a gate reading there reads the authored board, the unanswered question and
        # the body the reader has since rewritten — a page nobody is shown. The
        # caught-up stamp is the log's answer to that, and the frame it lands in is
        # the first frame of whatever the replay set moving, a replay past the
        # presentation boundary moving rather than teleporting. Both waits are taken
        # in both schemes, because every reading below has boxes or words in it. The
        # windows open under load alone, which is how one page passed at a desk and
        # reported words drawn over words under a full suite ("The page finishes
        # twice", in the layer's own CLAUDE.md).
        unsettled = []
        replayed = True
        try:
            wait_for_probe(page, "dataApplied", state["data"]["revision"])
        except PlaywrightTimeout:
            replayed = False
            unsettled = [
                (
                    "the runtime never presented external data revision "
                    f"{state['data']['revision']}"
                )
            ]
        if replayed and touched:
            applied = len(touched)
            try:
                wait_for_probe(page, "logApplied", applied)
            except PlaywrightTimeout:
                replayed = False
                stalled = (
                    "the runtime never finished replaying the log "
                    f"({applied} action(s))"
                )
                unsettled = [stalled]
        if replayed:
            try:
                wait_for_probe(page, "pageSettled")
            except PlaywrightTimeout:
                unsettled = [
                    "the page never stopped moving: "
                    + ", ".join(evaluate_probe(page, "moving"))
                ]
        failsoft = evaluate_probe(page, "failSoftErrors")
        missing_upgrades = evaluate_probe(page, "missingUpgrades", widgets)
        missing_visual_providers = evaluate_probe(
            page, "missingVisualProviders", widgets
        )
        tiny = evaluate_probe(page, "tinyBoxes", widgets)
        unmarkable = evaluate_probe(page, "unmarkableItems")
        overflow = evaluate_probe(page, "bodyOverflow")
        misplaced = evaluate_probe(page, "misplacedBoxes")
        withheld = evaluate_probe(page, "withheldRoom")
        squeezed = evaluate_probe(page, "squeezedTables")
        clipped = evaluate_probe(page, "clippedControls")
        unreachable = evaluate_probe(page, "unreachableWords")
        covered = evaluate_probe(page, "coveredWords")
        unread = evaluate_probe(page, "unreadSyntax")
        # Shadow roots the registry doesn't declare: the passage walk, the
        # capture and the id lookups cross exactly the declared ones, so an
        # undeclared root's words silently anchor quotes astray. UA shadow roots
        # are closed and invisible here; anything open was attached by a module.
        undeclared_shadow = evaluate_probe(page, "undeclaredShadowRoots", registry)
        # Replay is scheme-blind, so one scheme's reading covers both.
        conflicts = []
        dishonest_verbatim = []
        silent = []
        missing_conversations = []
        undeclared_attrs = []
        retired = []
        if scheme == "light":
            # x-conversation promises one page view per matching instance. A widget in
            # thread chrome already has the thread's reply surface and conversationBox
            # deliberately returns none there. Everywhere else, ask the merged registry
            # for the instances and the module's own marker for the host it placed.
            missing_conversations = evaluate_probe(
                page, "missingConversations", widgets
            )
            # x-verbatim honesty: the entry claims the body reaches the reader
            # as its own words, and the two readings built on that claim — the
            # browser's says() and the file's spoken() — are compared here on
            # every instance the log hasn't moved (a decided or rewritten
            # widget legitimately shows other words). A module that renders
            # something in the body's stead while the entry still says
            # verbatim strands quotes on words the screen no longer shows.
            # Both documents, because a widget an agent sent has words of its
            # own — in the frozen fragment that carries it, which is the file
            # side for it exactly as the version is for a page widget. Asked of
            # the version alone the two sides both read empty and the comparison
            # passed on the agreement of two blanks; asked of neither, an
            # x-verbatim widget in a message could render something other than
            # its own words with nothing saying so, which is the one thing the
            # declaration promises and the reason a quote may rest on it.
            shown = evaluate_probe(
                page, "shownVerbatim", {"widgets": widgets, "touched": touched}
            )
            if shown:
                _byid, thread_spk, _threads = thread_universe(state["events"], registry)
                spk = {**thread_spk, **spoken(markup, registry)}
                dishonest_verbatim = [
                    f"<{s['tag']} id={s['id']!r}> declares x-verbatim but shows "
                    f"{s['says'][:80]!r} where the file reads "
                    f"{spk.get(s['id'], EMPTY).words[:80]!r}"
                    for s in shown
                    if s["says"] != spk.get(s["id"], EMPTY).words
                ]
            if touched and replayed and earlier is not None:
                conflicts = evaluate_probe(
                    page,
                    "replayOverrides",
                    {"curHtml": markup, "prevHtml": earlier},
                )
            # Behind the caught-up wait above: a report moves a painted attribute and
            # the pass that speaks it runs before the stamp, so a reading taken any
            # earlier asks after a word the page has not been asked to say yet. A page
            # that never caught up is already reported there and read no further.
            if replayed:
                silent = evaluate_probe(page, "silentWords", widgets)
                # Behind the same wait, because reconciliation is one of the two
                # writers: an applyAction states one declared fact whole, and a
                # record form is exactly the attribute it may state that fact in.
                undeclared_attrs = evaluate_probe(page, "undeclaredAttrs", widgets)
                # Behind it too: the settlement mark is replay's own write, so a
                # reading taken earlier asks after paint the page has not been
                # asked to make yet. The expected outcomes are the file's, scoped
                # to each holder's own relation: `decisions` folds any verb that
                # retires somewhere in the vocabulary, so a verb of that name on
                # a family it settles nothing of decides nothing here — the
                # browser's write reads the per-holder relation, and a comparison
                # against anything wider would fail a page both sides are right
                # about.
                if slots := retirement_slots(registry):
                    projection, vparser, _ = page_projection(
                        markup, state["events"], registry, here
                    )
                    outcomes = decisions(projection.actions, registry)
                    holders = []
                    for h in retirement_holders(vparser, registry):
                        declared = slots[h["tag"]]
                        outcome = outcomes.get(h["id"])
                        if outcome not in declared:
                            outcome = None
                        holders.append(
                            {
                                "tag": h["tag"],
                                "id": h["id"],
                                "outcome": outcome,
                                "slots": sorted(declared.get(outcome, ())),
                            }
                        )
                    if holders:
                        retired = evaluate_probe(page, "retiredSlots", holders)
        # One scheme, the palettes carrying no geometry between them, and before the
        # medium moves: a box's inset is what it declared in either.
        #
        # The document's boxes, not the layer's over them. This is the only reading
        # here that reaches the runtime's own chrome, and it reaches it by accident:
        # inside `display: none` an element's own display is still `block` and its
        # padding and margins still resolve, so a shut panel answers with numbers that
        # look like the page's. They are not the panel's own. A size container query
        # does not match in there, so a rule switching a slot between two forms is
        # stuck on one of them, and a percentage margin comes back unresolved for
        # `px` to read as its bare number. Every box reading beside this one sees zero
        # and stops, which is the honest answer.
        #
        # And the finding would be one the author cannot act on. Everything in here is
        # somebody else's: the layer's own parts, told to them in the words of a class
        # no page of theirs has, and a widget an agent sent in a reply, frozen in an
        # append-only log and admitted at a door of its own. Either way the version
        # would stay refused with no edit that clears it, which is why the coarse
        # question — which document is this in — is the right one to ask here. That is the failure examples/CLAUDE.md names as the
        # reason a gate reading was moved out once already. The layer's half is leaf's
        # own to hold, and the suite holds it with the panel open, where the styles are
        # the panel's and the margin is one somebody can see.
        trapped = (
            [t for t in evaluate_probe(page, "trappedMargins") if not t["chrome"]]
            if scheme == "light"
            else []
        )
        # Last, and in one scheme: paper has no color scheme, and the medium has to be
        # put back before anything else reads a box.
        on_paper = []
        if scheme == "light":
            screen = evaluate_probe(page, "paperWords")
            page.emulate_media(media="print")
            paper = evaluate_probe(page, "paperWords")
            # Paper is laid out by rules no other medium runs, and it is the medium
            # nobody looks at, so the overlap reading is taken here too while it holds.
            on_paper = [f"[print] {c}" for c in evaluate_probe(page, "coveredWords")]
            page.emulate_media(media="screen")
            # Paired on the words as well as the position: the page is live, and a state
            # landing between the two readings would otherwise shift one against the
            # other and report whatever happened to line up. A pair that disagrees says
            # nothing, which is the right way round — the next run reads it again.
            on_paper += [
                f"[print] {s['at']} drops {json.dumps(s['text'])}, which it says on screen"
                for s, p in zip(screen, paper)
                if s["text"] == p["text"] and s["shown"] and not p["shown"]
            ]
        # Last of all, because it is the only reading here that writes: it applies each
        # standing action again, which is a no-op exactly when the contract holds and a
        # page nobody should read any further when it doesn't. Behind the same caught-up
        # wait as the conflicts above, for the same reason — a page mid-replay has not
        # finished producing the state the second application is measured against.
        relative = []
        if scheme == "light" and replayed:
            relative = evaluate_probe(page, "relativeReplays")
        # The print reset and replay above can resize what an observer watches. Chrome
        # delivers that notice in the next rendering turn, so closing on the write
        # would call an attempt complete before its last error channel had spoken.
        evaluate_probe(page, "nextFrame")
        page.close()
        found = [f"[{scheme}] console: {e}" for e in errors]
        found += [f"[{scheme}] a widget failed soft: {t}" for t in failsoft]
        if missing_upgrades:
            found.append(
                f"[{scheme}] upgraded widgets did not define their elements: "
                + ", ".join(f"<{tag}>" for tag in missing_upgrades)
            )
        found += [
            f"[{scheme}] <{p['tag']} id={p['id']!r}> declares addressable visual "
            f"parts but its module does not provide {', '.join(p['missing'])}"
            for p in missing_visual_providers
        ]
        if tiny:
            found.append(
                f"[{scheme}] widgets rendered with no usable size: {json.dumps(tiny)}"
            )
        found += [
            f"[{scheme}] <{u['tag']} id={u['id']!r}> shows {u['w']}x{u['h']}px of words"
            " and offers no box to mark: it draws none of its own and no element inside"
            " it draws one either, so a comment anchored here would outline nothing and"
            " the ask walk would travel to the top of the page. Put the words in an"
            " element that takes a box"
            for u in unmarkable
        ]
        if overflow > 0:
            found.append(f"[{scheme}] the page scrolls sideways by {overflow}px")
        found += [f"[{scheme}] {s}" for s in misplaced]
        found += [f"[{scheme}] {w}" for w in withheld]
        found += [f"[{scheme}] {s}" for s in squeezed]
        found += [
            f"[{scheme}] the control .{c['ctrl'].split()[0]}"
            + (f" (#{c['id']})" if c["id"] else "")
            + f" is drawn {c['lost']}px outside the {c['by']} that clips it, where"
            " nothing can scroll to reach it — the page offers a press it does not show"
            for c in clipped
        ]
        found += [f"[{scheme}] {w}" for w in unreachable]
        found += [f"[{scheme}] {c}" for c in covered]
        found += [f"[{scheme}] {u}" for u in unread]
        if undeclared_shadow:
            found.append(
                f"[{scheme}] shadow roots the registry doesn't declare "
                f"(an undeclared root's words anchor quotes astray; declare "
                f"x-shadow): {', '.join(undeclared_shadow)}"
            )
        found += [f"[{scheme}] {d}" for d in dishonest_verbatim]
        found += [f"[{scheme}] {s}" for s in silent]
        for c in missing_conversations:
            found.append(
                f"[{scheme}] <{c['tag']} id={c['id']!r}> declares x-conversation but "
                f"rendered {c['hosts']} matching hosts; its module must place exactly "
                "one conversationBox"
            )
        for u in {(x["tag"], x["attr"]): x for x in undeclared_attrs}.values():
            found.append(
                f"[{scheme}] <{u['tag']} id={u['id']!r}> carries {u['attr']!r}, which "
                "its registry entry does not declare — declare it as a verb's record "
                "form (x-state) if a version is meant to carry it, or write the state "
                "on the chrome the module built"
            )
        for t in {(x["tag"], x["edge"]): x for x in trapped}.values():
            box = f"<{t['tag']}" + (f" class={t['cls']!r}" if t["cls"] else "") + ">"
            found.append(
                f"[{scheme}] {box} draws {t['drawn']:g}px of inset and shows "
                f"{t['drawn'] + t['margin']:g}px {t['edge']} what it holds "
                f"(id={t['id']!r}): its {t['edge'] == 'above' and 'first' or 'last'} "
                f"block is a <{t['child']}> reserving {t['margin']:g}px against a "
                f"neighbour it hasn't got, and the box is where that margin stops. "
                f"Declare --lf-frame: 1 in the rule that draws the frame, so the trim "
                f"in theme.css reaches it"
            )

        found += [f"[{scheme}] {r}" for r in retired]
        found += [f"[{scheme}] {u}" for u in unsettled]
        found += [f"[{scheme}] {c}" for c in conflicts]
        found += [f"[{scheme}] {r}" for r in relative]
        found += on_paper
        notices = [f"[{scheme}] console: {e}" for e in resize_notices]
        return found, notices, True

    try:
        light, light_notices, light_complete = in_scheme("light")
        dark, dark_notices, dark_complete = in_scheme("dark")
    except PlaywrightError:
        for page in opened_pages:
            if not page.is_closed():
                page.close()
        raise
    return (
        [*light, *dark],
        [*light_notices, *dark_notices],
        light_complete and dark_complete,
    )


def render_version(browser, url: str, served_timeout_ms: int | None = None) -> list:
    """Read a version, confirming a complete attempt that reports a ResizeObserver
    loop notice.

    Chrome can emit the notice once under load, while a layout feedback loop emits it
    on every rendering. The unit here is the whole light-and-dark gate, including its
    print and replay probes: a notice is ignored only when a later complete attempt is
    clean. Ordinary failures from both attempts are retained, and an incomplete
    confirmation cannot pardon the notice that prompted it.
    """
    served_timeout_ms = (
        SERVED_TIMEOUT_MS if served_timeout_ms is None else served_timeout_ms
    )
    from playwright.sync_api import Error as PlaywrightError

    failures = []

    def retain(found):
        failures.extend(failure for failure in found if failure not in failures)

    def attempt():
        try:
            return _render_version_attempt(
                browser, url, served_timeout_ms=served_timeout_ms
            )
        except PlaywrightError as error:
            return (
                [
                    "the browser gate failed while running its probe module: "
                    + str(error).strip().splitlines()[0]
                ],
                [],
                False,
            )

    found, notices, complete = attempt()
    retain(found)
    if not complete:
        retain(notices)
        return failures
    if not notices:
        return failures

    found, confirming_notices, complete = attempt()
    retain(found)
    if not complete:
        for notice in [*notices, *confirming_notices]:
            retain([f"{notice} (the confirming render attempt did not complete)"])
        return failures
    if confirming_notices:
        failures.append(recurring_resize_observer_error("render attempt"))
    return failures


@contextlib.contextmanager
def preview_server(
    page_dir: Path,
    version: int,
    *,
    handler_factory=None,
    server_type=None,
    transition_held: bool = False,
):
    """The page directory on a loopback port, exposing versions up to this one, for
    the length of a `with`. Two callers need a browser to see a version the user
    may not have (`version check --render` before its note lands, `version export`
    on any published one), and the preview window is what lets them: the server's
    own liveness rule is the user's, and this widens it for exactly one process."""
    # Its own key, not the machine's: this server is loopback-only and lives for
    # the length of a `with`, so it neither needs nor should mint the access every
    # page here is read with. It sets that key under the one cookie name, which
    # would sign a reader out of every page on 127.0.0.1 — except that both
    # callers below drive Playwright, whose browser brings its own jar.
    handler_factory = handler_for if handler_factory is None else handler_factory
    server_type = LeafHTTPServer if server_type is None else server_type
    transition = (
        contextlib.nullcontext()
        if transition_held
        else flocked(transition_lock(page_dir))
    )
    with transition:
        token = secrets.token_urlsafe(16)
        httpd = server_type(
            ("127.0.0.1", 0), handler_factory(page_dir, token, preview_upto=version)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/versions/{version_name(version)}?t={token}"
        finally:
            httpd.shutdown()


@contextlib.contextmanager
def preview_source_server(
    page_dir: Path,
    source: bytes,
    revision: int,
    *,
    handler_factory=None,
    server_type=None,
    transition_held: bool = False,
):
    """Serve exact candidate source without making it a durable revision."""
    handler_factory = handler_for if handler_factory is None else handler_factory
    server_type = LeafHTTPServer if server_type is None else server_type
    transition = (
        contextlib.nullcontext()
        if transition_held
        else flocked(transition_lock(page_dir))
    )
    with transition:
        token = secrets.token_urlsafe(16)
        events = read_events(page_dir)
        active = {
            "revision": revision,
            "version": None,
            "url": "/",
            "label": revision_label(events, revision),
            "activated_at": now_iso(),
        }
        httpd = server_type(
            ("127.0.0.1", 0),
            handler_factory(
                page_dir,
                token,
                preview_source={"data": source, "active": active},
            ),
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/?t={token}"
        finally:
            httpd.shutdown()


def render_check(
    page_dir: Path,
    version: int | None = None,
    *,
    source: bytes | None = None,
    revision: int | None = None,
    preview=None,
    render=None,
    transition_held: bool = False,
) -> int:
    """Serve the page directory to the machine's installed Chrome and run the
    render invariants on this version.

    Playwright is the gate's own extra, not the script's: declaring it in the
    PEP 723 header would put its wheel in every `server run`, `leaf wait`, and
    `version stamp`, so the import happens here and its absence names the
    invocation that supplies it. Chrome is part of this gate: if it cannot
    launch, the gate fails."""
    if source is not None and revision is None:
        raise ValueError("a source preview needs its candidate revision")
    preview = (
        (preview_source_server if source is not None else preview_server)
        if preview is None
        else preview
    )
    render = render_version if render is None else render
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "version check --render needs Playwright; run it as\n"
            "  leaf version check <page> --render\n"
            "or, from a checkout,\n"
            "  plugins/leaf/bin/leaf version check <page> --render",
            file=sys.stderr,
        )
        return 1
    name = "index.html" if source is not None else version_name(version)
    preview_args = (
        (page_dir, source, revision) if source is not None else (page_dir, version)
    )
    with (
        preview(*preview_args, transition_held=transition_held) as url,
        sync_playwright() as p,
    ):
        try:
            browser = p.chromium.launch(channel="chrome")
        except PlaywrightError as error:
            print(
                "✗ render check failed — Chrome did not launch: "
                + str(error).strip().splitlines()[0],
                file=sys.stderr,
            )
            return 1
        try:
            failures = render(browser, url)
        finally:
            browser.close()
    if failures:
        print(f"✗ {name}: renders broken — {len(failures)} issue(s)", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(
        f"✓ {name}: renders clean in Chrome, light and dark — no console errors, "
        "every widget takes space, no words on top of other words, code that reads "
        "against the block it is on, boxes showing the inset they draw, nothing past the "
        "column, no sideways scroll"
    )
    return 0


# ---------- export: the page as one file ----------
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
    for src in sorted(set(parsed.media_refs) | css_refs):
        file = page_dir / src.lstrip("/")
        data = base64.b64encode(file.read_bytes()).decode()
        uri = f"data:{MEDIA_TYPES[file.suffix]};base64,{data}"
        html = html.replace(f'="{src}"', f'="{uri}"').replace(
            f"url({src})", f"url({uri})"
        )
    return html


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
            "  plugins/leaf/bin/leaf version export <page> -o <file>"
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
