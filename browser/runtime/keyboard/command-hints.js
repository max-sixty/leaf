/* Inline command hints are a projection of the dispatcher's exact reachable bindings.
 *
 * A row or route opts in through `bindingBadge`: an Element lends a widget-positioned
 * face; null requests a runtime corner chip. Native command buttons also receive
 * accessible shortcuts without requesting a visual badge. The widget owns placement,
 * while this presenter owns words, visibility and the accessible shortcuts. A lent
 * face keeps its out-of-flow seat even when empty or its command leaves reach. Neither Decision
 * metadata nor a second focus predicate is needed. Contextual aliases and intrinsic
 * bindings to one original command share a face, with a reachable contextual alias
 * preferred. Every remaining reachable binding stays in the accessible projection.
 *
 * Paint after the chrome's layout, so placement sees current fixed chrome.
 * The lent face is restored when its command leaves reach; stale source references
 * have already been rejected by the dispatcher. Accessible shortcuts compose with
 * existing control scopes through scopes.js rather than a second attribute writer.
 */
import {
  advertisesKeys,
  bindings,
  commandRoutes,
  routedCommand,
  spell,
  word,
} from "./bindings.js";
import { availableCommandRoutes } from "./dispatch.js";
import { buttonCommand, commandScope, projectCommandScope } from "./scopes.js";
import { keyBadgePlacement } from "./key-badge-placement.js";
import { chipSeats } from "./chip-seats.js";
import { renderedUnder } from "../shadow.js";
import { html, render } from "/runtime/framework.js";
import { inlineStyle, keepsText } from "../keeps.js";
import { repaint } from "../repaint.js";
import { scrolling, watchScrollEnds } from "../arrivals.js";

export const commandHintLayer = Object.assign(document.createElement("div"), {
  className: "lf-ui lf-key-chips lf-command-binding-badges",
});
commandHintLayer.setAttribute("aria-hidden", "true");
// A chip rides each scroll with its control and is seated again once the scroll settles.
const seats = chipSeats(commandHintLayer);

/** @typedef {Element} BindingBadge
 * @typedef {{text: string, display: [string, string], opacity: [string, string]}} LentFace
 */
/** @param {import("./bindings.js").CommandRoute} route @returns {route is import("./bindings.js").CommandRoute & {binding: string}} */
const boundRoute = (route) => route.binding !== undefined;

// Expand executable bindings, retaining the original command behind any contextual
// alias. A control has one face even when local and contextual routes both reach it.
/** @param {ReturnType<typeof availableCommandRoutes>} available */
function hintRoutes(available) {
  /** @type {{original: import("./bindings.js").Command, id: string, control: Element, bindingBadge: BindingBadge | null | undefined, keys: string[], contextual: boolean, binding: string}[]} */
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
      const control = word(contribution.control ?? row.control);
      if (control == null) continue;
      const reference = routedCommand(contribution);
      const original = reference?.row ?? row;
      const id = reference?.id ?? contribution.id;
      const owned = buttonCommand(control);
      if (badge === undefined && !(owned?.row === original && owned?.entry.id === id))
        continue;
      if (!(control instanceof Element))
        throw new TypeError(`leaf: ${contribution.id} has no Element hint control`);
      // Undefined requests only accessible shortcuts; explicit null requests a chip.
      const bindingBadge = badge === undefined ? undefined : (word(badge) ?? null);
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
          keys: [],
          contextual: false,
          binding: contribution.binding,
        };
        gathered.push(record);
      }
      if (record.bindingBadge !== bindingBadge)
        throw new TypeError(`leaf: ${id} has two binding badge faces`);
      if (!record.keys.includes(contribution.binding))
        record.keys.push(contribution.binding);
      // A contextual alias also advertises any intrinsic keys still reaching its
      // original command, even when that source row did not request its own hint.
      if (reference) {
        const reached = available.get(original) ?? new Set();
        const sourceRoutes = commandRoutes(original);
        const intrinsic = sourceRoutes.length
          ? sourceRoutes
              .filter(boundRoute)
              .filter((route) => route.id === id)
              .map((route) => route.binding)
          : bindings(original);
        for (const key of intrinsic)
          if (reached.has(key) && !record.keys.includes(key)) record.keys.push(key);
      }
      if (reference && !record.contextual) {
        record.binding = contribution.binding;
        record.contextual = true;
      }
    }
  }
  return gathered;
}

