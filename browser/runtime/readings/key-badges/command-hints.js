/* Inline command hints are a projection of the dispatcher's exact reachable bindings,
 * the one reading every control's keys come from (dom/keyboard/control-keys.js, `reachingNow`).
 *
 * A row or route opts in through `bindingBadge`: an Element lends a widget-positioned
 * face; null requests a runtime corner chip. A text box whose words cover the
 * placeholder that names the key entering it lends that key a face in its own corner
 * too (`coveredEntry`; annotations/composing/surface.js): the key is the dispatcher's,
 * and the box is where its press lands, which its command can't declare as a control
 * without the key dying wherever the box is gone. The widget owns placement, while this
 * presenter owns words and visibility; a control's accessible shortcuts are
 * dom/keyboard/control-keys.js's, from the same reading. A widget's CSS may still
 * withhold a face it lent: one it leaves no box (`display: none`, over the inline
 * `block` this presenter writes) hands its route to a chip, while one it turns
 * transparent stays worn, so nothing stands in for it. A lent face keeps its out-of-flow seat even
 * when empty or its command leaves reach. A face labels a key and takes no pointer, as
 * a chip takes none, so a press where one stands lands on what the widget drew it over,
 * whether the face shows, has just arrived or has just gone. Neither Decision metadata
 * nor a second focus predicate is needed. Contextual aliases and intrinsic bindings to
 * one original command share a face, with a reachable contextual alias preferred.
 *
 * Paint after the chrome's layout, so placement sees current fixed chrome.
 * The lent face is restored when its command leaves reach; stale source references
 * have already been rejected by the dispatcher.
 */
import {
  advertisesKeys,
  bindings,
  commandRoutes,
  routedCommand,
  spell,
  word,
} from "../../dom/keyboard/bindings.js";
import { reachingNow } from "../../dom/keyboard/control-keys.js";
import { keyBadgePlacement } from "./key-badge-placement.js";
import { chipSeats } from "./chip-seats.js";
import { renderedUnder } from "../../lib/shadow-tree.js";
import { elementFromPointAcross } from "../passages.js";
import { html, render } from "/vendor/lit.js";
import { inlineStyle, keepsText } from "../../lib/keeps.js";
import { repaint } from "../../dom/repaint.js";
import { scrolling, watchScrollEnds, watchScrolls } from "../../dom/arrivals.js";

export const commandHintLayer = Object.assign(document.createElement("div"), {
  className: "lf-ui lf-key-chips lf-command-binding-badges",
});
commandHintLayer.setAttribute("aria-hidden", "true");
// A chip rides each scroll with its control and is seated again once the scroll settles.
const seats = chipSeats(commandHintLayer);

/** @typedef {Element} BindingBadge
 * @typedef {{text: string, display: [string, string], opacity: [string, string]}} LentFace
 */
/** @param {import("../../dom/keyboard/bindings.js").CommandRoute} route @returns {route is import("../../dom/keyboard/bindings.js").CommandRoute & {binding: string}} */
const boundRoute = (route) => route.binding !== undefined;

// Expand the reachable bindings that ask for a face, retaining the original command
// behind any contextual alias. A control has one face even when local and contextual
// routes both reach it.
/** @param {ReturnType<typeof reachingNow>["available"]} available */
function hintRoutes(available) {
  /** @type {{original: import("../../dom/keyboard/bindings.js").Command, id: string, control: Element, bindingBadge: BindingBadge | null, contextual: boolean, binding: string}[]} */
  const gathered = [];
  for (const [row, reachable] of available) {
    const routes = commandRoutes(row);
    const contributions = routes.length
      ? routes.filter(boundRoute).filter((route) => reachable.has(route.binding))
      : bindings(row)
          .filter((binding) => reachable.has(binding))
          .map((binding) => ({ ...row, binding }));
    for (const contribution of contributions) {
      const badge =
        contribution.bindingBadge !== undefined
          ? contribution.bindingBadge
          : row.bindingBadge;
      // Undefined asks for no face; explicit null asks for a chip.
      if (badge === undefined) continue;
      const control = word(contribution.control ?? row.control);
      if (control == null) continue;
      const reference = routedCommand(contribution);
      const original = reference?.row ?? row;
      const id = reference?.id ?? contribution.id;
      if (!(control instanceof Element))
        throw new TypeError(`leaf: ${contribution.id} has no Element hint control`);
      const bindingBadge = word(badge) ?? null;
      if (bindingBadge != null && !(bindingBadge instanceof Element))
        throw new TypeError(`leaf: ${contribution.id} has no Element binding badge`);
      // The seat keeps the face out of flow, so filling it never resizes the control
      // it labels or any control holding it.
      if (bindingBadge && !bindingBadge.classList.contains("lf-binding-seat"))
        bindingBadge.classList.add("lf-binding-seat");
      if (!control.isConnected) continue;
      let record = gathered.find(
        (prior) =>
          prior.original === original && prior.id === id && prior.control === control,
      );
      if (!record) {
        record = {
          original,
          id,
          control,
          bindingBadge,
          contextual: false,
          binding: contribution.binding,
        };
        gathered.push(record);
      }
      if (record.bindingBadge !== bindingBadge)
        throw new TypeError(`leaf: ${id} has two binding badge faces`);
      if (reference && !record.contextual) {
        record.binding = contribution.binding;
        record.contextual = true;
      }
    }
  }
  return gathered;
}

