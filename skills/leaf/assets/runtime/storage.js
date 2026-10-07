// ---------- which address this document is ----------
// Which version a document is comes from its served `lf-version` marker
// (`document-identity.js`), and where another version is from that version's `url` in
// the state reading, which the server addresses at the page root. Neither is read off
// this path.
const PAGE_PATH = location.pathname;
// The live root follows the active revision in place; a virtual version address
// (`versions/vN.html`) stays pinned to its mapped revision.
export const LIVE_ROOT = PAGE_PATH.endsWith("/");
// Which page this document belongs to. The server declares the page's root in the
// canonical link it adds to every document it serves, the live root and each version
// address alike, and every page operation resolves against it. An interactive export
// has no server and no link, so no root: the file is the page.
export const PAGE_ROOT =
  document.querySelector('link[rel="canonical"][data-lf-runtime]')?.href ?? null;
// The same page as a prefix for what the tab keeps, which the prepaint declares on the
// root before the first paint, since it reads the tab's memory then too (prepaint.js).
export const PAGE_SCOPE = document.documentElement.dataset.lfPageScope;

// ---------- what the page keeps, and what a store may refuse ----------
// Reading or writing web storage throws outright where the browser has it switched off —
// a locked-down profile, a private window on some engines — and nothing kept here is
// worth breaking the page for: a user who cannot save which tab they were on still
// gets the page. Said once, because a policy spelled at each caller is a policy free to
// be spelled differently at the next one, and eleven of them had accumulated across the
// runtime and two widget modules.
//
// Which store is the part worth reading at a call site, and naming them is what puts it
// there. `tabStore` is this window's working state and dies with the tab — the reading
// position, which panel of a widget stands open, whether design mode is on — because each
// of those is about the window rather than about the page. `draftStore` is what the user
// typed and hasn't sent: it outlives the tab, because closing one is the ordinary end of
// a tab here, and every tab shows one live copy of it (see the draft section below).
// `userStore` is this user's standing preference across pages, which is the chrome
// they arrange and expect to find arranged. Anything two tabs must *agree* about is none
// of the three: it goes in the log.
//
// Values are the store's own vocabulary, strings and null, so nothing here has an
// opinion about encoding: an absent key reads back as null, and writing null removes it.
const { stored, tabStore: initialTabStore } = document.documentElement.lfStorage;
// Two of the three are scoped to the page (PAGE_SCOPE), and the odd one out is the reason
// there are three backings: what the user arranges is theirs wherever they are reading,
// while what they typed here belongs to this page. tabStore is the only one on the helper
// surface, because only widgets keep working state (lf-tabs' open panel, lf-options'
// collapsed group) — a module reaches its drafts through saveDraft/watchDraft, the chrome
// the user arranges is the runtime's own, and an export nothing imports is a promise
// nobody asked for.
export const tabStore = initialTabStore;
// Which member a holder that shows one at a time (`x-views`) opens on as it upgrades, and
// the record of each member it shows, which a reload reopens. The prepaint owns both
// (prepaint.js), since it shows the same member at the first paint, before any module
// has loaded; a holder's module asks it here, of the holder's own document.
const views = (holder) => holder.ownerDocument.documentElement.lfViews;
export const openingView = (holder, members) => views(holder).opening(holder, members);
export const keepView = (holder, member) => views(holder).keep(holder, member);
// What the author wrote: the early coordinator restores original widget sources
// before copying and takes off its marks and delivery's placeholders (version.js).
export const unmarkedCopy = (node) =>
  (
    node.ownerDocument?.documentElement?.lfInitial ?? document.documentElement.lfInitial
  ).authoredCopy(node);
export const draftStore = stored(() => localStorage, "local", PAGE_SCOPE);
// The delivery declares a child page's private user scope. Bootstrap reads the
// same fact before this module loads; neither derives it from the viewed revision.
export const userStore = stored(
  () => localStorage,
  "local",
  document.documentElement.dataset.lfUserScope ?? "",
);

// Disposable child pages have an exclusive URL scope. Call only after their
// browsing context has stopped: pagehide itself saves tab state.
export function discardPageStorage(url) {
  const scope = new URL(url).pathname;
  if (scope === "/") throw new Error("cannot discard root page storage");
  for (const [open, name] of [
    [() => localStorage, "local"],
    [() => sessionStorage, "session"],
  ]) {
    const store = stored(open, name, scope);
    for (const key of store.keys()) store.set(key, null);
  }
}
