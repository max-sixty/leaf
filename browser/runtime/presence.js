// Every timestamp the page renders was written by its server. Keep the browser's one
// measured offset here, beside the two public readings that depend on it, so no seat can
// accidentally render against a second clock.
import { computed, signal } from "/runtime/framework.js";
import { tick } from "./version-signal.js";

let clockSkew = 0;
// A native dependency for the shared clock's temporal readings.
const pulse = signal(0);
// The moment a reading answers for while one made at a moment already past is read
// again (`atClock`), else none.
/** @type {number | null} */
let pinned = null;
const serverNow = () => pinned ?? Date.now() + clockSkew;
// The calibrated server time now, as a reading made now answers for it.
export const clockNow = () => serverNow();
// `read` again at the moment `at`, as a standing preview reads its target again with the
// clock it first read (preview.js), so a presentation whose only change is the clock
// changes nothing it says: every clock reading inside answers for `at`.
/** @template T @param {number} at @param {() => T} read @returns {T} */
export function atClock(at, read) {
  const was = pinned;
  pinned = at;
  try {
    return read();
  } finally {
    pinned = was;
  }
}
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

// The clock time behind an age or a time, in the reader's own zone: "Sat 15 Aug 2026,
// 14:02 PT". An age says how long ago, and a reader checking a message against a
// commit, a meeting or a log line needs when. The day before its month and a 24-hour
// clock read one way to every reader, and the zone is the one the reader's browser
// keeps, named as briefly as the platform names it. The instant is the server's, as
// written, so no skew applies.
/** @param {string | null | undefined} ts */
export function clockTime(ts) {
  const at = new Date(ts ?? NaN);
  if (Number.isNaN(at.getTime())) return "";
  const part = clockParts(at);
  return `${part.weekday} ${part.day} ${part.month} ${part.year}, ${part.hour}:${part.minute} ${part.timeZoneName}`;
}
/** @param {Date} at */
const clockParts = (at) =>
  Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZoneName: "shortGeneric",
    })
      .formatToParts(at)
      .map(({ type, value }) => [type, value]),
  );
// The reader's calendar day an instant falls on, counted in days, so consecutive days
// differ by one.
/** @param {Date} at */
const dayOf = (at) =>
  Math.round(Date.UTC(at.getFullYear(), at.getMonth(), at.getDate()) / 86400000);

// When a message was said: its clock time in the reader's zone, and its day unless
// that is today ("17:52", "Yesterday 17:52", "13 Nov 15:29"), which its preview names
// with the weekday and zone (`clockTime`). A conversation says times, not ages,
// because each reply says what was true when it was sent ("I'm building it now"), and
// an age rounds to its unit, so replies hours apart both read "1d ago" a day later.
// Each time names its own day, so one read alone, in a sticky head or below the first
// message scrolled away, is never taken for today's.
/** @param {string | null | undefined} ts
 * @returns {{day: string, clock: string} | null} */
export function saidAt(ts) {
  const at = new Date(ts ?? NaN);
  if (Number.isNaN(at.getTime())) return null;
  const clock = [at.getHours(), at.getMinutes()]
    .map((figure) => String(figure).padStart(2, "0"))
    .join(":");
  const day = clockValue((now) => {
    const today = dayOf(new Date(now));
    if (dayOf(at) === today) return "";
    if (dayOf(at) === today - 1) return "Yesterday";
    const part = clockParts(at);
    const year =
      at.getFullYear() === new Date(now).getFullYear() ? "" : ` ${part.year}`;
    return `${part.day} ${part.month}${year}`;
  });
  return { day, clock };
}
// What an age or a time previews (preview.js): the clock time, day and zone of the
// instant its `<time>` holds, so every one the page draws declares one function and
// holds its instant once, in `datetime`, where the platform keeps it.
/** @this {Element} @returns {import("./preview.js").Preview | null} */
export function agePreview() {
  const at = clockTime(this.getAttribute("datetime"));
  return at ? { name: at } : null;
}

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
// `activityTransitionAt` is when, on the server's clock, the page's activity in an
// answer can next change without any file moving, or Infinity when none is timed. A
// neighbour's needs no clock here: its own server republishes its row at its
// transition, which moves the pages reading the news names (live-leaves.js).
/** @param {import("../types/contract.js").ServedState | null} state */
export const activityTransitionAt = (state) => {
  const at = state?.activity.next_transition_at;
  return at ? Date.parse(at) : Infinity;
};
/** @param {import("../types/contract.js").ServedState | null} state */
export const activityTransitionDue = (state) =>
  serverNow() >= activityTransitionAt(state);
