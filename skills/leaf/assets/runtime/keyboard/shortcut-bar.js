/* The shortcut bar at the foot of the page, the useful status opposite it or stacked
   above it when room is tight, and the More control that leads to the reference.

   The status keeps navigation state out of the command list. It appears after a
   semantic list walk and briefly takes the accent face when a repeated press cannot move
   from its destination. The bar gives compact hints rather than reproducing the
   command reference. It walks outward from the reader's innermost scope and drops
   bindings shadowed there. The
   ordinary shortlist is the first live row, then a promotable Escape or the next row.
   At rest on the page that
   is `c` for the page itself and `s` to select a more particular target, beside the More
   control. Once a target is selected, its Comment and React actions replace selection on
   the short line. Search and reading-page movement remain ordinary rows named by the shelf
   and the reference; scrolling is the one capability no page has to advertise. Ranking
   is a row's place in its scope, so moving the row is how the
   line's order changes. An active sequence instead shows every live row in its scope, so
   computed bindings, ranges, and capability filtering are the same ones dispatch and the
   reference use. Each destination row keeps its complete sequence: its leading steps that
   match accepted presses take the accent face, while a branch the reader has not taken
   keeps the ordinary face. Changing progress changes only those faces, not the sequence's
   keys or geometry. A mode's Escape or back row remains a
   separate control rather than appearing as a destination sequence. `lineWhen` may hide only
   an ordinary hint without changing the command's liveness or its place in the reference.
   Hint chips are `aria-hidden` because placeholders and live announcements carry the same
   facts for assistive technology.

   The compact line wraps when sequence rows need the room. Ordinary hints yield from the end
   on a window too narrow for them, but active sequence rows do not; More is the one control
   that always survives.

   `syncLayout` reserves the line's footprint only in a scroll region whose horizontal
   span meets it. Each reservation is the band from the line's top to that region's own
   foot: the window for the document and trays, and the thread list's rendered bottom at
   the top of the complete panel foot. The line's height, inset, any lift and the device's
   safe area are therefore one measurement off the rendered box rather than four numbers
   to keep in step. Over a covering thread panel, the line starts at its ordinary bottom
   inset and rises above the panel foot only when their rendered rectangles collide. A
   coarse pointer is drawn no hint line at all — there is no keyboard to advertise, and
   every hint would name a key the reader cannot press. A covering-width layout stacks
   the status above the line. The line, status, and chips take no pointer events; the More
   control does, because it is the pointer route to the reference. Brief reader feedback
   replaces an ordinal and then restores its live reading; background arrivals queue
   behind reader feedback and persistent command context.

   The accessible More control and its `?` binding share one progressive route. The first
   activation unfolds additional current-scene rows into a shelf capped at two lines; the
   second opens the complete reference. Escape returns through those layers, and another
   command folds the shelf before it runs. Expansion and contraction are announced because
   the revealed hint chips themselves remain visual. When there is no additional current
   row, the first activation opens the reference directly. The native control also opens
   it directly. */
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
  completeRowSteps,
  keySequence,
  neutralStates,
  progressStates,
  rowSteps,
} from "./presentation.js";
import { el } from "../widget-elements.js";
import { lineOwner, shadow, stack, executeCommand } from "./dispatch.js";

import { commandReferenceOpen, openCommandReference } from "./command-reference.js";
import { announce, noticeEl, setNoticeContext } from "../notifications.js";
import { repaint } from "../repaint.js";
import { walkPosition } from "../walk-position.js";

// The shortcut bar — the register's short rendering. Its fact chips are aria-hidden (the spoken
// copies are placeholders, announcements, and the reference); More is a real button because
// a visible door to the complete list should be a door every reader can work.
export const shortcutBarEl = el("div", "lf-ui lf-shortcut-bar");
shortcutBarEl.id = "lf-shortcut-bar";
export const bottomStatusEl = el("div", "lf-ui lf-bottom-status");
export const walkPositionEl = el("span", "lf-walk-position");
walkPositionEl.hidden = true;
walkPositionEl.setAttribute("aria-hidden", "true");
const goToStatusEl = el("span", "lf-go-to-status");
goToStatusEl.hidden = true;
goToStatusEl.setAttribute("aria-hidden", "true");
bottomStatusEl.append(goToStatusEl, walkPositionEl, noticeEl);
export const shortcutBarMore = el("button", "lf-shortcut-more");
shortcutBarMore.type = "button";
shortcutBarMore.title = "More keyboard shortcuts";
shortcutBarMore.setAttribute("aria-label", "? more");
export const shortcutBarMoreKey = document.createElement("kbd");
export const shortcutBarMoreText = el("span", "", "more");
shortcutBarMore.append(shortcutBarMoreKey, shortcutBarMoreText);

