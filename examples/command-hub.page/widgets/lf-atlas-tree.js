/* A page-owned worktree adapter preserves the source record's stable identity
 * and provenance. Native details owns disclosure; Leaf owns datum comments. */
import {
  ago,
  HeldReading,
  html,
  LeafElement,
  projectData,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-atlas-tree",
  class extends LeafElement {
    pending = false;
    #view = null;
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
      const next = JSON.stringify(this.data("worktrees"));
      const shown = this.held.hold(next);
      const view = (this.#view = JSON.parse(shown));
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
      return Object.hasOwn(view?.value ?? {}, this.id);
    }
    #record(view) {
      return this.#holds(view) ? view.value[this.id] : null;
    }
    updated(changed) {
      super.updated(changed);
      const view = this.#view;
      const present = this.#holds(view);
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
