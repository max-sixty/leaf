/* Pointing reads; pressing acts (browser/AGENTS.md, "Pointing reads; pressing acts"):
   the one owner of what a mark, control or value says before a press acts on it.

   Anything may preview, and the innermost under the pointer, the focus or the finger
   does:

   - A control previews its name and its keys without declaring either: its accessible
     name where its face shows a symbol or a mark or doesn't say that name, and each
     press that reaches it (control-keys.js, `controlKeys`) as key chips beside its
     name, which a coarse pointer leaves out with every other advertised key. A control
     whose face says its name and that no key reaches previews nothing. A field the user
     types in previews nothing: its words are what they read.
   - An element declares what pointing at it adds as its `lfPreview(route)`, called once
     as its preview shows on that route (`"pointer"`, `"focus"` or `"hold"`), and again
     for each new presentation of the document while the preview stands, so the words
     follow the page, a thread's turn or a link's place, redrawn in place with no fade
     and left as they are where they come back the same: `{name, keys, detail, at,
     excerpt}`, every field optional (module-input.md, "Previews"). On a control its
     lines stand under the control's own name and keys, and its name replaces the
     accessible name where that says more than the face should; `at` is where to stand,
     the declaring element by default, another element or a box in client coordinates
     inside it, as a chart's point, which the preview stands above; and `excerpt` asks
     for the face's room for a block of the page. When what it says changes under an aim
     that stays inside the element, as a chart's point, it says so (`previewChanged`,
     widget-upgrade.js), and a standing preview redraws in place or the route reading
     the element shows it. It returns null where it adds nothing, so the search goes on
     outward, and false where nothing shows and nothing around it may. A widget declares
     it with no import, as it declares `lfCommands` and `lfCopy()`, so off Leaf it reads
     nothing. What a declaration throws is reported and shows nothing.
   - A `title` is an element's declared words: a line under its name, or its name where
     it has none, so a portable widget that writes one reads off Leaf in the browser's
     tooltip and on Leaf on every route, in this face alone. The first time the pointer
     reaches the element, this takes the attribute off and keeps its words, so the
     browser's tooltip never stands beside the preview; a title the writer writes again
     is taken again with its new words. A writer's removal of one already taken removes
     nothing, so its words stay until it writes another. Authored markup's titles read
     the same way: they gain the keyboard and a finger.
   - A range with no element of its own, as a passage mark is, is its owner's to hit
     test, so the owner says where the pointer rests (`pointRange`), as often as it
     likes, a finger's press among its moves, and this module does the rest, placing the
     preview by the line the pointer is on.

   Nothing standing open (`aria-expanded="true"`) previews, since what pressing it opens
   is already in front of the user, and the search goes on outward from it, as it does
   from a proxy, whose thing previews for it. A preview is read once, as it shows, so its
   words keep still while the user reads them, as a status that ages beneath them would
   not.

   Every preview wears one face (`.lf-preview`, controls.css): its name on the first
   line with its key chips, then its lines of detail, in one type and colour. Only the
   words Leaf itself says keep their italic (voice.js), as they do on every seat. A
   preview that quotes a block of the page, as a link's place does, takes the face's
   excerpt room (`data-lf-face="excerpt"`): the same type, colours and spacing, wider.

   One preview stands at a time, in one element: a hint popover (`popover="hint"`), in
   the top layer, so it stands over a modal or an open popover around its target, and a
   hint closes no popover the user opened. It holds no control, so it is no layer the
   keyboard tiers its scopes over (layer-stack.js). A pointer's preview takes the
   pointer, so the pointer can cross from the target onto it and read it there; leaving
   it puts it away after a dwell, and reaching another target from it shows that one at
   once (WCAG 1.4.13, "Hoverable").

   Where it stands is one rule (`stand`), measured as it shows: by the gap that clears a
   focus ring, below the box it previews, or above where the window has no room below,
   above first for a finger, which covers what lies below, and for a point inside its
   target; beside a column of targets, as margin entries and a list's rows stand
   (`stacked`), so it covers none of them and the pointer reaches each, toward the
   nearer window edge, so a margin entry's covers no passage. Along the line
   it starts at the box's start edge and stays inside the nearest box around the target
   wide enough to hold it, so a link early in a line keeps it in the reading column and
   a control at a card's end edge keeps it in the card. It is written as insets from the
   box that carries the target, the nearest that scrolls, stands fixed or sticky, or
   stands in the top layer, else the page's root, by the name css-anchors.js gives that
   box, so the browser carries it through every scroll that moves the target, a hover
   names no target, which observers of the page's boxes would hear, and nothing around
   the target moves.

   Its routes:

   - A pointer resting on a target for `DWELL` shows its preview; moving onto another
     target within `WARM` of the last one shows the next at once, so reading along a row
     of controls waits once. Leaving the target hides it, and so do a press and any key
     but Escape, as the platform's tooltip goes, while the key does its own work; the
     target then stays quiet until the pointer comes back to it. A target that arrives
     under a pointer the user hasn't moved shows nothing, so news landing under a
     resting pointer never covers what the user reads, and nor does one a pointer
     reaches while it carries a press, as in a drag. A tab the user leaves takes its
     preview away.
   - Keyboard focus the browser shows (`:focus-visible`) shows its target's preview at
     once, with no fade, and leaving the target hides it. Focus the runtime hands back,
     as a closing surface returns the user to what opened it, shows nothing: the user
     is backing out, and a preview there would take their next Escape. A declaration that stops
     being true, as a grip's once its card is grabbed, says so (`previewChanged`).
   - A screen reader hears every preview shown on focus, whatever supplied it, as the
     focused element's description (`ariaDescribedByElements`) while it stands, except a
     control's own, which says what its accessible name and `aria-keyshortcuts` already
     do, and a proxy's, which describes what it stands for with its own markup, as a
     gloss's does.
   - A finger held on a target for `DWELL` shows its preview, and the finger reads its
     neighbours by sliding onto them: one of the same parent shows its own instead.
     Releasing after the preview showed presses the target it ends on, or none when it
     ends off them, so a finger that reads the wrong word slides off before letting go;
     a tap releases before then and the browser's own click presses. The release presses
     by dispatching the target's click, counted as a pointer's, and claims the browser's
     own click after it (`claimReleaseClick`, focus.js), since a finger held long enough
     to read may get none and the press may put something else under the finger, such
     as the thread a margin entry opens. It first focuses the target without a ring, as
     a pointer's press does, so what the press opens is laid out with the user on it. A
     press or release with a modifier is not this gesture (`plainPress`). Touch capture
     is released at the press so the slide is heard over each neighbour, and a finger
     that starts scrolling ends the hold with `pointercancel`, which presses nothing; a
     target that should not scroll from a press says so with `touch-action`. While a
     preview is held, the platform's long-press menu stays shut. A finger pressing where
     no element previews holds whatever range its owner says it rests on, and slides
     only as the owner says; its preview stands above the line, and its release presses
     the element holding the range, as a tap there would, which the owner answers as it
     answers a tap. A finger that only moves, as a pointer would, reads no range, and the
     author's element holding the range wears no `data-lf-held`.
   - While a preview stands, by pointer or by focus, it is Escape's first step and the
     press does nothing else (keyboard/AGENTS.md, "Escape"): it covers what lies under
     it, so the user can put it away without moving the pointer or focus, and without
     losing the surface they are in (WCAG 1.4.13, "Content on Hover or Focus"). A second
     Escape takes the step the first would have. Off a served page, where the register
     holds no page scopes, the key listener takes the same step.

   Each pointer boundary costs the path it walks, the nodes under the pointer, and a
   preview showing costs what it reads, for a control the page's commands, never the
   page's elements (root AGENTS.md, "Responsiveness"). The target a finger holds wears `data-lf-held` while the preview
   stands, so its surface can keep it where the finger is (margin-layout.js, `HELD`).

   Decisions: one dwell for the pointer and the finger, 200 ms, hides a flicker as either
   crosses targets without holding the user up; the margin's labels waited 90 ms, the
   platform's tooltips about a second. A preview says its words whole, wrapping where
   they run long, where a margin entry's label cut its question to one line. It finds a
   column of targets by one hit test each side of its own, where the margin's labels
   each measured every entry on the page to stand clear of them, a page-wide read on
   every hover. Until 5 November 2026 a preview took no pointer, so a covered neighbour
   took the pointer through it but the pointer couldn't stay on the preview to read it,
   and Escape put a preview away and took its own step too, which closed the thread
   card the user was reading, since the preview covers its first line. Rejected:
   `interestfor`, which gives a control the same three routes natively but ships only in
   Chromium; the platform's `title` alone, which no finger or keyboard reads and which
   can't draw a key chip; holding a `title` off only while the pointer rests within its
   element and putting it back as the pointer leaves, which writes it twice a hover, each
   a change of the element's description a screen reader hears; a popover's implicit
   anchor (`showPopover({source})`), which Firefox 157 keeps on the first source it was
   shown with; and a preview that follows its target by a script, which trails each
   scroll by a frame. */
