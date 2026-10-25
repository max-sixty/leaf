/* A widget that draws what it reads: the one paint route of a `LeafElement`.

   A module subclasses `LeafElement` and draws in `render()`, as any `LitElement` does,
   into the element itself unless `createRenderRoot()` names a part it generated.
   `render()` reads whatever it shows through readers: the widget's own reading
   (`this.reading`, `this.state`), a bound data source (`this.data(input)`), obligations,
   reports, work, the time (`ago`, `clockValue`). Every reader it calls synchronously is
   tracked by Lit's Preact SignalWatcher. Lit's reactive properties update it too,
   for state the widget keeps itself. Presentation readiness (`reportsReady`) instead
   waits once for prerequisites to finish, then requests an unclaimed update: claiming
   a new presentation for readiness would invalidate the proof it just received.

   The element owns one presentation region: its widget's render region when the
   registry declares it a widget, so startup, thread readers, gesture release and report
   narration wait on it as they did on the controller's, and otherwise a region of its
   own. A move claims that region synchronously, inside the publication that made it,
   and the next update that draws settles the claim once all of it, `updated` included,
   has run; a claim no update can draw yet stays open until one does. An update that
   throws anywhere settles it with the fail-soft box, which stands at the end of the
   render root after what the element drew, since a render may paint retained nodes no
   later draw would make again and nothing drawn moves for it; the next update that
   draws takes the box away. One no
   claim waits on, such as a mechanical redraw, reports and shows its failure the same
   way, and so does a failed preparation (`present()`) or a module's own
   `failSoft(this, …)`. A `setup()` that throws shows its failure, and the element draws
   nothing after it. A move draws in the presentation pass the publication starts,
   parents first and every widget before the document-wide renderers
   (`queueWidgetUpdate`, semantic-state.js): a suggestion measures the slot it folds
   before the layer marks it retired.

   Its readers are followed while it stands (`watchOwner`, arrivals.js), and it draws
   nothing while away. A return requests a Lit update to reconnect its dependencies
   and draw the current reading; unchanged template parts keep their nodes. It claims
   its region on every return, so a returning widget never leaves its epoch waiting. A widget whose reading lacks a declared verb, as a revision's
   replacement does before its document is adopted, draws nothing until it has them all
   (before the first state read, the authored state supplies every verb); its claim
   settles with nothing drawn. While its controller's `defer()` holds it, its claim stays
   open; the release draws the newest reading at once, changed or not, since the gesture
   may have rewritten its nodes. An element whose tag declares `x-data` holds the page's data
   version while it stands, until it has drawn what was delivered, and any drawing that
   draw held it for, such as highlighting or a loading frame, has landed: what
   `updateComplete` waits for, which a widget extends by overriding
   `getUpdateComplete`, as any Lit element does (the prototype keeps `drawing()` for
   the widgets not yet moved). Lit's own completion, without that extension, is what
   dependent DOM readers wait for (`#committed`).
   `setup()` runs once, on the first connection, before the first render.

   Bound values. An x-data input that names a `property` reaches the widget as a
   plain property: before each render that the input's delivery moves, this element
   sets `this[property]` to the delivered value, or null while the source has none,
   so the widget reads `this.value` as it would anywhere else a host sets it. The
   widget marks the items it drew with plain attributes (projection/data.js) and
   dispatches a `drawn` event whose detail maps the property to the value it drew.
   This element keeps the last few values it set with the snapshot that supplied
   each, so a draw that finishes after a newer value arrived is still stamped with
   the revision it drew, and validates the marks there. Off a Leaf page no one
   listens, and the marks mean nothing. The prototype binds one property per widget,
   since a seat's stamp carries one source and revision. */
import {
  LitElement,
  SignalWatcher,
  render,
  untracked,
} from "/vendor/browser-runtime.js";
import {
  attachApplicationPresentation,
  attachWidgetPresentation,
  queueWidgetUpdate,
  watchPresentation,
} from "./semantic-state.js";
import { widgetDescriptor } from "./widget-descriptors.js";
import { drawsItself, widgetController, widgetMounted } from "./widget-controller.js";
import {
  failSoft,
  failSoftUnreported,
  once,
  placesFailure,
  reportFailure,
} from "./widget-upgrade.js";
import { watchOwner } from "./arrivals.js";
import { paintKeysWithin } from "./keyboard/scopes.js";
import { dataReader, joinDataDelivery } from "./data.js";
import { registry } from "./registry.js";
import { projectMarked } from "./projection/data.js";

