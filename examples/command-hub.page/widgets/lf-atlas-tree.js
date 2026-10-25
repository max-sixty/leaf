/* A page-owned worktree adapter preserves the source record's stable identity
 * and provenance. Native details owns disclosure; Leaf owns datum comments. */
import { ago, HeldReading, html, keeps, LeafElement } from "/runtime/widget-api.js";
customElements.define(
  "lf-atlas-tree",
  class extends LeafElement {
    static properties = { value: { attribute: false } };
    pending = false;
    // The worktrees value drawn, which a held reading keeps while newer ones arrive.
    #view = null;
    constructor() {
      super();
      this.value = null;
    }
    setup() {
      this.held = new HeldReading(
        this,
        () => [...this.children],
        () => this.requestUpdate(),
      );
    }
    showLatest() {
      this.held.show();
    }
    render() {
      const next = JSON.stringify(this.value);
      const shown = this.held.hold(next);
      if (shown === next) this.#view = this.value;
      const view = this.#view;
      if (this.pending !== (next !== shown)) {
        this.pending = next !== shown;
        this.dispatchEvent(new CustomEvent("atlas-reading", { bubbles: true }));
      }
      const record = this.#record(view);
      return html`<details class="atlas-tree">
        <summary>Worktree evidence</summary>
        ${
          record
            ? html`<dl class="facts">
                  <dt>Branch</dt>
                  <dd>${record.branch}</dd>
                  <dt>Revision</dt>
                  <dd>${record.base}…${record.head}</dd>
                  <dt>Against base</dt>
                  <dd>
                    ↑${record.ahead} ↓${record.behind} · +${record.additions}
                    −${record.deletions} · ${record.commits} commits
                  </dd>
                  <dt>Tests</dt>
                  <dd>${record.tests}</dd>
                  <dt>Observed</dt>
                  <dd>
                    <time datetime=${record.observedAt} title=${record.observedAt}
                      >${ago(record.observedAt)}</time
                    >
                  </dd>
                </dl>
                <h4>Files</h4>
                <pre>${record.files ?? "No files recorded."}</pre>
                <h4>Diff</h4>
                <pre>${record.diff ?? "No diff recorded."}</pre>`
            : html`<p>No worktree snapshot.</p>`
        }
      </details>`;
    }
    #holds(view) {
      return Object.hasOwn(view ?? {}, this.id);
    }
    #record(view) {
      return this.#holds(view) ? view[this.id] : null;
    }
    updated(changed) {
      super.updated(changed);
      const view = this.#view;
      const present = this.#holds(view);
      const node = this.firstElementChild;
      keeps(node, "data-lf-datum", this.id);
      keeps(node, "data-lf-identity", present ? this.id : null);
      keeps(node, "data-lf-origin-path", present ? JSON.stringify([this.id]) : null);
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value: view } }));
    }
  },
);
