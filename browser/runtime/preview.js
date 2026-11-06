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
     as its preview shows on that route (`"pointer"`, `"focus"` or `"hold"`):
     `{name, keys, detail, at, excerpt}`, every field optional (module-input.md,
     "Previews"). On a control its lines stand under the control's own name and keys,
     and its name replaces the accessible name where that says more than the face
     should; `at` is where to stand, the declaring element by default, another element
     or a box in client coordinates inside it, as a chart's point, which the preview
     stands above; and `excerpt` asks for the face's room for a block of the page. When
     what it says changes under an aim that stays, it says so (`previewChanged`,
     widget-upgrade.js), and a standing preview redraws in place or the route reading
     the element shows it. It returns null where
     it adds nothing, so the search goes on outward, and false where nothing shows and
     nothing around it may. A widget declares it with no import, as it declares
     `lfCommands` and `lfCopy()`, so off Leaf it reads nothing. What a declaration
     throws is reported and shows nothing.
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
     likes, and this module does the rest, placing the preview by the line the pointer
     is on.

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
   hint closes no popover the user opened. It takes no pointer and holds no control, so
   it is no layer the keyboard tiers its scopes over (layer-stack.js). It stands beside
   its target by CSS anchor positioning, by the name css-anchors.js gives a target in
   the document, and by a place of its own over any other box (`standBy`), so a hover
   adds no rule: below it, its end edge in line with the target's, so it stays within
   the surface the target stands in, above where the window has no room below, and
   higher above a finger that holds it, which covers what lies below and around it. Its
   gap to the target clears the target's focus ring. The browser carries it through
   every scroll that moves its target, and nothing around the target moves. A range's
   preview stands by insets from the box in the document holding the range, measured
   when it shows.

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
     preview is held, the platform's long-press menu stays shut.
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
   they run long, where a margin entry's label cut its question to one line. It stands by
   its own target and may cover a neighbouring entry, which still takes the pointer
   through it: the margin's labels each measured every entry on the page to stand clear
   of them, a page-wide read on every hover. Escape put a preview away and took its own
   step too until 5 November 2026: dismissing one then closed the thread card the user
   was reading, since the preview covers its first line. Rejected: `interestfor`, which
   gives a control the same three routes natively but ships only in Chromium; the
   platform's `title` alone, which no finger or keyboard reads and which can't draw a
   key chip; holding a `title` off only while the pointer rests within its element and
   putting it back as the pointer leaves, which writes it twice a hover, each a change
   of the element's description a screen reader hears; a popover's implicit anchor (`showPopover({source})`), which Firefox 157
   keeps on the first source it was shown with; and a preview that follows its target
   by a script, which trails each scroll by a frame. */
import { html, nothing, render } from "/runtime/framework.js";
import { anchorAt, anchorElement, anchorName } from "./css-anchors.js";
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
import { plainPress } from "./pointer.js";
import { hostIn, isElement, renderedParent, under } from "./shadow-tree.js";
import { PREVIEW } from "./widget-upgrade.js";
import { keeps } from "./keeps.js";
import { watchOwner } from "./arrivals.js";
import { actionClass } from "./control-faces.js";

/** @typedef {string | Node | import("/vendor/lit.js").TemplateResult} Word
 * @typedef {Word | readonly Word[]} Words
 * @typedef {readonly (readonly string[])[]} Presses
 * @typedef {Words | null | undefined | false} Line
 * @typedef {{name?: Words | null, keys?: Presses, detail?: readonly Line[], at?: Element | import("./rect.js").Box | null, excerpt?: boolean}} Preview
 * @typedef {Preview | null | undefined | false} Declared
 * @typedef {"pointer" | "focus" | "hold"} Route
 * @typedef {(route: Route) => Declared} Read
 * @typedef {{name: Words | null, keys: Presses, detail: Words[], at: Element | import("./rect.js").Box | null, excerpt: boolean, restates: boolean}} Reading
 * @typedef {Element | Range} Target
 * @typedef {{from: Target, target: Target, holder: Element, route: Route, stop: () => void, described: {el: Element, attribute: string | null, elements: readonly Element[] | null} | null}} Shown
 * @typedef {{pointerId: number, parent: Element | null, target: Element | null, armed: boolean, timer: ReturnType<typeof setTimeout>}} Hold */

const DWELL = 200;
const WARM = 400;
// The space between a range's preview and the line it stands by, which a range's
// owner draws no ring around (the face's own gap is controls.css's).
const GAP = 6;

// The one element every preview draws in.
const tip = document.createElement("div");
tip.className = "lf-ui lf-preview";
tip.id = "lf-preview";
tip.setAttribute("popover", "hint");
tip.setAttribute("role", "tooltip");

