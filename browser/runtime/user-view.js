/* A document's disposable view context for its author. Nothing here changes page
   state, layout, or the event log. Geometry stays with its mechanical owners;
   passive checks run only after presentation, never as a presentation prerequisite.
   An unallocated document has no view to report; normal observation resumes when
   its viewport has room. A document id is deliberately not stored: duplicated tabs
   must never share a lease. */
import { pageIdentity } from "./page-identity.js";
import { darkPreference, shownScheme } from "./color-scheme.js";
import { offlineInteractive, pageUrl, runtime } from "./context.js";
import { layoutWindow, seenRect, shownWindow, watchRoom } from "./geometry.js";
import { randomId } from "./ids.js";
import { layerHeaders, sessionIsActive } from "./layer-client.js";
import { onMotionPreferenceChange, reducedMotion } from "./motion.js";
import { pageReadiness } from "./presentation.js";
import { coarsePointer } from "./pointer.js";
import { unconcealedReadingRegions } from "./reading-regions.js";
import { tagsDeclaring } from "./registry.js";
import { watchSemantic } from "./semantic-state.js";

const REPORT_MS = 10_000;
const QUIET_MS = 300;
const rectangle = ({ x, y, width, height }) => ({ x, y, width, height });

const session = randomId();
let sequence = 0;
let reading = null;
let loading = null;

// One lazy probe and one context producer serve periodic author observations and an
// explicit inspection. A failed load may be retried on the next request.
function loadReading() {
  return (loading ??= import("/checks/view.js")
    .then((module) => {
      reading = module.readViewChecks;
    })
    .catch((error) => {
      loading = null;
      throw error;
    }));
}

function context() {
  const visual = window.visualViewport;
  const { right: width, bottom: height } = layoutWindow();
  const viewport = { width, height };
  if (
    viewport.width <= 0 ||
    viewport.height <= 0 ||
    visual.width <= 0 ||
    visual.height <= 0
  )
    return null;
  const clips = new Map();
  return {
    session,
    identity: pageIdentity(),
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
      scale: visual.scale,
    },
    shown_window: rectangle(shownWindow()),
    color_scheme: shownScheme(),
    reduced_motion: reducedMotion(),
    pointer: coarsePointer.matches ? "coarse" : "fine",
    scroll: { x: window.scrollX, y: window.scrollY },
    visible_regions: unconcealedReadingRegions()
      .filter(({ body }) => seenRect(body, clips) !== null)
      .map(({ id }) => id),
  };
}

function readChecks(view) {
  const open = tagsDeclaring((entry) =>
    ["markup", "members"].includes(entry["x-content"]),
  );
  return {
    sequence: view.sequence,
    identity: view.identity,
    revision: view.revision,
    through_seq: view.through_seq,
    viewport: view.viewport,
    visual_viewport: view.visual_viewport,
    shown_window: view.shown_window,
    color_scheme: view.color_scheme,
    reading: reading(open),
  };
}

// Capture before an inspection opens a modal: a modal makes the page inert and can
// change which regions are observable. This reads only; it neither reports a lease
// nor activates a website session. Exports can still report their browser context.
export async function readCurrentUserView() {
  let unavailable = null;
  if (offlineInteractive) unavailable = "Layout probes are unavailable in an export.";
  else {
    try {
      await loadReading();
    } catch (error) {
      unavailable = `Layout probes unavailable: ${error.message}`;
    }
  }
  const view = context();
  if (!view)
    return { revision: null, unavailable: "The document has no allocated viewport." };
  return {
    ...view,
    observed_at: new Date().toISOString(),
    readiness: pageReadiness(),
    checks: unavailable ? null : readChecks(view),
    ...(unavailable ? { unavailable } : {}),
  };
}

export function observeUserView() {
  if (offlineInteractive) return;
  let pending = null;
  let checks = null;
  let checkedBasis = null;
  let lastSent = null;

  function send(view, keepalive = false) {
    // Optional context has no delivery obligation. A failed report expires at the
    // server; the next observation replaces it rather than queuing old geometry.
    void fetch(pageUrl("api/user-view"), {
      method: "POST",
      // The runtime it names keeps a tab from before an update from describing the
      // page a newer runtime draws (`_runtime_gate`).
      headers: layerHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ ...view, checks }),
      keepalive,
      signal: keepalive ? undefined : globalThis.AbortSignal.timeout(REPORT_MS),
    }).catch(() => {});
  }

  function report({ inspect = false, keepalive = false } = {}) {
    // A public website visitor has no private page until they act. Optional
    // observations cannot start a container merely to collect context.
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
      view.color_scheme,
    ]);
    if (
      view.visible &&
      pageReadiness() === null &&
      (inspect || basis !== checkedBasis)
    ) {
      if (reading) {
        checks = readChecks(view);
        checkedBasis = basis;
      } else if (!loading) {
        loadReading()
          .then(schedule)
          .catch(() => {
            // No checks is explicit in context; retry on the next report.
            loading = null;
          });
      }
    }
    // A change that leaves the reading as it stood sends nothing; the heartbeat keeps
    // it live.
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
  // Let the presented frame paint before importing or measuring checks.
  schedule();
}
