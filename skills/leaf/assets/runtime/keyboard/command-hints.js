/* Inline command hints are a projection of the dispatcher's exact reachable bindings.
 *
 * A row or route opts in through `bindingBadge`: an Element lends a widget-positioned
 * face; null requests a runtime corner chip. The widget owns placement, while this
 * presenter owns words, visibility and the accessible shortcuts. Neither Decision
 * metadata nor a second focus predicate is needed. Contextual aliases and intrinsic
 * bindings to one original command share a face, with a reachable contextual alias
 * preferred. Every remaining reachable binding stays in the accessible projection.
 *
 * Paint after the shortcut bar's layout, so placement sees current fixed chrome.
 * The lent face is restored when its command leaves reach; stale source references
 * have already been rejected by the dispatcher. Accessible shortcuts compose with
 * existing control scopes through scopes.js rather than a second attribute writer.
 */
import { bindings, commandRoutes, routedCommand, spell, word } from "./bindings.js";
import { availableCommandRoutes } from "./dispatch.js";
import { commandScope, projectCommandScope } from "./scopes.js";
import { coveringAuxiliarySurface } from "./register.js";
import { keyBadgePlacement } from "./key-badge-placement.js";
import { documentPoint } from "../geometry.js";
import { under } from "../shadow.js";
import { el } from "../widget-elements.js";
import { keepsText } from "../keeps.js";
import { repaint } from "../repaint.js";

export const commandHintLayer = Object.assign(document.createElement("div"), {
  className: "lf-ui lf-key-badges lf-command-binding-badges",
});
commandHintLayer.setAttribute("aria-hidden", "true");

