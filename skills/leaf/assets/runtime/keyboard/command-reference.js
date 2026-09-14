/* The command reference: the complete command catalog behind `?` and its modal search
   context.

   Opening captures the registered command vocabulary before the native dialog moves
   focus. The resulting catalog contains evaluated display values and stable command ids,
   not callbacks or live predicates. Search, ranking, selection, and metadata are local
   reader-session state projected through one Lit template. The dispatcher still resolves
   an activated id afresh after the dialog closes, so a stale row cannot run.

   The native dialog, retained Close button, top-layer restoration, return place, focus,
   selection, and scrolling stay with this controller. A modal dialog clears auto popovers
   on entry; the reference captures the platform layers that stood beneath it and restores
   eligible ones before returning focus. A covering auxiliary surface established while
   the reference stands supplies its own return place instead.

   The catalog is deliberately frozen while open. A command that becomes live waits until
   the next opening; one that becomes unavailable is rejected by fresh dispatch and causes
   the reference to reopen with an explanation. */
import { html, nothing, render, repeat } from "../../vendor/browser-runtime.js";

import {
  bindings,
  clampedRow,
  commandPresentations,
  declaredBindings,
  live,
  routedCommand,
  spell,
  spokenBinding,
  word,
} from "./bindings.js";
import { beginWalk, listWalkPosition } from "../walk-position.js";
import { completeRowSteps, keySequence, neutralStates } from "./presentation.js";
import { restoreReturnPlace } from "./return-stack.js";
import { el } from "../widget-elements.js";
import {
  coveringAuxiliaryFocus,
  coveringAuxiliarySurface,
  ELEMENTS,
  pageScopes,
  auxiliaryAllowsNativeLayer,
} from "./register.js";
import {
  byCommand,
  elementScopes,
  focused,
  merge,
  pruneScopedElements,
  scopeRefs,
  scopesFor,
} from "./scopes.js";
import { repaint } from "../repaint.js";
import { pageSelection } from "../composing/capture.js";
import { availableCommandRoutes, readerIn } from "./dispatch.js";
import { reachScrollers } from "../reach.js";
import { openNativePopovers } from "../native-layers.js";

export const commandReferenceDialog = document.createElement("dialog");
commandReferenceDialog.id = "lf-command-reference";
commandReferenceDialog.className = "lf-ui lf-command-reference";
commandReferenceDialog.setAttribute("aria-label", "Command reference");
commandReferenceDialog.setAttribute("aria-modal", "true");
// Focused on open, so the dialog is not silent to a screen reader.
commandReferenceDialog.tabIndex = -1;

// Page-key presentation owns this retained native control's changing words and shortcut
// metadata. The reference template only seats it.
export const commandReferenceClose = el("button", "lf-btn lf-command-reference-close");
commandReferenceClose.type = "button";
commandReferenceClose.title = "Close the command reference";
commandReferenceClose.setAttribute("aria-label", "Close the command reference");
render("Close", commandReferenceClose);

// Every scope the page has, gathered by title, for the reference. This is not the current
// stack: the catalog answers what the reader could do here, so it includes a card grip's
// commands even while that grip does not hold focus. Rows in the active scope still apply
// their liveness because a visible command must not promise a press that would be refused.
function declaredStack(origin) {
  pruneScopedElements();
  const sections = new Map();
  // Capture this before the dialog takes focus. Repeated widgets share command ids, but
  // their words can name the particular thing in front of the reader; active contributors
  // therefore get the last word in their section.
  const activeScopes = scopesFor(origin);
  const named = (section) =>
    activeScopes.some((scope) => scope.title === section.title);
  // Carry a scope's sequence down to each row before same-title sections merge. The prefix
  // belongs only to the rows that scope contributed.
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
    const declared = new Map();
    // Registration order follows asynchronous upgrade. Document order gives the reference
    // a stable shape across loads.
    const held = [...scopeRefs]
      .map((ref) => ref.deref())
      .filter((node) => node?.isConnected && elementScopes.get(node)?.title);
    held.sort((left, right) =>
      left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
    );
    for (const node of held) {
      const section = elementScopes.get(node);
      merge(declared, { ...section, rows: referenceRows(section) });
    }
    // Reapply the active path from outside in so the innermost live instance supplies
    // dynamic words for command ids shared by several instances.
    for (const section of activeScopes.toReversed())
      if (section.title) merge(declared, { ...section, rows: referenceRows(section) });
    for (const section of declared.values())
      merge(sections, { ...section, at: () => named(section) });
  }
  // A way out reads after the interaction it exits.
  const exit = (row) => (bindings(row).includes("Escape") ? 1 : 0);
  return [...sections.values()].map((section) => ({
    ...section,
    rows: [...section.rows.values()].sort((left, right) => exit(left) - exit(right)),
  }));
}

