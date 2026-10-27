/* Later until…: the control that sets obligations aside, and the words for where one
   stands.

   The server owns Later (`src/leaf/later.py`): a `later` event names the obligation
   records one card or On me row carries and one condition, `until` an instant or `after`
   an item on the agent's list, and its reading decides when they come back. The
   publisher draws the gesture's own result in the task that makes it, the records off
   On me and off a deck's pass (framework/application.js, `localLaters`), and an Undo
   withdraws it like any gesture. later-model.js holds what the browser reads off a
   record (`setAside`) and the times offered.

   One control offers it wherever it stands, a deck card's bar or an On me card
   (`laterControl`): the clock, Later's symbol, a menu button whose menu lists the times
   on the user's own clock, then the items on the agent's list as On <agent> titles
   them, so "when the agent finishes" names work the server already knows by id, never
   words. The menu is drawn as it opens, so its times are reckoned then, not when the
   page last painted, and a choice commits only on its own press or Enter. It is a
   popover menu walked by the arrows, as lf-file-editor's conflict menu is; Escape and
   a choice hand the user back to the clock.

   Rejected: a second row of buttons, one per choice, which put five presses beside
   every card for a gesture most cards never take; the platform's select laid unseen
   over the clock, on which Firefox commits a choice on one arrow key or typed letter
   while it is closed, so a stray key set a card aside (probed 2026-10-27); and a free
   date field, which wants its own popup on every platform for a choice the presets
   cover. */
import { html, nothing, ref, render } from "/runtime/framework.js";
import { iconTemplate } from "../icons.js";
import { offeredAction } from "../widget-elements.js";
import { agentName, readPart } from "../semantic-state.js";
import { readQueues } from "../queue-api.js";
import { queueTitle } from "../queue-title.js";
import { excerptWords } from "../words.js";
import { clockValue } from "../presence.js";
import { closeLayer, focusDestination, handBack, rove } from "../focus.js";
import { closeNativeLayer } from "../keyboard/layer-stack.js";
import { commandsOn } from "../keyboard/scopes.js";
import { allButCommandReference } from "../keyboard/register.js";
import { rowWalk } from "../walk-position.js";
import { laterTimes, untilWords } from "./later-model.js";

export { setAside } from "./later-model.js";

export const LATER = "Later until…";

const readWorkflows = readPart((root) => root.effective.workflows);

// The row on the agent's list an `after` names: the row by its id, or, where a follow-up
// moved an update's debt to a newer input, the row the named input's workflow serves.
function agentRow(after) {
  const queues = readQueues();
  if (queues.phase !== "ready") return null;
  const input = after.startsWith("update:") ? after.slice("update:".length) : null;
  const serving = input
    ? readWorkflows().find((workflow) => workflow.input === input)?.obligation
    : null;
  return queues.on_agent.find((row) => row.id === after || row.id === serving) ?? null;
}

// The control each `laterControl` draws keeps what its latest paint asked of it, so a
// choice made in an open menu sets aside what the card holds now.
const asked = new WeakMap();
let controls = 0;

function wire(holder, ask) {
  if (!holder) return;
  asked.set(holder, ask);
  if (holder.dataset.lfLater) return;
  const key = `lf-later-${++controls}`;
  holder.dataset.lfLater = key;
  holder.style.setProperty("anchor-name", `--${key}`);
  const menu = holder.querySelector(".lf-later-menu");
  menu.id = key;
  menu.style.setProperty("position-anchor", `--${key}`);
  // The clock is the first child; its role's class is written after this runs.
  holder.firstElementChild.setAttribute("popovertarget", key);
}

const rows = (menu) => [...menu.querySelectorAll("button")];
const putAway = (menu) =>
  closeLayer(
    () => closeNativeLayer(menu),
    () => handBack(menu.parentElement.firstElementChild),
  );

// The menu's rows, drawn as it opens: the times from now, then the agent's items.
function draw(menu) {
  const holder = menu.parentElement;
  const choose = (condition) => () => {
    const { ids, later, chosen } = asked.get(holder);
    putAway(menu);
    later(ids, condition);
    chosen();
  };
  const work = readQueues().phase === "ready" ? readQueues().on_agent : [];
  render(
    html`${laterTimes(new Date()).map(
      ({ label, until }) =>
        html`<button
          ${offeredAction("word")}
          role="menuitem"
          @click=${choose({ until: until.toISOString() })}
        >
          ${label}
        </button>`,
    )}${
      work.length
        ? html`<p class="lf-later-group" role="presentation">
              When ${agentName()} finishes
            </p>
            ${work.map(
              (row) =>
                html`<button
                  ${offeredAction("word")}
                  role="menuitem"
                  @click=${choose({ after: row.id })}
                >
                  ${excerptWords(queueTitle(row), 60)}
                </button>`,
            )}`
        : nothing
    }`,
    menu,
  );
}

/** Later's control for the records `ids`: choosing sets them aside through `later`
 * (`obligationActions.later`) and then calls `chosen`, as a deck sends its card on. */
export function laterControl(ids, later, chosen = () => {}) {
  if (!ids.length) return nothing;
  const keys = (menu) => [
    ...rowWalk({
      id: "later.choice",
      noun: "Choice",
      plural: "choices",
      rows: () => rows(menu),
      position: () => null,
      landed: (row) => rove(rows(menu), row),
    }),
    { id: "later.close", keys: ["Escape"], title: "close", run: () => putAway(menu) },
    ...["Tab", "Shift+Tab"].map((key) => ({
      id: `later.leave-${key === "Tab" ? "forward" : "backward"}`,
      keys: [key],
      title: key === "Tab" ? "leave forward" : "leave backward",
      native: true,
      run: () => putAway(menu),
    })),
  ];
  return html`<span
    class="lf-later"
    ${ref((holder) => wire(holder, { ids, later, chosen }))}
    ><button ${offeredAction("symbol", "lf-later-open", LATER)} aria-haspopup="menu">
      ${iconTemplate("waiting", "lf-action-icon")}
    </button>
    <div
      class="lf-later-menu"
      popover="auto"
      role="menu"
      aria-label=${LATER}
      @beforetoggle=${(event) => {
        if (event.newState === "open") draw(event.currentTarget);
        event.currentTarget.previousElementSibling.setAttribute(
          "aria-expanded",
          String(event.newState === "open"),
        );
      }}
      @toggle=${(event) => {
        if (event.newState !== "open") return;
        const [first] = rows(event.currentTarget);
        rove(rows(event.currentTarget), first);
        focusDestination(first, "move");
      }}
      ${commandsOn(LATER, keys, { claims: allButCommandReference })}
    ></div
  ></span>`;
}

/** Where a Later stands, in the words a row or a card says: when it brings its records
 * back, or that it has. */
export function laterWords(later) {
  if (!later) return "";
  if (later.returned) return "Back from Later";
  if (later.until) return clockValue((now) => untilWords(later.until, new Date(now)));
  const row = agentRow(later.after);
  return row
    ? `Back when ${agentName()} finishes “${excerptWords(queueTitle(row), 48)}”`
    : `Back when ${agentName()} finishes`;
}
