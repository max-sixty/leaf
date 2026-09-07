/* The keyboard reference: the complete listing behind `?`, the mode that owns the
   keyboard while it stands, and the character key shortcut preference it keeps.

   A true mode may own the keyboard. An armed address sequence and the open reference claim
   the relevant keys through their scope. A longer-lived menu keeps the reference
   available through `allButTheReference`. Closing the reference restores the shared
   captured `shortcutReferenceOrigin`, so the reader returns to the control or reading place that
   opened it. A modal dialog clears the top layer's auto popovers on its way in, so the
   reference notes the ones it was opened over and stands them back up before that restore
   — the dialog that says what a menu's keys are cannot be what takes the menu away. It
   stands each one back up from that layer's own invoker — `lfInvoker`, the link a layer
   declares because the platform's own runs one way only — so the layer's way out survives
   the round trip too.

   The reference lists every live capability the page has, grouped by scope, and filters
   those rows by normalized key, action, line word, and scope text. Search is a projection
   of the same gathered rows rather than another binding index. Computed ranges count
   current members. A declaration must survive `merge` with its `when`, `at`,
   `liveInReference`, and rows intact so the reference does not advertise a scope the
   current page cannot enter.

   The reference is a complete keyboard layer. Its registered Tab row cycles through the
   close control, search field, and actual overflow regions without letting focus enter
   the page behind it. Escape and the close control share one registered row. Closing
   restores the element that opened it and keeps an already expanded shortcut bar open.
   Restoration waits one frame only when that element is the temporarily removed More
   control.

   The reference also owns the persistent character key shortcut preference. Turning it off
   removes unmodified and Shift-only letter, number, and punctuation bindings from
   dispatch, the shortcut bar, the reference, tooltips, address labels, placeholders, and
   `aria-keyshortcuts` in one projection. Space is activation, not a character key shortcut,
   and remains live. The native More button and its Enter activation are the route back to
   the setting; do not make the setting depend on the character key it disables.

   An dialog may become stale while open. If a row goes dead, its dispatch no longer
   runs. A newly live row may wait until the reference is reopened. Do not rebuild a
   focused shortcut reference dialog under the reader merely to keep it live to the
   latest poll. */
import {
  bindings,
  characterKeyShortcuts,
  clampedRow,
  commandPresentations,
  declaredBindings,
  live,
  setCharacterKeyShortcuts as rememberCharacterKeyShortcuts,
  spell,
  spokenBinding,
  word,
} from "./bindings.js";
import { completeRowSteps, keySequence, neutralStates } from "./presentation.js";
import { captureReturnPlace, restoreReturnPlace } from "./return-stack.js";
import { el } from "../widget-elements.js";
import { ELEMENTS, pageScopes } from "./page.js";
import { setSequence } from "./address.js";
import { setReact } from "../reactions.js";
import {
  byCommand,
  elementScopes,
  focused,
  merge,
  paintHere,
  paintKeys,
  pruneScopedElements,
  scopeRefs,
  scopesFor,
} from "./scopes.js";
import { syncGeneral } from "../conversation/panel.js";
import { pageSelection } from "../composing/capture.js";
import { readingBlock } from "../version.js";
import { availableCommands, executeCommand, readerIn } from "./dispatch.js";
import { reachScrollers } from "../reach.js";

export const shortcutReferenceDialog = document.createElement("dialog");
shortcutReferenceDialog.className = "lf-ui lf-shortcut-reference";
shortcutReferenceDialog.setAttribute("aria-label", "All keyboard shortcuts");
shortcutReferenceDialog.setAttribute("aria-modal", "true");
shortcutReferenceDialog.tabIndex = -1; // focused on open, so the dialog isn't silent to a screen reader
export const shortcutReferenceClose = el(
  "button",
  "lf-btn lf-shortcut-reference-close",
  "Close",
);
shortcutReferenceClose.type = "button";
shortcutReferenceClose.title = "Close the shortcuts";
shortcutReferenceClose.setAttribute("aria-label", "Close the shortcuts");

