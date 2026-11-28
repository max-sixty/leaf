// Compiled from reports.ts by build/typescript.mjs; edit that file.
/* The report feed exposed to widgets and chrome.

   Projection answers where state stands. Some modules also need to narrate how the state
   arrived or when it was last reported. They read that through `readReports`, not
   through raw `events`.

   `readReports(target)` is a package's one reading of news about an item, `{phase,
   reports}`; `reportSequence(target)` is its `reports`, which the runtime's own readers
   (work.js) select without a phase. The target is either a widget element or an
   explicit `{kind, id}` pair; a bare id is not an identity and is rejected because a
   thread and a widget may spell theirs alike. With no target it reads the whole ordered
   feed. Each entry is a worker's report from the
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

   An agent-written verb (`verbs`) may declare `text: true`, which requires each report
   to carry non-empty `detail.text`. That is the envelope's `text`; consumers never
   infer prose from a field, verb, or widget name. The state boundary exposes it once.

   `readReports` filters the server-normalized report feed, and `readHistory` selects
   the history reading. A LeafElement's render() or an Effect UI component's inputs
   reads them, so the widget follows both initial state and later publications. A reading's `phase` is the page's, as
   `readHistory`'s is, so a render never narrates the empty feed a page holds before the
   server's reading. A widget's reading, which it makes as it draws its `state`, in a
   render or a plain element's setter, also waits until the projection has committed
   every report coordinate the widget holds: no renderer narrates a report the widget
   has not yet painted. Leaf sets the widget's `state` again once that reading is
   ready, so an element that follows no signal draws it too.

   Accepted and local attempts publish one complete snapshot, including reads whose
   event list did not grow and definitive refusals that restore authoritative truth.
   Time-dependent paints are separate: a synchronous `ago` or `clockValue` reading is
   recorded with what else the paint read (`state/presence.js`), and the shared tick repaints
   only paints whose reading changed, while their owners stand, so a new widget owes no
   entry in a kernel list of clock consumers. A held state does not reset the
   measured server clock offset. The renderer owns the subscription and its connection
   lifetime.

   `active.revision` identifies the immutable document currently shown; `active.version`
   is its public stamp when it has one, otherwise null, and `active.label` is `vN`,
   `Draft after vN`, or `Draft`. The timestamp of the latest note for that revision is
   the freshness floor for authored state when no report exists. A page with no worker
   report is not timeless; its authored assertion is as old as its revision.

   The shared presentation coordinator owns the proof that guards report callbacks.
   Raw report and history readings remain direct semantic selections. */
import {
  applicationRegionsPresented,
  readPart,
  watchPresentation,
} from "../state/semantic-state.js";
import { closestAcross } from "../lib/shadow-tree.js";
import { runtime } from "../state/context.js";
import { stateAgain } from "./element-integration.js";

function reportTarget(target) {
  if (target === null) return null;
  if (target instanceof Element) {
    if (target.id) return { kind: "widget", id: target.id };
  } else if (
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
const targetKey = (target) =>
  target ? JSON.stringify([target.kind, target.id]) : null;
// Each target's reports through a selection of its own, so a watcher reading one
// target's sequence repaints when that target's reports move and no other's.
const reportsByTarget = new Map();
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
export const reportSequence = (target = null) =>
  reportsFor(targetKey(reportTarget(target))).map((report) => structuredClone(report));

const publishedAt = readPart((root) => root.effective.view?.published_at ?? null);
export const saidAt = (el) => {
  const time = closestAcross(el, ".lf-msg")?.querySelector(
    ":scope > .lf-msg-head time",
  );
  return time?.dateTime || publishedAt();
};

// The server's history reading: `events`, the newest logged events, newest first, each
// already carrying its thread, whether it was undone, and a gesture's words as its own
// document had them, and the application's `phase`, so a widget never replaces a
// reading it retained with the empty one a page shows before it is `ready`. The server
// sends the events only to a page holding a widget that declares `history`;
// elsewhere they are empty.
export const readHistory = readPart((root) => ({
  phase: root.phase,
  events: root.authoritative?.browser.history ?? [],
}));

// A report can speak only once the server's reading has arrived and the renderer of
// its widget and coordinate chrome have committed, with any required asynchronous
// preparation, the same coordinator region startup and pending release use: a report
// names its widget by id, so the reports on a widget name no other. A widget asks as
// it draws its `state`, which is its own render, so only its preparation and the
// coordinate chrome must have committed. A draw told no is owed another once they
// have, which Leaf starts as it starts any element's draw, by setting the element's
// `state` again (`stateAgain`, element-integration.js). Leaf makes that set before
// any microtask runs, and every reading until then is told yes, since a draw that
// begins preparation before it reads would never find the region free. An element
// that left is set as it returns, and asks afresh then. An element Leaf sets no
// `state` on has no report of its own and no draw Leaf can start, so it waits on
// nothing here.
const proven = new WeakSet();
const waiting = new WeakSet();
const committed = (target) =>
  runtime.statePhase === "ready" &&
  applicationRegionsPresented(["projection:chrome", `widget:${target.id}:preparation`]);
const reportsReady = (target) => {
  const again = stateAgain(target);
  if (!again || proven.has(target) || committed(target)) return true;
  if (waiting.has(target)) return false;
  waiting.add(target);
  // The watch's first call comes before it has returned its stop.
  const watch = { stop: null, done: false };
  watch.stop = watchPresentation(() => {
    if (watch.done || (target.isConnected && !committed(target))) return;
    watch.done = true;
    watch.stop?.();
    waiting.delete(target);
    if (target.isConnected) {
      proven.add(target);
      queueMicrotask(() => proven.delete(target));
    }
    again();
  });
  if (watch.done) watch.stop();
  return false;
};

// A widget's reading, as it draws its `state`, also waits on its report coordinates
// (`reportsReady`), which it asks in every phase: a draw told that the page waits is
// owed another too. A thread's, or the whole feed's, phase is the page's.
export const readReports = (target = null) => {
  const reports = reportSequence(target);
  const phase = runtime.statePhase;
  const waits = target instanceof Element && !reportsReady(target);
  return { phase: waits && phase === "ready" ? "waiting" : phase, reports };
};
