/* Authored top-layer UI held measurable until the page is presented.

   `showModal()` calls from authored main are temporarily represented as measurable
   non-modal dialogs; `presentPage` promotes only connected, still-open dialogs whose
   reconciled branch remains visible. This prevents a modal's top-layer inertness from
   disabling the recovery chrome. `showPopover()` opens natively so the widget can
   observe and cancel it through `:popover-open`; the startup stylesheet withholds its
   top-layer paint and interaction, and `presentPage` closes any open popover whose
   reconciled branch is no longer visible. */

import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";

const presentedAttribute = PAGE_PAINT_ATTRIBUTE.presented;

// A modal is promoted into the top layer and makes the rest of the document inert. Both
// facts escape an ancestor boundary: hiding it with CSS alone would still disable the
// rest of the document while first replay waits. Custom
// widgets load after this module, so turn authored-main showModal() calls into measurable,
// non-modal dialogs until replay has produced the page. A widget can still close one
// while waiting; only a connected, still-open dialog whose post-replay place is visible
// is promoted, so replay retiring its authored branch cannot resurrect stale UI on top.
// Popovers open for real too. The startup stylesheet withholds their top-layer paint
// and interaction, while the native :popover-open state lets a widget's ordinary
// `if (open) hidePopover()` path cancel the pending surface before replay lands.
const nativeDialogShow = HTMLDialogElement.prototype.show;
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativeDialogClose = HTMLDialogElement.prototype.close;
const deferredModals = new Set();
const nativePopoverShow = HTMLElement.prototype.showPopover;
const nativePopoverHide = HTMLElement.prototype.hidePopover;
const deferredPopovers = new Set();
const inAuthoredMain = (node) => {
  const main = document.querySelector("body > main");
  for (let at = node; at;) {
    if (at === main) return true;
    if (at.parentElement) at = at.parentElement;
    else {
      const root = at.getRootNode();
      at = root instanceof ShadowRoot ? root.host : null;
    }
  }
  return false;
};
const authoredBranchVisible = (node) => {
  const main = document.querySelector("body > main");
  for (let at = node.parentElement ?? node.getRootNode()?.host; at;) {
    if (at === main) return true;
    if (!at.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
      return false;
    at = at.parentElement ?? at.getRootNode()?.host;
  }
  return false;
};
HTMLDialogElement.prototype.showModal = function () {
  if (!document.body.hasAttribute(presentedAttribute) && inAuthoredMain(this)) {
    if (!this.open) nativeDialogShow.call(this);
    deferredModals.add(this);
    return;
  }
  return nativeDialogShowModal.call(this);
};
HTMLDialogElement.prototype.show = function () {
  deferredModals.delete(this);
  return nativeDialogShow.call(this);
};
HTMLDialogElement.prototype.close = function (returnValue) {
  deferredModals.delete(this);
  return nativeDialogClose.call(this, returnValue);
};
HTMLElement.prototype.showPopover = function (...args) {
  if (!document.body.hasAttribute(presentedAttribute) && inAuthoredMain(this)) {
    deferredPopovers.add(this);
  }
  return nativePopoverShow.apply(this, args);
};
HTMLElement.prototype.hidePopover = function (...args) {
  deferredPopovers.delete(this);
  return nativePopoverHide.apply(this, args);
};
export function promoteDeferredModals() {
  for (const dialog of deferredModals) {
    if (
      !dialog.isConnected ||
      !dialog.open ||
      !inAuthoredMain(dialog) ||
      !dialog.checkVisibility({ opacityProperty: true, visibilityProperty: true })
    ) {
      dialog.removeAttribute("open");
      continue;
    }
    // Removing the non-modal state directly emits no spurious close event; the widget
    // asked for one opening, and this is that opening finally becoming modal.
    dialog.removeAttribute("open");
    nativeDialogShowModal.call(dialog);
  }
  deferredModals.clear();
  for (const popover of deferredPopovers) {
    if (
      popover.matches(":popover-open") &&
      (!popover.isConnected ||
        !inAuthoredMain(popover) ||
        !authoredBranchVisible(popover))
    )
      nativePopoverHide.call(popover);
  }
  deferredPopovers.clear();
}
