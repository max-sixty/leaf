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
 * A child starts as its frame nears the window (`whenNear`), so a page loads only the
 * children its reader comes near; one in a shut tab or a closed disclosure starts
 * when that opens. Until then nothing loads, the frame keeps its placeholder height
 * and the status line stays empty, so starting moves nothing; `ready` waits, and
 * Reset starts the child. The browser's Find searches only the children that have
 * started. A frame the reader sees as it mounts starts at once, and the containing
 * page presents before it unless the frame's resize on arrival would move what the
 * reader sees then, and stops waiting for it once the host says its load waits on the
 * server (`waiting`). The sample's arrival is its child's: the child's presentation
 * and then whatever that document deferred, the samples it started included. The page
 * reads as arriving until every started child has arrived, and until the browser's
 * first reading of each waiting frame has said whether it starts. Each document the
 * frame loads, on mount, Reset or a reload, is counted from when it begins
 * (`deferredArrival`) until it arrives, fails, departs or the sample leaves. A
 * reload's document is counted once it connects; the parent cannot tell its departure
 * from one to a page outside Leaf, whose load can land before the departure's notice,
 * so nothing is counted between. Work a child starts after it has arrived, such as
 * one of its own samples' Reset, is the child's to count. A resize of a child the
 * reader did not ask to load, one that started near the window but out of their
 * sight, waits while it would move what they see, the frame keeping its current
 * height (`heldGrowth`), until they look away, or until they click, type or press a
 * key inside the child, which makes every later resize of that document theirs,
 * though not a wheel or touch that scrolls past it; a resize after Reset or Return to
 * page, or one of a frame the reader saw as it mounted or as it started, as when a
 * tab, a link or a jump brings it into view, is theirs and applies at once. The user
 * chose on 14 November 2026 to fit a frame they bring into view to its page as soon
 * as the page draws, over keeping its placeholder height until they look away or
 * click into it, which left a short page standing in a blank frame. A load that
 * waited on its server arrives as news, held the same way, whoever asked for it:
 * after minutes of waiting the reader may have moved on. The status line keeps its
 * room through loading, ready and failure, so the frame below it stays put; a
 * failure's words that run past it stand in a disclosure the reader opens over the
 * frame.
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
  whenNear,
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
  // Settles what `#start` returns: the frame's first fit to its child.
  /** @type {(() => void) | null} */
  #fitted = null;
  #fit = () => {
    this.#frame.style.height = `${this.#heightReading}px`;
    this.#fitted?.();
    this.#fitted = null;
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
  // The first document's readiness, for whoever awaits it before the sample starts.
  // Its outcome is the owner's to read, as the readiness it adopts is.
  /** @type {PromiseWithResolvers<SampleReady>} */
  #starting = Promise.withResolvers();
  // What stops waiting for the frame to near the window, while the sample waits.
  /** @type {(() => void) | null} */
  #nearing = null;
  #focusedContent = false;
  #mounting = false;
  /** @type {AbortController | undefined} */
  #viewOperation;

  constructor() {
    super();
    this.#starting.promise.catch(() => {});
  }

  get ready() {
    return this.#ready ?? (this.#pageView ? this.#starting.promise : undefined);
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
        this.#nearing?.();
        this.#nearing = null;
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
    if (!this.#pageView || this.#host || this.#mounting || this.#nearing) return;
    // A frame the reader sees as it mounts is part of what they are being shown, the
    // page arriving or a view they opened, such as a thread in the floating panel: it
    // starts at once, and that showing waits for its resize to its child.
    if (this.#seen()) {
      this.#start(true, { present: true });
      return;
    }
    // One the reader sees as it starts, brought into view by a tab, a link or a jump,
    // is theirs too, and fits its page as soon as that draws; `whenNear` holds the fit
    // as the landing of the gesture that brought it near. One that starts near the
    // window but out of their sight arrives as news, and lands nothing they see.
    this.#nearing = whenNear(this.#frame, () => {
      this.#nearing = null;
      const asked = this.#seen();
      const fitted = this.#start(asked);
      return asked ? fitted : undefined;
    });
  }

  // Whether the frame's resize to its child would move what the reader sees now. A
  // window keeps its height.
  #seen() {
    return (
      !this.hasAttribute("window") &&
      !isNativeLayer(this.#view) &&
      growthIsSeen(this.#frame)
    );
  }

  // Start the child. Its resize on arrival applies at once where the reader `asked`
  // for it, and otherwise waits while they see it (`#height`). Returns the frame's
  // first fit to its child, or its readiness settling where it fits nothing then, or
  // the server's wait.
  /** @param {boolean} asked @returns {Promise<unknown>} */
  #start(asked, { present = false } = {}) {
    this.#mounting = true;
    /** @type {PromiseWithResolvers<void>} */
    const { promise: waiting, resolve: waited } = Promise.withResolvers();
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
        // A child whose server can't take it yet, or that waits for a load slot behind
        // one, may take minutes, as during a leaf.page deploy: the page presents
        // without it, and it arrives as one below the window does, its growth held
        // while seen.
        host.on("waiting", () => {
          this.#unclaimed = true;
          waited();
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
    // reader sees now. A window, and a frame below the window or scrolled past,
    // let the page present and take keys without them while they load. The page
    // reads as arriving until each started child has.
    this.#asked = asked;
    const following = this.#track(ready);
    this.#starting.resolve(following);
    const shown = following.catch(() => {});
    if (present) widgetController(this).present(Promise.race([shown, waiting]));
    /** @type {PromiseWithResolvers<void>} */
    const { promise: fitted, resolve: fit } = Promise.withResolvers();
    this.#fitted = fit;
    // A load its server makes wait arrives as news (`waiting`), so the fit is no
    // longer the landing of what brought the frame near.
    return Promise.race([fitted, shown, waiting]);
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
    const ready = this.ready;
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

  // Reset starts a child that has not started, or whose start failed.
  async reset() {
    this.#viewOperation?.abort();
    if (this.#mounting) await this.#ready;
    if (!this.#host) {
      if (!this.#pageView) return this.ready;
      this.#nearing?.();
      this.#nearing = null;
      this.#start(true);
      return this.#ready;
    }
    this.#asked = true;
    return this.#track(this.#host.reset());
  }
}

customElements.define("lf-sample", Sample);
