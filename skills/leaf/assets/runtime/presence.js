// Every timestamp the page renders was written by its server. Keep the browser's one
// measured offset here, beside the two public readings that depend on it, so no seat can
// accidentally render against a second clock.
import { watchOwner } from "./arrivals.js";

let clockSkew = 0;
let clockReads = null;
const clockPaints = new Set();
export const serverNow = () => Date.now() + clockSkew;
// When a gesture was made, on the clock every other reading of a message uses. A
// message this page paints before the log names it still has to say when it was said,
// and the browser's own clock is the one reading that can disagree with the rest.
export const saidNow = () => new Date(serverNow()).toISOString();

// A clock reading is a displayed value or a temporal predicate, not raw wall time.
// Remember the readings made by each synchronous paint so the shared tick can wake
// only the paints whose answers changed. The callback receives the calibrated server-now
// milliseconds used by the comparison. Nested paints own their own dependencies.
export function clockValue(read) {
  const value = read(serverNow());
  clockReads?.push({ read, value });
  return value;
}

// A deferred presenter supplies `invalidate` to claim its next pass synchronously.
// Only calling the returned paint replaces its dependencies; invalidation retains
// them while that pass is queued or awaiting preparation. The claim's return is
// ignored: its presenter owns completion and failure; the clock owns direct paints.
// The paint's time readings follow its owner's lifetime (`watchOwner`): they pause
// while it is away and its return puts them back on the clock, so the next tick
// repaints what aged. `stop()` takes the paint off the clock until it paints again.
export function clocked(owner, paint, invalidate) {
  let args;
  let painted = false;
  let reads = [];
  let generation = 0;
  let standing = false;
  let stopLifetime = null;
  const entry = {
    owner,
    changed: () => reads.some(({ read, value }) => read(serverNow()) !== value),
    refresh: () => {
      if (!painted) return;
      if (invalidate) invalidate();
      else return render(...args);
    },
  };
  const listen = () => {
    if (standing && reads.length) clockPaints.add(entry);
    else clockPaints.delete(entry);
  };
  function render(...next) {
    const painting = ++generation;
    args = next;
    painted = true;
    const outer = clockReads;
    clockReads = [];
    try {
      return paint(...args);
    } finally {
      const nextReads = clockReads;
      clockReads = outer;
      if (painting === generation) {
        reads = nextReads;
        if (reads.length)
          stopLifetime ??= watchOwner(owner, {
            connect() {
              standing = true;
              listen();
            },
            disconnect() {
              standing = false;
              listen();
            },
          });
        listen();
      }
    }
  }
  render.stop = () => {
    generation += 1;
    reads = [];
    stopLifetime?.();
    stopLifetime = null;
  };
  render.refresh = entry.refresh;
  return render;
}

/** The paint of one reading at a time, kept across the owner's departures, and the one
 * rule for what a returning owner is drawn again. Calling `paint(key, ...args)` draws
 * `draw(...args)` through `clocked`, unless `key` names the reading already painted: a
 * return repaints only what changed while away. A drawn reading stands, failed or not,
 * so a refusal is not reported twice; a draw whose returned promise does not settle
 * while its owner stands was cut short, and the next call draws it again. `owes(key)`
 * says whether `paint(key)` would draw, `forget()` owes the next call a draw,
 * `refresh()` redraws the last reading, at once or on the return, and `stop()` retires
 * the paint. Its owner's subscriptions stay the caller's. A deferred presenter passes
 * `invalidate`, as to `clocked`. */
export function readingPaint(owner, draw, invalidate) {
  const render = clocked(owner, draw, invalidate);
  let painted = false;
  let key;
  let pending = null;
  let stopped = false;
  const stopLifetime = watchOwner(owner, {
    disconnect() {
      if (pending) painted = false;
      pending = null;
    },
  });
  const owes = (next) => !painted || key !== next;
  const paint = (next, ...args) => {
    if (stopped || !owes(next)) return undefined;
    // Claim the reading before drawing, so a synchronous failure or a re-entrant call
    // cannot draw the same reading again.
    painted = true;
    key = next;
    pending = null;
    const result = render(...args);
    if (typeof result?.then === "function") {
      const mark = (pending = {});
      const settled = () => {
        if (pending !== mark) return;
        pending = null;
        if (!owner.isConnected) painted = false;
      };
      result.then(settled, settled);
    }
    return result;
  };
  paint.owes = owes;
  paint.forget = () => {
    painted = false;
  };
  // A refresh asked for while the owner is away is owed to its return.
  paint.refresh = () => {
    if (stopped) return undefined;
    if (owner.isConnected) return render.refresh();
    painted = false;
  };
  paint.stop = () => {
    stopped = true;
    stopLifetime();
    render.stop();
  };
  return paint;
}

export async function tickClock(reportError) {
  // Package paints are independent subscribers. A bad clock read or repaint must
  // not starve later subscribers or turn a healthy state feed back into polling.
  const settled = await Promise.allSettled(
    [...clockPaints].map(async (entry) => {
      // An owner removed before its departure reaches the arrival batch stays on the
      // clock until it does, and is not painted meanwhile.
      if (entry.owner.isConnected && entry.changed()) return entry.refresh();
    }),
  );
  for (const result of settled)
    if (result.status === "rejected") reportError(result.reason, "clock paint failed");
}

export const observeServerNow = (now) => {
  if (now) clockSkew = Date.parse(now) - Date.now();
};
export const JUST_NOW = "just now";
// How long ago a server timestamp was, rounded to its nearest unit, in the one wording
// the page and every package use: `ago` for a sentence, `shortAgo` where a seat has
// room for the figure alone, so two seats never give one moment two different ages.
const age = (ts, compact) =>
  clockValue((now) => {
    if (!ts) return "";
    const secs = Math.max(0, (now - new Date(ts).getTime()) / 1000);
    if (secs < 45) return compact ? "now" : JUST_NOW;
    const [count, unit] =
      secs < 3600
        ? [Math.round(secs / 60), "m"]
        : secs < 86400
          ? [Math.round(secs / 3600), "h"]
          : [Math.round(secs / 86400), "d"];
    return `${count}${unit}${compact ? "" : " ago"}`;
  });
export const ago = (ts) => age(ts, false);
export const shortAgo = (ts) => age(ts, true);

// How long working may go unheard before it reads as quiet. The server's activity fold
// owns the number and serves it beside `now`; until a state has arrived nothing is
// quiet, since there is no served clock to measure the silence against either.
let workingGrace = null;
export const observeWorkingGrace = (ms) => {
  workingGrace = ms;
};
export const quietSince = (ts) =>
  clockValue(
    (now) =>
      workingGrace !== null &&
      Boolean(ts) &&
      now - new Date(ts).getTime() >= workingGrace,
  );

// Temporal policy belongs to the server's canonical activity fold. The browser uses
// its calibrated copy of server time only to ask for the next projection when that
// fold says an answer can change; it never decides what the new answer is.
// `activityTransitionAt` is when, on the server's clock, the earliest activity in an
// answer can next change without any file moving, or Infinity when none is timed.
export const activityTransitionAt = (state) =>
  Math.min(
    ...[state?.activity, ...(state?.others ?? []).map((entry) => entry.activity)]
      .filter((activity) => activity?.next_transition_at)
      .map((activity) => Date.parse(activity.next_transition_at)),
  );
export const activityTransitionDue = (state) =>
  serverNow() >= activityTransitionAt(state);
