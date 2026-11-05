/* Web Awesome 3.14.0's select close watcher can finish after a
 * keyboard gesture has reopened it, hiding an open popup. Keep the library's
 * animation primitive and public promises; only a watcher for the current open
 * state may commit after its animation. The build targets its pinned module,
 * and rejects a changed seam when upgrading Web Awesome. */
export function patchTransitions(source) {
  const watcher = "async handleOpenChange() {";
  const animation = / {6}await animateWithClass\(this\.popup\.popup, "[a-z-]+"\);/g;
  if (
    source.split(watcher).length !== 2 ||
    [...source.matchAll(animation)].length !== 2
  )
    throw new Error("Web Awesome popup transition seam changed");
  return source
    .replace(watcher, `${watcher}\n    const opening = this.open;`)
    .replaceAll(animation, "$&\n      if (this.open !== opening) return;");
}