const boxesOf = (nodes) =>
  nodes
    .filter((node) => getComputedStyle(node).position === "fixed")
    .map((node) => node.getBoundingClientRect())
    .filter((box) => box.height > 0 && box.width > 0);

// Fixed boxes that Go-to hints and target-chooser hints must not cover. The bottom-only
// subset also bounds composers and reserves the document's foot. A transient notice
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
  if (!noticeEl.classList.contains("show"))
    [standingStatusBox = null] = boxesOf([bottomStatusEl]);
  return standingStatusBox ? [standingStatusBox] : [];
};
export const bottomChromeBoxes = () => [
  ...boxesOf([shortcutBarEl]),
  ...standingStatusBoxes(),
];
export const fixedChromeBoxes = bottomChromeBoxes;

// ---------- the shortcut bar ----------
// The rows the line shows, innermost scope first: the ones carrying a word for it. Each
// keeps only bindings no nearer scope has named, so an inner meaning wins while a grouped
// row's other presses remain visible — for example, an Ask's numbered pick replaces the
// page's ordinary digit meaning without hiding the option row's other keys.
const sourceRows = new WeakMap();
const sourceRow = (row) => sourceRows.get(row) ?? row;
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
    // dead row names nothing, so it shadows nothing either. Keep all unshadowed rows in
    // the batch so activeRows still rejects two live meanings inside this reachable scope.
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
let shortcutShelfIsOpen = false;
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
  const wayOut = candidates
    .slice(1)
    .find(
      (row) => bindings(row).includes("Escape") && word(row.promoteEscape) !== false,
    );
  const short = new Set(
    [first, wayOut ?? candidates.find((row) => row !== first)].filter(Boolean),
  );
  const tail = withoutReference.includes(CLOSE_SHORTCUT_SHELF)
    ? CLOSE_SHORTCUT_SHELF
    : null;
  return { candidates, reference, short, tail };
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
const openAllShortcuts = (captureReturnPlace) =>
  openCommandReference(
    (id, origin) => executeCommand(id, origin, beforeShortcutCommand),
    captureReturnPlace,
  );