import { html, nothing, render } from "/runtime/framework.js";
import { anchorAt, anchorElement } from "./css-anchors.js";
import { placeHolder } from "./geometry.js";
import { closeNativeLayer, showNativeLayer } from "./keyboard/layer-stack.js";
import { controlKeys } from "./keyboard/control-keys.js";
import { advertisesKeys } from "./keyboard/bindings.js";
import {
  claimReleaseClick,
  focused,
  nativeFocusTarget,
  onCurrentLocation,
  typesText,
} from "./focus.js";
import { pageScope } from "./keyboard/register.js";
import { offlineInteractive } from "./context.js";
import { watchPresentation, whenDocumentPresented } from "./semantic-state.js";
import { plainPress } from "./pointer.js";
import {
  hostIn,
  isElement,
  isNativeLayer,
  renderedParent,
  renderedUnder,
  under,
} from "./shadow-tree.js";
import { PREVIEW } from "./widget-upgrade.js";
import { keeps } from "./keeps.js";
import { watchOwner } from "./arrivals.js";
import { actionClass } from "./control-faces.js";
import { takeTitle, titled, titleWords } from "./element-markers.js";

/** @typedef {string | Node | import("/vendor/lit.js").TemplateResult} Word
 * @typedef {Word | readonly Word[]} Words
 * @typedef {readonly (readonly string[])[]} Presses
 * @typedef {Words | null | undefined | false} Line
 * @typedef {{name?: Words | null, keys?: Presses, detail?: readonly Line[], at?: Element | import("./rect.js").Box | null, excerpt?: boolean}} Preview
 * @typedef {Preview | null | undefined | false} Declared
 * @typedef {"pointer" | "focus" | "hold"} Route
 * @typedef {(route: Route) => Declared} Read
 * @typedef {{name: Words | null, keys: Presses, detail: Words[], at: Element | import("./rect.js").Box | null, excerpt: boolean, restates: boolean}} Reading
 * @typedef {import("./rect.js").Box} Box
 * @typedef {Element | Range} Target
 * @typedef {{from: Target, target: Target, holder: Element, route: Route, read: Read | null, at: {x: number, y: number} | undefined, stop: () => void, described: {el: Element, attribute: string | null, elements: readonly Element[] | null} | null}} Shown
 * @typedef {{pointerId: number, parent: Element | null, target: Target | null, read: Read | null, at: {x: number, y: number}, armed: boolean, timer: ReturnType<typeof setTimeout>}} Hold */

