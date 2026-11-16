// The gallery's "Move the rail" places the margin's rail left of this page's column,
// mirroring Leaf's own placement on the right, and a second press withdraws it.
import { keepsText, placeMarginRail, whileConnected } from "/runtime/widget-api.js";

const button = /** @type {HTMLButtonElement} */ (
  document.getElementById("bg-rail-side")
);
const status = document.querySelector("#bg-rail-side-status > span");

whileConnected(button, (signal) => {
  /** @type {(() => void) | null} */
  let withdraw = null;
  const toLeft = () =>
    placeMarginRail(({ column, shell, width, hang }) =>
      column.left - shell.left >= width
        ? { edge: column.left - hang, side: "left" }
        : null,
    );
  button.addEventListener(
    "click",
    () => {
      withdraw?.();
      withdraw = withdraw ? null : toLeft();
      keepsText(
        status,
        withdraw ? "This page places the rail, on the left." : "Leaf places the rail.",
      );
    },
    { signal },
  );
  return () => withdraw?.();
});
