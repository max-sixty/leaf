/* This review packet owns its forge facts and composition. Leaf supplies typed
 * source delivery, safe Markdown, the shared clock and identity-aware comments. */
import {
  ago,
  highlightBlocks,
  html,
  keyed,
  LeafElement,
  loadMarkdown,
  markdownReady,
  noChange,
  projectData,
  renderMarkdown,
  repeat,
  unsafeHTML,
} from "/runtime/widget-api.js";

const identityOf = (record) =>
  record ? `${record.repository}#${record.number}` : "unavailable";

customElements.define(
  "lf-pr-brief",
  class extends LeafElement {
    // The revision whose Markdown load the brief last waited on, and the delivery it
    // drew.
    #loading = null;
    #drawn;

    render() {
      const snapshot = this.data("request");
      const record = snapshot?.value;
      // The author's description is Markdown. The brief waits for its renderer once a
      // delivery, holding the widget's presentation; a load that fails draws the
      // escaped source, and the next delivery tries again.
      const delivery = JSON.stringify([snapshot?.revision, snapshot?.run]);
      if (record && !markdownReady() && this.#loading !== delivery) {
        this.#loading = delivery;
        this.controller.present(
          loadMarkdown().then(() => {
            this.requestUpdate();
            return this.updateComplete;
          }),
        );
        return noChange;
      }
      this.#drawn = snapshot;
      this.classList.toggle("lf-rendered", Boolean(record));
      const identity = identityOf(record);
      return keyed(
        identity,
        record
          ? html` <article
              class="pr-brief"
              aria-label=${`${record.repository} pull request ${record.number}: ${record.title}`}
            >
              <header>
                <p>${record.repository} · PR #${record.number} · ${record.status}</p>
                <h3>${record.title}</h3>
                <p>Opened by ${record.author}</p>
                <p>${record.base} → ${record.head} · revision ${record.revision}</p>
              </header>
              <dl class="facts">
                <dt>Files</dt>
                <dd>${record.diff.files}</dd>
                <dt>Added</dt>
                <dd>+${record.diff.additions}</dd>
                <dt>Deleted</dt>
                <dd>−${record.diff.deletions}</dd>
                <dt>Commits</dt>
                <dd>${record.diff.commits}</dd>
              </dl>
              <section class="pr-description">
                <h4>Author's description</h4>
                <div>
                  ${unsafeHTML(renderMarkdown(record.description || "No description was provided by the author."))}
                </div>
              </section>
              <table class="pr-checks">
                <caption>
                  Observed checks
                </caption>
                <tbody>
                  ${
                    Object.keys(record.checks).length
                      ? repeat(
                          Object.entries(record.checks).sort(([a], [b]) =>
                            a.localeCompare(b),
                          ),
                          ([name]) => name,
                          ([name, status]) =>
                            html`<tr>
                              <th scope="row">${name}</th>
                              <td>${status}</td>
                            </tr>`,
                        )
                      : html`<tr>
                          <td>No checks reported</td>
                        </tr>`
                  }
                </tbody>
              </table>
              <p class="pr-observed" title=${record.observedAt}>
                Observed ${ago(record.observedAt)}
              </p>
            </article>`
          : html`<p>Waiting for pull request data.</p>`,
      );
    }

    // The drawn brief's datum and code highlighting follow each draw; the highlighting
    // holds the widget's presentation until it lands.
    updated(changed) {
      super.updated(changed);
      const snapshot = this.#drawn;
      if (snapshot === undefined) return;
      this.#drawn = undefined;
      const record = snapshot?.value;
      const identity = identityOf(record);
      projectData(
        this,
        [
          {
            node: this.firstElementChild,
            key: identity,
            ...(record ? { identity } : {}),
          },
        ],
        { snapshot },
      );
      if (record) this.controller.present(highlightBlocks(this));
    }
  },
);