const DWELL = 200;
const WARM = 400;

// The one element every preview draws in.
const tip = document.createElement("div");
tip.className = "lf-ui lf-preview";
tip.id = "lf-preview";
tip.setAttribute("popover", "hint");
tip.setAttribute("role", "tooltip");

// The one face: the name with each press as key chips, then each line of detail.
const chip = (/** @type {string} */ step) =>
  html`<kbd class="lf-key-badge">${step}</kbd>`;
const chips = (/** @type {readonly string[]} */ steps) =>
  html`<span class="lf-preview-keys">${steps.map(chip)}</span>`;
const detailLine = (/** @type {Words} */ line) =>
  html`<span class="lf-preview-detail">${line}</span>`;
/** @type {(reading: Reading) => unknown[]} */
const face = ({ name, keys, detail }) => [
  name || keys.length
    ? html`<span class="lf-preview-name"
        ><span class="lf-preview-word">${name}</span>${keys.map(chips)}</span
      >`
    : nothing,
  ...detail.map(detailLine),
];

const CONTROL = 'button, summary, a[href], [role="button"], [data-lf-offer]';
// A proxy stands in for what the pointer takes by itself (control-faces.js, `proxy`),
// so what it stands for previews: a gloss's proxy, its phrase.
const PROXY = `.${actionClass("proxy")}`;

// The pointer takes the title the browser would show for it at `path`, the innermost,
// off its element the first time it comes, so the browser's own tooltip never stands
// beside the preview (element-markers.js, `takeTitle`). Putting it back as the pointer
// left wrote it twice a hover, which a screen reader hears as the element's description
// changing. A title the writer writes again is taken again with its new words.
/** @param {Iterable<EventTarget>} path */
function takePointedTitle(path) {
  for (const node of path)
    if (isElement(node) && node.hasAttribute("title") && titled(node))
      return takeTitle(node);
}

// The words of `text` alone, as one reads them, punctuation and case aside.
/** @param {string} text */
const wordsOf = (text) =>
  text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
// What a control's face says: its visible words, or none where it shows a symbol or a
// mark.
/** @param {Element} control */
const faceWords = (control) => wordsOf(control.textContent ?? "");
// A control's accessible name, as its markup gives it.
/** @param {Element} control */
function accessibleName(control) {
  const label = control.getAttribute("aria-label")?.trim();
  if (label) return label;
  const by = control.ariaLabelledByElements;
  if (by?.length)
    return by
      .map((el) => el.textContent?.trim() ?? "")
      .join(" ")
      .trim();
  return titleWords(control) ?? (control.textContent ?? "").replace(/\s+/g, " ").trim();
}

// What `node` declares, read once as its preview shows on `route`. A declaration that
// throws is a package's bug, reported where its author will see it, and says nothing.
/** @param {Element} node @param {Route} route @returns {Declared} */
function declaration(node, route) {
  const declared = node.lfPreview;
  if (typeof declared !== "function") return null;
  try {
    return declared.call(node, route);
  } catch (error) {
    reportError(error);
    return null;
  }
}

// Whether the search stops at `node` to read it: it declares a preview, carries a
// `title`, or is a control.
/** @param {Element} node */
const mayPreview = (node) =>
  typeof node.lfPreview === "function" ||
  titled(node) ||
  (node.matches(CONTROL) && !typesText(node));

/** Read `declared` into the face's lines: the name first, then each line of detail, each
 * said once, with the presses that reach `control`.
 * @param {Preview | null} declared @param {{name?: string | null, keys?: Presses, title?: string | null}} own
 * @returns {Reading | null} */
function lines(declared, own) {
  const keys = advertisesKeys()
    ? [
        ...new Map(
          [...(declared?.keys ?? []), ...(own.keys ?? [])].map((steps) => [
            steps.join(" "),
            steps,
          ]),
        ).values(),
      ]
    : [];
  /** @type {Words[]} */
  const said = [];
  for (const line of [
    declared?.name ?? own.name,
    ...(declared?.detail ?? []),
    own.title,
  ])
    if (line && !(typeof line === "string" && said.includes(line))) said.push(line);
  const [name = null, ...detail] = said;
  if (!name && !keys.length) return null;
  return {
    name,
    keys,
    detail,
    at: declared?.at ?? null,
    excerpt: Boolean(declared?.excerpt),
    restates: false,
  };
}

