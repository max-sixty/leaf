/* A widget drawn a second time where its obligation is answered away from where it
   stands: On me's card (PROTOTYPE, design C).

   The seat is a second element of the source's tag and id, copied from the source's
   authored markup and marked `data-lf-seat` with the seat's name. It binds to the
   source's captured descriptor (`widgetDescriptor` accepts a same-id replacement), so
   it reads the same state and dispatches the same actions as the source, and its own
   commands, undo and answer words work as they do on the page. It presents in regions
   of its own (`attachWidgetPresentation`'s `seat`), so the source keeps its own. A
   widget opts in with a static `seats` list naming the seats it draws a form for; its
   render and theme read `data-lf-seat` to choose that form. A widget that has not
   opted in gets no seat, and the card keeps its frame alone.

   The copy is made from what the author wrote, which the caller finds (`authored`):
   the revision's source for a page widget (version.js, `authoredElement`), the
   message's markup for one in a thread. Never from the live element, whose module has
   added nodes of its own that only it can tell from the author's. The seat is cached
   per obligation and descriptor while its card stands, so a repaint keeps its node,
   focus and caret, and a revision that rewrites the widget draws a fresh one. */
import { seatOf, widgetDescriptor, widgetElement } from "../widget-descriptors.js";

const seats = new Map();

// Whether a widget's module draws a form for `seat`.
export const seatsIn = (tag, seat) =>
  Boolean(
    /** @type {{seats?: string[]}} */ (customElements.get(tag))?.seats?.includes(seat),
  );

// The seated copy of `record`'s widget, or null where the widget draws no form for the
// seat or nothing says what its author wrote.
export function seatedWidget(record, seat, authored) {
  if (record?.source.kind !== "widget" || record.source.unit) return null;
  const { id, tag } = record.source;
  if (!seatsIn(tag, seat)) return null;
  const key = `${seat}:${record.id}`;
  const source = widgetElement(id);
  const cached = seats.get(key);
  if (cached && (!source || widgetDescriptor(cached) === widgetDescriptor(source)))
    return cached;
  const written = authored(record);
  if (!written || seatOf(written)) return null;
  const copy = /** @type {HTMLElement} */ (document.importNode(written, true));
  copy.setAttribute("data-lf-seat", seat);
  seats.set(key, copy);
  return copy;
}

// Let go of the seats no card holds any more.
export function keepSeats(seat, recordIds) {
  for (const key of [...seats.keys()])
    if (key.startsWith(`${seat}:`) && !recordIds.has(key.slice(seat.length + 1)))
      seats.delete(key);
}
