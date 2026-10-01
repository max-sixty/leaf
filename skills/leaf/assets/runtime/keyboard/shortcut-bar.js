/* The shortcut bar at the foot of the page, the useful status at the bar's far end,
   and the More control that leads to the reference.

   The status keeps navigation state out of the command list. It appears after a semantic
   list walk and briefly takes the accent face when a repeated press cannot move from its
   destination. The bar gives compact hints rather than reproducing the command reference.
   It walks outward from the user's innermost scope and drops bindings shadowed there. The
   ordinary shortlist is the first live row, then a promotable Escape or the next row. At
   rest on the page that is `c` for the page itself and `s` to select a more particular
   target, beside the More control. Once a target is selected, its Comment and React
   actions replace selection on the short line. Search and reading-page movement remain
   ordinary rows named by the expanded bar and the reference; scrolling is the one
   capability no page has to advertise. Ranking is a row's place in its scope, so moving
   the row is how the line's order changes. An active sequence instead offers every live
   row in its scope, so computed bindings, ranges, and capability filtering are the same
   ones dispatch and the reference use. Each destination row keeps its complete sequence:
   its leading steps that match accepted presses take the accent face, while a branch the
   user has not taken keeps the ordinary face. Changing progress changes only those faces,
   not the sequence's keys or geometry. A mode's Escape or back row remains a separate
   control rather than appearing as a destination sequence. `lineWhen` may hide only an
   ordinary hint without changing the command's liveness or its place in the reference.
   Hint chips are `aria-hidden` because placeholders and live announcements carry the same
   facts for assistive technology.

   The line is one row. Rows that do not fit leave it, the lowest-ranked first, so a
   narrow window keeps the leading hint and a sequence too long for the window keeps its
   leading destinations. More and the current way out never leave, and the reference
   behind More lists every row the line had no room for. The expanded bar, which the user
   unfolds to read the rest of the register, holds two rows under the same trim.

   The line is the bottom bar: one row at the stated `--lf-bottom-bar-h` (theme.css),
   which the document, a full-height workspace, the drawers' lists and the contents map
   all end above, so no reservation is measured off it. The expanded bar's second row
   grows upward over the page as an overlay and leaves that reservation alone. A covering
   thread panel makes the line inert background. A coarse pointer is drawn no hint line
   at all — there is no keyboard to advertise, and every hint would name a key the user
   cannot press — and states no bar height. The status stands at the bar's far end, and
   the line's row ends short of a standing one. The line, status, and chips take no
   pointer events; the More control does, because it is the pointer route to the
   reference. Brief user feedback replaces an ordinal and then restores its live reading;
   background arrivals queue behind user feedback and persistent command context.

   The accessible More control and its `?` binding share one progressive route. The first
   activation unfolds additional current-scene rows into an expanded bar capped at two
   lines; the second opens the complete reference. Escape returns through those layers,
   and another command folds the expanded bar before it runs. Expansion and contraction
   are announced because the revealed hint chips themselves remain visual. When there is
   no additional current row, the first activation opens the reference directly. The
   native control also opens it directly. */
import { html, nothing, render, repeat } from "../../vendor/browser-runtime.js";

import {
  activeRows,
  ariaShortcuts,
  bindings,
  commandPresentations,
  commandRoutes,
  spell,
  word,
} from "./bindings.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  neutralStates,
  progressStates,
  rowSteps,
} from "./presentation.js";
import { el } from "../widget-elements.js";
import { keeps, keepsHidden } from "../keeps.js";
import { lineOwner, shadow, stack, executeCommand } from "./dispatch.js";

import {
  commandReferenceDialog,
  commandReferenceOpen,
  declareExpandedBarBehindReference,
  openCommandReference,
} from "./command-reference.js";
import { pageCommand, pageScope } from "./register.js";
import {
  announce,
  noticeReading,
  noticeVisible,
  registerNoticePresentation,
  setNoticeContext,
} from "../notifications.js";
import { repaint } from "../repaint.js";
import { walkPosition } from "../walk-position.js";
import { declareBottomBar } from "../geometry.js";
import { pagePresented } from "../presentation.js";