function advanceShortcutHelp(captureReturnPlace) {
  if (!shortcutHelpAvailable() || shortcutShelfIsOpen)
    return openAllShortcuts(captureReturnPlace);
  const scopes = stack();
  const { candidates, short } = arrange(lineRows(scopes));
  const shown = completeLine(scopes, candidates)?.rows ?? short;
  if (!candidates.some((row) => !shown.has(row)))
    return openAllShortcuts(captureReturnPlace);
  shortcutShelfIsOpen = true;
  repaint();
  announce(
    "More keyboard shortcuts shown. Press question mark again for all shortcuts, or Escape to show less.",
  );
}
export function closeShortcutShelf({ silent = false } = {}) {
  if (!shortcutShelfIsOpen) return;
  shortcutShelfIsOpen = false;
  repaint();
  if (!silent) announce("Fewer keyboard shortcuts shown.");
}
export function renderShortcutBar(goToStatus) {
  // One walk, read twice: `at` and `when` are the page's own state and a second walk would
  // ask every one of them again for the same frame.
  const scopes = stack();
  const rows = lineRows(scopes);
  if (!shortcutHelpAvailable()) shortcutShelfIsOpen = false;
  const shelf = shortcutShelfIsOpen && !commandReferenceOpen();
  // `?` has its own permanent More control, so its ordinary row remains in the DOM only as
  // the register's hidden projection. In the shelf, the current Escape is drawn after that
  // control so both disclosure choices finish the second row.
  const { candidates, reference, short, tail } = arrange(rows);
  const complete = completeLine(scopes, candidates);
  const shown = complete?.rows ?? short;
  const position = walkPosition();
  const goToReading = goToStatus();
  setNoticeContext(Boolean(goToReading));
  goToStatusEl.textContent = goToReading ?? "";
  goToStatusEl.hidden = !goToReading;
  if (position) {
    walkPositionEl.dataset.kind = position.kind;
    walkPositionEl.textContent = position.text;
    walkPositionEl.hidden = false;
    walkPositionEl.toggleAttribute("data-lf-boundary", position.boundary);
  } else {
    walkPositionEl.hidden = true;
    walkPositionEl.removeAttribute("data-kind");
    walkPositionEl.removeAttribute("data-lf-boundary");
  }
  shortcutBarEl.dataset.lfShelfOpen = String(shelf);
  shortcutBarEl.dataset.lfMultiline = String(shelf || Boolean(complete));
  // Keep the two contextual hints together at the front of the ordinary line.
  // The shelf and a sequence retain registry order because each is a fuller reading of one
  // scene rather than a ranked shortlist.
  const projected =
    shelf || complete
      ? candidates
      : [...shown, ...candidates.filter((row) => !shown.has(row))];
  const projectedRows = projected.filter((row) => !shelf || row !== tail);
  const referenceRows = reference ? [reference] : [];
  // The interactive disclosure stays with the contextual shortlist. A wider system
  // font must not push More onto a lower row beside a page or panel control, where two
  // compact targets would no longer have the 24px separation either one owes.
  const ordered = [...projectedRows, ...referenceRows];
  // More is a permanent pointer and Tab route, but its key face is the same contextual
  // projection as every other key on the line. In a text box the typing scope claims `?`,
  // so the row is absent here and the button keeps only its non-keyboard route. Reading
  // the surviving row also keeps the face, accessible shortcut, label, and dispatch from
  // becoming four independent claims about the binding.
  const referenceBinding = reference ? bindings(reference)[0] : null;
  const referenceDoes = word(SHORTCUT_HELP.does);
  const referenceLine = word(SHORTCUT_HELP.line);
  shortcutBarMoreKey.hidden = !referenceBinding;
  if (referenceBinding) shortcutBarMoreKey.textContent = spell(referenceBinding);
  shortcutBarMoreText.textContent = referenceLine;
  shortcutBarMore.title = referenceDoes;
  shortcutBarMore.setAttribute("aria-expanded", String(shelf));
  shortcutBarMore.setAttribute(
    "aria-label",
    referenceBinding ? `${spell(referenceBinding)} ${referenceLine}` : referenceDoes,
  );
  if (referenceBinding)
    shortcutBarMore.setAttribute(
      "aria-keyshortcuts",
      ariaShortcuts([reference], false),
    );
  else shortcutBarMore.removeAttribute("aria-keyshortcuts");
  // Read where it is painted, like every other cell. Every destination keeps its complete
  // sequence while the reader advances through it: completed keys change face, but no key is
  // added, removed, or moved. A sequence control such as Escape is a way out of the mode, not
  // another destination, so it keeps its ordinary one-step face.
  const sequenceScope = complete?.scope;
  const sequence = word(sequenceScope?.sequence) ?? [];
  // Everything but More, which the reader may be standing on. `textContent = ""` takes
  // it out of the document, and removing a focused element blurs it: it returns on the
  // same line as the same node, connected again, with the reader dropped to `body`. That
  // lands one frame after they tabbed to it, because this runs under the repaint frame —
  // so the walk is whole at synthetic speed and broken at every human one, which is the
  // way round that hides from a suite. The line is cleared around the same seated node
  // instead, and the chips are drawn around it.
  for (const node of [...shortcutBarEl.childNodes])
    if (node !== shortcutBarMore) node.remove();
  const seated = shortcutBarMore.parentElement === shortcutBarEl;
  const chip = (steps, said, states, afterMore = false, row = null) => {
    const span = el("span", "lf-shortcut");
    span.setAttribute("aria-hidden", "true");
    if (row) {
      const active = bindings(row);
      const commands = commandPresentations(row, active).map(({ id }) => id);
      span.dataset.lfCommandIds = commands.join(" ");
      if (row.sequenceControl) span.classList.add("lf-sequence-command");
    }
    span.append(keySequence(steps, states));
    if (said) span.append(el("span", "", said));
    if (afterMore && seated) shortcutBarEl.append(span);
    else shortcutBarEl.insertBefore(span, seated ? shortcutBarMore : null);
    return span;
  };
  const drawn = ordered.map((row) => {
    const inSequence = sequence.length && !row.sequenceControl;
    const steps = inSequence ? [sequence[0], ...rowSteps(row)] : rowSteps(row);
    const states = inSequence ? progressStates(steps, sequence) : neutralStates(steps);
    const span = chip(steps, word(row.line), states, false, row);
    span.hidden = sourceRow(row) === SHORTCUT_HELP || (!shelf && !shown.has(row));
    return { row, span };
  });
  // The door is not useful behind the room it opens. While the reference stands, its
  // own Escape row is the short line and More leaves the focus order with the page. This
  // is the one removal that is meant: a reader standing on the door when the room opens
  // is a state change rather than a repaint, and the command reference takes focus anyway.
  if (commandReferenceOpen()) shortcutBarMore.remove();
  else if (!seated) shortcutBarEl.append(shortcutBarMore);

  if (shelf && tail) {
    const steps = rowSteps(tail);
    chip(steps, word(tail.line), neutralStates(steps), true);
  }

  const visible = () =>
    [...shortcutBarEl.children].filter(
      (node) => !node.hidden && node.checkVisibility(),
    );
  const rowsUsed = () => {
    const items = visible();
    const tolerance = Math.min(...items.map((node) => node.offsetHeight)) / 2;
    const tops = [];
    for (const node of items)
      if (tops.every((top) => Math.abs(top - node.offsetTop) > tolerance))
        tops.push(node.offsetTop);
    return tops.length;
  };

  // The shelf and ordinary line have two-row ceilings rather than permission to clip. The
  // shelf yields its lowest-ranked current commands until both disclosure controls fit;
  // hidden rows remain available to inspection and the reference. Active sequences return
  // below before any row can yield.
  if (shelf) {
    const removable = drawn
      .filter(({ span }) => !span.hidden)
      .map(({ span }) => span)
      .toReversed();
    while (rowsUsed() > 2 && removable.length) removable.shift().hidden = true;
    return;
  }
  // A sequence is the complete menu of the mode it names. Its live rows wrap rather than
  // disappearing, even where the ordinary shortlist would yield a lower-ranked hint.
  if (complete) return;
  // On a window narrower than those two
  // computed sentences, yield the lower-ranked hint and then the first; More is the one
  // control that always survives. At most two layouts are spent, independent of the size
  // of the register, while all hidden rows stay available to inspection and the reference.
  for (const span of drawn
    .filter(({ span }) => !span.hidden)
    .map(({ span }) => span)
    .toReversed()) {
    if (shortcutBarEl.scrollWidth <= shortcutBarEl.clientWidth) break;
    span.hidden = true;
  }
}