/** @param {{presentedControl: (control: Element) => Element | null}} options */
export function createCommandHints({ presentedControl }) {
  let mounted = false;
  let hasRoutes = false;
  /** @type {Map<BindingBadge, LentFace>} */
  const wornBindingBadges = new Map();
  const CONTROL_ROUTES = Symbol("Control binding routes");
  /** @type {Set<Element>} */
  const routedControls = new Set();
  /** @param {Element} bindingBadge @param {Element} control @param {import("../rect.js").Box} visible */
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
    // The whole stack at each point, read the same whether the face is worn or withheld
    // (transparent, and still in the hit test): nothing may stand over the face but the
    // control it labels, whose state mark shares the slot and yields it to a worn face
    // (an option's pick turns transparent).
    const root = bindingBadge.getRootNode();
    if (!(root instanceof Document || root instanceof ShadowRoot)) return false;
    /** @type {[number, number][]} */
    const points = [
      [x, y],
      [x, visible.top + inset],
      [x, visible.bottom - inset],
      [visible.left + inset, y],
      [visible.right - inset, y],
    ];
    return points.every(([atX, atY]) => {
      const stack = root.elementsFromPoint(atX, atY);
      const at = stack.indexOf(bindingBadge);
      return (
        at >= 0 && stack.slice(0, at).every((over) => renderedUnder(over, control))
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
  // Withdraw the routes' scope from every control but the ones still routed.
  /** @param {ReadonlySet<Element>} [kept] */
  function withdrawRoutes(kept = new Set()) {
    for (const control of routedControls) {
      if (kept.has(control)) continue;
      projectCommandScope(control, CONTROL_ROUTES, null);
      routedControls.delete(control);
    }
  }
  function clearProjections() {
    restoreBindingBadges();
    withdrawRoutes();
  }
  // The page scrolls under these projections on every frame, so a pass writes only what
  // changed (keeps.js): a badge already worn keeps its face, and a chip
  // stands in the document plane, where the scroll carries it.
  function paint() {
    const available = availableCommandRoutes();
    const routes = hintRoutes(available);
    /** @type {Map<Element, Set<string>>} */
    const controlKeys = new Map();
    for (const { control, keys } of routes) {
      let reached = controlKeys.get(control);
      if (!reached) {
        reached = new Set();
        controlKeys.set(control, reached);
      }
      for (const key of keys) reached.add(key);
    }
    for (const [control, keys] of controlKeys) {
      projectCommandScope(
        control,
        CONTROL_ROUTES,
        commandScope(null, [
          {
            id: "keyboard.control-route",
            title: "Control shortcuts",
            keys: [...keys],
          },
        ]),
      );
      routedControls.add(control);
    }
    withdrawRoutes(new Set(routes.map(({ control }) => control)));
    // A touch screen gets the accessible shortcuts and no faces: a digit drawn where the
    // user has no keyboard names a press they cannot make (`advertisesKeys`).
    const visualRoutes = advertisesKeys()
      ? routes.filter(({ bindingBadge }) => bindingBadge !== undefined)
      : [];
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
    // the next pass. The widget routes a press on its face to the labeled control.
    // The core chip takes the face's own place, the widget owning where its digit goes:
    // hung off the control's corner instead, a field's chip covered its first words.
    // Where what hides the face covers that place too, as an open thread card does, the
    // chip yields to it as the face did.
    /** @type {Set<BindingBadge>} */
    const lent = new Set();
    /** @type {Set<BindingBadge>} */
    const worn = new Set();
    /** @type {Map<BindingBadge, DOMRect>} */
    const faceBoxes = new Map();
    for (const { binding, control, bindingBadge } of visualRoutes) {
      // A control the window does not show cannot show its face either, and wearing
      // the face only to measure it away would write it twice on every scroll.
      if (
        !bindingBadge?.isConnected ||
        bindingBadgeClaims.get(bindingBadge) !== 1 ||
        !placement.visibleBounds(control)
      )
        continue;
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
      const box = bindingBadge.checkVisibility() && placement.badgeBox(bindingBadge);
      const exposed = Boolean(
        box &&
        exposedBindingBadge(bindingBadge, control, box) &&
        placement.reserve(box),
      );
      bindingBadge.toggleAttribute("data-lf-binding-badge", exposed);
      if (exposed) {
        restoreStyle(bindingBadge, said, "opacity");
        worn.add(bindingBadge);
      } else {
        inlineStyle(bindingBadge).opacity = "0";
        if (box) faceBoxes.set(bindingBadge, bindingBadge.getBoundingClientRect());
      }
    }
    restoreBindingBadges(lent);

    const chips = [];
    const moving = scrolling();
    for (const { binding, control, bindingBadge } of visualRoutes) {
      if (bindingBadge && worn.has(bindingBadge)) continue;
      const presented = presentedControl(control) ?? control;
      if (!presented.checkVisibility()) continue;
      const face = bindingBadge && faceBoxes.get(bindingBadge);
      const box = face
        ? {
            left: (face.left + face.right) / 2,
            top: (face.top + face.bottom) / 2,
            right: (face.left + face.right) / 2,
            bottom: (face.top + face.bottom) / 2,
          }
        : placement.badgeBox(presented);
      if (!box) continue;
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
      chips.push({ seat, owner: presented, corner: box });
    }
    // A scroll holds the seats; each chip's digit is current in its own, and a chip whose
    // command left reach is hidden.
    if (moving) seats.keepOnly(new Set(chips.map(({ owner }) => owner)));
    else placement.paint(seats, chips);
  }

  const scrollEnded = () => hasRoutes && repaint();
  let stopScrollEnds = () => {};
  function mount() {
    if (mounted) return;
    mounted = true;
    stopScrollEnds = watchScrollEnds(scrollEnded);
  }
  function destroy() {
    if (mounted) stopScrollEnds();
    mounted = false;
    hasRoutes = false;
    clearProjections();
    seats.clear();
  }
  return { mount, paint, destroy };
}
