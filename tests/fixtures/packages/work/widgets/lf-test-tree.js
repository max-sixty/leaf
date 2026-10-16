/* A page-owned worktree adapter preserves the source record's stable identity
 * and provenance. Native details owns disclosure; Leaf owns datum comments. */
import { html, LeafElement, projectData } from "/runtime/widget-api.js";
customElements.define(
  "lf-test-tree",
  class extends LeafElement {
    render() {
      const view = (this.snapshot = this.data("worktrees"));
      const present = Object.hasOwn(view?.value ?? {}, this.id);
      const record = present ? view.value[this.id] : null;
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
      const view = this.snapshot;
      const present = Object.hasOwn(view?.value ?? {}, this.id);
      projectData(
        this,
        [
          {
            node: this.firstElementChild,
            key: this.id,
            ...(present ? { identity: this.id } : {}),
            origin: view
              ? { ...view.origin, ...(present ? { path: [this.id] } : {}) }
              : null,
          },
        ],
        { snapshot: view },
      );
    }
  },
);
