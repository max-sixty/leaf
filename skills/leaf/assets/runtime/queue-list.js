/* The Queue panel's generated list. EXPERIMENTAL: the panel is a first cut at one place
   for what waits on the user and on the agent, and its groups, rows and words are
   expected to change a lot.

   Its immutable reading holds only the words and identities `queue-panel.js` has
   already derived: the two queues, each a heading with its count over its rows, then
   what is done, folded behind a native disclosure at the foot. This retained face keys
   the rows by item and keeps their light-DOM buttons stable across presentations. A row
   standing at an element, an Ask's or a widget's the user must act on, names it in
   `data-lf-at`, so the row stands at that element (`declareSide`, queue-panel.js) and
   mirrors the ring of the Ask the user stands in (asks/view.js, `markHere`). The fold's
   open state is the disclosure's own, a browser fact the reading never holds.

   A row whose task the user ends with Done carries a Done button beside it, which Tab
   reaches from the row and a finger taps, and `x` on the row presses it. Pressing it
   puts focus on its row first, so focus follows the list as the row leaves for Done. */
import { html, nothing, repeat } from "../vendor/browser-runtime.js";
import { PRESS } from "./keyboard/bindings.js";
import { keys } from "./keyboard/scopes.js";
import { RetainedFace, RowFocus } from "./retained-face.js";

const QUEUE_AT = "data-lf-at";
const QUEUE_ROW = "data-lf-row";
const QUEUE_DONE = "data-lf-done";
const ROW = `button[${QUEUE_ROW}]`;
const DONE = `button[${QUEUE_DONE}]`;
const TAG = "lf-queue-list";

const EMPTY_MODEL = Object.freeze({
  open: false,
  queues: Object.freeze([]),
  done: Object.freeze({ label: "", rows: Object.freeze([]) }),
});
const rowKeys = (model) =>
  [...model.queues.flatMap(({ rows }) => rows), ...model.done.rows].map(
    ({ key }) => key,
  );

const rowTemplate = (row, activate, finish) =>
  html`<div class="lf-queue-item">
    <button
      type="button"
      class="lf-queue-row"
      data-lf-row=${row.key}
      data-lf-at=${row.at ?? nothing}
      data-lf-kind=${row.kind}
      data-lf-live=${row.live ? "" : nothing}
      title=${row.account}
      @click=${activate}
    >
      <span class="lf-queue-kind">${row.word}</span>
      <span class="lf-queue-title">${row.title}</span>
      <span class="lf-queue-where">${row.where}</span>
    </button>
    ${
      row.done
        ? html`<button
            type="button"
            class="lf-btn lf-queue-finish"
            data-lf-done=${row.key}
            aria-label=${`Done: ${row.title}`}
            @click=${finish}
          >
            Done
          </button>`
        : nothing
    }
  </div>`;

const rowsTemplate = (rows, activate, finish) =>
  html`<div class="lf-queue-rows">
    ${repeat(
      rows,
      ({ key }) => key,
      (row) => rowTemplate(row, activate, finish),
    )}
  </div>`;

class QueueList extends RetainedFace {
  #activate = null;
  #finish = null;
  #fallback = null;
  #focus = new RowFocus(this, {
    rows: `button[${QUEUE_ROW}]`,
    key: QUEUE_ROW,
    keys: rowKeys,
  });
  #wired = new WeakSet();

  constructor() {
    super(EMPTY_MODEL);
  }

  configure({ activate, finish, fallback }) {
    this.#activate = activate;
    this.#finish = finish;
    this.#fallback = fallback;
  }

  willUpdate(changed) {
    if (!changed.has("model")) return;
    // A panel opened from its edge lands on the first row once that row exists.
    const first = rowKeys(this.model)[0];
    if (
      this.model.open &&
      !this.committed.open &&
      document.activeElement === this.parentElement &&
      first !== undefined
    ) {
      this.#focus.land(first);
      return;
    }
    this.#focus.hold(this.model, this.committed);
  }

  // Whether the row keyed `key` ends its task at Done in the reading drawn now.
  #ends(key) {
    return this.model.queues.some(({ rows }) =>
      rows.some((row) => row.key === key && row.done),
    );
  }

  // Done on the row keyed `key`, from its button or its key, standing on the row first.
  #end(key) {
    this.querySelector(`${ROW}[${QUEUE_ROW}="${CSS.escape(key)}"]`)?.focus({
      preventScroll: true,
    });
    this.#finish?.(key);
  }

  updated() {
    for (const row of this.querySelectorAll(ROW)) {
      if (this.#wired.has(row)) continue;
      this.#wired.add(row);
      keys(row, "In the Queue", [
        { id: "queue.row.open", keys: PRESS, title: "go to this item" },
        {
          id: "queue.row.done",
          keys: ["x"],
          title: "done",
          description: "Mark this task waiting on you done",
          when: () => this.#ends(row.getAttribute(QUEUE_ROW)),
          run: () => this.#end(row.getAttribute(QUEUE_ROW)),
        },
      ]);
    }
    for (const done of this.querySelectorAll(DONE)) {
      if (this.#wired.has(done)) continue;
      this.#wired.add(done);
      keys(done, "On a task's Done", [
        { id: "queue.done.press", keys: PRESS, title: "mark it done" },
      ]);
    }
    this.#focus.restore(this.#fallback);
  }

  #activateRow = (event) => {
    const key = event.currentTarget.getAttribute(QUEUE_ROW);
    if (key) this.#activate?.(key);
  };

  #finishRow = (event) => {
    const key = event.currentTarget.getAttribute(QUEUE_DONE);
    if (key) this.#end(key);
  };

  render() {
    if (!this.model.open) return html``;
    const { queues, done } = this.model;
    return html`${queues.map(
      ({ id, label, rows, empty }) =>
        html`<div class="lf-queue-group" data-lf-queue=${id}>
          <div class="lf-queue-heading" role="heading" aria-level="3">${label}</div>
          ${
            rows.length
              ? rowsTemplate(rows, this.#activateRow, this.#finishRow)
              : html`<div class="lf-queue-empty">${empty}</div>`
          }
        </div>`,
    )}
    ${
      done.rows.length
        ? html`<details class="lf-queue-group lf-queue-done" data-lf-queue="done">
            <summary class="lf-queue-heading">${done.label}</summary>
            ${rowsTemplate(done.rows, this.#activateRow, this.#finishRow)}
          </details>`
        : nothing
    }`;
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, QueueList);

export function createQueueList() {
  return document.createElement(TAG);
}

// The row standing at the element `id` names in an open list, or null: the row an
// Ask's ring is mirrored on and an arrival at that Ask reveals.
export const rowAt = (list, id) =>
  [...list.querySelectorAll(`${ROW}[${QUEUE_AT}]`)].find(
    (row) => row.getAttribute(QUEUE_AT) === id,
  ) ?? null;

// The id of the element the row holding `node` stands at, or null.
export const standsAt = (node) =>
  node.closest(`${ROW}[${QUEUE_AT}]`)?.getAttribute(QUEUE_AT) ?? null;

// The items an open list shows, in order: the rows of either queue, and Done's while it
// is open.
export const shownItems = (list) =>
  [...list.querySelectorAll(ROW)].filter(
    (row) => !row.closest(".lf-queue-done:not([open])"),
  );

// What a walk down the list stops at: its items, with Done's door in its place
// between them.
export const walkStops = (list) =>
  [...list.querySelectorAll(`${ROW}, .lf-queue-done > summary`)].filter(
    (stop) => stop.matches("summary") || !stop.closest(".lf-queue-done:not([open])"),
  );
