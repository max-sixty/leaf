/* The command reference: the complete command catalog behind `?` and its modal search
   context.

   Opening remembers the user's command context and cancellation destination, dismisses
   the auto and hint popovers that modal entry will close, then captures registered
   command vocabulary and executable routes
   before the native dialog moves focus. The resulting catalog contains evaluated display
   values and stable command ids, not callbacks or live predicates. Search, ranking,
   selection, and metadata are local user-session state projected through one Lit
   template. Activation closes the dialog and resolves its id afresh in the same gesture,
   after returning focus to its command context. Escape and Close return to the opening
   control instead, when chrome opened the reference on behalf of another context.
   No deferred dispatch can reinterpret the command at a newer control or take that
   control's focus; a stale row cannot run.

   The native dialog, retained Close button, return place, focus, selection, and scrolling
   stay with this controller. Modal entry follows the platform contract rather than
   rebuilding the popovers it dismisses.

   Every row wears one face, whether or not it can run from where the user is. Its
   section heading already says where it applies, and pressing one that cannot run says
   so in the meta line; muting those rows put most of a page's catalog in a second face
   that read as a different font beside the first.

   A row's description is its button's tooltip, and the meta line under the search
   shows it in place of the title for the row ↑↓ selects, so the keyboard reaches it
   too. As a grey line under the title it made the catalog harder to scan for the few
   rows that have one, so that line shows only where there is no hover to raise the
   tooltip. The meta line keeps one line, cutting a long description short, as the
   selected row does, so the results never move under the walk; a screen reader hears
   it whole. It once stacked every description, hidden, to stand as tall as the
   longest, which left the resting count over a blank line or two.

   The catalog is deliberately frozen while open. A command that becomes live waits until
   the next opening; one that becomes unavailable is rejected by fresh dispatch and causes
   the reference to reopen with an explanation.

   `?` opens it from anywhere a key reaches, and the page's controls carry the same
   door as their Keyboard shortcuts row (page-controls.js), for a pointer. That row
   opens it from where the user was before pressing it, and Escape returns to the row's
   door. */
import { setScroll } from "../arrivals.js";
import {
  showNativeLayer,
  closeNativeLayer,
  dismissPopoversOutside,
} from "./layer-stack.js";
import { scrollIntoView } from "../landing-scroll.js";
import { html, nothing, render, repeat } from "/runtime/framework.js";

import {
  bindings,
  declaredBindings,
  bindingEnabled,
  quickShortcuts,
  setQuickShortcuts,
  clampedRow,
  commandPresentations,
  contextBindings,
  allBindings,
  descriptionOf,
  titleOf,
  live,
  routedCommand,
  spell,
  spokenBinding,
  word,
} from "./bindings.js";
import { beginWalk, listWalkPosition } from "../walk-position.js";
import {
  completeRowKeySteps,
  completeRowSteps,
  stepText,
  keySequenceModel,
  keySequenceTemplate,
  neutralStates,
} from "./key-sequence.js";
import {
  handBack,
  focusDestination,
  focused,
  closeLayer,
  openLayer,
  openerOf,
  rove,
  currentLocationIn,
  deepFocus,
} from "../focus.js";
import { closeControl, offeredAction, searchField } from "../widget-elements.js";
import { keeps } from "../keeps.js";
import { renderedOrder } from "../shadow.js";
import { ELEMENTS, pageCommand, pageScope, pageScopes } from "./register.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "../page-controls.js";
import { EVERYTHING } from "./text-entry.js";
import {
  merge,
  pruneScopedElements,
  scopeRefs,
  scopesAt,
  scopesFor,
} from "./scopes.js";
import { repaint } from "../repaint.js";
import { pageSelection } from "../composing/capture.js";
import { availableCommandRoutes, executeCommand, userIn } from "./dispatch.js";
import { returnPlace } from "../history.js";
import { reachScrollers } from "../reach.js";
import { registerReadingRegion } from "../reading-regions.js";

export const commandReferenceDialog = document.createElement("dialog");
commandReferenceDialog.id = "lf-command-reference";
commandReferenceDialog.className = "lf-ui lf-command-reference";
commandReferenceDialog.setAttribute("aria-label", "Command reference");
commandReferenceDialog.setAttribute("closedby", "any");
commandReferenceDialog.setAttribute("aria-modal", "true");
// Focused on open, so the dialog is not silent to a screen reader.
commandReferenceDialog.tabIndex = -1;
let stopReferenceReading = null;
const commandReferenceSearch = searchField("lf-command-reference-search", {
  name: "shortcut-search",
  label: "Search commands",
  placeholder: "Find a key or action",
});
commandReferenceSearch.addEventListener("input", readCommandReferenceSearch);
// Page-key presentation owns this retained native control's changing name and shortcut
// metadata. The reference template only seats it.
const commandReferenceClose = closeControl({
  name: "Close the command reference",
  className: "lf-command-reference-close",
});

