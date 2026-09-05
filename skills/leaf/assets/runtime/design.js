/* This module owns layer-review (design) mode, its targets, and legend geometry. */
import { documentPoint, shownRect } from "./geometry.js";
import { el, WORKS } from "./widget-elements.js";
import { closePreview, marginTargetAt } from "./living-margin.js";
import { banner } from "./banner.js";
import { tabStore } from "./storage.js";
import { announce } from "./notifications.js";
import { syncGeneral } from "./conversation/panel.js";
import { isItem, ITEM, itemAt, itemWord, pageShifted, refreshAim } from "./anchors.js";
import { paintHere } from "./keyboard/scopes.js";
import { closestAcross, containsAcross, cut, inChrome, layerPart } from "./passages.js";
import { tagsDeclaring } from "./registry.js";
import { showFab } from "./composing/surface.js";
import { openComposer } from "./composing/selection.js";

// The name of what the pointer is over in design mode, floated at its corner. Chrome
// nothing presses (pointer-events none, in the stylesheet); refreshAim is its one
// writer (paintInspect), beside the box it names.
export const inspectEl = el("div", "lf-ui lf-inspect lf-target-paint");
inspectEl.setAttribute("aria-hidden", "true");
// Design mode's legend: a box for every item on the page while the mode stands, drawn
// here in the chrome's layer (paintLegend, its one writer). Paint about the page, so it
// says nothing to a screen reader — the mode's announcement and the names under the
// pointer are the spoken copy.
export const legendRoot = el("div", "lf-ui lf-legend");
legendRoot.setAttribute("aria-hidden", "true");

/* The reader commenting on the layer rather than the page: what a widget looks like or
 * does, a control, the runtime's own chrome. A mode rather than a chord, because it is
 * entered for a batch of remarks and changes what a press means everywhere: a press
 * comments on what it lands on and does nothing else, so a card can be pointed at
 * without moving it and a pick mark without picking. Prose keeps the browser's
 * selection — words are still the way to point at words — and a plain click on prose
 * comments on the block it is in. `designOn` is the state; the body class, the banner's
 * wash, the toggle's pressed face and the name under the pointer are its renderings,
 * written by the one setter, and every comment opened while it stands carries
 * `about: "layer"`, which is how the agent tells a remark about the layer from one about
 * the page's words. */
export let designOn = false;

// Kept per tab across document travel and reload, the way the panel's open state is
// (PANEL_KEY). Live activation keeps the variable itself; historical travel restores it.
// A reader put out of the mode by news they didn't ask for is a mode error the page made
// for them. Working state of this tab, so the tab's store rather than the reader's.
export const DESIGN_KEY = "lf-design";

// How long a name may run where the chrome writes one on a line of its own: the word
// design mode shows for the control under the pointer, and the passage the key line
// names in what `z` would take back. One cut, because it is one line's worth of room.
export const CONTROL_WORD_CAP = 24;

export function setDesign(on, { spoken = true } = {}) {
  // A popover is in the browser's top layer, above every ordinary z-index. Design mode
  // targets ordinary page and chrome paint, so retire that transient preview rather
  // than promise an aim and composer that the platform must paint underneath it.
  if (on) closePreview();
  designOn = on;
  document.body.classList.toggle("lf-design", on);
  banner.classList.toggle("lf-designing", on);
  tabStore.set(DESIGN_KEY, on ? "1" : null);
  // The renderings above are the eye's copy; the mode change is spoken, or it is silent
  // to exactly the reader who can't see them. Restoring after a reload changes nothing
  // the reader did, so it says nothing.
  if (spoken)
    announce(
      on
        ? "Design mode: a click comments on what it lands on — a widget, a control, the chrome. Escape leaves."
        : "Design mode off",
    );
  syncGeneral(); // the general box's hint says which of the two it posts
  refreshAim(); // the box and the name follow the mode, not only the pointer
  paintLegend(); // and so does the legend — with the class, not a frame behind it
  paintHere();
}

