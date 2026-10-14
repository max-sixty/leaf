import {
  DESIGN_MODE_KEY,
  registerCoveringAuxiliarySurface,
  retainUserIntent,
  tabStore,
  userStore
} from "./bundle-user-intent.js";
import {
  closeNativeLayer,
  dismissPopoversOutside,
  el,
  hides,
  keys,
  layoutWindow,
  pagePresented,
  placeHolder,
  setRuntimeRootStyle,
  showNativeLayer,
  transitionNativeAncestor
} from "./bundle-page-paint.js";
import {
  closeLayer,
  deepFocus,
  focusDestination,
  focused,
  handBack,
  holdFocus,
  keeps,
  keepsHidden,
  layerLanding,
  nativeLayerHolding,
  nativeLayerKind,
  nextRender,
  standingIn,
  under
} from "./bundle-sample-visibility.js";

// runtime/auxiliary-surfaces.js
var AUXILIARY_SURFACE_KEY = "lf-auxiliary-surface";
var selectedKey = null;
var currentAuxiliarySurface = () => selectedKey;
var standsBeside = () => parseFloat(
  getComputedStyle(document.body).getPropertyValue("--lf-auxiliary-beside")
) > 0;
function createAuxiliarySurfaces({
  envelope,
  band,
  syncLayout,
  afterChange,
  reachChanged
}) {
  const controllers = /* @__PURE__ */ new Map();
  const scrim = document.createElement("div");
  scrim.className = "lf-auxiliary-scrim";
  scrim.hidden = true;
  scrim.setAttribute("aria-hidden", "true");
  envelope.className = "lf-ui lf-auxiliary-envelope";
  envelope.setAttribute("open", "");
  envelope.setAttribute("role", "presentation");
  envelope.append(scrim);
  let active = null;
  let seated = null;
  let mounted = false;
  let arriving = null;
  let arrivalIntent = null;
  const landingIn = (controller) => controller.landing() ?? controller.surface;
  function seat(selected) {
    const next = selected?.covers() ? selected : null;
    if (seated === selected && active === next) return;
    const previous = active;
    const changedPosture = Boolean(active) !== Boolean(next);
    if (next) dismissPopoversOutside(next.surface);
    const held = holdFocus(document);
    closeLayer(
      () => {
        if (previous) previous.surface.removeAttribute("data-lf-covered");
        active = next;
        seated = selected;
        keeps(band, "inert", next && !next.underBand ? "" : null);
        if (next) keeps(next.surface, "data-lf-covered", "");
        if (changedPosture || !envelope.open) {
          transitionNativeAncestor(envelope, () => {
            if (envelope.open) closeNativeLayer(envelope);
            showNativeLayer(envelope, { modal: Boolean(next) });
          });
        }
        band.toggleAttribute("data-lf-over-covering", Boolean(next?.underBand));
        keepsHidden(scrim, !next);
        keeps(document.documentElement, "data-lf-covering-surface", next?.surface.id);
      },
      seatLanding(next, held)
    );
  }
  const seatLanding = (next, held) => layerLanding(() => {
    const restored = held?.();
    if (next && document.hasFocus() && !restored && nativeLayerKind(nativeLayerHolding(deepFocus())) !== "popover")
      focusDestination(landingIn(next), "return");
  });
  function registerAuxiliarySurface({
    key,
    surface,
    scroller,
    edge,
    beside = false,
    underBand = false,
    landing,
    opener,
    show,
    hide,
    arrival = "mount"
  }) {
    if (!key || !surface?.id || !(surface.hasAttribute("aria-label") || surface.hasAttribute("aria-labelledby")) || !scroller || !edge || !landing || !opener || !show || !hide)
      throw new Error(
        "leaf: an auxiliary surface needs a key, an id and an accessible name, a scroller, an edge, a focus destination, an opener, and visibility callbacks"
      );
    if (controllers.has(key))
      throw new Error(`leaf: duplicate auxiliary surface ${key}`);
    const controller = {
      key,
      surface,
      scroller,
      edge,
      covers: () => !beside || !standsBeside(),
      underBand,
      landing,
      opener,
      show,
      hide,
      arrival
    };
    controllers.set(key, controller);
    return () => {
      if (controllers.get(key) !== controller) return;
      if (selectedKey === key) select(null);
      controllers.delete(key);
    };
  }
  let reachQueued = false;
  function sync() {
    const selected = controllers.get(selectedKey);
    const shown = selected && selected !== arriving ? selected : null;
    keeps(envelope, "role", shown ? null : "presentation");
    keeps(envelope, "aria-label", shown?.surface.getAttribute("aria-label"));
    keeps(envelope, "aria-labelledby", shown?.surface.getAttribute("aria-labelledby"));
    seat(shown);
    if (reachQueued) return;
    reachQueued = true;
    nextRender(() => {
      reachQueued = false;
      reachChanged();
    });
  }
  function select(key, { remember = true, focus = false, phase = "gesture", land: land2 } = {}) {
    if (key !== null && !controllers.has(key))
      throw new Error(`leaf: unknown auxiliary surface ${key}`);
    if (selectedKey === key) return;
    const previous = controllers.get(selectedKey);
    selectedKey = key;
    const selected = controllers.get(key);
    if (key) document.body.dataset.lfAuxiliarySurface = key;
    else delete document.body.dataset.lfAuxiliarySurface;
    arriving = selected && phase === "arrival" && selected.arrival === "presentation" && !pagePresented() ? selected : null;
    arrivalIntent = arriving ? retainUserIntent({ since: 0 }) : null;
    if (!selected || arriving || Boolean(active) !== selected.covers()) seat(null);
    const swap = Boolean(previous && selected && previous.edge === selected.edge);
    if (previous) {
      const opener = previous.opener();
      const inside = standingIn(previous.surface);
      closeLayer(
        () => previous.hide({ swap }),
        land2 ?? (inside && (() => handBack(opener)))
      );
    }
    if (selected && !arriving) selected.show({ phase: swap ? "swap" : phase });
    sync();
    syncLayout();
    afterChange();
    if (focus && selected && !arriving) focusDestination(landingIn(selected), "move");
    if (remember) userStore.set(AUXILIARY_SURFACE_KEY, key ?? "");
  }
  function restore() {
    const key = userStore.get(AUXILIARY_SURFACE_KEY);
    select(controllers.has(key) ? key : null, { remember: false, phase: "arrival" });
  }
  function present() {
    if (!arriving) return;
    if (!arrivalIntent()) {
      select(null, { remember: false });
      return;
    }
    const surface = arriving;
    arriving = null;
    arrivalIntent = null;
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
  }
  function clearFor(where) {
    const selected = controllers.get(selectedKey);
    const holder = where && placeHolder(where);
    if (!selected || !holder || under(holder, selected.surface)) return;
    if (selected.covers() || hides(selected.surface, where)) select(null);
  }
  const selectedSurface = () => controllers.get(selectedKey)?.surface ?? null;
  const coveringSurface = () => active?.surface ?? null;
  const coveringScroller = () => active?.scroller() ?? null;
  const coveringFocus = () => active ? landingIn(active) : null;
  registerCoveringAuxiliarySurface(coveringSurface);
  return {
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
    coveringFocus
  };
}

