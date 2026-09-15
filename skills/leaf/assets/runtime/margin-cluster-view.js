/* The generated child-order owner for page and conversation margin controls.
 *
 * The margin projection supplies one frozen descriptor model before any DOM is
 * materialized. This synchronous light-DOM Lit owner retains native controls by
 * contribution and entry identity, then places them across the direct, disclosed, and
 * inline seats. The projection still owns semantic selection, keyboard state, and
 * whole-host placement; no other code inserts, moves, or removes a child inside a view.
 */
import { html, nothing, render, repeat } from "../vendor/browser-runtime.js";
import {
  clearMarginEntryControls,
  createMarginEntryControl,
  marginEntry,
  marginEntryControlMatches,
  marginEntryRecord,
  presentMarginEntry,
  trackMarginEntryControl,
} from "./margin-entries.js";
import { el, keeps, keepsHidden, offer } from "./widget-elements.js";

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-margin-cluster";

class MarginClusterView extends HTMLElement {
  #entryKey = null;
  #marker = null;
  #more = null;
  #optionsId = null;
  #owner = null;
  #offers = Object.freeze([]);
  #surface = null;

  configure({ owner, marker = null, more = null, optionsId = null }) {
    this.#owner = owner;
    this.#marker = marker;
    this.#more = more;
    this.#optionsId = optionsId;
  }

  get options() {
    return this.querySelector(":scope > .lf-margin-options");
  }

  get primary() {
    return this.querySelector(":scope > [data-lf-margin-entry-primary]");
  }

