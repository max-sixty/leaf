/* The browser's modal-dialog and popover stack as a keyboard ownership boundary.

   A layer may open through a prototype method or declarative popover activation, and a
   popover need not move focus into itself. Record both routes at every declared shadow
   boundary, then confirm native state at each read so cancellation and light dismissal
   cannot leave a stale owner. The monotonically increasing order survives a temporarily
   hidden popover and distinguishes a newer cover from an older layer revealed beneath a
   closed return frame. */

const layers = [];
const orders = new WeakMap();
const watchedRoots = new WeakSet();
let nextOrder = 0;
const open = (node) =>
  node?.isConnected && node.matches?.(":popover-open, dialog:modal");

export function rememberNativeLayer(node) {
  if (layers.at(-1) === node && open(node)) return;
  const prior = layers.indexOf(node);
  if (prior >= 0) layers.splice(prior, 1);
  layers.push(node);
  orders.set(node, ++nextOrder);
}

export const nativeLayerOrder = (node) => orders.get(node) ?? 0;

export function nativeLayersFor(node) {
  const containing = [];
  for (let at = node; at;) {
    if (open(at)) containing.push(at);
    at = at.parentElement ?? at.getRootNode()?.host ?? null;
  }
  return containing;
}

export const nativeLayerFor = (node) => nativeLayersFor(node)[0] ?? null;

const prune = () => {
  for (let index = layers.length - 1; index >= 0; index -= 1)
    if (!open(layers[index])) layers.splice(index, 1);
};

export function currentNativeLayer(focused = null) {
  const containing = nativeLayerFor(focused);
  prune();
  return layers.at(-1) ?? containing;
}

export function currentModalLayer(focused = null) {
  const containing = nativeLayersFor(focused).find((node) =>
    node.matches("dialog:modal"),
  );
  prune();
  for (let index = layers.length - 1; index >= 0; index -= 1)
    if (layers[index].matches("dialog:modal")) return layers[index];
  return containing ?? null;
}

export function watchNativeLayers(root) {
  if (watchedRoots.has(root)) return;
  watchedRoots.add(root);
  const opened = (event) => {
    if (event.newState === "open" && event.target?.matches?.("[popover]"))
      rememberNativeLayer(event.target);
  };
  // `beforetoggle` makes a declarative opening visible synchronously to the command
  // return frame that caused it. `toggle` follows the completed native transition and
  // corrects the order if an opening reentered another popover's beforetoggle handler.
  root.addEventListener("beforetoggle", opened, true);
  root.addEventListener("toggle", opened, true);
}

watchNativeLayers(document);