// runtime/drawn-edge.js
var EDGE_STEP = 24;
var activeResize = null;
function drawnEdge({ side, noun, defaultWidth, min, prop, key }) {
  const handles = /* @__PURE__ */ new Set();
  let chosen = null;
  const cap = () => layoutWindow().right;
  const held = (want) => Math.min(cap(), Math.max(min, want));
  const width = () => held(chosen ?? defaultWidth());
  function state() {
    setRuntimeRootStyle(document.documentElement, prop, width() + "px");
    for (const handle2 of handles) {
      keeps(handle2, "aria-valuenow", Math.round(width()));
      keeps(handle2, "aria-valuemax", Math.round(cap()));
      const fixed = cap() <= min;
      if (fixed && handle2 === focused())
        focusDestination(handle2.lfFixedFocus(), "return");
      keepsHidden(handle2, fixed);
    }
  }
  function set(want) {
    chosen = Math.round(held(want));
    userStore.set(key, String(chosen));
    land(state);
  }
  function handle(region, fixedFocus, when) {
    const edge = el("div", "lf-ui lf-edge");
    edge.lfFixedFocus = fixedFocus;
    edge.dataset.lfSide = side;
    edge.setAttribute("role", "separator");
    edge.setAttribute("aria-orientation", "vertical");
    edge.setAttribute("aria-label", `${noun[0].toUpperCase()}${noun.slice(1)} width`);
    edge.setAttribute("aria-valuemin", String(min));
    edge.tabIndex = 0;
    edge.addEventListener("pointerdown", (event) => {
      if (activeResize || !event.isPrimary || event.button !== 0) return;
      edge.blur();
      edge.setPointerCapture(event.pointerId);
      const box = region.getBoundingClientRect();
      activeResize = {
        edge,
        pointerId: event.pointerId,
        grab: event.clientX - (side === "right" ? box.left : box.right)
      };
    });
    edge.addEventListener("pointermove", (event) => {
      if (activeResize?.edge !== edge || activeResize.pointerId !== event.pointerId || !edge.hasPointerCapture(event.pointerId))
        return;
      const at = event.clientX - activeResize.grab;
      set(side === "right" ? layoutWindow().right - at : at);
    });
    edge.addEventListener("mousedown", (event) => event.stopPropagation());
    const finish = (event) => {
      if (activeResize?.edge !== edge || activeResize.pointerId !== event.pointerId)
        return;
      activeResize = null;
      focusDestination(edge, "move");
    };
    for (const ending of ["pointerup", "pointercancel", "lostpointercapture"])
      edge.addEventListener(ending, finish);
    const wider = side === "right" ? "ArrowLeft" : "ArrowRight";
    keys(
      edge,
      `On the ${noun}'s edge`,
      [
        {
          id: "region.resize",
          keys: ["ArrowLeft", "ArrowRight"],
          routes: [
            {
              id: "region.resize-left",
              binding: "ArrowLeft",
              title: `Move the ${noun}'s edge left`
            },
            {
              id: "region.resize-right",
              binding: "ArrowRight",
              title: `Move the ${noun}'s edge right`
            }
          ],
          label: "arrows",
          title: `resize the ${noun}`,
          repeat: true,
          run: (binding) => set(width() + (binding === wider ? EDGE_STEP : -EDGE_STEP))
        }
      ],
      when
    );
    handles.add(edge);
    region.prepend(edge);
    state();
    return edge;
  }
  function restore() {
    chosen = parseFloat(userStore.get(key)) || null;
    state();
  }
  return { width, state, restore, handle };
}
var land = null;
function landEdgesWith(landing) {
  land = landing;
}
var THREAD_PANEL_MIN = 320;
var THREAD_PANEL_PROP = "--lf-thread-panel-width";
var DRAWER_SLOT_W = 300;
var DRAWER_SLOT_MIN = 220;
var DRAWER_SLOT_PROP = "--lf-drawer-slot-width";
var sideEdge = drawnEdge({
  side: "right",
  noun: "side panel",
  defaultWidth: () => parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue(
      "--lf-thread-panel-default-width"
    )
  ),
  min: THREAD_PANEL_MIN,
  prop: THREAD_PANEL_PROP,
  key: "lf-thread-panel-width"
});
var drawerEdge = drawnEdge({
  side: "left",
  noun: "drawer panel",
  defaultWidth: () => DRAWER_SLOT_W,
  min: DRAWER_SLOT_MIN,
  prop: DRAWER_SLOT_PROP,
  key: "lf-drawer-slot-width"
});
function restateEdges() {
  sideEdge.state();
  drawerEdge.state();
}
function restoreEdges() {
  sideEdge.restore();
  drawerEdge.restore();
}

