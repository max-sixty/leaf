/* The color scheme the page is drawn in, as the user sees it now.
 *
 * The theme declares both schemes (`color-scheme: light dark`), so the user's
 * preference picks one; a page that declares only one is drawn in that one whatever
 * the preference. A reading of the user's view, such as the view report or a
 * drawing's record of the window it was drawn in, takes it from here. */

export const darkPreference = matchMedia("(prefers-color-scheme: dark)");

export function shownScheme() {
  const schemes = getComputedStyle(document.documentElement).colorScheme.split(/\s+/);
  return schemes.includes("dark") &&
    (darkPreference.matches || !schemes.includes("light"))
    ? "dark"
    : "light";
}
