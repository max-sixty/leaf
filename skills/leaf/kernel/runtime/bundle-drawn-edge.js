import {
  DESIGN_MODE_KEY,
  tabStore,
  userStore
} from "./bundle-user-intent.js";
import {
  el,
  keys,
  layoutWindow,
  setRuntimeRootStyle
} from "./bundle-page-paint.js";
import {
  focusDestination,
  focused,
  keeps,
  keepsHidden
} from "./bundle-sample-visibility.js";

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
    name: "the thread panel at the width the user drew it to",
    ...userStore.where("lf-thread-panel-width"),
    value: "560"
  },
  {
    name: "the drawer panel at the width the user drew it to",
    ...userStore.where("lf-drawer-slot-width"),
    value: "260"
  },
  { name: "design mode on", ...tabStore.where(DESIGN_MODE_KEY), value: "1" },
  { name: "annotations hidden", ...tabStore.where(ANNOTATIONS_KEY), value: "hidden" }
];
function restoreUserView({ setDesignMode }) {
  restoreEdges();
  if (tabStore.get(DESIGN_MODE_KEY) === "1") setDesignMode(true, { spoken: false });
}

export {
  landEdgesWith,
  sideEdge,
  drawerEdge,
  restateEdges,
  ANNOTATIONS_KEY,
  USER_VIEW_RESTORE_CASES,
  restoreUserView
};
