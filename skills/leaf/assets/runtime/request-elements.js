/* Shared wiring for one-shot package requests. Packages supply the child tag, bound
   detail, and every reader-facing word. The holder's Lit update owns the generated
   status and waits for each generated control; authored operation nodes never enter a
   template and retain their identity for the page's whole document lifetime. */
import { LitElement, html } from "../vendor/browser-runtime.js";
import { keys as commands } from "./keyboard/scopes.js";
import { offer, quoted } from "./widget-elements.js";
import { widgetController } from "./widget-controller.js";

const CONTROL_TAG = "lf-request-control";

class RequestControl extends LitElement {
  static properties = {
    activate: { attribute: false },
    available: { attribute: false },
    controlText: { attribute: false },
    label: { attribute: false },
    requested: {
      attribute: "data-lf-requested",
      reflect: true,
      type: Boolean,
    },
  };

  constructor() {
    super();
    this.activate = null;
    this.available = false;
    this.controlText = "";
    this.label = "";
    this.requested = false;
  }

  // This element and all its children are generated. Rendering into the host keeps the
  // native button in light DOM for package themes, print, copy, and the render gate.
  createRenderRoot() {
    return this;
  }

  get control() {
    return this.querySelector(":scope > .lf-request-press");
  }

  render() {
    return html`<button
      type="button"
      class="lf-btn lf-request-press lf-ui"
      data-lf-gen="1"
      data-lf-offer="button"
      aria-label=${this.label}
      aria-disabled=${String(!this.available)}
      tabindex=${this.available ? 0 : -1}
      @click=${this.activate}
    >
      ${this.controlText}
    </button>`;
  }
}

if (!customElements.get(CONTROL_TAG))
  customElements.define(CONTROL_TAG, RequestControl);

const title = (option) =>
  option.querySelector(":scope > strong")?.textContent.trim() ||
  option.getAttribute("verb").replaceAll("-", " ");

export function defineRequestElement(
  tagName,
  {
    itemTag,
    controlText,
    commandContext,
    commandPrefix,
    commandText,
    detail,
    statusText,
  },
) {
  const children = (holder) => [...holder.querySelectorAll(`:scope > ${itemTag}`)];

  customElements.define(
    tagName,
    class extends LitElement {
      #commandsWired = false;
      #controller = null;
      #controls = [];
      #quoted = false;
      #reading = null;
      #sending = false;
      #stop = null;
      #wired = false;

      // Lit owns only this generated status region. Authored item children remain direct
      // children of the holder, and each gets its own generated request-control owner.
      createRenderRoot() {
        const root = offer("div", "lf-request-render-root");
        root.style.display = "contents";
        this.append(root);
        return root;
      }

      connectedCallback() {
        this.#quoted = quoted(this);
        super.connectedCallback();
        if (this.#quoted) return;
        this.#controller ??= widgetController(this);
        if (!this.#wired) this.#wire();
        this.#reading ??= this.#controller.read();
        this.#syncControls();
        this.#stop ??= this.#controller.subscribe((reading) => {
          this.#reading = reading;
          this.#syncControls();
          this.requestUpdate();
        });
      }

      disconnectedCallback() {
        this.#stop?.();
        this.#stop = null;
        super.disconnectedCallback();
      }

      async getUpdateComplete() {
        const complete = await super.getUpdateComplete();
        await Promise.all(this.#controls.map(({ view }) => view.updateComplete));
        this.#wireCommands();
        return complete;
      }

      #wire() {
        this.#wired = true;
        for (const option of children(this)) {
          const view = offer(CONTROL_TAG, "lf-request-control");
          view.style.display = "contents";
          view.activate = () => void this.#send(option);
          view.controlText = controlText;
          view.label = title(option);
          option.append(view);
          this.#controls.push({ option, view });
        }
      }

      #wireCommands() {
        if (this.#commandsWired || this.#quoted) return;
        if (this.#controls.some(({ view }) => !view.control)) return;
        this.#commandsWired = true;
        commands(
          this,
          commandContext,
          this.#controls.map(({ option, view }) => {
            const label = title(option);
            return {
              id: `${commandPrefix}.${option.getAttribute("verb")}`,
              keys: [],
              control: view.control,
              ...commandText(label),
              run: () => view.control.click(),
            };
          }),
          {
            answer: () => {
              const action = this.#reading?.request.latest?.request?.action;
              const selected = this.#controls.find(
                ({ option }) => option.getAttribute("verb") === action,
              );
              return selected ? title(selected.option) : "";
            },
          },
        );
      }

      #syncControls() {
        if (!this.#reading) return;
        const lifecycle = this.#reading.request;
        const request = lifecycle.latest?.request;
        const locked = this.#sending || lifecycle.phase !== "ready";
        for (const { option, view } of this.#controls) {
          const verb = option.getAttribute("verb");
          view.available =
            !locked && (this.#reading.requests[verb]?.available ?? false);
          view.requested = request?.action === verb;
        }
      }

      async #send(option) {
        const verb = option.getAttribute("verb");
        if (
          this.#sending ||
          this.#reading.request.phase !== "ready" ||
          !this.#reading.requests[verb]?.available
        )
          return;
        this.#sending = true;
        this.#syncControls();
        this.requestUpdate();
        try {
          const sent = this.#controller.dispatch({
            kind: "request",
            verb,
            detail: detail(this),
          });
          if (sent) {
            this.#reading = sent.reading;
            this.#syncControls();
            this.requestUpdate();
          }
          await sent?.delivery;
        } finally {
          this.#sending = false;
          this.#reading = this.#controller.read();
          this.#syncControls();
          this.requestUpdate();
        }
      }

      render() {
        if (this.#quoted || !this.#reading) return html``;
        const { request, receipt } = this.#reading.request.latest ?? {};
        return html`<div
          class="lf-request-status lf-ui"
          data-lf-gen="1"
          data-lf-offer=""
          role="status"
          ?hidden=${!request}
          data-status=${request ? (receipt?.status ?? "pending") : ""}
        >
          ${request ? statusText(request, receipt) : ""}
        </div>`;
      }
    },
  );
}
