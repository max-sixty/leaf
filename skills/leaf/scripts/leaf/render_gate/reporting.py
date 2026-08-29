"""Human-readable findings from one color-scheme reading."""

import json

from .models import _SchemeContext, _SchemeReadings


def _scheme_result(
    context: _SchemeContext, readings: _SchemeReadings
) -> tuple[list, list, bool]:
    scheme = context.scheme
    errors = context.errors
    resize_notices = context.resize_notices
    unsettled = context.unsettled
    failsoft = readings.failsoft
    missing_upgrades = readings.missing_upgrades
    missing_visual_providers = readings.missing_visual_providers
    tiny = readings.tiny
    unmarkable = readings.unmarkable
    overflow = readings.overflow
    misplaced = readings.misplaced
    withheld = readings.withheld
    squeezed = readings.squeezed
    clipped = readings.clipped
    unreachable = readings.unreachable
    covered = readings.covered
    unread = readings.unread
    undeclared_shadow = readings.undeclared_shadow
    conflicts = readings.conflicts
    dishonest_verbatim = readings.dishonest_verbatim
    silent = readings.silent
    missing_conversations = readings.missing_conversations
    undeclared_attrs = readings.undeclared_attrs
    retired = readings.retired
    trapped = readings.trapped
    on_paper = readings.on_paper
    relative = readings.relative
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
        " the decision walk would travel to the top of the page. Put the words in an"
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
