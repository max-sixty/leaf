/* The keyboard reference: the complete listing behind `?` and the mode that owns the
   keyboard while it stands.

   A true mode may own the keyboard. An armed address chord and the open reference claim
   the relevant keys through their scope. A longer-lived menu keeps the reference
   available through `allButTheReference`. Closing the reference restores the shared
   captured `helpOrigin`, so the reader returns to the control or reading place that
   opened it. A modal dialog clears the top layer's auto popovers on its way in, so the
   reference notes the ones it was opened over and stands them back up before that restore
   — the overlay that says what a menu's keys are cannot be what takes the menu away. It
   stands each one back up from that layer's own invoker — `lfInvoker`, the link a layer
   declares because the platform's own runs one way only — so the layer's way out survives
   the round trip too.

   The reference lists every live capability the page has, grouped by scope, and searches
   those rows by key, action, line word, and scope text. Every declared binding alternative
   remains searchable even when its cell compacts several alternatives into one face.
   Binding-prefix matches form one leading result group across scopes; exact case leads
   case-insensitive matches, so a shifted key remains distinguishable. Search is a
   projection of the same gathered rows rather than another binding index. Computed ranges
   count current members.
   A declaration must survive `merge` with its `when`, `at`,
   `liveInReference`, and rows intact so the reference does not advertise a scope the
   current page cannot enter.

   The reference is a complete keyboard layer. Its registered Tab row cycles through the
   close control, search field, and actual overflow regions without letting focus enter
   the page behind it. Escape and the close control share one registered row. Closing
   restores the element that opened it and keeps an already expanded shortcut shelf open.
   Restoration waits one frame only when that element is the temporarily removed More
   control.

   An overlay may become stale while open. If a row goes dead, its dispatch no longer
   runs. A newly live row may wait until the reference is reopened. Do not rebuild a
   focused help surface under the reader merely to keep it live to the latest poll. */
import {
  bindings,
  clampedRow,
  commandPresentations,
  declaredBindings,
  live,
  spell,
  spokenBinding,
  word,
} from "./bindings.js";
import { completeRowSteps, keySequence, neutralStates } from "./presentation.js";
import { captureReturnPlace, restoreReturnPlace } from "./return-stack.js";
import { el } from "../widget-elements.js";
import { ELEMENTS, pageScopes } from "./page.js";
import {
  byCommand,
  elementScopes,
  focused,
  merge,
  paintHere,
  pruneScopedElements,
  scopeRefs,
  scopesFor,
} from "./scopes.js";
import { pageSelection } from "../composing/capture.js";
import { readingBlock } from "../version.js";
import { availableCommands, executeCommand, readerIn } from "./dispatch.js";
import { reachScrollers } from "../reach.js";

export const helpEl = document.createElement("dialog");
helpEl.id = "lf-help";
helpEl.className = "lf-ui lf-help";
helpEl.setAttribute("aria-label", "All keyboard shortcuts");
helpEl.setAttribute("aria-modal", "true");
helpEl.tabIndex = -1; // focused on open, so the dialog isn't silent to a screen reader
export const helpClose = el("button", "lf-btn lf-help-close", "Close");
helpClose.type = "button";
helpClose.title = "Close the shortcuts";
helpClose.setAttribute("aria-label", "Close the shortcuts");

