import { shallowSigs, standingState } from "/runtime/widget-api.js";

// A version whose markup asserts a state the log replays over — `chosen` moved
// to another option, a card re-authored into a column the user dragged it
// out of. Replay resolves it in the user's favor, so what needs reporting is
// the author's intent going down silently. The static half can't say which
// attribute is a verb's state — that lives in each widget's applyAction, and a
// table here would be the second copy the registry exists to prevent — so the
// browser compares: projection reconciliation records the ids it wrote on the body
// (data-lf-replay-wrote), and this pass asks which of them the author also
// changed since the previous version, reading both files with the runtime's own
// shallowSigs. An authored change replay then overrode is a conflict; an
// unchanged id is the initial condition the log is supposed to outrank. For the
// message, each conflicting id is laid at the door of the widget whose replay
// wrote it — its nearest ancestor with an applyAction.
//
// The two files are handed in rather than fetched: which pair to compare is a
// question about the log and the URL, both of which the caller holds, and a read
// it makes is a read it can put a deadline on (see `served` in render_version).
export async function replayOverrides({ curHtml, prevHtml }) {
  const ids = (document.body.dataset.lfReplayWrote ?? "").split(" ").filter(Boolean);
  if (!ids.length) return [];
  const sigs = (html) =>
    shallowSigs(new DOMParser().parseFromString(html, "text/html").body);
  const cur = sigs(curHtml),
    prev = sigs(prevHtml);
  const groups = new Map();
  for (const id of ids) {
    if ((cur.get(id) ?? "") === (prev.get(id) ?? "")) continue;
    let widget = null;
    for (let a = document.getElementById(id); a; a = a.parentElement)
      if (a.applyAction) {
        widget = a;
        break;
      }
    const key = widget
      ? `<${widget.tagName.toLowerCase()} id=${widget.id}>`
      : `id=${id}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(id);
  }
  return [...groups].map(
    ([who, asserted]) =>
      `${who} authors state the log replays over (${asserted.join(", ")}): ` +
      `the user's decision stands — either carry it in the markup, or ` +
      `rewrite the passage and declare restated`,
  );
}

// Whether an applyAction is absolute, which is the premise both folds and every view
// built on them rest on and the one thing about a widget module no gate could see. A
// relative implementation — a card shifted one column along, a pick toggled rather than
// set — is invisible to every other reading here: it renders perfectly, and what it
// costs arrives later, in the read that replays the sender's own action over the state
// that gesture already painted. The user drags a card once and watches it walk.
//
// So the page is asked rather than the code. Each standing action is applied a second
// time onto the state the page's own replay produced, and an absolute one has nothing
// to do. Re-running reconciliation would prove nothing — an already committed
// projection is clean whatever the widgets do — which is why this reaches past the
// runtime's checkpoint and calls the method.
//
// The standing state rather than the whole log, because that is the set the contract is
// for: the fold's own claim is that the last surviving action per coordinate *is* the state,
// so the page is already showing exactly these. It is also the set replay applied and
// did not skip — a retracted decision, a version's future action and a widget the
// markup dropped are all out of it — so nothing here re-applies what the page declined.
//
// The whole set at once and in the log's order, never one action measured on its own.
// An absolute applyAction states its own unit and says nothing about any other, so where
// two units share an ordered container the page is the sequence's result rather than any
// one action's: two cards dragged to the head of one column leave it holding the second
// above the first, and lifting the first back over the second is what replaying it alone
// is *supposed* to do. Read per action, that named lf-board relative and refused a page
// with nothing wrong with it — at the gate a handover cannot get past. Read across the
// batch, an absolute set lands exactly where it already was and a relative one walks.
//
// Two readings, because one is blind where the other sees. shallowSigs is the id-bearing
// markup state, which covers a moved card, a flipped attribute and a re-pointed pick;
// it looks away from text on purpose, and a `body` record is nothing but text, so the
// unit's declared facet is read beside it. A throw is a finding of its own rather than
// an exception out of the gate: whatever a second application was expected to do, it was
// not that. Each moved id is then laid at the door of the widget whose applyAction writes
// it — its nearest ancestor with the method, as a replayed override already is — since
// across a batch no single verb owns the difference.
export async function relativeReplays() {
  const at = (el) => `<${el.localName}${el.id ? " id=" + el.id : ""}>`;
  // A fold reads the registry, so a decided widget whose module never loaded is in it
  // and has no method to converge. That failure is reported on its own — the console,
  // the fail-soft box, the undefined element — and asking it this question would only
  // lay the same fault at a second door.
  const standing = standingState().filter((s) => s.widget?.applyAction);
  if (!standing.length) return [];
  const found = [];
  const before = shallowSigs(document.body);
  const stood = standing.map((s) => s.read());
  for (const s of standing) {
    const widget = s.widget;
    if (!widget?.applyAction) continue; // an earlier application replaced it
    try {
      widget.applyAction(s.action, s.detail);
    } catch (error) {
      found.push(
        `${at(widget)} applyAction(${s.action}) threw when the recorded ` +
          `action was applied a second time: ${error?.message ?? error} — ` +
          `replay lays the sender's own action down again, so it has to arrive twice`,
      );
    }
  }
  const now = shallowSigs(document.body);
  const verbs = new Map();
  for (const s of standing) {
    if (!s.widget) continue;
    const key = at(s.widget);
    if (!verbs.has(key)) verbs.set(key, new Set());
    verbs.get(key).add(s.action);
  }
  const groups = new Map();
  const note = (key, what) => {
    if (!groups.has(key)) groups.set(key, new Set());
    groups.get(key).add(what);
  };
  for (const id of new Set([...before.keys(), ...now.keys()])) {
    if (before.get(id) === now.get(id)) continue;
    let widget = null;
    for (let a = document.getElementById(id); a; a = a.parentElement)
      if (a.applyAction) {
        widget = a;
        break;
      }
    note(widget ? at(widget) : `id=${id}`, id);
  }
  // Only body records need the second reading: shallowSigs deliberately excludes
  // text. Key its wording by facet as well as unit, because a markup facet and a
  // body facet may both stand on the same unit and both move in this batch.
  standing.forEach((s, i) => {
    if (s.record !== "body" || s.read() === stood[i] || !s.widget) return;
    note(at(s.widget), `the ${s.facet} state recorded on ${s.unit}`);
  });
  return [
    ...found,
    ...[...groups].map(([who, moved]) => {
      const said = verbs.get(who);
      const named = said?.size ? `applyAction(${[...said].join(", ")})` : "applyAction";
      return (
        `${who} ${named} is relative — re-applying the standing log moved ` +
        `${[...moved].join(", ")}. Replay lays every standing action over the ` +
        `state they already produced, so state the whole value from the detail ` +
        `rather than stepping from what the page shows`
      );
    }),
  ];
}
