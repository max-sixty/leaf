// The glue version of pkg/widgets/lf-choice.js, before the `property`/`event` record form:
// the manifest's record was {"kind": "value", "attr": "value"} alone.
import "/vendor/webawesome.esm.js";
customElements.define(
  "lf-choice",
  class extends customElements.get("wa-select") {
    set state(next) {
      this.value = next.pick.value ?? "";
    }
    constructor() {
      super();
      this.addEventListener("change", () =>
        this.dispatchEvent(
          new CustomEvent("lf-action", {
            bubbles: true,
            composed: true,
            cancelable: true,
            detail: { verb: "pick", detail: { value: this.value }, says: `Picked ${this.value}` },
          }),
        ),
      );
    }
  },
);