// The shortcut bar — the register's short rendering. Its fact chips are aria-hidden (the spoken
// copies are placeholders, announcements, and the reference); More is a real button because
// a visible door to the complete list should be a door every user can work.
export const shortcutBarEl = el("div", "lf-ui lf-shortcut-bar");
shortcutBarEl.id = "lf-shortcut-bar";
export const bottomStatusEl = el("div", "lf-ui lf-bottom-status");
let activateShortcutMore = null;

const EMPTY_STATUS_CONTEXT = Object.freeze({ goTo: null, walk: null });
const EMPTY_BAR = Object.freeze({
  items: Object.freeze([]),
  more: Object.freeze({
    hidden: true,
    binding: null,
    line: "more",
    title: "More keyboard shortcuts",
    expanded: false,
    ariaLabel: "More keyboard shortcuts",
    ariaShortcuts: null,
  }),
  tail: null,
  expanded: false,
});

const bottomStatusTemplate = (model) => html`
  <span class="lf-go-to-status" aria-hidden="true" ?hidden=${!model.goTo}
    >${model.goTo ?? nothing}</span
  >
  <span
    class="lf-walk-position"
    aria-hidden="true"
    ?hidden=${!model.walk?.shown}
    data-kind=${model.walk?.shown ? model.walk.kind : nothing}
    ?data-lf-boundary=${model.walk?.shown ? model.walk.boundary : false}
    >${model.walk?.text ?? nothing}</span
  >
  <span class=${`lf-ui lf-notice${model.notice.visible ? " show" : ""}`}
    >${model.notice.message || nothing}</span
  >
`;

const shortcutBarTemplate = (model) =>
  html`${repeat(
      model.items,
      (item) => item.key,
      (item) => html`
        <span
          class=${`lf-shortcut${item.sequenceControl ? " lf-sequence-command" : ""}`}
          aria-hidden="true"
          data-lf-command-ids=${item.commandIds}
          >${keySequenceTemplate(item.sequence)}${
            item.said ? html`<span>${item.said}</span>` : nothing
          }</span
        >
      `,
    )}<button
      type="button"
      class="lf-shortcut-more"
      title=${model.more.title}
      aria-label=${model.more.ariaLabel}
      aria-expanded=${String(model.more.expanded)}
      aria-keyshortcuts=${model.more.ariaShortcuts ?? nothing}
      ?hidden=${model.more.hidden}
      @click=${() => activateShortcutMore?.()}
    >
      <kbd class="lf-key-badge">${model.more.binding}</kbd
      ><span>${model.more.line}</span></button
    >${
      model.tail
        ? html`<span class="lf-shortcut" aria-hidden="true"
            >${keySequenceTemplate(model.tail.sequence)}<span
              >${model.tail.said}</span
            ></span
          >`
        : nothing
    }`;

let bottomStatusContext = EMPTY_STATUS_CONTEXT;
const renderBottomStatus = () => {
  const model = Object.freeze({
    ...bottomStatusContext,
    notice: noticeReading(),
  });
  render(bottomStatusTemplate(model), bottomStatusEl);
};
renderBottomStatus();
render(shortcutBarTemplate(EMPTY_BAR), shortcutBarEl);
const walkPositionEl = bottomStatusEl.querySelector(".lf-walk-position");
const goToStatusEl = bottomStatusEl.querySelector(".lf-go-to-status");
const shortcutBarMore = shortcutBarEl.querySelector(".lf-shortcut-more");
registerNoticePresentation(renderBottomStatus);

const boxesOf = (nodes) =>
  nodes
    .filter((node) => getComputedStyle(node).position === "fixed")
    .map((node) => node.getBoundingClientRect())
    .filter((box) => box.height > 0 && box.width > 0);

// Fixed boxes that Go-to hints and target-picker hints must not cover. The bottom-only
// subset also bounds composers and floating cards. A transient notice
// alone does not change page geometry; over a standing walk or command context it keeps
// that surface's last stable footprint rather than making a four-second message reflow
// the page and its hints.
const standingStatus = () => !walkPositionEl.hidden || !goToStatusEl.hidden;
let standingStatusBox = null;
export const standingStatusBoxes = () => {
  if (!standingStatus()) {
    standingStatusBox = null;
    return [];
  }
  if (!noticeVisible()) [standingStatusBox = null] = boxesOf([bottomStatusEl]);
  return standingStatusBox ? [standingStatusBox] : [];
};
export const bottomChromeBoxes = () => [
  ...boxesOf([shortcutBarEl]),
  ...standingStatusBoxes(),
];
declareBottomBar(bottomChromeBoxes);

