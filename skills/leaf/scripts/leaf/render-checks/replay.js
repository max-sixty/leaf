import {
  exceptionText,
  shallowSigs,
  validationWidgetStates,
} from "/runtime/check-api.js";
import { at } from "./locate.js";

// The complete renderer must be idempotent. Invoke it directly rather than the
// reconciler, whose committed-state checkpoint would skip an unchanged value.
// Compare both id-bearing structure and body records: text is absent from shallowSigs.
export function relativeReplays() {
  const rendered = validationWidgetStates().filter((s) => s.widget?.renderState);
  if (!rendered.length) return [];
  const found = [];
  const before = shallowSigs(document.body);
  const bodies = rendered.map((s) => JSON.stringify(s.read()));
  for (const { widget, state } of rendered) {
    try {
      widget.renderState(state);
    } catch (error) {
      found.push({ code: "render-threw", at: at(widget), error: exceptionText(error) });
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
    /** @type {(HTMLElement & {renderState?: unknown}) | null} */
    let widget = document.getElementById(id);
    while (widget && !widget.renderState) widget = widget.parentElement;
    note(widget ? at(widget) : `id=${id}`, id);
  }
  rendered.forEach((s, i) => {
    if (JSON.stringify(s.read()) !== bodies[i]) note(at(s.widget), "body text");
  });
  return [
    ...found,
    ...[...groups].map(([who, moved]) => ({
      code: "relative-render",
      at: who,
      changed: [...moved],
    })),
  ];
}