let commandRoutesAtOpen = new Map();
let commandReferenceIsOpen = false;
let commandReferenceOrigin = null;
let commandReferenceLayers = [];
let commandReferenceBoundary = null;
let commandReferenceInvoke = null;
let commandReferenceCaptureOrigin = null;

const EMPTY_CATALOG = {
  total: 0,
  entries: [],
  sections: [],
};
let commandReferenceCatalog = EMPTY_CATALOG;
let commandReferenceState = {
  query: "",
  selectedCommandId: null,
  metaOverride: null,
};
let commandReferenceView = {
  shown: 0,
  metadata: "",
  bindingMatches: [],
  sections: [],
  visibleCommands: [],
  selectedCommandId: null,
  tabStopCommandId: null,
};

const commandReferenceWords = (value) =>
  String(value ?? "")
    .toLocaleLowerCase()
    .replace(/\s+/g, " ")
    .trim();

// A binding query retains a trailing separator: `g ` means the routes below the `g`
// prefix. Case is retained for the first rank so `g t` and `g T` remain distinct.
const commandReferenceBinding = (value) =>
  String(value ?? "")
    .replace(/^\s+/, "")
    .replace(/\s+/g, " ");

const availableWhere = (row, scopeTitle, scopeReach) => {
  const place = word(row.reach) ?? word(scopeReach) ?? scopeTitle;
  return `Available ${place.charAt(0).toLocaleLowerCase()}${place.slice(1)}`;
};

const spokenReferenceSteps = (row, route, steps, declared) => {
  const alternatives = route ? [route.binding] : declared;
  if (alternatives.length !== 1) return steps;
  const binding = alternatives[0];
  const spoken = [...steps];
  const index = spoken.lastIndexOf(spell(binding));
  if (index !== -1) spoken[index] = spokenBinding(binding);
  return spoken;
};

