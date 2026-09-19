/* The generated accessibility note beside each authored block carrying comments.
 *
 * Anchor paint supplies one immutable count and first-thread reading per block. Each
 * synchronous light-DOM Lit owner retains one native button while its authored holder
 * remains live. The outer element is the rendering and removal boundary: Lit never
 * claims, wraps, or rewrites the holder's authored or widget-owned children.
 */
import { LitElement, html, nothing } from "../vendor/browser-runtime.js";
import { pressOrigin } from "./keyboard/layer-stack.js";

// `lf-*` is reserved for authored widgets. This is generated runtime apparatus.
const TAG = "leaf-anchor-note";

class AnchorNoteView extends LitElement {
  static properties = {
    model: { attribute: false },
  };

  #openThread = null;

  constructor() {
    super();
    this.model = null;
  }

  createRenderRoot() {
    return this;
  }

  configure({ openThread }) {
    if (this.#openThread) throw new Error("The anchor note view is already configured");
    this.#openThread = openThread;
  }

  present(model) {
    if (!Object.isFrozen(model))
      throw new Error("Anchor note presentation models must be immutable");
    this.model = model;
    this.performUpdate();
  }

  #activate = () => {
    if (this.model?.firstThreadId)
      this.#openThread(this.model.firstThreadId, {
        focus: "thread",
        origin: pressOrigin(),
      });
  };

  render() {
    if (!this.model) return nothing;
    return html`<button
      type="button"
      class="lf-mark-note lf-ui"
      data-lf-gen="1"
      data-lf-offer="button"
      .textContent=${this.model.label}
      @click=${this.#activate}
    ></button>`;
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, AnchorNoteView);

const noteModel = (threadIds) => {
  const count = threadIds.length;
  return Object.freeze({
    count,
    firstThreadId: threadIds[0],
    label: `${count} comment${count === 1 ? "" : "s"}`,
  });
};

export function createAnchorNoteProjection({ openThread }) {
  const hosts = new Map();

  function present(notes) {
    const kept = new Set();
    for (const [holder, threadIds] of notes) {
      let host = hosts.get(holder);
      if (!host?.isConnected) {
        host = document.createElement(TAG);
        host.className = "lf-anchor-note-host lf-ui";
        host.dataset.lfGen = "1";
        host.configure({ openThread });
        holder.append(host);
        hosts.set(holder, host);
      }
      host.present(noteModel(threadIds));
      kept.add(holder);
    }
    for (const [holder, host] of hosts)
      if (!kept.has(holder)) {
        host.remove();
        hosts.delete(holder);
      }
  }

  function destroy() {
    for (const host of hosts.values()) host.remove();
    hosts.clear();
  }

  return { present, destroy };
}
