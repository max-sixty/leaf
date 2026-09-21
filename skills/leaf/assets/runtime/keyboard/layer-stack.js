/* The layer stack: the native layers standing over the page, in the order they opened.

   One ordered list holds every popover and modal dialog standing over the page, oldest at
   the bottom. Each pushes an entry as it opens, so their order against each other is
   recorded when it happens rather than inferred from focus ancestry and open state at
   every read. `kind` is `popover` or `modal`; the dispatcher tiers the scopes over them
   and makes a modal a floor.

   A layer may open through a prototype method or through declarative popover activation,
   and a popover need not move focus into itself, so every opener declares its own
   opening: the `showModal` and `showPopover` patches, and `beforetoggle` and `toggle` at
   the document and at each declared shadow boundary. `beforetoggle` makes a declarative
   opening visible synchronously to the command that caused it; `toggle` follows the
   completed native transition, and carries an opening whose earlier declarations this
   module was not yet listening for. An opening arrives once, so a declaration naming a
   layer the stack already holds leaves its entry where the arrival put it, however many
   more times that same opening is declared. Dismissal stays each layer's own `popover`
   or `closedby` value. A popover opened declaratively inside a shadow root nobody staged
   fires a `toggle` this module cannot hear, so it never reaches the stack; `shadowStage`
   is the declared route for a widget's shadow tree.

   Every read prunes first, and an entry whose surface no longer stands is removed
   wherever it sits, so a dialog closed by script beneath a re-shown popover cannot linger
   as a false floor. Beneath an active modal, not standing does not show a surface gone:
   `showModal` hides the auto popovers beneath it and the command reference re-shows the
   ones it displaced, so every entry under a live modal waits, whatever took its surface
   down. The modal marks them suspended as it is pushed, and only a suspended or standing
   entry is lifted when its node reopens.

   A covering auxiliary surface is not an entry. It takes modal semantics without entering
   the browser's top layer, and the dispatcher reads that surface as the floor when no
   modal entry stands; this stack never sees it.

   What Escape takes off is not recorded here, and not recorded anywhere: every step is
   read off the state standing in front of the reader, by the owner of that state, through
   `pageRung` and the scopes each owner declares. `register.js` orders those steps and
   `dispatch.js` resolves one of them per press. This module answers only which native
   layers the browser is holding, because that is the one fact about the scene that its
   own DOM cannot be asked for in order. */

const entries = [];
const watchedRoots = new WeakSet();

const held = (node) =>
  Boolean(node?.isConnected) && node.matches(":popover-open, dialog:modal");

// Top down, so the newest modal is known before the entries it covers are judged. An
// entry seen standing sheds its suspension mark: the mark is for the gap between a modal
// hiding a surface and that surface's return, and an opening after this one starts fresh.
function prune() {
  let covered = false;
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const entry = entries[index];
    if (entry.active()) {
      entry.suspended = false;
      covered ||= entry.kind === "modal";
      continue;
    }
    if (!covered) entries.splice(index, 1);
  }
}

// An opening that names a node already on the stack keeps that entry when the entry is
// standing or a modal suspended it: the command reference re-shows the popovers its modal
// displaced, and one that comes back is the layer the reader was already in rather than a
// fresh one over it. Lifting a suspended entry before the prune keeps it across the moment
// between the modal's close and the popover's return, when neither stands. An entry that
// simply closed, by light dismissal or by script, is not lifted: the prune retires it and
// the reopening starts a fresh entry.
//
// A modal marks what it covers as it is pushed, before the native call hides the auto
// popovers beneath it, so the mark is set by the cause rather than by whichever read
// happens to run while the modal stands. The mark stays through the return: one opening is
// declared more than once — by the patched method before the native call, by `beforetoggle`
// during it, and by `toggle` once the native transition completes — and a later declaration
// finds the entry lifted but not yet open.
//
// A standing entry is left alone wherever it sits, and not merely where it is already on
// top: `toggle` is queued rather than synchronous, so lifting a layer on that last
// declaration would make it the newest thing on the stack after something else had opened
// over it.
export function pushNativeLayer(node, kind) {
  const at = entries.findIndex((entry) => entry.root === node);
  const standing = at < 0 ? null : entries[at];
  if (standing?.active()) return;
  const lifted = standing?.suspended ? standing : null;
  if (lifted) {
    entries.splice(at, 1);
    lifted.kind = kind;
  }
  prune();
  if (kind === "modal") for (const entry of entries) entry.suspended = true;
  entries.push(
    lifted ?? { root: node, kind, active: () => held(node), suspended: false },
  );
}

export function watchLayers(root) {
  if (watchedRoots.has(root)) return;
  watchedRoots.add(root);
  const opened = (event) => {
    if (event.newState === "open" && event.target?.matches?.("[popover]"))
      pushNativeLayer(event.target, "popover");
  };
  root.addEventListener("beforetoggle", opened, true);
  root.addEventListener("toggle", opened, true);
}

watchLayers(document);

// The layers the browser is holding, bottom to top. A suspended entry is not one of them:
// its surface is hidden under a modal, so no scope is standing inside it.
export function nativeLayers() {
  prune();
  return entries.filter((entry) => entry.active());
}

// Modal owners close pre-existing popovers before establishing a new floor.
export const openPopovers = () =>
  nativeLayers()
    .filter((entry) => entry.kind === "popover")
    .map((entry) => entry.root);