// Every scope the page has, gathered by title, for the reference. Not the stack: the
// reference answers "what could I do here", so it names a card grip's keys whether or not
// a grip has focus. What it does not name is a key that would refuse the press, which is
// the rows' own liveness.
//
// The runtime's own modes come through the same door as a widget's, and the reference was
// blind to them while they did not: the sharpest case was the overlay never saying how to
// close the overlay, and a quiet page naming no Escape at all. So a section is its title
// wherever the title comes from — the box a reply is typed into declares its send key from
// wireInput and its way out from the typing mode, and they are one heading.
//
// The stack backwards, so a reader learning the keyboard starts from the page in front of them
// and reads inward, and the widgets' sections land where their scopes stand in it rather than
// wherever a second list happened to put them.
function declaredStack(origin) {
  pruneScopedElements();
  const sections = new Map();
  // Capture this before the overlay takes focus. Repeated widgets share command ids, but
  // their words can name the particular thing in front of the reader; the active
  // contributors therefore get the last word in their section.
  const activeScopes = scopesFor(origin);
  const named = (section) => activeScopes.some((s) => s.title === section.title);
  // Carry a scope's chord down to each of its rows before sections with the same title
  // merge. The prefix belongs only to the rows that scope contributed; putting it on the
  // merged section would also put it in front of an unrelated widget that chose the same
  // heading.
  const referenceRows = (scope) =>
    byCommand(scope.rows).map(([id, row]) => [
      id,
      scope.chord ? { ...row, chord: scope.chordPrefix ?? scope.chord } : row,
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
// the overlay claims the keyboard and the page stands down beneath it, and a key going live under it
// is merely unlisted until the next open, one press away.
let helpOpen = false;
let commandsAtOpen = new Set();
// Where the reference was opened from, so closing it hands the reader back. Any dialog that
// takes focus owes that; what makes it structural here is that a scope is *where focus is*,
// so the overlay explaining a walk was also the way out of it — open the reference from a
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
let helpOrigin = null;
// The shared return-place primitive records a control or the current reading block. A
// block is focused and then let go of, moving the browser's sequential starting point
// without turning prose into a standing item.
// The layers the reference was opened over. A modal dialog clears every auto popover on
// its way into the top layer — the platform's rule, not Leaf's — so the overlay that
// exists to say what the versions menu's keys are was also what took the menu away, and
// the stored control then pointed into a layer that was no longer painted: the restore reached a
// row in a hidden popover and focus fell to the body. Note what stood, put it back before
// the restore, and the exemption costs the reader nothing again.
let helpLayers = [];
const helpWords = (value) =>
  String(value ?? "")
    .toLocaleLowerCase()
    .replace(/\s+/g, " ")
    .trim();
// A binding query retains a trailing separator: `g ` means the routes below the `g`
// prefix, while prose matching still treats it as the word `g`. Case is retained for the
// first rank so `g t` and `g T` can put the actual requested face first.
const helpBinding = (value) =>
  String(value ?? "")
    .replace(/^\s+/, "")
    .replace(/\s+/g, " ");
helpEl.addEventListener("cancel", (event) => {
  event.preventDefault();
  showHelp(false);
});
// A modal dialog's backdrop reports the dialog itself as the click target. Compare
// the pointer with the painted box so the backdrop remains a light-dismiss surface
// without turning the dialog's own padding into one.
helpEl.addEventListener("mousedown", (event) => {
  if (event.target !== helpEl) return;
  const box = helpEl.getBoundingClientRect();
  if (
    event.clientX < box.left ||
    event.clientX > box.right ||
    event.clientY < box.top ||
    event.clientY > box.bottom
  ) {
    // Closing returns focus to the door. Consume the backdrop press so the dialog's
    // default mousedown focus does not immediately replace that deliberate return.
    event.preventDefault();
    showHelp(false);
  }
});
function showHelp(open, restoreFocus = true) {
  // Focusing a text input replaces the document selection. Keep a passage the reader has
  // in hand when `?` opens the reference, while an ordinary open lands directly in search.
  // The dialog itself remains a focus stop, so either route keeps the page suspended.
  const preserveSelection = open && Boolean(pageSelection());
  const handBack = !open && restoreFocus && helpEl.contains(focused());
  const origin = handBack ? helpOrigin : null;
  const restore = origin?.control ?? null;
  const closing = !open && helpEl.open;
  if (open && !helpOpen) {
    helpOrigin = captureReturnPlace({ focused, readingBlock });
    helpLayers = [...document.querySelectorAll(":popover-open")];
    commandsAtOpen = availableCommands();
  }
  helpOpen = open;
  if (open) {
    helpEl.textContent = "";
    const head = el("div", "lf-help-head");
    head.append(el("div", "lf-help-title", "All keyboard shortcuts"), helpClose);
    helpEl.append(head);
    const search = document.createElement("input");
    search.type = "search";
    search.className = "lf-help-search";
    search.placeholder = "Find a key or action";
    search.setAttribute("aria-label", "Search keyboard shortcuts");
    search.setAttribute("role", "combobox");
    search.setAttribute("aria-autocomplete", "list");
    search.setAttribute("aria-expanded", "true");
    search.setAttribute("aria-haspopup", "grid");
    search.autocomplete = "off";
    search.spellcheck = false;
    const meta = el("div", "lf-help-meta");
    meta.setAttribute("aria-live", "polite");
    const results = el("div", "lf-help-results");
    results.id = "lf-help-results";
    results.setAttribute("role", "grid");
    results.setAttribute("aria-label", "All keyboard shortcuts");
    search.setAttribute("aria-controls", results.id);
    const emptyRow = document.createElement("div");
    emptyRow.setAttribute("role", "row");
    const empty = el("div", "lf-help-empty", "No matching commands");
    empty.setAttribute("role", "gridcell");
    emptyRow.append(empty);
    emptyRow.hidden = true;
    const sections = [];
    let total = 0;
    // A chord row is reached from the standing page, so its cell shows the complete route.
    // Each physical press keeps its own keycap; an ordinary row remains one compact step.
    const referenceSteps = (row, route) => [
      ...(word(row.chord) ?? []),
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
          tr.id = `lf-help-row-${total + entries.length}`;
          tr.setAttribute("role", "row");
          if (row.chordControl) tr.classList.add("lf-chord-control");
          const steps = referenceSteps(row, route);
          const label = steps.join(" ");
          const sequence = keySequence(
            steps,
            neutralStates(steps),
            spokenReferenceSteps(row, route, steps),
          );
          if (!declaredBindings(row).length && row.decision !== undefined)
            sequence.classList.add("lf-key-label");
          sequence.id = `lf-help-key-${total + entries.length}`;
          const keyCell = document.createElement("td");
          keyCell.setAttribute("role", "gridcell");
          keyCell.append(sequence);
          const actionCell = document.createElement("td");
          actionCell.setAttribute("role", "gridcell");
          const action = el("div", "lf-help-action");
          const scopeLabel = el("span", "lf-help-scope", scopeTitle);
          const available = commandsAtOpen.has(id);
          if (row.run && row.runFromReference !== false) {
            const command = el("button", "lf-help-command", word(does));
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
              const origin = helpOrigin;
              showHelp(false);
              requestAnimationFrame(() => {
                if (!executeCommand(id, origin)) {
                  showHelp(true);
                  helpEl.querySelector(".lf-help-meta").textContent =
                    "That command is no longer available";
                }
              });
            };
            action.append(command);
            commandButtons.push(command);
          } else action.textContent = word(does);
          actionCell.append(action);
          tr.append(keyCell, actionCell);
          t.append(tr);
          const prefix = word(row.chord) ?? [];
          const alternatives = route ? [route.binding] : bindings(row);
          entries.push({
            el: tr,
            order: entries.length,
            action,
            scopeLabel,
            bindingForms: alternatives.map((binding) => ({
              display: [...prefix, spell(binding)].join(" "),
              spoken: [...prefix, spokenBinding(binding)].join(" "),
            })),
            directWords: helpWords(
              `${id} ${scopeTitle} ${label} ${word(does)} ${word(route?.line ?? row.line)}`,
            ),
            familyWords: helpWords(
              `${row.id} ${referenceSteps(row).join(" ")} ${word(row.does)}`,
            ),
          });
        }
      }
      total += entries.length;
      return { el: t, entries };
    };
    for (const scope of declaredStack(helpOrigin?.control)) {
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
      // Pointer-native actions can deliberately carry a label but no key, so the
      // complete reference filters commands by meaning and liveness rather than by
      // whether they currently have a keyboard route.
      const rows = scope.rows.filter(
        (row) =>
          row.does && (!inIt || (row.referenceWhen ? row.referenceWhen() : live(row))),
      );
      if (!rows.length) continue;
      const title = scope.title ?? "On this page";
      const section = document.createElement("section");
      section.className = "lf-help-section";
      section.setAttribute("role", "rowgroup");
      const heading = el("h3", "", title);
      heading.id = `lf-help-section-${sections.length}`;
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
        order: sections.length,
        heading,
        table: body.el,
        words: helpWords(title),
        entries: body.entries,
      });
    }
    const bindingSection = document.createElement("section");
    bindingSection.className = "lf-help-section lf-help-binding-matches";
    bindingSection.setAttribute("role", "rowgroup");
    const bindingHeading = el("h3", "", "Binding matches");
    bindingHeading.id = "lf-help-binding-matches";
    bindingSection.setAttribute("aria-labelledby", bindingHeading.id);
    const bindingHeadingRow = document.createElement("div");
    bindingHeadingRow.setAttribute("role", "row");
    const bindingHeadingCell = document.createElement("div");
    bindingHeadingCell.setAttribute("role", "gridcell");
    bindingHeadingCell.append(bindingHeading);
    bindingHeadingRow.append(bindingHeadingCell);
    const bindingTable = document.createElement("table");
    bindingTable.setAttribute("role", "presentation");
    bindingSection.append(bindingHeadingRow, bindingTable);
    bindingSection.hidden = true;
    results.append(emptyRow);
    const visibleCommands = () =>
      [...results.querySelectorAll(".lf-help-command")].filter(
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
      const query = helpWords(search.value);
      const bindingQuery = helpBinding(search.value);
      const foldedBindingQuery = bindingQuery.toLocaleLowerCase();
      const directMatch =
        query &&
        sections.some((section) =>
          section.entries.some((entry) => entry.directWords.includes(query)),
        );
      const ranked = [];
      for (const section of sections) {
        section.table.append(
          ...[...section.entries]
            .sort((left, right) => left.order - right.order)
            .map((entry) => entry.el),
        );
        for (const entry of section.entries) entry.scopeLabel.remove();
        const sectionMatch = query && section.words.includes(query);
        for (const entry of section.entries) {
          const exactBinding =
            bindingQuery &&
            entry.bindingForms.some(({ display }) => display.startsWith(bindingQuery));
          const foldedBinding =
            foldedBindingQuery &&
            entry.bindingForms.some(({ display }) =>
              display.toLocaleLowerCase().startsWith(foldedBindingQuery),
            );
          const spokenPrefix =
            foldedBindingQuery &&
            entry.bindingForms.some(({ spoken }) =>
              spoken.toLocaleLowerCase().startsWith(foldedBindingQuery),
            );
          const rank = !query
            ? 0
            : exactBinding
              ? 0
              : foldedBinding
                ? 1
                : spokenPrefix
                  ? 2
                  : sectionMatch || entry.directWords.includes(query)
                    ? 3
                    : !directMatch && entry.familyWords.includes(query)
                      ? 4
                      : Infinity;
          const match = Number.isFinite(rank);
          entry.el.hidden = !match;
          ranked.push({ entry, rank, section });
        }
      }
      const bindingMatches = query
        ? ranked
            .filter(({ rank }) => rank <= 2)
            .sort(
              (left, right) =>
                left.rank - right.rank ||
                left.section.order - right.section.order ||
                left.entry.order - right.entry.order,
            )
        : [];
      bindingTable.replaceChildren(
        ...bindingMatches.map(({ entry }) => {
          entry.action.append(entry.scopeLabel);
          return entry.el;
        }),
      );
      bindingSection.hidden = bindingMatches.length === 0;
      for (const section of sections) {
        const remaining = ranked
          .filter(
            (item) =>
              item.section === section &&
              Number.isFinite(item.rank) &&
              !bindingMatches.includes(item),
          )
          .sort(
            (left, right) =>
              left.rank - right.rank || left.entry.order - right.entry.order,
          );
        section.table.append(...remaining.map(({ entry }) => entry.el));
        section.el.hidden = remaining.length === 0;
        section.heading.hidden = remaining.length === 0;
        section.table.hidden = remaining.length === 0;
        section.rank = remaining[0]?.rank ?? Infinity;
      }
      const shown = ranked.filter(({ rank }) => Number.isFinite(rank)).length;
      const rankedSections = [...sections].sort(
        (left, right) => left.rank - right.rank || left.order - right.order,
      );
      results.replaceChildren(
        bindingSection,
        ...rankedSections.map(({ el }) => el),
        emptyRow,
      );
      emptyRow.hidden = shown !== 0;
      // The hint's verbs are the rows' (HELP in leaf.js: "choose next", "run"), since the
      // short key line has no slot for the arrow rows and this head is where a reader
      // in the search box learns them. Two spellings of one press — "choose" here,
      // "next command" on the line — were two registers.
      meta.textContent = query
        ? `${shown} of ${total} commands · ↑↓ choose · ⏎ run`
        : `${total} commands · ↑↓ choose · ⏎ run`;
      keepOneCommandReachable();
    };
    search.addEventListener("input", filter);
    filter();
    helpEl.append(search, meta, results);
  }
  helpEl.classList.toggle("open", open);
  if (open && !helpEl.open) helpEl.showModal();
  else if (!open && helpEl.open) helpEl.close();
  // Back in the same order they were in: the dialog is out of the top layer by here, so a
  // popover that is still on the page can stand again, and the restore below then reaches
  // a control that is painted.
  if (closing) {
    for (const layer of helpLayers) {
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
    helpLayers = [];
  }
  // The reference is a list long enough to scroll, and anything a mouse can scroll a
  // keyboard has to reach. `reachScrollers` is the runtime's one answer to that and had
  // never been pointed at the chrome it builds after upgrade: its rows carry no control,
  // so a reader working from the keyboard could read the first screenful of the key
  // reference and had no way to the rest of it. Called with the overlay open, because the
  // sweep reads computed overflow and a hidden box has none.
  if (open) reachScrollers(helpEl);
  if (open)
    helpEl
      .querySelector(preserveSelection ? ".lf-help-close" : ".lf-help-search")
      .focus({ preventScroll: true });
  // Only from inside the overlay: a mousedown somewhere else closes it (standDown), and the
  // press's own focus is the browser's default action, still to come — a restore made from
  // out here would be putting focus back for the click to take again.
  paintHere();
  if (!open && origin) restoreReturnPlace(origin);
}

