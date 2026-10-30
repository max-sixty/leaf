/* The color scheme the page is drawn in, as the user sees it now.
 *
 * A page that declares both schemes on its root (`color-scheme: light dark`, as the
 * reading theme does) is drawn in the one the user's preference picks; a page that
 * declares one, or none, is drawn in that one, or light, whatever the preference. A reading of the user's view, such as the view report or a
 * drawing's record of the window it was drawn in, takes it from here. */

export const darkPreference = matchMedia("(prefers-color-scheme: dark)");

export function shownScheme() {
  const schemes = getComputedStyle(document.documentElement).colorScheme.split(/\s+/);
  return schemes.includes("dark") &&
    (darkPreference.matches || !schemes.includes("light"))
    ? "dark"
    : "light";
}