  present(model) {
    if (!Object.isFrozen(model))
      throw new Error("Margin presentation models must be immutable");
    if (!this.#owner) throw new Error("Margin presentation needs its view owner");
    const standing = this.contains(document.activeElement)
      ? document.activeElement
      : null;
    this.lfEntry = model.entry;
    keeps(this, "data-lf-margin-for", model.target);
    keeps(this, "aria-label", model.label);
    this.#offers = model.offers;
    this.#surface = model.kind === "inline" ? "inline" : "margin";
    this.#owner.prepare(this.#offers, this.#surface);
    if (model.kind === "inline") {
      const nodes = this.#owner.materialize(model.items);
      for (const node of nodes) node.removeAttribute("data-lf-margin-entry-primary");
      render(html`${this.#owner.nodes(nodes)}`, this);
      if (standing?.isConnected && document.activeElement !== standing)
        standing.focus({ preventScroll: true });
      return null;
    }
    if (!this.#marker || !this.#more || !this.#optionsId)
      throw new Error("Page margin presentation needs its retained controls");
    this.#entryKey = model.options.entryKey;
    const direct = this.#owner.materialize(model.direct);
    const options = this.#owner.materializeOptions(model.options);
    for (const node of direct)
      node.toggleAttribute(
        "data-lf-margin-entry-primary",
        model.hasPrimary && node === direct[0],
      );
    keepsHidden(this.#more, !model.hasOptions || model.optionsOpen);
    this.#more.lfEntry = model.entry;
    keeps(this.#more, "aria-label", model.moreLabel);
    keeps(this.#more, "aria-expanded", model.optionsOpen);
    this.toggleAttribute("data-lf-options-open", model.optionsOpen);
    keeps(this, "data-lf-state", model.state);
    render(
      html`
        ${this.#owner.nodes(direct)} ${this.#marker} ${this.#more}
        <div
          class="lf-margin-options"
          id=${this.#optionsId}
          role="group"
          aria-label=${model.options.label}
          ?hidden=${model.options.hidden}
          .lfEntry=${model.entry}
        >
          ${this.#owner.nodes(options)}
        </div>
      `,
      this,
    );
    if (standing?.isConnected && document.activeElement !== standing)
      standing.focus({ preventScroll: true });
    return this.primary;
  }

  clear() {
    this.#owner?.clearOffers(this.#offers, this.#surface);
    if (this.#entryKey) this.#owner?.retire(this.#entryKey);
    this.#entryKey = null;
    this.#offers = Object.freeze([]);
    this.#surface = null;
    render(nothing, this);
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, MarginClusterView);

export function createMarginClusterViews({
  activateContribution,
  materializeReading,
  openSpill,
}) {
  const contributionControls = new WeakMap();
  const contributionNotices = new WeakMap();
  const spills = new Map();
  let relationOrdinal = 0;

  function controlsOf(offered, surface) {
    let controls = contributionControls.get(offered);
    if (!controls) {
      controls = new Map();
      contributionControls.set(offered, controls);
    }
    const entries = offered.reading.entries.filter((entry) => entry.visible);
    const liveKeys = new Set(entries.map((entry) => entry.key));
    const changed = new Set();
    for (const key of controls.keys()) if (!liveKeys.has(key)) controls.delete(key);
    for (const entry of entries) {
      let control = controls.get(entry.key);
      if (!control || !marginEntryControlMatches(control, entry)) {
        control = createMarginEntryControl(entry);
        controls.set(entry.key, control);
        changed.add(control);
      } else if (marginEntryRecord(control) !== entry) changed.add(control);
      control.onclick = (event) =>
        activateContribution({ offered, entry, control, surface, event });
      trackMarginEntryControl(offered, surface, entry.key, control);
    }
    clearMarginEntryControls(offered, surface, liveKeys);
    for (const entry of entries) {
      const control = controls.get(entry.key);
      const related =
        entry.relation?.kind === "entries"
          ? entry.relation.keys.map((key) => controls.get(key)).filter(Boolean)
          : [];
      related.forEach((node, index) => {
        if (!node.id) node.id = `lf-margin-related-${++relationOrdinal}-${index + 1}`;
      });
      if (changed.has(control))
        presentMarginEntry(control, entry, {
          relatedControlIds: related.map((node) => node.id),
        });
    }
    return controls;
  }

  function materializeOne(item) {
    if (item.kind === "contribution") {
      const node = controlsOf(item.offered, item.surface).get(item.record.key);
      if (item.cluster) node.lfEntry = item.cluster;
      return node;
    }
    if (item.kind === "reading") return materializeReading(item);
    if (item.kind === "notice") {
      let node = contributionNotices.get(item.offered);
      if (!node) {
        node = el("span", "lf-margin-receipt");
        contributionNotices.set(item.offered, node);
      }
      keeps(node, "data-lf-margin-receipt", item.notice.tone);
      render(html`${item.notice.text}`, node);
      return node;
    }
    throw new Error(`Unknown margin presentation item: ${item.kind}`);
  }

  const materialize = (items) => items.map(materializeOne);
  const nodes = (items) =>
    repeat(
      items,
      (node) => node,
      (node) => node,
    );
  const prepare = (offers, surface) => {
    for (const offered of offers) controlsOf(offered, surface);
  };
  const clearOffers = (offers, surface) => {
    if (!surface) return;
    for (const offered of offers) clearMarginEntryControls(offered, surface, new Set());
  };

  function materializeOptions(model) {
    const all = materialize(model.items);
    const byItem = new Map(model.items.map((item, index) => [item, all[index]]));
    const visible = new Set(model.visible);
    for (const [item, node] of byItem) {
      node.removeAttribute("data-lf-margin-entry-primary");
      node.toggleAttribute("data-lf-margin-entry-overflow", !visible.has(item));
    }
    const shown = model.visible.map((item) => byItem.get(item));
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
    presentMarginEntry(
      spill,
      marginEntry({
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
    spill.lfFirstSpilledOption = byItem.get(model.spill.first);
    spill.onclick = () => openSpill(model.entry, spill);
    shown.push(spill);
    return shown;
  }

  const owner = {
    materialize,
    materializeOptions,
    nodes,
    prepare,
    clearOffers,
    retire: (entryKey) => spills.delete(entryKey),
  };
  const create = (className, options = {}) => {
    const view = document.createElement(TAG);
    view.className = className;
    view.dataset.lfGen = "1";
    view.setAttribute("role", "group");
    view.configure({ owner, ...options });
    return view;
  };

  return Object.freeze({
    createInline: () => create("lf-ui lf-margin-inline"),
    createPage: (marker, more, optionsId) =>
      create("lf-ui lf-margin-cluster", { marker, more, optionsId }),
  });
}
