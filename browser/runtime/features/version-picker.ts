/* The version picker's commands, for the floating panel's Versions list
 * (panel/floating-panel.js), which draws its rows from `versionsReading` (version.js).
 *
 * Version travel supplies stable commands, which this owner holds for the panel. It
 * never fetches a document, chooses a version, or decides what a comparison means.
 */
import type { VersionRow } from "./version.js";
const LATEST_FAILED = "Latest edit couldn't be shown";

type VersionCommands = {
  activate: (entry: Readonly<VersionRow>) => unknown;
  compare: (version: number | null) => unknown;
  latest: () => unknown;
};
class VersionPicker {
  #activate: VersionCommands["activate"] | null = null;
  #compare: VersionCommands["compare"] | null = null;
  #latest: VersionCommands["latest"] | null = null;

  configure({ activate, compare, latest }: VersionCommands) {
    this.#activate = activate;
    this.#compare = compare;
    this.#latest = latest;
  }

  activate(entry: Readonly<VersionRow>) {
    this.#activate?.(entry);
  }
  compare(version: number | null) {
    this.#compare?.(version);
  }
  latest() {
    this.#latest?.();
  }
}

export const versionPicker = new VersionPicker();
// The latest control's words, or null while it isn't offered: the save hasn't failed
// and the page isn't behind.
export const latestVersionLabel = ({
  failed,
  activeLabel,
}: {
  failed: boolean;
  activeLabel: string | null;
}): string | null =>
  failed
    ? LATEST_FAILED
    : activeLabel
      ? `New page available → open ${activeLabel}`
      : null;
