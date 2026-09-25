/* The layer stack: the native layers standing over the page, in the order they opened.

   One ordered list holds every popover and modal dialog standing over the page, oldest at
   the bottom. Each pushes an entry as it opens, so their order against each other is
   recorded when it happens rather than inferred from focus ancestry and open state at
   every read. `kind` is `popover` or `modal`; the dispatcher tiers the scopes over them
   and makes a modal a floor.

   A layer may open through a prototype method or through declarative popover activation,
   and a popover need not move focus into itself, so every opener declares its own
   opening here: the `showModal` and `showPopover` patches, and `beforetoggle` and `toggle`
   at the document and at each declared shadow boundary. `beforetoggle` makes a declarative
   opening visible synchronously to the command that caused it; `toggle` follows the
   completed native transition, and carries an opening whose earlier declarations this
   module was not yet listening for. An opening arrives once, so a declaration naming a
   layer the stack already holds leaves its entry where the arrival put it, however many
   more times that same opening is declared. Dismissal stays each layer's own `popover`
   or `closedby` value. A popover opened declaratively inside a shadow root nobody staged
   fires a `toggle` this module cannot hear, so it never reaches the stack; `shadowStage`
   is the declared route for a widget's shadow tree.

   Every read prunes first, and an entry whose surface no longer stands is removed
   wherever it sits, so a dialog closed by script beneath another layer cannot linger as
   a false floor. Modal entry dismisses auto and hint popovers through the platform
   contract; a later opening joins as a new layer rather than preserving a hidden entry.

   A covering auxiliary surface is not an entry. It takes modal semantics without entering
   the browser's top layer, and the dispatcher reads that surface as the floor when no
   modal entry stands; this stack never sees it.

   What Escape takes off is not recorded here, and not recorded anywhere: every step is
   read off the state standing in front of the user, by the owner of that state, through
   `pageRung` and the scopes each owner declares. `register.js` orders those steps and
   `dispatch.js` resolves one of them per press. This module answers only which native
   layers the browser is holding, because that is the one fact about the scene that its
   own DOM cannot be asked for in order. */

const entries = [];
const watchedRoots = new WeakSet();
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativePopoverShow = HTMLElement.prototype.showPopover;

const held = (node) =>
  Boolean(node?.isConnected) && node.matches(":popover-open, dialog:modal");

function prune() {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (!entries[index].active()) entries.splice(index, 1);
  }
}

// A standing entry is left alone wherever it sits, and not merely where it is already on
// top: `toggle` is queued rather than synchronous, so moving a layer on that last
// declaration would make it the newest thing on the stack after something else opened over
// it. A closed entry is pruned and an actual reopening joins at the top.
function pushNativeLayer(node, kind) {
  const at = entries.findIndex((entry) => entry.root === node);
  const standing = at < 0 ? null : entries[at];
  if (standing?.active()) return;
  prune();
  entries.push({ root: node, kind, active: () => held(node) });
}

HTMLDialogElement.prototype.showModal = function () {
  if (!this.matches(":modal")) pushNativeLayer(this, "modal");
  return nativeDialogShowModal.call(this);
};

HTMLElement.prototype.showPopover = function (...args) {
  if (!this.matches(":popover-open")) pushNativeLayer(this, "popover");
  return nativePopoverShow.apply(this, args);
};

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

// The layers the browser is holding, bottom to top.
export function nativeLayers() {
  prune();
  return entries.filter((entry) => entry.active());
}

// Modal owners close pre-existing popovers before establishing a new floor.
export const openPopovers = () =>
  nativeLayers()
    .filter((entry) => entry.kind === "popover")
    .map((entry) => entry.root);
