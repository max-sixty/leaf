/* The entries this document adds to session history, and the traversals among them.
 *
 * Every same-document entry is a place the user can come Back to. `pushEntry` adds one,
 * leaving the entry the user stood on with the scroll offset the browser saves on it;
 * `replaceEntry` renames the entry the user stands on and keeps its state. A new entry
 * starts with no state of its own, since state belongs to the entry that set it.
 *
 * The browser restores a saved offset on traversal, except that Chrome answers a
 * traversal to an entry whose fragment names an element by scrolling to that element
 * instead (measured: Back to `#s2` after reading 3000px down landed on `#s2` at 666).
 * So every same-document traversal comes through here, through the Navigation API. An
 * owner that claims the destination (`claimTraversals`) places the page itself, as a
 * root tab set does for the entry of each of its views. Travel takes the traversal next
 * (`mountHistory`'s `returnToFragment`, anchor-travel.js) where the entry's fragment
 * names a place the page no longer shows: the offset was saved over a page that has
 * changed, so travel reveals the place and lands on it. Any other traversal is
 * intercepted only so the browser restores the entry's saved offset, which it does for
 * an intercepted traversal. Focus stays where it is either way, as an unintercepted
 * traversal leaves it.
 *
 * A fragment navigation, a followed `#id` link, is not a traversal: it adds its entry
 * and is a trip to the element it names. Travel claims it (`followFragment`) where the
 * fragment names an element of the page, and lands it through the browser's own
 * fragment scroll once travel has cleared and revealed the way; any other fragment
 * keeps native landing. An entry this document writes through `pushEntry` or
 * `replaceEntry`, as travel and a tab set do, is not a fragment navigation and is never
 * claimed. A browser without the Navigation API keeps its own traversals and fragment
 * landings. */

const claims = new Set();

// Whether this document is writing an entry itself. The Navigation API fires `navigate`
// synchronously inside `pushState` and `replaceState`, and those events look like a
// press on a link to the fragment the page already shows: both are a same-document
// `replace` or `push` with no hash change. Only the writer can tell them apart.
let writing = false;
function write(method, state, url) {
  writing = true;
  try {
    history[method](state, "", url);
  } finally {
    writing = false;
  }
}

export function pushEntry(url, state = null) {
  write("pushState", state, url);
}

export function replaceEntry(url, state = history.state) {
  write("replaceState", state, url);
}

// `claim(url)` returns the handler that places the page at a traversal to `url`, or
// nothing when the entry is not the claimant's. The first claim to answer takes it.
export function claimTraversals(claim, { signal } = {}) {
  claims.add(claim);
  signal?.addEventListener("abort", () => claims.delete(claim), { once: true });
}

let mounted = false;
export function mountHistory({ followFragment, returnToFragment }) {
  if (mounted) return;
  mounted = true;
  window.navigation?.addEventListener("navigate", (event) => {
    if (!event.destination.sameDocument || !event.canIntercept) return;
    const url = new URL(event.destination.url);
    if (event.navigationType === "traverse") {
      const handler = claimed(url) ?? returnToFragment(url);
      event.intercept(
        handler
          ? { scroll: "manual", focusReset: "manual", handler }
          : { focusReset: "manual" },
      );
      return;
    }
    // A followed link again to the fragment already shown is a `replace` with no hash
    // change, and still a trip: its target may have been shut since.
    if (writing || event.formData || !url.hash) return;
    const handler = followFragment(url, () => event.scroll());
    if (handler) event.intercept({ scroll: "manual", focusReset: "manual", handler });
  });
}

function claimed(url) {
  for (const claim of claims) {
    const handler = claim(url);
    if (handler) return handler;
  }
  return null;
}