export const shortcutShelfOpen = () => shortcutShelfIsOpen && shortcutHelpAvailable();

// Boot supplies the two transient modes More closes. The shelf renderer and its
// reference rows never import those command owners to draw their current declarations.
export function mountShortcutBar({ setGoToSequence, setReact, captureReturnPlace }) {
  shortcutBarMore.onclick = () => {
    setGoToSequence(false);
    setReact(false);
    advanceShortcutHelp(captureReturnPlace);
  };
  // A narrower window changes which rows fit even without another reader input.
  addEventListener("resize", repaint);
  repaint();
}

export const SHORTCUT_HELP = {
  id: "command.reference.open",
  runFromCommandReference: false,
  keys: ["?"],
  does: () => (shortcutShelfOpen() ? "Command reference" : "More keyboard shortcuts"),
  line: () => (shortcutShelfOpen() ? "all shortcuts" : "more"),
  control: () => shortcutBarMore,
  run: () => shortcutBarMore.click(),
};

export const CLOSE_SHORTCUT_SHELF = {
  id: "shortcut.shelf.close",
  keys: ["Escape"],
  does: "Show fewer keyboard shortcuts",
  line: "less",
  commandReferenceWhen: () => false,
  runFromCommandReference: false,
  run: () => closeShortcutShelf(),
};

export const beforeShortcutCommand = (row) => {
  if (
    shortcutShelfOpen() &&
    !commandReferenceOpen() &&
    row !== SHORTCUT_HELP &&
    row !== CLOSE_SHORTCUT_SHELF
  )
    closeShortcutShelf({ silent: true });
};
