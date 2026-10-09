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
   committed, so its faces commit or retain together. A face that keeps the user on
   its rows across a repaint holds them with a keyed `holdFocus` (focus.js). */
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

  // Every descendant is generated chrome in the stable control or drawer that holds it,
  // where drawer styling, keyboard scopes, export, and the render gate read it.
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