// Expand executable bindings, retaining the original command behind any contextual
// alias. A control has one face even when local and contextual routes both reach it.
function hintRoutes(available) {
  const gathered = [];
  for (const [row, reachable] of available) {
    const routes = commandRoutes(row);
    const contributions = routes.length
      ? routes.filter((route) => reachable.has(route.binding))
      : bindings(row)
          .filter((binding) => reachable.has(binding))
          .map((binding) => ({ ...row, binding }));
    for (const contribution of contributions) {
      const badge =
        contribution.bindingBadge !== undefined
          ? contribution.bindingBadge
          : row.bindingBadge;
      // An explicit null opts into the corner fallback; an absent field offers no hint.
      if (contribution.bindingBadge === undefined && row.bindingBadge === undefined)
        continue;
      const control = word(contribution.control ?? row.control);
      const bindingBadge = word(badge) ?? null;
      if (control == null) continue;
      if (!(control instanceof Element))
        throw new TypeError(`leaf: ${contribution.id} has no Element hint control`);
      if (!control.isConnected) continue;
      if (bindingBadge !== null && !(bindingBadge instanceof Element))
        throw new TypeError(`leaf: ${contribution.id} has no Element binding badge`);
      const reference = routedCommand(contribution);
      const original = reference?.row ?? row;
      const id = reference?.id ?? contribution.id;
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

export function createCommandHints({ presentedControl }) {
  let mounted = false;
  let hasRoutes = false;
  const wornBindingBadges = new Map();
  const CONTROL_ROUTES = Symbol("Control binding routes");
  const routedControls = new Set();
  function exposedBindingBadge(bindingBadge, control, visible) {
    const whole = bindingBadge.getBoundingClientRect();
    if (
      ["left", "right", "top", "bottom"].some(
        (edge) => Math.abs(whole[edge] - visible[edge]) > 0.5,
      )
    )
      return false;
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
    return [
      [x, y],
      [x, visible.top + inset],
      [x, visible.bottom - inset],
      [visible.left + inset, y],
      [visible.right - inset, y],
    ].every(([atX, atY]) => {
      const stack = root.elementsFromPoint(atX, atY);
      const at = stack.indexOf(bindingBadge);
      return at >= 0 && stack.slice(0, at).every((over) => under(over, control));
    });
  }
  // Restore the widget's original words and inline properties when the hint leaves.
  const LENT_PROPERTIES = ["display", "opacity"];
  function restoreStyle(bindingBadge, name) {
    const [value, priority] = wornBindingBadges.get(bindingBadge)[name];
    if (value) bindingBadge.style.setProperty(name, value, priority);
    else bindingBadge.style.removeProperty(name);
  }
  function restoreBindingBadge(bindingBadge) {
    bindingBadge.removeAttribute("data-lf-binding-badge");
    keepsText(bindingBadge, wornBindingBadges.get(bindingBadge).text);
    for (const name of LENT_PROPERTIES) restoreStyle(bindingBadge, name);
    wornBindingBadges.delete(bindingBadge);
  }
  function restoreBindingBadges(kept = new Set()) {
    for (const bindingBadge of [...wornBindingBadges.keys()])
      if (!kept.has(bindingBadge)) restoreBindingBadge(bindingBadge);
  }
  // A chip per control, kept across passes, so a pass that finds the same chips standing
  // where they stood writes nothing.
  const bindingChips = new Map();
  // Withdraw the routes' scope from every control but the ones still routed.
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
    hasRoutes = routes.length > 0;
    const controlKeys = new Map();
    for (const { control, keys } of routes) {
      if (!controlKeys.has(control)) controlKeys.set(control, new Set());
      for (const key of keys) controlKeys.get(control).add(key);
    }
    for (const [control, keys] of controlKeys) {
      projectCommandScope(
        control,
        CONTROL_ROUTES,
        commandScope(null, [
          {
            id: "keyboard.control-route",
            title: "Control shortcuts",
            line: false,
            keys: [...keys],
          },
        ]),
      );
      routedControls.add(control);
    }
    withdrawRoutes(new Set(routes.map(({ control }) => control)));
    if (!routes.length) {
      restoreBindingBadges();
      bindingChips.clear();
      keyBadgePlacement().paint(commandHintLayer, []);
      return;
    }
    // A covering auxiliary surface does not invalidate the commands or their accessible
    // shortcuts, but it does hide the page controls outside it that binding-badge faces
    // claim to label. What a surface standing over the page hides is shownRect's to say,
    // which the placement below reads.
    const covering = coveringAuxiliarySurface();
    const covered = (control) => covering && !under(control, covering);
    const placement = keyBadgePlacement();
    const bindingBadgeClaims = new Map();
    for (const { bindingBadge } of routes)
      if (bindingBadge)
        bindingBadgeClaims.set(
          bindingBadge,
          (bindingBadgeClaims.get(bindingBadge) ?? 0) + 1,
        );

    // Reuse a widget's page-local binding badge where it has one. Besides preserving the
    // widget's own card-versus-row alignment, leaving this face in the page's stack keeps
    // the fixed shortcut bar above it. One face belongs to one action, and every part of
    // it must be visible on top; otherwise the ordinary core chip carries the same route.
    // That can be read only off the face as it would stand, so the face stays lent while
    // its route stands: one that is not exposed keeps the digit and its box but turns
    // transparent, rather than being put back after each measurement and lent again on
    // the next pass. The widget routes a press on its face to the labeled control.
    const lent = new Set();
    const worn = new Set();
    for (const { binding, control, bindingBadge } of routes) {
      // A control the window does not show cannot show its face either, and wearing
      // the face only to measure it away would write it twice on every scroll.
      if (
        covered(control) ||
        !bindingBadge?.isConnected ||
        bindingBadgeClaims.get(bindingBadge) !== 1 ||
        !placement.visibleBounds(control)
      )
        continue;
      if (!wornBindingBadges.has(bindingBadge)) {
        const said = { text: bindingBadge.textContent };
        for (const name of LENT_PROPERTIES)
          said[name] = [
            bindingBadge.style.getPropertyValue(name),
            bindingBadge.style.getPropertyPriority(name),
          ];
        wornBindingBadges.set(bindingBadge, said);
      }
      keepsText(bindingBadge, spell(binding));
      bindingBadge.style.display = "block";
      lent.add(bindingBadge);
      const box = bindingBadge.checkVisibility() && placement.badgeBox(bindingBadge);
      const exposed = Boolean(
        box &&
        exposedBindingBadge(bindingBadge, control, box) &&
        placement.reserve(box),
      );
      bindingBadge.toggleAttribute("data-lf-binding-badge", exposed);
      if (exposed) {
        restoreStyle(bindingBadge, "opacity");
        worn.add(bindingBadge);
      } else bindingBadge.style.opacity = "0";
    }
    restoreBindingBadges(lent);

    const chips = [];
    for (const { binding, control, bindingBadge } of routes) {
      if (covered(control)) continue;
      if (bindingBadge && worn.has(bindingBadge)) continue;
      const presented = presentedControl(control) ?? control;
      if (!presented.checkVisibility()) continue;
      const box = placement.badgeBox(presented);
      if (!box) continue;
      let chip = bindingChips.get(control);
      if (!chip) {
        chip = el("span", "lf-key-badge lf-command-binding-badge");
        chip.setAttribute("aria-hidden", "true");
        bindingChips.set(control, chip);
      }
      keepsText(chip, spell(binding));
      chips.push({
        chip,
        owner: presented,
        corner: box,
        at: documentPoint(box.left, box.top),
      });
    }
    // `chips` holds seats, so a chip is kept by the seat that names it; comparing a chip
    // with the seats themselves dropped every chip, and each pass made its chips again
    // at their anchors, where a chip pulled inside the window was painted a frame early.
    const seated = new Set(chips.map(({ chip }) => chip));
    for (const control of [...bindingChips.keys()])
      if (!seated.has(bindingChips.get(control))) bindingChips.delete(control);
    placement.paint(commandHintLayer, chips);
  }

  const pageScrolled = () => hasRoutes && repaint();
  function mount() {
    if (mounted) return;
    mounted = true;
    addEventListener("scroll", pageScrolled, { capture: true, passive: true });
  }
  function destroy() {
    if (mounted)
      globalThis.removeEventListener("scroll", pageScrolled, { capture: true });
    mounted = false;
    hasRoutes = false;
    clearProjections();
    bindingChips.clear();
    keyBadgePlacement().paint(commandHintLayer, []);
  }
  return { mount, paint, destroy };
}
