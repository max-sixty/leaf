/* lf-sample: quoted content, or a complete live page authored in a template.
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
 * reload. Its loading saved state does not hold the parent. Reset stays focusable
 * while loading but accepts no new press, preserving the parent's keyboard position.
 * Ordinary children remain static
 * quotation. A disconnect releases the child; moving the retained element within a
 * document does not reset its work. */
import {
  aborted,
  frameFor,
  whileConnected,
  keeps,
  keepsText,
  layoutPx,
  mountSample,
  once,
  offer,
  widgetController,
  focusDestination,
  closeLayer,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  handBack,
} from "/runtime/widget-api.js";

export default class extends HTMLElement {
  #host;
  #frame;
  #template;
  #reset;
  #status;
  #heightReading;
  #fit = () => {
    const frame = this.#frame;
    frame.style.height = `${this.#heightReading + frame.offsetHeight - frame.clientHeight}px`;
  };
  #scheduleFit = frameFor(this, this.#fit);
  #ready;
  #following;
  #focusedContent = false;
  #mounting = false;
  #viewOperation;
  #view;
  #full;

  get ready() {
    return this.#ready;
  }

  get focusedContent() {
    return this.#focusedContent;
  }

  restoreStanding() {
    return this.#host?.call("restore-standing");
  }

  connectedCallback() {
    if (!once(this)) return;
    this.#build();
    if (!this.#frame) return;
    whileConnected(this, () => {
      this.#mount();
      return () => {
        this.#viewOperation?.abort();
        const host = this.#host;
        this.#host = null;
        host?.destroy().catch((error) => this.#failure(error));
      };
    });
  }

  #mount() {
    // Removal ends native modality even when a retained widget reconnects before
    // its host is retired. Reconcile the presentation with that platform state.
    if (this.#view?.getAttribute("role") === "dialog" && !isNativeLayer(this.#view))
      this.#embed();
    if (!this.#frame || this.#host || this.#mounting) return;
    this.#mounting = true;
    const ready = mountSample(this.#frame, {
      template: this.#template.id,
      window: this.hasAttribute("window") || isNativeLayer(this.#view),
      // The child reads with the chrome its element names, else with the reader's own.
      chrome: this.getAttribute("chrome") ?? document.documentElement.lfChrome?.mode,
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
        host.on("loading", () => {
          this.#focusedContent = false;
          this.#track(host.ready);
        });
        host.on("standing", ({ focused }) => {
          this.#focusedContent = focused;
        });
        // The departed document's frame shows the browser's destination, which
        // Reset replaces; a reload's `loading` follows the same promise.
        host.on("departed", () => {
          this.#focusedContent = false;
          this.#follow(host.ready);
          keepsText(this.#status, "");
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
    // completed parent rendering; the public sample.ready still rejects. A first
    // document that departs before upgrading holds it until the next document,
    // which a reload brings, or Reset: the parent cannot tell a reload from an
    // external destination.
    widgetController(this).present(this.#track(ready).catch(() => {}));
  }

  // Removal closes a modal Full view at once, so the view returns to its embedded
  // posture in the same task rather than at the arrival batch.
  disconnectedCallback() {
    if (this.#view?.getAttribute("role") === "dialog") this.#embed();
  }

  #build() {
    this.#template = this.querySelector(":scope > template[data-sample]");
    if (!this.#template) return;
    this.dataset.lfSampleLive = "";
    this.#frame = document.createElement("iframe");
    this.#frame.className = "lf-sample-frame";
    this.#frame.title = this.getAttribute("label") || "Leaf sample";
    this.#frame.addEventListener("lf-sample-return", () => {
      if (isNativeLayer(this.#view)) this.#return();
      else focusDestination(this, "return");
    });

    this.#view = document.createElement("dialog");
    this.#view.className = "lf-sample-view";
    this.#view.dataset.lfGen = "1";
    this.#view.setAttribute("open", "");
    this.#view.setAttribute("role", "presentation");
    this.#view.addEventListener("cancel", (event) => {
      event.preventDefault();
      this.#return();
    });

    const controls = document.createElement("div");
    controls.className = "lf-sample-controls lf-ui";
    controls.dataset.lfGen = "1";
    const actions = document.createElement("div");
    this.#reset = offer("button", "lf-btn", "Reset");
    this.#reset.addEventListener("click", () => {
      if (this.#reset.ariaDisabled === "true") return;
      this.reset().catch(() => {}); // #track paints the failed operation.
    });
    this.#status = offer("span", "lf-sample-status");
    this.#status.setAttribute("role", "status");
    this.#full = offer("button", "lf-btn", "Full view");
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
        keepsText(this.#full, "Return to page");
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
  }

  #return() {
    closeLayer(
      () => this.#embed(),
      () => handBack(this.#full),
    );
    if (this.#heightReading !== undefined)
      this.#height(this.#heightReading, { immediate: true });
  }

  #embed() {
    closeNativeLayer(this.#view);
    // Initial open markup keeps the embedded group visible without the native
    // focusing steps of show(), which could scroll the containing page.
    this.#view.setAttribute("open", "");
    this.#view.setAttribute("role", "presentation");
    this.#view.removeAttribute("aria-label");
    this.style.removeProperty("--lf-sample-height");
    keepsText(this.#full, "Full view");
    this.#setWindow(this.hasAttribute("window"));
  }

  #setWindow(value) {
    this.#host?.setWindow(value).then(
      ({ height }) => this.#height(height),
      (error) => this.#failure(error),
    );
  }

  // The child owns its body observer and reports values over the private port.
  // Full view retains the embedded height while its same frame fills the dialog;
  // returning applies the current block reading without replacing any native editor.
  #height(height, { immediate = false } = {}) {
    if (this.hasAttribute("window") || isNativeLayer(this.#view)) return;
    this.#heightReading = height;
    if (immediate) this.#fit();
    else this.#scheduleFit();
  }

  // Cancellation is this widget's own, and the departed notice draws a departure.
  #failure(error) {
    if (error.name === "AbortError" || error.name === "SampleDepartedError") return;
    keepsText(this.#status, error.message);
    keeps(this.#reset, "aria-disabled", null);
  }

  #track(promise) {
    keeps(this.#reset, "aria-disabled", "true");
    keepsText(this.#status, "Loading sample…");
    return this.#follow(promise);
  }

  // One `ready` per usable document the host promises, so a departure and the reload
  // that follows it are one wait for a selection or a page module.
  #follow(promise) {
    if (promise === this.#following) return this.#ready;
    this.#following = promise;
    const ready = promise.then(async (reading) => {
      if (this.#ready !== ready) return reading;
      const current = await this.#host.setWindow(
        this.hasAttribute("window") || isNativeLayer(this.#view),
      );
      if (this.#ready !== ready) return reading;
      this.#height(current.height, { immediate: true });
      keeps(this.#reset, "aria-disabled", null);
      keepsText(this.#status, "");
      this.dispatchEvent(
        new CustomEvent("lf-sample-ready", {
          bubbles: true,
          detail: { sample: this },
        }),
      );
      return reading;
    });
    this.#ready = ready;
    ready.catch((error) => {
      if (this.#ready === ready) this.#failure(error);
    });
    return this.#ready;
  }

  // Latest selection wins, including a selection waiting on a replacement child.
  // A departing child takes the selection's command with it but not the selection,
  // which waits for the next document as it waits for the first. A newer
  // selection, Reset or removal supersedes it. The outer control remains the
  // keyboard stop while the child draws its view.
  async showThread(id, { surface = "page", status, waiting } = {}) {
    this.#viewOperation?.abort();
    const operation = new AbortController();
    this.#viewOperation = operation;
    const { signal } = operation;
    const select = (ready) =>
      ready
        .then(() =>
          signal.aborted
            ? false
            : this.#host.showThread(id, { surface, status, waiting, signal }),
        )
        .catch((error) => {
          // The departure that rejected it has already promised the next document.
          if (error.name !== "SampleDepartedError" || ready === this.#ready)
            throw error;
          return select(this.#ready);
        });
    return Promise.race([select(this.#ready), aborted(signal).then(() => false)]);
  }

  async reset() {
    this.#viewOperation?.abort();
    if (this.#mounting) await this.#ready;
    if (!this.#host) {
      this.#mount();
      return this.#ready;
    }
    return this.#track(this.#host.reset());
  }
}
