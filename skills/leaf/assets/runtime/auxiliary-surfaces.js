/* One selected auxiliary surface, its remembered selection, and its covering boundary.

   Registered surfaces retain their own rendering and scrollports. Selecting one closes
   the previous surface before opening it; there is no per-surface visibility state.
   Every surface stands over the page and takes no room from it, so selecting one never
   changes the page's geometry. A surface whose rows need the first server reading
   declares presentation-time arrival, so its rendering and covering boundary wait for
   that reading.

   A surface either always covers the page or declares that it may stand `beside` it,
   leaving the page live. One that may stand beside covers the page only where it would
   leave less than a usable page beside it, and the stylesheet states that once for every
   such surface, as the width the selected one stands at or nothing where it covers
   (theme.css, `--lf-auxiliary-beside`); `standsBeside` is the runtime's one reading of it.

   In the covering posture this owner makes every sibling reading surface inert, dims that
   entire background, gives the surface modal semantics, and moves focus in only when it was
   elsewhere in this document. It re-derives those siblings when the live version replaces the authored
   page. Leaving that posture restores exactly the inert and role state it found; it
   does not rebuild, hide, or scroll either side.

   Beside the page, the panels still dominate focus (Max, 2026-10-06): focus never lands
   on page content a standing surface covers, and moving focus never closes or changes
   the surface. This owner makes the content it covers inert for as long as it stands
   beside the page, and nothing else, so Threads stands beside a full-width workspace
   with the uncovered part of it live.

   Travel asks this owner to clear whatever surface hides a destination (`clearFor`),
   so every trip that promises to show one closes the same surfaces by the same rule.

   A surface that stands under the bottom bar, as a drawer does (its list ends above the
   band's stated height), keeps that band over it in the covering posture too: the band
   is the one always-visible guide to the keys the surface answers, and its More control
   stays live, so this owner leaves it out of the inert background and marks it
   `data-lf-over-covering` for the stylesheet to raise it over the scrim and the
   surface. The thread panel carries its own foot, and the band yields to it instead.

   Native inertness owns sequential focus and pointer reach. This owner adds the Tab
   wrap and programmatic-focus recovery that a non-top-layer surface still needs.
   Entering the boundary dismisses pre-existing outside popovers. Native dialogs, and
   popovers deliberately opened after entry, remain available to their top-layer owner. */

import { openPopovers } from "./keyboard/layer-stack.js";
import { registerAuxiliaryModality } from "./keyboard/register.js";
import { hides, placeHolder } from "./geometry.js";
import { under } from "./shadow.js";
import { deepFocus, tabStops } from "./focus.js";
import { userStore } from "./storage.js";
import { pagePresented } from "./presentation.js";
import { keeps, keepsHidden } from "./keeps.js";
import { nextRender } from "./rendering.js";

export const AUXILIARY_SURFACE_KEY = "lf-auxiliary-surface";
let selectedKey = null;
export const currentAuxiliarySurface = () => selectedKey;
// Whether the selected surface stands beside the page, leaving it live: the length the
// stylesheet answers from the surface's width and the window's is more than nothing.
export const standsBeside = () =>
  parseFloat(
    getComputedStyle(document.body).getPropertyValue("--lf-auxiliary-beside"),
  ) > 0;

