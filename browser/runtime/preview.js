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
     inside it, as a chart's point, which the preview stands above; `about` is what it
     is about, which it leaves in view as it does the box it stands by, as a margin
     entry's passage or a time's message; `excerpt` asks
     for the face's room for a block of the page; and `list` is items under the lines,
     `{items, more}`, as the threads standing at one place, of which the face shows as
     many as the room it is held to holds, and under them the words `more(count)` gives
     for the rest, as "and 26 more threads" (`fit`), where another preview's last line
     that fits ends in an ellipsis. When what it says changes under an aim
     that stays inside the element, as a chart's point, it says so (`previewChanged`,
     widget-upgrade.js), and a standing preview redraws in place, or a pointer resting
     on the element or a finger holding it reads it; a preview the user put away stays
     away, whatever the element declares, until they aim again. When its preview goes,
     whatever puts it away, the pointer or focus leaving, the press after a finger's
     hold, Escape or another target's taking its place, the element hears
     `lf-preview-ended` (`PREVIEW_ENDED`), a `CustomEvent` dispatched at it alone, whose
     `detail.route` is the route that read it, so a mark it drew for the reading, as a
     chart's ring on its point, comes off then. It returns null where it adds nothing,
     so the search goes on outward, and false where nothing shows and nothing around it
     may. A widget declares it with no import, as it declares `lfCommands` and
     `lfCopy()`, so off Leaf it reads nothing. What a declaration throws is reported and shows nothing.
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

   Where it stands is one decision (`stand`), made again whenever what it rests on may
   have changed, and drawn by the browser from that decision alone, with no fallback of
   its own to disagree with it. It is shown with an element as its source
   (`showPopover({source})`), whose box is its implicit anchor (`position-anchor:
   auto`): the target, or a range's line by the element holding the range, a declared
   box by the declaring element and a shape by its drawing's HTML host, each box at its
   offsets inside that element. So the browser carries it with the element through
   every scroll, a shadow tree's included, and this module decides again as its words
   or the box they stand by change, as a box holding the element scrolls, and as the
   window resizes or a pinch or an on-screen keyboard changes what it shows; a hover
   writes nothing on the target, which observers of the page's boxes would hear. Its
   side is the first that holds it whole inside the part of the window the user sees,
   leaves what it is about in view (the box it stands by and the declaration's
   `about`), and covers no other target, tested every 23 px across the box it will draw.
   Where it stands now comes first, its top corner on the edge it stands by at the same
   offsets from the box it stands by, so new words for the same target don't move it:
   it stays while it holds the preview whole and what it is about clear, and lets the
   pointer through to a target it has come to cover rather than move under the user's
   aim (browser/AGENTS.md, "The page holds still under the user's aim"). Then below,
   then above, from the box's start edge and then its end edge, so a right-to-left
   target's starts at its right edge; beside, toward the nearer window edge first; then
   centred across the window.
   A finger's and a point's try above first. A new aim, as a chart's next point
   (`previewChanged` with `aim`), tries no place first. Where every one covers a
   target, the first that holds it stands and takes no pointer, so the pointer reaches
   what it covers; where none holds it whole, the one with the most room stands and the
   preview fits its lines to that room. A target smaller than the grid's step can stand
   under it unseen: Leaf's own targets meet WCAG's least, 24 px, and no sampling proves
   an arbitrary target absent, so that is the grid's stated limit, as the holder's own
   box, which it doesn't test, is its bound on cost.

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
   - A finger held on a target for `HOLD`, or until the browser says the press is long
     (`contextmenu`) where that comes first, shows its preview, and the finger reads its
     neighbours by sliding onto them: one of the same parent shows its own instead. A
     hold is the touch form of pointing, so it reads and presses nothing, as a
     platform's long press follows no link and its tooltip clicks nothing: once the hold
     has shown a preview, the touch's end is cancelled (`touchend`), wherever the finger
     ends, so the browser makes no click of it, which would press the target and, as a
     click outside a hint popover, close the preview. The preview stands until the next
     press: a tap on its target, which presses, or a touch elsewhere or a finger's
     scroll, which put it away, as iOS's link preview does. A press let go before `HOLD`
     is a tap, which shows nothing and which the browser's click presses. A press with a
     modifier is not this gesture (`plainPress`). Touch capture is released at the press
     so the slide is heard over each neighbour, and a finger that starts scrolling ends
     the hold with `pointercancel`, which puts its preview away; a target that should
     not scroll from a press says so with `touch-action`. While a preview is held, the
     platform's long-press menu stays shut.
   - While a preview stands, by pointer or by focus, it is Escape's first step and the
     press does nothing else (keyboard/AGENTS.md, "Escape"): it covers what lies under
     it, so the user can put it away without moving the pointer or focus, and without
     losing the surface they are in (WCAG 1.4.13, "Content on Hover or Focus"). A second
     Escape takes the step the first would have. Off a served page, where the register
     holds no page scopes, the key listener takes the same step.

   Each pointer boundary costs the path it walks, the nodes under the pointer, and a
   preview showing costs what it reads, for a control the page's commands, and a few
   hit tests for its side, never the page's elements (root AGENTS.md,
   "Responsiveness"). The target a finger held wears `data-lf-held` while its preview
   stands, so its surface can keep it where the finger held it (margin-layout.js,
   `HELD`).

   Decisions: a pointer's dwell, 200 ms, hides a flicker as it crosses targets without
   holding the user up; the margin's labels waited 90 ms, the platform's tooltips about a
   second. A finger's is the platform's long press, 500 ms on iOS and Android, since a
   press let go sooner is a tap, which presses. Until 5 November 2026 a finger read after
   the pointer's 200 ms, and its release pressed the target it ended on and put the
   preview away. That rule was dropped because a finger couldn't read without acting
   short of sliding off before letting go, which on touch often scrolls instead: one
   that held a link to read where it went followed it as it let go, and one that held a
   thread's words opened the thread. A preview says its words whole, wrapping where
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
   box in the chrome copied onto a range's line or a declared box, which kept still as
   the box scrolling the target moved; `position-try-fallbacks` behind the side test,
   which drew another box than the one tested; a preview that scrolls, whose detail no
   key reached and a pointer passed through where it covered a target; and keeping the
   preview inside the box around its target, which only a script measuring that box
   could do, where the window's edge serves. */