commandReferenceClose.dataset.lfKeyTitle = "Close the command reference";
commandReferenceClose.setAttribute("aria-label", "Close the command reference");
// Retained controls connect with their closed dialog at boot, so their native editor
// and command wiring are ready before the first opening. Local renders only seat them.
commandReferenceDialog.append(commandReferenceSearch, commandReferenceClose);

// Every scope the page has, gathered by title, for the reference. This is not the current
// stack: the catalog answers what the user could do here, so it includes a card grip's
// commands even while that grip does not hold focus. Rows in the active scope still apply
// their liveness because a visible command must not promise a press that would be refused.
function declaredStack(origin) {
  pruneScopedElements();
  const sections = new Map();
  // Capture this before the dialog takes focus. Repeated widgets share command ids, but
  // their words can name the particular thing in front of the user; active contributors
  // therefore get the last word in their section.
  const activeScopes = scopesFor(origin);
  const named = (section) =>
    activeScopes.some(
      (scope) => scope.title === section.title && (!scope.when || scope.when()),
    );
  // Carry a scope's sequence down to each row before same-title sections merge. The prefix
  // belongs only to the rows that scope contributed.
  // Intrinsic and contextual presentations share a canonical command id, but must survive
  // the section merge independently until reachability chooses one. Internal map keys
  // occupy a separate identity space; no authored command id can collide with them.
  const contextualIds = new Map();
  const referenceIdentity = (scope, row) => {
    if (!scope.contextual) return row.id;
    if (!contextualIds.has(row.id)) contextualIds.set(row.id, Symbol(row.id));
    return contextualIds.get(row.id);
  };
  const referenceRows = (scope) =>
    scope.rows.map((row) => [
      referenceIdentity(scope, row),
      // Presentation metadata belongs beside the registered row. Cloning a sequence
      // row loses the identity used by the dispatcher's route-availability snapshot.
      { row, sequence: scope.sequencePrefix ?? scope.sequence ?? row.sequence },
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
    held.sort(renderedOrder);
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
    rows: [...section.rows.values()].sort(
      (left, right) => exit(left.row) - exit(right.row),
    ),
  }));
}

let commandRoutesAtOpen = { on: new Map(), off: new Map() };
let commandReferenceInvoke = null;

const EMPTY_CATALOG = Object.freeze({
  total: 0,
  entries: Object.freeze([]),
  sections: Object.freeze([]),
});
/** @type {ReturnType<typeof captureCommandReferenceCatalog>} */
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