// How many values set on one bound property a `drawn` can still name. A draw names
// the value it started from, which a widget abandons once a newer one arrives, so
// only the last few can still finish.
const DRAWABLE = 8;

let regions = 0;

// Keep failures inside SignalWatcher's effect so its dependency subscription survives.
class UpdateBoundary extends LitElement {
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

export class LeafElement extends SignalWatcher(UpdateBoundary) {
  #signalError = null;
  #stopReadiness = null;
  signalUpdateFailed(error) {
    this.#signalError = { error };
  }

  requestUpdate(...args) {
    const wasPending = this.isUpdatePending;
    const result = super.requestUpdate(...args);
    // Lit owns change detection and coalescing. A request made during render can
    // belong to the active update; one made after Lit clears its pending flag, as
    // in updated(), schedules a new update and needs its own claim. The first
    // constructor request precedes this class's private fields.
    if (this.hasUpdated && this.isUpdatePending && (!wasPending || !this.#updating))
      untracked(() => {
        if (this.#connected && this.#region && !this.#ticket)
          this.#ticket = this.#claim();
      });
    return result;
  }

  /** Finish this render when its presentation prerequisites are ready. Readiness
   * does not claim another presentation, which would invalidate its own proof. */
  whenReady(read) {
    if (untracked(read)) return true;
    if (!this.#stopReadiness) {
      this.#stopReadiness = watchPresentation(() => {
        if (!untracked(read)) return;
        this.#stopReadiness?.();
        this.#stopReadiness = null;
        super.requestUpdate();
      });
    }
    return false;
  }

  #descriptor = null;
  #controller = null;
  #verbs = [];
  #region = null;
  #regionName = null;
  #connected = false;
  #connectedParent = null;
  // The open claim the next update that draws settles.
  #ticket = null;
  #held = false;
  // The fail-soft box standing until the next update that draws; a `setup()` that threw
  // leaves the element broken, drawing nothing.
  #box = null;
  #broken = false;
  // The claim the update under way draws, settled once `updated` has run too.
  #drawing = null;
  #updating = false;
  // The drawing that follows the update under way, which its claim waits for.
  #work = null;
  #data = new Map();
  #leaveData = null;
  #scheduled = null;
  // The x-data inputs the registry binds to a property, `{input, property}`.
  #bound = [];
  // Each bound property's values as set, newest last, with the snapshot that supplied
  // each, so a `drawn` naming a value finds the revision it came from.
  #sent = new Map();

  createRenderRoot() {
    return this;
  }

  scheduleUpdate() {
    return this.#scheduled ?? this.#queueUpdate();
  }

  // Lit's own completion of the update's DOM, without the drawing a widget's
  // `getUpdateComplete` adds: what a nested widget or a document renderer waits for
  // is the committed DOM, never the widget's later preparation.
  #committed() {
    return super.getUpdateComplete();
  }

