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
   gesture put a view away by its close request (keyboard/close-requests.js), so they
   rename the entry and never traverse. A route that travels to a thread names the entry
   it adds the same way: the step is written once the view stands open, and the entry
   left keeps the name it had (history.js, `prepareEntry`). A seat's thread stands in
   its widget rather than in a view, so its entry names no thread. The composition
   compares threads rather than spellings, so a link naming one of a thread's replies
   stands. The entry is renamed as the change happens, so a press that closes a card as
   it takes focus renames the entry it is on before the link it lands on adds the next
   one; history.js says when a rename waits (`replaceEntry`).

   A traversal shows the thread its entry names (`claim`): it opens that thread where
   the user stands, or puts the open thread away where the entry names none, beside any
   fragment the entry carries, and resolves to false, leaving the page and the user's
   place in it to the entry's record (history.js). Where the user was in the thread's
   view, the record holds the route's `reader` request for that view, which the claim
   passes on, so a thread about a passage the user read in the floating panel opens
   there again rather than beside its passage.

   A URL naming a thread on arrival (`arrive`) travels to it as a thread link does, with
   focus. Where the browser restored the page's place, as on a reload, the arrival is a
   return, which moves the page no further than the browser put it, as a fragment's
   return doesn't (version.js, `aimArrival`): the thread opens where the page stands,
   with the user in it, so the next `t` goes on from it. Where the URL also names an
   element, which places the page, the thread opens beside it without focus. So a widget
   that names the view it opens in the fragment, as a tab set names the panel the
   thread's passage stands in, leaves an address a reload or a copied link still reaches
   the thread by. */
import { effect, untracked } from "/runtime/framework.js";
import { replaceEntry } from "../history.js";
import { raiseError } from "../errors.js";
import { fragmentTarget } from "../anchor-resolution.js";
import { restrictUserIntent, retainUserIntent } from "../user-intent.js";
import { threadNamed } from "./state.js";

/** @typedef {{id: string, reader: "primary" | null}} OpenThread */

/** @param {{shown: () => OpenThread | null, putAway: () => void,
 * openPageThread: ReturnType<typeof import("./destination.js").createThreadDestinations>["openPageThread"]}} options */
export function createThreadAddress({ shown, putAway, openPageThread }) {
  // The thread an entry's URL names, by its id, or null.
  /** @param {URL} url */
  const named = (url) => {
    const name = url.searchParams.get("thread");
    return name ? (threadNamed(name)?.id ?? name) : null;
  };

  // `url` naming the thread that stands open now, or none: the one composition of the
  // parameter, which every entry history writes takes (history.js, `nameThread`).
  /** @param {URL} url */
  function name(url) {
    const open = untracked(shown)?.id ?? null;
    if (named(url) === open) return url;
    const renamed = new URL(url);
    if (open) renamed.searchParams.set("thread", open);
    else renamed.searchParams.delete("thread");
    return renamed;
  }
  // Each change of the thread that stands open renames the entry the user is on.
  function followOpenThread() {
    /** @type {string | null | undefined} */
    let last;
    return effect(() => {
      const open = shown()?.id ?? null;
      const changed = last !== undefined && open !== last;
      last = open;
      if (changed) replaceEntry();
    });
  }

  /** @type {import("../history.js").ThreadClaim} */
  function claim(url, place) {
    const id = named(url);
    const open = shown();
    const kept = place?.thread?.id === id ? place.thread : null;
    if (!id)
      return open
        ? () => {
            putAway();
            return false;
          }
        : null;
    if (open?.id === id && (!kept || open.reader === kept.reader)) return null;
    // Navigation though it takes no focus, not an editing continuation allowed to
    // open the thread after the user has gone elsewhere.
    const retained = retainUserIntent();
    const intent = restrictUserIntent(retained, retained);
    return async () => {
      if (!intent()) return false;
      if (!threadNamed(id)) {
        raiseError(`Thread ${id} is unavailable`);
        return false;
      }
      await openPageThread(id, {
        part: "thread",
        focus: false,
        travel: false,
        intent,
        reader: kept?.reader ?? null,
      });
      return false;
    };
  }

  // The arrival's route to the thread `url` names, under the intent the arrival began
  // with, or null where it names none. `restored` is an arrival whose place the browser
  // restored, a reload's or a traversal's into the document.
  /** @param {URL} url @param {import("../user-intent.js").UserIntent} arrival
   * @param {{restored: boolean}} options */
  function arrive(url, arrival, { restored }) {
    const id = url.searchParams.get("thread");
    if (!id) return null;
    const beside = !restored && Boolean(fragmentTarget(url.hash));
    const intent = restrictUserIntent(arrival, arrival);
    return async () => {
      if (!intent()) return null;
      if (!threadNamed(id)) {
        raiseError(`Thread ${id} is unavailable`);
        return null;
      }
      return openPageThread(id, {
        part: "thread",
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
