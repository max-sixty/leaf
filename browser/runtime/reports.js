/* The report feed exposed to widgets and chrome.

   Projection answers where state stands. Some modules also need to narrate how the state
   arrived or when it was last reported. They read that through the exported sequence
   helpers, not through raw `events`.

   `reportSequence(target)` is the one reading of news about an item. Its target is
   either a widget element or an explicit `{kind, id}` pair; a bare id is not an identity
   and is rejected because a thread and a widget may spell theirs alike. With no target
   it returns the whole ordered feed. Each entry is a worker's report from the
   append-only log, in one envelope: `id`, typed `target`, `source`, `action`,
   structured `detail`, declared human-readable `text`, `ts`, attribution,
   `disposition`, and the report's version and sequence. The work the agent has in hand
   is no report: it is the served workflows' Working stage and the open to-dos' `running`
   start.

   A report holds until a stamped revision's note absorbs or overrules it. The closed
   disposition is `effective` when a report contributes to current state on its semantic
   coordinate, `outranked` when it still needs source-specific settlement but a newer
   report on its coordinate takes precedence, and `settled` when that authority answers
   it. An older unabsorbed report can therefore be outranked by a newer report on its
   coordinate while a version still owes it an answer. Settled entries remain in the feed
   when their source retains history. A module showing freshness therefore still sees
   when the log last heard from a worker after a stamp absorbs the worker's report.

   An agent-written x-state verb may declare `text: true`, which requires each report
   to carry non-empty `detail.text`. That is the envelope's `text`; consumers never
   infer prose from a field, verb, or widget name. The state boundary exposes it once.

   `reportSequence` filters the server-normalized report feed, and `readHistory` selects
   the history reading. A LeafElement reads them in render(), so Lit follows both
   initial state and later publications. `reportsReady(target)` holds that render until
   the projection has committed every report coordinate its target holds: no renderer
   narrates a report the widget has not yet painted.

   Accepted and local attempts publish one complete snapshot, including reads whose
   event list did not grow and definitive refusals that restore authoritative truth.
   Time-dependent paints are separate: a synchronous `ago` or `clockValue` reading is
   recorded with what else the paint read (`presence.js`), and the shared tick repaints
   only paints whose reading changed, while their owners stand, so a new widget owes no
   entry in a kernel list of clock consumers. A held state does not reset the
   measured server clock offset. Lit owns the rendering subscription and its connection
   lifetime.

   `active.revision` identifies the immutable document currently shown; `active.version`
   is its public stamp when it has one, otherwise null, and `active.label` is `vN`,
   `Draft after vN`, or `Draft`. The timestamp of the latest note for that revision is
   the freshness floor for authored state when no report exists. A page with no worker
   report is not timeless; its authored assertion is as old as its revision.

   The shared presentation coordinator owns the proof that guards report callbacks.
   Raw report and history readings remain direct semantic selections. */
import { currentProjection } from "./projection/state.js";
import {
  applicationRegionsPresented,
  projectionRegionsPresented,
  readPart,
} from "./semantic-state.js";
import { closestAcross } from "./passages.js";

/** @typedef {{kind: "widget" | "thread", id: string}} ReportTarget */
/** @param {unknown} target @returns {ReportTarget | null} */
function reportTarget(target) {
  if (target === null) return null;
  if (target instanceof Element) {
    if (target.id) return { kind: "widget", id: target.id };
  } else if (
    target !== null &&
    typeof target === "object" &&
    "kind" in target &&
    "id" in target &&
    (target.kind === "widget" || target.kind === "thread") &&
    typeof target.id === "string" &&
    target.id
  ) {
    return { kind: target.kind, id: target.id };
  }
  throw new TypeError(
    "report target must be a widget element or {kind: 'widget' | 'thread', id}",
  );
}
/** @param {ReportTarget | null} target */
const targetKey = (target) =>
  target ? JSON.stringify([target.kind, target.id]) : null;
// Each target's reports through a selection of its own, so a watcher reading one
// target's sequence repaints when that target's reports move and no other's.
/** @type {Map<string | null, () => readonly import("../types/contract.js").ServedView["reports"][number][]>} */
const reportsByTarget = new Map();
/** @param {string | null} key */
const reportsFor = (key) => {
  let read = reportsByTarget.get(key);
  if (!read) {
    read = readPart((root) =>
      (root.effective.view?.reports ?? []).filter(
        (report) => key === null || targetKey(report.target) === key,
      ),
    );
    reportsByTarget.set(key, read);
  }
  return read();
};
/** @param {Element | ReportTarget | null} [target] */
export const reportSequence = (target = null) =>
  reportsFor(targetKey(reportTarget(target))).map((report) => structuredClone(report));

const publishedAt = readPart((root) => root.effective.view?.published_at ?? null);
/** @param {Element} el */
export const saidAt = (el) => {
  /** @type {HTMLTimeElement | null | undefined} */
  const time = closestAcross(el, ".lf-msg")?.querySelector(
    ":scope > .lf-msg-head time",
  );
  return time?.dateTime || publishedAt();
};

// The server's history reading: `events`, the newest logged events, newest first,
// each already carrying its thread, whether it was undone, and a gesture's words as its
// own document had them, and the application's `phase`, so a widget never replaces a
// reading it retained with the empty one a page shows before it is `ready`. The server
// sends the events only to a page holding a widget that declares `x-history`; elsewhere
// they are empty.
export const readHistory = readPart((root) => ({
  phase: root.phase,
  events: root.authoritative?.browser.history ?? [],
}));

// A report can speak only once the renderer of its widget and coordinate chrome
// have committed. Required asynchronous preparation is the same coordinator region
// used by startup and pending release, not a second coordinate/event-id commit map.
/** @param {Element | ReportTarget | null} [target] */
export const reportsPresented = (target = null) =>
  projectionRegionsPresented([...reportWidgets(target)]);

/** @param {Element | ReportTarget | null} target */
const reportWidgets = (target) => {
  const key = targetKey(reportTarget(target));
  const widgets = new Set(target instanceof Element ? [target.id] : []);
  for (const entry of currentProjection().classified.values()) {
    if (entry.terminal || entry.e.kind !== "report") continue;
    if (key === null || key === targetKey({ kind: "widget", id: entry.e.widget }))
      widgets.add(entry.e.widget);
  }
  return widgets;
};

// The same proof for a widget that narrates its reports in the update that draws its
// state (a `LeafElement`, leaf-element.js): that update is its render, so only its
// preparation, the coordinate chrome, and any other widget the reports name must have
// committed. Read in a render, the answer is followed as the time a render shows is.
/** @param {import("./leaf-element.js").LeafElement} target */
export const reportsReady = (target) =>
  target.whenReady(() =>
    applicationRegionsPresented([
      "projection:chrome",
      `widget:${target.id}:preparation`,
      ...[...reportWidgets(target)]
        .filter((widget) => widget !== target.id)
        .flatMap((widget) => [
          `widget:${widget}:render`,
          `widget:${widget}:preparation`,
        ]),
    ]),
  );
