/* The upgrade lifecycle every behavior module shares, in a form any document can load:
   it imports nothing Leaf composes into a page, so a widget built on it also runs on a
   plain HTML page that maps `/runtime/` with its own import map (portable-api.js).

   A module defines its custom element once and makes `connectedCallback` safe to run
   after reconnection, using `once(el)` for generated chrome so reconnecting does not
   duplicate it. A failed upgrade becomes a visible error box (`failSoft`) rather than
   a blank page.

   The widget tells its host what Leaf needs to hear through standard events on itself,
   which Leaf reads from outside and a plain page may ignore. A failure is an `error`
   ErrorEvent, bubbling and composed, which a Leaf page reports to the agent as the
   page's error, naming the widget (layer-client.js). Drawing still under way is a
   `pending-task` event (`PendingTaskEvent`), the Web Components Community Group's draft
   protocol for a component's asynchronous work, whose `complete` promise Leaf holds the
   widget's presentation on (widget-controller.js). An element that is not in a document
   when it dispatches either reaches no one. */
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";

const initialized = new WeakSet();

// One-shot guard for connectedCallback: re-connection (a parent wrapping or moving an
// already-upgraded child) must be harmless. A clone starts its own lifetime even when
// it copied the painted upgrade mark; that mark never owns initialization.
export function once(el) {
  if (initialized.has(el)) return false;
  initialized.add(el);
  if (!el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done))
    el.setAttribute(PAGE_PAINT_ATTRIBUTE.done, "1");
  return true;
}

// A data widget's body: the <pre> the content model requires, never the element's own
// textContent. The two used to be the same string and are not once the element holds a
// child — an HTML formatter is free to put the <pre> on its own line, and the newline
// and indent before it are the element's text too. Line one is load-bearing in every
// notation here, so that indent is not untidiness downstream: a diff's file header, a
// tree's root and a diagram's source type stop parsing, and a walkthrough's `hi` ranges
// and note anchors all point one line off.
export const dataBody = (el) => el.querySelector(":scope > pre").textContent;

// The body's text as a module reads its lines: leading blank lines and trailing
// whitespace are the <pre>'s layout, not lines. Notations whose whitespace is content,
// such as a diff or exact Markdown source, read `dataBody` instead.
export const bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();

// Drawing an element has under way, as the community protocol spells it: `complete`
// settles once the drawing is in, or the element shows why it could not draw.
export const PENDING_TASK = "pending-task";
export class PendingTaskEvent extends Event {
  constructor(complete) {
    super(PENDING_TASK, { bubbles: true, composed: true });
    this.complete = complete;
  }
}

// A failed upgrade becomes a visible error box rather than a blank page. A widget failure
// may failSoft its own element, or a part of it, so the rest of the page and Threads
// remain usable, but it does not convert a partial state read into a committed one. The
// box is where the user is looking; the agent that wrote the widget hears the same
// failure as the page's error, which is also what `page check` fails on wherever it
// runs the page.
export function failSoft(el, err, source) {
  reportFailure(el, err);
  showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`, source);
}

// The report alone, for a widget that shows a part's failure its own way, such as a
// diff file whose patch it cannot draw beside the files it can.
export function reportFailure(el, err) {
  el.dispatchEvent(
    new ErrorEvent("error", {
      error: err,
      message: err?.message ?? String(err),
      bubbles: true,
      composed: true,
    }),
  );
}

// How a failure names its widget to the agent: by tag and id, since that is how the
// agent finds it.
export function failureContext(el) {
  const owner = widgetOf(el);
  return `<${owner.localName}${owner.id ? ` id="${owner.id}"` : ""}> failed`;
}

// The box alone, for the presentation coordinator's fallback: the coordinator reports
// any failure it falls back from that no paint reported, so this path reports nothing.
export function failSoftUnreported(el, err) {
  showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`);
}

const widgetOf = (el) => {
  let owner = el;
  while (owner.parentElement && !owner.localName.includes("-"))
    owner = owner.parentElement;
  return owner.localName.includes("-") ? owner : el;
};

// An owner that keeps the nodes it drew through a failure places the box itself, beside
// them, rather than have them replaced by it: LeafElement and native renderers retain
// nodes no later draw would make again, and a shadow stage shows only what it holds
// (shadow-stage.js). Each placer answers whether it placed the box, in the order the
// owners took the element on, so an owner can leave a case to the next. With none
// placing it, the box replaces the element's children, and the widget's next draw of
// them replaces the box.
const placers = new WeakMap();
export const placesFailure = (el, place) =>
  placers.set(el, [...(placers.get(el) ?? []), place]);

function showFailure(el, text, source) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.textContent = text;
  if (source) {
    const pre = document.createElement("pre");
    pre.textContent = source;
    box.append(pre);
  }
  if (placers.get(el)?.some((place) => place(box))) return;
  releaseTemplate(el);
  el.replaceChildren(box);
}

// End a template's ownership of `el`, whose nodes the box replaces: Lit's public
// RootPart.setConnected(false) disconnects its directives, but render() has no public
// reset, so its pinned, deliberately unminified cache key goes too, and a template
// drawn there again starts afresh, after the box.
function releaseTemplate(el) {
  const part = el._$litPart$;
  if (!part) return;
  part.setConnected(false);
  delete el._$litPart$;
}
