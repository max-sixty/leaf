/* A thread's address: the `thread` query parameter of an entry's URL
   (`?thread=<message-id>`, skills/leaf/references/threads.md), the one record of which
   thread an entry shows. It names the thread whose view stands open on the entry, the
   floating panel's or a margin card's, so a reload, a copied link, Back and Forward each
   reach the thread view the entry showed.

   One writer keeps the parameter equal to the thread that stands open
   (`followOpenThread`): as a view opens, closes or turns to another thread where the
   user stands, it renames the entry the user is on and never adds one, keeping every
   other parameter, the page key above all, and the fragment. Escape and the back
   gesture put a view away by its close request (keyboard/close-requests.js), so they
   rename the entry and never traverse. A route that travels to a thread names the entry
   it adds through this writer too: the step takes the name the entry has once the view
   stands open, and the entry left keeps the name it had (history.js, `prepareEntry`). A
   seat's thread stands in its widget rather than in a view, so its entry names no
   thread. The writer compares threads rather than spellings, so a link naming one of a
   thread's replies stands. It names the entry as the change happens, so a press that
   closes a card as it takes focus renames the entry it is on before the link it lands
   on adds the next one; during a navigation it reads the name once the navigation ends
   (history.js, `replaceEntry`), for the entry it ends on. A browser that refuses a write
   past its rate limit, as Safari does by throwing, leaves the entry named as it was
   until the next change.

   A traversal shows the thread its entry names (`claim`): it opens that thread where
   the user stands, or puts the open thread away where the entry names none, beside any
   fragment the entry carries, and resolves to false, leaving the page and the user's
   place in it to the entry's record (history.js). Where the user was in the thread's
   view, the record holds the route's `reader` request for that view, which the claim
   passes on, so a thread about a passage the user read in the floating panel opens
   there again rather than beside its passage.

   A URL naming a thread on arrival (`arrive`) travels to it as a thread link does, with
   focus, unless the URL also names an element, which then places the page, and the
   thread opens beside it. So a widget that names the view it opens in the fragment, as
   a tab set names the panel the thread's passage stands in, leaves an address a reload
   or a copied link still reaches the thread by. */
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

  let waiting = false;
  function nameEntry() {
    const transition = window.navigation.transition;
    if (transition) {
      if (waiting) return;
      waiting = true;
      const retry = () => {
        waiting = false;
        nameEntry();
      };
      void transition.finished.then(retry, retry);
      return;
    }
    const open = untracked(shown)?.id ?? null;
    const url = new URL(location.href);
    if (named(url) === open) return;
    if (open) url.searchParams.set("thread", open);
    else url.searchParams.delete("thread");
    try {
      replaceEntry(url);
    } catch {
      // Over the browser's rate limit (the header).
    }
  }
  // Each change of the thread that stands open.
  function followOpenThread() {
    /** @type {string | null | undefined} */
    let last;
    return effect(() => {
      const open = shown()?.id ?? null;
      const changed = last !== undefined && open !== last;
      last = open;
      if (changed) nameEntry();
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
  // with, or null where it names none.
  /** @param {URL} url @param {import("../user-intent.js").UserIntent} arrival */
  function arrive(url, arrival) {
    const id = url.searchParams.get("thread");
    if (!id) return null;
    const beside = Boolean(fragmentTarget(url.hash));
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
        travel: !beside,
        history: false,
        intent,
      });
    };
  }

  return { followOpenThread, claim, arrive };
}
