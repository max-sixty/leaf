/* The generated owner of the version chooser's complete native surface.
 *
 * Version travel supplies one frozen presentation reading and stable commands. This
 * synchronous light-DOM Lit view retains the native chooser button, versions popover,
 * and latest-version chip in their separate banner and chrome seats. It owns their
 * labels, attributes, keyed rows, disclosure focus, and width reservation; it never
 * fetches a document, chooses a version, or decides what a comparison means.
 */
import { html, nothing, render, repeat } from "../vendor/browser-runtime.js";

import { anchorSurface } from "./anchoring.js";
import { walkRows } from "./keyboard/bindings.js";
import { listWalkPosition } from "./walk-position.js";
import { el, reserve } from "./widget-elements.js";

const VERSION_LABELS = Object.freeze(["Draft", "v999"]);
const LATEST_FAILED = "Latest edit couldn't be shown";
const LATEST_LABELS = Object.freeze(["New page available → open v999", LATEST_FAILED]);
const INITIAL_LATEST = LATEST_LABELS[0];
const EMPTY = Object.freeze([]);
const INITIAL = Object.freeze({
  chooser: Object.freeze({
    offered: false,
    token: "Draft",
    compared: false,
    news: false,
    keyTitle: "Draft",
    ariaLabel: "Draft",
  }),
  latest: Object.freeze({
    disabled: false,
    keyTitle: "Open the current page",
    label: INITIAL_LATEST,
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

class VersionChooserView {
  #activate = null;
  #compare = null;
  #displayedRows = EMPTY;
  #latest = null;
  #model = INITIAL;
  #toggle = null;

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
    // reading the state from a handler would see the dismissal and reopen it. `lfInvoker`
    // exposes the same relationship from the popover end to owners restoring a layer.
    this.button.popoverTargetElement = this.menu;
    this.menu.lfInvoker = this.button;
    anchorSurface(this.menu, { anchor: () => this.button, placement: "bottom-end" });
    this.menu.addEventListener("toggle", (event) => {
      const open = event.newState === "open";
      if (this.#model.chooser.offered)
        this.button.setAttribute("aria-expanded", String(open));
      if (open && !this.menu.contains(document.activeElement)) this.focusSelectedRow();
      if (!open) {
        this.#displayedRows = this.#model.rows;
        this.#renderMenu();
      }
      this.#toggle?.();
    });
    // The semantic owner supplies its one latest-version command: it releases the
    // composition hold at the live root and performs ordinary travel on an immutable
    // page. The view retains the native control without duplicating that decision.
    this.latestChip.onclick = () => this.#latest?.();
    this.present(INITIAL);
  }

  configure({ activate, compare, latest, toggle }) {
    this.#activate = activate;
    this.#compare = compare;
    this.#latest = latest;
    this.#toggle = toggle;
  }

  isOpen() {
    return this.menu.matches(":popover-open");
  }

  close() {
    if (this.isOpen()) this.menu.hidePopover();
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
    return document.activeElement === this.stops().at(end);
  }

  walk(direction) {
    return walkRows(this.rows(), direction);
  }

  walkPosition() {
    return listWalkPosition(this.rows(), document.activeElement);
  }

  numberedRoutes() {
    return this.rows()
      .map((control) => ({ control, version: +control.dataset.lfVersion }))
      .filter(({ version }) => version >= 1 && version <= 9)
      .sort((left, right) => left.version - right.version)
      .map(({ control, version }) => ({
        id: `version.open-v${version}`,
        binding: String(version),
        does: `Open v${version}`,
        line: `open v${version}`,
        control,
      }));
  }

  focusSelectedRow() {
    const { base, currentRevision } = this.#model.selection;
    (
      this.rows().find(
        (row) =>
          (base !== null && row.dataset.lfVersion === String(base)) ||
          (base === null && row.dataset.lfRevision === String(currentRevision)),
      ) ?? this.rows()[0]
    )?.focus();
  }

  reserve() {
    // Hidden pinned slots need representative words as well as a measured width: an
    // empty button is shorter, so its first real label would still move vertically.
    reserve(this.latestChip, LATEST_LABELS);
    reserve(this.button, VERSION_LABELS);
  }

  present(model) {
    this.#model = model;
    const { chooser, latest } = model;
    if (!chooser.offered) this.close();

    this.button.disabled = !chooser.offered;
    if (chooser.offered) {
      this.button.setAttribute("aria-haspopup", "menu");
      this.button.setAttribute("aria-expanded", String(this.isOpen()));
    } else {
      this.button.removeAttribute("aria-haspopup");
      this.button.removeAttribute("aria-expanded");
    }
    this.button.classList.toggle("on", chooser.compared);
    this.button.toggleAttribute("data-lf-news", chooser.news);
    this.button.dataset.lfKeyTitle = chooser.keyTitle;
    this.button.setAttribute("aria-label", chooser.ariaLabel);
    this.button.title = chooser.keyTitle;
    render(chooser.token, this.button);

    this.latestChip.disabled = latest.disabled;
    this.latestChip.dataset.lfKeyTitle = latest.keyTitle;
    this.latestChip.title = latest.keyTitle;
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

export const versionChooser = new VersionChooserView();
export const versionBtn = versionChooser.button;
export const versionMenu = versionChooser.menu;
export const latestChip = versionChooser.latestChip;
export const versionMenuIsOpen = () => versionChooser.isOpen();
export const reserveVersionControls = () => versionChooser.reserve();
export const latestVersionLabel = ({ failed = false, activeLabel = null } = {}) =>
  failed
    ? LATEST_FAILED
    : activeLabel
      ? `New page available → open ${activeLabel}`
      : INITIAL_LATEST;
