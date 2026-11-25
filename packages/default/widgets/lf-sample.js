/* lf-sample: inline content (quoted by default, interactive on the parent page
 * when declared), or a complete live page authored in a template. Its `label` is its
 * name wherever Leaf names it, and nothing draws it: the page introduces a sample in
 * its own words, and a caption it shows is the author's HTML, such as a `<figure>`'s
 * `<figcaption>`. The user chose this, as for option and board cards (lf-options.js):
 * a name Leaf reads is data apart from any title the page shows. The inline modes need
 * no controller; the registry owns their quotation semantics.
 * The shared host owns the child page, its independent event log and the frame's
 * height (host/sample.js): the frame takes its child's height, so the surrounding page
 * scrolls the sample like any other block and focus moves into it the way it moves into
 * any iframe, and a resize the reader did not ask for waits while it would move what
 * they see. A `window`
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
 * started. A frame the reader sees as it mounts starts at once, in the task that
 * shows it to them, the page arriving or a view they opened: the host makes that
 * showing wait for the frame's fit to its child only where it starts in that task.
 * The sample's arrival is its child's,
 * which the host counts; a frame waiting to start counts until the
 * browser's first reading of it has said whether it starts (`whenNear`). The status line
 * keeps its room through loading, ready and failure, so the frame below it stays put; a
 * failure's words that run past it stand in a disclosure the reader opens over the
 * frame.
 * Reset stays focusable
 * while loading but accepts no new press, preserving the parent's keyboard position.
 * Ordinary children remain static
 * quotation. A disconnect releases the child; moving the retained element within a
 * document does not reset its work. */
import {
  growthIsSeen,
  whileConnected,
  mountSample,
  focusDestination,
  whenNear,
} from "/runtime/widget-api.js";
import { nameAction, offer, offerAction } from "/runtime/lib/controls.js";
import { once } from "/runtime/lib/once.js";
import { keeps, keepsText, layoutPx } from "/runtime/lib/keeps.js";
import { describeFailure } from "/runtime/lib/exception.js";

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
  // Whether the view stands over the page as Full view's modal dialog.
  get #modal() {
    return this.#view.matches(":modal");
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
        const host = this.#host;
        this.#host = null;
        host?.destroy().catch((/** @type {unknown} */ error) => this.#failure(error));
      };
    });
  }

  #mount() {
    // Removal ends native modality even when a retained widget reconnects before
    // its host is retired. Reconcile the presentation with that platform state.
    if (this.#pageView?.view.getAttribute("role") === "dialog" && !this.#modal)
      this.#embed();
    if (!this.#pageView || this.#host || this.#mounting || this.#nearing) return;
    // A frame the reader sees as it mounts is part of what they are being shown, the
    // page arriving or a view they opened, such as a thread in the floating panel: it
    // starts at once, in the task that shows it, so that showing waits for its resize
    // to its child (host/sample.js). Any other starts as it nears the window. A window
    // keeps its height.
    if (!this.hasAttribute("window") && !this.#modal && growthIsSeen(this.#frame)) {
      this.#start();
      return;
    }
    this.#nearing = whenNear(this.#frame, () => {
      this.#nearing = null;
      this.#start();
    });
  }

  #start() {
    this.#mounting = true;
    const ready = mountSample(this.#frame, {
      template: this.#template.id,
      window: this.hasAttribute("window") || this.#modal,
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
        });
        return host.ready;
      },
      (error) => {
        this.#mounting = false;
        throw error;
      },
    );
    // A failed child is drawn by this widget's status and Reset. That is a
    // completed parent rendering; the public sample.ready still rejects. The child's
    // startup is another document's, and nothing in this page reads it: a window, and
    // a frame below the window or scrolled past, let the page present and take keys
    // without them while they load. The page reads as arriving until each started
    // child has.
    this.#starting.resolve(this.#track(ready));
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
      if (this.#modal) this.#return();
      else focusDestination(this, "return");
    });

    this.#view.className = "lf-sample-view";
    keeps(this.#view, "data-lf-gen", "1");
    this.#view.setAttribute("open", "");
    this.#view.setAttribute("role", "presentation");
    this.#view.addEventListener("cancel", (event) => {
      event.preventDefault();
      this.#return();
    });

    const controls = document.createElement("div");
    controls.className = "lf-sample-controls lf-ui";
    keeps(controls, "data-lf-gen", "1");
    const actions = document.createElement("div");
    this.#reset.addEventListener("click", () => {
      if (this.#reset.ariaDisabled === "true") return;
      this.reset().catch(() => {}); // #track paints the failed operation.
    });
    this.#status.setAttribute("role", "status");
    this.#paintFull(false);
    this.#full.addEventListener("click", () => {
      if (this.#modal) this.#return();
      else {
        // The frame never moves in the DOM: reparenting it destroys its browsing
        // context. Native modality supplies focus containment and parent isolation.
        // Reserve the height of the controls and frame leaving the flow.
        const height =
          this.#frame.getBoundingClientRect().bottom -
          controls.getBoundingClientRect().top;
        this.style.setProperty("--lf-sample-height", layoutPx(height));
        this.#view.close();
        this.#view.setAttribute("role", "dialog");
        this.#view.setAttribute("aria-label", this.#frame.title);
        this.#paintFull(true);
        this.#view.showModal();
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

  // The browser hands focus back to wherever it stood as Full view opened: the Full
  // view button inside the view the close hides, or, where a press leaves a button
  // unfocused, wherever the user was before. So the user is put on that button once
  // the view stands embedded again.
  #return() {
    this.#embed();
    focusDestination(this.#full, "return");
  }

  #embed() {
    this.#view.close();
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
    this.#host
      ?.setWindow(value)
      .catch((/** @type {unknown} */ error) => this.#failure(error));
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
    disclosure.append(offer("summary", "lf-disclosure-marker", message));
    this.#status.replaceChildren(disclosure);
    this.#disclosure = disclosure;
  }

  // Draw the frame's next document loading; the host counts its arrival (host/sample.js).
  /** @param {Promise<SampleReady>} promise */
  #track(promise) {
    keeps(this.#reset, "aria-disabled", "true");
    this.#say("Loading sample…");
    return this.#follow(promise);
  }

  // One `ready` per usable document the host promises, so a departure and the reload
  // that follows it are one wait for a selection or a page module. The sample draws
  // the document ready in the turn the host learns it is, before the document reports
  // its arrival, which the host counts until then (host/sample.js). A command to the
  // document awaited first would let the page read arrived while the sample still drew
  // it loading. A posture the document doesn't stand in yet, as one changed while the
  // host was mounting, reaches it now.
  /** @param {Promise<SampleReady>} promise */
  #follow(promise) {
    if (promise === this.#following?.source) return this.#following.ready;
    const ready = promise.then((reading) => {
      if (this.#ready !== ready) return reading;
      const asWindow = this.hasAttribute("window") || this.#modal;
      if (reading.block === asWindow) this.#setWindow(asWindow);
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
    /** @type {Promise<boolean>} */
    const superseded = new Promise((resolve) =>
      signal.addEventListener("abort", () => resolve(false), { once: true }),
    );
    return Promise.race([shown, superseded]);
  }

  // Reset starts a child that has not started, or whose start failed.
  async reset() {
    this.#viewOperation?.abort();
    if (this.#mounting) await this.#ready;
    if (!this.#host) {
      if (!this.#pageView) return this.ready;
      this.#nearing?.();
      this.#nearing = null;
      this.#start();
      return this.#ready;
    }
    return this.#track(this.#host.reset());
  }
}

customElements.define("lf-sample", Sample);