import { html, nothing, render } from "/runtime/framework.js";
import {
  carryChromeStyles,
  closeNativeLayer,
  nativeLayers,
  openedThisInput,
  showNativeLayer,
} from "./keyboard/layer-stack.js";
import { controlKeys } from "./keyboard/control-keys.js";
import { advertisesKeys } from "./keyboard/bindings.js";
import { focused, onCurrentLocation, typesText } from "./focus.js";
import { pageScope } from "./keyboard/register.js";
import { offlineInteractive } from "./context.js";
import { watchPresentation, whenDocumentPresented } from "./semantic-state.js";
import { plainPress } from "./pointer.js";
import {
  isElement,
  isHTML,
  renderedParent,
  renderedUnder,
  under,
} from "./shadow-tree.js";
import { PREVIEW, PREVIEW_ENDED } from "./widget-upgrade.js";
import { keeps, layoutPx } from "./keeps.js";
import { nextRender, sizeObserver } from "./rendering.js";
import { atClock, clockNow } from "./presence.js";
import { watchOwner } from "./arrivals.js";
import { actionClass } from "./control-faces.js";
import { shownParts, shownWindow, visualViewport } from "./geometry.js";

/** @typedef {string | Node | import("/vendor/lit.js").TemplateResult} Word
 * @typedef {Word | readonly Word[]} Words
 * @typedef {readonly (readonly string[])[]} Presses
 * @typedef {Words | null | undefined | false} Line
 * @typedef {{items: readonly Words[], more: (count: number) => Words}} List
 * @typedef {{name?: Words | null, keys?: Presses, detail?: readonly Line[], list?: List | null, at?: Element | import("./rect.js").Box | null, about?: Element | null, excerpt?: boolean}} Preview
 * @typedef {Preview | null | undefined | false} Declared
 * @typedef {"pointer" | "focus" | "hold"} Route
 * @typedef {(route: Route) => Declared} Read
 * @typedef {{name: Words | null, keys: Presses, detail: Words[], list: List | null, at: Element | import("./rect.js").Box | null, about: Element | null, excerpt: boolean, restates: boolean}} Reading
 * @typedef {import("./rect.js").Box} Box
 * @typedef {Element | Range} Target
 * @typedef {{from: Target, target: Target, holder: Element, route: Route, read: Read | null, at: {x: number, y: number} | undefined, line?: number, reading: Reading, clock: number, stop: () => void, described: {el: Element, attribute: string | null, elements: readonly Element[] | null} | null}} Shown
 * @typedef {{pointerId: number, parent: Element | null, target: Element | null, armed: boolean, read: boolean, timer: ReturnType<typeof setTimeout>}} Hold */

