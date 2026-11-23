/* A run's cases, one shown at a time, each owed the user an answer
 * (`awaits.records`): the fixture for obligations owed per record of a bound source,
 * and for threads seated on a datum that keeps its identity across new values.
 * Each case is a datum the user's Looks right answers. A case not shown is
 * `hidden="until-found"`, and opens on `beforematch`, as Leaf's travel and the
 * browser's find open it, hiding the case it leaves before the handler returns.
 * The shown case seats the threads on it, and the comment box, in its own outlet;
 * a hidden case seats none, so its threads stay in the margin. */
import { html, live, nothing, repeat } from "/vendor/lit.js";
import { LeafElement, threadSurface } from "/runtime/widget-api.js";

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
    #approved(id) {
      const review = this.state?.review;
      return Boolean(
        review && "units" in review && review.units[id]?.detail.approved === true,
      );
    }

    /** @param {string} id */
    #show(id) {
      if (id === this.#shown) return;
      this.#shown = id;
      this.requestUpdate();
      this.performUpdate();
      threadSurface(this).update();
    }

    /** @param {string} id @param {boolean} approved */
    #review(id, approved) {
      this.controller.dispatch({
        kind: "action",
        verb: "review",
        detail: { case: id, approved },
        says: approved ? "Looks right" : "Approval removed",
      });
    }

    /** @param {readonly import("/runtime/thread/surfaces.js").OutletTarget[]} targets */
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
      const available = Boolean(this.reading?.actions.review?.available);
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
            <label
              ><input
                type="checkbox"
                ?disabled=${!available}
                .checked=${live(this.#approved(id))}
                @change=${(/** @type {Event} */ event) =>
                  event.currentTarget instanceof HTMLInputElement &&
                  this.#review(id, event.currentTarget.checked)}
              />Looks right</label
            >
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
