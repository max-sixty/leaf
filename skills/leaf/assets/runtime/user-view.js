/* A document's disposable view context for its author. Nothing here changes page
   state, layout, or the event log. Geometry stays with its mechanical owners;
   passive checks run only after presentation, never as a presentation prerequisite.
   An unallocated document has no view to report; normal observation resumes when
   its viewport has room. A document id is deliberately not stored: duplicated tabs
   must never share a lease. */
import { offlineInteractive, passiveSample, pageUrl, runtime } from "./context.js";
import { seenRect, shownWindow } from "./geometry.js";
import { sessionIsActive } from "./layer-client.js";
import { onMotionPreferenceChange, reducedMotion } from "./motion.js";
import { pageReadiness } from "./presentation.js";
import { coarsePointer } from "./pointer.js";
import { readingRegions } from "./reading-regions.js";
import { watchSemantic } from "./semantic-state.js";

const REPORT_MS = 10_000;
const QUIET_MS = 300;
const rectangle = ({ x, y, width, height }) => ({ x, y, width, height });

export function observeUserView() {
  if (offlineInteractive || passiveSample) return;
  const session = [...crypto.getRandomValues(new Uint8Array(16))]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  const dark = matchMedia("(prefers-color-scheme: dark)");
  let sequence = 0;
  let pending = null;
  let reading = null;
  let loading = null;
  let checks = null;
  let checkedBasis = null;

  function context() {
    const visual = window.visualViewport;
    const viewport = {
      width: document.documentElement.clientWidth,
      height: document.documentElement.clientHeight,
    };
    if (
      viewport.width <= 0 ||
      viewport.height <= 0 ||
      visual.width <= 0 ||
      visual.height <= 0
    )
      return null;
    const clips = new Map();
    const schemes = getComputedStyle(document.documentElement).colorScheme.split(/\s+/);
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
        scale: visual.scale,
      },
      shown_window: rectangle(shownWindow()),
      color_scheme:
        schemes.includes("dark") && (dark.matches || !schemes.includes("light"))
          ? "dark"
          : "light",
      reduced_motion: reducedMotion(),
      pointer: coarsePointer.matches ? "coarse" : "fine",
      scroll: { x: window.scrollX, y: window.scrollY },
      visible_regions: readingRegions()
        .filter(({ body }) => seenRect(body, clips) !== null)
        .map(({ id }) => id),
    };
  }

  function send(view, keepalive = false) {
    // Optional context has no delivery obligation. A failed report expires at the
    // server; the next observation replaces it rather than queuing old geometry.
    void fetch(pageUrl("api/user-view"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
        const open = Object.entries(runtime.registry)
          .filter(([, entry]) => ["markup", "members"].includes(entry["x-content"]))
          .map(([tag]) => tag);
        checks = {
          sequence: view.sequence,
          revision: view.revision,
          through_seq: view.through_seq,
          viewport: view.viewport,
          visual_viewport: view.visual_viewport,
          shown_window: view.shown_window,
          color_scheme: view.color_scheme,
          reading: reading(open),
        };
        checkedBasis = basis;
      } else if (!loading) {
        loading = import("/checks/view.js")
          .then((module) => {
            reading = module.readViewChecks;
            schedule();
          })
          .catch(() => {
            // No checks is explicit in context; retry on the next report.
            loading = null;
          });
      }
    }
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
  window.addEventListener("resize", schedule);
  window.addEventListener("pageshow", schedule);
  document.addEventListener("scroll", schedule, { passive: true, capture: true });
  window.visualViewport.addEventListener("resize", schedule);
  window.visualViewport.addEventListener("scroll", schedule);
  onMotionPreferenceChange(schedule);
  for (const preference of [dark, coarsePointer])
    preference.addEventListener("change", schedule);
  setInterval(() => {
    if (document.visibilityState !== "hidden") report({ inspect: true });
  }, REPORT_MS);
  // Let the presented frame paint before importing or measuring checks.
  schedule();
}
