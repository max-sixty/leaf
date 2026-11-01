/* A widget that draws what it reads: the one paint route of a `LeafElement`.

   A module subclasses `LeafElement` and draws in `render()`, as any `LitElement` does,
   into its staged shadow root when the registry declares `x-shadow`, otherwise the
   element itself, unless `createRenderRoot()` names a part it generated.
   `render()` reads whatever it shows through readers: the widget's own reading
   (`this.reading`, `this.state`), obligations, reports, work, the time (`ago`,
   `clockValue`), and a bound data source through the property Leaf sets ("Bound
   values"). Every reader it calls synchronously is
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
   nothing after it. A move draws in the presentation pass the
   publication starts, parents first and every widget before the document-wide renderers
   (`queueWidgetUpdate`, semantic-state.js): a suggestion measures the slot it folds
   before the layer marks it retired.

   Its readers are followed while it stands (`watchOwner`, arrivals.js), and it draws
   nothing while away. A return requests a Lit update to reconnect its dependencies
   and draw the current reading; unchanged template parts keep their nodes. It claims
   its region on every return, so a returning widget never leaves its epoch waiting. A widget whose reading lacks a declared verb, as a revision's
   replacement does before its document is adopted, draws nothing until it has them all
   (before the first state read, the authored state supplies every verb); its claim
   settles with nothing drawn. One bound to a page data source likewise draws nothing
   until the page has delivered its data (`awaitsData`, data.js), so it never draws the
   empty reading of a source nobody has read yet; the theme's first-paint box stands
   until then. While its controller's `defer()` holds it, its claim stays
   open; the release draws the newest reading at once, changed or not, since the gesture
   may have rewritten its nodes. An update's claim settles once `updateComplete` does,
   which a widget whose drawing finishes after the render, such as highlighting or a
   loading frame, extends by overriding `getUpdateComplete`, as any Lit element does;
   a rejection there is the update's failure. So an element whose tag declares `x-data`
   holds the page's data version while it stands, until it has drawn what was
   delivered and finished that drawing. Lit's own completion, without the extension, is
   what dependent DOM readers wait for (`#committed`).
   `setup()` runs once, on the first connection, before the first render.

   Leaf's bound-value integration lives in element-data.js. It initializes authored
   inputs before setup, delivers values before the update gate, and stamps the marks
   a widget reports through its ordinary `drawn` event. Objects and primitives keep
   the snapshot that supplied the drawing, including one completed after a newer
   delivery. This lifecycle owns when those operations run, not their data meaning. */
import { LitElement, SignalWatcher, render, untracked } from "/runtime/framework.js";
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
import { ElementData } from "./element-data.js";
import { registry } from "./registry.js";
import { adoptShadowStage } from "./shadow-stage.js";

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
  #leaveData = null;
  #scheduled = null;
  #data = null;

  createRenderRoot() {
    return registry[this.localName]?.["x-shadow"]
      ? adoptShadowStage(super.createRenderRoot())
      : this;
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
    this.#data = new ElementData(this, () => this.#stage());
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
      this.#data.initialize();
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
    // runs is the next's. Before the first successful draw, Lit can retry a skipped
    // update without requestUpdate claiming it. Every connected update owns a claim,
    // including one that draws nothing and settles immediately.
    this.#drawing = this.#ticket ?? this.#claim();
    this.#ticket = null;
    if (!this.#draws()) return false;
    this.#data.deliver();
    return super.shouldUpdate(changed);
  }

  // Whether the element has a reading to draw: none after a `setup()` that threw,
  // while its reading lacks a declared verb, or while its data is undelivered.
  #draws() {
    return !this.#broken && this.#complete() && !this.#data.awaitsDelivery();
  }

  update(changed) {
    super.update(changed);
    this.#box?.remove();
    this.#box = null;
  }

  // An update settles its claim once all of it has run, `updated` included, and its
  // `updateComplete` has resolved; one that failed anywhere, its gate and that
  // completion too, reports once and shows its failure. Lit has marked it done, so the
  // next move draws again. A draw that `updated` asks for at once, as a module's own
  // paint may, settles its own claim inside this one; with no claim of its own, its
  // failure is the enclosing claimed update's.
  performUpdate() {
    const outer = this.#drawing;
    const updating = this.#updating;
    this.#drawing = null;
    this.#updating = true;
    try {
      this.#signalError = null;
      super.performUpdate();
      if (this.#signalError) throw this.#signalError.error;
      if (this.#drawing)
        // A failure names the widget; the claim it rejects reports nothing again.
        this.#drawing.resolve(
          this.updateComplete.then(
            () => undefined,
            (error) => {
              reportFailure(this, error);
              throw error;
            },
          ),
        );
    } catch (error) {
      if (outer && !this.#drawing) throw error;
      this.#failed(error, this.#drawing);
    } finally {
      this.#drawing = outer;
      this.#updating = updating;
    }
  }

  /** The render drawn again at once, outside any claim and Lit's own schedule, with a
   *  failure thrown rather than shown: the render check's replay
   *  (render-checks/replay.js), which holds a draw of the same reading to change
   *  nothing. `updated()` does not run, since what follows a draw may start
   *  preparation that would claim the widget's presentation and land after the check
   *  reads the page. An update Lit has queued stays queued, with its claim. An element
   *  with no reading to draw draws nothing here either, so one whose `setup()` threw
   *  keeps showing that failure. */
  redraw() {
    if (this.#draws()) render(this.render(), this.renderRoot, this.renderOptions);
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
    return this.#region.present((reason) => failSoftUnreported(this, reason));
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
      ? attachWidgetPresentation(this.#descriptor.id, "render")
      : attachApplicationPresentation(this.#regionName);
    const parentChanged = this.#connectedParent !== this.parentElement;
    this.#connectedParent = this.parentElement;
    this.#leaveData = this.#data.connect(
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
