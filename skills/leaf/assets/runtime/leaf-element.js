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
   and the next update that draws settles the claim once all of it, `updated` included,
   has run; a claim no update can draw yet stays open until one does. An update that
   throws anywhere settles it with the fail-soft box, which stands at the head of the
   render root beside what the element drew, since a render may paint retained nodes no
   later draw would make again; the next update that draws takes the box away. One no
   claim waits on, such as a mechanical redraw, reports and shows its failure the same
   way, and so does a failed preparation (`present()`) or a module's own
   `failSoft(this, …)`. A `setup()` that throws shows its failure, and the element draws
   nothing after it. Lit updates on the microtask after a claim, so the result stands
   before the browser draws the next frame.

   Its readers are followed while it stands (`watchOwner`, arrivals.js), and it draws
   nothing while away, so a draw queued as it left is owed to its return; a return draws
   again only where that is owed or something it read moved meanwhile, and claims its
   region either way, so a returning widget never leaves its epoch waiting. A widget
   whose reading lacks a declared verb, as at startup before the log is read, draws
   nothing until it has them all; its claim settles with nothing drawn. While its
   controller's `defer()` holds it, its claim stays open; the release draws the newest
   reading at once, changed or not, since the gesture may have rewritten its nodes. An
   element whose tag declares `x-data` holds the page's data version while it stands,
   until it has drawn what was delivered. `setup()` runs once, on the first connection,
   before the first render. */
import { LitElement, collectReads, untracked } from "/vendor/browser-runtime.js";
import {
  attachApplicationPresentation,
  attachWidgetPresentation,
  readsProof,
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
import { dataReader, joinDataDelivery, stagesOnly } from "./data.js";
import { registry } from "./registry.js";

let regions = 0;

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
  #held = false;
  // The fail-soft box standing until the next update that draws; a `setup()` that threw
  // leaves the element broken, drawing nothing.
  #box = null;
  #broken = false;
  // The claim the update under way draws, settled once `updated` has run too.
  #drawing = null;
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
        refresh: () => this.#refresh(),
      });
      this.#verbs = Object.keys(this.#descriptor.declaration["x-state"] ?? {});
    }
    this.#regionName = this.#descriptor
      ? null
      : `element:${this.localName}#${this.id}:${++regions}`;
    placesFailure(this, (box) => {
      this.#box?.remove();
      this.#box = box;
      // Before the render root exists, as in a `setup()` that threw, the box stands where
      // the element shows its contents.
      (this.renderRoot ?? this.shadowRoot ?? this).prepend(box);
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

  /** The bound source of a declared `x-data` input, as `watchData` delivers it. */
  data(input) {
    let read = this.#data.get(input);
    if (!read) this.#data.set(input, (read = dataReader(this, input)));
    return read();
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
      this.#owed = true;
      return false;
    }
    if (this.#held) return false;
    // The claim this update draws, from its gate on; one its own reads claim while it
    // runs is the next's. An update that draws nothing settles it all the same.
    this.#drawing = this.#ticket;
    this.#ticket = null;
    if (this.#broken) return false;
    const gate = collectReads(() => this.#complete());
    this.#gateReads = gate.reads;
    if ("error" in gate) {
      this.#follow();
      throw gate.error;
    }
    if (!gate.value) {
      // Nothing to draw until every declared verb has arrived.
      this.#follow();
      return false;
    }
    return super.shouldUpdate(changed);
  }

  update(changed) {
    const outcome = collectReads(() => super.update(changed));
    this.#renderReads = outcome.reads;
    this.#follow();
    if ("error" in outcome) throw outcome.error;
    this.#box?.remove();
    this.#box = null;
  }

  // An update settles its claim once all of it has run, `updated` included, and one
  // that failed anywhere, its gate too, reports once and shows its failure; Lit has
  // marked it done, so the next move draws again. A draw that `updated` asks for at
  // once, as a module's own paint may, settles its own claim inside this one.
  performUpdate() {
    const outer = this.#drawing;
    this.#drawing = null;
    try {
      super.performUpdate();
      this.#drawing?.resolve();
    } catch (error) {
      this.#failed(error, this.#drawing);
    } finally {
      this.#drawing = outer;
    }
  }

  updated(changed) {
    super.updated(changed);
    // The render may have changed what this widget's commands read from its nodes.
    paintKeysWithin(this);
  }

  // Every failure is reported here, naming the widget; a claim's rejection then shows
  // the box through the coordinator's fallback, which reports nothing again.
  #failed(error, ticket) {
    if (!ticket) return failSoft(this, error);
    reportFailure(this, error);
    ticket.reject(error);
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
      (reason) => failSoftUnreported(this, reason),
    );
  }

  // Claim the region for the reading as it stands, and draw it on the next update; a
  // claim the next update cannot draw stays open until one does.
  #present({ now = false } = {}) {
    if (!this.#region) return;
    const value = untracked(() => (this.#controller ? this.#controller.read() : {}));
    this.#ticket = this.#region.present(value, (reason) =>
      failSoftUnreported(this, reason),
    );
    if (this.#held) return;
    this.requestUpdate();
    if (now) this.performUpdate();
  }

  #refresh() {
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
    this.#ticket = null;
    this.#region?.disconnect();
    this.#region = null;
  }
}
