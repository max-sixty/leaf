/* A group is a named set of what it holds. Its `label` names it wherever Leaf names it,
   and a widget that asks inside it takes the innermost group as its question; the
   runtime writes the label as the group's title (`says`). This module tells assistive
   technology it is a group and what its name is, as a <fieldset> would, and builds
   nothing among the authored children, so a revision edits inside them in place. */
import { keeps } from "/runtime/widget-api.js";

customElements.define(
  "lf-group",
  class extends HTMLElement {
    static lfPatch = "members";

    connectedCallback() {
      keeps(this, "role", "group");
      keeps(this, "aria-label", this.getAttribute("label"));
    }
  },
);