// What `node` previews of its own as it shows on `route`: false where it says nothing
// and nothing around it may, null where it says nothing of its own. A control says its
// accessible name where its face shows a symbol or doesn't say that name, and the keys
// that press it; a declaration and a `title` add their lines under them. Its
// `aria-description` is a screen reader's, which often names what its face shows, as a
// diff row's names its path, so a preview leaves it out.
/** @param {Element} node @param {Route} route @returns {Reading | null | false} */
function readingOf(node, route) {
  if (node.getAttribute("aria-expanded") === "true" || node.matches(PROXY)) return null;
  const declared = declaration(node, route);
  if (declared === false) return false;
  const title = titleWords(node);
  if (!(node.matches(CONTROL) && !typesText(node)))
    return lines(declared ?? null, { title });
  const name = accessibleName(node);
  const face = faceWords(node);
  const keys = controlKeys(node);
  const unsaid = Boolean(name) && !(face && ` ${wordsOf(name)} `.includes(` ${face} `));
  // A title the name already says, as a symbol's short word under its longer label,
  // adds no line.
  const titled =
    title && !` ${wordsOf(name)} `.includes(` ${wordsOf(title)} `) ? title : null;
  if (!declared && !unsaid && !keys.length && !titled) return null;
  const reading = lines(declared ?? null, { name, keys, title: titled });
  // Made of the control's own name and keys alone, it says what a screen reader already
  // hears from them.
  if (reading) reading.restates = !declared && !titled;
  return reading;
}
// The innermost node along `path` the search stops at, read as its preview shows.
/** @param {Iterable<EventTarget>} path @returns {Element | null} */
function candidate(path) {
  for (const node of path) {
    if (!isElement(node)) continue;
    if (node === tip) return null;
    if (mayPreview(node)) return node;
  }
  return null;
}
// Whether `target` stands in a column of targets, as margin entries and a list's rows
// do, so a preview below it would cover the next and keep the pointer from it: a target
// just above or below it, and none just beside it, where a toolbar's controls stand,
// whose preview below covers none of them. A few hit tests each side, at the target's
// middle, as far as a preview's first line reaches.
const REACH = [10, 24, 40];
/** @param {Element} target */
function stacked(target) {
  const box = target.getBoundingClientRect();
  const x = (box.left + box.right) / 2;
  const y = (box.top + box.bottom) / 2;
  /** @param {number} atX @param {number} atY */
  const other = (atX, atY) => {
    let hit = document.elementFromPoint(atX, atY);
    const inner = hit?.shadowRoot?.elementFromPoint(atX, atY);
    if (inner) hit = inner;
    const found = hit && candidate(climb(hit));
    return Boolean(
      found && found !== target && !found.contains(target) && !target.contains(found),
    );
  };
  if (REACH.some((step) => other(box.left - step, y) || other(box.right + step, y)))
    return false;
  return REACH.some((step) => other(x, box.top - step) || other(x, box.bottom + step));
}
/** @param {Element} node */
function* climb(node) {
  for (let at = /** @type {Element | null} */ (node); at; at = renderedParent(at))
    yield at;
}
// What previews from `node` outward on `route`, and where it stands.
/** @param {Element} node @param {Route} route @returns {{target: Element, reading: Reading} | null} */
function readOutward(node, route) {
  for (let at = /** @type {Element | null} */ (node); at; at = renderedParent(at)) {
    if (at === tip) return null;
    if (!mayPreview(at)) continue;
    const reading = readingOf(at, route);
    if (reading === false) return null;
    if (reading) return { target: at, reading };
  }
  return null;
}

/** @type {Shown | null} */
let shown = null;
// When the last preview went, for the warm switch.
let cooled = -Infinity;
// The target under a hovering pointer, the read its range's owner gave, and the dwell
// before its preview.
/** @type {Target | null} */
let pointing = null;
/** @type {Read | null} */
let pointingRead = null;
/** @type {{x: number, y: number} | undefined} */
let pointingAt;
/** @type {ReturnType<typeof setTimeout> | undefined} */
let dwell;
// The wait before a pointer's preview goes once the pointer has left its target.
/** @type {ReturnType<typeof setTimeout> | undefined} */
let leaving;
// The target whose preview a press, a key or Escape put away, quiet until the user
// points at something else or focus arrives anew.
/** @type {Target | null} */
let quiet = null;
/** @type {Hold | null} */
let hold = null;
// Where the pointer last stood, which tells a target the user moved onto from one
// that arrived under a still pointer.
let rest = { x: NaN, y: NaN };
// The innermost node under a mouse pointer, which says whether a changed preview is the
// pointer's to read.
/** @type {Node | null} */
let beneath = null;
// The key that is down, if one is: a change a key brings to the focused element is the
// keyboard's to read, since Firefox shows no focus a key lands on once a pointer's press
// gave it, and a focus a key moves is the user's own, but for Escape's.
/** @type {string | null} */
let keyDown = null;
// Whether the pointer the user last moved or pressed is a finger, which reads a range
// only while it holds a press (`pointRange`).
let finger = false;

// What `from` previews on `route`, a range's through the read its owner gave.
/** @param {Target} from @param {Route} route @param {Read | null} read
 * @returns {{target: Target, holder: Element, reading: Reading} | null} */