// runtime/restore-state.js
var ANNOTATIONS_KEY = "lf-annotations";
var USER_VIEW_RESTORE_CASES = [
  {
    name: "the thread panel open",
    ...userStore.where(AUXILIARY_SURFACE_KEY),
    value: "threads"
  },
  {
    name: "the thread panel at the width the user drew it to",
    ...userStore.where("lf-thread-panel-width"),
    value: "560"
  },
  {
    name: "the drawer panel at the width the user drew it to",
    ...userStore.where("lf-drawer-slot-width"),
    value: "260"
  },
  ...["leaves", "queue"].map((drawer) => ({
    name: `the ${drawer} drawer open`,
    ...userStore.where(AUXILIARY_SURFACE_KEY),
    value: drawer
  })),
  { name: "design mode on", ...tabStore.where(DESIGN_MODE_KEY), value: "1" },
  { name: "annotations hidden", ...tabStore.where(ANNOTATIONS_KEY), value: "hidden" }
];
function restoreUserView({ restoreAuxiliarySurface, setDesignMode }) {
  restoreEdges();
  restoreAuxiliarySurface();
  if (tabStore.get(DESIGN_MODE_KEY) === "1") setDesignMode(true, { spoken: false });
}

export {
  landEdgesWith,
  sideEdge,
  drawerEdge,
  restateEdges,
  currentAuxiliarySurface,
  standsBeside,
  createAuxiliarySurfaces,
  ANNOTATIONS_KEY,
  USER_VIEW_RESTORE_CASES,
  restoreUserView
};