const DWELL = 200;
const HOLD = 500;
const WARM = 400;

// The one element every preview draws in.
const tip = document.createElement("div");
tip.className = "lf-ui lf-preview";
tip.id = "lf-preview";
tip.setAttribute("popover", "hint");
tip.setAttribute("role", "tooltip");
// What it shows, which fades in inside the box the browser places: an anchored box that
// fades is placed again in every frame of the fade, as Chromium 156 lays out the page's
// root for it, a cost that grows with the page.
const body = document.createElement("div");
body.className = "lf-preview-face";
tip.append(body);
// The chrome's own box the preview stands in, wherever it stands, a modal dialog of the
// page's included, so the chrome's sheet dresses it and the margin's observer hears none
// of its writes (margin-layout.js, `SURFACES`). It takes no box of its own in the
// dialog's layout. Its mark is a sibling the preview moves around (`open`).
const stage = document.createElement("div");
stage.className = "lf-chrome";
stage.style.display = "contents";
const mark = document.createElement("span");
mark.hidden = true;
stage.append(mark, tip);
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

// A preview longer than the room it stands in shows the lines that fit: the block the room
// ends in keeps the lines the browser wraps it to that fit there, its last ending in an
// ellipsis (`data-lf-clamp`, a line clamp), and the blocks after it stay laid out, unseen
// and unheard (`visibility: hidden`), so what it shows changes nothing about its size.
// Where the room ends between two blocks, the one before ends in an ellipsis
// (`data-lf-cut`). A list's items go whole, and its count, at the foot in their place,
// says how many more there are in the words its declaration gives. No preview scrolls:
// what pressing its target opens says the rest. Each place is written once, with its
// final value, so the lines a past fit clamped are read as they lay out whole.
/** @param {Reading} reading */
function fit(reading) {
  const lines = /** @type {HTMLElement[]} */ ([
    ...body.querySelectorAll(":scope > .lf-preview-name, :scope > .lf-preview-detail"),
  ]);
  const more = /** @type {HTMLElement | null} */ (
    body.querySelector(":scope > .lf-preview-more")
  );
  const { list } = reading;
  const was = clampedNow();
  const extra = was ? was.scrollHeight - was.clientHeight : 0;
  const holding = was ? lines.findIndex((line) => line.contains(was)) : -1;
  // The blocks from the clamped one on read as much higher as its clamp holds back.
  const after = holding < 0 ? Infinity : holding;
  let end = Infinity;
  if (wholeHeight() > body.clientHeight + 1) {
    if (list && more) {
      // The count line measures before it says anything, its first words those for all
      // the items, the longest it can say.
      if (!more.textContent) render(list.more(list.items.length), more);
      end = more.getBoundingClientRect().top;
    } else
      end =
        body.getBoundingClientRect().bottom -
        parseFloat(getComputedStyle(body).paddingBlockEnd);
  }
  const over = lines.findIndex(
    (line, at) =>
      line.getBoundingClientRect().bottom + (at >= after ? extra : 0) > end + 0.5,
  );
  // The block the room ends in, cut by line where it holds words, not a list's item.
  /** @type {{el: HTMLElement, lines: number} | null} */
  let clamp = null;
  const block = lines[over];
  if (block && !block.classList.contains("lf-preview-item")) {
    const el = /** @type {HTMLElement} */ (
      block.querySelector(":scope > .lf-preview-word") ?? block
    );
    const top = el.getBoundingClientRect().top + (over > after ? extra : 0);
    const line = parseFloat(getComputedStyle(el).lineHeight);
    const whole = Math.round((el === was ? el.scrollHeight : el.offsetHeight) / line);
    const fits = Math.floor((end - top + 0.5) / line);
    if (fits < whole && (fits >= 1 || over === 0))
      clamp = { el, lines: Math.max(1, fits) };
  }
  const kept = over < 0 ? lines.length : clamp ? over + 1 : Math.max(1, over);
  if (was && was !== clamp?.el) {
    keeps(was, "data-lf-clamp", null);
    was.style.removeProperty("--lf-preview-lines");
  }
  if (clamp) {
    keeps(clamp.el, "data-lf-clamp", "");
    clamp.el.style.setProperty("--lf-preview-lines", String(clamp.lines));
  }
  lines.forEach((line, at) => {
    line.style.visibility = at < kept ? "" : "hidden";
    keeps(
      line,
      "data-lf-cut",
      !list && !clamp && at === kept - 1 && kept < lines.length ? "" : null,
    );
  });
  if (!list || !more) return;
  const hidden = lines.length - kept;
  if (hidden) render(list.more(Math.min(hidden, list.items.length)), more);
  more.style.visibility = hidden ? "" : "hidden";
}
// The block a past fit clamped to the lines that fit, if any.
const clampedNow = () =>
  /** @type {HTMLElement | null} */ (body.querySelector("[data-lf-clamp]"));
