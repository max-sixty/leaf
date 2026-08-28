"""Validation of authored changes against standing actions and reports."""

from leaf.passages import EMPTY, collapse, enclosing_of
from leaf.projection import (
    NO_RECORD,
    StateProjection,
    action_subjects,
    folded_facet,
    markup_facet,
)

from .markup import at


# A verb with no declared record form (accept/reject — the honoring version
# retires the wrapper, so there is no markup value to compare) has no record.


def restatement_errors(
    cur,
    prev,
    was: dict,
    now: dict,
    prev_num: int,
    registry: dict,
    projection: StateProjection,
    floors: dict,
) -> list:
    """The other half of the id-survival rule. That one keeps a revision from
    dropping the anchors a user hung on the page; this one keeps it from
    dropping the decisions they recorded on it. CLAUDE.md carries why the log
    outranks the markup and what that cost.

    The runtime reconciles every standing action onto every later version, so a
    version cannot revise what a user acted on: reconciliation would paint their
    recorded state back over the revision and the new words would reach nobody. A
    version that means to revise says so — `restated` on what it rewrote — and one that
    changes those words in silence is refused here. An unearned `restated` is an
    error too: a decision thrown away for nothing, and, left unchecked, the
    one-word ritual that would make this gate meaningless.

    The comparison is the words each version says (`spoken`), because words are
    what a decision is about. Re-indenting a draft, marking the picked option
    `chosen`, or relocating a card the user already moved is not a revision,
    and neither is writing their own edit back — a version that says what they
    said is agreeing with them.

    Words are one divergence kind; declared state is the other. For each verb
    the registry declares (x-state), the fold gives the user's standing
    state per owner, unit, and facet, and a version whose markup actively changes that unit's
    record away from both the previous version's and the fold is refused the
    same way a silent rewrite of words is. Writing the folded state is the
    state-level echo (honoring); re-emitting the previous version's state is
    blessed silence, which reconciliation resolves; a unit with no surviving folded
    action is exempt — never decided, or retracted back to the author. And
    `restated` is earned by either divergence kind: a words-unchanged
    relocation earns it at the unit even though no subject's words moved."""
    errors = []
    declared = cur.restated
    # Retractions up to prev — never this version's own, which is what it is
    # here to declare, so re-checking a stamped revision reaches the same
    # verdict as checking it did.
    byid = cur.by_id

    decided = {}  # subject id → the actions resting on it
    within = enclosing_of(now)
    for e, _spec in projection.actions.values():
        for subject in action_subjects(e, byid, within, registry):
            if subject in was:
                decided.setdefault(subject, []).append(e)

    # The state gate, beside the words gate: one gate, two divergence kinds.
    prev_byid = prev.by_id
    facet_earned = set()
    for coordinate in sorted(projection.actions):
        _widget, unit, _facet = coordinate
        e, spec = projection.actions[coordinate]
        rec = byid.get(unit)
        # A unit either version lacks is id-survival's business, not this gate's.
        if rec is None or unit not in prev_byid:
            continue
        f_cur = markup_facet(unit, spec, byid, now, registry)
        f_prev = markup_facet(unit, spec, prev_byid, was, registry)
        if f_cur is NO_RECORD or f_cur == f_prev:
            continue  # no record form, or no active change — replay resolves silence
        f_fold = folded_facet(e, spec)
        if f_cur == f_fold:
            continue  # writing the folded state is honoring: the state-level echo
        if unit in declared:
            facet_earned.add(unit)
            continue
        where = at(rec, f"id={unit!r}")
        errors.append(
            f"{where}: its state changed under the user's decision — the markup "
            f"shows {f_cur!r} where their {e['action']} (on r{e['revision']}) "
            f"left {f_fold!r}. Their decision is what the page shows, so this state "
            f"would never reach them — add `restated` to retract it and ask again, "
            f"or leave it as r{prev_num} had it."
        )

    for sid, rec in sorted(byid.items()):
        live, restated = decided.get(sid, []), sid in declared
        # A version that writes back what the user themselves recorded is
        # agreeing with them, not overruling them — an honored `edit` is the
        # commonest and most correct thing an author does with a draft, and the
        # gate has to stay quiet for it or it fires on nearly every version and
        # teaches authors to reach for `restated` by reflex. No verb is special-
        # cased: it is enough that the words on the page are words the user
        # sent.
        # `resolves` is not among them: the registry reserves it for the thread
        # an action answers, so its value is a comment id rather than words
        # anybody sent. `action_rests_on` reads past it for the same reason.
        echoed = {
            collapse(str(v))
            for e in live
            for field, v in e["detail"].items()
            if field != "resolves" and isinstance(v, str)
        }
        said = now.get(sid, EMPTY).words
        changed = sid in was and said != was[sid].words and said not in echoed
        where = at(rec, f"id={sid!r}")
        # `restated` is earned by either divergence kind — words on the leaf, or
        # declared state at the unit — else a words-unchanged relocation would
        # be refused both with the attribute and without it.
        if restated and not ((live and changed) or sid in facet_earned):
            # An already-retracted widget is the case an author lands on by being
            # careful — carrying the attribute forward the way state used to have
            # to be carried — so it gets its own answer rather than the
            # never-decided one, which would read as if the user had done
            # nothing.
            if sid in floors:
                errors.append(
                    f"{where}: restated, but r{floors[sid]} already took that "
                    f"back — a retraction is recorded when it is stamped and holds "
                    f"without being repeated. Drop the attribute."
                )
            else:
                why = (
                    f"its words are unchanged since r{prev_num}"
                    if live
                    else "the user has recorded nothing on it"
                )
                errors.append(
                    f"{where}: restated, but there is nothing to retract — {why}. "
                    f"Drop the attribute; `restated` discards their decision."
                )
        elif changed and live and not restated:
            did = ", ".join(f"{e['action']} on r{e['revision']}" for e in live[-3:])
            errors.append(
                f"{where}: its words changed, and the user has already acted "
                f"on it ({did}). Their decision is what the page shows, so these "
                f"words would never reach them — add `restated` to retract it and "
                f"ask again, or leave the text as r{prev_num} had it."
            )
    return errors


