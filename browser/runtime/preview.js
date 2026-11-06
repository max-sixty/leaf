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
     and left as they are where they come back the same: `{name, keys, detail, list,
     at, excerpt}`, every field optional (module-input.md, "Previews"). On a control its
     lines stand under the control's own name and keys, and its name replaces the
     accessible name where that says more than the face should; `at` is where to stand,
     the declaring element by default, another element or a box in client coordinates
     inside it, as a chart's point, which the preview stands above; `excerpt` asks
     for the face's room for a block of the page; and `list` is items under the lines,
     `{items, more}`, as the threads standing at one place, of which the face shows as
     many as the room it is held to holds, and under them the words `more(count)` gives
     for the rest, as "and 26 more threads" (`fitList`), where another preview's face
     scrolls. When what it says changes under an aim
     that stays inside the element, as a chart's point, it says so (`previewChanged`,
     widget-upgrade.js), and a standing preview redraws in place, or a pointer resting
     on the element or a finger holding it reads it; a preview the user put away stays
     away, whatever the element declares, until they aim again. When its preview goes,
     whatever puts it away, the pointer or focus leaving, a finger lifting, Escape or
     another target's taking its place, the element hears `lf-preview-ended`
     (`PREVIEW_ENDED`), a `CustomEvent` dispatched at it alone, whose `detail.route` is
     the route that read it, so a mark it drew for the reading, as a chart's ring on its
     point, comes off then. It returns null where it adds nothing, so the search goes on
     outward, and false where nothing shows and nothing around it may. A widget declares
     it with no import, as it declares `lfCommands` and `lfCopy()`, so off Leaf it reads
     nothing. What a declaration throws is reported and shows nothing.
   - A `title` is its writer's, and the browser shows it to a pointer: over an element
     the browser's tooltip speaks for, its own title or one around it, a pointer reads
     no preview, so no second tooltip stands beside the browser's. Focus and a finger,
     which the browser's tooltip never reaches, read its words as a line under the
     element's name, or as its name where it has none. Nothing here writes or removes a
     title, so it says what its writer last wrote and names what it names. Leaf's own
     controls declare their words as `lfPreview` and write no title on Leaf (the
     portable writers, element-markers.js and control-labels.js, write one off Leaf,
     where the browser's tooltip is the only reading).
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
   the top layer, so it stands over an open popover around its target, and a hint
   closes no popover the user opened. While a modal dialog stands, it stands inside the
   topmost one, since a modal makes everything outside it inert, a top-layer popover
   too, and the pointer couldn't reach a preview there. It holds no control, so it is
   no layer the keyboard tiers its scopes over (layer-stack.js). A pointer's preview
   takes the pointer, so the pointer can cross from the target onto it and read it
   there; leaving it puts it away after a dwell, and reaching another target from it
   shows that one at once (WCAG 1.4.13, "Hoverable").

   The browser places it (`stand`): it is shown with its target as its source
   (`showPopover({source})`), whose box is its implicit anchor (`position-anchor:
   auto`), and controls.css stands it there in logical terms (`position-area`), with
   the fallbacks that keep it inside the window (`position-try-fallbacks`). So it
   follows its target through every scroll and resize, a shadow tree's included, a
   right-to-left target's starts at its right edge, and a hover writes nothing on the
   target, which observers of the page's boxes would hear. A target with no HTML box of
   its own, as a range's line, a declared box or a shape in a drawing, is stood for by
   the place (`.lf-preview-place`), a box in the chrome this module moves onto it as it
   shows, which scrolls with the page but not with a box scrolling inside it, and stays
   where it was as the window resizes, a rare move under a resting aim. Which side it
   stands on is this module's, measured as it shows: below by the gap that clears a
   focus ring, or above, or beside toward the nearer window edge, the first where it
   fits the window and covers no other target, a few hit tests across the room each
   side offers, so in a column of targets or a grid of them the pointer reaches each
   neighbour; above first for a finger, which covers what lies below, and for a point
   inside its target. Where every side covers a target, it stands below and takes no
   pointer, so the pointer reaches what it covers.

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
     once, with no fade, where the user moved it there, as whoever moved it says: a Tab
     or Shift+Tab, or a placement standing in for one (`step`), and a move to a place
     (`move`), as a walk lands, the `m` walk onto a margin card's message among them: the
     cause its mover gives (focus.js, `focusDestination`). Leaving the target hides it.
     Focus a surface places as it opens, as the Page Map's first row, and focus handed
     back as a surface closes or as Escape backs the user out (`return`) show nothing:
     the user is opening or backing out, and a preview there would take their next
     Escape. A declaration
     that stops being true, as a grip's once its card is grabbed, says so
     (`previewChanged`), which redraws a preview standing on focus and opens none.
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
   preview showing costs what it reads, for a control the page's commands, and a few
   hit tests for its side, never the page's elements (root AGENTS.md,
   "Responsiveness"). The target a finger holds wears `data-lf-held` while the preview
   stands, so its surface can keep it where the finger is (margin-layout.js, `HELD`).

   Decisions: one dwell for the pointer and the finger, 200 ms, hides a flicker as either
   crosses targets without holding the user up; the margin's labels waited 90 ms, the
   platform's tooltips about a second. A preview says its words whole, wrapping where
   they run long, where a margin entry's label cut its question to one line. It finds its
   neighbours by a few hit tests in the room it would take, where the margin's labels
   each measured every entry on the page to stand clear of them, a page-wide read on
   every hover. Until 5 November 2026 a preview took no pointer, so a covered neighbour
   took the pointer through it but the pointer couldn't stay on the preview to read it,
   and Escape put a preview away and took its own step too, which closed the thread
   card the user was reading, since the preview covers its first line. Until that day
   it also took a title off its element as the pointer came, to read it on every route
   with no second tooltip beside it, which kept words a writer had since removed and
   left a control its title named unnamed. Rejected: `interestfor`, which gives a
   control the same three routes natively but ships only in Chromium; the platform's
   `title` alone for Leaf's controls, which no finger or keyboard reads and which can't
   draw a key chip; holding a `title` off only while the pointer rests within its
   element and putting it back as the pointer leaves, which writes it twice a hover,
   each a change of the element's description a screen reader hears; naming the target
   as an anchor, which writes its style, so the margin laid out again the first time
   each paragraph previewed; insets measured from the box that scrolls the target, which
   lost the target as it moved inside that box and stood by the layout viewport; a
   script moving the place as the page scrolls, which trails each scroll by a frame and
   which Firefox warns of as a scroll-linked effect; and
   keeping the preview inside the box around its target, which only a script measuring
   that box could do, where the window's edge serves. */
