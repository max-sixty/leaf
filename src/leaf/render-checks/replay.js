import {
  exceptionText,
  shallowSigs,
  validationWidgetStates,
} from "/runtime/check-api.js";
import { at } from "./locate.js";

// The complete renderer must be idempotent. Draw each widget's reading again directly,
// through its `redraw` (leaf-element.js), rather than through its update cycle, which
// could skip an unchanged value or show a throw as the widget's failure box. Compare
// both id-bearing structure and body records: text is absent from shallowSigs.
/** @param {(Element & {redraw?: unknown}) | null | undefined} widget
 * @returns {widget is Element & {redraw: () => void}} */
const drawsWhole = (widget) => typeof widget?.redraw === "function";
export function relativeReplays() {
  const rendered = validationWidgetStates().flatMap(({ widget, read }) =>
    drawsWhole(widget) ? [{ widget, read }] : [],
  );
  if (!rendered.length) return [];
  const found = [];
  const before = shallowSigs(document.body);
  const bodies = rendered.map((s) => JSON.stringify(s.read(s.widget)));
  for (const { widget } of rendered) {
    try {
      widget.redraw();
    } catch (error) {
      found.push({ code: "render-threw", at: at(widget), error: exceptionText(error) });
    }
  }
  const now = shallowSigs(document.body);
  /** @type {Map<string, Set<string>>} */
  const groups = new Map();
  const note = (/** @type {string} */ key, /** @type {string} */ what) => {
    const group = groups.get(key);
    if (group) group.add(what);
    else groups.set(key, new Set([what]));
  };
  for (const id of new Set([...before.keys(), ...now.keys()])) {
    if (before.get(id) === now.get(id)) continue;
    /** @type {(Element & {redraw?: unknown}) | null} */
    let widget = document.getElementById(id);
    while (widget && !drawsWhole(widget)) widget = widget.parentElement;
    note(widget ? at(widget) : `id=${id}`, id);
  }
  rendered.forEach((s, i) => {
    if (JSON.stringify(s.read(s.widget)) !== bodies[i]) note(at(s.widget), "body text");
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