// Titles are written for the surface that shows them most: a compact lowercase word
// for a hint, a sentence for a route only the reference shows. Listed
// together, the reference starts every one with a capital, as a menu does.
const listedTitle = (title) =>
  `${title.charAt(0).toLocaleUpperCase()}${title.slice(1)}`;

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
  const referenceScopes = declaredStack(openerOf(commandReferenceDialog))
    .map((scope) => {
      const inScope = userIn(scope) || scope.liveInCommandReference;
      const rows = scope.rows
        .filter(
          ({ row }) =>
            !inScope ||
            (row.commandReferenceWhen ? row.commandReferenceWhen() : live(row)),
        )
        .map(({ row, sequence: prefix }) => {
          const sequence = [...(word(prefix) ?? [])];
          const declared = [...allBindings(row)];
          const shownBindings = declared.filter(bindingEnabled);
          const referenceRow = { ...row, keys: shownBindings };
          const rowBindings = [...declaredBindings(row)];
          const baseTitle = titleOf(row);
          const baseDescription = descriptionOf(row);
          return {
            row,
            sequence,
            declared,
            rowBindings,
            referenceRow,
            baseTitle,
            baseDescription,
            familySteps: shownBindings.length
              ? [...sequence, ...completeRowSteps(referenceRow)]
              : [],
            presentations: commandPresentations(row, declared, {
              includeUnavailable: true,
            }).map(({ id, route }) => ({
              id,
              route:
                route && route.binding == null
                  ? { ...route, binding: contextBindings(route)[0] }
                  : route,
            })),
          };
        });
      return { scope, rows };
    })
    .filter(({ rows }) => rows.length);

  const available = (rowInfo, route) => {
    const routes =
      commandRoutesAtOpen[quickShortcuts() ? "on" : "off"].get(rowInfo.row) ??
      new Set();
    const alternatives = route ? [route.binding] : rowInfo.rowBindings;
    return rowInfo.declared.length === 0
      ? routes.has(undefined)
      : alternatives.some((binding) => routes.has(binding));
  };
  const actionable = (row, route) =>
    Boolean(
      (row.run || routedCommand(route)) &&
      (routedCommand(route)?.row ?? row).runFromCommandReference !== false,
    );

  // One command id is one capability, with potentially several ways to reach it.
  // A control's native Enter/Space scope can name that capability without an action of
  // its own. Prefer a row the reference can invoke, then teach a keyboard route rather
  // than an unbound control; among keyboard routes,
  // prefer the reachable one (an obligation digit can replace a shadowed intrinsic key).
  // Invoking the reference names the capability, so any executable route makes the
  // entry available even when its displayed sequence has not been entered yet.
  const preferred = new Map();
  const executable = new Set();
  for (const { rows } of referenceScopes)
    for (const rowInfo of rows)
      for (const { id, route } of rowInfo.presentations) {
        const candidate = {
          row: rowInfo.row,
          binding: route?.binding ?? null,
          available: available(rowInfo, route),
          actionable: actionable(rowInfo.row, route),
          keyed: rowInfo.declared.length > 0,
        };
        if (candidate.available) executable.add(id);
        const prior = preferred.get(id);
        if (
          !prior ||
          (!prior.actionable && candidate.actionable) ||
          (prior.actionable === candidate.actionable &&
            ((!prior.keyed && candidate.keyed) ||
              (prior.keyed === candidate.keyed &&
                !prior.available &&
                candidate.available)))
        )
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
        const title = listedTitle(route ? titleOf(route) : rowInfo.baseTitle);
        const description =
          route?.description !== undefined
            ? descriptionOf(route)
            : rowInfo.baseDescription;
        const alternatives = (route ? [route.binding] : rowInfo.declared).filter(
          bindingEnabled,
        );
        const keySteps = alternatives.length
          ? [
              ...rowInfo.sequence.map((step) => [step]),
              ...completeRowKeySteps(rowInfo.referenceRow, route),
            ]
          : [];
        const steps = keySteps.map(stepText);
        const isAvailable = executable.has(id);
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
          descriptionId: `lf-command-reference-description-${entryIndex}`,
          sectionId: `lf-command-reference-section-${sectionOrder}`,
          sectionTitle,
          order: sectionEntries.length,
          sequenceControl: Boolean(rowInfo.row.sequenceControl),
          keyLabel: rowInfo.declared.length === 0 && word(rowInfo.row.label) == null,
          steps: Object.freeze(steps),
          keySequence: steps.length
            ? keySequenceModel(steps, neutralStates(steps), spokenSteps, keySteps)
            : null,
          title,
          description,
          actionable: actionable(rowInfo.row, route),
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
            `${id} ${sectionTitle} ${steps.join(" ")} ${title} ${description ?? ""}`,
          ),
          familyWords: commandReferenceWords(
            `${rowInfo.row.id} ${rowInfo.familySteps.join(" ")} ${rowInfo.baseTitle} ${rowInfo.baseDescription ?? ""}`,
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

// What the meta line says of the row ↑↓ selects. The row already shows its title.
const selectionMeta = (entry) =>
  [entry.description || entry.title, entry.steps[0], "⏎ activate"]
    .filter(Boolean)
    .join(" · ");

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
  // Native modal close and the origin handoff are synchronous, so fresh dispatch sees
  // the original gesture's context before another input can change it.
  const invokeCommand = commandReferenceInvoke;
  const origin = openerOf(commandReferenceDialog);
  const returnTo = commandReferenceReturn;
  closeLayer(
    () => closeCommandReference(false),
    () => handBack(origin),
  );
  if (invokeCommand?.(entry.id)) return;
  // Complete native close before opening its replacement. This microtask still belongs
  // to the same input turn: no newer gesture can intervene as it could before a frame.
  queueMicrotask(() => {
    openCommandReference(invokeCommand, returnTo);
    commandReferenceState = {
      ...commandReferenceState,
      metaOverride: "That command is no longer available",
    };
    presentCommandReference();
  });
}