// Evaluate every dynamic declaration once while opening. Search never calls back into the
// register, and rendered records retain no executable command or liveness function.
function captureCommandReferenceCatalog() {
  const referenceScopes = declaredStack(commandReferenceOrigin?.control)
    .map((scope) => {
      const inScope = readerIn(scope) || scope.liveInCommandReference;
      const rows = scope.rows
        .filter(
          (row) =>
            row.does &&
            (!inScope ||
              (row.commandReferenceWhen ? row.commandReferenceWhen() : live(row))),
        )
        .map((row) => {
          const sequence = [...(word(row.sequence) ?? [])];
          const declared = [...declaredBindings(row)];
          const rowBindings = [...bindings(row)];
          const baseDoes = word(row.does);
          return {
            row,
            sequence,
            declared,
            rowBindings,
            baseDoes,
            familySteps: [...sequence, ...completeRowSteps(row)],
            presentations: [...commandPresentations(row)],
          };
        });
      return { scope, rows };
    })
    .filter(({ rows }) => rows.length);

  const available = (rowInfo, route) => {
    const routes = commandRoutesAtOpen.get(rowInfo.row) ?? new Set();
    const alternatives = route ? [route.binding] : rowInfo.rowBindings;
    return alternatives.some((binding) => routes.has(binding));
  };

  // One command id is one capability. Prefer its reachable presentation over an earlier
  // unreachable one, as when an Ask digit replaces a shadowed intrinsic binding.
  const preferred = new Map();
  for (const { rows } of referenceScopes)
    for (const rowInfo of rows)
      for (const { id, route } of rowInfo.presentations) {
        const candidate = {
          row: rowInfo.row,
          binding: route?.binding ?? null,
          available: available(rowInfo, route),
        };
        const prior = preferred.get(id);
        if (!prior || (!prior.available && candidate.available))
          preferred.set(id, candidate);
      }

  const presented = new Set();
  const sections = [];
  const entries = [];
  let entryIndex = 0;
  for (const { scope, rows } of referenceScopes) {
    const sectionOrder = sections.length;
    const sectionTitle = scope.title ?? "On this page";
    const sectionEntries = [];
    for (const rowInfo of rows) {
      for (const { id, route } of rowInfo.presentations) {
        const chosen = preferred.get(id);
        if (
          chosen?.row !== rowInfo.row ||
          chosen.binding !== (route?.binding ?? null) ||
          presented.has(id)
        )
          continue;
        presented.add(id);
        const action = word(route?.does ?? rowInfo.baseDoes);
        const steps = [...rowInfo.sequence, ...completeRowSteps(rowInfo.row, route)];
        const alternatives = route ? [route.binding] : rowInfo.rowBindings;
        const isAvailable = available(rowInfo, route);
        const entry = {
          id,
          rowId: `lf-command-reference-row-${entryIndex}`,
          keyId: `lf-command-reference-key-${entryIndex}`,
          sectionTitle,
          order: sectionEntries.length,
          sequenceControl: Boolean(rowInfo.row.sequenceControl),
          keyLabel: rowInfo.declared.length === 0 && rowInfo.row.decision !== undefined,
          steps,
          spokenSteps: spokenReferenceSteps(
            rowInfo.row,
            route,
            steps,
            rowInfo.declared,
          ),
          action,
          actionable: Boolean(
            (rowInfo.row.run || routedCommand(route)) &&
            rowInfo.row.runFromCommandReference !== false,
          ),
          available: isAvailable,
          unavailableMessage: availableWhere(rowInfo.row, sectionTitle, scope.reach),
          bindingForms: alternatives.map((binding) => ({
            display: [...rowInfo.sequence, spell(binding)].join(" "),
            spoken: [...rowInfo.sequence, spokenBinding(binding)].join(" "),
          })),
          directWords: commandReferenceWords(
            `${id} ${sectionTitle} ${steps.join(" ")} ${action} ${word(
              route?.line ?? rowInfo.row.line,
            )}`,
          ),
          familyWords: commandReferenceWords(
            `${rowInfo.row.id} ${rowInfo.familySteps.join(" ")} ${rowInfo.baseDoes}`,
          ),
        };
        entryIndex += 1;
        entries.push(entry);
        sectionEntries.push(entry);
      }
    }
    sections.push({
      id: `lf-command-reference-section-${sectionOrder}`,
      title: sectionTitle,
      words: commandReferenceWords(sectionTitle),
      order: sectionOrder,
      entries: sectionEntries,
    });
  }
  return {
    total: entries.length,
    entries,
    sections,
  };
}

