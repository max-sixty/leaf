/* One native copy button for code blocks and the floating panel. The Clipboard API
 * performs the action; a retained Solid glyph and Leaf's status line show its
 * outcome, including activation while focus stands elsewhere. A failed copy remains
 * in Leaf's errors after the transient face resets. */
import { html, createView, Show } from "/vendor/browser-runtime.js";
import { offer, el } from "./widget-elements.js";
import { iconElement } from "./icons.js";
import { notice } from "./notifications.js";
import { raiseError } from "./errors.js";
import { keeps } from "./keeps.js";
import { whileConnected } from "./arrivals.js";

/** A copy control named `label` that says `success` or `error` once pressed. */
export function copyControl(
  className,
  { label = "Copy", title = label, success, error },
) {
  const copy = offer("button", `lf-copy-control ${className}`);
  copy.type = "button";
  copy.setAttribute("aria-label", label);
  copy.title = title;
  const glyph = el("span", "lf-copy-glyph");
  glyph.setAttribute("aria-hidden", "true");
  copy.append(glyph);
  const drawing = createView(
    glyph,
    (read) =>
      html`${Show({
        get when() {
          return read().icon;
        },
        keyed: true,
        children: (icon) => iconElement(icon, "lf-copy-icon"),
      })}`,
    { icon: "copy" },
  );
  let reset;
  let busy = false;
  const idle = () => {
    clearTimeout(reset);
    drawing.update({ icon: "copy" });
    keeps(copy, "aria-label", label);
    keeps(copy, "title", title);
  };
  whileConnected(copy, () => {
    idle();
    return () => clearTimeout(reset);
  });
  copy.addEventListener("click", async (event) => {
    if (event.defaultPrevented || busy || copy.disabled) return;
    busy = true;
    clearTimeout(reset);
    try {
      await navigator.clipboard.writeText(copy.value);
      drawing.update({ icon: "check" });
      keeps(copy, "aria-label", success);
      keeps(copy, "title", success);
      notice(success);
      copy.dispatchEvent(new CustomEvent("lf-copy", { bubbles: true, composed: true }));
    } catch {
      drawing.update({ icon: "cross" });
      keeps(copy, "aria-label", error);
      keeps(copy, "title", error);
      raiseError(error);
      copy.dispatchEvent(
        new CustomEvent("lf-copy-error", { bubbles: true, composed: true }),
      );
    } finally {
      busy = false;
      if (copy.isConnected) reset = setTimeout(idle, 1500);
    }
  });
  return copy;
}