  #queueUpdate() {
    if (!this.#descriptor) return super.scheduleUpdate();
    const scheduled = queueWidgetUpdate(
      this.#descriptor.id,
      () => {
        if (this.#scheduled !== scheduled) return;
        this.#scheduled = null;
        return super.scheduleUpdate();
      },
      () => this.#committed(),
    );
    this.#scheduled = scheduled;
    return scheduled;
  }

  connectedCallback() {
    if (once(this)) this.#setup();
    super.connectedCallback();
  }

  #setup() {
    this.#descriptor = widgetDescriptor(this);
    if (this.#descriptor) {
      this.#controller = widgetController(this);
      drawsItself(this, {
        hold: () => this.#hold(),
        refresh: () => this.#refresh(),
      });
      this.#verbs = Object.keys(this.#descriptor.declaration["x-state"] ?? {});
    }
    this.#regionName = this.#descriptor
      ? null
      : `element:${this.localName}#${this.id}:${++regions}`;
    this.#bound = Object.entries(registry[this.localName]?.["x-data"] ?? {}).flatMap(
      ([input, { property }]) => (property ? [{ input, property }] : []),
    );
    if (this.#bound.length)
      this.addEventListener("drawn", (event) => {
        if (event.target === this)
          this.#drawn(/** @type {CustomEvent} */ (event).detail);
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
    // The element is an owner of its own: a paint that mounts it connects it inside that
    // paint, and what it reads to connect is its own to follow, never that paint's.
    watchOwner(this, {
      connect: () => untracked(() => this.#connect()),
      disconnect: () => this.#disconnect(),
    });
  }

  /** The module's one-time build, on the first connection, before the first render. */
  setup() {}

  /** The widget's complete reading (`widgetController(this).read()`), collected; null
   *  for an element the registry does not declare a widget, such as a quoted one. */
  get reading() {
    return this.#controller?.read() ?? null;
  }

  /** The widget's state, with every admitted and unresolved record folded in. */
  get state() {
    return this.reading.state;
  }

  /** The widget's controller, for `dispatch` and `present`. */
  get controller() {
    return this.#controller;
  }

  /** The bound reading of a declared `x-data` input, one copy a delivery (data.js). */
  data(input) {
    let read = this.#data.get(input);
    if (!read)
      this.#data.set(input, (read = dataReader(this, input, () => this.#stage())));
    return read();
  }

  // Set each bound property to the value its input delivers, before the render that
  // reads it. Reading the input here follows it as `render()` reading it would.
  willUpdate(changed) {
    super.willUpdate(changed);
    for (const { input, property } of this.#bound) {
      const snapshot = this.data(input);
      const sent = this.#sent.get(property) ?? [];
      if (sent.length && sent.at(-1).snapshot === snapshot) continue;
      const value = snapshot ? snapshot.value : null;
      sent.push({ value, snapshot });
      if (sent.length > DRAWABLE) sent.shift();
      this.#sent.set(property, sent);
      this[property] = value;
    }
  }

  // The widget reports the value it drew, by the property it read it from, once its
  // marks for that drawing stand. A seat carries one source and revision, so one bound
  // property supplies them.
  #drawn(detail) {
    try {
      const [{ property }] = this.#bound;
      if (!detail || !Object.hasOwn(detail, property))
        throw new Error(
          `<${this.localName}> drawn must carry the ${property} it drew in its detail`,
        );
      // The newest snapshot carrying that value: a draw that finishes after a newer
      // value arrived is stamped with the revision it drew. Equal values share a
      // revision, which digests the value.
      const entry = (this.#sent.get(property) ?? []).findLast(
        (entry) => entry.value === detail[property],
      );
      if (!entry)
        throw new Error(
          `<${this.localName} id=${this.id}> drew a ${property} Leaf did not set`,
        );
      projectMarked(this, entry.snapshot);
    } catch (error) {
      failSoft(this, error);
    }
  }

  // The controller's `defer` for this widget, which refuses a second hold and releases
  // once: hold its presentation through a gesture that rewrites its nodes; the release
  // draws the newest reading at once.
  #hold() {
    this.#held = true;
    return () => {
      this.#held = false;
      this.#refresh();
    };
  }

  #complete() {
    if (!this.#controller) return true;
    const { state } = this.#controller.read();
    return this.#verbs.every((verb) => verb in state);
  }

  shouldUpdate(changed) {
    // A draw queued as the element left waits for its return, whether or not the arrival
    // batch has told it yet.
    if (!this.#connected || !this.isConnected) {
      return false;
    }
    if (this.#held) return false;
    // The claim this update draws, from its gate on; one its own reads claim while it
    // runs is the next's. An update that draws nothing settles it all the same.
    this.#drawing = this.#ticket;
    this.#ticket = null;
    if (this.#broken) return false;
    if (!this.#complete()) return false;
    return super.shouldUpdate(changed);
  }

  update(changed) {
    super.update(changed);
    this.#box?.remove();
    this.#box = null;
  }

  // An update settles its claim once all of it has run, `updated` included, and one
  // that failed anywhere, its gate too, reports once and shows its failure; Lit has
  // marked it done, so the next move draws again. A draw that `updated` asks for at
  // once, as a module's own paint may, settles its own claim inside this one; with no
  // claim of its own, its failure is the enclosing claimed update's.
  performUpdate() {
    const outer = this.#drawing;
    const updating = this.#updating;
    let outerWork = this.#work;
    this.#drawing = null;
    this.#work = null;
    this.#updating = true;
    try {
      this.#signalError = null;
      super.performUpdate();
      if (this.#signalError) throw this.#signalError.error;
      const work = this.#work;
      // Drawing an update with no claim of its own holds goes to the claim enclosing
      // it, or else claims the region, as a retry's or a follow-up draw's does.
      if (work && !this.#drawing) {
        if (outer) outerWork = outerWork ? Promise.all([outerWork, work]) : work;
        else if (this.#region) this.#drawing = this.#claim();
      }
      // The claim settles once the update completes as the element tells it: Lit's
      // `updateComplete`, which a widget whose drawing finishes later extends by
      // overriding `getUpdateComplete`.
      if (this.#drawing) {
        const complete = this.updateComplete.then(() => undefined);
        this.#drawing.resolve(work ? Promise.all([work, complete]) : complete);
      }
    } catch (error) {
      if (outer && !this.#drawing) throw error;
      this.#failed(error, this.#drawing);
    } finally {
      this.#drawing = outer;
      this.#work = outerWork;
      this.#updating = updating;
    }
  }

  /** Hold the update under way's claim until `work`, drawing that follows the render
   *  asynchronously, lands: highlighting a document, say. An update no move claimed
   *  claims the region for it. The widget's presentation, and the data version a
   *  delivery it draws holds, wait for it. Call it from `render()` or `updated()`. */
  drawing(work) {
    // A failure names the widget; the claim it rejects reports nothing again.
    const named = Promise.resolve(work).catch((error) => {
      reportFailure(this, error);
      throw error;
    });
    this.#work = this.#work ? Promise.all([this.#work, named]) : named;
  }

  /** The render drawn again at once, outside any claim and Lit's own schedule, with a
   *  failure thrown rather than shown: the render check's replay
   *  (render-checks/replay.js), which holds a draw of the same reading to change
   *  nothing. `updated()` does not run, since what follows a draw may start
   *  preparation that would claim the widget's presentation and land after the check
   *  reads the page. An update Lit has queued stays queued, with its claim. */
  redraw() {
    render(this.render(), this.renderRoot, this.renderOptions);
  }

  updated(changed) {
    super.updated(changed);
    // The render may have changed what this widget's commands read from its nodes.
    untracked(() => paintKeysWithin(this));
  }

  // Every failure is reported here, naming the widget; a claim's rejection then shows
  // the box through the coordinator's fallback, which reports nothing again.
  #failed(error, ticket) {
    if (!ticket) return failSoft(this, error);
    reportFailure(this, error);
    ticket.reject(error);
  }

  // A claim on the region for the reading as it stands, which a failure settles with
  // the fail-soft box.
  #claim() {
    return this.#region.present(
      untracked(() => this.#controller?.read() ?? {}),
      (reason) => failSoftUnreported(this, reason),
    );
  }

  // Claim the region for a reading that draws later, leaving the claim open.
  #stage() {
    if (!this.#connected || this.#ticket || !this.#region) return;
    this.#ticket = this.#claim();
  }

  // Claim the region for the reading as it stands, and draw it on the next update; a
  // claim the next update cannot draw stays open until one does.
  #present({ now = false } = {}) {
    if (!this.#region) return;
    this.#ticket = this.#claim();
    if (this.#held) return;
    this.requestUpdate();
    if (now) {
      this.#scheduled = null;
      this.performUpdate();
    } else if (this.#descriptor) this.#queueUpdate();
  }

  #refresh() {
    if (this.#connected) this.#present({ now: true });
  }

  #connect() {
    this.#connected = true;
    this.#region = this.#descriptor
      ? attachWidgetPresentation(this.#descriptor.id, "render", this)
      : attachApplicationPresentation(this.#regionName, this);
    const parentChanged = this.#connectedParent !== this.parentElement;
    this.#connectedParent = this.parentElement;
    if (registry[this.localName]?.["x-data"])
      this.#leaveData = joinDataDelivery(
        this.#descriptor ? `widget:${this.#descriptor.id}:render` : this.#regionName,
      );
    this.#present();
    if (this.#descriptor) widgetMounted(this, this.#descriptor, parentChanged);
  }

  #disconnect() {
    this.#connected = false;
    this.#stopReadiness?.();
    this.#stopReadiness = null;
    this.#leaveData?.();
    this.#leaveData = null;
    this.#ticket = null;
    this.#region?.disconnect();
    this.#region = null;
  }
}
