/* The key line at the foot of the page, and the More control that leads from it to the
   reference.

   The key line is short help, not the keyboard reference. It walks outward from the
   reader's innermost scope and drops bindings shadowed there. The ordinary shortlist is
   the first live row, then a promotable Escape or the next row. At rest on the page that
   is `c` for the page itself and `s` to select a more particular target, beside the More
   control. Once a target is selected, its Comment and React actions replace selection on
   the short line. Search and reading-page movement remain ordinary rows named by the shelf
   and the reference; scrolling is the one capability no page has to advertise. Ranking
   is a row's place in its scope, so moving the row is how the
   line's order changes. An active chord instead shows every live row in its scope, so
   computed bindings, ranges, and capability filtering are the same ones dispatch and the
   reference use. Each destination row keeps its complete chord: already pressed keys take
   the accent face and pending keys keep the ordinary face. Changing progress changes only
   those faces, not the sequence's keys or geometry. A mode's Escape or back row remains a
   separate control rather than appearing as a destination chord. `lineWhen` may hide only
   an ordinary hint without changing the command's liveness or its place in the reference.
   Hint chips are `aria-hidden` because placeholders and live announcements carry the same
   facts for assistive technology.

   The compact line wraps when chord rows need the room. Ordinary hints yield from the end
   on a window too narrow for them, but active chord rows do not; More is the one control
   that always survives.

   `syncLayout` reserves the line's footprint only in a scroll region whose horizontal
   span meets it. Each reservation is the band from the line's top to that region's own
   foot: the window for the document and trays, and the thread list's rendered bottom at
   the top of the complete panel foot. The line's height, inset, any lift and the device's
   safe area are therefore one measurement off the rendered box rather than four numbers
   to keep in step. Over a covering thread panel, the line starts at its ordinary bottom
   inset and rises above the panel foot only when their rendered rectangles collide; a
   thread list in another lane keeps its stylesheet inset and reserves nothing for the
   line. A coarse pointer is drawn no line at all — there is no keyboard to advertise, and
   every hint would name a key the reader cannot press — so the footprint is zero and
   nothing reserves room for it. The line and its chips take no pointer events; the More
   control does, because it is the only pointer route to the reference and so to the
   character-shortcut preference, which cannot be made to depend on the character key it
   turns off.

   The accessible More control and its `?` binding share one progressive route. The first
   activation unfolds additional current-scene rows into a shelf capped at two lines; the
   second opens the complete reference. Escape returns through those layers, and another
   command folds the shelf before it runs. Expansion and contraction are announced because
   the revealed hint chips themselves remain visual. When there is no additional current
   row, the first activation opens the reference directly. The native control also opens
   it directly when character shortcuts are off. */
