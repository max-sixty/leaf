// Every timestamp the page renders was written by its server. Keep the browser's one
// measured offset here, beside the two public readings that depend on it, so no seat can
// accidentally render against a second clock.
import { computed, signal } from "/runtime/framework.js";
import { tick } from "./version-signal.js";

let clockSkew = 0;
// A native dependency for the shared clock's temporal readings.
const pulse = signal(0);
const serverNow = () => Date.now() + clockSkew;
// When a gesture was made, on the clock every other reading of a message uses. A
// message this page paints before the log names it still has to say when it was said,
// and the browser's own clock is the one reading that can disagree with the rest.
export const saidNow = () => new Date(serverNow()).toISOString();

// A clock reading is a displayed value or a temporal predicate, not raw wall time. It is
// recorded in the collection of whatever paint reads it, beside the parts of the
// publication that paint read, so a watcher or a region follows the
// time it shows by the rule it follows those by, and the shared tick wakes only the
// paints whose answers changed. The callback receives the calibrated server-now
// milliseconds used by the comparison.
/** @template T @param {(now: number) => T} read */
export const clockValue = (read) =>
  computed(() => {
    pulse.value;
    return read(serverNow());
  }).value;

/** @param {typeof import("./layer-client.js").reportCarried} reportError */
export async function tickClock(reportError) {
  try {
    tick(pulse);
  } catch (error) {
    reportError(error, "clock paint failed");
  }
}

/** @param {string | null | undefined} now */
export const observeServerNow = (now) => {
  if (now) clockSkew = Date.parse(now) - Date.now();
};
// How long ago a server timestamp was, rounded to its nearest unit, in the one wording
// the page and every package use: `ago` for a sentence, `shortAgo` where a seat has
// room for the figure alone, so two seats never give one moment two different ages.
/** @param {string | null | undefined} ts @param {boolean} compact */
const age = (ts, compact) =>
  clockValue((now) => {
    if (!ts) return "";
    const secs = Math.max(0, (now - new Date(ts).getTime()) / 1000);
    if (secs < 45) return compact ? "now" : "just now";
    const [count, unit] =
      secs < 3600
        ? [Math.round(secs / 60), "m"]
        : secs < 86400
          ? [Math.round(secs / 3600), "h"]
          : [Math.round(secs / 86400), "d"];
    return `${count}${unit}${compact ? "" : " ago"}`;
  });
/** @param {string | null | undefined} ts */
export const ago = (ts) => age(ts, false);
/** @param {string | null | undefined} ts */
export const shortAgo = (ts) => age(ts, true);

// How long working may go unheard before it reads as quiet. The server's activity fold
// owns the number and serves it beside `now`; until a state has arrived nothing is
// quiet, since there is no served clock to measure the silence against either.
/** @type {number | null} */
let workingGrace = null;
/** @param {number} ms */
export const observeWorkingGrace = (ms) => {
  workingGrace = ms;
};
/** @param {string | null | undefined} ts */
export const quietSince = (ts) =>
  clockValue(
    (now) =>
      workingGrace !== null && !!ts && now - new Date(ts).getTime() >= workingGrace,
  );

// Temporal policy belongs to the server's canonical activity fold. The browser uses
// its calibrated copy of server time only to ask for the next projection when that
// fold says an answer can change; it never decides what the new answer is.
// `activityTransitionAt` is when, on the server's clock, the earliest activity in an
// answer can next change without any file moving, or Infinity when none is timed.
/** @param {import("../types/contract.js").ServedState | null} state */
export const activityTransitionAt = (state) =>
  Math.min(
    ...[
      state?.activity,
      ...(state?.others ?? []).map((entry) => entry?.activity),
    ].flatMap((activity) =>
      activity?.next_transition_at ? [Date.parse(activity.next_transition_at)] : [],
    ),
  );
/** @param {import("../types/contract.js").ServedState | null} state */
export const activityTransitionDue = (state) =>
  serverNow() >= activityTransitionAt(state);
