/* lf-sample: quoted content, or a complete live page authored in a template.
 * The shared host owns the child page and its independent event log. The frame
 * keeps its CSS allocation while its child loads and scrolls inside it. Parent
 * presentation includes that loading surface, independently of child readiness.
 * A `window` sample is a whole Leaf window, chrome included. The child's
 * final Escape brings focus back to this element. Full view promotes the same frame
 * into a native modal dialog, keeping its document, gestures, and drafts alive. The
 * Full view waits for the child's reading capture; repeated presses renew that
 * same pending action. A newer parent action cancels the eventual promotion. The
 * sample retains its embedded allocation while the dialog fills the viewport; Return
 * to page and the child's final Escape restore the Full view button. Each child announces
 * lf-sample-ready with its sample element, on first mount and Reset. Reset stays focusable
 * while loading but accepts no new press, preserving the parent's keyboard position.
 * Ordinary children remain static
 * quotation. A disconnect releases the child; moving the retained element within a
 * document does not reset its work. */
import {
  whileConnected,
  keeps,
  keepsText,
  mountSample,
  once,
  initialRender,
  widgetController,
  focusDestination,
  closeLayer,
  showNativeLayer,
  closeNativeLayer,
  handBack,
  elementAxes,
  deferredArrival,
  retainUserIntent,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-sample",
  class extends HTMLElement {
    #host;
    #frame;
    #template;
    #reset;
    #status;
    #ready;
    #focusedContent = false;
    #mounting = false;
    #viewOperation;
    #view;
    #full;
    #inspection;

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
          this.#inspection = null;
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
      if (
        this.#view?.getAttribute("role") === "dialog" &&
        !this.#view.matches(":modal")
      )
        this.#embed();
      if (!this.#frame || this.#host || this.#mounting) return;
      this.#mounting = true;
      const ready = mountSample(this.#frame, {
        template: this.#template.id,
        window: this.hasAttribute("window") || this.#view.matches(":modal"),
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
          host.on("loading", () => this.#track(host.ready));
          host.on("standing", ({ focused }) => {
            this.#focusedContent = focused;
          });
          host.on("departed", () => {
            this.#focusedContent = false;
            this.#ready = host.ready;
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
      // The parent has presented this stable frame and its loading controls.
      // Only the sample's public promise waits for the independent child page.
      this.#track(ready);
      widgetController(this).present(Promise.resolve());
    }

    disconnectedCallback() {
      if (this.#view?.getAttribute("role") === "dialog") this.#embed();
    }

    #build() {
      const drawing = initialRender(this);
      if (!drawing) return;
      this.#template = drawing.template;
      this.#frame = drawing.frame;
      this.#view = drawing.view;
      this.#reset = drawing.reset;
      this.#full = drawing.full;
      this.#status = drawing.status;
      const { controls } = drawing;
      this.#frame.addEventListener("lf-sample-return", () => {
        if (this.#view.matches(":modal")) this.#return();
        else focusDestination(this, "return");
      });

      this.#view.addEventListener("cancel", (event) => {
        event.preventDefault();
        this.#return();
      });

      this.#reset.addEventListener("click", () => {
        if (this.#reset.ariaDisabled === "true") return;
        this.reset().catch(() => {}); // #track paints the failed operation.
      });
      this.#full.addEventListener("click", () => {
        if (this.#view.matches(":modal")) this.#return();
        else if (this.#inspection)
          this.#inspection.intent = retainUserIntent({ source: this.#full });
        else {
          const inspection = { intent: retainUserIntent({ source: this.#full }) };
          const promote = () => {
            if (this.#inspection !== inspection || !this.isConnected) return;
            this.#inspection = null;
            if (!inspection.intent()) return;
            // The frame never moves in the DOM: reparenting it destroys its browsing
            // context. Native modality supplies focus containment and parent isolation.
            // The label stays in flow; reserve only the controls and frame leaving it.
            const height =
              (this.#frame.getBoundingClientRect().bottom -
                controls.getBoundingClientRect().top) /
              elementAxes(this).y.y;
            this.style.setProperty("--lf-sample-height", `${height}px`);
            closeNativeLayer(this.#view);
            this.#view.setAttribute("role", "dialog");
            this.#view.setAttribute("aria-label", this.#frame.title);
            keepsText(this.#full, "Return to page");
            showNativeLayer(this.#view);
            this.#setWindow(true);
            focusDestination(this.#full, "move");
          };
          this.#inspection = inspection;
          // A loading child has no reading to hand back. Otherwise capture its
          // landmark before changing the viewport, under this exact press.
          if (!this.#host?.presented) promote();
          else
            this.#host.call("inspection", { opening: true }).then(
              () => promote(),
              (error) => {
                this.#failure(error);
                // Departure or failure leaves no child reading to capture, but
                // the same retained press still owns opening its current frame.
                promote();
              },
            );
        }
      });
      keeps(this.#reset, "disabled", null);
      keeps(this.#full, "disabled", null);
    }

    #return() {
      closeLayer(
        () => this.#embed(),
        () => handBack(this.#full),
      );
    }

    #embed() {
      this.#inspection = null;
      closeNativeLayer(this.#view);
      // Initial open markup keeps the embedded group visible without the native
      // focusing steps of show(), which could scroll the containing page.
      this.#view.setAttribute("open", "");
      this.#view.setAttribute("role", "presentation");
      this.#view.removeAttribute("aria-label");
      this.style.removeProperty("--lf-sample-height");
      keepsText(this.#full, "Full view");
      // Both commands enter the same private port in order, before a later Full
      // view press can capture another place. No old reply may clear a new hold.
      this.#setWindow(this.hasAttribute("window"));
      this.#host
        ?.call("inspection", { opening: false })
        .catch((error) => this.#failure(error));
    }

    #setWindow(value) {
      this.#host?.setWindow(value).catch((error) => this.#failure(error));
    }

    #failure(error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      keepsText(this.#status, error.message);
      keeps(this.#reset, "aria-disabled", null);
    }

    #track(promise) {
      this.#focusedContent = false;
      keeps(this.#reset, "aria-disabled", "true");
      keepsText(this.#status, "Loading sample…");
      const ready = promise.then(async (reading) => {
        if (this.#ready !== ready) return reading;
        await this.#host.setWindow(
          this.hasAttribute("window") || this.#view.matches(":modal"),
        );
        if (this.#ready !== ready) return reading;
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
      deferredArrival(ready, { layout: false });
      ready.catch((error) => {
        if (this.#ready === ready) this.#failure(error);
      });
      return this.#ready;
    }

    // Latest selection wins, including a selection waiting on a replacement child.
    // The outer control remains the keyboard stop while the child draws its view.
    async showThread(id, { surface = "page", status, waiting } = {}) {
      this.#viewOperation?.abort();
      const operation = new AbortController();
      this.#viewOperation = operation;
      const { signal } = operation;
      const ready = this.#ready;
      let cancelled;
      const cancellation = new Promise((resolve) => {
        cancelled = () => resolve(false);
        signal.addEventListener("abort", cancelled, { once: true });
      });
      const select = async () => {
        if (signal.aborted || ready !== this.#ready || !this.isConnected) return false;
        const shown = await this.#host.showThread(id, {
          surface,
          status,
          waiting,
          signal,
        });
        if (signal.aborted || ready !== this.#ready || !this.isConnected) return false;
        return shown;
      };
      try {
        return await Promise.race([ready.then(select), cancellation]);
      } finally {
        signal.removeEventListener("abort", cancelled);
      }
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
  },
);
