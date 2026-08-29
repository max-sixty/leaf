export function createDeferredModals({ presentedAttribute }) {
  // A modal is promoted into the top layer and makes the rest of the document inert. Both
  // facts escape an ancestor paint gate: hiding it with CSS alone would still disable the
  // Threads chrome that deliberately remains usable while first replay waits. Custom
  // widgets load after this module, so turn authored-main showModal() calls into measurable,
  // non-modal dialogs until replay has produced the page. A widget can still close one
  // while waiting; only a connected, still-open dialog whose post-replay place is visible
  // is promoted, so replay retiring its authored branch cannot resurrect stale UI on top.
  const nativeDialogShow = HTMLDialogElement.prototype.show;
  const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
  const nativeDialogClose = HTMLDialogElement.prototype.close;
  const deferredModals = new Set();
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
  function promoteDeferredModals() {
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
  }

  return { promoteDeferredModals };
}