// Rank the frozen catalog without reading or moving its rendered rows.
function projectCommandReference(catalog, state) {
  const query = commandReferenceWords(state.query);
  const bindingQuery = commandReferenceBinding(state.query);
  const foldedBindingQuery = bindingQuery.toLocaleLowerCase();
  const directMatch =
    Boolean(query) &&
    catalog.entries.some((entry) => entry.directWords.includes(query));
  const ranked = catalog.sections.flatMap((section) => {
    const sectionMatch = Boolean(query) && section.words.includes(query);
    return section.entries.map((entry) => {
      const exactBinding =
        Boolean(bindingQuery) &&
        entry.bindingForms.some(({ display }) => display.startsWith(bindingQuery));
      const foldedBinding =
        Boolean(foldedBindingQuery) &&
        entry.bindingForms.some(({ display }) =>
          display.toLocaleLowerCase().startsWith(foldedBindingQuery),
        );
      const spokenPrefix =
        Boolean(foldedBindingQuery) &&
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
      return { entry, section, rank };
    });
  });
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
  const promoted = new Set(bindingMatches.map(({ entry }) => entry.id));
  const sections = catalog.sections
    .map((section) => {
      const matches = ranked
        .filter(
          (candidate) =>
            candidate.section === section &&
            Number.isFinite(candidate.rank) &&
            !promoted.has(candidate.entry.id),
        )
        .sort(
          (left, right) =>
            left.rank - right.rank || left.entry.order - right.entry.order,
        );
      return {
        ...section,
        rank: matches[0]?.rank ?? Infinity,
        entries: matches.map(({ entry }) => entry),
      };
    })
    .sort((left, right) => left.rank - right.rank || left.order - right.order);
  const visibleEntries = [
    ...bindingMatches.map(({ entry }) => ({ entry, promoted: true })),
    ...sections.flatMap(({ entries: visible }) =>
      visible.map((entry) => ({ entry, promoted: false })),
    ),
  ];
  const visibleCommands = visibleEntries.filter(({ entry }) => entry.actionable);
  const selected = visibleCommands.find(
    ({ entry }) => entry.id === state.selectedCommandId,
  );
  const selectedCommandId = selected?.entry.id ?? null;
  const shown = ranked.filter(({ rank }) => Number.isFinite(rank)).length;
  const metadata =
    state.metaOverride ??
    (query
      ? `${shown} of ${catalog.total} commands · ↑↓ choose · ⏎ activate`
      : `${catalog.total} commands · ↑↓ choose · ⏎ activate`);
  return {
    shown,
    metadata,
    bindingMatches: bindingMatches.map(({ entry }) => entry),
    sections,
    visibleCommands,
    selectedCommandId,
    tabStopCommandId: selectedCommandId ?? visibleCommands[0]?.entry.id ?? null,
  };
}

function updateCommandReferenceView() {
  let view = projectCommandReference(commandReferenceCatalog, commandReferenceState);
  // Filtering a selected command away clears the selection rather than reviving it when
  // a later query happens to include the command again.
  if (commandReferenceState.selectedCommandId && !view.selectedCommandId) {
    commandReferenceState = {
      ...commandReferenceState,
      selectedCommandId: null,
    };
    view = projectCommandReference(commandReferenceCatalog, commandReferenceState);
  }
  commandReferenceView = view;
}

// The existing key presentation primitive returns a DOM subtree. Catalog entries are
// replaced at each opening, so a weak view cache keeps those unchanged nodes through
// local Lit renders without putting DOM into the catalog or retaining stale entries.
const commandKeySequences = new WeakMap();
function commandKeySequence(entry) {
  const retained = commandKeySequences.get(entry);
  if (retained) return retained;
  const sequence = keySequence(
    entry.steps,
    neutralStates(entry.steps),
    entry.spokenSteps,
  );
  sequence.id = entry.keyId;
  if (entry.keyLabel) sequence.classList.add("lf-key-label");
  commandKeySequences.set(entry, sequence);
  return sequence;
}

function activateCommandEntry(entry) {
  if (!entry.available) {
    commandReferenceState = {
      ...commandReferenceState,
      metaOverride: entry.unavailableMessage,
    };
    return presentCommandReference();
  }
  // Restore the displaced origin first, then let fresh dispatch choose the command's
  // destination on the next frame.
  const origin = commandReferenceOrigin;
  const invokeCommand = commandReferenceInvoke;
  const captureOrigin = commandReferenceCaptureOrigin;
  closeCommandReference();
  requestAnimationFrame(() => {
    if (invokeCommand?.(entry.id, origin)) return;
    openCommandReference(invokeCommand, captureOrigin);
    commandReferenceState = {
      ...commandReferenceState,
      metaOverride: "That command is no longer available",
    };
    presentCommandReference();
  });
}

