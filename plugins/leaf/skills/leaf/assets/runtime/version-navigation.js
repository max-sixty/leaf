import { runtime } from "./context.js";
import { versionUrl } from "./storage.js";

export function createVersionNavigation({
  comparable,
  el,
  latestChip,
  liveRoot,
  midComposition,
  paintDiff,
  pinned,
  poll,
  pressComparison,
  showNews,
  showVersionMenu,
  versionBtn,
  versionMenu,
  versionMenuIsOpen,
  versions,
  versionsOffered,
}) {
  let lastVersionsKey = "";
  // Navigate to a version with the pin semantics every chooser shares: an older
  // version pins the view, the newest unpins it.
  let forceActivation = false;
  const goVersion = (version) => {
    if (liveRoot && version === runtime.currentVersion) return;
    if (liveRoot && version === runtime.latestVersion) {
      forceActivation = true;
      showVersionMenu(false);
      poll();
      return;
    }
    const path = versionUrl(version);
    location.href = version === runtime.latestVersion ? path : `${path}?pin`;
  };
  function renderVersions(state) {
    versions.splice(0, versions.length, ...state.versions);
    versionBtn.disabled = !versionsOffered();
    const notes = {};
    for (const e of runtime.events) if (e.kind === "note") notes[e.version] = e.text;
    const key = JSON.stringify([state.versions, notes]);
    const current = state.versions.includes(runtime.currentVersion)
      ? runtime.currentVersion
      : null;
    // Rebuilt rather than reconciled: this runs only when the versions or their notes
    // actually changed, which on a page's whole life is a handful of times, and the
    // menu is only ever read while it is open — where a rebuild would take the focused
    // row out from under a walk. So an open menu defers the rebuild, and the key is
    // what the built list holds rather than what the last poll saw: consuming it here
    // and skipping the build inside would mark the change handled and leave that
    // version out of the menu until some later one happened along. A version arriving
    // under an open menu is the new-version chip's news; the list catches up on the
    // next poll after it closes.
    if (key !== lastVersionsKey && !versionMenuIsOpen()) {
      lastVersionsKey = key;
      versionMenu.textContent = "";
      for (const version of state.versions) {
        const isLatest = version === state.versions.at(-1);
        const row = el("button", "lf-version-row");
        row.setAttribute("role", "menuitem");
        row.dataset.lfVersion = version;
        // The version and its note are two kinds of word — which one this is, and
        // what it was — so they are two elements rather than one string. That is
        // what lets the note wrap to as many lines as it needs, which is the whole
        // reason the notes are here rather than on a control 190px wide.
        row.append(
          el("span", "lf-version-num", `v${version}${isLatest ? " (latest)" : ""}`),
        );
        if (notes[version]) row.append(el("span", "lf-version-note", notes[version]));
        if (version === current) row.setAttribute("aria-current", "true");
        row.onclick = () => {
          showVersionMenu(false);
          goVersion(version);
        };
        versionMenu.append(row);
        // The comparison this row offers, in the menu's second column beside the note
        // that says the same thing in words. A grid sibling rather than a child, a
        // button inside a button being no markup at all, and named in full: the glyph
        // is the eye's shorthand and says nothing aloud.
        if (comparable(version)) {
          const press = el("button", "lf-version-diff", "Δ");
          press.setAttribute("role", "menuitemcheckbox");
          press.dataset.lfVersion = version;
          press.setAttribute("aria-label", `Mark what changed since v${version}`);
          press.title = `Mark what changed since v${version}`;
          // The pointer's own door, and it closes the menu: the marks are on the page this
          // hangs over, and a pointer has no walk to be standing in the middle of. The
          // keyboard's is the walk itself, which leaves the list up.
          press.onclick = () => {
            showVersionMenu(false);
            pressComparison(version);
          };
          versionMenu.append(press);
        }
      }
      paintDiff(); // a fresh list, and a standing comparison to show on it
    }
    runtime.latestVersion = state.versions.at(-1) ?? null;
    const behind =
      runtime.latestVersion !== null &&
      runtime.currentVersion !== null &&
      runtime.latestVersion !== runtime.currentVersion;
    // An immutable unpinned document still follows by navigation. The live root's
    // activation decision was made before this rendering, where its fetched document and
    // the composition hold were both available. Either route leaves the chip as news
    // while it is behind.
    if (behind && !liveRoot && !pinned && !midComposition()) {
      location.replace(versionUrl(runtime.latestVersion));
      return;
    }
    showNews(latestChip, behind);
    if (behind)
      latestChip.textContent = `New version available → open v${runtime.latestVersion}`;
  }

  const activationIsForced = () => forceActivation;
  const clearForcedActivation = () => {
    forceActivation = false;
  };

  return { activationIsForced, clearForcedActivation, goVersion, renderVersions };
}
