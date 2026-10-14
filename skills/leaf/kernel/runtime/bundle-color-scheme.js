// runtime/color-scheme.js
var darkPreference = matchMedia("(prefers-color-scheme: dark)");
function shownScheme() {
  const schemes = getComputedStyle(document.documentElement).colorScheme.split(/\s+/);
  return schemes.includes("dark") && (darkPreference.matches || !schemes.includes("light")) ? "dark" : "light";
}

export {
  darkPreference,
  shownScheme
};
