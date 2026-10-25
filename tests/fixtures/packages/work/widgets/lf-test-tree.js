/* A page-owned worktree adapter preserves the source record's stable identity
 * and provenance. Native details owns disclosure; Leaf owns datum comments. */
import { html, keeps, LeafElement } from "/runtime/widget-api.js";
customElements.define(
  "lf-test-tree",
  class extends LeafElement {
    static properties = { value: { attribute: false } };
    constructor() {
      super();
      this.value = null;
    }
    render() {
      const view = this.value;
      const present = Object.hasOwn(view ?? {}, this.id);
      const record = present ? view[this.id] : null;
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
                    <time datetime=${record.observedAt}>${record.observedAt}</time>
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
    updated(changed) {
      super.updated(changed);
      const view = this.value;
      const present = Object.hasOwn(view ?? {}, this.id);
      const node = this.firstElementChild;
      keeps(node, "data-lf-datum", this.id);
      keeps(node, "data-lf-identity", present ? this.id : null);
      keeps(node, "data-lf-origin-path", present ? JSON.stringify([this.id]) : null);
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value: view } }));
    }
  },
);
