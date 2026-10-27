// @ts-check
/* Later's facts the browser reads off a record, and its times on the user's clock, with
   no DOM or application service, so the publisher, the tally, the panel and packages
   share one reading (`src/leaf/later.py` owns what a Later means).

   A record's `later` is the chain of Laters in force on it, newest first, each naming
   the one it replaced as `beneath`, so taking one back is drawn by dropping it from the
   chain (`withoutLaters`) rather than by guessing what the log would say. */

/** @typedef {import("../../types/contract.js").ServedLater} Later */

/** Whether a Later that hasn't brought it back sets `record` aside: open, with no next
 * actor while the Later stands.
 * @param {{status: string, next_actor: string | null, later?: Later | null}} record */
export const setAside = (record) =>
  record.status === "open" &&
  record.next_actor === null &&
  Boolean(record.later && !record.later.returned);

/** The chain `later` with the Laters `undone` names taken out.
 * @param {Later | null | undefined} later @param {ReadonlySet<string>} undone
 * @returns {Later | null} */
export function withoutLaters(later, undone) {
  if (!later) return null;
  const beneath = withoutLaters(later.beneath, undone);
  return later.event && undone.has(later.event.id) ? beneath : { ...later, beneath };
}

// Today's or a later day's hour on the user's clock. `setDate` and `setHours` keep
// the wall-clock hour across a change of daylight saving time.
/** @param {Date} now @param {number} days @param {number} hour */
const dayAt = (now, days, hour) => {
  const at = new Date(now);
  at.setDate(at.getDate() + days);
  at.setHours(hour, 0, 0, 0);
  return at;
};
/** @param {Date} at */
const clock = (at) => at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
/** @param {Date} at */
const weekday = (at) => at.toLocaleDateString([], { weekday: "long" });

/** The times Later offers at `now`, each with the instant it names: an hour on, this
 * evening while it is still before five, tomorrow morning, and next Monday morning
 * where that isn't tomorrow.
 * @param {Date} now @returns {{label: string, until: Date}[]} */
export function laterTimes(now) {
  const choices = [{ label: "In an hour", until: new Date(+now + 3_600_000) }];
  if (now.getHours() < 17) {
    const evening = dayAt(now, 0, 18);
    choices.push({ label: `This evening, ${clock(evening)}`, until: evening });
  }
  const tomorrow = dayAt(now, 1, 9);
  choices.push({ label: `Tomorrow, ${clock(tomorrow)}`, until: tomorrow });
  const monday = (8 - now.getDay()) % 7 || 7;
  if (monday > 1) {
    const at = dayAt(now, monday, 9);
    choices.push({ label: `${weekday(at)}, ${clock(at)}`, until: at });
  }
  return choices;
}

/** When a Later on a clock brings its records back, said from `now`: "Back at 6:00 PM",
 * "Back tomorrow at 9:00 AM", "Back Monday at 9:00 AM", or a date beyond a week.
 * @param {string} until @param {Date} now */
export function untilWords(until, now) {
  const at = new Date(until);
  const days = Math.round(
    (dayAt(at, 0, 12).getTime() - dayAt(now, 0, 12).getTime()) / 86_400_000,
  );
  const day =
    days <= 0
      ? ""
      : days === 1
        ? "tomorrow "
        : days < 7
          ? `${weekday(at)} `
          : `${at.toLocaleDateString([], { month: "short", day: "numeric" })} `;
  return `Back ${day}at ${clock(at)}`;
}
