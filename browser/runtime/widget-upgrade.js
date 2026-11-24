/* The events with which a widget tells its host what Leaf needs to hear, by name. The
   module imports nothing Leaf composes into a page, so `LeafElement`
   (leaf-element.js), which dispatches them, loads in a plain HTML page that maps
   `/runtime/` with its own import map too (portable-api.js).

   Leaf reads each event from outside, and a plain page may ignore it. That the widget
   has connected and wants what its host sets on it is `lf-connect` (`CONNECT`), a hold
   it has on its own drawing is `lf-defer` (`DeferEvent`), and the user's hold on
   something in it is `lf-hold` (`HOLD`). A failure is an `error` event
   (lib/failure.js), and drawing still under way a `pending-task` event
   (lib/pending-task.js). A rearrangement inside an unchanged box is `lf-layout`
   (`LAYOUT`), which the readers that measure what a widget holds hear. And the keys an
   element binds are data on it, `lfCommands`, which the widget says it set or changed
   with `lf-commands` (`COMMANDS`): Leaf reads them then and binds them
   (keyboard/scopes.js), and a plain page, reading nothing, binds no key and advertises
   none. Words for a listener are `lf-announce` on the window, which a
   Leaf page says in its live region (notifications.js) and a plain page leaves unsaid.
   Words telling the user that something they did has not taken are `lf-error` on the
   window, which a Leaf page keeps in its Errors list (errors.js).
   What pointing at an element reads is data on it too, `lfPreview`, and the widget says
   when that changes with `lf-preview`, as the user's aim moves from
   one of a chart's points to the next, or a grip's words stop being true once its card
   is grabbed: Leaf reads it again (preview.js). Leaf says at the element when that
   preview has gone (`lf-preview-ended`), so a mark the widget drew for it comes off. */
import { version } from "./kept.js";

// That an element has connected and wants what its host sets on it now: a bubbling,
// composed event the element dispatches from `connectedCallback`. A Leaf page answers
// before `dispatchEvent` returns (element-integration.js): it dresses the element's open
// shadow root and makes the sets it can, each bound input and then `state`. It
// cancels the event where it will set `state`, at once or once it has everything the
// element draws from. Without the event Leaf makes the same sets once it sees the
// element arrive, a microtask later.
export const CONNECT = "lf-connect";

// A hold an element has on its own drawing while it rewrites its nodes itself, such
// as through a drag that moves them or an edit in place: `complete` settles as the hold
// ends. A Leaf page counts what it set meanwhile as drawn only then, and reads the
// document again (widget-controller.js), since the element changed its nodes outside
// any draw. It keeps no revision or undo waiting, which `lf-hold` does.
export const DEFER = "lf-defer";
export class DeferEvent extends Event {
  /** @param {PromiseLike<unknown>} complete */
  constructor(complete) {
    super(DEFER, { bubbles: true, composed: true });
    this.complete = complete;
  }
}

// A hold the user has on something in an element, as through a drag, a keyboard grab or
// a scrub: a bubbling, composed event the element dispatches as the hold starts, whose
// `complete` property is a promise it settles as the hold ends. While it stands a Leaf
// page applies no revision and takes nothing back (widget-elements.js, `dragHeld`), so
// nothing replaces the nodes under the user's hand. It says nothing of the element's
// drawing, which `lf-defer` holds.
export const HOLD = "lf-hold";

// ResizeObserver covers size changes. A view swap can instead keep its outer box while
// rearranging descendants, so the widget states that geometry change explicitly, with a
// bubbling, composed event on the element whose parts moved, and geometry readers
// listen for it instead of watching every DOM mutation. A thread pass, which asks a
// widget that seats threads for its outlets again, follows the event and no resize
// (anchor-controls.js), so such a widget says it after any change in the data it shows.
export const LAYOUT = "lf-layout";
// How many times an element in the page has said its layout changed, which a reader of
// what widgets draw that the page's reading doesn't hear reads (kept.js, `version`).
// The count is taken as the event starts down from the window, so it has moved before
// any listener the event reaches reads it.
const layouts = version();
export const layoutsChanged = () => layouts.read();
addEventListener(LAYOUT, () => layouts.move(), { capture: true });
/** Say `el`'s layout changed, as Leaf says for an element it drives.
 * @param {Element} el */
export const layoutChanged = (el) =>
  void el.dispatchEvent(new CustomEvent(LAYOUT, { bubbles: true, composed: true }));

// That what pointing at an element reads, its `lfPreview`, changed: a composed
// CustomEvent the widget dispatches at the element. `detail.aim` true says the user
// aimed at something new inside the element, as a chart's pointer or key reaching
// another point, which shows its preview whatever put the last one away, on the side a
// standing one stood, where a redraw of the same reading shows nothing new.
export const PREVIEW = "lf-preview";
// That the preview Leaf showed of an element has gone, a `CustomEvent` dispatched at
// that element alone whose `detail.declared` is what its `lfPreview` returned for the
// reading that ended (preview.js): a mark the widget drew for that reading, as a chart's
// ring on its point, comes off then, and one for a reading declared since stays.
export const PREVIEW_ENDED = "lf-preview-ended";
// That an element's `lfCommands`, or anything its rows read, changed: a bubbling,
// composed CustomEvent the element dispatches on itself while it stands in the page,
// since nothing hears one from an element out of it. `detail.within` true says the
// element drew, so the keys declared on it and on anything under it may read differently
// from the nodes it drew, where the plain form speaks for the element's own rows alone.
// Leaf reads the element the event began at (keyboard/scopes.js).
export const COMMANDS = "lf-commands";
// Words a listener should hear now, such as where a step put the reader: a widget
// dispatches an `lf-announce` CustomEvent on the window carrying them as its `detail`.
// Leaf says them in the page's live region; a page without Leaf hears nothing unless it
// listens.
export const ANNOUNCE = "lf-announce";
