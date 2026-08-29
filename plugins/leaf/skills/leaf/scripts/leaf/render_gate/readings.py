"""Browser probe readings for one settled color scheme."""

import json

from leaf.event_contracts import thread_universe
from leaf.passages import EMPTY, spoken
from leaf.projection import decisions, page_projection, retirement_holders
from leaf.registry.state import retirement_slots
from leaf.render_checks import evaluate_probe

from .models import _SchemeContext, _SchemeReadings


def _read_scheme(context: _SchemeContext) -> _SchemeReadings:
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
    failsoft = evaluate_probe(page, "failSoftErrors")
    missing_upgrades = evaluate_probe(page, "missingUpgrades", widgets)
    missing_visual_providers = evaluate_probe(page, "missingVisualProviders", widgets)
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
    return _SchemeReadings(
        failsoft=failsoft,
        missing_upgrades=missing_upgrades,
        missing_visual_providers=missing_visual_providers,
        tiny=tiny,
        unmarkable=unmarkable,
        overflow=overflow,
        misplaced=misplaced,
        withheld=withheld,
        squeezed=squeezed,
        clipped=clipped,
        unreachable=unreachable,
        covered=covered,
        unread=unread,
        undeclared_shadow=undeclared_shadow,
        conflicts=conflicts,
        dishonest_verbatim=dishonest_verbatim,
        silent=silent,
        missing_conversations=missing_conversations,
        undeclared_attrs=undeclared_attrs,
        retired=retired,
        trapped=trapped,
        on_paper=on_paper,
        relative=relative,
    )