function commandEntryTemplate(entry, promoted = false) {
  const selected = commandReferenceView.selectedCommandId === entry.id;
  const tabStop = commandReferenceView.tabStopCommandId === entry.id;
  const action = entry.actionable
    ? html`<button
        type="button"
        class="lf-command-reference-command"
        data-lf-command=${entry.id}
        data-lf-available=${String(entry.available)}
        data-lf-selected=${String(selected)}
        aria-describedby=${entry.keyId}
        .tabIndex=${tabStop ? 0 : -1}
        title=${entry.available ? "Run command" : entry.unavailableMessage}
        @click=${() => activateCommandEntry(entry)}
        .textContent=${entry.action}
      ></button>`
    : entry.action;
  const scope = promoted
    ? html`<span class="lf-command-reference-scope">${entry.sectionTitle}</span>`
    : nothing;
  // Whitespace in this cell is observable to accessibility and command consumers.
  // prettier-ignore
  const actionBody = html`<div class="lf-command-reference-action">${action}${scope}</div>`;
  const actionCell = html`<td role="gridcell">${actionBody}</td>`;
  return html`
    <tr
      id=${entry.rowId}
      role="row"
      class=${entry.sequenceControl ? "lf-sequence-command" : ""}
      data-lf-command=${entry.id}
      aria-selected=${entry.actionable ? String(selected) : nothing}
    >
      <td role="gridcell">${commandKeySequence(entry)}</td>
      ${actionCell}
    </tr>
  `;
}

const headingRow = (id, title) => html`
  <div role="row">
    <div role="gridcell"><h3 id=${id}>${title}</h3></div>
  </div>
`;

function commandSectionTemplate(section) {
  return html`
    <section
      class="lf-command-reference-section"
      role="rowgroup"
      aria-labelledby=${section.id}
      ?hidden=${section.entries.length === 0}
    >
      ${headingRow(section.id, section.title)}
      <table role="presentation">
        ${repeat(
          section.entries,
          (entry) => entry.id,
          (entry) => commandEntryTemplate(entry),
        )}
      </table>
    </section>
  `;
}

function commandReferenceTemplate() {
  const selected = commandReferenceView.visibleCommands.find(
    ({ entry }) => entry.id === commandReferenceView.selectedCommandId,
  );
  return html`
    <div class="lf-command-reference-head">
      <div class="lf-command-reference-title">Command reference</div>
      ${commandReferenceClose}
    </div>
    <input
      type="search"
      name="shortcut-search"
      class="lf-command-reference-search"
      placeholder="Find a key or action"
      aria-label="Search commands"
      role="combobox"
      aria-autocomplete="list"
      aria-expanded="true"
      aria-haspopup="grid"
      aria-controls="lf-command-reference-results"
      aria-activedescendant=${selected?.entry.rowId ?? nothing}
      autocomplete="off"
      spellcheck="false"
      @input=${readCommandReferenceSearch}
    />
    <div
      class="lf-command-reference-meta"
      aria-live="polite"
      .textContent=${commandReferenceView.metadata}
    ></div>
    <div
      id="lf-command-reference-results"
      class="lf-command-reference-results"
      role="grid"
      aria-label="Command reference"
    >
      <section
        class="lf-command-reference-section lf-command-reference-binding-matches"
        role="rowgroup"
        aria-labelledby="lf-command-reference-binding-matches"
        ?hidden=${commandReferenceView.bindingMatches.length === 0}
      >
        ${headingRow("lf-command-reference-binding-matches", "Binding matches")}
        <table role="presentation">
          ${repeat(
            commandReferenceView.bindingMatches,
            (entry) => entry.id,
            (entry) => commandEntryTemplate(entry, true),
          )}
        </table>
      </section>
      ${repeat(
        commandReferenceView.sections,
        (section) => section.id,
        commandSectionTemplate,
      )}
      <div role="row" ?hidden=${commandReferenceView.shown !== 0}>
        <div class="lf-command-reference-empty" role="gridcell">
          No matching commands
        </div>
      </div>
    </div>
  `;
}

