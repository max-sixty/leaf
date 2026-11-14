// lf-finalists: the picked candidates of a shortlist another widget holds.
//
// The widget keeps no picks. It reads the `shortlist` value through its `value`
// property, which Leaf sets from the output of the widget its `for` names, again
// each time that widget says `change`, and from the new element when a revision
// replaces it; a page without Leaf sets the property itself. Each Drop is an
// invoker command to that widget, which owns the picks: `command="--toggle"`
// with the candidate's key as the button's value, so the browser delivers it on
// either host and the owner records the change as its own.
import {
  LeafElement,
  html,
  nothing,
  repeat,
  offeredAction,
} from "/runtime/portable-api.js";

customElements.define(
  "lf-finalists",
  class extends LeafElement {
    static properties = { value: { attribute: false } };

    constructor() {
      super();
      this.value = null;
    }

    // Draw into the element itself on either host; it has no authored children.
    createRenderRoot() {
      return this;
    }

    render() {
      const candidates = this.value?.candidates;
      if (!candidates) {
        return html`<p class="lf-finalists-empty">No shortlist to read.</p>`;
      }
      const picked = candidates.filter((candidate) => candidate.picked);
      if (!picked.length) {
        return html`<p class="lf-finalists-empty">Nobody is picked.</p>`;
      }
      const target = this.getAttribute("for");
      return html`<ul class="lf-finalists-list">
        ${repeat(
          picked,
          (candidate) => candidate.key,
          (candidate) =>
            html`<li
              class="lf-finalists-row"
              data-lf-datum=${candidate.key}
              data-lf-identity=${candidate.key}
              data-lf-datum-label=${candidate.name}
            >
              <span class="lf-finalists-name">${candidate.name}</span>
              <button
                ${offeredAction("word", "lf-finalists-drop")}
                commandfor=${target}
                command="--toggle"
                value=${candidate.key}
                aria-label=${`Drop ${candidate.name}`}
              >
                Drop
              </button>
            </li>`,
        )}
      </ul>`;
    }

    updated(changed) {
      super.updated(changed);
      // Name the value these rows show, so a comment on a row follows its
      // candidate across new values. Nothing listens on a page without Leaf.
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value: this.value } }));
    }
  },
);