// The legend: what is on the page, shown while the mode stands rather than found by
// hovering. One box per item in the chrome's layer (the stylesheet's .lf-legend-box
// says what it looks like and why), and on every item but a widget's parts the
// item's name — the words a design comment on it will carry (designName). The parts
// keep the hairline alone: a board's cards each have an id and each is a target, but a
// tag on every card names nothing a reader can't see and hides what they can.
//
// Painted whole from the page on every ask, like the aim's box, because a legend is a
// reading of the page and a box kept from a previous reading is a claim about a page
// that has since moved. What moves it: a scroll (a board's sideways one included), a
// replay (paintAnchors), a resize, the page's markup changing under it (legendMoves —
// a diagram finishing its draw, a details opening, a card dragged), and a size
// changing with no mutation to say so (legendSizes — an image landing inside an item,
// a font swapping in). The shell observer in chrome-layout hears the body's own size
// and workspace-margin motion and sends them through pageShifted too.
// Coalesced to a frame off those doors; the mode change paints in place, so the class
// and the legend land together.
//
// Reads before writes, in two passes: a box's geometry is a DOM write, and an item's
// rect read after one is a layout forced per item — the thrash a legend of a few
// hundred boxes cannot afford on every scroll frame. So the box set is settled first,
// every rect is read, and only then is anything placed.
const legendBoxes = new Map(); // item → { box, radius, tagW }
const legendSizes = new ResizeObserver(() => pageShifted());
const legendMoves = new MutationObserver((records) => {
  // The legend's own writes are mutations too, inside the chrome; a repaint that heard
  // itself would never stop.
  if (records.some((r) => !inChrome(r.target))) pageShifted();
});
let legendQueued = false;
// One tag's height, measured once: where a box's top is nearer the banner than this,
// the tag sits inside.
let legendTagH = 0;
export function queueLegend() {
  if (!designOn || legendQueued) return;
  legendQueued = true;
  requestAnimationFrame(() => {
    legendQueued = false;
    paintLegend();
  });
}
export function paintLegend() {
  if (!designOn) {
    legendRoot.replaceChildren();
    legendBoxes.clear();
    legendSizes.disconnect();
    legendMoves.disconnect();
    return;
  }
  legendMoves.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    characterData: true,
  });
  const items = [...document.querySelectorAll(ITEM)].filter(isItem);
  // The set: a box for every item, in document order so a part's box paints over its
  // widget's, and no box for an item the page no longer holds.
  const present = new Set(items);
  for (const [item, { box }] of legendBoxes)
    if (!present.has(item)) {
      box.remove();
      legendBoxes.delete(item);
      legendSizes.unobserve(item);
    }
  // A widget's part is what its entry says it is — a tag declaring x-parent has a
  // holder, and is what the holder is made of — rather than what stands inside a
  // widget: a tab holds a whole page, and every heading and paragraph of that page is
  // the author's, and named.
  const parts = new Set(tagsDeclaring((e) => e["x-parent"]));
  for (const item of items) {
    if (legendBoxes.has(item)) continue;
    const box = el("div", "lf-legend-box lf-page-paint");
    box.dataset.for = item.id; // which item, stated where a test can read it (as .lf-aim's)
    if (!parts.has(item.tagName.toLowerCase()))
      box.append(el("span", "lf-legend-tag", designName(item)));
    legendBoxes.set(item, { box });
    legendRoot.append(box);
    legendSizes.observe(item);
  }
  // The reads.
  const clips = new Map();
  const under = banner.getBoundingClientRect().bottom;
  const placed = items.map((item) => {
    const entry = legendBoxes.get(item);
    entry.radius ??= getComputedStyle(item).borderRadius;
    if (!legendTagH && entry.box.firstChild)
      legendTagH = entry.box.firstChild.getBoundingClientRect().height;
    // A tag's width is its text's (nowrap) under a viewport-relative cap (40vw), so
    // it is re-measured while shown rather than cached: a width taken in a narrow
    // window understates the tag after a resize, and a missed step is the garble
    // this pass exists to prevent. A box hidden by an earlier write measures zero,
    // so it keeps its last answer until the pass after it shows again.
    if (entry.box.style.display !== "none")
      entry.tagW = entry.box.firstChild ? entry.box.firstChild.offsetWidth : 0;
    return [entry, shownRect(item, clips)];
  });
  // The writes. Names that would land on one spot step apart: a suggestion and the
  // block it wraps share a top-left corner, and two tags written there garble both —
  // the longer peeking out past the shorter as fragments of a word nobody wrote. The
  // later tag (document order, so the part's over its widget's) steps away from the
  // corner by tag heights until it stands clear.
  const said = []; // tag boxes already placed this pass, in viewport coordinates
  for (const [{ box, radius, tagW }, r] of placed) {
    if (!r) {
      box.style.display = "none";
      continue;
    }
    const at = documentPoint(r.left - 1, r.top - 1);
    Object.assign(box.style, {
      display: "block",
      left: at.left + "px",
      top: at.top + "px",
      width: r.right - r.left + 2 + "px",
      height: r.bottom - r.top + 2 + "px",
      borderRadius: radius,
    });
    const inward = r.top - legendTagH < under;
    box.classList.toggle("lf-in", inward);
    if (!tagW) continue;
    const left = r.left - 1;
    const step = inward ? legendTagH : -legendTagH;
    let top = inward ? r.top : r.top - legendTagH;
    let moved = 0;
    while (
      said.some(
        (t) =>
          left < t.left + t.width &&
          t.left < left + tagW &&
          top < t.top + legendTagH &&
          t.top < top + legendTagH,
      )
    ) {
      top += step;
      moved += step;
    }
    box.firstChild.style.transform = moved ? `translateY(${moved}px)` : "";
    said.push({ left, top, width: tagW });
  }
}