function readFrom(from, route, read) {
  if (!(from instanceof Range)) {
    const outward = from.isConnected ? readOutward(from, route) : null;
    return outward && { ...outward, holder: outward.target };
  }
  const holder = isElement(from.startContainer)
    ? from.startContainer
    : from.startContainer.parentElement;
  let declared = null;
  try {
    declared = holder?.isConnected && read ? read(route) : null;
  } catch (error) {
    reportError(error);
  }
  const reading = declared ? lines(declared, {}) : null;
  return holder && reading ? { target: from, holder, reading } : null;
}

// Show what `from` previews on `route`, and say whether one shows. Shown `again` for
// the preview standing, it draws what its target says now where it stands, with no
// fade.
/** @param {Target} from @param {Route} route @param {Read | null} [read] @param {{x: number, y: number}} [at] @param {boolean} [again] */
function show(from, route, read = null, at, again = false) {
  if (!again && shown?.from === from && shown.route === route) return true;
  const found = readFrom(from, route, read);
  const standing = again && found && shown?.from === from ? shown : null;
  // Ending the standing record's watch can run its disconnect, which hides whatever
  // `shown` names, so the record stops being the one shown first.
  if (standing) {
    shown = null;
    standing.stop();
  } else hide();
  if (!found) return false;
  const { target, holder, reading } = found;
  render(face(reading), tip);
  /** @type {Shown} */
  /** @type {Shown} */
  const record = {
    from,
    target,
    holder,
    route,
    read,
    at,
    stop: () => {},
    described: null,
  };
  // A target that leaves the page, as a re-render replaces it, takes its preview along.
  record.stop = watchOwner(holder, { disconnect: () => shown === record && hide() });
  shown = record;
  keeps(tip, "data-lf-route", route);
  keeps(tip, "data-lf-face", reading.excerpt ? "excerpt" : null);
  if (route === "hold" && !(target instanceof Range)) keeps(holder, "data-lf-held", "");
  if (!standing) showNativeLayer(tip);
  stand(record, reading, at);
  if (standing) {
    record.described = standing.described;
    return true;
  }
  // A screen reader hears a preview shown on focus as what focus is on describes, unless
  // it says only what the control's own name and keys already do, or focus is on a
  // proxy, whose own markup describes what it stands for.
  const on = focused();
  if (route === "focus" && on && !reading.restates && !on.matches(PROXY)) {
    record.described = {
      el: on,
      attribute: on.getAttribute("aria-describedby"),
      elements: on.ariaDescribedByElements,
    };
    on.ariaDescribedByElements = [...(on.ariaDescribedByElements ?? []), tip];
  }
  return true;
}

// Where a preview stands, one rule for every target (`stand`): beside the box it
// previews, a range's line, a declared box or element, or the target, by the gap that
// clears a focus ring; below it, or above where the window has no room below, and above
// first for a finger, which covers what lies below, and for a point inside its target,
// as a chart's tip leaves the axis below in view; beside a column of targets
// (`stacked`), so it covers none of them, on the side toward the nearer window edge
// where there is room, as a margin entry's stands in the free margin rather than over
// the passage it is about. Along the other axis it starts at the box's
// start edge and stays inside the nearest box around the target wide enough to hold it,
// shifting back toward the start where it would cross that box's end: a link early in a
// line keeps its preview in the reading column, and a control at a card's end edge keeps
// its preview in the card. It is written as insets from the box that carries the target
// through a scroll (`carrier`, css-anchors.js `anchorAt`), so a hover names no target and
// adds no rule.
const EDGE = 8;
const GAP = { line: 6, box: 11, hold: 27 };

/** @param {Box} box @param {number} x @param {number} y */
const holds = (box, x, y) =>
  x >= box.left && x <= box.right && y >= box.top && y <= box.bottom;

