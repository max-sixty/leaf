/* The version picker's commands, for the floating panel's Versions list
 * (floating-panel.js), which draws its rows from `versionsReading` (version.js).
 *
 * Version travel supplies stable commands, which this owner holds for the panel. It
 * never fetches a document, chooses a version, or decides what a comparison means.
 */
const LATEST_FAILED = "Latest edit couldn't be shown";
const INITIAL_LATEST = "New page available → open v999";

/** @typedef {{activate: (entry: Readonly<import("./version.js").VersionRow>) => unknown,
 * compare: (version: number | null) => unknown, latest: () => unknown}} VersionCommands */
class VersionPicker {
  /** @type {VersionCommands["activate"] | null} */
  #activate = null;
  /** @type {VersionCommands["compare"] | null} */
  #compare = null;
  /** @type {VersionCommands["latest"] | null} */
  #latest = null;

  /** @param {VersionCommands} commands */
  configure({ activate, compare, latest }) {
    this.#activate = activate;
    this.#compare = compare;
    this.#latest = latest;
  }

  /** @param {Readonly<import("./version.js").VersionRow>} entry */
  activate(entry) {
    this.#activate?.(entry);
  }
  /** @param {number | null} version */
  compare(version) {
    this.#compare?.(version);
  }
  latest() {
    this.#latest?.();
  }
}

export const versionPicker = new VersionPicker();
/** @param {{failed?: boolean, activeLabel?: string | null}} [reading] */
export const latestVersionLabel = ({ failed = false, activeLabel = null } = {}) =>
  failed
    ? LATEST_FAILED
    : activeLabel
      ? `New page available → open ${activeLabel}`
      : INITIAL_LATEST;