// What a design press is about: the nearest thing with an id — a page item, the same
// answer the ⌥ aim gives, or inside the chrome the part the runtime named — and the
// control the press landed on where it landed on one, since "the grip" and "the card"
// are different remarks. Nothing where the press is the mode's own machinery: the
// composer being typed into, the 💬 that opens it, the name floating under the pointer.
const DESIGN_OWN = ".lf-composer, .lf-fab-bar, .lf-inspect";
// Asked at use: widget-elements.js's selector reaches this module back through the
// geometry helpers, so it is not readable as this module evaluates.
const controls = () => `${WORKS},[data-lf-offer]`;
export function designTarget(node) {
  const at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at || closestAcross(at, DESIGN_OWN)) return null;
  const marginTarget = marginTargetAt(at);
  // In the layer, the nearest id — but the author's before the runtime's. The runtime's
  // own parts wear its namespace and are the target themselves; a widget an agent sent
  // wears an authored id and its module's generated parts wear the runtime's, so passing
  // over those lands on the widget, which is where `itemAt` lands out on the page. Taking
  // the nearest of any kind anchored a design comment on `lf-diagram-3` — a number that
  // changes with draw order — and `layerPart` then read it back as a part of the layer.
  const el =
    marginTarget ??
    (inChrome(at)
      ? (closestAcross(at, '[id]:not([id^="lf-"])') ?? closestAcross(at, "[id]"))
      : itemAt(at));
  if (!el) return null;
  const control = closestAcross(at, controls());
  const part =
    control && control !== el && (marginTarget === el || containsAcross(el, control))
      ? controlWord(control)
      : "";
  return { el, part };
}

// A control's word for the label: what it says to a screen reader, else what it shows,
// else what it is.
function controlWord(control) {
  const said =
    control.getAttribute("aria-label") ||
    control.textContent.replace(/\s+/g, " ").trim();
  if (!said) return control.tagName.toLowerCase();
  return [...said].length > CONTROL_WORD_CAP
    ? cut(said, 0, CONTROL_WORD_CAP) + "…"
    : said;
}

// The name a design target wears — under the pointer, in the composer, beside its
// thread. A widget is its tag and id, because both are what a fix is written against; a
// page element takes the reader's word for its kind; a runtime part is its name, the id
// minus the runtime's prefix.
export function designName(el) {
  if (layerPart(el)) return el.id.replace(/^lf-/, "").replace(/-/g, " ");
  const tag = el.tagName.toLowerCase();
  return `${tag.startsWith("lf-") ? tag : itemWord(el)} · ${el.id}`;
}

// Which presses the mode takes at the press, ahead of the page: everything but prose and
// the mode's own machinery. A widget, a control, a picture, the chrome — none has words
// to select and each has something a press would otherwise do, and the mode's promise is
// that it does none of it. Whether the press has a durable target decides only whether a
// composer can open; it never gives the activation back to the page. Prose is left to the
// browser, so a drag still selects, and the click that ends a plain press on it reaches
// the handler in the entry module rather than being taken here.
const PRESSED = () =>
  [...tagsDeclaring(() => true), controls(), "svg", "img", "figure"].join(",");
export function designPress(target) {
  const at = target?.nodeType === 1 ? target : target?.parentElement;
  return Boolean(
    designOn &&
    at &&
    !closestAcross(at, DESIGN_OWN) &&
    (inChrome(at) || closestAcross(at, PRESSED())),
  );
}

// The one way a design target becomes the composer's anchor: the element by id, and the
// control's word where the press landed on one.
export function openOnDesign({ el, part }) {
  showFab(null);
  openComposer({ section: el.id, ...(part && { part }) }, "");
}
