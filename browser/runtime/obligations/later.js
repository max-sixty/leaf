/* Later: what the user sets aside, the choices that bring it back, and the words for
   where it stands.

   The server owns Later (`src/leaf/later.py`): a `later` event names the obligation
   records one card or On me row carries and one condition, `until` an instant or `after`
   an item on the agent's list, and its reading decides when they come back. The
   publisher draws the gesture's own result in the task that makes it, the records off
   On me and off a deck's pass (framework/application.js, `localLaters`), and an Undo
   withdraws it like any gesture.

   One control offers it wherever it stands, a deck card's bar or an On me card
   (`laterControl`): the clock, Later's symbol, with the platform's select over it, so a
   key, a pointer and a finger each open the same list of words, as the panel's
   arrangement chooser does. Its choices are times on the user's own clock, then the
   items on the agent's list, read from On <agent> as it stands when the list opens, so
   "when the agent finishes" names work the server already knows by id, never words.
   A time is reckoned when it is chosen, so a list left open an hour still means an hour
   from the choice.

   Rejected: a second row of buttons, one per choice, which put five presses beside
   every card for a gesture most cards never take; and a free date field, which wants
   its own popup on every platform for a choice the presets cover. */
import { html, live, nothing } from "/runtime/framework.js";
import { iconTemplate } from "../icons.js";
import { agentName } from "../semantic-state.js";
import { readQueues } from "../queue-api.js";
import { queueTitle } from "../queue-title.js";
import { excerptWords } from "../words.js";
import { clockValue } from "../presence.js";

export const LATER = "Later until…";

// Today's or a later day's hour on the user's clock.
const dayAt = (now, days, hour) => {
  const at = new Date(now);
  at.setDate(at.getDate() + days);
  at.setHours(hour, 0, 0, 0);
  return at;
};
const clock = (at) => at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const weekday = (at) => at.toLocaleDateString([], { weekday: "long" });

// The times Later offers from `now`: an hour on, this evening while it is still
// afternoon, tomorrow morning, and next week's first morning.
function times(now) {
  const choices = [{ label: "In an hour", until: (at) => new Date(+at + 3_600_000) }];
  if (now.getHours() < 17)
    choices.push({
      label: `This evening, ${clock(dayAt(now, 0, 18))}`,
      until: (at) => dayAt(at, 0, 18),
    });
  choices.push({
    label: `Tomorrow, ${clock(dayAt(now, 1, 9))}`,
    until: (at) => dayAt(at, 1, 9),
  });
  const monday = (8 - now.getDay()) % 7 || 7;
  if (monday > 1)
    choices.push({
      label: `${weekday(dayAt(now, monday, 9))}, ${clock(dayAt(now, monday, 9))}`,
      until: (at) => dayAt(at, (8 - at.getDay()) % 7 || 7, 9),
    });
  return choices;
}

// The items on the agent's list Later can wait for, each by the title On <agent> gives it.
function agentItems() {
  const queues = readQueues();
  if (queues.phase !== "ready") return [];
  return queues.on_agent.map((row) => ({
    label: excerptWords(queueTitle(row), 60),
    after: row.id,
  }));
}

/** The condition a choice sets, reckoned at `at`. */
const condition = (choice, at) =>
  "after" in choice
    ? { after: choice.after }
    : { until: choice.until(at).toISOString() };

/** Later's control for the records `ids`: choosing sets them aside through `later`
 * (`obligationActions.later`) and then calls `chosen`, as a deck sends its card on. */
export function laterControl(ids, later, chosen = () => {}) {
  if (!ids.length) return nothing;
  const offered = [...times(new Date()), ...agentItems()];
  const work = offered.filter((choice) => "after" in choice);
  const option = (choice) =>
    html`<option value=${offered.indexOf(choice)}>${choice.label}</option>`;
  return html`<span class="lf-later" title=${LATER}
    >${iconTemplate("waiting", "lf-action-icon")}<select
      aria-label=${LATER}
      .value=${live("")}
      @change=${(event) => {
        const choice = offered[Number(event.target.value)];
        event.target.value = "";
        if (!choice) return;
        later(ids, condition(choice, new Date()));
        chosen();
      }}
    >
      <option value="" disabled hidden>${LATER}</option>
      ${offered.filter((choice) => !("after" in choice)).map(option)}
      ${
        work.length
          ? html`<optgroup label=${`When ${agentName()} finishes`}>
              ${work.map(option)}
            </optgroup>`
          : nothing
      }
    </select></span
  >`;
}

/** Where a Later stands, in the words a row or a card says: when it brings its records
 * back, or that it has. */
export function laterWords(later) {
  if (!later) return "";
  if (later.returned) return "Back from Later";
  if (later.until)
    return clockValue((now) => {
      const at = new Date(later.until);
      const today = new Date(now);
      const days = Math.round(
        (dayAt(at, 0, 0).getTime() - dayAt(today, 0, 0).getTime()) / 86_400_000,
      );
      const day =
        days === 0
          ? ""
          : days === 1
            ? "tomorrow "
            : days < 7
              ? `${weekday(at)} `
              : `${at.toLocaleDateString([], { month: "short", day: "numeric" })} `;
      return `Back ${day}at ${clock(at)}`;
    });
  const queues = readQueues();
  const row =
    queues.phase === "ready"
      ? queues.on_agent.find((item) => item.id === later.after)
      : null;
  return row
    ? `Back when ${agentName()} finishes “${excerptWords(queueTitle(row), 48)}”`
    : `Back when ${agentName()} finishes`;
}
