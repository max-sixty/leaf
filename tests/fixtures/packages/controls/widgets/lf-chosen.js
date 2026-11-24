// <lf-chosen>: the choice another widget holds, as words.
//
// Nothing here is written for Leaf, which sets `value` from the output of the widget
// its `for` names (package-data.md, "Widget outputs").
customElements.define(
  "lf-chosen",
  class extends HTMLElement {
    set value(next) {
      this.textContent = next ?? "";
    }
  },
);
