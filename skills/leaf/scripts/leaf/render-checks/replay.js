import { inChrome, shallowSigs, standingState } from "/runtime/widget-api.js";

// Measure the state painted by surviving decisions made before this revision.
// A decision made on this markup cannot contradict its authoring, even when the
// widget or facet changed since the previous stamp. Render the authored baseline
// and those carried winners through the same complete-state fold, then restore
// the full current state. This also separates old and new facets on one owner.
// Run after the observational probes: these temporary renders change the page.
export function replayOverrides({ curHtml, prevHtml, carriedActions }) {
  if (!carriedActions.length) return [];
  const pageStates = (ids) =>
    standingState(ids).filter((s) => s.widget?.renderState && !inChrome(s.widget));
  const current = pageStates(null);
  const render = (states) => {
    for (const { widget, state } of states) widget.renderState(state);
  };
  let baseline, carried;
  try {
    render(pageStates([]));
    baseline = shallowSigs(document.body);
    render(pageStates(carriedActions));
    carried = shallowSigs(document.body);
  } finally {
    render(current);
  }
  const sigs = (html) =>
    shallowSigs(new DOMParser().parseFromString(html, "text/html").body);
  const cur = sigs(curHtml),
    prev = sigs(prevHtml);
  // Intersect facts, not whole elements: a carried choice changing `chosen`
  // does not overrule a freshly authored label on that same option.
  const facts = (signature) => {
    if (!signature) return {};
    const { attrs, ...placement } = JSON.parse(signature);
    return {
      ...placement,
      ...Object.fromEntries(
        Object.entries(attrs).map(([key, value]) => [`attr:${key}`, value]),
      ),
    };
  };
  const changed = (before, after) =>
    Object.keys({ ...before, ...after }).filter((key) => before[key] !== after[key]);
  const groups = new Map();
  for (const id of new Set([...baseline.keys(), ...carried.keys()])) {
    const written = changed(facts(baseline.get(id)), facts(carried.get(id)));
    const authored = changed(facts(prev.get(id)), facts(cur.get(id)));
    if (!written.some((key) => authored.includes(key))) continue;
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