// The toggle behind the reference's own control: every surface loses or regains the
// same keys together, and a paint that throws puts the preference back.
const setCharacterKeyShortcuts = (on) => {
  const before = characterKeyShortcuts();
  rememberCharacterKeyShortcuts(on);
  setSequence(false);
  setReact(false);
  try {
    paintKeys();
    syncGeneral();
  } catch (error) {
    rememberCharacterKeyShortcuts(before);
    paintKeys();
    syncGeneral();
    throw error;
  }
};

// Every scope the page has, gathered by title, for the reference. Not the stack: the
// reference answers "what could I do here", so it names a card grip's keys whether or not
// a grip has focus. What it does not name is a key that would refuse the press, which is
// the rows' own liveness.
//
// The runtime's own modes come through the same door as a widget's, and the reference was
// blind to them while they did not: the sharpest case was the dialog never saying how to
// close the dialog, and a quiet page naming no Escape at all. So a section is its title
// wherever the title comes from — the box a reply is typed into declares its send key from
// wireInput and its way out from the typing mode, and they are one heading.
//
// The stack backwards, so a reader learning the keyboard starts from the page in front of them
// and reads inward, and the widgets' sections land where their scopes stand in it rather than
// wherever a second list happened to put them.
function declaredStack(origin) {
  pruneScopedElements();
  const sections = new Map();
  // Capture this before the dialog takes focus. Repeated widgets share command ids, but
  // their words can name the particular thing in front of the reader; the active
  // contributors therefore get the last word in their section.
  const activeScopes = scopesFor(origin);
  const named = (section) => activeScopes.some((s) => s.title === section.title);
  // Carry a scope's sequence down to each of its rows before sections with the same title
  // merge. The prefix belongs only to the rows that scope contributed; putting it on the
  // merged section would also put it in front of an unrelated widget that chose the same
  // heading.
  const referenceRows = (scope) =>
    byCommand(scope.rows).map(([id, row]) => [
      id,
      scope.sequence
        ? { ...row, sequence: scope.sequencePrefix ?? scope.sequence }
        : row,
    ]);
  for (const scope of pageScopes().toReversed()) {
    if (scope !== ELEMENTS) {
      merge(sections, { ...scope, rows: referenceRows(scope) });
      continue;
    }
    // Where the reader is, for a widget's section, is whether the focused element declares it
    // — the one thing core's own scopes state for themselves and an element scope cannot,
    // since it is gathered here by title and the elements wearing that title are many.
    const declared = new Map();
    // In the order the page holds them, not the order they registered. `scopeRefs` is
    // insertion-ordered and a widget registers at upgrade, so the sections came out in
    // whatever order the modules happened to finish in — the same build read twice put
    // "On a tab" above "On a card grip" once and below it the next time. A reference whose
    // headings move between loads is one a reader cannot learn the shape of, and any
    // assertion on it flakes rather than fails.
    const held = [...scopeRefs]
      .map((ref) => ref.deref())
      .filter((el) => el?.isConnected && elementScopes.get(el)?.title);
    held.sort((a, b) =>
      a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
    );
    for (const el of held) {
      const section = elementScopes.get(el);
      merge(declared, { ...section, rows: referenceRows(section) });
    }
    // DOM order makes the reference stable. Re-applying the active path from outside in
    // keeps that stability while letting the innermost live instance supply dynamic
    // labels and actions for command ids shared by several instances.
    for (const section of activeScopes.toReversed())
      if (section.title) merge(declared, { ...section, rows: referenceRows(section) });
    for (const section of declared.values())
      merge(sections, { ...section, at: () => named(section) });
  }
  // The way out reads last, after what the scope is for. A section gathers its rows from
  // wherever they were declared, and a mode contributing only its Escape would otherwise
  // put the exit above the walk it exits from.
  const exit = (row) => (bindings(row).includes("Escape") ? 1 : 0);
  return [...sections.values()].map((s) => ({
    ...s,
    rows: [...s.rows.values()].sort((a, b) => exit(a) - exit(b)),
  }));
}

