/* A widget that draws what it reads: the one paint route of a `LeafElement`.

   A module subclasses `LeafElement` and draws in `render()`, as any `LitElement` does,
   into the element itself unless `createRenderRoot()` names a part it generated.
   `render()` reads whatever it shows through readers: the widget's own reading
   (`this.reading`, `this.state`), a bound data source (`this.data(input)`), asks,
   reports, work, the time (`ago`, `clockValue`). Every reader it calls synchronously is
   collected (`collectReads`, snapshot.ts), and a move of any of them updates the element
   again, as a watcher's or a region's paint is followed; nothing else is. Lit's own
   reactive properties update it too, for state the widget keeps itself. A reading of
   presentation proof (`proofReading`, semantic-state.js), such as `reportsReady`,
   updates it without claiming its region, since the claim would move that proof.

   The element owns one presentation region: its widget's render region when the
   registry declares it a widget, so startup, thread mirrors, gesture release and report
   narration wait on it as they did on the controller's, and otherwise a region of its
   own. A move claims that region synchronously, inside the publication that made it,
   and the next update that draws settles the claim as it commits; a claim no update can
   draw yet stays open until one does. An update that throws settles it with the
   fail-soft box in the render root, which the next update draws over; one no claim
   waits on, such as a mechanical redraw, reports and shows its failure the same way.
   Lit updates on the microtask after a claim, so the result stands before the browser
   draws the next frame.

   Its readers are followed while it stands (`watchOwner`, arrivals.js), and it draws
   nothing while away, so a draw queued as it left is owed to its return; a return draws
   again only where that is owed or something it read moved meanwhile, and claims its
   region either way, so a returning widget never leaves its epoch waiting. A widget
   whose reading lacks a declared verb, as at startup before the log is read, draws
   nothing until it has them all; its claim settles with nothing drawn. While its
   controller's `defer()` holds it, or a drag holds the page (`dragging`), its claim stays
   open; the release draws the newest reading at once, changed or not, since the gesture
   may have rewritten its nodes. An element whose tag declares `x-data` holds the page's
   data version while it stands, until it has drawn what was delivered. `setup()` runs
   once, on the first connection, before the first render. */
import { LitElement, collectReads, untracked } from "../vendor/browser-runtime.js";
import {
  attachApplicationPresentation,
  attachWidgetPresentation,
  readsProof,
} from "./semantic-state.js";
import { widgetDescriptor } from "./widget-descriptors.js";
import { drawsItself, widgetController, widgetMounted } from "./widget-controller.js";
import { failSoft, failSoftUnreported, once } from "./widget-upgrade.js";
import { watchOwner } from "./arrivals.js";
import { dragHeld, watchDragRelease } from "./widget-elements.js";
import { paintKeysWithin } from "./keyboard/scopes.js";
import { dataReader, joinDataDelivery, stagesOnly } from "./data.js";
import { registry } from "./registry.js";

const REFRESH = Symbol("refresh");
let regions = 0;

// Elements a drag held back, drawn in the order they asked once the last hand is down.
const dragWaiting = new Set();
watchDragRelease(() => {
  const waiting = [...dragWaiting];
  dragWaiting.clear();
  for (const element of waiting) element[REFRESH]();
});

export class LeafElement extends LitElement {
  #descriptor = null;
  #controller = null;
  #verbs = [];
  #region = null;
  #regionName = null;
  #connected = false;
  #connectedParent = null;
  // What the last gate and the last render read, each with the value it read.
  #gateReads = new Map();
  #renderReads = new Map();
  #following = [];
  // A draw owed to the next connection: queued as it left, or a reading moved meanwhile.
  #owed = false;
  // The open claim the next update that draws settles.
  #ticket = null;
  #holds = 0;
  // Whether the failure of the update under way has been reported.
  #reported = false;
  #data = new Map();
  #leaveData = null;

