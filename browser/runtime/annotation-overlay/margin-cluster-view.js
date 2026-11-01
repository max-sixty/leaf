/* The generated child-order owner for overlay annotation controls.
 *
 * The margin projection supplies one frozen descriptor model before any DOM is
 * materialized. This synchronous light-DOM owner seats shared retained native
 * controls across direct and disclosed positions, placing both lists at once
 * (`setChildLists`) so a control moving between them keeps the user in it.
 * The overlay owns selection, keyboard state, and whole-host placement; no other code
 * inserts, moves, or removes a child inside a view.
 */
import { html, render } from "/runtime/framework.js";
import { setChildLists } from "../dom-children.js";
import {
  clearContributionControls,
  materializeContributionControls,
  contributionEntry,
  presentContributionEntry,
  presentContributionReceipts,
} from "../contribution-controls.js";
import { el, generatedElement, offer } from "../widget-elements.js";
import { keeps, keepsHidden } from "../keeps.js";
import { holdFocus } from "../focus.js";

/** @typedef {import("../contributions.js").ContributionOffer} ContributionOffer
 * @typedef {import("../contributions.js").ContributionSurface} ContributionSurface
 * @typedef {import("../margin-model.js").MarginEntry<ContributionOffer>} MarginEntry
 * @typedef {ReturnType<typeof import("../margin-model.js").clusterProjection<ContributionOffer>>} Cluster
 * @typedef {Cluster["options"]} Options
 * @typedef {Cluster["direct"][number] | Options["items"][number]} Item
 * @typedef {ReturnType<typeof createMarginClusterViewsOwner>} Owner
 * @typedef {{owner: Owner, optionsId: string}} Configuration
 */

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-margin-cluster";

