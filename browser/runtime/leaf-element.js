/* A widget that draws what it reads: the one paint route of a `LeafElement`.

   A module subclasses `LeafElement` and draws in `render()`, with a retained Solid view or native DOM,
   into the element itself unless `createRenderRoot()` names a part it generated.
   `render()` reads whatever it shows through readers: the widget's own reading
   (`this.reading`, `this.state`), a bound data source (`this.data(input)`), obligations,
   reports, work, the time (`ago`, `clockValue`). Every reader it calls synchronously is
   tracked by a native Solid reaction, as a watcher's or a region's paint is followed.
   Presentation readiness (`reportsReady`) instead waits once for prerequisites to
   finish, then requests an unclaimed update: claiming another presentation for
   readiness would invalidate the proof it just received.

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
   nothing after it. Native Solid effects follow the DOM dependencies the publication
   moves, parents first and every widget before document projection
   (`elementRenderTask`, semantic-state.js). `renderCommit` separates their writes
   from `updated()` and other `afterRender` callbacks. A suggestion measures the slot
   it folds before projection marks it retired. A disconnected or superseded draw
   releases its reactions and runs no remaining owner callbacks.

   Its readers are followed while it stands (`watchOwner`, arrivals.js), and it draws
   nothing while away. A return requests an update to reconnect its dependencies
   and draw the current reading; unchanged template parts keep their nodes. It claims
   its region on every return, so a returning widget never leaves its epoch waiting. A widget whose reading lacks a declared verb, as a revision's
   replacement does before its document is adopted, draws nothing until it has them all
   (before the first state read, the authored state supplies every verb); its claim
   settles with nothing drawn. While its controller's `defer()` holds it, its claim stays
   open; the release draws the newest reading at once, changed or not, since the gesture
   may have rewritten its nodes. An element whose tag declares `x-data` holds the page's data
   version while it stands, until it has drawn what was delivered, and any drawing that
   draw held it for (`drawing()`), such as highlighting or a loading frame, has landed.
   `setup()` runs once, on the first connection, before the first render. */
