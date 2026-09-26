/* The Asks tray's generated list. Its immutable row models contain only the words and
   identities the view has already derived; this retained face keys those rows by Ask id
   and keeps the native light-DOM buttons stable across presentations. */
import { html, repeat } from "../../vendor/browser-runtime.js";
import { PRESS } from "../keyboard/bindings.js";
import { keys } from "../keyboard/scopes.js";
import { RetainedFace, RowFocus } from "../retained-face.js";

export const ASK_AT = "data-lf-at";
const TAG = "lf-asks-tray-list";

const EMPTY_MODEL = Object.freeze({ open: false, rows: Object.freeze([]) });

class AskTrayList extends RetainedFace {
  #activate = null;
  #fallback = null;
  #focus = new RowFocus(this, {
    rows: `button[${ASK_AT}]`,
    key: ASK_AT,
    keys: (model) => model.rows.map(({ id }) => id),
  });
  #wired = new WeakSet();

  constructor() {
    super(EMPTY_MODEL);
  }

  configure({ activate, fallback }) {
    this.#activate = activate;
    this.#fallback = fallback;
  }

  willUpdate(changed) {
    if (!changed.has("model")) return;
    // A tray opened from its edge lands on the first row once that row exists.
    if (
      this.model.open &&
      !this.committed.open &&
      document.activeElement === this.parentElement &&
      this.model.rows.length
    ) {
      this.#focus.land(this.model.rows[0].id);
      return;
    }
    this.#focus.hold(this.model, this.committed);
  }

  updated() {
    for (const row of this.querySelectorAll(`button[${ASK_AT}]`)) {
      if (this.#wired.has(row)) continue;
      this.#wired.add(row);
      keys(row, "In the Asks tray", [
        {
          id: "ask.open",
          keys: PRESS,
          does: "Go to this ask",
          line: "go to this ask",
        },
      ]);
    }
    this.#focus.restore(this.#fallback);
  }

  #activateRow = (event) => {
    const id = event.currentTarget.getAttribute(ASK_AT);
    if (id) this.#activate?.(id);
  };

  render() {
    if (!this.model.open) return html``;
    if (!this.model.rows.length)
      return html`<div class="lf-empty">
        Nothing is waiting on you. A question the page needs an answer for appears here
        when the agent asks one.
      </div>`;
    return repeat(
      this.model.rows,
      ({ id }) => id,
      ({ id, kind, says, answer, answerState, title }) =>
        html`<button
          type="button"
          class="lf-asks-row"
          data-lf-at=${id}
          data-lf-answer-state=${answerState}
          title=${title}
          @click=${this.#activateRow}
        >
          <span class="lf-asks-kind">${kind}</span>
          <span class="lf-asks-says">${says}</span>
          <span class="lf-asks-answer">${answer}</span>
        </button>`,
    );
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, AskTrayList);

export function createAskTrayList() {
  return document.createElement(TAG);
}