/** @typedef {MarginClusterView} MarginClusterViewElement For its tag (`runtime-globals.d.ts`). */
class MarginClusterView extends HTMLElement {
  /** @type {string | null} */
  #entryKey = null;
  #marker = presentContributionEntry(
    offer("span", "lf-margin-marker"),
    contributionEntry({
      key: "reading",
      icon: "dot",
      label: "Open page details",
      behavior: "disclosure",
      rank: "reading",
    }),
    { writesRelation: false, writesSeat: false },
  );
  #more = offer("button", "lf-margin-more");
  /** @type {HTMLElement | null} */
  #options = null;
  /** @type {string | null} */
  #optionsId = null;
  /** @type {Owner | null} */
  #owner = null;
  /** @type {Cluster["toggle"] | null} */
  #toggle = null;
  /** @type {readonly ContributionOffer[]} */
  #offers = Object.freeze([]);
  /** @type {ContributionSurface | null} */
  #surface = null;

  /** @param {Configuration} configuration */
  configure({ owner, optionsId }) {
    this.#owner = owner;
    this.#optionsId = optionsId;
    this.#more.setAttribute("aria-controls", optionsId);
  }

  get marker() {
    return this.#marker;
  }

  get more() {
    return this.#more;
  }

  get options() {
    return this.querySelector(":scope > .lf-margin-options");
  }

  get primary() {
    return this.querySelector(":scope > [data-lf-margin-entry-primary]");
  }

  /** @param {Cluster} model */
  present(model) {
    if (!this.#owner) throw new Error("Margin presentation needs its view owner");
    const restoreFocus = holdFocus(this);
    this.lfEntry = model.entry;
    keeps(this, "data-lf-margin-for", model.target);
    keeps(this, "aria-label", model.label);
    this.#offers = model.offers;
    this.#surface = "margin";
    this.#owner.prepare(this.#offers, this.#surface);
    if (!this.#optionsId)
      throw new Error("Page margin presentation needs its retained controls");
    this.#entryKey = model.options.entryKey;
    const direct = this.#owner.materialize(model.direct);
    const options = this.#owner.materializeOptions(model.options);
    for (const node of direct)
      node.toggleAttribute(
        "data-lf-margin-entry-primary",
        model.hasPrimary && node === direct[0],
      );
    // Folded, the toggle stays while its options are open, after them: a pin unfolds
    // leftward from its right edge, so the toggle stays under the press that opened it.
    keepsHidden(this.#more, !model.hasOptions || (model.optionsOpen && !model.folded));
    // The toggle's face, More or the kind a folded pin folds, painted when it changes.
    if (this.#toggle !== model.toggle) {
      this.#toggle = model.toggle;
      presentContributionEntry(
        this.#more,
        contributionEntry({
          key: "options",
          action: "action" in model.toggle ? model.toggle.action : null,
          icon: "icon" in model.toggle ? model.toggle.icon : null,
          label: model.toggle.label,
          accessibleLabel: model.moreLabel,
          behavior: "disclosure",
          rank: "overflow",
        }),
        // Whether it is open is written below, from the model.
        { writesRelation: false },
      );
    }
    this.#more.lfEntry = model.entry;
    keeps(this.#more, "aria-label", model.moreLabel);
    keeps(this.#more, "aria-expanded", model.optionsOpen);
    this.toggleAttribute("data-lf-options-open", model.optionsOpen);
    this.toggleAttribute("data-lf-options-expanded", model.optionsExpanded);
    this.toggleAttribute("data-lf-folded", model.folded);
    keeps(this, "data-lf-state", model.state);
    if (!this.#options) {
      this.#options = el("div", "lf-margin-options");
      this.#options.id = this.#optionsId;
      this.#options.setAttribute("role", "group");
    }
    keeps(this.#options, "aria-label", model.options.label);
    keepsHidden(this.#options, model.options.hidden);
    this.#options.lfEntry = model.entry;
    const [marker, more, group] = [this.#marker, this.#more, this.#options];
    setChildLists([
      [
        this,
        model.folded
          ? [...direct, marker, group, more]
          : [...direct, marker, more, group],
      ],
      [group, options],
    ]);
    restoreFocus?.();
    return this.primary;
  }

  clear() {
    this.#owner?.clearOffers(this.#offers, this.#surface);
    if (this.#entryKey) this.#owner?.retire(this.#entryKey);
    this.#entryKey = null;
    this.#offers = Object.freeze([]);
    this.#surface = null;
    this.replaceChildren();
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, MarginClusterView);

/** @param {{activateContribution: Parameters<typeof materializeContributionControls>[2], materializeReading: (item: Extract<Item, {kind: "reading"}>) => HTMLElement, openSpill: (entry: MarginEntry, spill: HTMLElement) => unknown}} dependencies */
function createMarginClusterViewsOwner({
  activateContribution,
  materializeReading,
  openSpill,
}) {
  /** @type {WeakMap<import("../contributions.js").ContributionSource, HTMLElement>} */
  const contributionNotices = new WeakMap();
  /** @type {Map<string, HTMLButtonElement>} */
  const spills = new Map();

  /** @param {ContributionOffer} offered @param {ContributionSurface} surface */
  const controlsOf = (offered, surface) =>
    materializeContributionControls(offered, surface, activateContribution);

  /** @param {Item} item @returns {HTMLElement} */
  function materializeOne(item) {
    if (item.kind === "contribution") {
      const node = controlsOf(item.offered, "margin")(item.record);
      if (item.cluster) node.lfEntry = item.cluster;
      presentContributionReceipts(node, item.receipt, false);
      return node;
    }
    if (item.kind === "reading") return materializeReading(item);
    if (item.kind === "notice") {
      let node = contributionNotices.get(item.offered.source());
      if (!node) {
        node = el("span", "lf-margin-receipt");
        contributionNotices.set(item.offered.source(), node);
      }
      keeps(node, "data-lf-margin-receipt", item.notice.tone);
      render(html`${item.notice.text}`, node);
      return node;
    }
    throw new Error("Unknown margin presentation item");
  }

  /** @param {readonly Item[]} items */
  const materialize = (items) => items.map(materializeOne);
  /** @param {readonly ContributionOffer[]} offers @param {ContributionSurface} surface */
  const prepare = (offers, surface) => {
    for (const offered of offers) controlsOf(offered, surface);
  };
  /** @param {readonly ContributionOffer[]} offers @param {ContributionSurface | null} surface */
  const clearOffers = (offers, surface) => {
    if (!surface) return;
    for (const offered of offers)
      clearContributionControls(offered.source(), surface, new Set());
  };

  /** @param {Options} model */
  function materializeOptions(model) {
    const byItem = model.items.map((item) => ({ item, node: materializeOne(item) }));
    const visible = new Set(model.visible);
    for (const { item, node } of byItem) {
      node.removeAttribute("data-lf-margin-entry-primary");
      node.toggleAttribute("data-lf-margin-entry-overflow", !visible.has(item));
    }
    const shown = byItem
      .filter(({ item }) => visible.has(item))
      .map(({ node }) => node);
    if (!model.spill) {
      spills.delete(model.entryKey);
      return shown;
    }
    let spill = spills.get(model.entryKey);
    if (!spill) {
      spill = offer("button", "lf-margin-spill");
      spill.type = "button";
      spills.set(model.entryKey, spill);
    }
    presentContributionEntry(
      spill,
      contributionEntry({
        key: "all-options",
        icon: "all",
        label: model.spill.label,
        behavior: "disclosure",
        rank: "overflow",
        state: "idle",
      }),
    );
    keeps(spill, "data-lf-spill-count", model.spill.count);
    keeps(spill, "aria-label", model.spill.label);
    spill.lfFirstSpilledOption = model.spill.first;
    const control = spill;
    spill.onclick = () => openSpill(model.entry, control);
    shown.push(spill);
    return shown;
  }

  return {
    materialize,
    materializeOptions,
    prepare,
    clearOffers,
    retire: (/** @type {string} */ entryKey) => spills.delete(entryKey),
  };
}

/** @param {Parameters<typeof createMarginClusterViewsOwner>[0]} dependencies */
export function createMarginClusterViews(dependencies) {
  const owner = createMarginClusterViewsOwner(dependencies);
  /** @param {string} className @param {Omit<Configuration, "owner">} options */
  const create = (className, options) => {
    const view = document.createElement(TAG);
    view.className = className;
    generatedElement(view, { says: false });
    view.setAttribute("role", "group");
    view.configure({ owner, ...options });
    return view;
  };

  return Object.freeze({
    /** @param {MarginEntry} entry @param {Element | null} target @param {string} optionsId */
    createPage: (entry, target, optionsId) =>
      Object.assign(create("lf-ui lf-margin-cluster", { optionsId }), {
        lfEntry: entry,
        lfTarget: target,
      }),
  });
}