// ---------- the shortcut bar ----------
// The rows the line shows, innermost scope first: the ones carrying a word for it. Each
// keeps only bindings no nearer scope has named, so an inner meaning wins while a grouped
// row's other presses remain visible — for example, an Ask's numbered pick replaces the
// page's ordinary digit meaning without hiding the option row's other keys.
const sourceRows = new WeakMap();
const sourceRow = (row) => sourceRows.get(row) ?? row;
const rowPresentationKeys = new WeakMap();
let nextRowPresentationKey = 1;
const rowPresentationKey = (row) => {
  const source = sourceRow(row);
  if (!rowPresentationKeys.has(source))
    rowPresentationKeys.set(source, nextRowPresentationKey++);
  return rowPresentationKeys.get(source);
};
const effectiveRow = (row, declared, active) => {
  if (active.length === declared.length) return row;
  const routes = commandRoutes(row).filter((route) => active.includes(route.binding));
  const route = routes.length === 1 ? routes[0] : null;
  const projected = {
    ...row,
    keys: active,
    routes,
    // A custom group label cannot describe a binding removed by a nearer scope. A route
    // may supply the short word for its remaining direction; otherwise the row's shared
    // word still describes the reduced binding set.
    label: route?.label,
    does: route?.does ?? row.does,
    line: route?.line ?? row.line,
  };
  sourceRows.set(projected, row);
  return projected;
};
function lineRows(scopes) {
  const escape = lineOwner("Escape");
  const named = new Set();
  const nearer = shadow();
  const rows = [];
  for (const scope of scopes) {
    // Shadowing before liveness, for the reason the dispatcher matches the key first:
    // under the reference every page row is claimed away, and asking each one what the
    // page is waiting on to then say nothing about it is the table's cost per paint. A
    // dead row names nothing within its own scope, where mutually exclusive rows may reuse
    // a binding. `nearer.past(scope)` then records every element-scope declaration before
    // outer scopes are read. Keep all unshadowed rows in the batch so activeRows still
    // rejects two live meanings inside this reachable scope.
    const reachable = scope.rows.flatMap((row) => {
      if (!row.line || (!scope.sequence && word(row.lineWhen) === false)) return [];
      const bound = bindings(row);
      const active = bound.filter((binding) =>
        binding === "Escape"
          ? escape?.visible && escape.scope === scope && escape.row === row
          : !named.has(binding) && !nearer.takes(binding),
      );
      return active.length ? [effectiveRow(row, bound, active)] : [];
    });
    for (const row of activeRows(reachable, scope.title ?? "the page's keys")) {
      for (const binding of bindings(row)) named.add(binding);
      rows.push(row);
    }
    nearer.past(scope);
  }
  return rows;
}
let shortcutBarIsExpanded = false;
let lastWalkPresentation = null;
const shortcutHelpAvailable = () => bindings(SHORTCUT_HELP).length > 0;
const arrange = (rows) => {
  const referenceAt = rows.findIndex((row) => sourceRow(row) === SHORTCUT_HELP);
  const reference = referenceAt === -1 ? null : rows[referenceAt];
  const withoutReference =
    referenceAt === -1
      ? rows
      : [...rows.slice(0, referenceAt), ...rows.slice(referenceAt + 1)];
  const candidates = withoutReference;
  const first = candidates[0];
  const wayOut = candidates.find(
    (row) => bindings(row).includes("Escape") && word(row.promoteEscape) !== false,
  );
  const second =
    wayOut && wayOut !== first ? wayOut : candidates.find((row) => row !== first);
  const short = new Set([first, second].filter(Boolean));
  const tail = withoutReference.includes(COLLAPSE_SHORTCUT_BAR)
    ? COLLAPSE_SHORTCUT_BAR
    : null;
  return { candidates, reference, short, tail, wayOut };
};
const completeLine = (scopes, candidates) => {
  const scope = scopes.find((candidate) => candidate.sequence);
  if (!scope) return null;
  const owned = new Set(scope.rows);
  const rows = new Set(candidates.filter((row) => owned.has(sourceRow(row))));
  // A nearer modal scope can shadow the sequence wholesale while keeping it armed beneath.
  // In that state its own way out is the line, not an empty menu for the suspended sequence.
  if (!rows.size) return null;
  return {
    scope,
    rows,
  };
};
const openCompleteReference = () =>
  openCommandReference((id) => executeCommand(id, beforeShortcutCommand));