// The face's whole height, laid out unclamped and unheld, whatever room it was last held
// to: its drawn height where it is whole, which is fractional where scrollHeight rounds,
// and what a past fit's clamp holds back added in.
function wholeHeight() {
  const was = clampedNow();
  if (was) return body.scrollHeight + was.scrollHeight - was.clientHeight;
  return body.scrollHeight > body.clientHeight + 1
    ? body.scrollHeight
    : body.getBoundingClientRect().height;
}

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
    about: declared?.about ?? null,
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
// Whether the release just heard ended a hold that read, whose touch's end it cancels.
let spent = false;
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

// Show what `from` previews on `route`, and say whether one shows. It reads first, and
// only a new reading replaces the standing preview: an aim at what says nothing there,
// as empty space inside a chart, leaves it standing, as plain text does, and a preview
// shown `again` for what it stands for goes once that says nothing. Shown `again`, it
// draws what its target says now where it stands, with no fade.
/** @param {Target} from @param {Route} route @param {Read | null} [read] @param {{x: number, y: number}} [at] @param {boolean} [again] @param {boolean} [fresh] */
function show(from, route, read = null, at, again = false, fresh = false) {
  if (!again && shown?.from === from && shown.route === route) return true;
  const found = readFrom(from, route, read);
  const standing = again && shown?.from === from ? shown : null;
  if (!found) {
    if (standing) hide();
    return false;
  }
  // Ending the standing record's watch can run its disconnect, which hides whatever
  // `shown` names, so the record stops being the one shown first.
  if (standing) {
    shown = null;
    standing.stop();
    if (standing.target !== found.target) ended(standing);
  } else hide();
  const { target, holder, reading } = found;
  render(face(reading), body);
  /** @type {Shown} */
  const record = {
    from,
    target,
    holder,
    route,
    read,
    at,
    reading,
    clock: clockNow(),
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
  if (!stand(record, reading, Boolean(standing), Boolean(standing) && !fresh)) {
    hide();
    return false;
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

// Where a preview stands (`stand`), decided here, from the box the browser will draw,
// and drawn by the browser from that decision alone, with no fallback of its own. Its
// anchor is an element: the target or the declared element, a range's line by the element
// holding the range, and a declared box by the declaring element, each box held at its
// offsets inside its element, so the browser carries the preview with the element
// through every scroll and resize (`anchor()`, chrome.css). Its edges stand at offsets
// from that element's (`--lf-preview-{top,bottom,left,right}`), its top or its bottom and
// its left or its right, or, centred, at the left the window gives it, as its side says
// (`data-lf-y`, `data-lf-x`). Its side is the
// first of: where it stands now; below, then above, each from the box's start edge and
// then its end edge; beside, toward the nearer window edge and then the other; centred
// across the window below, then above; that holds the whole preview inside the part of
// the window the user sees and covers no other target, by a hit test every `REACH` across
// the box it would draw. A finger's and a point's try above first, since the finger
// covers what lies below and a point's axis stands under it. Where every one that holds
// it covers a target, the first stands and lets the pointer through to what it covers
// (`data-lf-covers`); where none holds it whole, the one with the most room stands, held
// to that room, and the preview fits its lines to it (`fit`).
const EDGE = 8;
const GAP = { line: 6, box: 11, hold: 27 };
const REACH = 23;

/** @param {Box} box @param {number} x @param {number} y */
const holds = (box, x, y) =>
  x >= box.left && x <= box.right && y >= box.top && y <= box.bottom;

// The nearest HTML element with a box of its own at or around `el`: a `display:
// contents` element's first shown part, and a shape in a drawing's HTML host.
/** @param {Element} el @returns {HTMLElement | null} */
function boxed(el) {
  for (let at = /** @type {Element | null} */ (el); at; at = renderedParent(at)) {
    if (!isHTML(at)) continue;
    const [part] = shownParts(at);
    if (isHTML(part)) return /** @type {HTMLElement} */ (part);
  }
  return null;
}

// A declared box at the offsets inside its element it was declared at, which the
// element carries as the page moves, so a decision made again later, as a scroll's,
// reads it where it stands then.
/** @type {WeakMap<Box, Box>} */
const declaredWithin = new WeakMap();
// What the preview stands by: its anchor element and the box inside it, in client
// coordinates, the anchor's own where it stands for itself.
/** @param {Shown} record @param {Reading} reading @returns {{source: HTMLElement, box: Box} | null} */
function anchorOf(record, reading) {
  const { target, holder, at } = record;
  if (target instanceof Range) {
    const lines = [...target.getClientRects()];
    // The line pointed at as it showed, which it stands by as the page moves after.
    record.line ??= Math.max(
      0,
      lines.findIndex((box) => at && holds(box, at.x, at.y)),
    );
    const line = lines[record.line] ?? lines[0];
    const common = target.commonAncestorContainer;
    const around = isElement(common) ? common : common.parentElement;
    const source = around && boxed(around);
    return line && source ? { source, box: line } : null;
  }
  const declared = reading.at;
  if (declared && !isElement(declared)) {
    const source = boxed(holder);
    if (!source) return null;
    const by = source.getBoundingClientRect();
    let within = declaredWithin.get(declared);
    if (!within)
      declaredWithin.set(
        declared,
        (within = {
          top: declared.top - by.top,
          right: by.right - declared.right,
          bottom: by.bottom - declared.bottom,
          left: declared.left - by.left,
        }),
      );
    return {
      source,
      box: {
        top: by.top + within.top,
        right: by.right - within.right,
        bottom: by.bottom - within.bottom,
        left: by.left + within.left,
      },
    };
  }
  const el = declared?.isConnected ? declared : holder;
  const source = boxed(el);
  if (!source) return null;
  return {
    source,
    box: (source === el || source.parentElement === el
      ? source
      : el
    ).getBoundingClientRect(),
  };
}

// The source the preview was last shown with, where it stood then, what it said, and
// which side of its stage's mark it stands on.
/** @type {Element | null} */
let anchored = null;
/** @type {Element | null} */
let seated = null;
let said = "";
let beforeMark = false;
// Stand the stage in the topmost modal dialog while one stands, else in the chrome, and
// say whether it moved.
function seat() {
  const modal = nativeLayers().findLast((layer) => layer.kind === "modal")?.root;
  const into = modal ?? home;
  if (!into || into === seated) return false;
  if (modal) carryChromeStyles(modal);
  into.append(stage);
  seated = into;
  beforeMark = false;
  return true;
}
// Show the preview by `source`. Firefox 157 stands a popover hidden and shown again by a
// new source in one task by the source it was last shown with, while nothing about the
// popover itself changed since, as its words (notes/browser-support.md). Any insertion
// lays it out again, so a new source that comes with the same words moves it to the
// other side of its mark, a change the page's watch of its writes reads as one.
/** @param {HTMLElement} source @param {boolean} standing @param {boolean} moved */
function open(source, standing, moved) {
  if (standing && source === anchored && !moved) return;
  if (standing) closeNativeLayer(tip);
  if (!moved && source !== anchored && tip.textContent === said) {
    beforeMark = !beforeMark;
    if (beforeMark) mark.before(tip);
    else mark.after(tip);
  }
  anchored = source;
  said = tip.textContent ?? "";
  showNativeLayer(tip, { source });
}

// The element the standing preview stands by, whose resizing reads it again, words and
// place (`refresh`), as the window's resizing does, since what a target previews may
// follow the width it is given. Its first reading, as observing it starts, is the size
// it was placed at, so it moves nothing. A scroll of a box holding it decides its place
// again (`replace`), heard at the document and at each shadow root around it, since a
// scroll inside a shadow tree is heard no further than its root.
/** @type {Element | null} */
let followed = null;
/** @type {{width: number, height: number} | null} */
let followedSize = null;
/** @type {ShadowRoot[]} */
let followedRoots = [];
const following = sizeObserver(
  (entries) => {
    const entry = entries.at(-1);
    if (!entry) return;
    const { width, height } = entry.contentRect;
    const was = followedSize;
    followedSize = { width, height };
    if (shown && was && (was.width !== width || was.height !== height)) refresh();
  },
  // A preview comes and goes for as long as the page plays.
  { counted: false },
);
/** @param {Element | null} source */
function follow(source) {
  if (source === followed) return;
  if (followed) following.unobserve(followed);
  for (const root of followedRoots) root.removeEventListener("scroll", scrolled, true);
  followed = source;
  followedSize = null;
  followedRoots = [];
  if (!source) return;
  following.observe(source);
  for (
    let root = source.getRootNode();
    root instanceof ShadowRoot;
    root = root.host.getRootNode()
  ) {
    root.addEventListener("scroll", scrolled, { capture: true, passive: true });
    followedRoots.push(root);
  }
}
/** @param {Event} event */
function scrolled(event) {
  const box = event.target;
  if (
    followed &&
    (box === document || (isElement(box) && renderedUnder(followed, box)))
  )
    replace();
}
// Decide the standing preview's place again in the next frame, once however many of its
// grounds changed in this one.
let replacing = 0;
function replace() {
  if (!shown || replacing) return;
  replacing = nextRender(() => {
    replacing = 0;
    if (shown) stand(shown, shown.reading, true, true);
  });
}

/** @typedef {{y: "below" | "above" | "top", x: "left" | "right" | "after" | "before" | "center", box: Box, room: number}} Placement */
// The target the standing preview stands for, the edge across it stands by, left or
// right, and its top corner on that edge as offsets from the box it stands by, which the
// next decision for that target tries first.
/** @type {{target: Target, x: "left" | "right", corner: {x: number, y: number}} | null} */
let placed = null;

/** @param {Box} a @param {Box} b */
const meets = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

// Stand the preview by its anchor, and say whether it stands: the one decision of where
// it stands, made `again` for the target it already stands for, which tries the place it
// stands at now first, and afresh for a new target or a new aim.
/** @param {Shown} record @param {Reading} reading @param {boolean} standing @param {boolean} again */
function stand(record, reading, standing, again) {
  const moved = seat();
  const anchor = anchorOf(record, reading);
  if (!anchor) return false;
  const { source, box } = anchor;
  const { target, holder, route } = record;
  const declared = reading.at;
  const point = Boolean(declared) && !isElement(declared);
  const gap =
    target instanceof Range ? GAP.line : route === "hold" ? GAP.hold : GAP.box;
  const rtl = getComputedStyle(holder).direction === "rtl";
  keeps(tip, "dir", rtl ? "rtl" : "ltr");
  open(source, standing, moved);
  follow(source);
  // The part of the window the user sees, which a pinch or an on-screen keyboard makes
  // smaller than the layout viewport, and which nothing the chrome covers takes from,
  // since the preview stands over all of it; its width bounds the preview's.
  const room = shownWindow({ gap: EDGE, item: tip });
  tip.style.setProperty("--lf-preview-span", layoutPx(room.width));
  const by = source.getBoundingClientRect();
  const width = tip.getBoundingClientRect().width;
  const height = wholeHeight();
  // What it is about stays in view: the box it stands by, and what its declaration
  // names (`about`), as a margin entry's passage or a time's message.
  const about = reading.about?.isConnected
    ? reading.about.getBoundingClientRect()
    : null;
  /** @param {Placement} at */
  const clear = (at) => !meets(at.box, box) && !(about && meets(at.box, about));
  /** @param {Placement} at */
  const inside = (at) =>
    at.box.left >= room.left - 0.5 &&
    at.box.right <= room.right + 0.5 &&
    at.box.top >= room.top - 0.5;
  /** @param {Placement["y"]} y */
  const rowRoom = (y) =>
    y === "below"
      ? room.bottom - (box.bottom + gap)
      : y === "above"
        ? box.top - gap - room.top
        : room.bottom - box.top;
  /** @param {Placement["x"]} x */
  const leftOf = (x) =>
    x === "left"
      ? box.left
      : x === "right"
        ? box.right - width
        : x === "after"
          ? box.right + gap
          : x === "before"
            ? box.left - gap - width
            : room.left + (room.width - width) / 2;
  /** @param {Placement["y"]} y @param {Placement["x"]} x @returns {Placement} */
  const placement = (y, x) => {
    const space = rowRoom(y);
    const tall = Math.min(height, Math.max(space, 0));
    const left = leftOf(x);
    const top =
      y === "below" ? box.bottom + gap : y === "above" ? box.top - gap - tall : box.top;
    return {
      y,
      x,
      box: { left, top, right: left + width, bottom: top + tall },
      room: space,
    };
  };
  const [start, end] = rtl
    ? /** @type {const} */ (["right", "left"])
    : /** @type {const} */ (["left", "right"]);
  /** @type {Placement[]} */
  const placements = [];
  // Where it stands now: its top corner on the edge it stands by at the same offsets
  // from the box it stands by.
  const was = again && placed?.target === target ? placed : null;
  /** @type {Placement | null} */
  let now = null;
  if (was) {
    const left =
      was.x === "right" ? box.right - was.corner.x - width : box.left + was.corner.x;
    const top = box.top + was.corner.y;
    now = {
      y: "top",
      x: was.x,
      box: { left, top, right: left + width, bottom: top + height },
      room: room.bottom - top,
    };
    placements.push(now);
  }
  /** @type {Placement["y"][]} */
  const rows = route === "hold" || point ? ["above", "below"] : ["below", "above"];
  placements.push(...rows.flatMap((y) => [placement(y, start), placement(y, end)]));
  if (!(target instanceof Range)) {
    const toward =
      box.left + box.right > room.left + room.right
        ? /** @type {const} */ (["after", "before"])
        : /** @type {const} */ (["before", "after"]);
    placements.push(...toward.map((x) => placement("top", x)));
  }
  placements.push(...rows.map((y) => placement(y, "center")));
  // Only where none keeps what it is about clear may it cover that.
  const clearOnes = placements.filter(clear);
  const pool = clearOnes.length ? clearOnes : placements;
  const whole = pool.filter((at) => inside(at) && at.room >= height);
  // Where it stands now holds while it holds it whole and what it is about clear, and
  // there it lets the pointer through to a target it has come to cover rather than move
  // under the user's aim; a fresh decision takes the first place that covers none.
  const stays = now && whole.includes(now) ? now : null;
  const uncovered = stays ? null : whole.find((at) => !covers(at.box, holder));
  const chosen =
    stays ??
    uncovered ??
    whole[0] ??
    pool
      .filter(inside)
      .reduce(
        (most, at) => (!most || at.room > most.room ? at : most),
        /** @type {Placement | null} */ (null),
      ) ??
    placement(rows[0] ?? "below", "center");
  const free = chosen === uncovered || !covers(chosen.box, holder);
  // Its edges at their offsets from the element it stands by: its top, or, above, its
  // bottom, and its left, or its right where it stands from the box's right edge; centred,
  // its left stands where the window puts it, whatever the element does across.
  const edges = {
    top: chosen.box.top - by.top,
    bottom: chosen.box.bottom - by.top,
    left: chosen.box.left - (chosen.x === "center" ? 0 : by.left),
    right: by.right - chosen.box.right,
  };
  for (const [edge, length] of Object.entries(edges))
    tip.style.setProperty(`--lf-preview-${edge}`, layoutPx(length));
  const right = chosen.x === "right" || chosen.x === "before";
  placed = {
    target,
    x: right ? "right" : "left",
    corner: {
      x: right ? box.right - chosen.box.right : chosen.box.left - box.left,
      y: chosen.box.top - box.top,
    },
  };
  keeps(tip, "data-lf-y", chosen.y);
  keeps(tip, "data-lf-x", chosen.x);
  tip.style.setProperty(
    "--lf-preview-room",
    chosen.room >= height ? "none" : layoutPx(Math.max(chosen.room, 0)),
  );
  keeps(tip, "data-lf-covers", free ? null : "");
  fit(reading);
  return true;
}
// Whether a preview drawn in `at` covers a target other than `holder`: a hit test every
// `REACH` across it, through the preview where it stands now. A target too small to hold
// a test point is smaller than any Leaf asks a pointer to reach, WCAG's least, 24 px; an
// author's smaller one can stand unseen between the points, since no sampling proves a
// target absent, which is the grid's limit. A point inside the holder's own box finds the
// holder or what it holds, which are no other target, so it is not tested, as most of a
// preview standing over a chart is not, which bounds its cost.
/** @param {Box} at @param {Element} holder */
function covers(at, holder) {
  const own = holder.getBoundingClientRect();
  /** @param {number} from @param {number} to */
  const steps = (from, to) => {
    const count = Math.max(1, Math.ceil((to - from - 2) / REACH));
    return Array.from(
      { length: count + 1 },
      (_, n) => from + 1 + ((to - from - 2) * n) / count,
    );
  };
  for (const y of steps(at.top, at.bottom))
    for (const x of steps(at.left, at.right)) {
      if (holds(own, x, y)) continue;
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
  follow(null);
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
// it after the dwell, unless the user put its preview away. Focus on it opens none for
// a redraw. Where the user aimed at something new inside it (`aim`), as a chart's next
// point, the aim is a new target: whatever put the last preview away, the route reading
// the element shows it, focus included.
// What changed is the element that supplied the reading, its owner, which may stand
// around what the route aims at, as a widget declares for the control in it that holds
// focus.
/** @param {Element} node @param {boolean} aim */
function changed(node, aim) {
  /** @param {Target | null | undefined} at */
  const within = (at) => isElement(at) && renderedUnder(at, node);
  if (aim && within(quiet)) quiet = null;
  if (shown && (shown.target === node || shown.from === node)) {
    show(shown.from, shown.route, shown.read, shown.at, true, aim);
    return;
  }
  const on = focused();
  if (hold?.armed) {
    if (within(hold.target)) show(/** @type {Element} */ (hold.target), "hold");
    else if (!hold.target && hold.parent === node.parentElement) {
      hold.target = node;
      show(node, "hold");
    }
  } else if (aim && on && within(on)) showFocus(on);
  else if (beneath && under(beneath, node) && !within(quiet)) {
    pointing = null;
    point(node);
  }
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
// stands, with no fade, and words that came back the same leave it as it is. It is read
// at the moment it first showed (presence.js, `atClock`), so a presentation whose only
// change is the clock, as a later state read's, ages nothing it says. A preview whose
// target now says nothing goes.
function refresh() {
  const record = shown;
  if (!record) return;
  const found = atClock(record.clock, () =>
    readFrom(record.from, record.route, record.read),
  );
  if (!found) return hide();
  if (found.target !== record.target)
    return void show(record.from, record.route, record.read, record.at, true, true);
  render(face(found.reading), body);
  record.reading = found.reading;
  stand(record, found.reading, true, true);
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
  window.addEventListener("resize", () => shown && refresh(), { passive: true });
  document.addEventListener("scroll", scrolled, { capture: true, passive: true });
  visualViewport.addEventListener("resize", replace, { passive: true });
  visualViewport.addEventListener("scroll", replace, { passive: true });

  document.addEventListener(
    PREVIEW,
    (event) => {
      const [node] = event.composedPath();
      if (isElement(node))
        changed(node, Boolean(/** @type {CustomEvent} */ (event).detail?.aim));
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
  // not one into a surface that opened since the user's last input, which is the
  // surface placing them as it opens (layer-stack.js, `openedThisInput`).
  onCurrentLocation((node, cause) => {
    quiet = null;
    if (shown?.route === "focus" && shown.from !== node) hide();
    if (node && (cause === "step" || (cause === "move" && !openedThisInput(node))))
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
      spent = false;
      if (shown?.route === "hold") hide();
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
        read: false,
        timer: setTimeout(() => arm(held), HOLD),
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
      if (neighbour && show(neighbour, "hold")) hold.read = true;
      else hide();
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointerup",
    (event) => {
      if (hold?.pointerId !== event.pointerId) return;
      spent = hold.read;
      endHold();
    },
    { capture: true },
  );
  document.addEventListener(
    "touchend",
    (event) => {
      if (!spent) return;
      spent = false;
      // One the browser won't let be cancelled ended a touch that moved, of which it
      // makes no click.
      if (event.cancelable) event.preventDefault();
    },
    { capture: true, passive: false },
  );
  document.addEventListener(
    "pointercancel",
    (event) => {
      if (hold?.pointerId !== event.pointerId) return;
      endHold();
      if (shown?.route === "hold") hide();
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
      if (hold) arm(hold);
      // Only while a held preview shows: a hold over a target that showed none, as an
      // external link, keeps the platform's own long-press menu.
      if (hold?.armed && shown?.route === "hold") event.preventDefault();
    },
    { capture: true },
  );
}

// Held for `HOLD`, or once the browser calls the press long, the finger reads, wherever
// it is now: one that slid onto the gap beside a neighbour reads the next it reaches.
/** @param {Hold} held */
function arm(held) {
  if (hold !== held || held.armed) return;
  clearTimeout(held.timer);
  held.armed = true;
  if (held.target && show(held.target, "hold")) held.read = true;
}

// The hold ends with its release, and what it read stands until the next press.
function endHold() {
  if (!hold) return;
  clearTimeout(hold.timer);
  hold = null;
}
