/* One placement owner for a surface that hangs off the control that opens it.
 *
 * The layer has one positioning model, and this is where a surface joins it: the same
 * Floating UI the margin projection and the composing surface already use, with the
 * same `flip`, `shift`, and `size` answers to a viewport edge. Those answers come from
 * measuring the surface and its anchor, so the room a menu may take is the room it
 * actually has, rather than a CSS expression restating the banner's declared height and
 * going stale when that height changes.
 *
 * Geometry only. The surface is a native popover throughout, so its own owner keeps the
 * top layer, light dismissal, invoker relationship, and focus; this module reads the
 * open state the popover publishes and writes `left`, `top`, and the two room custom
 * properties the surface's rules consume.
 *
 * The bundle stays out of startup: it arrives on the first open, which is the one open
 * that waits for a fetch. Until a surface is placed it holds at zero opacity rather than
 * painting once at its static position and again where it belongs, and the hold goes on
 * in `beforetoggle` so no frame between the two events can show it. A placed surface
 * says so with `data-lf-anchored`, which is the fact anything measuring its box waits
 * on; `:popover-open` alone answers before the placement it is being read for.
 *
 * Placement waits for `toggle`, which is the first point the surface is measurable. A
 * popover is added to the top layer after `beforetoggle` returns, and the microtask a
 * resolved bundle would place from runs in that gap — on the first open the import is
 * slow enough to miss it, and every open after would measure a display:none box.
 */

let floatingUiModule = null;
const floatingUi = () => (floatingUiModule ??= import("/vendor/floating-ui.esm.js"));

// The distance a surface stands off its anchor, and the distance it keeps from the
// viewport's edge. Both are placement facts rather than paint, so they live here with
// the rest of the geometry instead of in each surface's rules.
const GAP = 6;
const EDGE = 8;
const ANCHORED = "data-lf-anchored";

/**
 * Place `surface` under `anchor()` for as long as the surface is open.
 *
 * `anchor` is read at each open so an owner that rebuilds its control hands over the
 * live node. While the surface stands, Floating UI follows the anchor through scroll,
 * resize, and layout shift; `--lf-anchor-width` carries the anchor's width and
 * `--lf-anchor-room` the height available below it, for rules that reserve either.
 */
export function anchorSurface(
  surface,
  { anchor, placement = "bottom-start", gap = GAP },
) {
  let epoch = 0;
  let release = null;

  const hold = () => {
    epoch += 1;
    surface.removeAttribute(ANCHORED);
    surface.style.opacity = "0";
    surface.style.pointerEvents = "none";
  };

  const placed = (anchored) => {
    surface.toggleAttribute(ANCHORED, anchored);
    surface.style.removeProperty("opacity");
    surface.style.removeProperty("pointer-events");
  };

  const stop = () => {
    epoch += 1;
    release?.();
    release = null;
    // A surface closed before its first placement would otherwise keep the hold, and a
    // static copy or a printed page draws it where the popover's rules no longer apply.
    placed(false);
  };

  const start = () => {
    const at = ++epoch;
    const standing = () => at === epoch && surface.matches(":popover-open");
    const withdraw = (error) => {
      // The layer's answer to a lazy module that never arrives: take the surface away
      // rather than leave one standing that nothing can place, and let the error reach
      // the page's own channel.
      if (standing()) surface.hidePopover();
      throw error;
    };
    void floatingUi().then((ui) => {
      const reference = anchor();
      if (!standing() || !reference?.isConnected) return;
      const place = () =>
        void ui
          .computePosition(reference, surface, {
            placement,
            strategy: "fixed",
            middleware: [
              ui.offset(gap),
              ui.flip({ padding: EDGE }),
              ui.shift({ padding: EDGE }),
              ui.size({
                padding: EDGE,
                apply({ availableHeight, rects }) {
                  if (!standing()) return;
                  surface.style.setProperty(
                    "--lf-anchor-width",
                    `${rects.reference.width}px`,
                  );
                  surface.style.setProperty(
                    "--lf-anchor-room",
                    `${Math.max(0, availableHeight)}px`,
                  );
                },
              }),
            ],
          })
          .then(({ x, y }) => {
            if (!standing()) return;
            surface.style.left = `${x}px`;
            surface.style.top = `${y}px`;
            placed(true);
          })
          .catch(withdraw);
      release = ui.autoUpdate(reference, surface, place);
    }, withdraw);
  };

  surface.addEventListener("beforetoggle", (event) => {
    if (event.newState === "open") hold();
    else stop();
  });
  surface.addEventListener("toggle", (event) => {
    if (event.newState === "open") start();
    else stop();
  });
}
