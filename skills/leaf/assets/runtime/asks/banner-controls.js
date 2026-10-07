/* Generated faces for the Ask blanket answers in the banner ("Accept all (3)"). The
   banner toolbar owns the stable native buttons and their fixed overflow seats; these
   light-DOM Lit owners paint one frozen Ask presentation reading inside them. */
import { html } from "../../vendor/browser-runtime.js";
import {
  BANNER_CONTROL_RANK,
  registerBannerControl,
  showNews,
} from "../banner-toolbar.js";
import { RetainedFace } from "../retained-face.js";
import { el } from "../widget-elements.js";
import { keeps } from "../keeps.js";

const FACE_TAG = "lf-ask-banner-face";

class AskBannerFace extends RetainedFace {
  updated() {
    const control = this.parentElement;
    if (!control) return;
    // A blanket answer has no key, so its title is its name.
    keeps(control, "title", this.model.title);
    keeps(control, "aria-disabled", this.model.busy ? "true" : null);
    showNews(control, this.model.offered);
  }

  render() {
    return html`${this.model.text}`;
  }
}

if (!customElements.get(FACE_TAG)) customElements.define(FACE_TAG, AskBannerFace);

const face = (control, initial) => {
  const owner = document.createElement(FACE_TAG);
  owner.model = initial;
  owner.commit();
  owner.style.display = "contents";
  control.append(owner);
  return owner;
};

export function createAskBannerControls(activateBulk) {
  const bulk = new Map();

  function registerBulk(outcome, label) {
    if (bulk.has(outcome)) return bulk.get(outcome).control;
    const control = el("button", "lf-btn lf-answer-all", "");
    control.type = "button";
    control.onclick = () => activateBulk(outcome);
    const owner = face(
      control,
      Object.freeze({
        busy: false,
        offered: false,
        text: `${label} all (0)`,
        title: `${label} every one still waiting on you`,
        outcome,
      }),
    );
    registerBannerControl({
      key: `blanket:${outcome}`,
      control,
      rank: BANNER_CONTROL_RANK.blanket,
      conditional: true,
    });
    showNews(control, false);
    bulk.set(outcome, { control, owner });
    return control;
  }

  async function present(model) {
    try {
      await Promise.all(
        model.bulk.map((reading) => bulk.get(reading.outcome).owner.present(reading)),
      );
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
    for (const { owner } of bulk.values()) owner.commit();
  }

  async function retainCommitted() {
    await Promise.all([...bulk.values()].map(({ owner }) => owner.retainCommitted()));
  }

  return Object.freeze({
    commit,
    registerBulk,
    present,
    retainCommitted,
  });
}
