/* Browser working state has one backing policy, selected by prepaint before widgets
 * draw. Isolated samples keep all stores inside their disposable realm; ordinary
 * documents use native scoped storage, whose refusal never prevents reading. */

// ---------- which page the stores are scoped to ----------
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
// typed into a composition the log settles (a comment, a reply, an `lf-draft`) and hasn't
// sent: it outlives the tab, because closing one is the ordinary end of a tab here, and
// every tab shows one live copy of it (see the draft section below). An edit to a bound
// file is not one: the file on disk is what tabs share, so its buffer is working state.
// `userStore` is this user's lasting preference across pages, which is the chrome
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
export const openingView = (holder, members, fallback) =>
  views(holder).opening(holder, members, fallback);
export const keepView = (holder, member) => views(holder).keep(holder, member);
export const draftStore = stored(() => localStorage, "local", PAGE_SCOPE);
// The delivery declares a child page's private user scope. Bootstrap reads the
// same fact before this module loads; neither derives it from the viewed revision.
export const userStore = document.documentElement.lfStorage.userStore;
// Which of a view's arrangements the user chose, such as On me's grouping, kept for
// every page as the chrome they arrange is: the stored value while it is one of
// `values`, else null, as a store that refuses reads, so the caller's default stands.
export const userChoice = (key, values) =>
  Object.freeze({
    read: () => {
      const value = userStore.get(key);
      return values.includes(value) ? value : null;
    },
    write: (value) => userStore.set(key, value),
  });
