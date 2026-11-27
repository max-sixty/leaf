// Every timestamp the page renders was written by its server. Keep the browser's one
// measured offset here, beside the two public readings that depend on it, so no seat can
// accidentally render against a second clock.
import { computed, signal } from "/vendor/signals-core.js";
import { tick } from "./version-signal.js";
import type { Preview } from "../base/preview-declaration.js";
import type { ServedState } from "../../types/contract.js";

let clockSkew = 0;
// A native dependency for the shared clock's temporal readings.
const pulse = signal(0);
// The moment a reading answers for while one made at a moment already past is read
// again (`atClock`), else none.
let pinned: number | null = null;
const serverNow = () => pinned ?? Date.now() + clockSkew;
// The calibrated server time now, as a reading made now answers for it.
export const clockNow = () => serverNow();
// `read` again at the moment `at`, as a standing preview reads its target again with the
// clock it first read (annotations/preview.js), so a presentation whose only change is the clock
// changes nothing it says: every clock reading inside answers for `at`.
export function atClock<T>(at: number, read: () => T): T {
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
export const clockValue = <T>(read: (now: number) => T) =>
  computed(() => {
    pulse.value;
    return read(serverNow());
  }).value;

export async function tickClock(
  reportError: (reason: unknown, context: string) => unknown,
) {
  try {
    tick(pulse);
  } catch (error) {
    reportError(error, "clock paint failed");
  }
}

export const observeServerNow = (now: string | null | undefined) => {
  if (now) clockSkew = Date.parse(now) - Date.now();
};
// How long ago a server timestamp was, rounded to its nearest unit, in the one wording
// every age on the page has: `ago` for a sentence, which is also what an author's
// `lf-age` draws (age.js), and `shortAgo` where a seat has room for the figure alone, so
// two seats never give one moment two different ages. A timestamp that names no moment
// has no age.
const age = (ts: string | null | undefined, compact: boolean) =>
  clockValue((now) => {
    const then = Date.parse(ts ?? "");
    return Number.isNaN(then) ? "" : ageWords(elapsed(then, now), compact);
  });
export const ago = (ts: string | null | undefined) => age(ts, false);
export const shortAgo = (ts: string | null | undefined) => age(ts, true);
// The figure and unit of an age, none under 45 seconds. The rounded figure picks the
// unit, so 59 minutes and 40 seconds reads "1h", never "60m".
const elapsed = (then: number, now: number): [number, "m" | "h" | "d"] | null => {
  const secs = Math.max(0, (now - then) / 1000);
  if (secs < 45) return null;
  const minutes = Math.round(secs / 60);
  if (minutes < 60) return [minutes, "m"];
  const hours = Math.round(secs / 3600);
  return hours < 24 ? [hours, "h"] : [Math.round(secs / 86400), "d"];
};
const ageWords = (span: ReturnType<typeof elapsed>, compact: boolean) =>
  span ? `${span[0]}${span[1]}${compact ? "" : " ago"}` : compact ? "now" : "just now";

// A time of day as the reader's platform writes it: its locale's hour cycle, in the
// zone the browser keeps ("3:24 PM" in American English, "15:24" in British), as are
// the dates below. A reader checks a time against their own clock, calendar and logs,
// which already read that way. The instant is the server's, as written, so no skew
// applies.
export const timeOfDay = (at: Date | number) =>
  new Date(at).toLocaleTimeString(undefined, { timeStyle: "short" });

// The clock time behind an age or a time, with its weekday, date and zone, named as
// briefly as the platform names it: "Sat, Aug 15, 2026, 2:02 PM PT". An age says how
// long ago, and a reader checking a message against a commit, a meeting or a log line
// needs when.
export function clockTime(ts: string | null | undefined) {
  const at = new Date(ts ?? NaN);
  if (Number.isNaN(at.getTime())) return "";
  return at.toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "shortGeneric",
  });
}
// The reader's calendar day an instant falls on, counted in days, so consecutive days
// differ by one.
const dayOf = (at: Date) =>
  Math.round(Date.UTC(at.getFullYear(), at.getMonth(), at.getDate()) / 86400000);

// When a message was said. Within the hour, how long ago ("just now", "12m ago"),
// which reads at a glance and is as exact as a clock to the minute. After that, its
// time of day, and its day unless that is today ("3:24 PM", "Yesterday 3:24 PM",
// "Nov 13 3:29 PM"), which its preview names with the weekday and zone
// (`clockTime`): each reply says what was true when it was sent ("I'm building it
// now"), and an age past the hour rounds to hours or days, so replies hours apart
// both read "1d ago" a day later. Each time names its own day, so one read alone, in
// a sticky head or below the first message scrolled away, is never taken for today's.
export function saidAt(
  ts: string | null | undefined,
): { day: string; time: string } | null {
  const at = new Date(ts ?? NaN);
  if (Number.isNaN(at.getTime())) return null;
  const recent = clockValue((now) => {
    const span = elapsed(at.getTime(), now);
    return !span || span[1] === "m" ? ageWords(span, false) : "";
  });
  if (recent) return { day: "", time: recent };
  const day = clockValue((now) => {
    const today = dayOf(new Date(now));
    if (dayOf(at) === today) return "";
    if (dayOf(at) === today - 1) return "Yesterday";
    const thisYear = at.getFullYear() === new Date(now).getFullYear();
    return at.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      ...(thisYear ? {} : { year: "numeric" }),
    });
  });
  return { day, time: timeOfDay(at) };
}
// What an age or a time previews (annotations/preview.js): the clock time, day and zone of the
// instant its element holds, a `<time>` or an `lf-age`, so every one the page draws
// declares one function and holds its instant once, in `datetime`, where the platform
// keeps it.
export function agePreview(this: Element): Preview | null {
  const at = clockTime(this.getAttribute("datetime"));
  return at ? { name: at } : null;
}

// How long working may go unheard before it reads as quiet. The server's activity fold
// owns the number and serves it beside `now`; until a state has arrived nothing is
// quiet, since there is no served clock to measure the silence against either.
let workingGrace: number | null = null;
export const observeWorkingGrace = (ms: number) => {
  workingGrace = ms;
};
export const quietSince = (ts: string | null | undefined) =>
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
// transition, which moves the pages reading the news names (host/live-leaves.js).
export const activityTransitionAt = (state: ServedState | null) => {
  const at = state?.activity.next_transition_at;
  return at ? Date.parse(at) : Infinity;
};
export const activityTransitionDue = (state: ServedState | null) =>
  serverNow() >= activityTransitionAt(state);
