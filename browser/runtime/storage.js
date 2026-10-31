/* Browser state has one backing policy, selected by prepaint and shared
 * by bootstrap and the runtime. Isolated samples keep stores inside their disposable realm; ordinary
 * documents use native scoped storage, whose refusal never prevents reading. */
import { registry } from "./registry.js";
import { keeps } from "./keeps.js";
import { marks } from "./kernel-facts.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";

// ---------- which page the stores are scoped to ----------
// Prepaint declares the page scope once; widget state and chrome use that same prefix.
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
// there. `tabStore` is what only this window keeps, and it dies with the tab — the reading
// position, which panel of a widget stands open, whether design mode is on — because each
// of those is about the window rather than about the page. `draftStore` is what the user
// typed or drew into a composition the log settles (a comment, a reply, an `lf-draft`)
// and hasn't sent. The agent reads none of it, because sending is when the user says it.
// It outlives the tab, because closing one is the ordinary end of a tab here, and
// every tab shows one live copy of it (see the draft section below). An edit to a bound
// file is not one: the file on disk is what tabs share, so its buffer stays in its tab.
// `userStore` is this user's lasting preference across pages, which is the chrome
// they arrange and expect to find arranged. The stores reach this tab or this browser.
// What another browser or the agent must read is none of the three: it goes in the log,
// which every tab already follows, such as a playground's settings before the user
// submits them. The skill's `module-state.md`, "Where a widget keeps its state", tells
// package authors which kind of state goes where.
//
// Values are the store's own vocabulary, strings and null, so nothing here has an
// opinion about encoding: an absent key reads back as null, and writing null removes it.
const { stored } = document.documentElement.lfStorage;
// Two of the three are scoped to the page (PAGE_SCOPE), and the odd one out is the reason
// there are three backings: what the user arranges is theirs wherever they are reading,
// while what they typed here belongs to this page. tabStore is the only one on the helper
// surface, because only widgets keep state in the tab (lf-tabs' open panel, lf-options'
// collapsed group) — a module reaches its drafts through saveDraft/watchDraft, the chrome
// the user arranges is the runtime's own, and an export nothing imports is a promise
// nobody asked for. tab-store.js owns the portable widget store.
// Delivery carries the member selector into prepaint; generated holders use the
// registry's same declaration. Only the browser evaluates it. Reading members or
// the opening choice changes no DOM; keeping a choice owns its presentation.
const memberSelector = (holder) => registry[holder.localName]?.["x-views"]?.members;
export function viewMembers(holder) {
  return document.documentElement.lfViews.members(holder, memberSelector(holder));
}
export function openingView(holder, fallback = undefined) {
  return document.documentElement.lfViews.opening(
    holder,
    fallback,
    memberSelector(holder),
  );
}
export function markViews(holder) {
  const declaration = registry[holder.localName]?.["x-views"];
  if (!declaration) return;
  keeps(holder, marks["x-views"].paint, declaration.parts ? "parts" : "");
  keeps(holder, PAGE_PAINT_ATTRIBUTE.viewMembers, declaration.members);
}
export function keepView(holder, member, leaving = null) {
  markViews(holder);
  return document.documentElement.lfViews.keep(holder, member, leaving);
}
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