function commandEntryTemplate(entry, promoted = false, shown = true) {
  const selected = commandReferenceView.selectedCommandId === entry.id;
  const action = entry.actionable
    ? html`<button
        type="button"
        class="lf-command-reference-command"
        data-lf-command=${entry.id}
        data-lf-available=${String(entry.available)}
        data-lf-selected=${String(selected)}
        aria-describedby=${[
          entry.keySequence ? entry.keyId : null,
          entry.description ? entry.descriptionId : null,
        ]
          .filter(Boolean)
          .join(" ")}
        title=${
          [entry.description, entry.available ? "" : entry.unavailableMessage]
            .filter(Boolean)
            .join("\n") || nothing
        }
        @click=${() => activateCommandEntry(entry)}
        .textContent=${entry.title}
      ></button>`
    : entry.title;
  const scope = promoted
    ? html`<span class="lf-command-reference-scope">${entry.sectionTitle}</span>`
    : nothing;
  // Whitespace in these cells is observable to accessibility and command consumers.
  // prettier-ignore
  const actionCell = html`<div role="gridcell" class="lf-command-reference-action">${action}${scope}</div>`;
  // prettier-ignore
  const descriptionCell = entry.description ? html`<div role="gridcell" id=${entry.descriptionId} class="lf-command-reference-description">${entry.description}</div>` : nothing;
  return html`
    <div
      id=${entry.rowId}
      role="row"
      ${offeredAction(
        "row",
        `lf-command-reference-row${entry.sequenceControl ? " lf-sequence-command" : ""}`,
      )}
      data-lf-command=${entry.id}
      aria-selected=${entry.actionable ? String(selected) : nothing}
      ?hidden=${!shown}
    >
      ${actionCell}
      <div role="gridcell" class="lf-command-reference-key">
        ${
          entry.keySequence
            ? keySequenceTemplate(entry.keySequence, {
                id: entry.keyId,
                label: entry.keyLabel,
              })
            : nothing
        }
      </div>
      ${descriptionCell}
    </div>
  `;
}

const headingRow = (id, title, hidden = false) => html`
  <div role="rowgroup" ?hidden=${hidden}>
    <div role="row">
      <div role="gridcell"><h3 class="lf-rows-head" id=${id}>${title}</h3></div>
    </div>
  </div>
`;

