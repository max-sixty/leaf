// Compiled from address.ts by build/typescript.mjs; edit that file.
/* A thread's address: the `thread` query parameter of an entry's URL
   (`?thread=<message-id>`, skills/leaf/references/threads.md), the one record of which
   thread an entry shows. It names the thread whose view stands open on the entry, the
   floating panel's or a margin card's, so a reload, a copied link, Back and Forward each
   reach the thread view the entry showed.

   One composition writes the parameter (`name`): every entry history writes, a
   route's step, a widget's or a rename, names the thread that stands open as it is
   written, keeping every other parameter, the page key above all, and the fragment. As a
   view opens, closes or turns to another thread where the user stands, the entry the
   user is on is renamed (`followOpenThread`), never added. Escape and the back
   gesture put a view away by its close request (dom/keyboard/close-requests.js), so they
   rename the entry and never traverse. A route that travels to a thread names the entry
   it adds the same way: the step is written once the view stands open, and the entry
   left keeps the name it had (records/history.js, `prepareEntry`). A seat's thread stands in
   its widget rather than in a view, so its entry names no thread. The composition
   compares threads rather than spellings, so a link naming one of a thread's replies
   stands. The entry is renamed as the change happens, so a press that closes a card as
   it takes focus renames the entry it is on before the link it lands on adds the next
   one; records/history.js says when a rename waits (`replaceEntry`).

   A traversal shows the thread its entry names (`claim`): it opens that thread where
   the user stands, or puts the open thread away where the entry names none, beside any
   fragment the entry carries, and resolves to false, leaving the page and the user's
   place in it to the entry's record (records/history.js). The record holds the reader the
   entry's view was, the route's `reader` request for it, which the claim passes on, so
   a thread about a passage the user read in the floating panel opens there again, and
   one they read in its card opens in its card, or where Leaf places it when no card can
   stand by then (records/thread/destination.js, `reader: "card"`). The user's choice of where
   threads open (threads-in-panel.js) says where routes open a thread from now on, not
   which view the user stood in, so Back after Show on page returns them to the panel's
   view they read the thread in, though Show on page chose cards, and Back after Open in
   panel to the card, though Open in panel chose the panel. Rejected: opening the
   entry's thread by the choice alone, under which that Back no longer returned the
   user to the view they had left. Where the record says
   the floating panel showed a list, the list comes back as the user left it: On on
   its tab, read to where they had read it, standing on the row the record names, the
   one the user left by, else the row of the thread put away (panel/floating-panel.js,
   `putThreadAway`), so Back from a thread opened from Threads returns to Threads on
   its row though a reload has forgotten the panel's views since, or Escape put the
   thread away first.

   A URL naming a thread on arrival (`arrive`) travels to it as a thread link does, with
   focus, and where it names one of the thread's replies, lands on that reply rather
   than where opening the thread lands. Where the browser restored the page's place,
   as on a reload, the arrival is a return, which moves the page no further than the
   browser put it, as a fragment's return doesn't (features/version.js, `aimArrival`):
   the thread opens where the page stands, with the user in it, so the next `t` goes
   on from it. Where the URL also names an
   element, which places the page, the thread opens beside it without focus. So a widget
   that names the view it opens in the fragment, as a tab set names the panel the
   thread's passage stands in, leaves an address a reload or a copied link still reaches
   the thread by.

   A message's Copy link (messages.js) copies `messageLink`: the page's address naming
   the message, with no fragment, since a fragment left from an earlier step in the page
   would land the reader there and open the thread beside it. Like a section's link
   (records/heading-links.js), it keeps the address's other parameters, so it reaches
   the page wherever the address it was copied from does. Rejected: the share address
   (panel/page-about.js), whose key grants access to every page on the machine, which
   the menu's row says and a link handed around shouldn't carry unannounced. */
import { effect, untracked } from "/vendor/signals-core.js";
import { replaceEntry } from "../history.js";
import { raiseError } from "../../transport/errors.js";
import { fragmentTarget } from "../../readings/anchor-resolution.js";
import { threadNamed } from "./state.js";

// The query parameter that names the thread an entry shows.
const PARAMETER = "thread";

// The link to the message `id` (the header): this page's address naming it, without
// a fragment.
export function messageLink(id) {
  const url = new URL(location.href);
  url.searchParams.set(PARAMETER, id);
  url.hash = "";
  return url.href;
}

export function createThreadAddress({ shown, putAway, openPageThread }) {
  // The thread an entry's URL names, by its id, or null.
  const named = (url) => {
    const name = url.searchParams.get(PARAMETER);
    return name ? (threadNamed(name)?.id ?? name) : null;
  };

  // `url` naming the thread that stands open now, or none: the one composition of the
  // parameter, which every entry history writes takes (records/history.js, `nameThread`).
  function name(url) {
    const open = untracked(shown)?.id ?? null;
    if (named(url) === open) return url;
    const renamed = new URL(url);
    if (open) renamed.searchParams.set(PARAMETER, open);
    else renamed.searchParams.delete(PARAMETER);
    return renamed;
  }
  // Each change of the thread that stands open renames the entry the user is on.
  function followOpenThread() {
    let last;
    return effect(() => {
      const open = shown()?.id ?? null;
      const changed = last !== undefined && open !== last;
      last = open;
      if (changed) replaceEntry();
    });
  }

  const claim = (url, record, intent) => {
    const id = named(url);
    const open = shown();
    const kept = record?.thread ?? null;
    const list = record?.list ?? null;
    if (!id)
      return open || list
        ? () => {
            putAway(list, open?.id ?? null, intent);
            return false;
          }
        : null;
    if (open?.id === id && (!kept || open.reader === kept.reader)) return null;
    // Under the intent of the restoration that asks (records/history.js), which a newer
    // navigation or the user's own input ends.
    return async () => {
      if (!intent()) return false;
      if (!threadNamed(id)) {
        raiseError(`Thread ${id} is unavailable`);
        return false;
      }
      // Where the user stands, moving no scroller: a passage the page no longer shows
      // there, as one a revision moved into a closed tab, leaves the thread to the
      // floating panel rather than reveal it under the user.
      await openPageThread(id, {
        part: "thread",
        focus: false,
        travel: false,
        scroll: false,
        intent,
        reader: kept?.reader ?? null,
      });
      return false;
    };
  };

  // The arrival's route to the thread `url` names, under the arrival's intent
  // (records/history.js, `beginRestoration`), or null where it names none. `restored` is an
  // arrival whose place the browser restored, a reload's or a traversal's into the
  // document.
  function arrive(url, intent, { restored }) {
    const id = url.searchParams.get(PARAMETER);
    if (!id) return null;
    const beside = !restored && Boolean(fragmentTarget(url.hash));
    return async () => {
      if (!intent()) return null;
      const thread = threadNamed(id);
      if (!thread) {
        raiseError(`Thread ${id} is unavailable`);
        return null;
      }
      const reply =
        id !== thread.root.id && thread.msgs.some((message) => message.id === id);
      return openPageThread(id, {
        part: reply ? "message" : "thread",
        focus: !beside,
        travel: !restored && !beside,
        ...(restored && { scroll: false }),
        history: false,
        intent,
      });
    };
  }

  return { followOpenThread, claim, arrive, name };
}