import {
  activeRows,
  bindings,
  commandPresentations,
  commandRoutes,
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
import { shadow, stack } from "./dispatch.js";
import { LESS_SHORTCUTS, REFERENCE } from "./page.js";
import { referenceOpen, showReference } from "./reference.js";
import { announce } from "../notifications.js";
import { paintHere } from "./scopes.js";
import { setChord } from "./address.js";
import { setReact } from "../reactions.js";

// The key line — the register's short rendering. Its fact chips are aria-hidden (the spoken
// copies are placeholders, announcements, and the reference); More is a real button because
// a visible door to the complete list should be a door every reader can work.
export const keylineEl = el("div", "lf-ui lf-keyline");
export const keylineMore = el("button", "lf-key-more");
keylineMore.type = "button";
keylineMore.title = "More keyboard shortcuts";
keylineMore.setAttribute("aria-label", "? more");
export const keylineMoreKey = document.createElement("kbd");
keylineMoreKey.textContent = "?";
export const keylineMoreText = el("span", "", "more");
keylineMore.append(keylineMoreKey, keylineMoreText);

// ---------- the key line ----------
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
      if (!row.line || (!scope.chord && word(row.lineWhen) === false)) return [];
      const bound = bindings(row);
      const active = bound.filter((k) => !named.has(k) && !nearer.takes(k));
      return active.length ? [effectiveRow(row, bound, active)] : [];
    });
    for (const row of activeRows(reachable, scope.title ?? "the page's keys")) {
      const bound = bindings(row);
      for (const k of bound) named.add(k);
      rows.push(row);
    }
    nearer.past(scope);
  }
  return rows;
}
let expanded = false;
const shortcutAvailable = () => bindings(REFERENCE).length > 0;
const arrange = (rows) => {
  const referenceAt = rows.indexOf(REFERENCE);
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
  const tail = withoutReference.includes(LESS_SHORTCUTS) ? LESS_SHORTCUTS : null;
  return { candidates, referenceAt, short, tail };
};
const completeLine = (scopes, candidates) => {
  const scope = scopes.find((candidate) => candidate.chord);
  if (!scope) return null;
  const owned = new Set(scope.rows);
  const rows = new Set(candidates.filter((row) => owned.has(sourceRow(row))));
  // A nearer modal scope can shadow the chord wholesale while keeping it armed beneath.
  // In that state its own way out is the line, not an empty menu for the suspended chord.
  if (!rows.size) return null;
  return {
    scope,
    rows,
  };
};
function more() {
  if (!shortcutAvailable() || expanded) return showReference(true);
  const scopes = stack();
  const { candidates, short } = arrange(lineRows(scopes));
  const shown = completeLine(scopes, candidates)?.rows ?? short;
  if (!candidates.some((row) => !shown.has(row))) return showReference(true);
  expanded = true;
  paintHere();
  announce(
    "More keyboard shortcuts shown. Press question mark again for all shortcuts, or Escape to show less.",
  );
}
export function less({ silent = false } = {}) {
  if (!expanded) return;
  expanded = false;
  paintHere();
  if (!silent) announce("Fewer keyboard shortcuts shown.");
}
export function renderLine() {
  // One walk, read twice: `at` and `when` are the page's own state and a second walk would
  // ask every one of them again for the same frame.
  const scopes = stack();
  const rows = lineRows(scopes);
  if (!shortcutAvailable()) expanded = false;
  const shelf = expanded && !referenceOpen();
  // `?` has its own permanent More control, so its ordinary row remains in the DOM only as
  // the register's hidden projection. In the shelf, the current Escape is drawn after that
  // control so both disclosure choices finish the second row.
  const { candidates, referenceAt, short, tail } = arrange(rows);
  const complete = completeLine(scopes, candidates);
  const shown = complete?.rows ?? short;
  keylineEl.dataset.lfExpanded = String(shelf);
  keylineEl.dataset.lfWrap = String(shelf || Boolean(complete));
  // Keep the two contextual hints together at the front of the ordinary line.
  // The shelf and a chord retain registry order because each is a fuller reading of one
  // scene rather than a ranked shortlist.
  const projected =
    shelf || complete
      ? candidates
      : [...shown, ...candidates.filter((row) => !shown.has(row))];
  const projectedRows = projected.filter((row) => !shelf || row !== tail);
  const referenceRows = referenceAt === -1 ? [] : [REFERENCE];
  // The interactive disclosure stays with the contextual shortlist. A wider system
  // font must not push More onto a lower row beside a page or panel control, where two
  // compact targets would no longer have the 24px separation either one owes.
  const ordered = [...projectedRows, ...referenceRows];
  // Read where it is painted, like every other cell. Every destination keeps its complete
  // chord while the reader advances through it: completed keys change face, but no key is
  // added, removed, or moved. A chord control such as Escape is a way out of the mode, not
  // another destination, so it keeps its ordinary one-step face.
  const chordScope = complete?.scope;
  const chord = word(chordScope?.chord) ?? [];
  // Everything but More, which the reader may be standing on. `textContent = ""` takes
  // it out of the document, and removing a focused element blurs it: it returns on the
  // same line as the same node, connected again, with the reader dropped to `body`. That
  // lands one frame after they tabbed to it, because this runs under paintHere's frame —
  // so the walk is whole at synthetic speed and broken at every human one, which is the
  // way round that hides from a suite. The line is cleared around the same seated node
  // instead, and the chips are drawn around it.
  for (const node of [...keylineEl.childNodes]) if (node !== keylineMore) node.remove();
  const seated = keylineMore.parentElement === keylineEl;
  const chip = (steps, said, states, afterMore = false, row = null) => {
    const span = el("span", "lf-key");
    span.setAttribute("aria-hidden", "true");
    if (row) {
      const active = bindings(row);
      const commands = commandPresentations(row, active).map(({ id }) => id);
      span.dataset.lfCommands = commands.join(" ");
      if (row.chordControl) span.classList.add("lf-chord-control");
    }
    span.append(keySequence(steps, states));
    if (said) span.append(el("span", "", said));
    if (afterMore && seated) keylineEl.append(span);
    else keylineEl.insertBefore(span, seated ? keylineMore : null);
    return span;
  };
  const drawn = ordered.map((row) => {
    const inChord = chord.length && !row.chordControl;
    const steps = inChord ? [chord[0], ...completeRowSteps(row)] : rowSteps(row);
    const states = inChord ? progressStates(steps, chord.length) : neutralStates(steps);
    const span = chip(steps, word(row.line), states, false, row);
    span.hidden = row === REFERENCE || (!shelf && !shown.has(row));
    return { row, span };
  });
  // The door is not useful behind the room it opens. While the reference stands, its
  // own Escape row is the short line and More leaves the focus order with the page. This
  // is the one removal that is meant: a reader standing on the door when the room opens
  // is a state change rather than a repaint, and the help takes the focus anyway.
  if (referenceOpen()) keylineMore.remove();
  else if (!seated) keylineEl.append(keylineMore);

  if (shelf && tail) {
    const steps = rowSteps(tail);
    chip(steps, word(tail.line), neutralStates(steps), true);
  }

  const visible = () =>
    [...keylineEl.children].filter((node) => !node.hidden && node.checkVisibility());
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
  // hidden rows remain available to inspection and the reference. Active chords return
  // below before any row can yield.
  if (shelf) {
    const removable = drawn
      .filter(({ span }) => !span.hidden)
      .map(({ span }) => span)
      .toReversed();
    while (rowsUsed() > 2 && removable.length) removable.shift().hidden = true;
    return;
  }
  // A chord is the complete menu of the mode it names. Its live rows wrap rather than
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
    if (keylineEl.scrollWidth <= keylineEl.clientWidth) break;
    span.hidden = true;
  }
}
paintHere();
// The room is the window's, so the window changing is a scope change like any other. It
// was the one edge no writer reported: a reader who narrowed their window kept the wide
// selection until they next moved focus, and the CSS clip did the cutting instead.
addEventListener("resize", paintHere);

export const keylineExpanded = () => expanded && shortcutAvailable();

keylineMore.onclick = () => {
  setChord(false);
  setReact(false);
  more();
};