// ---------- the reference ----------
// Every scope the page has, live rows only, so nothing on screen is a key that does
// nothing. It renders at open and can go stale while it stands, and the two directions
// cost differently, both acceptably: a row going dead under it cannot be pressed, since
// the dialog claims the keyboard and the page stands down beneath it, and a key going live under it
// is merely unlisted until the next open, one press away.
let shortcutReferenceOpen = false;
let commandsAtOpen = new Set();
// Where the reference was opened from, so closing it hands the reader back. Any dialog that
// takes focus owes that; what makes it structural here is that a scope is *where focus is*,
// so the dialog explaining a walk was also the way out of it — open the reference from a
// version row or a held card and the row's keys, which it had just listed, reached nothing
// afterwards. A mode over the page keeps this one key (`allButTheReference`), and a kept key
// that costs the reader their place is not much of an exemption.
//
// A reader working from the page is standing on `body` by design — `letGo` puts them
// there so Space and PageDown reach the document's own scroll box — so `?` from the page
// recorded `body` and closing handed focus back to it. That is worse than handing back
// nothing: focusing `body` resets the browser's sequential focus navigation starting
// point, so the reader's next Tab began at the top of the document rather than beside
// the words they had been reading.
let shortcutReferenceOrigin = null;
// The shared return-place primitive records a control or the current reading block. A
// block is focused and then let go of, moving the browser's sequential starting point
// without turning prose into a standing item.
// The layers the reference was opened over. A modal dialog clears every auto popover on
// its way into the top layer — the platform's rule, not Leaf's — so the dialog that
// exists to say what the versions menu's keys are was also what took the menu away, and
// the stored control then pointed into a layer that was no longer painted: the restore reached a
// row in a hidden popover and focus fell to the body. Note what stood, put it back before
// the restore, and the exemption costs the reader nothing again.
let shortcutReferenceLayers = [];
const shortcutReferenceWords = (value) =>
  String(value ?? "")
    .toLocaleLowerCase()
    .replace(/\s+/g, " ")
    .trim();
shortcutReferenceDialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  showShortcutReference(false);
});
// A modal dialog's backdrop reports the dialog itself as the click target. Compare
// the pointer with the painted box so the backdrop remains a light-dismiss surface
// without turning the dialog's own padding into one.
shortcutReferenceDialog.addEventListener("mousedown", (event) => {
  if (event.target !== shortcutReferenceDialog) return;
  const box = shortcutReferenceDialog.getBoundingClientRect();
  if (
    event.clientX < box.left ||
    event.clientX > box.right ||
    event.clientY < box.top ||
    event.clientY > box.bottom
  ) {
    // Closing returns focus to the door. Consume the backdrop press so the dialog's
    // default mousedown focus does not immediately replace that deliberate return.
    event.preventDefault();
    showShortcutReference(false);
  }
});
function showShortcutReference(open, restoreFocus = true) {
  // Focusing a text input replaces the document selection. Keep a passage the reader has
  // in hand when `?` opens the reference, while an ordinary open lands directly in search.
  // The dialog itself remains a focus stop, so either route keeps the page suspended.
  const preserveSelection = open && Boolean(pageSelection());
  const handBack = !open && restoreFocus && shortcutReferenceDialog.contains(focused());
  const origin = handBack ? shortcutReferenceOrigin : null;
  const restore = origin?.control ?? null;
  const closing = !open && shortcutReferenceDialog.open;
  if (open && !shortcutReferenceOpen) {
    shortcutReferenceOrigin = captureReturnPlace({ focused, readingBlock });
    shortcutReferenceLayers = [...document.querySelectorAll(":popover-open")];
    commandsAtOpen = availableCommands();
  }
  shortcutReferenceOpen = open;
  if (open) {
    shortcutReferenceDialog.textContent = "";
    const head = el("div", "lf-shortcut-reference-head");
    head.append(
      el("div", "lf-shortcut-reference-title", "All keyboard shortcuts"),
      shortcutReferenceClose,
    );
    shortcutReferenceDialog.append(head);
    const search = document.createElement("input");
    search.type = "search";
    search.className = "lf-shortcut-reference-search";
    search.placeholder = "Find a key or action";
    search.setAttribute("aria-label", "Search keyboard shortcuts");
    search.setAttribute("role", "combobox");
    search.setAttribute("aria-autocomplete", "list");
    search.setAttribute("aria-expanded", "true");
    search.setAttribute("aria-haspopup", "grid");
    search.autocomplete = "off";
    search.spellcheck = false;
    const meta = el("div", "lf-shortcut-reference-meta");
    meta.setAttribute("aria-live", "polite");
    const preference = el("div", "lf-shortcut-reference-preference");
    const characterKeyToggle = el("button", "lf-btn lf-shortcut-reference-shortcuts");
    characterKeyToggle.type = "button";
    characterKeyToggle.setAttribute("aria-label", "Character key shortcuts");
    const paintCharacterKeyToggle = () => {
      const on = characterKeyShortcuts();
      characterKeyToggle.setAttribute("aria-pressed", String(on));
      characterKeyToggle.title = `Turn ${on ? "off" : "on"} letter, number, and punctuation shortcuts`;
      characterKeyToggle.replaceChildren(
        document.createTextNode("Character key shortcuts "),
        el("span", "", on ? "on" : "off"),
      );
    };
    paintCharacterKeyToggle();
    characterKeyToggle.onclick = () => {
      setCharacterKeyShortcuts(!characterKeyShortcuts());
      // Re-enter through the page so the dispatch snapshot sees the newly available
      // bindings before this modal scope shadows them. This rebuilds one surface rather
      // than entering another: preserve the place the original reference displaced and
      // focus the replacement preference instead of minting either control as an origin.
      const origin = shortcutReferenceOrigin;
      showShortcutReference(false, false);
      showShortcutReference(true);
      shortcutReferenceOrigin = origin;
      shortcutReferenceDialog
        .querySelector(".lf-shortcut-reference-shortcuts")
        .focus({ preventScroll: true });
    };
    preference.append(meta, characterKeyToggle);
    const results = el("div", "lf-shortcut-reference-results");
    results.id = "lf-shortcut-reference-results";
    results.setAttribute("role", "grid");
    results.setAttribute("aria-label", "All keyboard shortcuts");
    search.setAttribute("aria-controls", results.id);
    const emptyRow = document.createElement("div");
    emptyRow.setAttribute("role", "row");
    const empty = el("div", "lf-shortcut-reference-empty", "No matching commands");
    empty.setAttribute("role", "gridcell");
    emptyRow.append(empty);
    emptyRow.hidden = true;
    const sections = [];
    let total = 0;
    // A sequence row is reached from the standing page, so its cell shows the complete route.
    // Each physical press keeps its own keycap; an ordinary row remains one compact step.
    const referenceSteps = (row, route) => [
      ...(word(row.sequence) ?? []),
      ...completeRowSteps(row, route),
    ];
    const spokenReferenceSteps = (row, route, steps) => {
      const declared = route ? [route.binding] : declaredBindings(row);
      if (declared.length !== 1) return steps;
      const binding = declared[0];
      const visual = spell(binding);
      const spoken = [...steps];
      const index = spoken.lastIndexOf(visual);
      if (index !== -1) spoken[index] = spokenBinding(binding);
      return spoken;
    };
    const commandButtons = [];
    // A command id is one capability even when several scopes project it. Ask actions
    // are the sharp case: the package declaration supplies the control and the page's
    // Ask row supplies a contextual binding. The page row is visited first while it is
    // live, so keep that complete route and omit the package's second telling of it.
    const presentedCommands = new Set();
    const availableWhere = (row, scopeTitle, scopeReach) => {
      const place = word(row.reach) ?? word(scopeReach) ?? scopeTitle;
      return `Available ${place.charAt(0).toLocaleLowerCase()}${place.slice(1)}`;
    };
    const table = (rows, scopeTitle, scopeReach) => {
      const t = document.createElement("table");
      t.setAttribute("role", "presentation");
      const entries = [];
      for (const row of rows) {
        for (const presentation of commandPresentations(row)) {
          const { id, route } = presentation;
          if (presentedCommands.has(id)) continue;
          presentedCommands.add(id);
          const does = route?.does ?? word(row.does);
          const tr = document.createElement("tr");
          tr.dataset.lfCommand = id;
          tr.id = `lf-shortcut-reference-row-${total + entries.length}`;
          tr.setAttribute("role", "row");
          if (row.sequenceControl) tr.classList.add("lf-sequence-control");
          const steps = referenceSteps(row, route);
          const label = steps.join(" ");
          const sequence = keySequence(
            steps,
            neutralStates(steps),
            spokenReferenceSteps(row, route, steps),
          );
          sequence.id = `lf-shortcut-reference-key-${total + entries.length}`;
          const keyCell = document.createElement("td");
          keyCell.setAttribute("role", "gridcell");
          keyCell.append(sequence);
          const actionCell = document.createElement("td");
          actionCell.setAttribute("role", "gridcell");
          const available = commandsAtOpen.has(id);
          if (row.run && row.runFromReference !== false) {
            const command = el("button", "lf-shortcut-reference-command", word(does));
            command.type = "button";
            command.tabIndex = -1;
            command.dataset.lfCommand = id;
            command.dataset.lfAvailable = String(available);
            command.dataset.lfSelected = "false";
            command.setAttribute("aria-describedby", sequence.id);
            command.title = available
              ? "Run command"
              : availableWhere(row, scopeTitle, scopeReach);
            command.onclick = () => {
              if (!available) {
                meta.textContent = availableWhere(row, scopeTitle, scopeReach);
                return;
              }
              // Closing a native modal may leave this soon-hidden button focused until
              // the click finishes. The command's origin is the place the reference
              // displaced, not that transient implementation node. Run after the close's
              // focus restoration too, so the command's own destination wins the frame.
              const origin = shortcutReferenceOrigin;
              showShortcutReference(false);
              requestAnimationFrame(() => {
                if (!executeCommand(id, origin)) {
                  showShortcutReference(true);
                  shortcutReferenceDialog.querySelector(
                    ".lf-shortcut-reference-meta",
                  ).textContent = "That command is no longer available";
                }
              });
            };
            actionCell.append(command);
            commandButtons.push(command);
          } else actionCell.textContent = word(does);
          tr.append(keyCell, actionCell);
          t.append(tr);
          entries.push({
            el: tr,
            directWords: shortcutReferenceWords(
              `${id} ${scopeTitle} ${label} ${word(does)} ${word(route?.line ?? row.line)}`,
            ),
            familyWords: shortcutReferenceWords(
              `${row.id} ${referenceSteps(row).join(" ")} ${word(row.does)}`,
            ),
          });
        }
      }
      total += entries.length;
      return { el: t, entries };
    };
    for (const scope of declaredStack(shortcutReferenceOrigin?.control)) {
      // A scope the reader is standing in is filtered by each row's own liveness, because
      // they can see which state they are in and a row that would refuse the press must
      // not be on screen. A scope they are merely near is listed whole: a row's `when`
      // asks whether the press moves *here*, and here is not where they are, so a grip's
      // "arrows move" belongs in the reference though no card is held and `x` belongs in
      // it though no thread is focused. Filtering both by the same predicate is what took
      // the thread's own keys out of the reference altogether.
      //
      // A transient mode is the exception, and it is one because there is no standing near
      // it: the reader is in it or it is not there. Opening this modal dismisses the mode,
      // so its declaration records that its rows must retain their boundary-time liveness.
      // Deriving that fact from a blanket keyboard claim coupled two independent parts of a
      // scope and made exempting `?` change what the reference listed.
      const inIt = readerIn(scope) || scope.liveInReference;
      // A declared section may merge many element instances under one title. Their
      // identical bindings are alternatives at different focus locations, not competing
      // meanings in one dispatch scope, so conflict validation stays on each registered
      // scope and this aggregate only filters the rows relevant to the current state.
      const rows = scope.rows.filter(
        (row) =>
          row.does &&
          // Pointer-native actions can deliberately carry a label but no key. Keep
          // those in the complete reference; only hide a row whose declared character
          // binding the reader has turned off.
          (bindings(row).length > 0 || declaredBindings(row).length === 0) &&
          (!inIt || (row.referenceWhen ? row.referenceWhen() : live(row))),
      );
      if (!rows.length) continue;
      const title = scope.title ?? "On this page";
      const section = document.createElement("section");
      section.className = "lf-shortcut-reference-section";
      section.setAttribute("role", "rowgroup");
      const heading = el("h3", "", title);
      heading.id = `lf-shortcut-reference-section-${sections.length}`;
      section.setAttribute("aria-labelledby", heading.id);
      const headingRow = document.createElement("div");
      headingRow.setAttribute("role", "row");
      const headingCell = document.createElement("div");
      headingCell.setAttribute("role", "gridcell");
      headingCell.append(heading);
      headingRow.append(headingCell);
      const body = table(rows, title, scope.reach);
      section.append(headingRow, body.el);
      results.append(section);
      sections.push({
        el: section,
        heading,
        table: body.el,
        words: shortcutReferenceWords(title),
        entries: body.entries,
      });
    }
    results.append(emptyRow);
    const visibleCommands = () =>
      commandButtons.filter(
        (button) => !button.closest("tr").hidden && !button.closest("section").hidden,
      );
    const keepOneCommandReachable = () => {
      const visible = visibleCommands();
      const selected = visible.find((command) => command.dataset.lfSelected === "true");
      const tabStop = selected ?? visible[0];
      for (const command of commandButtons) {
        const on = command === selected;
        command.tabIndex = command === tabStop ? 0 : -1;
        command.dataset.lfSelected = String(on);
        command.closest("tr").setAttribute("aria-selected", String(on));
      }
      if (selected)
        search.setAttribute("aria-activedescendant", selected.closest("tr").id);
      else search.removeAttribute("aria-activedescendant");
    };
    const filter = () => {
      const query = shortcutReferenceWords(search.value);
      const directMatch =
        query &&
        sections.some((section) =>
          section.entries.some((entry) => entry.directWords.includes(query)),
        );
      let shown = 0;
      for (const section of sections) {
        const sectionMatch = query && section.words.includes(query);
        let sectionShown = 0;
        for (const entry of section.entries) {
          const match =
            !query ||
            sectionMatch ||
            entry.directWords.includes(query) ||
            (!directMatch && entry.familyWords.includes(query));
          entry.el.hidden = !match;
          if (match) sectionShown++;
        }
        section.el.hidden = sectionShown === 0;
        section.heading.hidden = sectionShown === 0;
        section.table.hidden = sectionShown === 0;
        shown += sectionShown;
      }
      emptyRow.hidden = shown !== 0;
      // The hint's verbs are the rows' (SHORTCUT_REFERENCE in leaf.js: "choose next", "run"), since the
      // short shortcut bar has no slot for the arrow rows and this head is where a reader
      // in the search box learns them. Two spellings of one press — "choose" here,
      // "next command" on the line — were two registers.
      meta.textContent = query
        ? `${shown} of ${total} commands · ↑↓ choose · ⏎ run`
        : `${total} commands · ↑↓ choose · ⏎ run`;
      keepOneCommandReachable();
    };
    search.addEventListener("input", filter);
    filter();
    shortcutReferenceDialog.append(search, preference, results);
  }
  shortcutReferenceDialog.classList.toggle("open", open);
  if (open && !shortcutReferenceDialog.open) shortcutReferenceDialog.showModal();
  else if (!open && shortcutReferenceDialog.open) shortcutReferenceDialog.close();
  // Back in the same order they were in: the dialog is out of the top layer by here, so a
  // popover that is still on the page can stand again, and the restore below then reaches
  // a control that is painted.
  if (closing) {
    for (const layer of shortcutReferenceLayers) {
      if (!layer.isConnected || layer.matches(":popover-open")) continue;
      // A popover hands focus back to whatever had it when it was shown, and what the
      // closing dialog leaves focused is the body — so a layer stood back up from here
      // would have no way out, and the reader's exit from the menu would be the one thing
      // the round trip cost. Stand it up from its invoker (`lfInvoker`), and only where
      // the restore below is going back inside it, so a reader whose focus is somewhere
      // else entirely is not moved to say so.
      if (restore && layer.contains(restore))
        layer.lfInvoker?.focus({ preventScroll: true });
      layer.showPopover();
    }
    shortcutReferenceLayers = [];
  }
  // The reference is a list long enough to scroll, and anything a mouse can scroll a
  // keyboard has to reach. `reachScrollers` is the runtime's one answer to that and had
  // never been pointed at the chrome it builds after upgrade: its rows carry no control,
  // so a reader working from the keyboard could read the first screenful of the key
  // reference and had no way to the rest of it. Called with the dialog open, because the
  // sweep reads computed overflow and a hidden box has none.
  if (open) reachScrollers(shortcutReferenceDialog);
  if (open)
    shortcutReferenceDialog
      .querySelector(
        preserveSelection
          ? ".lf-shortcut-reference-close"
          : ".lf-shortcut-reference-search",
      )
      .focus({ preventScroll: true });
  // Only from inside the dialog: a mousedown somewhere else closes it (standDown), and the
  // press's own focus is the browser's default action, still to come — a restore made from
  // out here would be putting focus back for the click to take again.
  paintHere();
  if (!open && origin) restoreReturnPlace(origin);
}

