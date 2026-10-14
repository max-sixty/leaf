/* The generated owner of the version picker's complete native surface.
 *
 * Version travel supplies one frozen presentation reading and stable commands. This
 * synchronous light-DOM Lit view retains the native picker button, versions popover,
 * and latest-version chip in their separate banner and chrome seats. It owns their
 * labels, attributes, keyed rows, and disclosure focus, all but the `title`: a control
 * names itself in `data-lf-key-title`, and the keyboard pass writes the title that adds
 * its shortcut (keyboard/control-keys.js), so each has one writer. It never
 * fetches a document, chooses a version, or decides what a comparison means.
 */
import { closeNativeLayer } from "./keyboard/layer-stack.js";
import { isNativeLayer } from "./shadow-tree.js";
import { html, nothing, render, repeat } from "/vendor/browser-runtime.js";

import { dismissBannerControls } from "./banner-toolbar.js";
import { el } from "./widget-elements.js";
import { keeps } from "./keeps.js";
import { focusDestination, canPlaceFocus, inputCount, focused } from "./focus.js";
import { scrollIntoView } from "./landing-scroll.js";

const LATEST_FAILED = "Latest edit couldn't be shown";
const INITIAL_LATEST = "New page available → open v999";
const EMPTY = Object.freeze([]);
const INITIAL = Object.freeze({
  picker: Object.freeze({
    offered: false,
    token: "Showing Draft",
    compared: false,
    news: false,
    keyTitle: "Draft",
    ariaLabel: "Draft",
  }),
  latest: Object.freeze({
    disabled: false,
    keyTitle: "Open the current page",
    label: INITIAL_LATEST,
    shown: null,
  }),
  rows: EMPTY,
  selection: Object.freeze({
    base: null,
    currentRevision: null,
    on: false,
    pendingBase: null,
    baseRevision: null,
  }),
});

class VersionPickerView {
  #activate = null;
  #compare = null;
  #displayedRows = EMPTY;
  #latest = null;
  #model = INITIAL;
  #toggle = null;
  #openingInput = null;

  constructor() {
    this.button = el("button", "lf-btn lf-version");
    this.menu = el("div", "lf-ui lf-version-menu");
    this.latestChip = el("button", "lf-ui lf-btn lf-latest-chip");

    this.menu.id = "lf-versions";
    this.menu.setAttribute("popover", "auto");
    this.menu.setAttribute("role", "menu");
    this.menu.setAttribute("aria-label", "Versions");
    // Use the platform's invoker relationship rather than toggling from a click handler.
    // A press on an open auto-popover's invoker is both a light dismissal and a press;
    // reading the state from a handler would see the dismissal and reopen it. The
    // relationship also exposes the button's expanded state natively.
    this.button.setAttribute("popovertarget", this.menu.id);
    this.menu.addEventListener("beforetoggle", (event) => {
      if (event.newState === "open") {
        this.#openingInput = inputCount();
        dismissBannerControls();
      }
    });
    this.menu.addEventListener("toggle", (event) => {
      if (event.newState === "open") {
        // The platform has now opened the popover and completed its autofocus.
        // Arrive on the selected row without revealing an outer sample frame.
        const arrival = this.#selectedRow();
        // The toggle event is deferred. A key can move the user inside the open
        // menu first; its arrival wins over the picker's initial placement.
        if (arrival && canPlaceFocus() && inputCount() === this.#openingInput) {
          focusDestination(arrival, "move");
          scrollIntoView(arrival, { block: "nearest" });
        }
      } else {
        this.#openingInput = null;
        this.#displayedRows = this.#model.rows;
        this.#renderMenu();
      }
      this.#toggle?.();
    });
    // The semantic owner supplies its one latest-version command: it releases the
    // composition hold at the live root and performs ordinary travel on an immutable
    // page. The view retains the native control without duplicating that decision.
    this.latestChip.onclick = () => this.latest();
    this.present(INITIAL);
  }

  configure({ activate, compare, latest, toggle }) {
    this.#activate = activate;
    this.#compare = compare;
    this.#latest = latest;
    this.#toggle = toggle;
  }

  isOpen() {
    return isNativeLayer(this.menu);
  }

  close() {
    if (this.isOpen()) closeNativeLayer(this.menu);
  }

  rows() {
    return [...this.menu.querySelectorAll(".lf-version-row")];
  }

  stops() {
    return [...this.menu.querySelectorAll("button:not(:disabled)")].filter(
      (control) => control.getClientRects().length,
    );
  }

  atBoundary(end) {
    return focused() === this.stops().at(end);
  }

