import { shallowSigs, validationWidgetStates } from "/runtime/check-api.js";
import { exceptionText } from "/runtime/lib/exception.js";
import { at } from "./locate.js";

// The complete renderer must be idempotent: Leaf may set an equal `state` twice, and
// the setter draws the whole of it (module-plain-elements.md, "`state`"). So set each
// widget that holds a state a copy equal to it, as Leaf would, and compare both
// id-bearing structure and body records: text is absent from shallowSigs. A widget
// whose `state` reads back nothing, as one with a setter alone, is not replayed. A
// setter's failure, thrown or said as the widget's `error`, is the replay's finding,
// kept from the page's own report of failures so it is said once.
/** @param {(Element & {state?: unknown}) | null | undefined} widget
 * @returns {widget is Element & {state: object}} */
const holdsState = (widget) =>
  typeof widget?.state === "object" && widget.state !== null;
export function relativeReplays() {
  const rendered = validationWidgetStates().flatMap(({ widget, read }) =>
    holdsState(widget) ? [{ widget, read }] : [],
  );
  if (!rendered.length) return [];
  /** @type {Set<Element>} */
  const replayed = new Set(rendered.map(({ widget }) => widget));
  /** @type {Record<string, unknown>[]} */
  const found = [];
  const before = shallowSigs(document.body);
  const bodies = rendered.map((s) => JSON.stringify(s.read(s.widget)));
  for (const { widget } of rendered) {
    /** @param {unknown} error */
    const threw = (error) =>
      found.push({ code: "render-threw", at: at(widget), error: exceptionText(error) });
    /** @param {Event} event */
    const said = (event) => {
      if (event.target !== widget) return;
      event.stopImmediatePropagation();
      const failure = /** @type {ErrorEvent} */ (event);
      threw(failure.error ?? failure.message);
    };
    widget.addEventListener("error", said, { capture: true });
    try {
      widget.state = Object.freeze({ ...widget.state });
    } catch (error) {
      threw(error);
    } finally {
      widget.removeEventListener("error", said, { capture: true });
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
    /** @type {Element | null} */
    let widget = document.getElementById(id);
    while (widget && !replayed.has(widget)) widget = widget.parentElement;
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