import { html, nothing, render } from "/runtime/framework.js";
import {
  carryChromeStyles,
  closeNativeLayer,
  nativeLayers,
  showNativeLayer,
} from "./keyboard/layer-stack.js";
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
  isElement,
  isHTML,
  isNativeLayer,
  renderedParent,
  renderedUnder,
  under,
} from "./shadow-tree.js";
import { PREVIEW, PREVIEW_ENDED } from "./widget-upgrade.js";
import { keeps, layoutPx } from "./keeps.js";
import { sizeObserver } from "./rendering.js";
import { watchOwner } from "./arrivals.js";
import { actionClass } from "./control-faces.js";
import { shownParts } from "./geometry.js";

/** @typedef {string | Node | import("/vendor/lit.js").TemplateResult} Word
 * @typedef {Word | readonly Word[]} Words
 * @typedef {readonly (readonly string[])[]} Presses
 * @typedef {Words | null | undefined | false} Line
 * @typedef {{items: readonly Words[], more: (count: number) => Words}} List
 * @typedef {{name?: Words | null, keys?: Presses, detail?: readonly Line[], list?: List | null, at?: Element | import("./rect.js").Box | null, excerpt?: boolean}} Preview
 * @typedef {Preview | null | undefined | false} Declared
 * @typedef {"pointer" | "focus" | "hold"} Route
 * @typedef {(route: Route) => Declared} Read
 * @typedef {{name: Words | null, keys: Presses, detail: Words[], list: List | null, at: Element | import("./rect.js").Box | null, excerpt: boolean, restates: boolean}} Reading
 * @typedef {import("./rect.js").Box} Box
 * @typedef {Element | Range} Target
 * @typedef {{from: Target, target: Target, holder: Element, route: Route, read: Read | null, at: {x: number, y: number} | undefined, stop: () => void, described: {el: Element, attribute: string | null, elements: readonly Element[] | null} | null}} Shown
 * @typedef {{pointerId: number, parent: Element | null, target: Element | null, armed: boolean, timer: ReturnType<typeof setTimeout>}} Hold */

