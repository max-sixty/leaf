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
 * root tab set does for the entry of each of its views. Any other traversal is
 * intercepted only so the browser restores the entry's saved offset, which it does for
 * an intercepted traversal. The one exception is an entry whose fragment names an
 * element the page no longer shows (a tab or disclosure closed since): the offset was
 * saved over a page that has changed, so the browser's own fragment landing, which
 * reveals the element, answers instead. Focus stays where it is either way, as an
 * unintercepted traversal leaves it.
 *
 * A fragment navigation, a followed `#id` link, is not a traversal: it adds its entry
 * and is a trip to the element it names. The travel owner claims it (`mountHistory`'s
 * `followFragment`, anchor-travel.js) where the fragment names an element of the page,
 * and lands it through the browser's own fragment scroll once travel has cleared and
 * revealed the way; any other fragment keeps native landing. `pushEntry` and
 * `replaceEntry` are not fragment navigations, so an entry travel or a tab set records
 * is never claimed. A browser without the Navigation API keeps its own traversals and
 * fragment landings. */

const claims = new Set();

export function pushEntry(url, state = null) {
  history.pushState(state, "", url);
}

export function replaceEntry(url, state = history.state) {
  history.replaceState(state, "", url);
}

// `claim(url)` returns the handler that places the page at a traversal to `url`, or
// nothing when the entry is not the claimant's. The first claim to answer takes it.
export function claimTraversals(claim, { signal } = {}) {
  claims.add(claim);
  signal?.addEventListener("abort", () => claims.delete(claim), { once: true });
}

let mounted = false;
export function mountHistory({ followFragment }) {
  if (mounted) return;
  mounted = true;
  window.navigation?.addEventListener("navigate", (event) => {
    if (!event.destination.sameDocument || !event.canIntercept) return;
    const url = new URL(event.destination.url);
    if (event.hashChange && event.navigationType !== "traverse") {
      const arrive = followFragment(url);
      if (arrive)
        event.intercept({
          scroll: "manual",
          focusReset: "manual",
          handler: () => arrive(() => event.scroll()),
        });
      return;
    }
    if (event.navigationType !== "traverse") return;
    for (const claim of claims) {
      const handler = claim(url);
      if (!handler) continue;
      event.intercept({ scroll: "manual", focusReset: "manual", handler });
      return;
    }
    if (hiddenTarget(url.hash)) return;
    event.intercept({ focusReset: "manual" });
  });
}

function hiddenTarget(hash) {
  let id;
  try {
    id = decodeURIComponent(hash.slice(1));
  } catch {
    return false;
  }
  const target = id && document.getElementById(id);
  return Boolean(target) && !target.checkVisibility();
}
