"""Browser probe readings for one settled color scheme, and the finding each becomes."""

import json
from dataclasses import dataclass

from leaf.passages import EMPTY, spoken
from leaf.projection import (
    frozen_thread_reading,
    page_projection,
    retirement_holders,
    retirement_outcomes,
)
from leaf.registry.state import retirement_slots
from leaf.render_checks import evaluate_probe, wait_for_probe


@dataclass(frozen=True, slots=True)
class _SchemeContext:
    page: object
    scheme: str
    errors: list
    resize_notices: list
    registry: dict
    widgets: dict
    state: dict
    markup: str
    here: int
    earlier: str | None
    touched: list
    replayed: bool
    unsettled: list


def _scheme_findings(context: _SchemeContext) -> tuple[list, list]:
    page = context.page
    scheme = context.scheme
    registry = context.registry
    widgets = context.widgets
    state = context.state
    markup = context.markup
    here = context.here
    earlier = context.earlier
    touched = context.touched
    replayed = context.replayed
    errors = context.errors
    resize_notices = context.resize_notices
    unsettled = context.unsettled
    failsoft = evaluate_probe(page, "failSoftErrors")
    invalid_paints = evaluate_probe(page, "invalidPaints")
    missing_upgrades = evaluate_probe(page, "missingUpgrades", widgets)
    visual_provider_problems = evaluate_probe(page, "invalidVisualProviders", widgets)
    tiny = evaluate_probe(page, "tinyBoxes", widgets)
    unmarkable = evaluate_probe(page, "unmarkableItems")
    overflow = evaluate_probe(page, "rootOverflow")
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
        missing_conversations = evaluate_probe(page, "missingConversations", widgets)
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
            thread = frozen_thread_reading(state["events"], registry)
            spk = {**thread.spoken, **spoken(markup, registry)}
            dishonest_verbatim = [
                f"<{s['tag']} id={s['id']!r}> declares x-verbatim but shows "
                f"{s['says'][:80]!r} where the file reads "
                f"{spk.get(s['id'], EMPTY).words[:80]!r}"
                for s in shown
                if s["says"] != spk.get(s["id"], EMPTY).words
            ]
        # Behind the caught-up wait above: a report moves a painted attribute and
        # the pass that speaks it runs before the stamp, so a reading taken any
        # earlier asks after a word the page has not been asked to say yet. A page
        # that never caught up is already reported there and read no further.
        if replayed:
            silent = evaluate_probe(page, "silentWords", widgets)
            # Behind the same wait, because reconciliation is one of the two
            # writers: a renderState states one declared fact whole, and a
            # record form is exactly the attribute it may state that fact in.
            undeclared_attrs = evaluate_probe(page, "undeclaredAttrs", widgets)
            # Behind it too: the settlement mark is replay's own write, so a
            # reading taken earlier asks after paint the page has not been
            # asked to make yet. The expected outcomes are the file's, scoped
            # to each holder's own relation: `retirement_outcomes` folds any verb that
            # retires somewhere in the vocabulary, so a verb of that name on
            # a family it settles nothing of decides nothing here — the
            # browser's write reads the per-holder relation, and a comparison
            # against anything wider would fail a page both sides are right
            # about.
            if slots := retirement_slots(registry):
                projection, vparser, _ = page_projection(
                    markup, state["events"], registry, here
                )
                outcomes = retirement_outcomes(projection.actions, registry)
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
            for s, p in zip(screen, paper, strict=False)
            if s["text"] == p["text"] and s["shown"] and not p["shown"]
        ]
    # Last: these probes render temporary complete states. Compare carried actions
    # against the authored baseline, restore current state, then prove idempotence.
    # The caught-up wait ensures they observe the same settled projection as the
    # preceding read-only probes.
    relative = []
    if scheme == "light" and replayed:
        if touched and earlier is not None:
            projection, _, _ = page_projection(markup, state["events"], registry, here)
            conflicts = evaluate_probe(
                page,
                "replayOverrides",
                {
                    "curHtml": markup,
                    "prevHtml": earlier,
                    "carriedActions": [
                        event["id"]
                        for event, _spec in projection.actions.values()
                        if event["revision"] < here
                    ],
                },
            )
        relative = evaluate_probe(page, "relativeReplays")
    # The print reset and replay above can resize what an observer watches. Chrome
    # delivers that notice in the next rendering turn, so closing on the write
    # would call an attempt complete before its last error channel had spoken. Ask
    # synchronously and poll the presented-frame fact from the driver: a compositor
    # that never draws cannot strand page.evaluate on its unresolved Promise.
    requested_frame = evaluate_probe(page, "requestFrame")
    wait_for_probe(page, "framePresented", requested_frame)
    found = [f"[{scheme}] console: {e}" for e in errors]
    found += [f"[{scheme}] a widget failed soft: {t}" for t in failsoft]
    for paint in invalid_paints:
        owner = f"<{paint['tag']}" + (f" id={paint['id']!r}>" if paint["id"] else ">")
        part = f" for data-id={paint['part']!r}" if paint["part"] else ""
        found.append(
            f"[{scheme}] {owner} renders {paint['property']}={paint['value']!r} "
            f"on <{paint['element']}>{part}, but that value does not resolve to valid "
            f"{paint['property']}"
        )
    if missing_upgrades:
        found.append(
            f"[{scheme}] upgraded widgets did not define their elements: "
            + ", ".join(f"<{tag}>" for tag in missing_upgrades)
        )
    found += [
        f"[{scheme}] <{p['tag']} id={p['id']!r}> declares addressable visual "
        f"parts but its module {'; '.join(p['problems'])}"
        for p in visual_provider_problems
    ]
    if tiny:
        found.append(
            f"[{scheme}] widgets rendered with no usable size: {json.dumps(tiny)}"
        )
    found += [
        f"[{scheme}] <{u['tag']} id={u['id']!r}> shows {u['w']}x{u['h']}px of words"
        " and offers no box to mark: it draws none of its own and no element inside"
        " it draws one either, so a comment anchored here would outline nothing and"
        " the Ask walk would travel to the top of the page. Put the words in an"
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
    return found, notices