function presentCommandReference() {
  updateCommandReferenceView();
  render(commandReferenceTemplate(), commandReferenceDialog);
}

function readCommandReferenceSearch(event) {
  commandReferenceState = {
    ...commandReferenceState,
    query: event.currentTarget.value,
    metaOverride: null,
  };
  presentCommandReference();
}

commandReferenceDialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeCommandReference();
});

// A modal dialog's backdrop reports the dialog itself as the click target. Compare the
// pointer with the painted box so the backdrop remains a light-dismiss surface.
commandReferenceDialog.addEventListener("mousedown", (event) => {
  if (event.target !== commandReferenceDialog) return;
  const box = commandReferenceDialog.getBoundingClientRect();
  if (
    event.clientX < box.left ||
    event.clientX > box.right ||
    event.clientY < box.top ||
    event.clientY > box.bottom
  ) {
    event.preventDefault();
    closeCommandReference();
  }
});

function showCommandReference(open, restoreFocus, invokeCommand, captureOrigin) {
  const fresh = open && !commandReferenceIsOpen;
  // Focusing a text input replaces the document selection. Keep a passage the reader has
  // in hand and focus Close instead; an ordinary opening lands directly in search.
  const preserveSelection = fresh && Boolean(pageSelection());
  const handBack = !open && restoreFocus && commandReferenceDialog.contains(focused());
  let origin = handBack ? commandReferenceOrigin : null;
  const restore = origin?.control ?? null;
  const closing = !open && commandReferenceDialog.open;
  if (fresh) {
    commandReferenceOrigin = captureOrigin();
    commandReferenceLayers = openNativePopovers();
    commandReferenceBoundary = coveringAuxiliarySurface();
    // The displaced page decides what can run. Capture before the reference's own scope
    // becomes active, then gather its instructional rows after it does.
    commandRoutesAtOpen = availableCommandRoutes();
    commandReferenceInvoke = invokeCommand;
    commandReferenceCaptureOrigin = captureOrigin;
  }
  commandReferenceIsOpen = open;
  if (fresh) {
    commandReferenceCatalog = captureCommandReferenceCatalog();
    commandReferenceState = {
      query: "",
      selectedCommandId: null,
      metaOverride: null,
    };
    presentCommandReference();
    const search = commandReferenceDialog.querySelector(".lf-command-reference-search");
    const results = commandReferenceDialog.querySelector(
      ".lf-command-reference-results",
    );
    // Native editing and scrolling values begin fresh and remain untouched by local Lit
    // renders.
    search.value = "";
    results.scrollTop = 0;
  }
  commandReferenceDialog.classList.toggle("open", open);
  if (open && !commandReferenceDialog.open) commandReferenceDialog.showModal();
  else if (!open && commandReferenceDialog.open) commandReferenceDialog.close();

  // Restore native layers in their prior order before focus returns to a control inside
  // one of them.
  if (closing) {
    for (const layer of commandReferenceLayers) {
      if (!layer.isConnected || layer.matches(":popover-open")) continue;
      if (!auxiliaryAllowsNativeLayer(layer, commandReferenceBoundary)) continue;
      if (restore && layer.contains(restore))
        layer.lfInvoker?.focus({ preventScroll: true });
      layer.showPopover();
    }
    const originNode = origin?.control ?? origin?.reading;
    if (
      originNode &&
      !auxiliaryAllowsNativeLayer(originNode, commandReferenceBoundary)
    ) {
      const focus = coveringAuxiliaryFocus();
      origin = focus ? { control: focus, reading: null } : null;
    }
    commandReferenceLayers = [];
    commandReferenceBoundary = null;
  }

  // The results are a real overflow region and must enter the modal Tab loop.
  if (open) reachScrollers(commandReferenceDialog);
  if (open)
    commandReferenceDialog
      .querySelector(
        preserveSelection
          ? ".lf-command-reference-close"
          : ".lf-command-reference-search",
      )
      .focus({ preventScroll: true });
  repaint();
  if (!open && origin) restoreReturnPlace(origin);
}

