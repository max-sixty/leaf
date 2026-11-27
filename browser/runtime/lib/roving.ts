/* A group's one Tab stop: of a set of controls the user moves through with the group's
   own arrow keys, Tab reaches only the stop, and every other item leaves the tab order
   while staying focusable by script (the ARIA practice of a roving `tabindex`).

   ```js
   rove(rows, rows.find((row) => row.ariaSelected === "true") ?? rows[0]);
   ``` */
import { keeps } from "./keeps.js";

// A null `stop` takes every item out of the tab order.
export function rove(items: Iterable<Element>, stop: Element | null | undefined) {
  for (const item of items) keeps(item, "tabindex", item === stop ? 0 : -1);
}
