// <lf-select>: Web Awesome's select under a Leaf name. Nothing here is written for
// Leaf: the declaration's `record` names the component's `value` property, so Leaf
// sets the recorded choice on it and records each `change`
// (module-plain-elements.md, "`record.property`").
import "/vendor/webawesome.esm.js";

customElements.define("lf-select", class extends customElements.get("wa-select") {});
