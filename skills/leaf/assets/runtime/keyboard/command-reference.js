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
import {
  completeRowSteps,
  keySequenceModel,
  keySequenceTemplate,
  neutralStates,
} from "./presentation.js";
import { restoreReturnPlace } from "./layer-stack.js";
import { el, keeps } from "../widget-elements.js";
import {
  coveringAuxiliaryFocus,
  coveringAuxiliarySurface,
  ELEMENTS,
  pageScopes,
  auxiliaryAllowsNativeLayer,
} from "./register.js";
import {
  byCommand,
  focused,
  merge,
  pruneScopedElements,
  scopeRefs,
  scopesAt,
  scopesFor,
} from "./scopes.js";
import { repaint } from "../repaint.js";
import { pageSelection } from "../composing/capture.js";
import { availableCommandRoutes, readerIn } from "./dispatch.js";
import { reachScrollers } from "../reach.js";
import { openPopovers } from "./layer-stack.js";

export const commandReferenceDialog = document.createElement("dialog");
commandReferenceDialog.id = "lf-command-reference";
commandReferenceDialog.className = "lf-ui lf-command-reference";
commandReferenceDialog.setAttribute("aria-label", "Command reference");
commandReferenceDialog.setAttribute("closedby", "any");
commandReferenceDialog.setAttribute("aria-modal", "true");
// Focused on open, so the dialog is not silent to a screen reader.
commandReferenceDialog.tabIndex = -1;

// Page-key presentation owns this retained native control's changing words and shortcut
// metadata. The reference template only seats it.
export const commandReferenceClose = el("button", "lf-btn lf-command-reference-close");
commandReferenceClose.type = "button";