def report_errors(
    cur,
    prev,
    was: dict,
    now: dict,
    registry: dict,
    projection: StateProjection,
) -> list:
    """The report gate, beside the reviewer one — the same shape with the
    precedence reversed. A report is a worker's provisional news: the runtime
    paints it onto every revision activated before it, and it stands only until
    a version settles its typed id on the note (the agent-side counterpart to
    `restated`). Three outcomes are legal. Writing the reported state is
    honoring — stamping records it as absorption. Leaving the markup as the
    previous version had it is blessed silence — the report keeps painting.
    Marking the element `overruled` keeps this version's own state and retires
    the report, with the why in the note's text. What is refused is the fourth
    thing, markup that contradicts a standing report it never names: the drop
    must be the publisher's to adjudicate, never silent. And an unearned
    `overruled` is refused like an unearned `restated` — spent where nothing
    stands or where the markup agrees with the report, it is the reflex that
    would make the gate meaningless.

    Standing is read up to prev — never this version's own note, which is what
    stamping is about to record — so re-checking a stamped version reaches
    the same verdict as checking it did."""
    errors = []
    declared = cur.overruled
    byid = cur.by_id
    prev_byid = prev.by_id
    effective_standing = {
        coordinate: reports
        for coordinate, reports in projection.reports.items()
        if coordinate not in projection.actions
    }
    earned = set()
    for coordinate in sorted(effective_standing):
        _widget, unit, _facet = coordinate
        e, spec = effective_standing[coordinate][-1]
        f_cur = markup_facet(unit, spec, byid, now, registry)
        f_rep = folded_facet(e, spec)
        # Whether an `overruled` is earned is this version's markup against the
        # report, so it is settled ahead of the skip below: a unit the gate declines
        # to adjudicate would otherwise land in `unearned` and be told it writes the
        # reported state it in fact contradicts.
        if unit in declared and f_cur != f_rep:
            earned.add(unit)  # a named disagreement, whatever state it keeps
            continue
        rec = byid.get(unit)
        # A unit either version lacks is id-survival's business, not this gate's.
        if rec is None or unit not in prev_byid:
            continue
        if f_cur == f_rep:
            continue  # honoring: stamping absorbs the report by id
        if f_cur == markup_facet(unit, spec, prev_byid, was, registry):
            continue  # blessed silence: the report keeps painting
        where = at(rec, f"id={unit!r}")
        who = e.get("agent", "a worker")
        errors.append(
            f"{where}: its markup contradicts a standing report — it shows "
            f"{f_cur!r} where {who}'s {e['action']} (report {e['id']}, on "
            f"r{e['revision']}) left {f_rep!r}. Adjudicate it: write the reported "
            f"state to absorb the report, or add `overruled` to keep this state "
            f"and retire it (say why in the note)."
        )
    unearned = declared - earned
    # Where an attribute is spent past its revision: which revision already
    # answered the unit's reports, for the message that says to drop it.
    answered_at = {}
    if unearned:
        for (_widget, unit, _facet), revision in projection.report_settlements.items():
            answered_at[unit] = max(answered_at.get(unit, 0), revision)
    for sid in sorted(unearned):
        rec = byid.get(sid)
        if rec is None:
            continue
        where = at(rec, f"id={sid!r}")
        if any(unit == sid for _widget, unit, _facet in effective_standing):
            errors.append(
                f"{where}: overruled, but this version writes the reported state — "
                f"that is absorption, which stamping records on its own. "
                f"Drop the attribute."
            )
        elif sid in answered_at:
            errors.append(
                f"{where}: overruled, but r{answered_at[sid]} already answered the "
                f"reports on it — an answer is recorded when it is stamped and "
                f"holds without being repeated. Drop the attribute."
            )
        else:
            errors.append(
                f"{where}: overruled, but no report is standing on it — there is "
                f"nothing to overrule. Drop the attribute."
            )
    return errors