function advanceShortcutHelp() {
  if (!shortcutHelpAvailable() || shortcutBarIsExpanded) return openCompleteReference();
  const scopes = stack();
  const { candidates, short } = arrange(lineRows(scopes));
  const shown = completeLine(scopes, candidates)?.rows ?? short;
  if (!candidates.some((row) => !shown.has(row))) return openCompleteReference();
  shortcutBarIsExpanded = true;
  repaint();
  announce(
    "Shortcut bar expanded. Press question mark again for Command reference, or Escape to collapse it.",
  );
}
export function collapseShortcutBar({ silent = false } = {}) {
  if (!shortcutBarIsExpanded) return;
  shortcutBarIsExpanded = false;
  repaint();
  if (!silent) announce("Shortcut bar collapsed.");
}
export function renderShortcutBar(goToStatus) {
  // The line says what the page's keys do, and until the page presents none of them does
  // anything: the bootstrap holds every press for the presented page (controller.js). A
  // line drawn from the commands live before then named a different pair, and More moved
  // when presentation replaced it, so the band stands empty until its first true reading.
  if (!pagePresented()) return;
  // One walk, read twice: `at` and `when` are the page's own state and a second walk would
  // ask every one of them again for the same frame.
  const scopes = stack();
  const rows = lineRows(scopes);
  if (!shortcutHelpAvailable()) shortcutBarIsExpanded = false;
  const expanded = shortcutBarIsExpanded && !commandReferenceOpen();
  // `?` has its own permanent More control, so its ordinary row remains in the DOM only
  // as the register's hidden projection. In the expanded bar, the current Escape is drawn
  // after that control so both disclosure choices finish the second row.
  const { candidates, reference, short, tail, wayOut } = arrange(rows);
  const complete = completeLine(scopes, candidates);
  const shown = complete?.rows ?? short;
  const position = walkPosition();
  const goToReading = goToStatus();
  if (position)
    lastWalkPresentation = Object.freeze({
      kind: position.kind,
      text: position.text,
      boundary: position.boundary,
    });
  bottomStatusContext = Object.freeze({
    goTo: goToReading,
    // A retired walk hides but keeps its last wording, matching the native status
    // surface's continuity while transient notice text occupies the same seat.
    walk: lastWalkPresentation
      ? Object.freeze({ ...lastWalkPresentation, shown: Boolean(position) })
      : null,
  });
  setNoticeContext(Boolean(goToReading));
  renderBottomStatus();
  // Keep the two contextual hints together at the front of the ordinary line. The
  // expanded bar and a sequence retain registry order because each is a fuller reading of
  // one scene rather than a ranked shortlist.
  const projected =
    expanded || complete
      ? candidates
      : [...shown, ...candidates.filter((row) => !shown.has(row))];
  const projectedRows = projected.filter((row) => !expanded || row !== tail);
  const referenceRows = reference ? [reference] : [];
  // The interactive disclosure stays with the contextual shortlist. A wider system
  // font must not push More onto a lower row beside a page or panel control, where two
  // compact targets would no longer have the 24px separation either one owes.
  const ordered = [...projectedRows, ...referenceRows];
  // More's key face is the same contextual projection as every other key on the line, and
  // the line shows only what works from where the user is. In a text box the typing scope
  // claims `?`, so the row is absent and More stands down with it: a bare "more" read as
  // a hint that had lost its key. Reading the surviving row also keeps the face,
  // accessible shortcut, label, and dispatch from becoming four independent claims about
  // the binding.
  const referenceBinding = reference ? bindings(reference)[0] : null;
  const referenceDoes = word(SHORTCUT_HELP.does);
  const referenceLine = word(SHORTCUT_HELP.line);
  // Read where it is painted, like every other cell. Every destination keeps its complete
  // sequence while the user advances through it: completed keys change face, but no key is
  // added, removed, or moved. A sequence control such as Escape is a way out of the interaction, not
  // another destination, so it keeps its ordinary one-step face.
  const sequenceScope = complete?.scope;
  const sequence = word(sequenceScope?.sequence) ?? [];
  const presentations = ordered.map((row) => {
    const inSequence = sequence.length && !row.sequenceControl;
    const steps = inSequence ? [sequence[0], ...rowSteps(row)] : rowSteps(row);
    const states = inSequence ? progressStates(steps, sequence) : neutralStates(steps);
    const active = bindings(row);
    return Object.freeze({
      key: rowPresentationKey(row),
      sequenceControl: Boolean(row.sequenceControl),
      sequence: keySequenceModel(steps, states),
      said: word(row.line),
      commandIds: commandPresentations(row, active)
        .map(({ id }) => id)
        .join(" "),
      wayOut: row === wayOut,
      hidden: sourceRow(row) === SHORTCUT_HELP || (!expanded && !shown.has(row)),
    });
  });
  // The door is not useful behind the room it opens, nor where its key does not work.
  // While the reference stands, its own Escape row is the short line; in either case More
  // remains retained but leaves layout and the focus order. The reference takes focus
  // before this state is painted.
  const model = Object.freeze({
    items: Object.freeze(presentations),
    more: Object.freeze({
      hidden: commandReferenceOpen() || !referenceBinding,
      binding: referenceBinding ? spell(referenceBinding) : null,
      line: referenceLine,
      title: referenceDoes,
      expanded,
      ariaLabel: referenceBinding
        ? `${spell(referenceBinding)} ${referenceLine}`
        : referenceDoes,
      ariaShortcuts: referenceBinding ? ariaShortcuts([reference], false) : null,
    }),
    tail:
      expanded && tail
        ? Object.freeze({
            sequence: keySequenceModel(rowSteps(tail), neutralStates(rowSteps(tail))),
            said: word(tail.line),
          })
        : null,
    expanded,
  });
  keeps(shortcutBarEl, "data-lf-expanded", model.expanded);
  render(shortcutBarTemplate(model), shortcutBarEl);
  const rowSpans = shortcutBarEl.querySelectorAll(":scope > .lf-shortcut");
  const drawn = model.items.map((presentation, index) => ({
    presentation,
    span: rowSpans[index],
  }));
  // The status stands at the bar's far end, level with the one row, so a standing status
  // pads the row's end and More and the way out stop short of it. A transient notice
  // keeps the footprint of what it stands over (standingStatusBoxes) rather than trimming
  // the line for the seconds it shows. The expanded bar's upper row is not level with the
  // status, so it reserves nothing.
  const barStyle = getComputedStyle(shortcutBarEl);
  const gap = parseFloat(barStyle.columnGap);
  const [status] = expanded ? [] : standingStatusBoxes();
  const reserved = status ? status.width + gap : 0;
  // Which rows fit is worked out from widths the line already has, not by showing a row
  // to see whether it wraps: a row the line leaves keeps its width out of flow
  // (chrome.css), so every row is measured where it stands and each `hidden` and the
  // status room are written once, to the value they end at. The line breaks as flex-wrap
  // breaks it: a box joins the row while it and the gap before it still fit.
  const outer = (node) => {
    const style = getComputedStyle(node);
    return (
      node.getBoundingClientRect().width +
      parseFloat(style.marginLeft) +
      parseFloat(style.marginRight)
    );
  };
  const line =
    shortcutBarEl.getBoundingClientRect().width -
    parseFloat(barStyle.borderLeftWidth) -
    parseFloat(barStyle.borderRightWidth) -
    parseFloat(barStyle.paddingLeft) -
    parseFloat(barStyle.paddingRight) +
    (parseFloat(shortcutBarEl.style.getPropertyValue("--lf-status-room")) || 0);
  const eligible = new Map(
    drawn.map(({ span, presentation }) => [span, !presentation.hidden]),
  );
  const widths = new Map(
    [...shortcutBarEl.children]
      .filter((node) => eligible.get(node) ?? !node.hidden)
      .map((node) => [node, outer(node)]),
  );
  const trimmed = new Set();
  const rowsUsed = (room) => {
    let rows = 0;
    let used = Infinity;
    for (const [node, width] of widths) {
      if (trimmed.has(node)) continue;
      used += gap + width;
      if (used > line - room) {
        rows += 1;
        used = width;
      }
    }
    return rows;
  };
  // A row ceiling rather than permission to clip: one row, or two in the expanded bar.
  // The line yields its lowest-ranked current commands until More fits; hidden rows remain
  // available to inspection and the reference. The way out is the one row the trim may
  // not spend. A line covering the page at a narrow width is exactly where the user needs
  // it: the way out sits last in the register's order, so a trim that only counted from
  // the end would drop it first of all.
  const ceiling = expanded ? 2 : 1;
  const removable = drawn
    .filter(({ presentation }) => !presentation.hidden && !presentation.wayOut)
    .map(({ span }) => span)
    .toReversed();
  while (rowsUsed(reserved) > ceiling && removable.length)
    trimmed.add(removable.shift());
  // A wide row that had to go can free room a narrower one trimmed before it would fit
  // in, so each trimmed row is offered its place back, highest-ranked first.
  for (const span of [...trimmed].toReversed()) {
    trimmed.delete(span);
    if (rowsUsed(reserved) > ceiling) trimmed.add(span);
  }
  // A status too wide to leave More and the way out their row gives the room back and
  // stands over them, since it takes no pointer events and the row is the promise.
  const room = reserved && rowsUsed(reserved) > ceiling ? 0 : reserved;
  shortcutBarEl.style.setProperty("--lf-status-room", `${room}px`);
  for (const { presentation, span } of drawn)
    keepsHidden(span, presentation.hidden || trimmed.has(span));
}