const commandReferenceStops = () =>
  [
    ...commandReferenceDialog.querySelectorAll(
      'button, input, [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((node) => node.tabIndex >= 0 && node.checkVisibility());

export function moveCommandReferenceFocus(dir) {
  const stops = commandReferenceStops();
  if (!stops.length) return commandReferenceDialog.focus({ preventScroll: true });
  const at = stops.indexOf(focused());
  const next =
    at < 0
      ? dir > 0
        ? stops[0]
        : stops.at(-1)
      : stops[(at + dir + stops.length) % stops.length];
  next.focus({ preventScroll: true });
}

const commandButton = (id) =>
  [...commandReferenceDialog.querySelectorAll(".lf-command-reference-command")].find(
    (button) => button.dataset.lfCommand === id,
  ) ?? null;

const focusedCommandId = () =>
  focused()?.matches?.(".lf-command-reference-command")
    ? focused().dataset.lfCommand
    : null;

export const commandReferenceCommandActive = () =>
  commandReferenceView.visibleCommands.length > 0 &&
  (focused()?.matches?.(
    ".lf-command-reference-search, .lf-command-reference-command",
  ) ??
    false);

export function moveCommandReferenceSelection(dir) {
  const ids = commandReferenceView.visibleCommands.map(({ entry }) => entry.id);
  if (!ids.length) return;
  const focusedId = focusedCommandId();
  const nextId = clampedRow(
    ids,
    focusedId ?? commandReferenceState.selectedCommandId,
    dir,
  );
  const nextRecord = commandReferenceView.visibleCommands.find(
    ({ entry }) => entry.id === nextId,
  );
  const scopeWords = nextRecord.promoted ? nextRecord.entry.sectionTitle : "";
  commandReferenceState = {
    ...commandReferenceState,
    selectedCommandId: nextId,
    metaOverride: `${nextRecord.entry.action}${scopeWords} · ${
      nextRecord.entry.steps[0]
    } · ⏎ activate`,
  };
  presentCommandReference();
  const next = commandButton(nextId);
  if (focusedId) next.focus({ preventScroll: true });
  next.closest("tr").scrollIntoView({ block: "nearest" });
  beginWalk("shortcut-command", "Command", () => {
    const current = focusedCommandId() ?? commandReferenceState.selectedCommandId;
    return listWalkPosition(
      commandReferenceView.visibleCommands.map(({ entry }) => entry.id),
      current,
    );
  });
}

export function activateSelectedCommand() {
  if (!commandReferenceCommandActive()) return false;
  const id =
    focusedCommandId() ??
    commandReferenceState.selectedCommandId ??
    commandReferenceView.visibleCommands[0]?.entry.id;
  const record = commandReferenceView.visibleCommands.find(
    ({ entry }) => entry.id === id,
  );
  if (!record) return false;
  activateCommandEntry(record.entry);
  return true;
}

commandReferenceClose.onclick = () => closeCommandReference();

export const commandReferenceOpen = () => commandReferenceIsOpen;
// The opening command supplies the action chosen from this particular reference. The
// rendered catalog retains only ids and sends one back through that injected authority.
export const openCommandReference = (invokeCommand, captureOrigin) =>
  showCommandReference(true, true, invokeCommand, captureOrigin);
export const closeCommandReference = (restoreFocus = true) =>
  showCommandReference(false, restoreFocus, null, null);
