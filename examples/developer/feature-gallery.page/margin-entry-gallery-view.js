/* Lit view for the margin-entry exhibit, constructed during widget setup. The
 * exhibit's entry is a real contribution, which Leaf draws at the exhibit's margin and
 * in Page Map. */
import { html, ref } from "/vendor/lit.js";

export function createView(host) {
  const view = {
    result: null,
    render: () =>
      html`<div class="margin-entry-gallery-projection">
        <strong class="margin-entry-gallery-heading" data-lf-gen="1">Projection</strong>
        <span class="margin-entry-gallery-summary" data-lf-gen="1"
          >Compact margin face · full Page Map row</span
        >
        <p class="margin-entry-gallery-projection-guide" data-lf-gen="1">
          Use the live Inspect projection control at this exhibit's margin. Press g then
          Shift+P to find the same disclosure as a labeled Page Map row.
        </p>
        <p
          class="margin-entry-gallery-projection-result"
          data-lf-gen="1"
          ${ref((node) => {
            if (node) view.result = node;
          })}
          id=${`${host.id}-projection-result`}
          hidden
        >
          The same contributed action serves both projections.
        </p>
      </div>`,
  };
  host.replaceChildren();
  return view;
}
