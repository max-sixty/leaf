/* Web Awesome 3.14.0's select and tooltip close watchers can finish after a
 * keyboard gesture has reopened them, hiding an open popup. Keep the library's
 * animation primitive and public promises; only a watcher for the current open
 * state may commit after its animation. The build targets these two pinned
 * modules, and rejects a changed seam when upgrading Web Awesome. */
export function patchTransitions(source) {
  const watcher = "async handleOpenChange() {";
  const animation = /      await animateWithClass\(this\.popup\.popup, "[a-z-]+"\);/g;
  if (
    source.split(watcher).length !== 2 ||
    [...source.matchAll(animation)].length !== 2
  )
    throw new Error("Web Awesome popup transition seam changed");
  return source
    .replace(watcher, `${watcher}\n    const opening = this.open;`)
    .replaceAll(animation, "$&\n      if (this.open !== opening) return;");
}
