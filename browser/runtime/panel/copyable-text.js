/* Read-only diagnostic text always brings its copy control. Keep the text selectable
 * when clipboard access is refused; use transport/copy-control.js for clipboard permissions,
 * plain-HTTP copying, outcome icons and announcements. This template keeps the control
 * at its render position across paints, rather than making each text's caller own one.
 * Each line stands in a box of its own, as a page's code block's do (readings/code-lines.js), so a
 * row a long line wraps onto hangs from its indent behind the face's mark. */
import { capitalized } from "../lib/words.js";
import { guard, html } from "/vendor/lit.js";
import { copyControl } from "../transport/copy-control.js";
import { indentColumns } from "../readings/code-lines.js";

/** @param {string} value */
const lines = (value) =>
  value.split(/(?<=\n)/).map((line) => {
    const indent = indentColumns(line, 8);
    return html`<span
      data-lf-pre-line
      style=${indent ? `--lf-code-indent: ${indent}` : ""}
      >${line}</span
    >`;
  });

/** @param {string} value @param {string} label */
export function copyableText(label, value) {
  return html`<div class="lf-copyable-text">
    <div class="lf-copyable-head">
      <span>${label}</span>
      ${guard([label, value], () => {
        const copy = copyControl("", {
          label: `Copy ${label}`,
          success: `${capitalized(label)} copied`,
          error: `${capitalized(label)} not copied · select the text to copy`,
          role: "symbol",
        });
        copy.value = value;
        return copy;
      })}
    </div>
    <pre tabindex="0" aria-label=${label}>${lines(value)}</pre>
  </div>`;
}
