/* Where key chips stand. Each chip stands in a seat, a box anchored to the target the
   chip names (target-paint-geometry.js, `paintSet`, with nothing cutting it), so the
   browser carries the chip with every scroll that moves its target, and no scroll
   writes it. A placement pass seats chips where the room around their targets puts
   them at rest; a scroll leaves each chip riding where it was seated, hidden once its
   target is out of sight, and the pass seats them again once the scroll settles. A
   chip the window's edge or the chrome holds in, or one naming a control on the fixed
   chrome, stands where the window holds it, so a scroll leaves it standing.

   A chip stacks under the bars and banner it keeps clear of, so one riding a scroll
   slides beneath them as the page does, unless its target stacks at or above that
   level, in a surface standing over the page, where the chip stands above every
   surface instead (chrome.css, `.lf-key-chips`). */
import { paintSet } from "../target-paint-geometry.js";
import { stackLevel } from "../geometry.js";

let chipLevel = 0;
const plane = (target) => {
  chipLevel ||= Number.parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue("--lf-z-page-hints"),
  );
  return !target || stackLevel(target) >= chipLevel ? "chrome" : "page";
};

export function chipSeats(root) {
  const set = paintSet(root);
  const seats = new Map(); // key → seat

  return {
    // The seat for `key`, made where there is none, in the document so the chip it is
    // given can be read before it is seated.
    seat(key) {
      let seat = seats.get(key);
      if (!seat) {
        seat = document.createElement("span");
        seat.className = "lf-chip-seat";
        seats.set(key, seat);
      }
      if (!seat.isConnected) root.append(seat);
      return seat;
    },
    // The seat standing for `key`, if one does.
    standing: (key) => (seats.get(key)?.isConnected ? seats.get(key) : null),
    // Hides every standing seat but those for `keys`, as a scroll holds the seats while
    // what they say changes: a typed letter leaves chips that no longer match, and a
    // command can leave reach. Hidden, a seat keeps its box, so the pass that seats it
    // again once the scroll settles reads its chip where it stands.
    keepOnly(keys) {
      for (const [key, seat] of seats) {
        const visibility = keys.has(key) ? "" : "hidden";
        if (seat.style.visibility !== visibility) seat.style.visibility = visibility;
      }
    },
    // The box `seat`'s chip takes with the seat at `at`, read off where both stand.
    boxAt(seat, at) {
      const chip = seat.firstElementChild.getBoundingClientRect();
      const own = seat.getBoundingClientRect();
      return new DOMRect(
        at.left + chip.left - own.left,
        at.top + chip.top - own.top,
        chip.width,
        chip.height,
      );
    },
    // Stands each seat over `target` so its chip takes `box`, read as `start` with the
    // seat at `at`, or where the window holds it where it is `held` by the window's edge
    // or the chrome, and puts away every seat not among them.
    place(seated) {
      set.place(
        seated.map(({ seat, target, at, start, box, held = false }) => ({
          node: seat,
          target: held ? null : target,
          plane: plane(target),
          cut: false,
          rect: {
            left: at.left + box.left - start.left,
            top: at.top + box.top - start.top,
          },
        })),
      );
      const kept = new Set(seated.map(({ seat }) => seat));
      for (const [key, seat] of seats)
        if (!kept.has(seat)) seats.delete(key);
        else if (seat.style.visibility) seat.style.removeProperty("visibility");
    },
    clear() {
      set.clear();
      seats.clear();
    },
  };
}
