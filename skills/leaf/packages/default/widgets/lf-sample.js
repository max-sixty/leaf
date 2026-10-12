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
 * lf-sample-ready with its sample element, on first mount, Reset and reload.
 * Each child starts loading as its sample mounts, but the containing page presents
 * before it unless the frame's resize on arrival would move what the reader sees then.
 * The sample's arrival is its child's: the child's presentation and then whatever that
 * document deferred, its own samples included, so the page reads as still arriving
 * until every child has arrived. Until then a resize the reader would see, because
 * they scrolled to the sample while it loaded, waits until it would move nothing they
 * see, the frame keeping its loading height (`heldGrowth`); a resize after Reset or
 * Return to page is the reader's own and applies at once. The status line keeps its
 * room through loading, ready and failure, so the frame below it stays put.
 * Reset stays focusable
 * while loading but accepts no new press, preserving the parent's keyboard position.
 * Ordinary children remain static
 * quotation. A disconnect releases the child; moving the retained element within a
 * document does not reset its work. */
import {
  aborted,
  deferredArrival,
  frameFor,
  growthIsSeen,
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
  heldGrowth,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-sample",
  class extends HTMLElement {
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
    // Drops a resize `heldGrowth` holds.
    #heldFit = null;
    // The current load's arrival, which lands once the child reports its own; whether
    // a resize during it waits while seen; and whether the reader asked for the load.
    #arrival;
    #landArrival;
    #arriving = false;
    #asked = false;
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
          this.#landArrival?.();
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
          host.on("arrived", () => this.#landArrival?.());
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
      // document that departs before presenting holds it until the next document,
      // which a reload brings, or Reset: the parent cannot tell a reload from an
      // external destination.
      const shown = this.#track(ready).catch(() => {});
      // The child's startup is another document's, and nothing in this page reads
      // it, so presentation waits for it only where its arrival would move what the
      // reader sees now: a block frame resizes to its child once that presents. A
      // window keeps its height, and a frame below the window or scrolled past grows
      // where the reader isn't looking, so the page presents and takes keys without
      // them while they load. The page reads as arriving until each child has.
      if (
        !this.hasAttribute("window") &&
        !isNativeLayer(this.#view) &&
        growthIsSeen(this.#frame)
      )
        widgetController(this).present(shown);
      deferredArrival(this.#arrival);
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
      keepsText(this.#full, "Full view");
      this.#setWindow(this.hasAttribute("window"));
    }

    #setWindow(value) {
      this.#host?.setWindow(value).then(
        ({ height }) => this.#height(height, { asked: true }),
        (error) => this.#failure(error),
      );
    }

    // The child owns its body observer and reports values over the private port.
    // Full view retains the embedded height while its same frame fills the dialog;
    // returning applies the current block reading without replacing any native editor.
    // A reading while the child arrives waits while its resize would be seen, unless
    // the reader `asked` for it.
    #height(height, { immediate = false, asked = false } = {}) {
      if (this.hasAttribute("window") || isNativeLayer(this.#view)) return;
      this.#heightReading = height;
      this.#heldFit?.();
      this.#heldFit = null;
      const fit = immediate ? this.#fit : this.#scheduleFit;
      if (this.#arriving && !asked) this.#heldFit = heldGrowth(this.#frame, fit);
      else fit();
    }

    // Cancellation is this widget's own, and the departed notice draws a departure.
    #failure(error) {
      if (error.name === "AbortError" || error.name === "SampleDepartedError") return;
      keepsText(this.#status, error.message);
      keeps(this.#status, "title", error.message);
      keeps(this.#reset, "aria-disabled", null);
    }

    #track(promise) {
      keeps(this.#reset, "aria-disabled", "true");
      keepsText(this.#status, "Loading sample…");
      keeps(this.#status, "title", null);
      this.#landArrival?.();
      const { promise: reported, resolve } = Promise.withResolvers();
      this.#landArrival = resolve;
      this.#arriving = !this.#asked;
      this.#asked = false;
      const ready = this.#follow(promise);
      // The child reports its arrival after its presentation, which this widget draws
      // a turn later. A failed or cancelled child has nothing more to bring.
      const arrival = ready.then(
        () => reported,
        () => {},
      );
      this.#arrival = arrival;
      void arrival.then(() => {
        if (this.#arrival === arrival) this.#arriving = false;
      });
      return ready;
    }

    // One `ready` per presentation the host promises, so a departure and the reload
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
      this.#asked = true;
      if (!this.#host) {
        this.#mount();
        return this.#ready;
      }
      return this.#track(this.#host.reset());
    }
  },
);
