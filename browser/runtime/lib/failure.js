// @ts-check
/* A widget's failure: a box where the user is looking, and an `error` event its host
   hears.

   A widget calls `failSoft(el, err, source)` for an upgrade or a part of one that
   failed, which does both, so the rest of the page stays usable rather than blank. A
   widget that shows a failure its own way dispatches the event itself
   (module-plain-elements.md, "`error`"). `showFailure` and `reportFailure`, the box
   alone and the event alone, are for a host that catches a failure on an element it
   drives, as Leaf does for a setter that threw.

   The box names the widget and the failure, with `source` beneath it when given. Where
   it goes is `placesFailure`'s, below; by default it replaces the element's children,
   and the widget's next draw of them replaces it, a template render into the element
   included.

   The event is an `ErrorEvent` named `error`, bubbling and composed, on the element. An
   element out of the document, such as a cached message body while its thread is shut,
   has no way out to the window, so its failure is dispatched there directly. Every
   listener gets an Error: a reason thrown as something else is wrapped. A Leaf page
   reports the failure to the agent as the page's error, naming the widget (`failureOf`,
   `failureContext`), which `page check` fails on; a page that hears nothing still shows
   the box. */
import { describeFailure, exceptionError } from "./exception.js";

/** Show `err` where `el` stands and dispatch it as `el`'s `error` event.
 * @param {Element} el @param {unknown} err @param {string} [source] */
export function failSoft(el, err, source) {
  reportFailure(el, err);
  showFailure(el, err, source);
}

/** Dispatch `err` as `el`'s `error` event, on the window while `el` stands in no
 * document.
 * @param {Element} el @param {unknown} err */
export function reportFailure(el, err) {
  const event = Object.assign(
    new ErrorEvent("error", {
      error: exceptionError(err),
      message: describeFailure(err),
      bubbles: true,
      composed: true,
    }),
    { [FAILURE]: { element: el, reason: err } },
  );
  (el.isConnected ? el : window).dispatchEvent(event);
}

// The element and reason a failure event of `reportFailure`'s carries, the reason as
// thrown.
const FAILURE = Symbol("failure");

/** The failure an `error` event reports: the element and reason `reportFailure` gave
 * it, or, for one an element dispatched, that element, where the event began rather
 * than the shadow host it reached the document by, and the event's error, or its
 * message where it carries no error. Null for an error that is the window's own, such as
 * an exception. A package may send a plain `Event` named `error`, which has neither.
 * @param {Event & Partial<ErrorEvent> & {[FAILURE]?: {element: Element, reason: unknown}}} event
 * @returns {{element: Element, reason: unknown} | null} */
export function failureOf(event) {
  if (event[FAILURE]) return event[FAILURE];
  const [origin] = event.composedPath();
  return origin instanceof Element
    ? { element: origin, reason: event.error ?? event.message }
    : null;
}

/** How a failure names its widget to the agent: by tag and id, since that is how the
 * agent finds it.
 * @param {Element} el */
export function failureContext(el) {
  const owner = widgetOf(el);
  return `<${owner.localName}${owner.id ? ` id="${owner.id}"` : ""}> failed`;
}

/** @param {Element} el */
const widgetOf = (el) => {
  let owner = el;
  while (owner.parentElement && !owner.localName.includes("-"))
    owner = owner.parentElement;
  return owner.localName.includes("-") ? owner : el;
};

// Where the box goes, in this order. An owner that keeps the nodes it drew through a
// failure places the box itself, beside them, rather than have them replaced by it:
// LeafElement and native renderers retain nodes no later draw would make again. Each
// element has one such placer, and registering again replaces it, so an owner may
// register on every connection. `place(box)` answers whether it placed the box; one that
// declines leaves it to the rest, and the owner removes the box once the failed content
// recovers. Next, a shadow host shows only what its stage holds, so the box stands
// there (`stagesFailure`, which only Leaf's shadow stage registers), and the widget's
// next stage replaces it. Otherwise the box replaces the element's children.
/** @type {WeakMap<Element, (box: HTMLDivElement) => boolean>} */
const placers = new WeakMap();
/** @param {Element} el @param {(box: HTMLDivElement) => boolean} place */
export const placesFailure = (el, place) => placers.set(el, place);
/** Whether an owner places `el`'s box already, which a host that would place it for an
 * element it drives asks first, so the element's own placer stands.
 * @param {Element} el */
export const failurePlaced = (el) => placers.has(el);
/** @type {WeakMap<Element, (box: HTMLDivElement) => boolean>} */
const stages = new WeakMap();
/** @param {Element} host @param {(box: HTMLDivElement) => boolean} place */
export const stagesFailure = (host, place) => stages.set(host, place);

/** Show `err` where `el` stands, with `source` beneath it when given, and dispatch
 * nothing.
 * @param {Element} el @param {unknown} err @param {string} [source] */
export function showFailure(el, err, source) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.textContent = `<${widgetOf(el).localName}> failed: ${describeFailure(err)}`;
  if (source) {
    const pre = document.createElement("pre");
    pre.textContent = source;
    box.append(pre);
  }
  if (placers.get(el)?.(box) || stages.get(el)?.(box)) return;
  const part = el._$litPart$;
  if (!part) {
    el.replaceChildren(box);
    return;
  }
  // A template drawn into the element owns its children, so the box becomes that
  // template's value, and the widget's next render replaces it as it replaces any value.
  // Setting it clears the template's own value, which disconnects its directives. Lit
  // keeps the part on the element under the name it pins for every copy of Lit to share,
  // and has no public way to set the part's value from outside a directive, so this sets
  // it as lit/directive-helpers.js's `setChildPartValue` does, by the name every
  // production build of Lit 3 gives the setter (`_$AI`; a development build keeps
  // `_$setValue`). Importing Lit's `render` instead would tie this module to one Lit.
  // A native draw may have taken the part's marker
  // since; the box stands after it, in the part's place.
  el.replaceChildren(part.startNode);
  (part._$AI ?? part._$setValue).call(part, box);
}
