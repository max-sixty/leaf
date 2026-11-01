/* This module owns Design mode and legend geometry. Anchor resolution owns the
 * target reading shared by its direct presses, pointer promise, and keyboard picker. */
import { cancelRender, nextRender, sizeObserver } from "./rendering.js";
import { shownBox } from "./geometry.js";
import { layoutPx } from "./keeps.js";
import { paintSet } from "./target-paint-geometry.js";
import { el } from "./widget-elements.js";
import { tabStore } from "./tab-store.js";
import {
  isAddressable,
  ADDRESSABLE,
  aimTargetAt,
  aimTargets,
  designPressAt,
} from "./anchor-resolution.js";
import { inChrome, leafSurface } from "./passages.js";
import { tagsDeclaring } from "./registry.js";
import { designName, DESIGN_MODE_KEY } from "./design-readings.js";
import { pageCommand, pageRung, pageScope } from "./keyboard/register.js";
import { coarsePointer } from "./pointer.js";

// The name of what the pointer is over in design mode, floated at its corner. Chrome
// nothing presses (pointer-events none, in the stylesheet); refreshAim is its one
// writer (paintInspect), in the aim's planes beside the box it names.
export const inspectEl = el("div", "lf-ui lf-inspect");
inspectEl.setAttribute("aria-hidden", "true");
// Design mode's legend: a box for every addressable element on the page while the mode stands, drawn
// here in the chrome's layer (paintLegend, its one writer). Paint about the page, so it
// says nothing to a screen reader — the mode's announcement and the names under the
// pointer are the spoken copy.
export const legendRoot = el("div", "lf-ui lf-legend");
legendRoot.setAttribute("aria-hidden", "true");

/* The user marking presentation or interaction intent: what a widget looks like or
 * does, a control on the page. A mode rather than a sequence, because it is entered for
 * a batch of remarks and changes what a press on the page means: a press comments on
 * what it lands on and does nothing else, so a card can be pointed at without moving it
 * and a pick mark without picking. The mode is about what the agent made: the page, a
 * margin entry, which stands for a page item or is a widget's own action, and a widget
 * the agent sent in a reply. Leaf's own chrome — the floating panel, its menu and its
 * views — works as it does outside the mode, as it does for the target
 * picker: a remark on it has no reader who can act on it, and a mode that took it
 * would take the way out of whatever the mode's own send opened. Prose keeps the
 * browser's selection — words are still the way to point at words — and a plain click on
 * prose comments on the block it is in. `designModeOn` is the state; the body marker, the toggle's
 * pressed face and the name under the pointer are its renderings,
 * written by the one setter, and every comment opened while it stands carries
 * `about: "design"`, which is how the agent tells design intent from a remark about
 * the page's words. The mode owns that state and supplies `active` to every
 * renderer or command that needs the reading. */

/** @param {{pageGeometry: {refreshAim: () => unknown, pageShifted: () => unknown},
 * syncGeneral: () => unknown,
 * composer: Pick<ReturnType<typeof import("./composing/surface.js").createResponseSurface>, "showFab" | "openComposer">,
 * closePreview: () => unknown, marginTargetAt: NonNullable<import("./anchor-resolution.js").AimOptions["marginTargetAt"]>,
 * closeDrawMode: () => unknown, closeTargetPicker: () => unknown, closeReactionMode: () => unknown,
 * announce: (message: string) => unknown, repaint: () => unknown}} options */