import {
  watchReaction,
  untracked,
  renderCommit,
  afterRender,
} from "/vendor/browser-runtime.js";
import {
  attachApplicationPresentation,
  attachWidgetPresentation,
  elementRenderTask,
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
import { bindQueuedWork } from "./queued-work.js";

let regions = 0;

export class LeafElement extends HTMLElement {
  #following = [];
  #stopReadiness = null;
  #rendering = false;

  /** Complete a waiting render without claiming the proof it waits for again. */
  whenReady(read) {
    if (untracked(read)) return true;
    if (!this.#stopReadiness)
      this.#stopReadiness = watchPresentation(() => {
        if (!untracked(read)) return;
        this.#stopReadiness?.();
        this.#stopReadiness = null;
        this.#requestUpdate();
      });
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
  // Each synchronous stretch restores its drawing context, including post-render
  // work. Nested draws retain their own claim and asynchronous preparation.
  #draw = null;
  #task = null;
  #data = new Map();
  #leaveData = null;
  #pending = null;
  hasUpdated = false;
  updateComplete = Promise.resolve(true);
  renderRoot;

  get isUpdatePending() {
    return this.#pending !== null;
  }

  requestUpdate() {
    // Requests made by the active render are fulfilled by that render. A request
    // from updated() belongs to a new draw and claims its own presentation.
    if (this.#rendering) return;
    if (this.hasUpdated) untracked(() => this.#stage());
    this.#requestUpdate();
  }

  #requestUpdate() {
    if (this.#pending) return;
    const pending = (this.#pending = Promise.withResolvers());
    this.updateComplete = pending.promise;
    // The native task coalesces requests and follows this element's DOM dependencies.
    // Starting a draw consumes its token; an obsolete request cannot consume a later one.
    void this.#task?.enqueue(() => {
      if (this.#pending === pending) return this.performUpdate();
    });
  }

  createRenderRoot() {
    return this;
  }

  connectedCallback() {
    if (once(this)) this.#setup();
    this.renderRoot ??= this.createRenderRoot();
    if (!this.hasUpdated) this.requestUpdate();
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
    // Setup may have built the generated root. Establish it before registering a
    // connection: native effects may render during that registration's flush.
    this.renderRoot ??= this.createRenderRoot();
    // The element is an owner of its own: a paint that mounts it connects it inside that
    // paint, and what it reads to connect is its own to follow, never that paint's.
    watchOwner(this, {
      connect: () => untracked(() => this.#connect()),
      disconnect: () => this.#disconnect(),
    });
  }

  /** The module's one-time build, on the first connection, before the first render. */
  setup() {}

  render() {}

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
    this.#draw.ticket = this.#ticket;
    this.#ticket = null;
    if (this.#broken) return false;
    return this.#complete();
  }

  update(changed) {
    this.render();
    this.#box?.remove();
    this.#box = null;
  }

  // An update settles its claim once all of it has run, `updated` included, and one
  // that failed anywhere, its gate too, reports once and shows its failure; The scheduler has
  // marked it done, so the next move draws again. A draw that `updated` asks for at
  // once, as a module's own paint may, settles its own claim inside this one; with no
  // claim of its own, its failure is the enclosing claimed update's.
  performUpdate() {
    if (!this.#pending) return;
    const pending = this.#pending;
    this.#pending = null;
    const outer = this.#draw;
    const draw = { ticket: null, work: null };
    for (const stop of this.#following) stop();
    const following = (this.#following = []);
    const run = (callback) => {
      const previous = this.#draw;
      this.#draw = draw;
      let outcome;
      try {
        const stop = watchReaction(
          () => {
            try {
              outcome = { value: callback() };
            } catch (error) {
              outcome = { error };
            }
          },
          () => {
            if (this.#connected) this.#present();
          },
        );
        if (following === this.#following && this.#connected) following.push(stop);
        else stop();
        if ("error" in outcome) throw outcome.error;
        return outcome.value;
      } finally {
        this.#draw = previous;
      }
    };
    const commit = renderCommit(
      () => {
        this.#rendering = true;
        try {
          if (this.shouldUpdate()) {
            this.update();
            this.hasUpdated = true;
            afterRender(() => this.updated());
          }
        } finally {
          this.#rendering = false;
        }
      },
      {
        run,
        bind: bindQueuedWork,
        current: () =>
          this.#connected && this.isConnected && following === this.#following,
      },
    );
    const finished = commit.ready.then(
      () => {
        if (draw.work && !draw.ticket) {
          if (outer)
            outer.work = outer.work ? Promise.all([outer.work, draw.work]) : draw.work;
          else if (this.#region) draw.ticket = this.#claim();
        }
        draw.ticket?.resolve(draw.work ?? undefined);
      },
      (error) => {
        if (outer && !draw.ticket) throw error;
        this.#failed(error, draw.ticket);
      },
    );
    void finished.catch(() => undefined);
    void commit.committed.then(
      () => pending.resolve(!this.#pending),
      () => pending.resolve(!this.#pending),
    );
    return finished;
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
    this.#draw.work = this.#draw.work ? Promise.all([this.#draw.work, named]) : named;
  }

  /** The render drawn again at once, outside any claim and the update schedule, with a
   *  failure thrown rather than shown: the render check's replay
   *  (render-checks/replay.js), which holds a draw of the same reading to change
   *  nothing. `updated()` does not run, since what follows a draw may start
   *  preparation that would claim the widget's presentation and land after the check
   *  reads the page. An update the scheduler has queued stays queued, with its claim. */
  redraw() {
    this.render();
  }

  updated(changed) {
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
    if (now) this.performUpdate();
  }

  #refresh() {
    if (this.#connected) this.#present({ now: true });
  }

  #connect() {
    this.#connected = true;
    this.#task = elementRenderTask(this.#descriptor?.id);
    if (this.#pending) {
      const pending = this.#pending;
      void this.#task.enqueue(() => {
        if (this.#pending === pending) return this.performUpdate();
      });
    }
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
    for (const stop of this.#following) stop();
    this.#following = [];
    this.#task?.disconnect();
    this.#task = null;
    this.#stopReadiness?.();
    this.#stopReadiness = null;
    this.#leaveData?.();
    this.#leaveData = null;
    this.#ticket = null;
    this.#region?.disconnect();
    this.#region = null;
  }
}
