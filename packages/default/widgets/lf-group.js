/* A group is a named set of what it holds. Its `label` names it wherever Leaf names it,
   and a widget that asks inside it takes the innermost group as its question. The
   label is data: the group draws none of it, and any heading it shows is the author's
   own child. This module tells assistive technology it is a group and what its name
   is, as a <fieldset> would, and builds nothing among the authored children, so a
   revision edits inside them in place. */
import { keeps } from "/runtime/lib/keeps.js";

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
