// @ts-check
/* One member of several on screen at a time, as a tab set's panels or a deck's cards
   are. The others are `hidden="until-found"`, so the browser's find-in-page, a fragment
   and a page's travel to a passage still reach what they hold, and fire `beforematch`
   on the member holding it, which the widget hears to show that member.

   The member shown is remembered for this browser tab, by its id or its first
   descendant's, so a reload or a return through history opens on it. A visit to an
   address whose fragment names a place inside a member opens that member instead, as
   does `widget:key`, by the widget's id before the colon; a reload keeps the address
   it was first given, which may no longer name the member shown. A widget without an
   id remembers nothing. Before the module that shows one member runs, every member
   stands in the page; a widget's stylesheet that should show only one by then says so
   itself, as with `:not(:defined)`. */

/** @param {Element} holder */
const keyOf = (holder) => `lf-shown:${location.pathname}#${holder.id}`;

/** @param {string} raw */
const decoded = (raw) => {
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
};

/** Show `member` of `members` and hide the rest, or show none where it is null.
 * `leaving` stays shown too, for its exit, without being remembered.
 * @param {Element} holder @param {readonly Element[]} members
 * @param {Element | null} member @param {Element | null} [leaving] */
export function showMember(holder, members, member, leaving = null) {
  for (const each of members) {
    if (each === member || each === leaving) {
      if (each.hasAttribute("hidden")) each.removeAttribute("hidden");
    } else if (each.getAttribute("hidden") !== "until-found")
      each.setAttribute("hidden", "until-found");
  }
  const id = member && (member.id || member.querySelector("[id]")?.id);
  if (!id || !holder.id) return;
  try {
    sessionStorage.setItem(keyOf(holder), id);
  } catch {
    // A tab whose storage is off remembers nothing.
  }
}

/** The member to open on: on a visit, the one holding the place the address names,
 * else the one this tab showed last; on a reload or a return, the other way round;
 * else null.
 * @template {Element} T @param {Element} holder @param {readonly T[]} members
 * @returns {T | null} */
export function openingMember(holder, members) {
  const raw = location.hash.slice(1);
  const at = raw.indexOf(":");
  const named = [decoded(raw), at > 0 ? decoded(raw.slice(0, at)) : null];
  let kept = null;
  try {
    if (holder.id) kept = sessionStorage.getItem(keyOf(holder));
  } catch {
    // A tab whose storage is off remembers nothing.
  }
  const visit =
    /** @type {PerformanceNavigationTiming | undefined} */ (
      performance.getEntriesByType("navigation")[0]
    )?.type === "navigate";
  for (const id of visit ? [...named, kept] : [kept, ...named]) {
    const target = id ? document.getElementById(id) : null;
    const member = target && members.find((each) => each.contains(target));
    if (member) return member;
  }
  return null;
}