export function presentCommandReferenceClose(returningToMore) {
  const label = returningToMore ? "Back to more shortcuts" : "Close";
  const title = returningToMore
    ? "Back to more shortcuts"
    : "Close the command reference";
  render(label, commandReferenceClose);
  keeps(commandReferenceClose, "data-lf-key-title", title);
  keeps(commandReferenceClose, "aria-label", title);
}
presentCommandReferenceClose(false);

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
    activeScopes.some(
      (scope) => scope.title === section.title && (!scope.when || scope.when()),
    );
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
      .filter(
        (node) => node?.isConnected && scopesAt(node).some((scope) => scope.title),
      );
    held.sort((left, right) =>
      left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
    );
    const seen = new Set();
    for (const node of held) {
      for (const section of scopesAt(node)) {
        if (!section.title) continue;
        const identity = section.identity ?? section;
        if (seen.has(identity)) continue;
        seen.add(identity);
        merge(declared, { ...section, rows: referenceRows(section) });
      }
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

const EMPTY_CATALOG = Object.freeze({
  total: 0,
  entries: Object.freeze([]),
  sections: Object.freeze([]),
});
let commandReferenceCatalog = EMPTY_CATALOG;
let commandReferenceState = {
  query: "",
  selectedCommandId: null,
  metaOverride: null,
};
let commandReferenceView = {
  shown: 0,
  metadata: "",
  bindingHeading: null,
  sectionHeadings: [],
  entryPresentations: [],
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
        const spokenSteps = spokenReferenceSteps(
          rowInfo.row,
          route,
          steps,
          rowInfo.declared,
        );
        const entry = Object.freeze({
          id,
          rowId: `lf-command-reference-row-${entryIndex}`,
          keyId: `lf-command-reference-key-${entryIndex}`,
          sectionId: `lf-command-reference-section-${sectionOrder}`,
          sectionTitle,
          order: sectionEntries.length,
          sequenceControl: Boolean(rowInfo.row.sequenceControl),
          keyLabel: rowInfo.declared.length === 0 && rowInfo.row.decision !== undefined,
          steps: Object.freeze(steps),
          keySequence: keySequenceModel(steps, neutralStates(steps), spokenSteps),
          action,
          actionable: Boolean(
            (rowInfo.row.run || routedCommand(route)) &&
            rowInfo.row.runFromCommandReference !== false,
          ),
          available: isAvailable,
          unavailableMessage: availableWhere(rowInfo.row, sectionTitle, scope.reach),
          bindingForms: Object.freeze(
            alternatives.map((binding) =>
              Object.freeze({
                display: [...rowInfo.sequence, spell(binding)].join(" "),
                spoken: [...rowInfo.sequence, spokenBinding(binding)].join(" "),
              }),
            ),
          ),
          directWords: commandReferenceWords(
            `${id} ${sectionTitle} ${steps.join(" ")} ${action} ${word(
              route?.line ?? rowInfo.row.line,
            )}`,
          ),
          familyWords: commandReferenceWords(
            `${rowInfo.row.id} ${rowInfo.familySteps.join(" ")} ${rowInfo.baseDoes}`,
          ),
        });
        entryIndex += 1;
        entries.push(entry);
        sectionEntries.push(entry);
      }
    }
    sections.push(
      Object.freeze({
        id: `lf-command-reference-section-${sectionOrder}`,
        title: sectionTitle,
        words: commandReferenceWords(sectionTitle),
        order: sectionOrder,
        entries: Object.freeze(sectionEntries),
      }),
    );
  }
  return Object.freeze({
    total: entries.length,
    entries: Object.freeze(entries),
    sections: Object.freeze(sections),
  });
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
  let presentationOrder = 0;
  const bindingHeading = bindingMatches.length
    ? Object.freeze({ order: presentationOrder++ })
    : null;
  const entryPresentations = bindingMatches.map(({ entry }) =>
    Object.freeze({ entry, promoted: true, order: presentationOrder++ }),
  );
  const sectionHeadings = sections.map((section) => {
    const heading = Object.freeze({
      id: section.id,
      title: section.title,
      shown: section.entries.length > 0,
      order: section.entries.length > 0 ? presentationOrder++ : -1,
    });
    entryPresentations.push(
      ...section.entries.map((entry) =>
        Object.freeze({ entry, promoted: false, order: presentationOrder++ }),
      ),
    );
    return heading;
  });
  return {
    shown,
    metadata,
    bindingHeading,
    sectionHeadings,
    entryPresentations,
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

function commandEntryTemplate(entry, promoted = false, shown = true) {
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
      ?hidden=${!shown}
    >
      <td role="gridcell">
        ${keySequenceTemplate(entry.keySequence, {
          id: entry.keyId,
          label: entry.keyLabel,
        })}
      </td>
      ${actionCell}
    </tr>
  `;
}

const headingRow = (id, title, hidden = false) => html`
  <tbody ?hidden=${hidden}>
    <tr role="row">
      <th role="gridcell" colspan="2"><h3 id=${id}>${title}</h3></th>
    </tr>
  </tbody>
`;

const commandReferenceItems = () => {
  const visible = [];
  if (commandReferenceView.bindingHeading)
    visible.push({
      kind: "heading",
      key: "heading:bindings",
      id: "lf-command-reference-binding-matches",
      title: "Binding matches",
      order: commandReferenceView.bindingHeading.order,
    });
  for (const heading of commandReferenceView.sectionHeadings)
    if (heading.shown)
      visible.push({
        kind: "heading",
        key: `heading:${heading.id}`,
        id: heading.id,
        title: heading.title,
        order: heading.order,
      });
  for (const presentation of commandReferenceView.entryPresentations)
    visible.push({
      kind: "entry",
      key: `entry:${presentation.entry.id}`,
      ...presentation,
    });
  visible.sort((left, right) => left.order - right.order);

  // Keep every catalog row under this one keyed parent. Filtering and binding promotion
  // then reorder retained rows instead of recreating their native controls and keycaps.
  const visibleKeys = new Set(visible.map(({ key }) => key));
  const hidden = [
    {
      kind: "heading",
      key: "heading:bindings",
      id: "lf-command-reference-binding-matches",
      title: "Binding matches",
    },
    ...commandReferenceCatalog.sections.map((section) => ({
      kind: "heading",
      key: `heading:${section.id}`,
      id: section.id,
      title: section.title,
    })),
    ...commandReferenceCatalog.sections.flatMap((section) =>
      section.entries.map((entry) => ({
        kind: "entry",
        key: `entry:${entry.id}`,
        entry,
        promoted: false,
      })),
    ),
  ].filter(({ key }) => !visibleKeys.has(key));
  return [...visible, ...hidden.map((item) => ({ ...item, hidden: true }))];
};

function commandReferenceItemTemplate(item) {
  if (item.kind === "heading") return headingRow(item.id, item.title, item.hidden);
  return html`<tbody
    role="rowgroup"
    aria-labelledby=${
      item.promoted ? "lf-command-reference-binding-matches" : item.entry.sectionId
    }
    class=${item.promoted ? "lf-command-reference-binding-matches" : nothing}
    ?hidden=${item.hidden}
  >
    ${commandEntryTemplate(item.entry, item.promoted, !item.hidden)}
  </tbody>`;
}

function commandReferenceTemplate() {
  const selected = commandReferenceView.visibleCommands.find(
    ({ entry }) => entry.id === commandReferenceView.selectedCommandId,
  );
  const items = commandReferenceItems();
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
      <table role="presentation">
        <colgroup>
          <col class="lf-command-reference-key-column" />
          <col />
        </colgroup>
        ${repeat(items, (item) => item.key, commandReferenceItemTemplate)}
      </table>
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

// Escape and a backdrop press both arrive here as a close request.
commandReferenceDialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeCommandReference();
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
    commandReferenceLayers = openPopovers();
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
  commandReferenceState = {
    ...commandReferenceState,
    selectedCommandId: nextId,
    metaOverride: `${nextRecord.entry.action} · ${
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