const DWELL = 200;
const WARM = 400;

// The one element every preview draws in.
const tip = document.createElement("div");
tip.className = "lf-ui lf-preview";
tip.id = "lf-preview";
tip.setAttribute("popover", "hint");
tip.setAttribute("role", "tooltip");
// What stands for a target with no HTML box of its own as the preview's source.
const place = document.createElement("div");
place.className = "lf-preview-place";
// The chrome's own box the two stand in, wherever it stands, a modal dialog of the
// page's included, so the chrome's guard and rules dress them and the margin's observer
// hears none of their writes (margin-layout.js, `SURFACES`). It takes no box of its own
// in the dialog's layout.
const stage = document.createElement("div");
stage.className = "lf-chrome";
stage.style.display = "contents";
stage.append(place, tip);
// The chrome the preview stands in when no modal dialog does.
/** @type {Element | null} */
let home = null;

// The one face: the name with each press as key chips, then each line of detail.
const chip = (/** @type {string} */ step) =>
  html`<kbd class="lf-key-badge">${step}</kbd>`;
const chips = (/** @type {readonly string[]} */ steps) =>
  html`<span class="lf-preview-keys">${steps.map(chip)}</span>`;
const detailLine = (/** @type {Words} */ line) =>
  html`<span class="lf-preview-detail">${line}</span>`;
const item = (/** @type {Words} */ line) =>
  html`<span class="lf-preview-detail lf-preview-item">${line}</span>`;
/** @type {(reading: Reading) => unknown[]} */
const face = ({ name, keys, detail, list }) => [
  name || keys.length
    ? html`<span class="lf-preview-name"
        ><span class="lf-preview-word">${name}</span>${keys.map(chips)}</span
      >`
    : nothing,
  ...detail.map(detailLine),
  ...(list
    ? [...list.items.map(item), html`<span class="lf-preview-more"></span>`]
    : []),
];

// A list longer than the room its face is held to shows the items that fit and, in
// their place below, the words its declaration gives for how many more there are. The
// rest stay laid out, unseen and unheard (`visibility: hidden`), so what the face
// shows changes nothing about its size, and the browser's choice of where it stands,
// which a shorter face could change, holds; a resize the face's bound follows fits it
// again (`fitting`). Each fit reads the face's items, a few at one place.
/** @type {List | null} */
let listing = null;
/** @param {List | null} list */
function fitList(list) {
  listing = list;
  if (!list) return;
  const items = /** @type {HTMLElement[]} */ ([
    ...tip.querySelectorAll(".lf-preview-item"),
  ]);
  const more = /** @type {HTMLElement | null} */ (
    tip.querySelector(".lf-preview-more")
  );
  if (!more) return;
  // Each place is written once, with its final value: the count line stands laid out
  // and unseen, so it measures before it says anything, its first words those for all
  // the items, the longest it can say.
  let fit = items.length;
  if (tip.scrollHeight > tip.clientHeight + 1) {
    if (!more.textContent) render(list.more(items.length), more);
    const end = more.getBoundingClientRect().top;
    const over = items.findIndex((line) => line.getBoundingClientRect().bottom > end);
    if (over >= 0) fit = over;
  }
  items.forEach((line, at) => {
    line.style.visibility = at < fit ? "" : "hidden";
  });
  if (fit < items.length) render(list.more(items.length - fit), more);
  more.style.visibility = fit < items.length ? "" : "hidden";
}
// The face's box, which a resize of the room it is held to changes, fits its list again.
const fitting = sizeObserver(
  () => {
    if (shown && listing) fitList(listing);
  },
  // A preview comes and goes for as long as the page plays.
  { counted: false },
);
fitting.observe(tip);

const CONTROL = 'button, summary, a[href], [role="button"], [data-lf-offer]';
// A proxy stands in for what the pointer takes by itself (control-faces.js, `proxy`),
// so what it stands for previews: a gloss's proxy, its phrase.
const PROXY = `.${actionClass("proxy")}`;

// The words a `title` gives `el`. A frame's title is its accessible name, not words a
// tooltip shows.
/** @param {Element} el */
const titleOf = (el) =>
  el.localName === "iframe" ? null : el.getAttribute("title") || null;
