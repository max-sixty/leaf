/* The upgrade lifecycle every behavior module shares, in a form any document can load:
   it imports nothing Leaf composes into a page, so a widget built on it also runs on a
   plain HTML page that maps `/runtime/` with its own import map (portable-api.js).

   A module defines its custom element once and makes `connectedCallback` safe to run
   after reconnection, using `once(el)` for generated chrome so reconnecting does not
   duplicate it. A failed upgrade becomes a visible error box (`failSoft`) rather than
   a blank page.

   The widget tells its host what Leaf needs to hear through standard events, which Leaf
   reads from outside and a plain page may ignore. A failure is an `error` ErrorEvent,
   bubbling and composed, which a Leaf page reports to the agent as the page's error,
   naming the widget (layer-client.js, `failureOf`). Drawing still under way is a
   `pending-task` event (`PendingTaskEvent`), the Web Components Community Group's draft
   protocol for a component's asynchronous work, whose `complete` promise Leaf holds the
   widget's presentation on (widget-controller.js). A rearrangement inside an unchanged
   box is `lf-layout` (`layoutChanged`), which the readers that measure what a widget
   holds hear. And the keys an element binds are data on it, `lfCommands`, which the
   widget says it set or changed with `lf-commands` (`commandsChanged`): Leaf reads them
   then and binds them (keyboard/scopes.js), and a plain page, reading nothing, binds no
   key and advertises none. Words for a listener are `lf-announce` (`announce`), which a
   Leaf page says in its live region (notifications.js) and a plain page leaves unsaid. */
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

// ResizeObserver covers size changes. A view swap can instead keep its outer box while
// rearranging descendants, so the widget states that geometry change explicitly, and
// geometry readers listen for it instead of watching every DOM mutation.
export const LAYOUT = "lf-layout";
export const layoutChanged = (el) => {
  el.dispatchEvent(new CustomEvent(LAYOUT, { bubbles: true, composed: true }));
};

// That an element's `lfCommands`, or anything its rows read, changed. An element out of
// the document, such as a control built before it is placed, has no way out to the
// window, so its event is dispatched there directly, carrying the element, as a failure's
// is (`reportFailure`). A declaration Leaf refuses throws here, where the widget made
// it, since a listener's exception never reaches the dispatcher.
export const COMMANDS = "lf-commands";
const CHANGED = Symbol("element whose commands changed");
const REFUSED = Symbol("why Leaf refused the declaration");
export function commandsChanged(el) {
  const event = new Event(COMMANDS, { bubbles: true, composed: true });
  event[CHANGED] = el;
  (el.isConnected ? el : window).dispatchEvent(event);
  if (event[REFUSED]) throw event[REFUSED];
}
// Words a listener should hear now, such as where a step put the reader: an
// `lf-announce` event on the window carrying them as its `detail`. Leaf says them in the
// page's live region; a page without Leaf hears nothing unless it listens.
export const ANNOUNCE = "lf-announce";
export const announce = (words) =>
  window.dispatchEvent(new CustomEvent(ANNOUNCE, { detail: words }));

// The element a `commandsChanged` event names, and the refusal its reader hands back.
export const commandsChangedOn = (event) => event[CHANGED];
export const refuseCommands = (event, error) => {
  event[REFUSED] = error;
};

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
// diff file whose patch it cannot draw beside the files it can. It is dispatched on the
// element, so it reaches the element's listeners and, through the document, the
// window's; an element out of the document, such as a cached message body while its
// thread is shut, has no way out to the window, so its failure is dispatched there
// directly. Every listener gets an Error: a reason thrown as something else is wrapped,
// and Leaf reports the reason as thrown.
export function reportFailure(el, err) {
  const event = new ErrorEvent("error", {
    error: err instanceof Error ? err : siteless(err),
    message: err?.message ?? String(err),
    bubbles: true,
    composed: true,
  });
  event[FAILURE] = { element: el, reason: err };
  (el.isConnected ? el : window).dispatchEvent(event);
}

// The element and reason a failure event of `reportFailure`'s carries.
const FAILURE = Symbol("failure");

// An Error for a reason thrown as something else, with no stack: its site would be the
// line here rather than the failure's (`exceptionText`, layer-client.js).
const siteless = (reason) =>
  Object.assign(Object.create(Error.prototype), { message: String(reason) });

// The failure an `error` event reports, as Leaf reads it: the element and reason
// `reportFailure` gave it, or, for one another element dispatched, that element, where
// the event began rather than the shadow host it reached the document by, and the
// event's error. Null for an error that is the window's own, such as an exception.
export function failureOf(event) {
  if (event[FAILURE]) return event[FAILURE];
  const [origin] = event.composedPath();
  return origin instanceof Element ? { element: origin, reason: event.error } : null;
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

// Where the box goes, in this order. An owner that keeps the nodes it drew through a
// failure places the box itself, beside them, rather than have them replaced by it:
// LeafElement and native renderers retain nodes no later draw would make again. Each
// element has one such placer, and registering again replaces it, so an owner may
// register on every connection. `place(box)` answers whether it placed the box; one that
// declines leaves it to the rest. Next, a shadow host shows only what its stage holds,
// so the box stands there (`stagesFailure`, which only shadow-stage.js registers), and
// the widget's next stage replaces it. Otherwise the box replaces the element's
// children, and the widget's next draw of them replaces the box, a template's included.
const placers = new WeakMap();
export const placesFailure = (el, place) => placers.set(el, place);
const stages = new WeakMap();
export const stagesFailure = (host, place) => stages.set(host, place);

function showFailure(el, text, source) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.textContent = text;
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
