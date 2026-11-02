/* lf-sample: inline content (quoted by default, interactive on the parent page
 * when declared), or a complete live page authored in a template. The inline modes
 * need no controller; the registry owns their quotation semantics.
 * The shared host owns the child page and its independent event log. The frame
 * takes its child's height, so the surrounding page scrolls the sample like any
 * other block and focus moves into it the way it moves into any iframe. A `window`
 * sample is instead a whole Leaf window at the frame's own height, chrome included,
 * and scrolls inside itself. The child's
 * final Escape brings focus back to this element. Full view promotes the same frame
 * into a native modal dialog, keeping its document, gestures, and drafts alive. The
 * sample retains its embedded allocation while the dialog fills the viewport; Return
 * to page and the child's final Escape restore the Full view button. Each child announces
 * lf-sample-ready with its sample element after upgrade, on first mount, Reset and
 * reload; its loading saved state does not hold the parent.
 * Each child starts loading as its sample mounts, but the containing page presents
 * before it unless the frame's resize on arrival would move what the reader sees then.
 * The sample's arrival is its child's: the child's presentation and then whatever that
 * document deferred, its own samples included, so the page reads as still arriving
 * until every child has arrived. Each document the frame loads, on mount, Reset or a
 * reload, is counted from when it begins (`deferredArrival`) until it arrives, fails,
 * departs or the sample leaves. A reload's document is counted once it connects; the
 * parent cannot tell its departure from one to a page outside Leaf, whose load can
 * land before the departure's notice, so nothing is counted between. Work a child
 * starts after it has arrived, such as one of its own samples' Reset, is the child's
 * to count. A resize of a child the reader did not ask to load, reached by scrolling,
 * waits until it would move nothing they see, the frame keeping its current height
 * (`heldGrowth`), or until the reader clicks,
 * types or presses a key inside the child, which makes every later resize of that
 * document theirs, though not a wheel or touch that scrolls past it; a resize
 * after Reset or Return to page, or one of a frame the reader saw as it mounted, is
 * theirs and applies at once. The status line keeps its room through loading, ready
 * and failure, so the frame below it stays put; a failure's words that run past it
 * stand in a disclosure the reader opens over the frame.
 * Reset stays focusable
 * while loading but accepts no new press, preserving the parent's keyboard position.
 * Ordinary children remain static
 * quotation. A disconnect releases the child; moving the retained element within a
 * document does not reset its work. */
import {
  aborted,
  describeFailure,
  deferredArrival,
  frameFor,
  growthIsSeen,
  whileConnected,
  keeps,
  keepsText,
  nameAction,
  layoutPx,
  mountSample,
  once,
  offer,
  offerAction,
  generatedElement,
  widgetController,
  focusDestination,
  closeLayer,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  handBack,
  heldGrowth,
} from "/runtime/widget-api.js";

