/* The collection owns one summary of its supplied snapshots. A document revision
 * may retain the collection while replacing members, so reread their scalars at
 * the shared interface boundary. No copy of the patch inventory is maintained. */
import {
  LeafElement,
  initialRender,
  PAGE_INTERFACE,
  whileConnected,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-worktree-diffs",
  class extends LeafElement {
    #view;

    createRenderRoot() {
      return this.#view?.root ?? this;
    }

    setup() {
      this.#view = initialRender(this);
      const update = () => {
        this.requestUpdate();
        this.performUpdate();
      };
      whileConnected(this, (signal) => {
        update();
        this.ownerDocument.addEventListener(PAGE_INTERFACE, update, { signal });
      });
    }

    render() {
      return this.#view.render();
    }
  },
);