  #selectedRow() {
    const { base, currentRevision } = this.#model.selection;
    return (
      this.rows().find((row) =>
        base !== null
          ? row.dataset.lfVersion === String(base)
          : row.dataset.lfRevision === String(currentRevision),
      ) ?? this.rows()[0]
    );
  }

  numberedRoutes() {
    return this.rows()
      .map((control) => ({ control, version: +control.dataset.lfVersion }))
      .filter(({ version }) => version >= 1 && version <= 9)
      .sort((left, right) => left.version - right.version)
      .map(({ control, version }) => ({
        id: `version.open-v${version}`,
        binding: String(version),
        title: `open v${version}`,
        control,
      }));
  }

  // The picker's commands, and word of each reading it presents, for another
  // presentation of the same versions, the floating panel's Versions view, which draws
  // its own rows from `versionsReading` (version.js).
  #listeners = new Set();
  watch(listener) {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }
  activate(entry) {
    this.#activate?.(entry);
  }
  compare(version) {
    this.#compare?.(version);
  }
  latest() {
    this.#latest?.();
  }

  present(model) {
    this.#model = model;
    for (const listener of this.#listeners) listener(model);
    const { picker, latest } = model;
    if (!picker.offered) this.close();

    // A disabled invoker has no popover target, so it announces no menu either.
    this.button.toggleAttribute("disabled", !picker.offered);
    keeps(this.button, "aria-haspopup", picker.offered ? "menu" : null);
    this.button.classList.toggle("on", picker.compared);
    this.button.toggleAttribute("data-lf-news", picker.news);
    keeps(this.button, "data-lf-key-title", picker.keyTitle);
    keeps(this.button, "aria-label", picker.ariaLabel);
    render(picker.token, this.button);

    this.latestChip.toggleAttribute("disabled", latest.disabled);
    keeps(this.latestChip, "data-lf-key-title", latest.keyTitle);
    render(latest.label, this.latestChip);

    if (!this.isOpen()) this.#displayedRows = model.rows;
    this.#renderMenu();
  }

  #renderMenu() {
    const { selection } = this.#model;
    render(
      html`${repeat(
        this.#displayedRows,
        // Draft and stamped destinations can share a revision and remain distinct.
        (entry) => `${entry.version === null ? "draft" : "version"}:${entry.revision}`,
        (entry) => {
          const compared =
            selection.on &&
            selection.baseRevision !== null &&
            entry.revision >= selection.baseRevision &&
            entry.revision <= selection.currentRevision;
          const pending = entry.version === selection.pendingBase;
          return html`
            <button
              class=${`lf-version-row${compared ? " lf-compared" : ""}`}
              role="menuitem"
              data-lf-revision=${entry.revision}
              data-lf-version=${entry.version ?? nothing}
              aria-current=${entry.current ? "true" : nothing}
              @click=${() => {
                this.close();
                this.#activate?.(entry);
              }}
            >
              <span class="lf-version-num">${entry.name}</span>
              ${
                entry.note
                  ? html`<span class="lf-version-note">${entry.note}</span>`
                  : nothing
              }
            </button>
            ${
              entry.comparable
                ? html`<button
                    class="lf-version-diff"
                    role="menuitemcheckbox"
                    data-lf-version=${entry.version}
                    aria-label=${`Compare with v${entry.version}`}
                    title=${`Mark what changed since v${entry.version}`}
                    aria-checked=${String(
                      pending || (selection.on && entry.version === selection.base),
                    )}
                    aria-busy=${pending ? "true" : nothing}
                    @click=${() => {
                      this.close();
                      this.#compare?.(entry.version);
                    }}
                  >
                    Compare
                  </button>`
                : nothing
            }
          `;
        },
      )}`,
      this.menu,
    );
  }
}

export const versionPicker = new VersionPickerView();
export const versionBtn = versionPicker.button;
export const versionMenu = versionPicker.menu;
export const latestChip = versionPicker.latestChip;
export const versionMenuIsOpen = () => versionPicker.isOpen();
// The browser owns top-layer state, light dismissal and the handback. What it restores
// focus to on a hide is the element that had it when the popover showed — not the
// `source`, which buys the anchor and the invoker relationship and nothing about focus
// — so every door into this menu shows it from the button, and a pointer press that
// lands on the button gets it back. Escape is Leaf's, and the menu's own row performs
// the whole of it: the close, and then the menu's parent. The picker stands in More,
// so the menu opens from inside More and a layer's one step lands the user back there,
// on the picker, whichever route opened it. Scoping the platform handback to its door
// rather than to the state is what keeps it off a light dismissal, which restores
// nothing on purpose: a user who pressed away into the page is left where they
// pressed.
export const closeVersionMenu = () => versionPicker.close();
export const latestVersionLabel = ({ failed = false, activeLabel = null } = {}) =>
  failed
    ? LATEST_FAILED
    : activeLabel
      ? `New page available → open ${activeLabel}`
      : INITIAL_LATEST;
