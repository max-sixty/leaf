/* What this tab has said to the server and heard back, counted at the door each trip
   goes through and painted on the root element as one fact (data-lf-traffic). A reader
   outside the page — the suite, a probe — waits on the runtime's own ledger, rather than
   rebuilding one from the browser's request events: that copy was a second
   representation of the outbox's lifecycle, and it needed a protocol of its own to stay
   in step with the first — a post a reload killed mid-flight that no event reported, a
   waiter the browser woke before the listeners that counted, a body read that could not
   run out. Counts are the document's: a navigation starts the ledger over with the page
   that carries it, and a page that has not booted paints nothing.

   On `<html>` rather than `<body>` because the body is what the page's observers watch —
   design mode relays every page mutation into a legend layout — and a counter that
   moves on every trip is not a page movement. The root carries no authored share that
   activation would replace, and the bake drops the attribute from a copy.

   `sends` and `acked` are posts to /api/event, counted as issued and as ended whichever
   way — answered, refused, or failed — so a retry is a second send. `asked` and `heard`
   are the same pair for reads of /api/state, `heard` once the body has been read or the
   read has failed. `pending` names the attempts the outbox still holds with no delivery
   outcome, in the outbox's own serial order: an entry behind a head that is retrying
   stays pending until its turn, even where a read has already shown its attempt landed,
   because delivery is what the outbox says it is. That is the fact a wait for "what this
   page sent has come back" consumes. */
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";

const ledger = { sends: 0, acked: 0, asked: 0, heard: 0, pending: [] };

function paint() {
  document.documentElement.setAttribute(
    PAGE_PAINT_ATTRIBUTE.traffic,
    JSON.stringify(ledger),
  );
}

export function countTraffic(key) {
  ledger[key] += 1;
  paint();
}

export function pendingTraffic(attempts) {
  ledger.pending = attempts;
  paint();
}
