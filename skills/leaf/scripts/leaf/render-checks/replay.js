import { shallowSigs } from "/runtime/widget-api.js";
import { validationWidgetStates } from "/runtime/check-api.js";
import { at } from "./locate.js";

// The complete renderer must be idempotent. Invoke it directly rather than the
// reconciler, whose committed-state checkpoint would skip an unchanged value.
// Compare both id-bearing structure and body records: text is absent from shallowSigs.
export function relativeReplays() {
  const standing = validationWidgetStates().filter((s) => s.widget?.renderState);
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