// Whether the browser shows its own tooltip over the innermost node of `path`: the
// nearest element along it with a title says, and an empty one says none.
/** @param {Iterable<EventTarget>} path */
function tooltipped(path) {
  for (const node of path)
    if (isElement(node) && node.hasAttribute("title")) return Boolean(titleOf(node));
  return false;
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
  Boolean(titleOf(node)) ||
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
  const list = declared?.list?.items.length ? declared.list : null;
  if (!name && !keys.length && !list) return null;
  return {
    name,
    keys,
    detail,
    at: declared?.at ?? null,
    excerpt: Boolean(declared?.excerpt),
    list,
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
// The target whose preview a press, a key or Escape put away, quiet until the user aims
// again: the pointer reaches a target, focus arrives or a keyboard walk lands, or a
// finger holds. What a widget declares again, as it redraws with the same reading,
// is no aim of the user's.
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
    if (standing.target !== found?.target) ended(standing);
  } else hide();
  if (!found) return false;
  const { target, holder, reading } = found;
  render(face(reading), tip);
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
  keeps(tip, "data-lf-list", reading.list ? "" : null);
  if (route === "hold") keeps(holder, "data-lf-held", "");
  if (!stand(record, reading, Boolean(standing))) {
    hide();
    return false;
  }
  fitList(reading.list);
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

// Where a preview stands (`stand`). The browser stands it by its source in logical
// terms, keeps it inside the window and carries it through every scroll and resize
// (controls.css); this module picks the source and the side. The source is the box it
// previews: a declared element or the target, or, where that is no HTML box with a box
// of its own, as a range's line under the pointer, a declared box or a shape in a
// drawing, the place moved onto that box. The side is the first of below, above, and
// beside toward the nearer window edge, then the other edge, where the preview fits the
// window and covers no other target; above first for a finger and for a point inside
// its target. Where every side covers one, it stands below and the pointer passes
// through it to what it covers.
const EDGE = 8;
const GAP = { line: 6, box: 11, hold: 27 };
tip.style.setProperty("--lf-preview-edge", `${EDGE}px`);

/** @param {Box} box @param {number} x @param {number} y */
const holds = (box, x, y) =>
  x >= box.left && x <= box.right && y >= box.top && y <= box.bottom;

// The place, moved onto `box`, in client coordinates, as offsets from the box that
// holds it: the chrome's, at the document's origin, so it scrolls with the page, or a
// modal dialog's.
/** @param {Box} box */
function placeAt(box) {
  const holder = place.offsetParent ?? document.documentElement;
  const by = holder.getBoundingClientRect();
  place.style.width = layoutPx(box.right - box.left);
  place.style.height = layoutPx(box.bottom - box.top);
  place.style.left = layoutPx(
    box.left - by.left - holder.clientLeft + holder.scrollLeft,
  );
  place.style.top = layoutPx(box.top - by.top - holder.clientTop + holder.scrollTop);
  return place;
}

/** @param {Shown} record @param {Reading} reading @returns {HTMLElement | null} */
function sourceOf(record, reading) {
  const { target, holder, at } = record;
  if (target instanceof Range) {
    const lines = [...target.getClientRects()];
    const line = lines.find((box) => at && holds(box, at.x, at.y)) ?? lines[0];
    return line ? placeAt(line) : null;
  }
  const declared = reading.at;
  if (declared && !isElement(declared)) return placeAt(declared);
  const el = declared?.isConnected ? declared : holder;
  // A `display: contents` box stands by its first shown part.
  const [part] = shownParts(el);
  if (isHTML(part)) return /** @type {HTMLElement} */ (part);
  return placeAt(el.getBoundingClientRect());
}

// The source the preview was last shown with, where it stood then, what it said, and
// which side of the place it stands on among its seat's children.
/** @type {Element | null} */
let anchored = null;
/** @type {Element | null} */
let seated = null;
let said = "";
let beforePlace = false;
// Stand the stage in the topmost modal dialog while one stands, else in the chrome, and
// say whether it moved.
function seat() {
  const modal = nativeLayers().findLast((layer) => layer.kind === "modal")?.root;
  const into = modal ?? home;
  if (!into || into === seated) return false;
  if (modal) carryChromeStyles(modal);
  into.append(stage);
  seated = into;
  beforePlace = false;
  return true;
}
// Show the preview by `source`. Firefox 157 stands a popover shown by a new source by the
// source it was last shown with while nothing about the popover itself changed since,
// as its words (notes/browser-support.md), and any insertion lays it out again, so a new
// source that comes with the same words moves it to the place's other side, a change
// the page's watch of its writes reads as one.
/** @param {HTMLElement} source @param {boolean} standing @param {boolean} moved */
function open(source, standing, moved) {
  if (standing && source === anchored && !moved) return;
  if (standing) closeNativeLayer(tip);
  if (!moved && source !== anchored && tip.textContent === said) {
    beforePlace = !beforePlace;
    if (beforePlace) place.before(tip);
    else place.after(tip);
  }
  anchored = source;
  said = tip.textContent ?? "";
  showNativeLayer(tip, { source });
}

// Stand the preview by its source on its side, and say whether it stands.
/** @param {Shown} record @param {Reading} reading @param {boolean} standing */
function stand(record, reading, standing) {
  const moved = seat();
  const source = sourceOf(record, reading);
  if (!source) return false;
  const { target, holder, route } = record;
  const declared = reading.at;
  const point = Boolean(declared) && !isElement(declared);
  const gap =
    target instanceof Range ? GAP.line : route === "hold" ? GAP.hold : GAP.box;
  keeps(tip, "dir", getComputedStyle(holder).direction === "rtl" ? "rtl" : "ltr");
  tip.style.setProperty("--lf-preview-gap", `${gap}px`);
  open(source, standing, moved);
  const box = source.getBoundingClientRect();
  const { width, height } = tip.getBoundingClientRect();
  const room = { width: document.documentElement.clientWidth, height: innerHeight };
  const rtl = tip.dir === "rtl";
  const start = Math.max(
    EDGE,
    Math.min(rtl ? box.right - width : box.left, room.width - EDGE - width),
  );
  /** @type {[string, Box][]} */
  const rooms = [
    [
      "below",
      {
        left: start,
        top: box.bottom + gap,
        right: start + width,
        bottom: box.bottom + gap + height,
      },
    ],
    [
      "above",
      {
        left: start,
        top: box.top - gap - height,
        right: start + width,
        bottom: box.top - gap,
      },
    ],
  ];
  if (route === "hold" || point) rooms.reverse();
  // Beside it, the side toward the nearer window edge first, named in logical terms:
  // the right is the inline end of a left-to-right target.
  if (!(target instanceof Range)) {
    /** @type {[string, Box]} */
    const right = [
      rtl ? "start" : "end",
      {
        left: box.right + gap,
        top: box.top,
        right: box.right + gap + width,
        bottom: box.top + height,
      },
    ];
    /** @type {[string, Box]} */
    const left = [
      rtl ? "end" : "start",
      {
        left: box.left - gap - width,
        top: box.top,
        right: box.left - gap,
        bottom: box.top + height,
      },
    ];
    rooms.push(...(box.left + box.right > room.width ? [right, left] : [left, right]));
  }
  /** @param {Box} at */
  const fits = (at) =>
    at.left >= EDGE &&
    at.top >= EDGE &&
    at.right <= room.width - EDGE &&
    at.bottom <= room.height - EDGE;
  const free = rooms.find(([, at]) => fits(at) && !covers(at, holder));
  const [side = "below"] = free ?? rooms[0] ?? [];
  keeps(tip, "data-lf-side", side);
  keeps(tip, "data-lf-covers", free ? null : "");
  return true;
}
// Whether a preview standing in `at` covers a target other than `holder`, by a few hit
// tests across it, through the preview where it stands now.
/** @param {Box} at @param {Element} holder */
function covers(at, holder) {
  for (const y of [at.top + 4, at.bottom - 4])
    for (const x of [at.left + 4, (at.left + at.right) / 2, at.right - 4]) {
      let hit =
        document.elementsFromPoint(x, y).find((el) => !tip.contains(el)) ?? null;
      for (
        let inner = hit?.shadowRoot?.elementFromPoint(x, y);
        hit && inner && inner !== hit;
        inner = hit.shadowRoot?.elementFromPoint(x, y)
      )
        hit = inner;
      const found = hit && candidate(climb(hit));
      if (found && !renderedUnder(found, holder) && !renderedUnder(holder, found))
        return true;
    }
  return false;
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
  ended(record);
}
// The element whose preview `record` read hears that it ended (`PREVIEW_ENDED`), with
// the route that read it, as a chart that drew a mark for the point it read takes the
// mark off. A range's owner knows its own.
/** @param {Shown} record */
function ended(record) {
  if (isElement(record.target))
    record.target.dispatchEvent(
      new CustomEvent(PREVIEW_ENDED, { detail: { route: record.route } }),
    );
}

// The pointer's target changed: start its dwell, or show it at once while warm. A
// pointer that leaves its target for nothing, as on its way onto the preview, puts the
// preview away only after a dwell, which its reaching the preview or the target cancels;
// one that reaches another target shows that one at once.
/** @param {Target | null} target @param {Read | null} [read] @param {{x: number, y: number}} [at] */
function point(target, read = null, at) {
  if (target === pointing) return;
  clearTimeout(leaving);
  // The pointer reaching another target, or leaving one, is an aim of its own.
  quiet = null;
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
  if (!target) return;
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
 * innermost and wins, as it does for the keyboard and a finger.
 * @param {Range | null} range @param {Read} [read] @param {{x: number, y: number}} [at] */
export function pointRange(range, read, at) {
  if (range) {
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

// What `node` previews changed (`previewChanged`): a preview standing for it reads it
// again where it stands, with no dwell and no fade, or goes where it now says nothing;
// otherwise a finger holding it or one beside it reads it, and a pointer resting over
// it after the dwell, unless the user put its preview away. Focus on it opens none:
// only the user's own move there does (`showFocus`).
/** @param {Element} node */
function changed(node) {
  if (shown && shown.from === node) {
    show(node, shown.route, null, undefined, true);
    return;
  }
  if (hold?.armed) {
    if (hold.target === node || (!hold.target && hold.parent === node.parentElement)) {
      hold.target = node;
      show(node, "hold");
    }
  } else if (beneath && under(beneath, node) && quiet !== node) {
    pointing = null;
    point(node);
  }
}

// Whether focus moving from `left` to `node` enters a surface it wasn't in, a native
// layer or a dialog, which is the surface placing the user as it opens.
/** @param {Element} node @param {Element | null} left */
function entersSurface(node, left) {
  for (let at = /** @type {Element | null} */ (node); at; at = renderedParent(at))
    if (isNativeLayer(at) || at.getAttribute("role") === "dialog")
      return !(left && renderedUnder(left, at));
  return false;
}
// Focus the user moved to `node` shows its preview once the task that moved it has
// done, which may be opening a popover the platform lets no other open inside, where
// the browser shows that focus, and not where they put this preview away.
/** @param {Element} node */
const showFocus = (node) =>
  queueMicrotask(() => {
    if (focused() !== node || !node.matches(":focus-visible")) return;
    if (shown?.from !== node) show(node, "focus");
  });

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
  if (tip.textContent !== before) stand(record, found.reading, true);
  fitList(found.reading.list);
}
let refreshing = false;

/** @param {HTMLElement} chrome */
export function mountPreviews(chrome) {
  home = chrome;
  chrome.append(stage);
  seated = chrome;
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
      // Something that arrives under a pointer the user hasn't moved takes it, but
      // shows nothing: the user pointed at what was there before. A pointer carrying a
      // press, as a drag does, is acting, not reading. Where the browser shows a title's
      // tooltip, the pointer reads nothing more.
      const still = event.clientX === rest.x && event.clientY === rest.y;
      rest = { x: event.clientX, y: event.clientY };
      const found = tooltipped(path) ? null : candidate(path);
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
  // focus leaving takes its preview along. It shows where the user moved it, as whoever
  // moved it says (focus.js, `focusDestination`): a Tab, Shift+Tab or a placement
  // standing in for one (`step`), and a move to a place, as a walk lands (`move`), but
  // not one that enters a surface as it opens.
  onCurrentLocation((node, cause, left) => {
    quiet = null;
    if (shown?.route === "focus" && shown.from !== node) hide();
    if (node && (cause === "step" || (cause === "move" && !entersSurface(node, left))))
      showFocus(node);
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
      if (event.key === "Escape") {
        if (offlineInteractive) quieten();
      } else if (shown?.route === "pointer" || !shown) quieten();
    },
    { capture: true },
  );
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
