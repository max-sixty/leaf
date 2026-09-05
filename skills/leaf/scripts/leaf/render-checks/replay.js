import { shallowSigs, standingState } from "/runtime/widget-api.js";

// A version whose markup asserts a state the log replays over — `chosen` moved
// to another option, a card re-authored into a column the user dragged it
// out of. Replay resolves it in the user's favor, so what needs reporting is
// the author's intent going down silently. The static half can't say which
// attribute is a verb's state — that lives in each widget's renderState, and a
// table here would be the second copy the registry exists to prevent — so the
// browser compares: projection reconciliation records the ids it wrote on the body
// (data-lf-replay-wrote), and this pass asks which of them the author also
// changed since the previous version, reading both files with the runtime's own
// shallowSigs. An authored change replay then overrode is a conflict; an
// unchanged id is the initial condition the log is supposed to outrank. For the
// message, each conflicting id is laid at the door of the widget whose replay
// wrote it — its nearest ancestor with an renderState.
//
// The two files are handed in rather than fetched: which pair to compare is a
// question about the log and the URL, both of which the caller holds, and a read
// it makes is a read it can put a deadline on (see `served` in render_version).
export function replayOverrides({ curHtml, prevHtml }) {
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
      if (a.renderState) {
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

// The complete renderer must be idempotent. Invoke it directly rather than the
// reconciler, whose committed-state checkpoint would skip an unchanged value.
// Compare both id-bearing structure and body facets: text is absent from shallowSigs.
export function relativeReplays() {
  const at = (el) => `<${el.localName}${el.id ? " id=" + el.id : ""}>`;
  const standing = standingState().filter((s) => s.widget?.renderState);
  if (!standing.length) return [];
  const found = [];
  const before = shallowSigs(document.body);
  const bodies = standing.map((s) => JSON.stringify(s.read()));
  for (const { widget, state } of standing) {
    try {
      widget.renderState(state);
    } catch (error) {
      found.push(
        `${at(widget)} renderState threw when the complete state was rendered a second time: ${error?.message ?? error}`,
      );
    }
  }
  const now = shallowSigs(document.body);
  const groups = new Map();
  const note = (key, what) => {
    if (!groups.has(key)) groups.set(key, new Set());
    groups.get(key).add(what);
  };
  for (const id of new Set([...before.keys(), ...now.keys()])) {
    if (before.get(id) === now.get(id)) continue;
    let widget = document.getElementById(id);
    while (widget && !widget.renderState) widget = widget.parentElement;
    note(widget ? at(widget) : `id=${id}`, id);
  }
  standing.forEach((s, i) => {
    if (JSON.stringify(s.read()) !== bodies[i]) note(at(s.widget), "body text");
  });
  return [
    ...found,
    ...[...groups].map(
      ([who, moved]) =>
        `${who} renderState is relative — rendering the same complete state changed ${[...moved].join(", ")}. Render the supplied values without stepping from the DOM.`,
    ),
  ];
}