/** @param {Shown} record @param {Reading} reading @param {{x: number, y: number}} [at] */
function stand(record, reading, at) {
  const { target, holder, route } = record;
  const declared = reading.at;
  /** @type {Box | undefined} */
  let box;
  if (target instanceof Range) {
    const lines = [...target.getClientRects()];
    box = lines.find((line) => at && holds(line, at.x, at.y)) ?? lines[0];
  } else if (declared && !isElement(declared)) box = declared;
  else
    box = anchorElement(
      declared?.isConnected ? declared : holder,
    ).getBoundingClientRect();
  if (!box) return;
  const { width, height } = tip.getBoundingClientRect();
  const room = { width: document.documentElement.clientWidth, height: innerHeight };
  const point = Boolean(declared) && !isElement(declared);
  const gap =
    target instanceof Range ? GAP.line : route === "hold" ? GAP.hold : GAP.box;
  /** @param {number} at @param {number} low @param {number} high */
  const clamp = (at, low, high) => Math.max(low, Math.min(at, high));
  let left;
  let top;
  const before = box.left - gap - width;
  const after = box.right + gap;
  const fitsBefore = before >= EDGE;
  const fitsAfter = after + width <= room.width - EDGE;
  // A column too wide to stand beside, as a list of full rows, takes it below instead.
  if (
    route !== "hold" &&
    !point &&
    !(target instanceof Range) &&
    (fitsBefore || fitsAfter) &&
    stacked(holder)
  ) {
    const outward = box.left + box.right > room.width ? fitsAfter : !fitsBefore;
    left = outward && fitsAfter ? after : fitsBefore ? before : after;
    top = box.top;
  } else {
    const above = box.top - gap - height;
    const below = box.bottom + gap;
    const upFirst = route === "hold" || point;
    top = upFirst
      ? above >= EDGE
        ? above
        : below
      : below + height <= room.height - EDGE || above < EDGE
        ? below
        : above;
    const container = containerFor(holder, width);
    left = clamp(box.left, container.left, container.right - width);
  }
  left = clamp(left, EDGE, room.width - width - EDGE);
  top = clamp(top, EDGE, room.height - height - EDGE);
  anchorAt(
    tip,
    anchorElement(carrier(holder)),
    { left, top },
    undefined,
    "anchors-visible",
  );
}
// The box that carries `holder` through a scroll or holds it still over one: the nearest
// box around it that scrolls, stands fixed or sticky, or stands in the top layer, else
// the page's root. The preview stands by insets from it, so a hover names no target:
// naming one wrote its style, which observers of the page's boxes, as the margin's, hear
// as a change and lay out again, the first time each paragraph previewed. These boxes
// are few, each named once.
/** @param {Element} holder */
function carrier(holder) {
  for (
    let at = /** @type {Element | null} */ (hostIn(holder, document) ?? holder);
    at && at !== document.documentElement;
    at = renderedParent(at)
  ) {
    if (isNativeLayer(at)) return at;
    const { position, overflowX, overflowY } = getComputedStyle(at);
    if (position === "fixed" || position === "sticky") return at;
    if (/auto|scroll/.test(`${overflowX} ${overflowY}`)) return at;
  }
  return document.documentElement;
}
// The nearest box around `holder` wide enough to hold a preview `width` wide: the
// paragraph a link stands in, the card a toolbar stands in, else the window.
/** @param {Element} holder @param {number} width @returns {Box} */
function containerFor(holder, width) {
  for (
    let at = renderedParent(holder);
    at && at !== document.body;
    at = renderedParent(at)
  ) {
    const box = at.getBoundingClientRect();
    if (box.width >= width) return box;
  }
  return {
    left: 0,
    top: 0,
    right: document.documentElement.clientWidth,
    bottom: innerHeight,
  };
}

function hide() {
  if (!shown) return;
  const record = shown;
  shown = null;
  record.stop();
  const described = record.described;
  if (described) {
    // What it was described by before, an attribute's ids, elements set or nothing.
    if (described.attribute === null) described.el.ariaDescribedByElements = null;
    else if (described.attribute === "")
      described.el.ariaDescribedByElements = described.elements;
    else described.el.setAttribute("aria-describedby", described.attribute);
  }
  if (record.route === "hold" && !(record.target instanceof Range))
    record.holder.removeAttribute("data-lf-held");
  // Its words stay in the closed popover, so the next preview that says the same
  // writes nothing.
  closeNativeLayer(tip);
  cooled = performance.now();
}

// The pointer's target changed: start its dwell, or show it at once while warm. A
// pointer that leaves its target for nothing, as on its way onto the preview, puts the
// preview away only after a dwell, which its reaching the preview or the target cancels;
// one that reaches another target shows that one at once.
/** @param {Target | null} target @param {Read | null} [read] @param {{x: number, y: number}} [at] */
function point(target, read = null, at) {
  if (target === pointing) return;
  clearTimeout(leaving);
  pointing = target;
  pointingRead = read;
  pointingAt = at;
  clearTimeout(dwell);
  if (shown?.route === "pointer" && !target) {
    const record = shown;
    leaving = setTimeout(() => {
      if (shown === record && !pointing) hide();
    }, DWELL);
  } else if (shown && shown.route !== "focus" && shown.from !== target) hide();
  if (target !== quiet) quiet = null;
  if (!target || target === quiet) return;
  if (performance.now() - cooled < WARM) show(target, "pointer", read, at);
  else
    dwell = setTimeout(() => {
      if (pointing === target) show(target, "pointer", pointingRead, pointingAt);
    }, DWELL);
}

// Put the standing preview away for its target, until the user comes to another.
function quieten() {
  clearTimeout(dwell);
  if (!shown) return;
  quiet = shown.from;
  hide();
}

/** @param {Range} a @param {Target | null} b */
const sameRange = (a, b) =>
  b instanceof Range &&
  a.startContainer === b.startContainer &&
  a.startOffset === b.startOffset &&
  a.endContainer === b.endContainer &&
  a.endOffset === b.endOffset;

/** A range's owner says the pointer rests on one of its ranges, or on none of them: what
 * pointing at it reads, and where the pointer is, which picks the line it stands by. A
 * range with the same boundaries as the one pointed at is the same range, however many
 * times its owner makes it, and its latest read is the one a standing preview says. A
 * target inside the range under the pointer, as a link in a thread's passage, is the
 * innermost and wins, as it does for the keyboard and a finger. A finger holding a
 * press holds the range it rests on (`holdRange`); one that only moved reads none.
 * @param {Range | null} range @param {Read} [read] @param {{x: number, y: number}} [at] */
