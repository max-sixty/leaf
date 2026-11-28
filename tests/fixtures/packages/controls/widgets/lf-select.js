// <lf-select>: the Leaf element round Web Awesome's select. The page writes the select
// inside it under the library's own tag, which the library's styles and its options
// find it by. Nothing in the library is written for Leaf: the declaration's `record`
// names `value`, this element keeps that property on the select it holds, and the
// select's `change` reaches it by bubbling
// (module-widgets.md, "A third-party component").
import "/vendor/webawesome.esm.js";

customElements.define(
  "lf-select",
  class extends HTMLElement {
    get value() {
      return this.querySelector("wa-select").value;
    }
    set value(next) {
      this.querySelector("wa-select").value = next;
    }
  },
);
