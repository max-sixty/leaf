/* A widget that draws what it reads, as a Lit element on the protocol any custom
   element has with its host: properties in, events out, and nothing asked of Leaf.

   A module subclasses `LeafElement` and draws in `render()`, as any `LitElement` does,
   into the element itself, unless `createRenderRoot()` names a part it generated or
   the class says `static shadow = true`, which draws into an open shadow root.
   `render()` reads whatever it shows: `this.state`, the reading Leaf sets on a widget
   whose tag declares `verbs`, each bound input through the property Leaf sets
   (host/element-data.js, "Bound values"), Lit's reactive properties for state the widget
   keeps itself, and any signal-backed reader, such as obligations, reports, work or
   the time (`clockValue`). Every signal `render()` reads synchronously is
   tracked by Lit's Preact SignalWatcher, so the element draws again when one moves.

   What it says to its host, all of it events a plain element could dispatch:

   - `lf-connect`, each time it connects, before `setup()`. Leaf answers before the
     event returns: it dresses the element's open shadow root and makes the sets it
     can, each bound input and then `state`, so `setup()` reads them. Leaf cancels the
     event where it will set `state` on the element, and such an element draws nothing
     until `state` is set: Leaf sets nothing while it waits for a source nobody has
     read yet or for a revision's replacement to be adopted. An ancestor hears a
     descendant's `lf-connect` and draws again, since it may own the place of a part a
     renderer mounted anew.
   - `pending-task`, once for each update Lit schedules, made in the stack that asked
     for the update, with a promise that settles once `updateComplete` has: the page
     reads as presented only after the draw, and a set Leaf makes holds its claim on
     the drawing the set started. A widget whose drawing finishes after the render,
     such as highlighting or a loading frame, extends that by overriding
     `getUpdateComplete`, as any Lit element does.
   - `lf-commands`, after each draw, at its render root: the render may have changed
     what the keys declared in what it drew read from those nodes. A draw leaves what
     the page wrote beside a part it draws into as it was, such as a tab set's panels,
     so their keys aren't read again.
   - `lf-defer`, as `defer()` starts, with a promise that settles as the hold ends.
     A set Leaf makes meanwhile is not drawn, so the page counts it as presented only
     once the hold has ended and the release has drawn; and the gesture rewrote the
     element's nodes outside any draw, so Leaf reads the document again then.
   - `error`, for an update that throws anywhere (`failSoft`, failure.js). The
     fail-soft box stands at the end of the render root after what the element drew,
     since a render may paint retained nodes no later draw would make again and nothing
     drawn moves for it; the next update that draws takes the box away. A `setup()`
     that throws shows its failure, and the element draws nothing after it.
   - `lf-action` and `lf-undo`, through `record()` and `takeBack()`.

   It draws before the caller returns when Leaf sets its `state`, as a plain element
   draws in its setter, so a document-wide renderer that reads its nodes next finds
   them drawn. Every other update, its first, a signal or a reactive property moving, a
   return, an input Leaf set, runs on Lit's schedule.
   It draws nothing while away; a return requests a Lit update to reconnect its
   dependencies and draw the current reading, and unchanged template parts keep their
   nodes. While `defer()` holds it, it draws nothing; the release draws the newest
   reading at once, changed or not, since the gesture may have rewritten its nodes.
   `setup()` runs once, on the first connection, before the first render.

   Off a Leaf page nobody answers `lf-connect` or hears the rest, so `state` stays
   undefined and the element draws what its markup and its own properties give it. */
import { LitElement, render } from "/vendor/lit.js";
import { SignalWatcher, untracked } from "/vendor/signals-core.js";
import { COMMANDS, CONNECT, DeferEvent, sendGesture } from "./widget-events.js";
import { PendingTaskEvent } from "./pending-task.js";
import { failSoft, placesFailure } from "./failure.js";
import { once } from "./once.js";

// Keep failures inside SignalWatcher's effect so its dependency subscription survives.
class UpdateBoundary extends LitElement {
  /** @param {unknown} error */
  signalUpdateFailed(error) {
    throw error;
  }
  performUpdate() {
    try {
      super.performUpdate();
    } catch (error) {
      this.signalUpdateFailed(error);
    }
  }
}

/** @import { WidgetState } from "../../types/domain.js" */

export class LeafElement extends SignalWatcher(UpdateBoundary) {
  /** Whether the element draws into an open shadow root of its own. */
  static shadow = false;