const commandReferenceItems = () => {
  const visible = [];
  if (commandReferenceView.bindingHeading)
    visible.push({
      kind: "heading",
      key: "heading:bindings",
      id: "lf-command-reference-binding-matches",
      title: "Matching shortcuts",
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
      title: "Matching shortcuts",
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
  return html`<div
    role="rowgroup"
    aria-labelledby=${
      item.promoted ? "lf-command-reference-binding-matches" : item.entry.sectionId
    }
    class=${item.promoted ? "lf-command-reference-binding-matches" : nothing}
    ?hidden=${item.hidden}
  >
    ${commandEntryTemplate(item.entry, item.promoted, !item.hidden)}
  </div>`;
}

function commandReferenceTemplate() {
  const items = commandReferenceItems();
  return html`
    <div class="lf-command-reference-head">
      <div class="lf-command-reference-title">Command reference</div>
      ${commandReferenceClose}
    </div>
    <label class="lf-command-reference-preference">
      <input
        type="checkbox"
        name="quick-keyboard-shortcuts"
        autocomplete="off"
        .checked=${quickShortcuts()}
        aria-labelledby="lf-quick-keyboard-label"
        aria-describedby="lf-quick-keyboard-help"
        @change=${(event) => {
          setQuickShortcuts(event.currentTarget.checked);
          commandReferenceCatalog = captureCommandReferenceCatalog();
          presentCommandReference();
          repaint();
        }}
      />
      <span id="lf-quick-keyboard-label">Quick keyboard shortcuts</span>
      <small id="lf-quick-keyboard-help"
        >Use letters, numbers and symbols for Leaf actions.</small
      >
    </label>
    ${commandReferenceSearch}
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
      ${repeat(items, (item) => item.key, commandReferenceItemTemplate)}
      <div role="row" ?hidden=${commandReferenceView.shown !== 0}>
        <div class="lf-rows-empty" role="gridcell">No matching commands.</div>
      </div>
    </div>
  `;
}

function presentCommandReference() {
  updateCommandReferenceView();
  render(commandReferenceTemplate(), commandReferenceDialog);
  // The combobox belongs to the native editor, not its component host. Element
  // references keep its result relationships valid across the editor's shadow root.
  const search = commandReferenceSearch.input;
  keeps(search, "role", "combobox");
  keeps(search, "aria-autocomplete", "list");
  keeps(search, "aria-expanded", "true");
  keeps(search, "aria-haspopup", "grid");
  const results = commandReferenceDialog.querySelector(".lf-command-reference-results");
  if (search.ariaControlsElements?.[0] !== results)
    search.ariaControlsElements = [results];
  const selected = commandReferenceView.visibleCommands.find(
    ({ entry }) => entry.id === commandReferenceView.selectedCommandId,
  );
  const row = selected
    ? commandReferenceDialog.querySelector(`#${selected.entry.rowId}`)
    : null;
  if (search.ariaActiveDescendantElement !== row)
    search.ariaActiveDescendantElement = row;
  // The results are one roving group: Tab reaches the selected command, or the first,
  // and the arrows walk the rest (focus.js, `rove`).
  rove(
    commandReferenceDialog.querySelectorAll(".lf-command-reference-command"),
    commandButton(commandReferenceView.tabStopCommandId),
  );
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

let commandReferenceReturn = null;

function showCommandReference(open, restoreFocus, invokeCommand, returnTo) {
  const fresh = open && !commandReferenceDialog.open;
  // Focusing a text input replaces the document selection. Keep a passage the user has
  // in hand and focus Close instead; an ordinary opening lands directly in search.
  const preserveSelection = fresh && Boolean(pageSelection());
  const handingBack =
    !open && restoreFocus && currentLocationIn(commandReferenceDialog);
  const restore = handingBack ? commandReferenceReturn : null;
  if (fresh) {
    commandReferenceInvoke = invokeCommand;
    dismissPopoversOutside(commandReferenceDialog);
    // The origin is read off the scene the reference leaves behind: hiding a popover
    // hands focus back to where the user was when it opened, and that is the place
    // the reference owes them. A control, or nothing: a user working from the page
    // stands on `body`, which is not a place to be given back — focusing it resets the
    // browser's sequential focus navigation starting point to the top of the document,
    // and the user who opened the reference four screens down would Tab from there.
    // A popover opened while nothing held focus lets go as it closes (layer-stack.js),
    // so that user reads as standing on `body` here too.
    openLayer(commandReferenceDialog);
    commandReferenceReturn = returnTo ?? openerOf(commandReferenceDialog);
    commandRoutesAtOpen = {
      on: availableCommandRoutes({ commands: true, quick: true }),
      off: availableCommandRoutes({ commands: true, quick: false }),
    };
  }
  if (fresh) {
    commandReferenceCatalog = captureCommandReferenceCatalog();
    commandReferenceState = {
      query: "",
      selectedCommandId: null,
      metaOverride: null,
    };
    presentCommandReference();
    /** @type {HTMLInputElement} */
    const search = commandReferenceDialog.querySelector(".lf-command-reference-search");
    const results = commandReferenceDialog.querySelector(
      ".lf-command-reference-results",
    );
    // Native editing and scrolling values begin fresh and remain untouched by local Lit
    // renders.
    search.value = "";
    setScroll(results, { top: 0, behavior: "instant" });
    stopReferenceReading = registerReadingRegion({
      id: "lf-region:command-reference",
      host: commandReferenceDialog,
      body: results,
    });
  }
  if (open && !commandReferenceDialog.open) showNativeLayer(commandReferenceDialog);
  // The reference is a bounded interaction rather than a level of the page: it claims the
  // whole keyboard while it stands and hands the user back itself, to the control the
  // press displaced, or to the page where that control has gone — the layer it stood in
  // may have closed under the user while the reference was up — which is where a user
  // who pressed `?` from the page was all along. A closed dialog's search box keeps focus
  // until the browser's next focus fixup, so the repaint below would read the user as
  // still typing there: the close releases it with the dialog, and hands the user back
  // once its repaint has run.
  if (!open) {
    stopReferenceReading?.();
    stopReferenceReading = null;
    closeLayer(
      () => {
        if (commandReferenceDialog.open) closeNativeLayer(commandReferenceDialog);
        if (currentLocationIn(commandReferenceDialog))
          /** @type {HTMLElement | null} */ (deepFocus())?.blur();
        repaint();
      },
      handingBack && (() => handBack(restore)),
    );
    return;
  }
  // The results are a real overflow region, so they take a Tab stop of their own.
  reachScrollers(commandReferenceDialog);
  focusDestination(
    commandReferenceDialog.querySelector(
      preserveSelection
        ? ".lf-command-reference-close"
        : ".lf-command-reference-search",
    ),
    "move",
  );
  repaint();
}

const commandButton = (id) =>
  [
    .../** @type {NodeListOf<HTMLElement>} */ (
      commandReferenceDialog.querySelectorAll(".lf-command-reference-command")
    ),
  ].find((button) => button.dataset.lfCommand === id) ?? null;

const focusedCommandId = () =>
  focused()?.matches?.(".lf-command-reference-command")
    ? focused().dataset.lfCommand
    : null;

const commandReferenceCommandActive = () =>
  commandReferenceView.visibleCommands.length > 0 &&
  (focused() === commandReferenceSearch.input || focusedCommandId() !== null);

function moveCommandReferenceSelection(dir) {
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
    metaOverride: selectionMeta(nextRecord.entry),
  };
  presentCommandReference();
  const next = commandButton(nextId);
  if (focusedId) focusDestination(next, "move");
  scrollIntoView(next.closest('[role="row"]'), { block: "nearest" });
  beginWalk("shortcut-command", "Command", () => {
    const current = focusedCommandId() ?? commandReferenceState.selectedCommandId;
    return listWalkPosition(
      commandReferenceView.visibleCommands.map(({ entry }) => entry.id),
      current,
    );
  });
}

function activateSelectedCommand() {
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

// The opening command supplies the action chosen from this particular reference. The
// rendered catalog retains only ids and sends one back through that injected authority.
const openCommandReference = (invokeCommand, returnTo = null) =>
  showCommandReference(true, true, invokeCommand, returnTo);
const closeCommandReference = (restoreFocus = true) =>
  showCommandReference(false, restoreFocus, null, null);

// The dialog's own keys. It is a modal search context and claims the whole keyboard while
// it stands, so its rows are the only ones the user can reach; the boundary's one route
// through to another layer is the universal reference binding itself. None of these runs
// from the reference, which is this dialog.
pageScope("command reference", {
  title: "In the command reference",
  escape: "inner",
  root: () => commandReferenceDialog,
  at: () => commandReferenceDialog.open,
  claims: EVERYTHING,
  rows: [
    {
      id: "command.reference.command.next",
      touch: false,
      keys: ["ArrowDown"],
      title: "choose next",
      repeat: true,
      travels: true,
      runFromCommandReference: false,
      // The list is built before search receives focus, so physical liveness is false at
      // that instant even though the reference always lists this instruction.
      commandReferenceWhen: () => true,
      when: () => commandReferenceCommandActive(),
      run: () => moveCommandReferenceSelection(1),
    },
    {
      id: "command.reference.command.previous",
      touch: false,
      keys: ["ArrowUp"],
      title: "choose previous",
      repeat: true,
      travels: true,
      runFromCommandReference: false,
      commandReferenceWhen: () => true,
      when: () => commandReferenceCommandActive(),
      run: () => moveCommandReferenceSelection(-1),
    },
    {
      id: "command.reference.command.activate",
      touch: false,
      keys: ["Enter"],
      title: "activate",
      runFromCommandReference: false,
      commandReferenceWhen: () => true,
      when: () => commandReferenceCommandActive(),
      run: () => activateSelectedCommand(),
    },
    {
      id: "command.reference.close",
      touch: false,
      keys: ["Escape"],
      title: "close command reference",
      control: () => commandReferenceClose,
      runFromCommandReference: false,
      run: () => closeCommandReference(),
    },
  ],
});

// What a press must end before the reference opens over it, such as an armed Go-to
// sequence or react mode, which boot supplies (`mountCommandReference`).
let closeInteractions = () => {};
export function mountCommandReference({ beforeOpening }) {
  closeInteractions = beforeOpening;
}
const openReference = (returnTo = null) => {
  closeInteractions();
  openCommandReference((id) => executeCommand(id), returnTo);
};

// `?`, from wherever a key reaches.
pageCommand({
  id: "command.reference.open",
  touch: false,
  runFromCommandReference: false,
  keys: ["?"],
  title: "Command reference",
  run: () => openReference(),
});
// The row's press stands where the user pressed it, such as the floating panel's leaf,
// and is handed the location they had before stepping in. The reference opens from that
// place, so its commands act there, as `?` pressed there would; closing it unrun returns
// to the control that opened it.
registerPageControl({
  key: "keyboard",
  rank: PAGE_CONTROL_RANK.keyboard,
  label: "Keyboard shortcuts",
  shortcut: ["?"],
  group: "page",
  press: (held) => {
    const door = focused();
    if (held) returnPlace(held);
    openReference(door);
  },
});