const helpStops = () =>
  [...helpEl.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])')].filter(
    (node) => node.tabIndex >= 0 && node.checkVisibility(),
  );
export function moveReference(dir) {
  const stops = helpStops();
  if (!stops.length) return helpEl.focus({ preventScroll: true });
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
  [...helpEl.querySelectorAll(".lf-help-command")].filter((node) =>
    node.checkVisibility(),
  );
export const onCommandRail = () =>
  commandStops().length > 0 &&
  (focused()?.matches?.(".lf-help-search, .lf-help-command") ?? false);
export function moveCommand(dir) {
  const stops = commandStops();
  if (!stops.length) return;
  const focusedCommand = focused()?.matches?.(".lf-help-command") ? focused() : null;
  const selected =
    focusedCommand ?? stops.find((stop) => stop.dataset.lfSelected === "true");
  const next = clampedRow(stops, selected, dir);
  for (const stop of stops) {
    const on = stop === next;
    stop.tabIndex = on ? 0 : -1;
    stop.dataset.lfSelected = String(on);
    stop.closest("tr").setAttribute("aria-selected", String(on));
  }
  const search = helpEl.querySelector(".lf-help-search");
  search.setAttribute("aria-activedescendant", next.closest("tr").id);
  if (focusedCommand) next.focus({ preventScroll: true });
  next.closest("tr").scrollIntoView({ block: "nearest" });
  const key = next.closest("tr").querySelector("kbd").textContent;
  helpEl.querySelector(".lf-help-meta").textContent =
    `${next.textContent} · ${key} · ⏎ run`;
}
export function runSelected() {
  if (!onCommandRail()) return false;
  const command = focused().matches(".lf-help-command")
    ? focused()
    : (commandStops().find((stop) => stop.dataset.lfSelected === "true") ??
      commandStops()[0]);
  if (!command) return false;
  command.click();
  return true;
}
helpClose.onclick = () => showHelp(false);

export const referenceOpen = () => helpOpen;
export { showHelp as showReference };
