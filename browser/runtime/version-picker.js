/* The version picker's reading and commands, for the floating panel's Versions list
 * (floating-panel.js), which draws its rows from `versionsReading` (version.js).
 *
 * Version travel supplies one frozen presentation reading and stable commands, which
 * this owner holds between them. It never fetches a document, chooses a version, or
 * decides what a comparison means.
 */
const LATEST_FAILED = "Latest edit couldn't be shown";
const INITIAL_LATEST = "New page available → open v999";

class VersionPicker {
  #activate = null;
  #compare = null;
  #latest = null;
  #listeners = new Set();

  configure({ activate, compare, latest }) {
    this.#activate = activate;
    this.#compare = compare;
    this.#latest = latest;
  }

  // Word of each reading it presents, for a presentation that draws the versions.
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
    for (const listener of this.#listeners) listener(model);
  }
}

export const versionPicker = new VersionPicker();
export const latestVersionLabel = ({ failed = false, activeLabel = null } = {}) =>
  failed
    ? LATEST_FAILED
    : activeLabel
      ? `New page available → open ${activeLabel}`
      : INITIAL_LATEST;
