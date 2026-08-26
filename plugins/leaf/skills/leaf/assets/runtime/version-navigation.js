import { runtime } from "./context.js";
import { PRESS, walkRows } from "./keyboard/bindings.js";
import { versionUrl } from "./storage.js";

export function createVersionNavigation({
  allButTheReference,
  comparable,
  comparisonBase,
  el,
  keys,
  latestChip,
  liveRoot,
  midComposition,
  paintDiff,
  paintHere,
  pinned,
  poll,
  pressComparison,
  setDiff,
  showComparison,
  showNews,
}) {
  const versions = runtime.versions;
  // The version chooser: a press that says which version this is, and a menu that says
  // what each one was and what it changed. It was a <select>, and the two things that
  // cost were both the control's rather than the styling's. A select takes its inner
  // height from Chrome's own metrics and refuses line-height, so it could never stand
  // level with the buttons beside it; and its closed label is its selected option's whole
  // text, so the note had to be in both places or neither — 190px of bar, the widest
  // control on the row, for about nine characters of a note that then ellipsized. A press
  // states the version alone, and the menu is the only place the notes are, where a row
  // can wrap and carry one whole.
  //
  // The diff was a second press beside it, and everything the two shared was in the
  // menu already. It named the previous version because a control with one label can
  // offer one base, and the previous version is the least useful of them on a page that
  // ships a version whenever the work moves: what the reader wants marked is what has
  // changed since they last looked, which is as far back as they were away. The base is
  // the menu's to say, so every version older than this one offers itself as one.
  //
  // Which version this is, is the live document's answer, so the
  // press says it now rather than standing empty until the first poll answers, and the
  // only word it ever rewrites is the Δ that says a comparison is standing — enumerable,
  // so the room for it is taken from the words themselves at load (reserve) and the
  // control still cannot move the row. It is a word rather than the accent alone because
  // a reader who leaves a comparison on and scrolls into a stretch that changed nothing
  // has only this control to read it back off, and a colour is not a thing a screen
  // reader announces.
  const versionLabel = (comparing) =>
    (comparing ? "Δ " : "") +
    (runtime.currentVersion === null ? "▾" : `v${runtime.currentVersion} ▾`);
  const versionBtn = el("button", "lf-btn lf-version", versionLabel(false));
  // Nothing to open until the log says what versions there are, and a control that answers
  // nothing is a way in painted where there is no layer behind it — the same reason the
  // page's own approve button waits for the page. `versionsOffered` is what the key and the
  // menu already read; this is the pointer's half of it, cleared by renderVersions.
  versionBtn.disabled = true;
  versionBtn.setAttribute("aria-haspopup", "menu");
  versionBtn.setAttribute("aria-expanded", "false");
  const versionMenu = el("div", "lf-ui lf-version-menu");
  versionMenu.setAttribute("role", "menu");
  versionMenu.setAttribute("aria-label", "Versions");
  let versionMenuOpen = false;
  // Two facts about the versions, which had been one comparison spelled in three places and
  // read as though it answered both. Whether there is a menu to open is not whether there is
  // anything in it to walk: a first version has no neighbour to step to, and its menu still
  // holds that version and the note saying what it changed, which is the whole reason the
  // chooser is a menu rather than a select.
  //
  // Conflated, they left the menu's way in live over a page its way out was not. `v` opened
  // on any page while the mode binding the menu's Escape stood only above one version, so on
  // the commonest page there is — a page with one version — `v` raised a menu no key could
  // put down: the Escape chip read "back to the page", focus fell to body, and the menu
  // stayed painted. A layer owes a way out over exactly the pages its way in is live on, and
  // the way to keep that true is to stop asking one question for both.
  //
  // Named the way the trays name theirs (`leavesOffered`, `asksOffered`), so the next
  // surface to ask reads the fact rather than spelling a comparison of its own.
  const versionsOffered = () => versions.length > 0;
  const versionsToWalk = () => versions.length > 1;
  // The walk is the versions, not every press in the menu.
  const versionRows = () => [...versionMenu.querySelectorAll(".lf-version-row")];
  // One setter stating the whole outcome, per showComposer and showFab: nothing reads
  // the class back to find out whether the menu is up.
  function showVersionMenu(open) {
    versionMenuOpen = open;
    versionMenu.classList.toggle("open", open);
    versionBtn.setAttribute("aria-expanded", String(open));
    // Opening lands on the version being read, so the menu's own keys are the next
    // press rather than a Tab-hunt — the same move o makes into the leaves tray.
    //
    // Or on the standing base, where a comparison is up, because inside this menu the focused
    // row *is* the base (the walk below). Landing on the version being read instead left the
    // two disagreeing at the one moment the reader cannot see it coming: their first arrow
    // press would have moved the base off the version they had marked from to the neighbour of
    // the one they are reading, silently, with the marks redrawn to match.
    if (open)
      (
        versionRows().find(
          (r) =>
            r.dataset.lfVersion === String(comparisonBase() ?? runtime.currentVersion),
        ) ?? versionRows()[0]
      )?.focus();
    else if (versionMenu.contains(document.activeElement)) versionBtn.focus();
    paintHere();
  }
  // The pointer's door, held to the same fact as the key's: a button that opened a menu
  // nothing could close would put the trap back for the reader who never touches the
  // keyboard.
  versionBtn.onclick = () => showVersionMenu(versionsOffered() && !versionMenuOpen);
  // The menu's own scope. The walk is the menu's rather than the page's, because ArrowUp and
  // ArrowDown anywhere else are the page's own scroll; ⏎ is the browser's, a row being a
  // button, and the row says so with no `run`. A row's Δ is the same comparison for the
  // pointer, which has no walk to state it with, and takes no key of its own.
  //
  // v is the second half of the motion that opened the menu, and the one row worth a key of
  // its own: the newest version is where the walk ends, and where a reader who came for the
  // current state is going. The letter is the menu's here for the walk's own kind of reason
  // — outside it, v is already the chooser — and being the inner scope's is what shadows the
  // page's v, where the two listeners used to depend on one consuming the press.
  //
  // The scope is live while there is a list to walk. The menu's *way out* is not — it is the
  // mode's below, on the wider fact that there is a menu at all, because a layer's Escape
  // has to hold wherever the layer does. Reading one predicate for both is what left `v`
  // opening a menu on a page whose Escape no scope was live to bind: the reader's next press
  // was the page's own rung, focus fell to body, and the menu stayed painted. So this scope
  // answers "is there anything to walk" and the mode answers "is there a menu", and the
  // reference's section is the two of them merged by title — on a first version, the way out
  // and nothing else.
  const NEWEST = {
    keys: ["v"],
    does: "Open the newest version",
    line: "open the newest version",
    // Through its own row's press, so the key leaves the menu by the door the pointer uses —
    // the menu closes and the pin lifts, both goVersion's and showVersionMenu's to say,
    // neither restated here. There is always a row to press: the scope holds only with focus
    // inside the menu, and an open lands focus on a row.
    run: () => versionRows().at(-1).click(),
  };
  keys(
    versionMenu,
    "In the versions menu",
    [
      {
        keys: ["ArrowUp", "ArrowDown"],
        // The walk marks as it goes, which is what the list is for: the note says in words
        // what a version changed and the page behind the menu then says it in the passages
        // themselves, without the reader having to leave the list to find out. A note is
        // Claude's sentence about a version and the marks are the version's own account of
        // itself, so reading them together is the only way to tell the two apart.
        does: "Walk the versions, marking what changed since the one you are on",
        line: "walk — marking changes",
        repeat: true,
        run: (binding) => {
          const was = document.activeElement;
          const row = walkRows(versionRows(), binding === "ArrowDown" ? 1 : -1);
          // A press at either end lands on the row it started from, and now that the walk
          // states a comparison, landing is not free — it would re-fetch the base and toast
          // its count again for a press that moved nothing.
          if (!row || row === was) return;
          // The comparison the row states: its own version as the base, or none at all where
          // that version is not older than the one being read. So the reader walks up to mark
          // from further back and back down to stop, and the row that stops it is the version
          // they are reading — the end of the walk in the direction they came from, which is
          // why it needs no key of its own and no reader has to be told where it is — and,
          // the page having no key for a comparison, the whole of the way off one.
          const version = +row.dataset.lfVersion;
          if (comparable(version)) showComparison(version);
          else setDiff(false);
        },
      },
      // The browser's own, the row being a real <button> — no `run`, or the press would
      // click a control the platform has already activated. The word is the line's all the
      // same, and the keys are the shared fact rather than this row's reading of it:
      // spelled by hand, it said Enter and left Space unnamed on a control that answers
      // both.
      { keys: PRESS, does: "Open that version", line: "open that version" },
      NEWEST,
    ],
    versionsToWalk,
  );
  // The way out is the menu standing, not the reader being inside it: a menu opened and
  // then Tabbed out of is still over the page, and an Escape that could not reach it left
  // the reader closing the panel underneath instead. So the rung is a mode rather than the
  // element scope's — which is what every other layer that can outlive its own focus does
  // (the composer holds a draft the reader clicked away from; the leaves tray stands while
  // focus is on the button that opened it). The menu's walk stays the element scope's,
  // because a walk has nothing to walk unless focus is on a row.
  const VERSIONS = {
    title: "In the versions menu",
    // The way out is live wherever the way in is, which is the wider fact and not the walk's:
    // a menu holding one version is still a layer the reader is standing in, and its Escape
    // is the only key that ends it. Stated as the walk's liveness, this scope went quiet on
    // exactly the page where the menu could not otherwise be closed.
    when: versionsOffered,
    at: () => versionMenuOpen,
    // A mode over the page suspends the page, which the two modes above this one always did
    // and this one did not — so a reader in the middle of choosing a version could press `l`
    // and take focus out of the menu into the leaves tray, `d` and scroll a page they were
    // not looking at, or `c` and open the composer under the list. None of it fails loudly:
    // the press does exactly what it says on a page the reader has stopped reading. The
    // worst of them was a page-level key that set a comparison base, which the walk they
    // were standing in then disagreed with — that key is the menu's own business now, and
    // the claim is what would have held it either way. The claim is also what narrows
    // the line to the menu's own keys, so what the mode takes and what it offers are one
    // statement rather than a suspension the surfaces have to be told about separately.
    claims: allButTheReference,
    rows: [
      {
        keys: ["Escape"],
        does: "Close the versions menu",
        line: "close versions",
        run: () => showVersionMenu(false),
      },
    ],
  };

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
    if (key !== lastVersionsKey && !versionMenuOpen) {
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

  const versionMenuIsOpen = () => versionMenuOpen;

  return {
    NEWEST,
    VERSIONS,
    activationIsForced,
    clearForcedActivation,
    goVersion,
    renderVersions,
    showVersionMenu,
    versionBtn,
    versionLabel,
    versionMenu,
    versionMenuIsOpen,
    versionsOffered,
  };
}