export function pointRange(range, read, at) {
  if (hold) holdRange(hold, range, read, at);
  else if (finger) return;
  else if (range) {
    // The same range again may say other words: its declaration is the latest, and a
    // preview standing for it reads it now.
    if (sameRange(range, pointing)) {
      pointingRead = read ?? null;
      if (shown?.from === pointing && read) {
        shown.read = read;
        refresh();
      }
      return;
    }
    const holder = isElement(range.commonAncestorContainer)
      ? range.commonAncestorContainer
      : range.commonAncestorContainer.parentElement;
    if (pointing && isElement(pointing) && holder && renderedUnder(pointing, holder))
      return;
    point(range, read, at);
  } else if (pointing instanceof Range) point(null);
}

// A finger's hold rests on a range or on none, unless it holds an element, which
// previews itself; once the dwell has armed the hold, it shows the range's preview. The
// same range again keeps its place and takes its owner's latest words.
/** @param {Hold} held @param {Range | null} range @param {Read | undefined} read @param {{x: number, y: number}} [at] */
function holdRange(held, range, read, at) {
  if (isElement(held.target)) return;
  if (range ? sameRange(range, held.target) : !held.target) {
    if (range && read) held.read = read;
    return;
  }
  held.target = range;
  held.read = (range && read) || null;
  if (at) held.at = at;
  if (!held.armed) return;
  if (!range || !show(range, "hold", held.read, held.at)) hide();
}

// What `node` previews changed (`previewChanged`): a preview standing for it reads it
// again where it stands, with no dwell and no fade, or goes where it now says nothing;
// otherwise the route reading the node now shows it, a finger holding it or one beside
// it, the keyboard's focus on it, or a pointer over it, after the dwell. Each is a new
// reading, whatever put the last one away.
/** @param {Element} node */
function changed(node) {
  if (quiet === node) quiet = null;
  if (shown && shown.from === node) {
    show(node, shown.route, null, undefined, true);
    return;
  }
  if (hold?.armed) {
    if (hold.target === node || (!hold.target && hold.parent === node.parentElement)) {
      hold.target = node;
      show(node, "hold");
    }
  } else if (focused() === node && (keyDown || node.matches(":focus-visible")))
    show(node, "focus");
  else if (beneath && under(beneath, node)) {
    pointing = null;
    point(node);
  }
}

// Whether the user moved focus to `node` themselves, which is what a focus preview
// reads: a Tab or Shift+Tab (`step`), or a key that moved them between items, as an
// arrow, Home or End does in a list or a widget, a move made while a key is down that
// stays in the surface the user was in. Focus the runtime places as a surface opens,
// as the Page Map's first row or a margin card's first control, focus it hands back as
// one closes (`return`), and focus Escape moves as the user backs out, as from a reply
// box to its thread, are no aim of theirs: a preview there stands in front of the
// Escape the user reaches for next, which it would take.
/** @param {Element} node @param {import("./focus.js").CurrentLocationCause} cause @param {Element | null} left */
function aimed(node, cause, left) {
  if (cause === "step") return true;
  if (cause !== "move" || !keyDown || keyDown === "Escape") return false;
  for (let at = /** @type {Element | null} */ (node); at; at = renderedParent(at))
    if (isNativeLayer(at) || at.getAttribute("role") === "dialog")
      return Boolean(left && renderedUnder(left, at));
  return true;
}

// A new presentation of the document reads the standing preview again, as the place a
// link opens or a thread's turn changes under it: what it says now is drawn where it
// stands, with no fade, and words that came back the same leave it as it is. A
// preview whose target now says nothing goes.
function refresh() {
  const record = shown;
  if (!record) return;
  const found = readFrom(record.from, record.route, record.read);
  if (!found) return hide();
  if (found.target !== record.target)
    return void show(record.from, record.route, record.read, record.at, true);
  const before = tip.textContent;
  render(face(found.reading), tip);
  if (tip.textContent !== before) stand(record, found.reading, record.at);
}
let refreshing = false;