  createRenderRoot() {
    return this;
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
        refresh: () => this[REFRESH](),
      });
      this.#verbs = Object.keys(this.#descriptor.declaration["x-state"] ?? {});
    }
    this.#regionName = this.#descriptor
      ? null
      : `element:${this.localName}#${this.id}:${++regions}`;
    this.setup();
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

  /** The bound source of a declared `x-data` input, as `watchData` delivers it. */
  data(input) {
    let read = this.#data.get(input);
    if (!read) this.#data.set(input, (read = dataReader(this, input)));
    return read();
  }

  // The controller's `defer` for this widget: hold its presentation through a gesture
  // that rewrites its nodes; the release draws the newest reading at once.
  #hold() {
    this.#holds += 1;
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.#holds -= 1;
      if (!this.#held()) this[REFRESH]();
    };
  }

  #held() {
    return this.#holds > 0 || dragHeld();
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
      this.#owed = true;
      return false;
    }
    if (this.#held()) {
      if (dragHeld()) dragWaiting.add(this);
      return false;
    }
    const gate = collectReads(() => this.#complete());
    this.#gateReads = gate.reads;
    if ("error" in gate) {
      this.#failed(gate.error, this.#ticket);
      this.#follow();
      throw gate.error;
    }
    if (!gate.value) {
      // Nothing to draw until every declared verb has arrived; the claim stands drawn.
      this.#settle();
      this.#follow();
    }
    return gate.value && super.shouldUpdate(changed);
  }

  update(changed) {
    // The claim this update draws; one its own reads claim while it runs is the next's.
    const ticket = this.#ticket;
    this.#ticket = null;
    const outcome = collectReads(() => super.update(changed));
    this.#renderReads = outcome.reads;
    if ("error" in outcome) {
      this.#failed(outcome.error, ticket);
      this.#follow();
      throw outcome.error;
    }
    ticket?.resolve();
    this.#follow();
  }

  // An update that failed anywhere, its gate and `updated` included, reports once and
  // shows its failure; Lit has marked it done, so the next move draws again.
  performUpdate() {
    this.#reported = false;
    try {
      super.performUpdate();
    } catch (error) {
      if (!this.#reported) this.#failed(error, null);
    }
  }

  updated(changed) {
    super.updated(changed);
    // The render may have changed what this widget's commands read from its nodes.
    paintKeysWithin(this);
  }

  #settle() {
    this.#ticket?.resolve();
    this.#ticket = null;
  }

  // The fail-soft box goes where the render draws, so the next update draws over it.
  #failed(error, ticket) {
    this.#reported = true;
    if (ticket === this.#ticket) this.#ticket = null;
    if (ticket) ticket.reject(error);
    else failSoft(this.renderRoot, error);
  }

  #follow() {
    for (const stop of this.#following) stop();
    const reads = [...this.#gateReads, ...this.#renderReads];
    this.#following = this.#connected
      ? reads.map(([reading, seen]) =>
          reading.subscribe((now) => {
            if (now === seen) return;
            // Proof moving draws again without a claim, which would move proof again;
            // accepted data claims and waits for its delivery to draw.
            if (readsProof(reading)) this.requestUpdate();
            else if (stagesOnly(reading)) this.#stage();
            else this.#moved();
          }),
        )
      : [];
  }

  #moved() {
    if (!this.#connected) {
      this.#owed = true;
      return;
    }
    this.#present();
  }

  // Claim the region for a reading that draws later, leaving the claim open.
  #stage() {
    if (!this.#connected || this.#ticket || !this.#region) return;
    this.#ticket = this.#region.present(
      untracked(() => this.#controller?.read() ?? {}),
      (reason) => failSoftUnreported(this.renderRoot, reason),
    );
  }

  // Claim the region for the reading as it stands, and draw it on the next update; a
  // claim the next update cannot draw stays open until one does.
  #present({ now = false } = {}) {
    if (!this.#region) return;
    const value = untracked(() => (this.#controller ? this.#controller.read() : {}));
    this.#ticket = this.#region.present(value, (reason) =>
      failSoftUnreported(this.renderRoot, reason),
    );
    if (this.#held()) {
      if (dragHeld()) dragWaiting.add(this);
      return;
    }
    this.requestUpdate();
    if (now) this.performUpdate();
  }

  [REFRESH]() {
    if (this.#connected) this.#present({ now: true });
    else this.#owed = true;
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
    this.#follow();
    const moved = untracked(() =>
      [...this.#gateReads, ...this.#renderReads].some(
        ([reading, seen]) => reading.read() !== seen,
      ),
    );
    if (!this.hasUpdated || this.#owed || moved) {
      this.#owed = false;
      this.#present();
    } else
      this.#region.present(untracked(() => this.#controller?.read() ?? {})).resolve();
    if (this.#descriptor) widgetMounted(this, this.#descriptor, parentChanged);
  }

  #disconnect() {
    this.#connected = false;
    this.#follow();
    this.#leaveData?.();
    this.#leaveData = null;
    dragWaiting.delete(this);
    this.#ticket = null;
    this.#region?.disconnect();
    this.#region = null;
  }
}
