/* The arrow keys of a flat list of focusable rows, as two command rows a widget puts in
   the list's scope (`lfCommands`): ArrowUp and ArrowDown step, stopping at the ends,
   and Home and End reach them. A step focuses the row, brings it into view at the
   nearest edge of each box that scrolls it unless `scroll` is false, and says where it
   landed with an `lf-walk` event (widget-events.js, `WALK`), which a Leaf page's panel
   shows as "Option 2 of 5" while the list runs past the window. A list whose rows name
   their places to a screen reader themselves, as a menu's do, passes `place: false`.
   `rows()` returns the list at each press; `landed(row)` runs after a step that moved
   the user to another row; `steps` names the four steps in place of previous, next,
   first and last. */
import { WALK } from "./widget-events.js";

/** @type {readonly [string, string, string, string]} */
const STEPS = Object.freeze(["previous", "next", "first", "last"]);

// The element focus is on, followed down through each open shadow tree.
const focusedElement = () => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  return at;
};

/** @param {{
 *   id: string,
 *   noun: string,
 *   plural: string,
 *   rows: () => HTMLElement[],
 *   steps?: readonly [string, string, string, string],
 *   landed?: (row: HTMLElement) => void,
 *   scroll?: boolean,
 *   place?: boolean,
 * }} walk */
export function rowWalk({
  id,
  noun,
  plural,
  rows,
  steps = STEPS,
  landed,
  scroll = true,
  place = true,
}) {
  const [up, down, home, end] = steps;
  /** @param {string} binding @param {string} step */
  const route = (binding, step) => ({
    id: `${id}.${step}`,
    binding,
    title: `${step.charAt(0).toUpperCase()}${step.slice(1)} ${noun.toLowerCase()}`,
  });
  /** @param {(list: HTMLElement[], at: Element | null) => HTMLElement | undefined} pick */
  const land = (pick) => {
    const list = rows();
    const was = focusedElement();
    const row = pick(list, was);
    if (!row) return;
    row.focus({ preventScroll: true });
    if (scroll) row.scrollIntoView({ block: "nearest", inline: "nearest" });
    if (place)
      row.dispatchEvent(
        new CustomEvent(WALK, {
          bubbles: true,
          composed: true,
          detail: {
            noun,
            position: list.indexOf(row) + 1,
            total: list.length,
            list: [list[0], list.at(-1)],
          },
        }),
      );
    if (row !== was) landed?.(row);
  };
  // The next row `dir` away from the one the user is on, stopping at the ends, or the
  // first where they are on none.
  /** @param {HTMLElement[]} list @param {Element | null} at @param {-1 | 1} dir */
  const next = (list, at, dir) => {
    const index = list.findIndex((row) => row === at);
    return list[index < 0 ? 0 : Math.max(0, Math.min(list.length - 1, index + dir))];
  };
  return [
    {
      id: `${id}.walk`,
      keys: ["ArrowUp", "ArrowDown"],
      routes: [route("ArrowUp", up), route("ArrowDown", down)],
      title: `walk the ${plural}`,
      repeat: true,
      travels: scroll,
      runKey: /** @param {string} binding */ (binding) =>
        land((list, at) => next(list, at, binding === "ArrowDown" ? 1 : -1)),
    },
    {
      id: `${id}.edge`,
      keys: ["Home", "End"],
      routes: [route("Home", home), route("End", end)],
      title: `${home} / ${end}`,
      travels: scroll,
      runKey: /** @param {string} binding */ (binding) =>
        land((list) => (binding === "Home" ? list[0] : list.at(-1))),
    },
  ];
}