/** @param {HTMLElement} home */
export function mountPreviews(home) {
  home.append(tip);
  // Once for each new presentation, a revision's included, after it has painted, and
  // never for a pointer's move.
  const presented = () => {
    if (!shown || refreshing) return;
    refreshing = true;
    void whenDocumentPresented()
      .catch(() => {})
      .then(() => {
        refreshing = false;
        refresh();
      });
  };
  watchPresentation(presented);

  document.addEventListener(
    PREVIEW,
    (event) => {
      const [node] = event.composedPath();
      if (isElement(node)) changed(node);
    },
    { capture: true },
  );
  // The platform hides a hint as another popover opens over it, or as a press lands
  // elsewhere, and the record goes with it.
  tip.addEventListener("toggle", (event) => {
    if (/** @type {ToggleEvent} */ (event).newState === "closed" && shown) hide();
  });
  document.addEventListener(
    "pointerover",
    (event) => {
      if (event.pointerType === "touch") return;
      const path = event.composedPath();
      beneath = isElement(path[0]) ? path[0] : null;
      // The pointer on a preview keeps it, as on its target (WCAG 1.4.13, "Hoverable").
      if (path.includes(tip)) {
        clearTimeout(leaving);
        if (shown?.route === "pointer") pointing = shown.from;
        return;
      }
      takePointedTitle(path);
      // Something that arrives under a pointer the user hasn't moved takes it, but
      // shows nothing: the user pointed at what was there before. A pointer carrying a
      // press, as a drag does, is acting, not reading.
      const still = event.clientX === rest.x && event.clientY === rest.y;
      rest = { x: event.clientX, y: event.clientY };
      const found = candidate(path);
      if (still || event.buttons) {
        if (found !== pointing) {
          pointing = found;
          pointingRead = null;
        }
        clearTimeout(dwell);
        if (shown?.route === "pointer" && shown.from !== pointing) hide();
      } else if (found) point(found);
      else if (!(pointing instanceof Range)) point(null);
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      rest = { x: event.clientX, y: event.clientY };
      finger = event.pointerType === "touch";
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointerout",
    (event) => {
      if (event.pointerType === "touch" || event.relatedTarget !== null) return;
      beneath = null;
      point(null);
    },
    { capture: true, passive: true },
  );
  // Focus arriving is a new reading, whatever put the target's last one away, and
  // focus leaving takes its preview along. It shows once the task that moved focus has
  // done, which may be opening a popover the platform lets no other open inside, and
  // only where the user moved focus there themselves (`aimed`).
  onCurrentLocation((node, cause, left) => {
    quiet = null;
    if (shown?.route === "focus" && shown.from !== node) hide();
    if (!node || !aimed(node, cause, left)) return;
    queueMicrotask(() => {
      if (focused() !== node || !node.matches(":focus-visible")) return;
      if (shown?.from !== node) show(node, "focus");
    });
  });
  // Escape is the preview's own step while one stands, ahead of every other, which
  // does nothing else; any other key puts a pointer's away and goes on to its work.
  pageScope("preview", {
    title: "A preview",
    escape: "inner",
    at: () => shown !== null,
    rows: [
      {
        id: "preview.dismiss",
        keys: ["Escape"],
        title: "put the preview away",
        touch: false,
        run: quieten,
      },
    ],
  });
  document.addEventListener(
    "keydown",
    (event) => {
      keyDown = event.key;
      if (event.key === "Escape") {
        if (offlineInteractive) quieten();
      } else if (shown?.route === "pointer" || !shown) quieten();
    },
    { capture: true },
  );
  document.addEventListener("keyup", () => (keyDown = null), { capture: true });
  document.addEventListener(
    "pointerdown",
    (event) => {
      endHold();
      finger = event.pointerType === "touch";
      if (!finger) return quieten();
      if (!event.isPrimary || !plainPress(event)) return;
      const found = candidate(event.composedPath());
      if (found?.matches(":disabled, [aria-disabled='true']")) return;
      const origin = event.composedPath()[0];
      if (found && isElement(origin) && origin.hasPointerCapture(event.pointerId))
        origin.releasePointerCapture(event.pointerId);
      // Where no element previews, the hold waits for a range's owner to say what the
      // finger rests on (`holdRange`), which it says as the press arrives.
      /** @type {Hold} */
      const held = {
        pointerId: event.pointerId,
        parent: found?.parentElement ?? null,
        target: found,
        read: null,
        at: { x: event.clientX, y: event.clientY },
        armed: false,
        timer: setTimeout(() => {
          if (hold !== held) return;
          // Held this long, the finger reads, wherever it is now: one that slid onto
          // the gap beside a neighbour reads the next it reaches.
          held.armed = true;
          if (held.target) show(held.target, "hold", held.read, held.at);
        }, DWELL),
      };
      hold = held;
    },
    { capture: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      if (hold?.pointerId !== event.pointerId || hold.target instanceof Range) return;
      const found = candidate(event.composedPath());
      const neighbour = found?.parentElement === hold.parent ? found : null;
      if (neighbour === hold.target) return;
      hold.target = neighbour;
      if (!hold.armed) return;
      if (!neighbour || !show(neighbour, "hold")) hide();
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointerup",
    (event) => {
      if (hold?.pointerId !== event.pointerId) return;
      const { target } = hold;
      const read = shown?.route === "hold" && shown.from === target;
      endHold();
      if (!read || !target || !plainPress(event)) return;
      claimReleaseClick();
      if (target instanceof HTMLElement || target instanceof SVGElement)
        nativeFocusTarget(target).focus({ preventScroll: true, focusVisible: false });
      placeHolder(target)?.dispatchEvent(
        new MouseEvent("click", {
          bubbles: true,
          cancelable: true,
          composed: true,
          detail: 1,
          clientX: event.clientX,
          clientY: event.clientY,
        }),
      );
    },
    { capture: true },
  );
  document.addEventListener(
    "pointercancel",
    (event) => {
      if (hold?.pointerId === event.pointerId) endHold();
    },
    { capture: true },
  );
  // A tab the user leaves ends what they were reading in it.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      keyDown = null;
      point(null);
      quieten();
      endHold();
    }
  });
  document.addEventListener(
    "contextmenu",
    (event) => {
      // Only while a held preview shows: a hold over a target that showed none, as an
      // external link, keeps the platform's own long-press menu.
      if (hold?.armed && shown?.route === "hold") event.preventDefault();
    },
    { capture: true },
  );
}

function endHold() {
  if (!hold) return;
  clearTimeout(hold.timer);
  hold = null;
  if (shown?.route === "hold") hide();
}