export function createDesignMode({
  pageGeometry,
  syncGeneral,
  composer,
  closePreview,
  marginTargetAt,
  closeDrawMode,
  closeTargetPicker,
  closeReactionMode,
  announce,
  repaint,
}) {
  // Live activation belongs to this controller. Historical travel restores it through
  // DESIGN_MODE_KEY; commands and renderers receive `active` rather than sharing mutable state.
  let designModeOn = false;

  /** @param {boolean} on @param {{spoken?: boolean}} [options] */
  function setDesignMode(on, { spoken = true } = {}) {
    // Design mode reinterprets presses on the page and its margin as interface comments,
    // so retire the thread card rather than leave a thread up that no press can work.
    // The page is in one mode at a time, as Draw mode's own setter keeps it. A finger
    // reaches this from More while the picker or Draw mode holds, where no key could.
    if (on) {
      closePreview();
      closeDrawMode();
      closeTargetPicker();
      closeReactionMode();
    }
    designModeOn = on;
    document.body.toggleAttribute("data-lf-design-mode", on);
    tabStore.set(DESIGN_MODE_KEY, on ? "1" : null);
    // The renderings above are the eye's copy; the mode change is spoken, or it is silent
    // to exactly the user who can't see them. Restoring after a reload changes nothing
    // the user did, so it says nothing.
    if (spoken)
      announce(
        on
          ? `Design mode: a click comments on what it lands on — a widget, a control, a picture. ${
              coarsePointer.matches ? "Exit Design mode leaves." : "Escape leaves."
            }`
          : "Design mode off",
      );
    syncGeneral(); // the general box's hint says which of the two it posts
    pageGeometry.refreshAim(); // the box and name follow the mode, not only the pointer
    paintLegend(); // and so does the legend — with the class, not a frame behind it
    repaint();
  }

  // The legend: what is on the page, shown while the mode stands rather than found by
  // hovering. One box per addressable element in the chrome's layer (the stylesheet's
  // .lf-legend-box says what it looks like and why), and on every addressable but a
  // widget's parts the element's name — the words a design comment on it will carry
  // (designName). The parts
  // keep the hairline alone: a board's cards each have an id and each is a target, but a
  // tag on every card names nothing a user can't see and hides what they can.
  //
  // Painted whole from the page on every ask that can move it, like the aim's box,
  // because a legend is a reading of the page and a box kept from a previous reading is a
  // claim about a page that has since moved. What moves it: a replay (paintAnchors), a
  // resize, the page's markup changing under it (legendMoves — a diagram finishing its
  // draw, a details opening, a card dragged), and a size changing with no mutation to
  // say so (legendSizes — an image landing inside an element, a font swapping in). The
  // shell observer in page-layout hears the body's own size and margin motion and sends
  // them through pageShifted too. Coalesced to a frame off those
  // doors; the mode change paints in place, so the class and the legend land together.
  //
  // A scroll is none of these. Each box stands in the frames of the boxes that clip
  // what it names, anchored to what it names (target-paint-geometry.js, `paintSet`), so
  // the browser carries it through every scroll, a pane's or a board's sideways one
  // included, and through a sticky offset, a transform or layout that moves its element
  // as well. Only a box whose element is within a screen of where it would show is in
  // the document, so a legend of a few hundred boxes holds a screenful of anchors, not
  // one for each, the layout cost that took the margin's rows off anchors of their own.
  // A scroll changes only which tags stand inside their box (`legendScrolled`).
  //
  // Reads before writes: a box's geometry is a DOM write, and an element's rect read
  // after one is a layout forced per element — the thrash a legend of a few hundred
  // boxes cannot afford. So the box set is settled first, every box is measured and
  // placed (`place` reads them all before it writes), and only the tags are left.
  /** @typedef {{holder: Element | null, from: number}} LegendCut */
  /** @typedef {{addressable: Element, box: HTMLDivElement, tag: HTMLSpanElement | null, radius: string, cuts: LegendCut[], tagW?: number}} LegendEntry */
  /** @type {Map<Element, LegendEntry>} */
  const legendBoxes = new Map(); // addressable → { box, radius, tagW, cuts }
  // The addressables in document order, as the last pass found them.
  /** @type {LegendEntry[]} */
  let legendOrder = [];
  const legendSizes = sizeObserver(() => pageGeometry.pageShifted());
  const legend = paintSet(legendRoot, { onNear: () => placeTags() });
  // The legend's own writes are mutations too, inside the chrome, and so is the runtime's
  // paint on page elements: a mark rewrites its classes, in the runtime's namespace, on
  // every repaint, which a shift starts. A repaint that heard either would never stop,
  // and on a page with reactions it didn't, at thousands of mutations a second. Naming
  // the start of a scroller's words (`data-lf-content-start`) moves nothing either.
  const authoredClasses = (/** @type {string | null} */ value) =>
    (value ?? "")
      .split(/\s+/)
      .filter((name) => name && !name.startsWith("lf-"))
      .sort()
      .join(" ");
  const movesPage = (/** @type {MutationRecord} */ r) =>
    !inChrome(r.target) &&
    r.attributeName !== "data-lf-content-start" &&
    !(
      r.attributeName === "class" &&
      r.target instanceof Element &&
      authoredClasses(r.oldValue) === authoredClasses(r.target.getAttribute("class"))
    );
  const legendMoves = new MutationObserver((records) => {
    if (records.some(movesPage)) pageGeometry.pageShifted();
  });
  let legendFrame = 0;
  // One tag's height, measured once: where a box's top is nearer the window's head than this,
  // the tag sits inside.
  let legendTagH = 0;
  function queueLegend() {
    if (!designModeOn || legendFrame) return;
    legendFrame = nextRender(() => {
      legendFrame = 0;
      paintLegend();
    });
  }
  function paintLegend() {
    if (!designModeOn) {
      legend.clear();
      legendRoot.replaceChildren();
      legendBoxes.clear();
      legendOrder = [];
      legendSizes.disconnect();
      legendMoves.disconnect();
      return;
    }
    legendMoves.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeOldValue: true,
      characterData: true,
    });
    const addressables = [...document.querySelectorAll(ADDRESSABLE)].filter(
      isAddressable,
    );
    // The set: a box for every addressable, in document order so a part's box paints over
    // its widget's, and no box for an element the page no longer holds.
    const present = new Set(addressables);
    for (const addressable of legendBoxes.keys())
      if (!present.has(addressable)) {
        legendBoxes.delete(addressable);
        legendSizes.unobserve(addressable);
      }
    // A widget's part is what its declaration says it is — a tag declaring x-owners has a
    // compound owner, and is what the owner is made of — rather than what stands inside a
    // widget: a tab holds a whole page, and every heading and paragraph of that page is
    // the author's, and named.
    const parts = new Set(tagsDeclaring((e) => e["x-owners"]));
    /** @type {LegendEntry[]} */
    const entries = [];
    for (const addressable of addressables) {
      let entry = legendBoxes.get(addressable);
      if (!entry) {
        const box = el("div", "lf-legend-box lf-page-paint");
        box.dataset.for = addressable.id;
        const tag = parts.has(addressable.tagName.toLowerCase())
          ? null
          : el("span", "lf-legend-tag", designName(addressable));
        if (tag) box.append(tag);
        entry = {
          addressable,
          box,
          tag,
          radius: getComputedStyle(addressable).borderRadius,
          cuts: [],
        };
        legendBoxes.set(addressable, entry);
        legendSizes.observe(addressable);
      }
      entries.push(entry);
    }
    // Hidden targets retain their frames until scrolling brings them back.
    const shown = entries.filter(({ addressable }) => addressable.checkVisibility());
    const placed = legend
      .place(
        shown.map(({ addressable, box }) => ({
          node: box,
          target: addressable,
          rect: ({ rect }) => ({
            left: rect.left - 1,
            top: rect.top - 1,
            right: rect.right + 1,
            bottom: rect.bottom + 1,
          }),
        })),
      )
      .values();
    for (const entry of shown) {
      if (entry.box.style.borderRadius !== entry.radius)
        entry.box.style.borderRadius = entry.radius;
      const placement = placed.next().value;
      entry.cuts = (placement?.levels ?? [])
        .filter(({ axes }) => axes.y)
        .map(({ holder, from }) => ({ holder, from: from.top }));
    }
    legendOrder = entries;
    placeTags();
  }
  // Names that would land on one spot step apart: a suggestion and the block it wraps
  // share a top-left corner, and two tags written there garble both — the longer peeking
  // out past the shorter as fragments of a word nobody wrote. The later tag (document
  // order, so the part's over its widget's) steps away from the corner by tag heights
  // until it stands clear. A tag stands above its box, or inside its corner where the
  // window or a frame cutting the box leaves no room above. Read where the elements and
  // the cuts stand now, on every scroll, since a sticky or fixed element's tag and the
  // tags the page carries past it move apart; a tag is written only where its step or
  // its side changed.
  function placeTags(scrolled = false) {
    const roomTop = 0;
    /** @type {Map<Element, number>} */
    const holders = new Map();
    const tags = [];
    for (const entry of legendOrder) {
      const { addressable, tag } = entry;
      if (!tag || !legend.stands(entry.box) || !legend.near(addressable)) continue;
      legendTagH ||= tag.getBoundingClientRect().height;
      const width =
        !scrolled || entry.tagW === undefined ? tag.offsetWidth : entry.tagW;
      entry.tagW = width;
      const rect = shownBox(addressable);
      const room = Math.max(
        roomTop,
        ...entry.cuts.map(({ holder, from }) => {
          if (!holder) return from;
          let top = holders.get(holder);
          if (top === undefined) {
            top = holder.getBoundingClientRect().top;
            holders.set(holder, top);
          }
          return top + from;
        }),
      );
      tags.push({ entry, tag, rect, width, inward: rect.top - 1 - legendTagH < room });
    }
    /** @type {{left: number, top: number, width: number}[]} */
    const said = []; // tag boxes already placed, in viewport coordinates
    for (const { entry, tag, rect, width, inward } of tags) {
      const { box } = entry;
      box.classList.toggle("lf-in", inward);
      const left = rect.left - 1;
      const step = inward ? legendTagH : -legendTagH;
      let top = inward ? rect.top - 1 : rect.top - 1 - legendTagH;
      let shift = 0;
      while (
        said.some(
          (t) =>
            left < t.left + t.width &&
            t.left < left + width &&
            top < t.top + legendTagH &&
            t.top < top + legendTagH,
        )
      ) {
        top += step;
        shift += step;
      }
      const transform = shift ? `translateY(${layoutPx(shift)})` : "";
      if (tag.style.transform !== transform) tag.style.transform = transform;
      said.push({ left, top, width });
    }
  }
  const legendScrolled = () => {
    if (designModeOn && legendBoxes.size) placeTags(true);
  };

  const targetOptions = { design: true, marginTargetAt };
  const designTarget = (/** @type {Node | null} */ node) =>
    aimTargetAt(node, targetOptions);

  // Which presses the mode takes at the press, ahead of the page: everything on the page
  // but prose, and whatever in the chrome the agent made. A widget, a control, a picture —
  // none has words to select and each has something a press would otherwise do, and the
  // mode's promise is that it does none of it. Whether the press has a durable target decides only whether a
  // composer can open; it never gives the activation back to the page. Prose is left to the
  // browser, so a drag still selects, and the click that ends a plain press on it reaches
  // the handler in the entry module rather than being taken here.
  /** @param {Node | null} target */
  function designPress(target) {
    const at = target instanceof Element ? target : target?.parentElement;
    if (!designModeOn || !at) return false;
    return Boolean(leafSurface(at) ? designTarget(at) : designPressAt(at));
  }

  // The one way a design target becomes the composer's anchor: the element by id, and the
  // control's word where the press landed on one.
  /** @param {import("./anchor-resolution.js").AimTarget} target */
  function openOnDesign({ anchor }) {
    composer.showFab(null);
    composer.openComposer(anchor, "");
  }

  function destroy() {
    if (legendFrame) cancelRender(legendFrame);
    legendFrame = 0;
    legendSizes.disconnect();
    legendMoves.disconnect();
    legend.clear();
    legendBoxes.clear();
    legendRoot.replaceChildren();
    document.body.removeAttribute("data-lf-design-mode");
    designModeOn = false;
  }

  // A page mode the user is in for a batch of design remarks. The press the mode
  // is made of is not a key at all, so that row binds nothing and says nothing on the
  // line, the way the ⌥ aim's row does.
  pageScope("design mode", {
    title: "In Design mode",
    at: () => designModeOn,
    rows: [
      {
        id: "design.mode.comment",
        keys: [],
        label: "click",
        title: "Comment on appearance",
        description: "Click a widget, control or picture. Text still selects as usual",
      },
      {
        id: "design.mode.exit",
        keys: ["l"],
        title: "exit Design mode",
        exit: true,
        run: () => setDesignMode(false),
      },
    ],
  });
  // A mode is the stance the whole page is in rather than something standing on part of
  // it, so everything the user puts up while it holds is put up inside it and Escape
  // takes it off from the ladder last, before the page itself: a composer opened in the
  // mode closes first, its own scope being nearer, then a panel the mode's own send
  // opened, then the mode.
  pageRung("design mode", () =>
    designModeOn
      ? {
          title: "exit Design mode",

          out: () => setDesignMode(false),
        }
      : null,
  );
  // The way in; the mode's own scope takes the letter back out, nearer than this row, so
  // while the mode stands this one is shadowed off the line.
  pageCommand({
    id: "design.mode.enter",
    keys: ["l"],
    description: "Comment on how the page looks and works",
    title: "design mode",
    touch: "Design mode",
    menu: "annotate",
    when: () => !designModeOn,
    run: () => setDesignMode(true),
  });

  return {
    destroy,
    active: () => designModeOn,
    setActive: setDesignMode,
    queueLegend,
    legendScrolled,
    paintLegend,
    target: designTarget,
    targets: () => aimTargets(targetOptions),
    press: designPress,
    open: openOnDesign,
    name: designName,
    inspectElement: inspectEl,
  };
}
