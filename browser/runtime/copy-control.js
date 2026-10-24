/* Leaf's copy control: Web Awesome's copy button, which copies its `value` and shows
 * the result on its own face, a check or a cross where its copy icon stood, and Leaf
 * says the same words in its status line, since focus need not be on the control to
 * have pressed it. Every copy Leaf offers is this one control, so a code block and the
 * floating panel's About rows look and answer alike.
 * A control wrapping a trigger of its own wears that trigger's face
 * instead of the icon. A failed copy remains an error after the control's transient
 * face changes again; Web Awesome announces the outcome itself. */
import { offer } from "./widget-elements.js";
import { notice } from "./notifications.js";
import { raiseError } from "./errors.js";

// Plain HTTP on a machine name has no Clipboard API. A copy press can still use the
// browser's selection command there. Embedded samples deliberately cannot write the
// clipboard, so a frame never bypasses its own permission path.
function copyThroughSelection(value) {
  if (!value) return false;
  const selection = document.getSelection();
  const ranges = selection
    ? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i))
    : [];
  let focused = document.activeElement;
  while (focused?.shadowRoot?.activeElement)
    focused = focused.shadowRoot.activeElement;
  const field = document.createElement("textarea");
  field.value = value;
  field.style.cssText = "position: fixed; left: -9999px; top: 0";
  document.body.append(field);
  try {
    field.focus({ preventScroll: true });
    field.select();
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    field.remove();
    selection?.removeAllRanges();
    for (const range of ranges) selection?.addRange(range);
    if (focused instanceof HTMLElement) focused.focus({ preventScroll: true });
  }
}

/** A copy control named `label` that says `success` or `error` once pressed. */
export function copyControl(className, { label = "", success, error }) {
  const copy = offer("wa-copy-button", className);
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
        if (isSecureContext || window !== window.top || navigator.clipboard?.writeText)
          return;
        event.stopPropagation();
        if (event.defaultPrevented || copy.disabled || copy.isCopying) return;
        copy.isCopying = true;
        const copied = copyThroughSelection(copy.value);
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
