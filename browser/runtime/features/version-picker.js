// Compiled from version-picker.ts by build/typescript.mjs; edit that file.
/* The version picker's commands, for the floating panel's Versions list
 * (panel/floating-panel.js), which draws its rows from `versionsReading` (version.js).
 *
 * Version travel supplies stable commands, which this owner holds for the panel. It
 * never fetches a document, chooses a version, or decides what a comparison means.
 */

const LATEST_FAILED = "Latest edit couldn't be shown";

class VersionPicker {
  #activate = null;
  #compare = null;
  #latest = null;

  configure({ activate, compare, latest }) {
    this.#activate = activate;
    this.#compare = compare;
    this.#latest = latest;
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
}

export const versionPicker = new VersionPicker();
// The latest control's words, or null while it isn't offered: the save hasn't failed
// and the page isn't behind.
export const latestVersionLabel = ({ failed, activeLabel }) =>
  failed
    ? LATEST_FAILED
    : activeLabel
      ? `New page available → open ${activeLabel}`
      : null;