/** The keys the hints label `control` with from where the user is, each as its chip
 * spells it: a face lent beside or inside it, as an option's digit, or a corner chip. A
 * touch screen gets none (`advertisesKeys`). Read from the dispatcher's reading rather
 * than the paint, which lands a frame after the focus move that reaches them, so a
 * preview shown on that move already counts them as its target's chips (annotations/preview.js).
 * A chip the paint withholds, for want of a free corner or while a scroll settles, is
 * still counted, so a preview leaves its key unsaid there too.
 * @param {Element} control @returns {string[]} */
export const drawnKeys = (control) =>
  advertisesKeys()
    ? hintRoutes(reachingNow().available)
        .filter((route) => route.control === control)
        .map(({ binding }) => spell(binding))
    : [];

/** @param {{presentedControl: (control: Element) => Element, coveredEntry: () => {control: Element, bindingBadge: Element, binding: string} | null}} options */
export function createCommandHints({ presentedControl, coveredEntry }) {
  let mounted = false;
  let hasRoutes = false;
  // Whether the last paint ran while a scroll moved, and so wore every face.
  let paintedMoving = false;
  /** @type {Map<BindingBadge, LentFace>} */
  const wornBindingBadges = new Map();
  // TODO(#5194): a Tab pays this hit test at every face the window shows. Leaving what
  // stands over a lent face to paint order would delete it: a thread card or a pin
  // covers the control as well as its face, so only a face under the page's own content,
  // such as a sticky bar, would go unseen instead of becoming a corner chip.
  /** @param {Element} bindingBadge @param {Element} control @param {import("../../base/box.js").Box} visible */
  function exposedBindingBadge(bindingBadge, control, visible) {
    const whole = bindingBadge.getBoundingClientRect();
    /** @type {readonly ("left" | "right" | "top" | "bottom")[]} */
    const edges = ["left", "right", "top", "bottom"];
    if (edges.some((edge) => Math.abs(whole[edge] - visible[edge]) > 0.5)) return false;
    const x = (visible.left + visible.right) / 2;
    const y = (visible.top + visible.bottom) / 2;
    const inset = Math.min(
      3,
      (visible.right - visible.left) / 4,
      (visible.bottom - visible.top) / 4,
    );
    // A face takes no pointer (surfaces.css, `.lf-binding-seat`), so a hit test at its
    // place finds what stands there without it, the same whether the face is worn or
    // withheld. The face is exposed where that is the control it labels or something
    // inside it, whose state mark may share the seat (an option's pick turns transparent
    // under a worn face), or a box that holds the face. Anything else there may stand
    // over the face, which this hit test can't tell from standing under it, so the face
    // is withheld and a chip takes its place. A host whose own shadow tree draws a part
    // over a face slotted into it reads as the box that holds the face, so that face is
    // worn under the part. `reserve` gives two faces that overlap to the earlier route.
    /** @type {[number, number][]} */
    const points = [
      [x, y],
      [x, visible.top + inset],
      [x, visible.bottom - inset],
      [visible.left + inset, y],
      [visible.right - inset, y],
    ];
    return points.every(([atX, atY]) => {
      const under = elementFromPointAcross(atX, atY);
      return (
        under !== null &&
        (renderedUnder(under, control) || renderedUnder(bindingBadge, under))
      );
    });
  }
  // Restore the widget's original words and inline properties when the hint leaves.
  /** @type {readonly ["display", "opacity"]} */
  const LENT_PROPERTIES = ["display", "opacity"];
  /** @param {BindingBadge} bindingBadge @param {LentFace} face @param {"display" | "opacity"} name */
  function restoreStyle(bindingBadge, face, name) {
    const [value, priority] = face[name];
    if (value) inlineStyle(bindingBadge).setProperty(name, value, priority);
    else inlineStyle(bindingBadge).removeProperty(name);
  }
  /** @param {BindingBadge} bindingBadge @param {LentFace} face */
  function restoreBindingBadge(bindingBadge, face) {
    bindingBadge.removeAttribute("data-lf-binding-badge");
    keepsText(bindingBadge, face.text);
    for (const name of LENT_PROPERTIES) restoreStyle(bindingBadge, face, name);
    wornBindingBadges.delete(bindingBadge);
  }
  /** @param {ReadonlySet<Element>} [kept] */
  function restoreBindingBadges(kept = new Set()) {
    for (const [bindingBadge, face] of wornBindingBadges)
      if (!kept.has(bindingBadge)) restoreBindingBadge(bindingBadge, face);
  }
  // The page scrolls under these projections on every frame, so a pass writes only what
  // changed (lib/keeps.js): a badge already worn keeps its face, and a chip
  // stands in the document plane, where the scroll carries it.
  function paint() {
    // Read afresh, since the painters before this one may have moved what is live, and
    // the frame's accessible shortcuts read the same (dom/keyboard/control-keys.js).
    const { available } = reachingNow({ fresh: true });
    // A touch screen gets the accessible shortcuts and no faces: a digit drawn where the
    // user has no keyboard names a press they cannot make (`advertisesKeys`).
    /** @type {{binding: string, control: Element, bindingBadge: BindingBadge | null}[]} */
    const visualRoutes = advertisesKeys() ? hintRoutes(available) : [];
    // A touch screen's dispatcher names no key, so no box wears one.
    const entry = coveredEntry();
    if (entry) visualRoutes.push(entry);
    hasRoutes = visualRoutes.length > 0;
    if (!visualRoutes.length) {
      restoreBindingBadges();
      seats.place([]);
      return;
    }
    // What a surface standing over the page hides is shownRect's to say, which the
    // placement below reads.
    const placement = keyBadgePlacement();
    /** @type {Map<BindingBadge, number>} */
    const bindingBadgeClaims = new Map();
    for (const { bindingBadge } of visualRoutes)
      if (bindingBadge)
        bindingBadgeClaims.set(
          bindingBadge,
          (bindingBadgeClaims.get(bindingBadge) ?? 0) + 1,
        );

    // Reuse a widget's page-local binding badge where it has one. Besides preserving the
    // widget's own card-versus-row alignment, leaving this face in the page's stack keeps
    // the fixed chrome above it. One face belongs to one action, and every part of
    // it must be visible on top; otherwise the ordinary core chip carries the same route.
    // That can be read only off the face as it would stand, so the face stays lent while
    // its route stands: one that is not exposed keeps the digit and its box but turns
    // transparent, rather than being put back after each measurement and lent again on
    // the next pass.
    // The core chip takes the face's own place, the widget owning where its digit goes:
    // hung off the control's corner instead, a field's chip covered its first words.
    // Where what hides the face covers that place too, as an open thread card does, the
    // chip yields to it as the face did.
    //
    // The faces go in passes over every route: which controls the window shows, then
    // each of their faces lent, then each face read as it stands, then each worn or
    // withheld. A paint so forces one style and layout pass for its faces however many
    // it lends, where reading each face right after writing it forced two per face
    // (root AGENTS.md, "Responsiveness"). The chips below go the same way.
    //
    // Those rules are for a page at rest. A face whose control the window doesn't show,
    // and every face while any box on the page scrolls, is worn unmeasured, unless its
    // widget leaves it no box, whose chip stays (above): the browser
    // carries it with its control and clips and stacks it as it does the control, so a
    // scroll brings the digit in with the choice it labels, a trackpad's momentum
    // included, and the rules apply again once the scroll ends. So a box that scrolls
    // apart from the control also swaps a chip standing in for a cut face back to the
    // face while it moves. Rejected: painting again whenever a reading of the window
    // changes during the scroll, which copied part of these rules into the reading,
    // missed page content standing over a face and cost a repaint at each crossing.
    const moving = scrolling();
    paintedMoving = moving;
    /** @type {{binding: string, control: Element, bindingBadge: BindingBadge, measured: boolean}[]} */
    const shown = [];
    for (const { binding, control, bindingBadge } of visualRoutes)
      if (bindingBadge?.isConnected && bindingBadgeClaims.get(bindingBadge) === 1)
        shown.push({
          binding,
          control,
          bindingBadge,
          measured: !moving && Boolean(placement.visibleBounds(control)),
        });
    /** @type {Set<BindingBadge>} */
    const lent = new Set();
    const lending = shown.map((route) => {
      const { binding, bindingBadge } = route;
      let said = wornBindingBadges.get(bindingBadge);
      if (!said) {
        /** @param {"display" | "opacity"} name @returns {[string, string]} */
        const property = (name) => [
          inlineStyle(bindingBadge).getPropertyValue(name),
          inlineStyle(bindingBadge).getPropertyPriority(name),
        ];
        said = {
          text: bindingBadge.textContent,
          display: property("display"),
          opacity: property("opacity"),
        };
        wornBindingBadges.set(bindingBadge, said);
      }
      keepsText(bindingBadge, spell(binding));
      inlineStyle(bindingBadge).display = "block";
      lent.add(bindingBadge);
      return { ...route, said };
    });
    const faces = lending.map((route) => {
      const { control, bindingBadge, measured } = route;
      if (!measured)
        return { ...route, exposed: bindingBadge.checkVisibility(), face: null };
      const box = bindingBadge.checkVisibility() && placement.badgeBox(bindingBadge);
      const exposed = Boolean(
        box &&
        exposedBindingBadge(bindingBadge, control, box) &&
        placement.reserve(box, control),
      );
      const face = box && !exposed ? bindingBadge.getBoundingClientRect() : null;
      return { ...route, exposed, face };
    });
    /** @type {Set<BindingBadge>} */
    const worn = new Set();
    /** @type {Map<BindingBadge, DOMRect>} */
    const faceBoxes = new Map();
    for (const { bindingBadge, said, exposed, face } of faces) {
      bindingBadge.toggleAttribute("data-lf-binding-badge", exposed);
      if (exposed) {
        restoreStyle(bindingBadge, said, "opacity");
        worn.add(bindingBadge);
      } else {
        inlineStyle(bindingBadge).opacity = "0";
        if (face) faceBoxes.set(bindingBadge, face);
      }
    }
    restoreBindingBadges(lent);

    // The chips read where each goes, then write their digits.
    /** @type {{binding: string, presented: Element, corner: import("../../base/box.js").Box}[]} */
    const placed = [];
    for (const { binding, control, bindingBadge } of visualRoutes) {
      if (bindingBadge && worn.has(bindingBadge)) continue;
      const presented = presentedControl(control);
      if (!presented.checkVisibility()) continue;
      const face = bindingBadge && faceBoxes.get(bindingBadge);
      const corner = face
        ? {
            left: (face.left + face.right) / 2,
            top: (face.top + face.bottom) / 2,
            right: (face.left + face.right) / 2,
            bottom: (face.top + face.bottom) / 2,
          }
        : placement.badgeBox(presented);
      if (corner) placed.push({ binding, presented, corner });
    }
    const chips = [];
    for (const { binding, presented, corner } of placed) {
      // During a scroll only existing seats update; new chips wait for placement
      // so they cannot flash at an unmeasured position.
      const seat = moving ? seats.seated(presented) : seats.seat(presented);
      if (!seat) continue;
      render(
        html`<span class="lf-key-badge lf-command-binding-badge" aria-hidden="true"
          >${spell(binding)}</span
        >`,
        seat,
      );
      chips.push({ seat, owner: presented, corner });
    }
    // A scroll holds the seats; each chip's digit is current in its own, and a chip whose
    // command left reach is hidden.
    if (moving) seats.keepOnly(new Set(chips.map(({ owner }) => owner)));
    else placement.paint(seats, chips);
  }

  // A scroll's first event repaints with every face worn; its end measures the faces
  // and seats the chips again.
  const paintAgain = () => hasRoutes && repaint();
  const scrolled = () => {
    if (!paintedMoving) paintAgain();
  };
  let stopScrolls = () => {};
  let stopScrollEnds = () => {};
  function mount() {
    if (mounted) return;
    mounted = true;
    stopScrolls = watchScrolls(scrolled);
    stopScrollEnds = watchScrollEnds(paintAgain);
  }
  function destroy() {
    if (mounted) {
      stopScrolls();
      stopScrollEnds();
    }
    paintedMoving = false;
    mounted = false;
    hasRoutes = false;
    restoreBindingBadges();
    seats.clear();
  }
  return { mount, paint, destroy };
}