export class Sample extends HTMLElement {
  /** @typedef {Awaited<ReturnType<typeof mountSample>>} SampleHost */
  /** @typedef {Awaited<SampleHost["ready"]>} SampleReady */
  /** @typedef {{template: HTMLTemplateElement, frame: HTMLIFrameElement, view: HTMLDialogElement, reset: HTMLButtonElement, status: HTMLSpanElement, full: HTMLButtonElement}} SampleView */
  /** @type {SampleHost | null} */
  #host = null;
  get #activeHost() {
    if (!this.#host) throw new Error("Sample has no active child");
    return this.#host;
  }
  /** @type {SampleView | null} */
  #pageView = null;
  get #page() {
    if (!this.#pageView) throw new Error("Inline sample has no child page");
    return this.#pageView;
  }
  get #frame() {
    return this.#page.frame;
  }
  get #template() {
    return this.#page.template;
  }
  get #view() {
    return this.#page.view;
  }
  get #reset() {
    return this.#page.reset;
  }
  get #status() {
    return this.#page.status;
  }
  get #full() {
    return this.#page.full;
  }
  /** @type {HTMLDetailsElement | null} */
  #disclosure = null;
  /** @type {number | undefined} */
  #heightReading;
  #fit = () => {
    this.#frame.style.height = `${this.#heightReading}px`;
  };
  #scheduleFit = frameFor(this, this.#fit);
  // Drops a resize `heldGrowth` holds.
  /** @type {(() => void) | null} */
  #heldFit = null;
  // The current document's arrival (`#track`); whether its resizes wait while seen
  // until the reader claims it; and whether the reader asked for the load.
  /** @type {{land: () => void, reported: (() => void) | null} | null} */
  #arrival = null;
  #unclaimed = false;
  #asked = false;
  /** @type {{source: Promise<SampleReady>, ready: Promise<SampleReady>} | null} */
  #following = null;
  get #ready() {
    return this.#following?.ready;
  }
  #focusedContent = false;
  #mounting = false;
  /** @type {AbortController | undefined} */
  #viewOperation;

  get ready() {
    return this.#ready;
  }

  get focusedContent() {
    return this.#focusedContent;
  }

  restoreCurrentLocation() {
    return this.#host?.restoreCurrentLocation();
  }

  connectedCallback() {
    if (!once(this)) return;
    if (!this.#build()) return;
    whileConnected(this, () => {
      this.#mount();
      return () => {
        this.#viewOperation?.abort();
        this.#arrival?.land();
        const host = this.#host;
        this.#host = null;
        host?.destroy().catch((/** @type {unknown} */ error) => this.#failure(error));
      };
    });
  }

  #mount() {
    // Removal ends native modality even when a retained widget reconnects before
    // its host is retired. Reconcile the presentation with that platform state.
    if (
      this.#pageView?.view.getAttribute("role") === "dialog" &&
      !isNativeLayer(this.#view)
    )
      this.#embed();
    if (!this.#pageView || this.#host || this.#mounting) return;
    this.#mounting = true;
    const ready = mountSample(this.#frame, {
      template: this.#template.id,
      window: this.hasAttribute("window") || isNativeLayer(this.#view),
    }).then(
      async (host) => {
        this.#mounting = false;
        if (!this.isConnected) {
          // Destroy cancels presentation; nobody awaits this removed element.
          host.ready.catch(() => {});
          await host.destroy();
          throw new DOMException("sample disconnected", "AbortError");
        }
        this.#host = host;
        host.on("height", ({ height }) => this.#height(height));
        host.on("arrived", () => this.#arrival?.reported?.());
        // A click, a key or text entered in the child claims the frame. A wheel, or a
        // touch that scrolls, moves the containing page past it and claims nothing.
        host.on("input", ({ type }) => {
          if (type === "click" || type === "keydown" || type === "input")
            this.#release();
        });
        host.on("loading", () => {
          this.#focusedContent = false;
          this.#track(host.ready);
        });
        host.on("current-location", ({ focused }) => {
          this.#focusedContent = focused;
        });
        // The departed document's frame shows the browser's destination, which
        // Reset replaces; a reload's `loading` follows the same promise.
        host.on("departed", () => {
          this.#focusedContent = false;
          this.#follow(host.ready);
          this.#say("");
          keeps(this.#reset, "aria-disabled", null);
          this.#arrival?.land();
        });
        return host.ready;
      },
      (error) => {
        this.#mounting = false;
        throw error;
      },
    );
    // A failed child is drawn by this widget's status and Reset. That is a
    // completed parent rendering; the public sample.ready still rejects. A first
    // document that departs before upgrading holds it until the next document,
    // which a reload brings, or Reset: the parent cannot tell a reload from an
    // external destination.
    // The child's startup is another document's, and nothing in this page reads
    // it, so presentation waits for it only where its arrival would move what the
    // reader sees now: a block frame resizes to its child once that presents. A
    // window keeps its height, and a frame below the window or scrolled past grows
    // where the reader isn't looking, so the page presents and takes keys without
    // them while they load. The page reads as arriving until each child has.
    // A frame the reader sees as it mounts is part of what they are being shown,
    // the page arriving or a view they opened, such as a thread in the floating
    // panel: its resize is that showing's, not news, so it applies at once, as one
    // the reader asked for does. Only a frame they come upon while it loads holds it.
    const presented =
      !this.hasAttribute("window") &&
      !isNativeLayer(this.#view) &&
      growthIsSeen(this.#frame);
    this.#asked = presented;
    const shown = this.#track(ready).catch(() => {});
    if (presented) widgetController(this).present(shown);
  }

  // Removal closes a modal Full view at once, so the view returns to its embedded
  // posture in the same task rather than at the arrival batch.
  disconnectedCallback() {
    if (this.#pageView?.view.getAttribute("role") === "dialog") this.#embed();
  }

  #build() {
    /** @type {HTMLTemplateElement | null} */
    const template = this.querySelector(":scope > template[data-sample]");
    if (!template) return false;
    this.#pageView = {
      template,
      frame: document.createElement("iframe"),
      view: document.createElement("dialog"),
      reset: offerAction("symbol", "lf-sample-action", "Reset", { action: "reset" }),
      status: offer("span", "lf-sample-status"),
      full: offerAction("symbol", "lf-sample-action", undefined, { action: "expand" }),
    };
    this.#frame.className = "lf-sample-frame";
    this.#frame.title = this.getAttribute("label") || "Leaf sample";
    this.#frame.addEventListener("lf-sample-return", () => {
      if (isNativeLayer(this.#view)) this.#return();
      else focusDestination(this, "return");
    });

    this.#view.className = "lf-sample-view";
    generatedElement(this.#view, { says: false });
    this.#view.setAttribute("open", "");
    this.#view.setAttribute("role", "presentation");
    this.#view.addEventListener("cancel", (event) => {
      event.preventDefault();
      this.#return();
    });

    const controls = document.createElement("div");
    controls.className = "lf-sample-controls lf-ui";
    generatedElement(controls, { says: false });
    const actions = document.createElement("div");
    this.#reset.addEventListener("click", () => {
      if (this.#reset.ariaDisabled === "true") return;
      this.reset().catch(() => {}); // #track paints the failed operation.
    });
    this.#status.setAttribute("role", "status");
    this.#paintFull(false);
    this.#full.addEventListener("click", () => {
      if (isNativeLayer(this.#view)) this.#return();
      else {
        // The frame never moves in the DOM: reparenting it destroys its browsing
        // context. Native modality supplies focus containment and parent isolation.
        // The label stays in flow; reserve only the controls and frame leaving it.
        const height =
          this.#frame.getBoundingClientRect().bottom -
          controls.getBoundingClientRect().top;
        this.style.setProperty("--lf-sample-height", layoutPx(height));
        closeNativeLayer(this.#view);
        this.#view.setAttribute("role", "dialog");
        this.#view.setAttribute("aria-label", this.#frame.title);
        this.#paintFull(true);
        showNativeLayer(this.#view);
        this.#setWindow(true);
        focusDestination(this.#full, "move");
      }
    });
    actions.append(this.#reset, this.#full, this.#status);
    controls.append(actions);
    const exhibit = document.createElement("div");
    exhibit.className = "lf-sample-exhibit";
    exhibit.append(this.#frame);
    this.#view.append(controls, exhibit);
    this.append(this.#view);
    return true;
  }

  #return() {
    closeLayer(
      () => this.#embed(),
      () => handBack(this.#full),
    );
    if (this.#heightReading !== undefined)
      this.#height(this.#heightReading, { immediate: true, asked: true });
  }

  #embed() {
    closeNativeLayer(this.#view);
    // Initial open markup keeps the embedded group visible without the native
    // focusing steps of show(), which could scroll the containing page.
    this.#view.setAttribute("open", "");
    this.#view.setAttribute("role", "presentation");
    this.#view.removeAttribute("aria-label");
    this.style.removeProperty("--lf-sample-height");
    this.#paintFull(false);
    this.#setWindow(this.hasAttribute("window"));
  }

  /** @param {boolean} expanded */
  #paintFull(expanded) {
    nameAction(this.#full, expanded ? "collapse" : "expand", {
      label: expanded ? "Return to page" : "Full view",
    });
  }

  /** @param {boolean} value */
  #setWindow(value) {
    this.#host?.setWindow(value).then(
      ({ height }) => this.#height(height, { asked: true }),
      (/** @type {unknown} */ error) => this.#failure(error),
    );
  }

  // The child owns its body observer and reports values over the private port.
  // Full view retains the embedded height while its same frame fills the dialog;
  // returning applies the current block reading without replacing any native editor.
  // An unclaimed child's reading waits while its resize would be seen, unless
  // the reader `asked` for it, by Reset or Return to page.
  /** @param {number} height */
  #height(height, { immediate = false, asked = false } = {}) {
    if (this.hasAttribute("window") || isNativeLayer(this.#view)) return;
    this.#heightReading = height;
    this.#heldFit?.();
    this.#heldFit = null;
    const fit = immediate ? this.#fit : this.#scheduleFit;
    if (this.#unclaimed && !asked) this.#heldFit = heldGrowth(this.#frame, fit);
    else fit();
  }

  // The reader's click or key inside the child makes the frame theirs to move: a
  // resize held while they read applies now, and so does each later one.
  #release() {
    this.#unclaimed = false;
    if (!this.#heldFit) return;
    this.#heldFit();
    this.#heldFit = null;
    this.#fit();
  }

  // Cancellation is this widget's own, and the departed notice draws a departure.
  /** @param {unknown} error */
  #failure(error) {
    if (
      error instanceof Error &&
      (error.name === "AbortError" || error.name === "SampleDepartedError")
    )
      return;
    this.#sayFailure(describeFailure(error));
    keeps(this.#reset, "aria-disabled", null);
  }

  // The status's words. A failure's can run past the row's one line, so they stand in
  // a disclosure, cut short until the reader opens it by key or by tap to read them
  // whole (sample.css); a later failure saying the same leaves it as the reader left it.
  /** @param {string} words */
  #say(words) {
    this.#disclosure = null;
    keepsText(this.#status, words);
  }
  /** @param {string} message */
  #sayFailure(message) {
    if (this.#disclosure?.textContent === message) return;
    const disclosure = offer("details", "lf-sample-failure");
    disclosure.append(offer("summary", "", message));
    this.#status.replaceChildren(disclosure);
    this.#disclosure = disclosure;
  }

  // Count the frame's next document as arriving, landing the one before: the page
  // reads as arriving until `land` is called, or `reported` once its child is drawn.
  /** @param {Promise<SampleReady>} promise */
  #track(promise) {
    keeps(this.#reset, "aria-disabled", "true");
    this.#say("Loading sample…");
    this.#arrival?.land();
    const { promise: landed, resolve: settle } = Promise.withResolvers();
    const land = () => settle(undefined);
    /** @type {{land: () => void, reported: (() => void) | null}} */
    const arrival = { land, reported: null };
    this.#arrival = arrival;
    deferredArrival(landed).then(() => {
      if (this.#arrival !== arrival) return;
      this.#arrival = null;
    });
    this.#unclaimed = !this.#asked;
    this.#asked = false;
    const ready = this.#follow(promise);
    // The child reports its arrival after its presentation, which this widget draws
    // a turn later. A failed or cancelled child has nothing more to bring.
    const { promise: reported, resolve } = Promise.withResolvers();
    arrival.reported = () => resolve(undefined);
    ready
      .then(
        () => reported,
        () => {},
      )
      .then(arrival.land);
    return ready;
  }

  // One `ready` per usable document the host promises, so a departure and the reload
  // that follows it are one wait for a selection or a page module.
  /** @param {Promise<SampleReady>} promise */
  #follow(promise) {
    if (promise === this.#following?.source) return this.#following.ready;
    const ready = promise.then(async (reading) => {
      if (this.#ready !== ready) return reading;
      const current = await this.#activeHost.setWindow(
        this.hasAttribute("window") || isNativeLayer(this.#view),
      );
      if (this.#ready !== ready) return reading;
      this.#height(current.height, { immediate: true });
      keeps(this.#reset, "aria-disabled", null);
      this.#say("");
      this.dispatchEvent(
        new CustomEvent("lf-sample-ready", {
          bubbles: true,
          detail: { sample: this },
        }),
      );
      return reading;
    });
    this.#following = { source: promise, ready };
    ready.catch((error) => {
      if (this.#ready === ready) this.#failure(error);
    });
    return ready;
  }

  // Latest selection wins, including a selection waiting on a replacement child. A
  // newer selection, Reset, removal or the child's departure supersedes it, and the
  // page reapplies its view on the next document's lf-sample-ready. The outer
  // control remains the keyboard stop while the child draws its view.
  /** @param {string} id
   * @param {{surface?: "page" | "panel"}} [view] */
  async showThread(id, { surface = "page" } = {}) {
    this.#viewOperation?.abort();
    const operation = new AbortController();
    this.#viewOperation = operation;
    const { signal } = operation;
    const ready = this.#ready;
    if (!ready) return false;
    const shown = ready
      .then(() =>
        signal.aborted ? false : this.#activeHost.showThread(id, { surface, signal }),
      )
      .catch((error) => {
        if (error instanceof Error && error.name === "SampleDepartedError")
          return false;
        throw error;
      });
    return Promise.race([shown, aborted(signal).then(() => false)]);
  }

  async reset() {
    this.#viewOperation?.abort();
    if (this.#mounting) await this.#ready;
    this.#asked = true;
    if (!this.#host) {
      this.#mount();
      return this.#ready;
    }
    return this.#track(this.#host.reset());
  }
}

customElements.define("lf-sample", Sample);