export function createAuxiliarySurfaces({
  chromeRoot,
  band,
  syncLayout,
  afterChange,
  reachChanged,
}) {
  const controllers = new Map();
  const scrim = document.createElement("div");
  scrim.className = "lf-auxiliary-scrim";
  scrim.hidden = true;
  scrim.setAttribute("aria-hidden", "true");
  let active = null;
  let placingFocus = false;
  let mounted = false;
  let arriving = null;

  const place = (node) => {
    placingFocus = true;
    try {
      node.focus({ preventScroll: true });
    } finally {
      placingFocus = false;
    }
  };
  const nativeLayerContains = (node) => node?.closest?.("dialog:modal, :popover-open");
  const overlay = (node) => node.matches?.("dialog:not(.lf-thread-panel), [popover]");
  // Every other surface is out of the background: only one is selected, so the rest are
  // closed, or inert for the length of their exit slide (motion.js). Each surface's own
  // show and hide own whether it takes presses, and the boundary never records or
  // restores a state that belongs to them.
  const background = ({ underBand }) => {
    const surfaces = new Set([...controllers.values()].map(({ surface }) => surface));
    const nodes = [];
    for (const child of document.body.children) {
      if (child !== chromeRoot) nodes.push(child);
    }
    for (const child of chromeRoot.children) {
      if (
        !surfaces.has(child) &&
        child !== scrim &&
        !overlay(child) &&
        !(underBand && child === band)
      )
        nodes.push(child);
    }
    return nodes;
  };

  // The inert state each node had before a boundary took it, restored exactly when the
  // boundary lets it go. The covering boundary's map belongs to the boundary rather than
  // to a surface, so a node the next surface's boundary also takes stays inert through
  // the handover instead of being restored and taken again.
  // Answers whether the set it holds changed.
  const hold = (held, next) => {
    let changed = false;
    for (const [node, inert] of held) {
      if (next.has(node)) continue;
      node.toggleAttribute("inert", inert);
      held.delete(node);
      changed = true;
    }
    for (const node of next) {
      if (held.has(node)) continue;
      held.set(node, node.inert);
      node.toggleAttribute("inert", true);
      changed = true;
    }
    return changed;
  };
  const suspended = new Map();
  const syncBackground = (controller) =>
    hold(suspended, new Set(controller ? background(controller) : []));

  const backgroundMutations = new MutationObserver(() => {
    if (active) syncBackground(active);
  });

  // Beside the page a surface still stands over part of it, and the panels dominate
  // focus: focus never lands on page content a standing surface covers, and moving focus
  // never closes or changes the surface. So page content it stands over by more than
  // half its width, the measure `hides` (geometry.js) applies to a destination, is inert
  // while it stands beside the page, and the rest stays live. The walk takes the
  // outermost element so covered and goes inside one it only overlaps, so a workspace's
  // rail under Threads goes whole and a line's last link goes alone. It reads border
  // boxes alone, since it runs over the whole page whenever the page's content or the
  // surface's place changes.
  const footprint = new Map();
  const coveredBy = (surface) => {
    const left = surface.offsetLeft;
    const right = left + surface.offsetWidth;
    const covered = [];
    const visit = (parent) => {
      for (const child of [
        ...parent.children,
        ...(parent.shadowRoot?.children ?? []),
      ]) {
        const box = child.getBoundingClientRect();
        if (!box.width && !box.height) {
          visit(child);
          continue;
        }
        const over = Math.min(box.right, right) - Math.max(box.left, left);
        if (over <= 0) continue;
        if (over > box.width / 2) covered.push(child);
        else visit(child);
      }
    };
    const page = document.querySelector("body > main");
    if (page) visit(page);
    return covered;
  };
  let footprintQueued = false;
  // Whether a surface stands beside the page, so page changes read its footprint again.
  let watching = false;
  // A surface moving changes which seats the user can reach, so the page is presented
  // again (`reachChanged`) to move whatever stands in a seat it now covers or uncovers.
  // Content arriving under a standing surface is presented already, so its own pass only
  // holds the new footprint; presenting again there could replace what it just made inert.
  const syncFootprint = ({ surfaceMoved = false } = {}) => {
    footprintQueued = false;
    const selected = controllers.get(selectedKey);
    const beside = selected && selected !== arriving && !active ? selected : null;
    watching = Boolean(beside);
    if (beside)
      pageMutations.observe(document.body, { childList: true, subtree: true });
    else pageMutations.disconnect();
    const changed = hold(footprint, new Set(beside ? coveredBy(beside.surface) : []));
    if (changed && surfaceMoved) reachChanged();
  };
  const queueFootprint = () => {
    if (footprintQueued) return;
    footprintQueued = true;
    nextRender(() => syncFootprint());
  };
  const pageMutations = new MutationObserver((records) => {
    if (!records.every(({ target }) => chromeRoot.contains(target))) queueFootprint();
  });
  // A box scrolled sideways carries what it holds under the surface or out from under it
  // with no change to the document; a vertical scroll moves nothing across the surface's
  // edge, so only a change of `scrollLeft` reads the footprint again.
  const scrolledLeft = new WeakMap();
  addEventListener(
    "scroll",
    ({ target }) => {
      if (!watching || !(target instanceof Element)) return;
      const left = target.scrollLeft;
      if (scrolledLeft.get(target) === left) return;
      scrolledLeft.set(target, left);
      queueFootprint();
    },
    { capture: true, passive: true },
  );

  // Focus is moved in only from elsewhere in this document. Where the document holds no
  // focus at all, the user is in another one — the page around a sample, a sibling
  // sample, another window — and moving it in would pull them back into this frame: four
  // samples with open panels did so to each other on every frame. The boundary takes the
  // focus when the document does instead, once the press or key that brought the user
  // back has put them somewhere. The band a surface stands under stays live beside it.
  const outside = (controller) =>
    document.hasFocus() &&
    !controller.surface.contains(document.activeElement) &&
    !(controller.underBand && band.contains(document.activeElement));
  const recover = () => {
    if (active && outside(active) && !nativeLayerContains(document.activeElement))
      place(active.focus() ?? active.surface);
  };
  const focusMutations = new MutationObserver(recover);
  addEventListener("focus", () => nextRender(recover));

  // The covering boundary moves in one step, from the surface holding it to `next` or to
  // none. What both boundaries say — the inert background they share, the scrim, the
  // band's place — is written once, to where it ends, rather than lifted by one surface
  // and put back by the next.
  function cover(next) {
    if (active === next) return;
    const previous = active;
    if (previous) {
      backgroundMutations.disconnect();
      focusMutations.disconnect();
      keeps(previous.surface, "role", previous.role);
      previous.surface.removeAttribute("aria-modal");
    }
    active = next;
    if (next)
      for (const popover of openPopovers())
        if (!under(popover, next.surface)) popover.hidePopover();
    syncBackground(next);
    band.toggleAttribute("data-lf-over-covering", Boolean(next?.underBand));
    keepsHidden(scrim, !next);
    if (!next) {
      delete document.documentElement.dataset.lfCoveringSurface;
      return;
    }
    next.role = next.surface.getAttribute("role");
    keeps(next.surface, "role", "dialog");
    keeps(next.surface, "aria-modal", "true");
    keeps(document.documentElement, "data-lf-covering-surface", next.surface.id);
    backgroundMutations.observe(document.body, { childList: true });
    backgroundMutations.observe(chromeRoot, { childList: true });
    focusMutations.observe(next.surface, { childList: true, subtree: true });

    if (outside(next)) place(next.focus() ?? next.surface);
  }

  function registerAuxiliarySurface({
    key,
    surface,
    scroller,
    beside = false,
    underBand = false,
    focus,
    show,
    hide,
    arrival = "mount",
  }) {
    // Named for assistive technology as well as by id: in the covering posture this
    // owner makes the surface a modal dialog, and a dialog needs a name.
    if (
      !key ||
      !surface?.id ||
      !(
        surface.hasAttribute("aria-label") || surface.hasAttribute("aria-labelledby")
      ) ||
      !scroller ||
      !focus ||
      !show ||
      !hide
    )
      throw new Error(
        "leaf: an auxiliary surface needs a key, an id and an accessible name, a scroller, a focus destination, and visibility callbacks",
      );
    if (controllers.has(key))
      throw new Error(`leaf: duplicate auxiliary surface ${key}`);
    const controller = {
      key,
      surface,
      scroller,
      covers: () => !beside || !standsBeside(),
      underBand,
      focus,
      show,
      hide,
      arrival,
      role: null,
    };
    controllers.set(key, controller);
    return () => {
      if (controllers.get(key) !== controller) return;
      if (selectedKey === key) select(null);
      controllers.delete(key);
    };
  }

  function sync() {
    const selected = controllers.get(selectedKey);
    cover(selected && selected !== arriving && selected.covers() ? selected : null);
    syncFootprint({ surfaceMoved: true });
  }

  function select(
    key,
    { remember = true, returnFocus = true, phase = "gesture" } = {},
  ) {
    if (key !== null && !controllers.has(key))
      throw new Error(`leaf: unknown auxiliary surface ${key}`);
    if (selectedKey === key) return;
    const previous = controllers.get(selectedKey);
    selectedKey = key;
    const selected = controllers.get(key);
    // The selected surface's width reaches the stylesheet's covering rule through this.
    if (key) document.body.dataset.lfAuxiliarySurface = key;
    else delete document.body.dataset.lfAuxiliarySurface;
    arriving =
      selected &&
      phase === "arrival" &&
      selected.arrival === "presentation" &&
      !pagePresented()
        ? selected
        : null;
    // A surface that will cover takes the boundary straight over at `sync`. Otherwise
    // the boundary lifts before the previous surface hides, so the focus it hands back
    // lands on a live page.
    if (!selected || arriving || !selected.covers()) cover(null);
    previous?.hide({ returnFocus });
    if (selected && !arriving) selected.show({ phase });
    sync();
    syncLayout();
    afterChange();
    if (remember) userStore.set(AUXILIARY_SURFACE_KEY, key ?? "");
  }

  function restore() {
    const key = userStore.get(AUXILIARY_SURFACE_KEY);
    select(controllers.has(key) ? key : null, { remember: false, phase: "arrival" });
  }

  function present() {
    if (!arriving) return;
    const surface = arriving;
    arriving = null;
    surface.show({ phase: "arrival" });
    sync();
    syncLayout();
    afterChange();
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    scrim.addEventListener("pointerdown", (event) => event.preventDefault());
    scrim.addEventListener("click", () => select(null));
    document.addEventListener(
      "keydown",
      (event) => {
        if (
          !active ||
          event.key !== "Tab" ||
          event.altKey ||
          event.ctrlKey ||
          event.metaKey
        )
          return;
        const available = tabStops(active.surface);
        if (!available.length) {
          event.preventDefault();
          place(active.surface);
          return;
        }
        const at = available.indexOf(deepFocus());
        if (
          (!event.shiftKey && at === available.length - 1) ||
          (event.shiftKey && at === 0)
        ) {
          event.preventDefault();
          place(event.shiftKey ? available.at(-1) : available[0]);
        }
      },
      true,
    );
    document.addEventListener("focusin", (event) => {
      if (
        !active ||
        placingFocus ||
        active.surface.contains(event.target) ||
        nativeLayerContains(event.target)
      )
        return;
      place(active.focus() ?? active.surface);
    });
  }

  // Travel that promises to show a destination clears the selected surface hiding it:
  // one covering the page, for anything outside it, or one standing over most of the
  // destination where it lands (geometry.js, `hides`). A destination inside the surface
  // is the surface's own to show. The one owner of this, so a trip to a thread, an Ask
  // or a datum each clears whatever surface happens to stand.
  function clearFor(where) {
    const selected = controllers.get(selectedKey);
    const holder = where && placeHolder(where);
    if (!selected || !holder || under(holder, selected.surface)) return;
    if (selected.covers() || hides(selected.surface, where)) select(null);
  }
  const selectedSurface = () => controllers.get(selectedKey)?.surface ?? null;
  const coveringSurface = () => active?.surface ?? null;
  const coveringScroller = () => active?.scroller() ?? null;
  const coveringFocus = () => (active ? (active.focus() ?? active.surface) : null);
  // The keyboard register carries this reading to the dispatcher, whose own closure stops
  // there: a direct edge to this owner would give a key press this owner's whole
  // initialization graph.
  registerAuxiliaryModality({ coveringSurface });
  return {
    scrim,
    registerAuxiliarySurface,
    select,
    restore,
    present,
    sync,
    mount,
    clearFor,
    selectedSurface,
    coveringSurface,
    coveringScroller,
    coveringFocus,
  };
}