const referenceStops = () =>
  [
    ...shortcutReferenceDialog.querySelectorAll(
      'button, input, [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((node) => node.tabIndex >= 0 && node.checkVisibility());
export function moveReference(dir) {
  const stops = referenceStops();
  if (!stops.length) return shortcutReferenceDialog.focus({ preventScroll: true });
  const at = stops.indexOf(focused());
  const next =
    at < 0
      ? dir > 0
        ? stops[0]
        : stops.at(-1)
      : stops[(at + dir + stops.length) % stops.length];
  next.focus({ preventScroll: true });
}
const commandStops = () =>
  [
    ...shortcutReferenceDialog.querySelectorAll(".lf-shortcut-reference-command"),
  ].filter((node) => node.checkVisibility());
export const onCommandRail = () =>
  commandStops().length > 0 &&
  (focused()?.matches?.(
    ".lf-shortcut-reference-search, .lf-shortcut-reference-command",
  ) ??
    false);
export function moveCommand(dir) {
  const stops = commandStops();
  if (!stops.length) return;
  const focusedCommand = focused()?.matches?.(".lf-shortcut-reference-command")
    ? focused()
    : null;
  const selected =
    focusedCommand ?? stops.find((stop) => stop.dataset.lfSelected === "true");
  const next = clampedRow(stops, selected, dir);
  for (const stop of stops) {
    const on = stop === next;
    stop.tabIndex = on ? 0 : -1;
    stop.dataset.lfSelected = String(on);
    stop.closest("tr").setAttribute("aria-selected", String(on));
  }
  const search = shortcutReferenceDialog.querySelector(".lf-shortcut-reference-search");
  search.setAttribute("aria-activedescendant", next.closest("tr").id);
  if (focusedCommand) next.focus({ preventScroll: true });
  next.closest("tr").scrollIntoView({ block: "nearest" });
  const key = next.closest("tr").querySelector("kbd").textContent;
  shortcutReferenceDialog.querySelector(".lf-shortcut-reference-meta").textContent =
    `${next.textContent} · ${key} · ⏎ run`;
}
export function runSelected() {
  if (!onCommandRail()) return false;
  const command = focused().matches(".lf-shortcut-reference-command")
    ? focused()
    : (commandStops().find((stop) => stop.dataset.lfSelected === "true") ??
      commandStops()[0]);
  if (!command) return false;
  command.click();
  return true;
}
shortcutReferenceClose.onclick = () => showShortcutReference(false);

export const referenceOpen = () => shortcutReferenceOpen;
export { showShortcutReference as showReference };