// The one face: the name with each press as key chips, then each line of detail.
/** @param {Reading} reading */
const face = ({ name, keys, detail }) =>
  html`${
    name || keys.length
      ? html`<span class="lf-preview-name"
          ><span class="lf-preview-word">${name}</span>${keys.map(
            (steps) =>
              html`<span class="lf-preview-keys"
                >${steps.map(
                  (step) => html`<kbd class="lf-key-badge">${step}</kbd>`,
                )}</span
              >`,
          )}</span
        >`
      : nothing
  }${detail.map((line) => html`<span class="lf-preview-detail">${line}</span>`)}`;

const CONTROL = 'button, summary, a[href], [role="button"], [data-lf-offer]';
// A proxy stands in for what the pointer takes by itself (control-faces.js, `proxy`),
// so what it stands for previews: a gloss's proxy, its phrase.
const PROXY = `.${actionClass("proxy")}`;

// The words an element's `title` gave it, taken off the element the first time the
// pointer reaches it, so the browser's own tooltip never stands beside its preview.
// Putting it back as the pointer left wrote it twice a hover, which a screen reader
// hears as the element's description changing. A title the writer writes again is
// taken again, with its new words, the next time the pointer comes.
/** @type {WeakMap<Element, string>} */
const takenTitles = new WeakMap();
/** @param {Element} el */
const titleOf = (el) => el.getAttribute("title") ?? takenTitles.get(el) ?? null;
// Take the title the browser would show for the pointer at `path`: the innermost one.
/** @param {Iterable<EventTarget>} path */
function takeTitle(path) {
  for (const node of path) {
    if (!isElement(node) || !node.hasAttribute("title")) continue;
    takenTitles.set(node, node.getAttribute("title") ?? "");
    node.removeAttribute("title");
    return;
  }
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
  return titleOf(control) ?? (control.textContent ?? "").replace(/\s+/g, " ").trim();
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
  node.hasAttribute("title") ||
  takenTitles.has(node) ||
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
  const title = titleOf(node);
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
// Whether a key is down: a change a key brings to the focused element is the keyboard's
// to read, since Firefox shows no focus a key lands on once a pointer's press gave it.
let keying = false;

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
  if (standing) standing.stop();
  else hide();
  if (!found) return false;
  const { target, holder, reading } = found;
  render(face(reading), tip);
  /** @type {Shown} */
  const record = { from, target, holder, route, stop: () => {}, described: null };
  // A target that leaves the page, as a re-render replaces it, takes its preview along.
  record.stop = watchOwner(holder, { disconnect: () => shown === record && hide() });
  shown = record;
  keeps(tip, "data-lf-route", route);
  const point = Boolean(reading.at) && !isElement(reading.at);
  keeps(tip, "data-lf-at", target instanceof Range ? "range" : point ? "point" : null);
  keeps(tip, "data-lf-face", reading.excerpt ? "excerpt" : null);
  if (route === "hold") keeps(holder, "data-lf-held", "");
  if (target instanceof Range) {
    tip.style.removeProperty("position-anchor");
    showNativeLayer(tip);
    standByRange(target, holder, at);
  } else {
    for (const inset of ["position", "left", "top", "position-visibility"])
      tip.style.removeProperty(inset);
    tip.style.setProperty("position-anchor", standBy(reading.at ?? holder, holder));
    if (!standing) showNativeLayer(tip);
  }
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

// The places a preview stands by where its target is no box the document can name, as
// a box in a widget's shadow tree is not, or where it names a box inside itself, as a
// chart's point: each stands over that box by insets from the nearest box in the
// document, which carries it through every scroll. Naming the box itself would declare
// a `::part()` rule for each box a hover reached, kept for the session, and in Chromium
// restyle the page each time an anchor's name moved. Two take turns, so a preview whose
// anchor changed is placed afresh, where one keeping its anchor would first stand where
// the last box's fallback had put it.
/** @param {string} name */
const placeNamed = (name) => {
  const place = document.createElement("div");
  place.className = "lf-ui lf-preview-at";
  place.style.setProperty("anchor-name", name);
  return { place, name };
};
const places = /** @type {const} */ ([
  placeNamed("--lf-preview-at"),
  placeNamed("--lf-preview-by"),
]);
let turn = 0;
/** The name the preview stands by: a box in the document by its own, and any other by a
 * place over it, an element or a box in client coordinates inside `holder`.
 * @param {Element | import("./rect.js").Box} at @param {Element} holder */
function standBy(at, holder) {
  if (isElement(at) && at.getRootNode() === document)
    return anchorName(anchorElement(at));
  const box = isElement(at) ? at.getBoundingClientRect() : at;
  const host =
    hostIn(isElement(at) ? at : holder, document) ?? document.documentElement;
  turn = turn ? 0 : 1;
  const { place, name } = turn ? places[1] : places[0];
  anchorAt(place, anchorElement(host), box, undefined, "anchors-visible");
  return name;
}

// A range's preview stands below the line the pointer is on, or above it where the
// window has no room below, inside the window's width, by insets from the nearest box
// in the document holding it.
/** @param {Range} range @param {Element} holder @param {{x: number, y: number}} [at] */
function standByRange(range, holder, at) {
  const lines = [...range.getClientRects()];
  const line =
    lines.find(
      (rect) =>
        at &&
        at.x >= rect.left &&
        at.x <= rect.right &&
        at.y >= rect.top &&
        at.y <= rect.bottom,
    ) ?? lines[0];
  if (!line) return;
  const { width, height } = tip.getBoundingClientRect();
  const room = document.documentElement.clientWidth;
  const left = Math.max(GAP, Math.min(line.left, room - width - GAP));
  const top =
    line.bottom + GAP + height > innerHeight
      ? line.top - GAP - height
      : line.bottom + GAP;
  const host = hostIn(holder, document) ?? document.documentElement;
  anchorAt(tip, anchorElement(host), { left, top }, undefined, "anchors-visible");
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
  if (record.route === "hold") record.holder.removeAttribute("data-lf-held");
  // Its words stay in the closed popover, so the next preview that says the same
  // writes nothing.
  closeNativeLayer(tip);
  cooled = performance.now();
}

// The pointer's target changed: start its dwell, or show it at once while warm.
/** @param {Target | null} target @param {Read | null} [read] @param {{x: number, y: number}} [at] */
function point(target, read = null, at) {
  if (target === pointing) return;
  pointing = target;
  pointingRead = read;
  pointingAt = at;
  clearTimeout(dwell);
  if (shown && shown.route !== "focus" && shown.from !== target) hide();
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
 * times its owner makes it.
 * @param {Range | null} range @param {Read} [read] @param {{x: number, y: number}} [at] */
export function pointRange(range, read, at) {
  if (range) {
    if (sameRange(range, pointing)) return;
    point(range, read, at);
  } else if (pointing instanceof Range) point(null);
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
  } else if (focused() === node && (keying || node.matches(":focus-visible")))
    show(node, "focus");
  else if (beneath && under(beneath, node)) {
    pointing = null;
    point(node);
  }
}

/** @param {HTMLElement} home */
export function mountPreviews(home) {
  home.append(...places.map(({ place }) => place), tip);
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
      takeTitle(path);
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
  // done, which may be opening a popover the platform lets no other open inside. Focus
  // handed back, as a surface the user closed returns them to what opened it, is no
  // arrival of theirs, so it reads nothing there: a preview over it would stand in
  // front of the next Escape the user is backing out with.
  onCurrentLocation((node, cause) => {
    quiet = null;
    if (shown?.route === "focus" && shown.from !== node) hide();
    if (!node || cause === "return") return;
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
      keying = true;
      if (event.key === "Escape") {
        if (offlineInteractive) quieten();
      } else if (shown?.route === "pointer" || !shown) quieten();
    },
    { capture: true },
  );
  document.addEventListener("keyup", () => (keying = false), { capture: true });
  document.addEventListener(
    "pointerdown",
    (event) => {
      endHold();
      if (event.pointerType !== "touch") return quieten();
      if (!event.isPrimary || !plainPress(event)) return;
      const found = candidate(event.composedPath());
      if (!found || found.matches(":disabled, [aria-disabled='true']")) return;
      const origin = event.composedPath()[0];
      if (isElement(origin) && origin.hasPointerCapture(event.pointerId))
        origin.releasePointerCapture(event.pointerId);
      /** @type {Hold} */
      const held = {
        pointerId: event.pointerId,
        parent: found.parentElement,
        target: found,
        armed: false,
        timer: setTimeout(() => {
          if (hold !== held) return;
          // Held this long, the finger reads, wherever it is now: one that slid onto
          // the gap beside a neighbour reads the next it reaches.
          held.armed = true;
          if (held.target) show(held.target, "hold");
        }, DWELL),
      };
      hold = held;
    },
    { capture: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      if (hold?.pointerId !== event.pointerId) return;
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
      target.dispatchEvent(
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
      keying = false;
      point(null);
      quieten();
      endHold();
    }
  });
  document.addEventListener(
    "contextmenu",
    (event) => {
      if (hold?.armed) event.preventDefault();
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