  /** @type {{error?: unknown}} */
  #signalError = {};
  /** @param {unknown} error */
  signalUpdateFailed(error) {
    this.#signalError.error = error;
  }

  /** @type {WidgetState | undefined} */
  #state;
  // A host answered `lf-connect`: it sets `state`, and nothing draws before it has.
  #hosted = false;
  // It has been through its first update: from here a `state` Leaf sets is drawn at
  // once.
  #ready = false;
  // The hold a gesture has on drawing, settled as it releases.
  /** @type {PromiseWithResolvers<void> | null} */
  #hold = null;
  // The update Lit has pending is already announced.
  #announced = false;
  #updating = false;
  // The fail-soft box standing until the next update that draws; a `setup()` that threw
  // leaves the element broken, drawing nothing.
  /** @type {HTMLElement | null} */
  #box = null;
  #broken = false;

  /** The widget's reading as Leaf set it (`module-plain-elements.md`, "`state`"):
   *  each declared verb's state with every admitted and unresolved record folded in,
   *  whether the user may act on it now (`available`), the reason they may not where
   *  Leaf has one (`unavailable`), and whether `takeBack` would take its action in
   *  force back (`undoable`). An element whose tag declares no verb
   *  holds an empty one once Leaf has set its inputs. Undefined where no host set it:
   *  off a Leaf page, and for a widget the page did not capture, such as one with no
   *  id.
   *  @returns {WidgetState | undefined} */
  get state() {
    return this.#state;
  }
  /** @param {WidgetState | undefined} value */
  set state(value) {
    const old = this.#state;
    this.#state = value;
    this.requestUpdate("state", old);
    this.#drawNow();
  }

