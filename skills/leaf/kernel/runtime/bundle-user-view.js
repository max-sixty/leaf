import {
  darkPreference,
  shownScheme
} from "./bundle-color-scheme.js";
import {
  onMotionPreferenceChange,
  reducedMotion
} from "./bundle-motion.js";
import {
  pageReadiness,
  unconcealedReadingRegions
} from "./bundle-presence.js";
import "./bundle-passage-facts.js";
import {
  coarsePointer,
  layoutWindow,
  randomId,
  seenRect,
  sessionIsActive,
  shownWindow,
  watchRoom
} from "./bundle-page-paint.js";
import {
  offlineInteractive,
  pageUrl,
  runtime,
  watchSemantic
} from "./bundle-semantic-state.js";
import "./bundle-sample-visibility.js";
import "./bundle-queued-work.js";
import "./bundle-__export.js";

// runtime/user-view.js
var REPORT_MS = 1e4;
var QUIET_MS = 300;
var rectangle = ({ x, y, width, height }) => ({ x, y, width, height });
function observeUserView() {
  if (offlineInteractive) return;
  const session = randomId();
  let sequence = 0;
  let pending = null;
  let reading = null;
  let loading = null;
  let checks = null;
  let checkedBasis = null;
  let lastSent = null;
  function context() {
    const visual = window.visualViewport;
    const { right: width, bottom: height } = layoutWindow();
    const viewport = { width, height };
    if (viewport.width <= 0 || viewport.height <= 0 || visual.width <= 0 || visual.height <= 0)
      return null;
    const clips = /* @__PURE__ */ new Map();
    return {
      session,
      sequence: ++sequence,
      visible: document.visibilityState !== "hidden",
      revision: runtime.currentRevision,
      through_seq: runtime.lastEventSeq,
      viewport,
      visual_viewport: {
        width: visual.width,
        height: visual.height,
        offset_left: visual.offsetLeft,
        offset_top: visual.offsetTop,
        scale: visual.scale
      },
      shown_window: rectangle(shownWindow()),
      color_scheme: shownScheme(),
      reduced_motion: reducedMotion(),
      pointer: coarsePointer.matches ? "coarse" : "fine",
      scroll: { x: window.scrollX, y: window.scrollY },
      visible_regions: unconcealedReadingRegions().filter(({ body }) => seenRect(body, clips) !== null).map(({ id }) => id)
    };
  }
  function send(view, keepalive = false) {
    void fetch(pageUrl("api/user-view"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...view, checks }),
      keepalive,
      signal: keepalive ? void 0 : globalThis.AbortSignal.timeout(REPORT_MS)
    }).catch(() => {
    });
  }
  function report({ inspect = false, keepalive = false } = {}) {
    if (!sessionIsActive()) return;
    if (!Number.isInteger(runtime.currentRevision)) return;
    const view = context();
    if (!view) return;
    const basis = JSON.stringify([
      view.revision,
      view.through_seq,
      view.viewport,
      view.visual_viewport,
      view.shown_window,
      view.color_scheme
    ]);
    if (view.visible && pageReadiness() === null && (inspect || basis !== checkedBasis)) {
      if (reading) {
        const open = Object.entries(runtime.registry).filter(([, entry]) => ["markup", "members"].includes(entry["x-content"])).map(([tag]) => tag);
        checks = {
          sequence: view.sequence,
          revision: view.revision,
          through_seq: view.through_seq,
          viewport: view.viewport,
          visual_viewport: view.visual_viewport,
          shown_window: view.shown_window,
          color_scheme: view.color_scheme,
          reading: reading(open)
        };
        checkedBasis = basis;
      } else if (!loading) {
        loading = import("/checks/view.js").then((module) => {
          reading = module.readViewChecks;
          schedule();
        }).catch(() => {
          loading = null;
        });
      }
    }
    const said = JSON.stringify({ ...view, sequence: null, checks });
    if (!inspect && !keepalive && said === lastSent) return;
    lastSent = said;
    send(view, keepalive);
  }
  function schedule() {
    clearTimeout(pending);
    pending = setTimeout(() => {
      pending = null;
      report();
    }, QUIET_MS);
  }
  document.addEventListener("visibilitychange", () => {
    clearTimeout(pending);
    report({ keepalive: document.visibilityState === "hidden" });
  });
  window.addEventListener("pagehide", () => {
    if (!sessionIsActive()) return;
    const view = context();
    if (view) send({ ...view, visible: false }, true);
  });
  document.addEventListener("lf-session-active", schedule);
  watchSemantic(() => {
    if (document.visibilityState !== "hidden") schedule();
  });
  watchRoom(schedule);
  window.addEventListener("pageshow", schedule);
  onMotionPreferenceChange(schedule);
  for (const preference of [darkPreference, coarsePointer])
    preference.addEventListener("change", schedule);
  setInterval(() => {
    if (document.visibilityState !== "hidden") report({ inspect: true });
  }, REPORT_MS);
  schedule();
}
export {
  observeUserView
};