const shortcutBarExpanded = () => shortcutBarIsExpanded && shortcutHelpAvailable();

// Boot supplies the two transient interactions More closes. The bar renderer and its
// reference rows never import those command owners to draw their current declarations.
export function mountShortcutBar({ setGoToSequence, setReact }) {
  activateShortcutMore = () => {
    setGoToSequence(false);
    setReact(false);
    advanceShortcutHelp();
  };
  // Which rows fit follows the line's width, which the window and a panel beside the page
  // both set; chrome layout's observer of the line repaints on any change to its box.
  repaint();
}

const SHORTCUT_HELP = pageCommand({
  id: "command.reference.open",
  touch: false,
  runFromCommandReference: false,
  keys: ["?"],
  does: () => (shortcutBarExpanded() ? "Command reference" : "More keyboard shortcuts"),
  line: () => (shortcutBarExpanded() ? "command reference" : "more"),
  control: () => shortcutBarMore,
  run: () => shortcutBarMore.click(),
});

const COLLAPSE_SHORTCUT_BAR = {
  id: "shortcut.bar.collapse",
  keys: ["Escape"],
  does: "Show fewer keyboard shortcuts",
  line: "less",
  commandReferenceWhen: () => false,
  runFromCommandReference: false,
  run: () => collapseShortcutBar(),
};

// The expanded bar stands inside the reference's own dialog box, and the reference claims
// the keyboard whole while it is open, so this scope answers only in the state between
// the two presses: the bar expanded, the reference not yet opened.
pageScope("expanded shortcut bar", {
  title: "In the expanded shortcut bar",
  escape: "inner",
  root: () => commandReferenceDialog,
  at: () => Boolean(shortcutBarExpanded()),
  rows: [COLLAPSE_SHORTCUT_BAR],
});
declareExpandedBarBehindReference(shortcutBarExpanded);

export const beforeShortcutCommand = (row) => {
  if (
    shortcutBarExpanded() &&
    !commandReferenceOpen() &&
    row !== SHORTCUT_HELP &&
    row !== COLLAPSE_SHORTCUT_BAR
  )
    collapseShortcutBar({ silent: true });
};