  /** @param {Parameters<LitElement["requestUpdate"]>} args */
  requestUpdate(...args) {
    const wasPending = this.isUpdatePending;
    const result = super.requestUpdate(...args);
    // Lit owns change detection and coalescing. A request made during render belongs
    // to the active update; one made after Lit clears its pending flag, as in
    // updated(), schedules a new update, announced in its turn. Lit's constructor
    // requests the first update before this class's private fields exist.
    if (
      #announced in this &&
      this.isConnected &&
      this.isUpdatePending &&
      (!wasPending || !this.#updating)
    )
      this.#announce();
    return result;
  }

  // Tell the host a draw is under way until the update Lit has pending is in. A
  // failure of that drawing shows and reports here, so the promise only settles.
  #announce() {
    if (this.#announced) return;
    this.#announced = true;
    untracked(() =>
      this.dispatchEvent(
        new PendingTaskEvent(
          this.updateComplete.then(
            () => undefined,
            (error) => failSoft(this, error),
          ),
        ),
      ),
    );
  }

  // Draw the pending update before the caller returns.
  #drawNow() {
    if (!this.#ready || !this.isConnected || this.#updating || !this.isUpdatePending)
      return;
    this.#announce();
    this.performUpdate();
  }

  /** @returns {HTMLElement | DocumentFragment} */
  createRenderRoot() {
    return /** @type {typeof LeafElement} */ (this.constructor).shadow
      ? super.createRenderRoot()
      : this;
  }

  connectedCallback() {
    // A paint that mounts the element connects it inside that paint, and what the
    // element reads to connect is its own to follow, never that paint's.
    untracked(() => {
      const first = once(this);
      // A shadow root exists before the host is asked, so the host can dress it.
      if (first && /** @type {typeof LeafElement} */ (this.constructor).shadow)
        Object.assign(this, { renderRoot: this.createRenderRoot() });
      const answered = !this.dispatchEvent(
        new Event(CONNECT, { bubbles: true, composed: true, cancelable: true }),
      );
      this.#hosted ||= answered;
      if (first) this.#setup();
      super.connectedCallback();
    });
  }

  #setup() {
    // A listener on a shadow host sees itself as the target of an event from inside
    // its root, so the element that connected is read off the path.
    this.addEventListener(CONNECT, (event) => {
      if (event.composedPath()[0] !== this && this.hasUpdated) this.requestUpdate();
    });
    placesFailure(this, (box) => {
      const root = this.renderRoot ?? this;
      // A widget showing a shadow stage over its host shows the box as that stage,
      // which its next stage replaces, as any shadow widget does.
      if (root === this && this.shadowRoot) return false;
      // The same failure again leaves the box that already says it.
      if (this.#box?.parentNode === root && this.#box.textContent === box.textContent)
        return true;
      this.#box?.remove();
      this.#box = box;
      // After what the element drew, so nothing it drew moves for the box.
      root.append(box);
      return true;
    });
    try {
      this.setup();
    } catch (error) {
      this.#broken = true;
      failSoft(this, error);
    }
  }

  /** The module's one-time build, on the first connection, before the first render. */
  setup() {}

  /** Record an action of the widget's own: an `lf-action` event Leaf sends, after
   *  which `this.state` already shows the result. Returns the event's `delivery`, a
   *  promise of the event the server admitted, or of `null` once it refuses and Leaf
   *  has set the server's state again; `null` at once where nothing records the
   *  action, as off a Leaf page or while it is not `available`. `attempt` names the
   *  draft the words were written in (a draft's `send`, widget-api.js's `draft`).
   *  @param {string} verb @param {Record<string, unknown>} detail
   *  @param {{says?: string, attempt?: string | null | undefined}} [options]
   *  @returns {Promise<unknown> | null} */
  record(verb, detail, { says, attempt } = {}) {
    return this.#send("lf-action", {
      verb,
      detail,
      ...(says && { says }),
      ...(attempt && { attempt }),
    });
  }

  /** Take back the action in force for a verb, or for one of its units: an `lf-undo`
   *  event. Returns as `record` does.
   *  @param {string} verb @param {string} [unit] */
  takeBack(verb, unit) {
    return this.#send("lf-undo", { verb, ...(unit !== undefined && { unit }) });
  }

  /** @param {"lf-action" | "lf-undo"} type @param {Record<string, unknown>} detail */
  #send(type, detail) {
    return sendGesture(this, type, detail);
  }

  /** Hold drawing through a gesture that rewrites the element's nodes, and return the
   *  release, which draws the newest reading at once. A second hold is refused, and a
   *  release acts once. */
  defer() {
    if (this.#hold) throw new Error("Widget presentation is already deferred");
    /** @type {PromiseWithResolvers<void>} */
    const hold = (this.#hold = Promise.withResolvers());
    this.dispatchEvent(new DeferEvent(hold.promise));
    return () => {
      if (this.#hold !== hold) return;
      this.#hold = null;
      hold.resolve();
      if (!this.isConnected) return;
      this.requestUpdate();
      this.#drawNow();
    };
  }

  /** @param {Parameters<LitElement["shouldUpdate"]>[0]} changed */
  shouldUpdate(changed) {
    // A draw queued as the element left waits for its return, which requests another.
    if (!this.isConnected || this.#hold || !this.#draws()) return false;
    return super.shouldUpdate(changed);
  }

  // Whether the element has a reading to draw: none after a `setup()` that threw, or
  // until the host that answered it has set its `state`.
  #draws() {
    return !this.#broken && !(this.#hosted && this.#state === undefined);
  }

  /** @param {Parameters<LitElement["update"]>[0]} changed */
  update(changed) {
    super.update(changed);
    this.#box?.remove();
    this.#box = null;
    // Said here, since a subclass overrides `updated()`: one that left out
    // `super.updated()` would draw and keep stale key hints, which nothing reports.
    const root = this.renderRoot;
    untracked(() =>
      (root instanceof Element ? root : this).dispatchEvent(
        new CustomEvent(COMMANDS, {
          bubbles: true,
          composed: true,
          detail: { within: true },
        }),
      ),
    );
  }

  // An update that fails anywhere, its gate and `updated` included, reports once and
  // shows its failure. Lit has marked it done, so the next move draws again.
  performUpdate() {
    if (!this.isUpdatePending) return;
    const updating = this.#updating;
    this.#updating = true;
    this.#announced = false;
    this.#ready = true;
    try {
      const boundary = (this.#signalError = {});
      super.performUpdate();
      if ("error" in boundary) throw boundary.error;
    } catch (error) {
      failSoft(this, error);
    } finally {
      this.#updating = updating;
    }
  }

  /** The render drawn again at once, outside Lit's own schedule, with a failure thrown
   *  rather than shown: the render check's replay (render-checks/replay.js), which
   *  reads this method off any element that has one and holds a draw of the same
   *  reading to change nothing. `updated()` does not run, since what follows a draw
   *  may start preparation that would land after the check reads the page. An update
   *  Lit has queued stays queued. An element with no reading to draw draws nothing
   *  here either, so one whose `setup()` threw keeps showing that failure. */
  redraw() {
    if (this.#draws()) render(this.render(), this.renderRoot, this.renderOptions);
  }
}
