/* A run's cases, one shown at a time: the fixture for threads seated on a datum
 * that keeps its identity across new values. A case not shown is
 * `hidden="until-found"`, and opens on `beforematch`, as Leaf's travel and the
 * browser's find open it, hiding the case it leaves before the handler returns.
 * The shown case seats the threads on it, and the comment box, in its own outlet;
 * a hidden case seats none, so its threads stay in the margin. */
import { html, nothing, repeat } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";

customElements.define(
  "lf-test-review",
  class extends LeafElement {
    static properties = { value: { attribute: false } };

    constructor() {
      super();
      /** @type {{cases: {id: string, title: string}[]} | null} */
      this.value = null;
    }

    /** @type {string | null} */
    #shown = null;
    /** @type {unknown} */
    #drawn;

    /** @param {string} id */
    #show(id) {
      if (id === this.#shown) return;
      this.#shown = id;
      this.requestUpdate();
      this.performUpdate();
      this.dispatchEvent(
        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
      );
    }

    /** @param {readonly import("/runtime/records/thread/surfaces.js").OutletTarget[]} targets */
    threadOutlets(targets) {
      return targets.map(({ anchor, placement }) =>
        anchor.datum && anchor.datum === this.#shown
          ? (placement.datumElement?.querySelector(":scope > .test-threads") ?? null)
          : null,
      );
    }

    render() {
      const cases = this.value?.cases ?? [];
      if (!cases.some(({ id }) => id === this.#shown))
        this.#shown = cases[0]?.id ?? null;
      return html`${repeat(
        cases,
        ({ id }) => id,
        ({ id, title }, index) =>
          html`<article
            class="test-case"
            data-lf-datum=${id}
            data-lf-identity=${id}
            data-lf-datum-label=${title}
            data-lf-origin-path=${JSON.stringify(["cases", index])}
            hidden=${id === this.#shown ? nothing : "until-found"}
            @beforematch=${(/** @type {Event} */ event) => {
              if (event.target === event.currentTarget) this.#show(id);
            }}
          >
            <h3>${title}</h3>
            <div class="test-threads lf-ui" data-lf-gen="1"></div>
          </article>`,
      )}`;
    }

    /** @param {import("lit").PropertyValues} changed */
    updated(changed) {
      super.updated(changed);
      if (this.value === this.#drawn) return;
      this.#drawn = this.value;
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value: this.value } }));
    }
  },
);
