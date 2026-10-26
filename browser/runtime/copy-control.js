/* Leaf's copy control: Web Awesome's copy button, which copies its `value` and shows
 * the result on its own face, a check or a cross where its copy icon stood, and Leaf
 * says the same words in its status line, since focus need not be on the control to
 * have pressed it. Every copy Leaf offers is this one control, so a code block and the
 * floating panel's About rows look and answer alike. Its icons are Leaf's (icons.js),
 * `icon` at rest and the check or cross for the result, since Web Awesome's glyphs fill
 * their box and stood larger than the icons beside them at one size.
 * A control wrapping a trigger of its own wears that trigger's face
 * instead of the icon. A failed copy remains an error after the control's transient
 * face changes again; Web Awesome announces the outcome itself. */
import { offer, offerActionElement } from "./widget-elements.js";
import { iconElement } from "./icons.js";
import { notice } from "./notifications.js";
import { raiseError } from "./errors.js";
import { focused, focusDestination } from "./focus.js";
import { nativeLayerHolding } from "./shadow-tree.js";

// Plain HTTP on a machine name has no Clipboard API. A copy press can still use the
// browser's selection command there. Embedded samples deliberately cannot write the
// clipboard, so a frame never bypasses its own permission path.
function copyThroughSelection(value, trigger) {
  if (!value) return false;
  const selection = document.getSelection();
  const ranges = selection
    ? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i))
    : [];
  const before = focused();
  const field = document.createElement("textarea");
  field.value = value;
  field.style.cssText = "position: fixed; left: -9999px; top: 0";
  // A modal makes the rest of the document inert, including a field at body level.
  (nativeLayerHolding(trigger) ?? document.body).append(field);
  try {
    focusDestination(field, "return");
    field.select();
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    field.remove();
    selection?.removeAllRanges();
    for (const range of ranges) selection?.addRange(range);
    if (before?.isConnected) focusDestination(before, "return");
  }
}

/** A copy control named `label`, drawn with `icon`, that says `success` or `error`
 * once pressed, wearing the face of `role` where one is given (`offerAction`). */
export function copyControl(
  className,
  { label = "", success, error, icon = "copy", role = undefined },
) {
  const copy = role
    ? offerActionElement(document.createElement("wa-copy-button"), role, className)
    : offer("wa-copy-button", className);
  for (const [name, slot] of [
    [icon, "copy-icon"],
    ["check", "success-icon"],
    ["cross", "error-icon"],
  ])
    copy.append(Object.assign(iconElement(name, "lf-copy-icon"), { slot }));
  if (label) copy.copyLabel = label;
  copy.successLabel = success;
  copy.errorLabel = error;
  copy.tooltip = "none";
  // Web Awesome announces the result; Leaf puts the same words in its status line.
  copy.addEventListener("wa-copy", () => notice(success, { announce: false }));
  copy.addEventListener("wa-error", () => raiseError(error, { announce: false }));
  // The code block attaches its source reader immediately after creating this host.
  // Register last so a press reads the current source while activation is still live.
  queueMicrotask(() =>
    copy.addEventListener(
      "click",
      (event) => {
        if (
          window.isSecureContext ||
          window !== window.top ||
          navigator.clipboard?.writeText
        )
          return;
        event.stopPropagation();
        if (event.defaultPrevented || copy.disabled || copy.isCopying) return;
        copy.isCopying = true;
        const copied = copyThroughSelection(copy.value, copy);
        // Use the component's normal icon, announcement and lock reset.
        /** @type {any} */ (copy).showStatus(copied ? "success" : "error");
        copy.dispatchEvent(
          copied
            ? new CustomEvent("wa-copy", {
                bubbles: true,
                composed: true,
                detail: { value: copy.value },
              })
            : new Event("wa-error", { bubbles: true, composed: true }),
        );
      },
      { capture: true },
    ),
  );
  return copy;
}
