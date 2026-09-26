/* A retained face: a light-DOM Lit owner that paints one immutable presentation reading
   at a time and keeps the last committed reading to roll back to.

   `paint(model)` assigns a reading and settles once Lit has rendered it, rejecting
   with that update's own failure. The failure is captured in `scheduleUpdate`, so Lit
   does not report a second rejected internal update beside the one failure the
   presentation coordinator owns. `present(model)` is `paint` unless a face owns more
   of its region, such as opening its presentation ticket. `commit()` makes the painted
   reading the one a later failure returns to, and `retainCommitted()` repaints it. The
   committed reading starts as the face's initial model. A face never rolls itself back:
   the presenter that paints several faces for one region decides whether an attempt
   committed, so its faces commit or retain together.

   `RowFocus` keeps focus in a keyed row list across a repaint. When the row holding
   focus leaves the list, focus moves to the nearest row that survives after it, then
   before it, and otherwise to the caller's fallback, so the user is never left on a
   node the list removed. */
import { LitElement } from "../vendor/browser-runtime.js";

export class RetainedFace extends LitElement {
  static properties = { model: { attribute: false } };

  #committed;
  #failure = null;

  constructor(initial) {
    super();
    this.model = initial;
    this.#committed = initial;
  }

  // Every descendant is generated chrome in the stable control or tray that holds it,
  // where tray styling, keyboard scopes, export, and the render gate read it.
  createRenderRoot() {
    return this;
  }

  get committed() {
    return this.#committed;
  }

  // `now` runs the update in this turn rather than the next microtask, for a face whose
  // forward gesture must be on screen in the turn that sent it.
  async paint(model, { now = false } = {}) {
    this.#failure = null;
    this.model = model;
    if (now) this.performUpdate();
    await this.updateComplete;
    if (this.#failure) throw this.#failure;
    return model;
  }

  present(model) {
    return this.paint(model);
  }

  commit() {
    this.#committed = this.model;
  }

  retainCommitted() {
    return this.paint(this.#committed);
  }

  async scheduleUpdate() {
    try {
      await super.scheduleUpdate();
    } catch (error) {
      this.#failure = error;
    }
  }
}

export class RowFocus {
  #list;
  #rows;
  #key;
  #keys;
  #pending = undefined; // a row key, null for the fallback, undefined for no move

  // `rows` selects the list's focusable rows, `key` is the attribute naming a row, and
  // `keys(model)` lists a reading's row keys in order.
  constructor(list, { rows, key, keys }) {
    this.#list = list;
    this.#rows = rows;
    this.#key = key;
    this.#keys = keys;
  }

  // Before an update replaces `prior` with `next`: note where focus goes if its row is
  // leaving.
  hold(next, prior) {
    const focused = document.activeElement?.closest?.(this.#rows);
    if (!focused || !this.#list.contains(focused)) return;
    const held = focused.getAttribute(this.#key);
    const kept = this.#keys(next);
    if (kept.includes(held)) return;
    const before = this.#keys(prior);
    const at = before.indexOf(held);
    this.#pending =
      before.slice(at + 1).find((key) => kept.includes(key)) ??
      before
        .slice(0, at)
        .reverse()
        .find((key) => kept.includes(key)) ??
      null;
  }

  // Land on a row once the update that draws it has painted, unless a move is already
  // owed.
  land(key) {
    if (this.#pending === undefined) this.#pending = key;
  }

  drop() {
    this.#pending = undefined;
  }

  // After the update: make the owed move.
  restore(fallback) {
    if (this.#pending === undefined) return;
    const key = this.#pending;
    this.#pending = undefined;
    const destination =
      key === null
        ? null
        : [...this.#list.querySelectorAll(this.#rows)].find(
            (row) => row.getAttribute(this.#key) === key,
          );
    (destination ?? fallback)?.focus();
  }
}
