/* Read-only diagnostic text always brings its copy control. Keep the text selectable
 * when clipboard access is refused; use copy-control.js for clipboard permissions,
 * plain-HTTP copying, outcome icons and announcements. This template keeps the control
 * at its render position across paints, rather than making each text's caller own one. */
import { guard, html } from "/runtime/framework.js";
import { copyControl } from "./copy-control.js";

export function copyableText(label, value) {
  return html`<div class="lf-copyable-text">
    <div class="lf-copyable-head">
      <span>${label}</span>
      ${guard([label, value], () => {
        const copy = copyControl("", {
          label: `Copy ${label}`,
          success: `${label[0].toUpperCase()}${label.slice(1)} copied`,
          error: `${label[0].toUpperCase()}${label.slice(1)} not copied · select the text to copy`,
        });
        copy.value = value;
        return copy;
      })}
    </div>
    <pre tabindex="0" aria-label=${label}>${value}</pre>
  </div>`;
}
