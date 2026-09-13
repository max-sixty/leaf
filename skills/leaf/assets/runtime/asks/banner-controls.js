/* Generated faces for the Asks banner controls. The banner shelf owns the stable native
   buttons and may move them between its row and overflow menu; these light-DOM Lit
   owners move with those buttons and paint one frozen Ask presentation reading. */
import { LitElement, html } from "../../vendor/browser-runtime.js";
import { foldShelf, showNews } from "../banner-shelf.js";
import { el } from "../widget-elements.js";

const FACE_TAG = "lf-ask-banner-face";
const EMPTY_PROGRESS = Object.freeze({
  complete: false,
  offered: false,
  text: "",
  title: "Show or hide this page's asks",
});

class AskBannerFace extends LitElement {
  static properties = { model: { attribute: false } };

  #committed = null;
  #failure = null;
  kind = null;

  constructor() {
    super();
    this.model = EMPTY_PROGRESS;
  }

  createRenderRoot() {
    return this;
  }

  async present(model) {
    this.#failure = null;
    this.model = model;
    await this.updateComplete;
    if (this.#failure) throw this.#failure;
    return model;
  }

  commit() {
    this.#committed = this.model;
  }

  async retainCommitted() {
    this.#failure = null;
    if (this.#committed) this.model = this.#committed;
    await this.updateComplete;
    if (this.#failure) throw this.#failure;
    return this.#committed;
  }

  async scheduleUpdate() {
    try {
      await super.scheduleUpdate();
    } catch (error) {
      this.#failure = error;
    }
  }

  updated() {
    const control = this.parentElement;
    if (!control) return;
    if (control.title !== this.model.title) control.title = this.model.title;
    if (this.kind === "progress") {
      if (control.dataset.lfKeyTitle !== this.model.title)
        control.dataset.lfKeyTitle = this.model.title;
      control.toggleAttribute("data-lf-complete", this.model.complete);
    } else {
      if (this.model.busy) control.setAttribute("aria-disabled", "true");
      else control.removeAttribute("aria-disabled");
    }
    showNews(control, this.model.offered);
  }

  render() {
    return html`${this.model.text}`;
  }
}

if (!customElements.get(FACE_TAG)) customElements.define(FACE_TAG, AskBannerFace);

const face = (control, kind) => {
  const owner = document.createElement(FACE_TAG);
  owner.kind = kind;
  owner.style.display = "contents";
  control.append(owner);
  return owner;
};

export function createAskBannerControls(progress, activateBulk) {
  const progressFace = face(progress, "progress");
  const bulk = new Map();

  function registerBulk(verb, label) {
    if (bulk.has(verb)) return bulk.get(verb).control;
    const control = el("button", "lf-btn lf-answer-all", "");
    control.type = "button";
    control.onclick = () => activateBulk(verb);
    const owner = face(control, "bulk");
    const initial = Object.freeze({
      busy: false,
      offered: false,
      text: `${label} all (0)`,
      title: `${label} every one still waiting on you`,
      verb,
    });
    owner.model = initial;
    owner.commit();
    showNews(control, false);
    bulk.set(verb, { control, owner });
    return control;
  }

  async function present(model) {
    try {
      await Promise.all([
        progressFace.present(model.progress),
        ...model.bulk.map((reading) => bulk.get(reading.verb).owner.present(reading)),
      ]);
      // showNews coalesces ordinary batches. The presentation boundary asks for the final
      // reparenting now so readiness includes the shelf position and any focus handoff.
      foldShelf();
    } catch (error) {
      try {
        await retainCommitted();
      } catch (retaining) {
        throw new AggregateError(
          [error, retaining],
          "Ask banner presentation and retention failed",
        );
      }
      throw error;
    }
    return model;
  }

  function commit() {
    progressFace.commit();
    for (const { owner } of bulk.values()) owner.commit();
  }

  async function retainCommitted() {
    await Promise.all([
      progressFace.retainCommitted(),
      ...[...bulk.values()].map(({ owner }) => owner.retainCommitted()),
    ]);
    foldShelf();
  }

  return Object.freeze({
    commit,
    progressFace,
    registerBulk,
    present,
    retainCommitted,
  });
}

export const askProgressModel = (completed, total, offered) => {
  const title = total
    ? `${completed} of ${total} asks answered — show or hide the list`
    : "Show or hide this page's asks";
  return Object.freeze({
    complete: total > 0 && completed === total,
    offered,
    text: `Asks ${completed}/${total}`,
    title,
  });
};
