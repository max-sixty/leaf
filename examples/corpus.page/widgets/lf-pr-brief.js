/* This review packet owns its forge facts and composition. Leaf supplies typed
 * source delivery, safe Markdown, the shared clock and identity-aware comments. */
import {
  ago,
  highlightBlocks,
  html,
  createView,
  Show,
  For,
  LeafElement,
  loadMarkdown,
  markdownReady,
  projectData,
  renderMarkdown,
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
    #drawing = null;

    render() {
      const snapshot = this.data("request");
      const record = snapshot?.value;
      // The author's description is Markdown. The brief waits for its renderer once a
      // delivery, the delivery's claim with it; a load that fails draws the escaped
      // source, and the next delivery tries again.
      const delivery = JSON.stringify([snapshot?.revision, snapshot?.run]);
      if (record && !markdownReady() && this.#loading !== delivery) {
        this.#loading = delivery;
        this.drawing(
          loadMarkdown().then(() => {
            this.requestUpdate();
            return this.updateComplete;
          }),
        );
        return;
      }
      this.#drawn = snapshot;
      this.classList.toggle("lf-rendered", Boolean(record));
      const identity = identityOf(record);
      const props = {
        identity,
        record,
        observed: record ? ago(record.observedAt) : "",
        description: record
          ? renderMarkdown(
              record.description || "No description was provided by the author.",
            )
          : "",
        checks: Object.entries(record?.checks ?? {}).sort(([a], [b]) =>
          a.localeCompare(b),
        ),
      };
      if (this.#drawing) this.#drawing.update(props);
      else
        this.#drawing = createView(
          this.renderRoot,
          (read) =>
            html`${Show({
              get when() {
                return read().identity;
              },
              keyed: true,
              children: (identity) =>
                identity === "unavailable"
                  ? html`<p>Waiting for pull request data.</p>`
                  : html` <article
                      class="pr-brief"
                      aria-label=${() => `${read().record.repository} pull request ${read().record.number}: ${read().record.title}`}
                    >
                      <header>
                        <p>
                          ${() => read().record.repository} · PR
                          #${() => read().record.number} · ${() => read().record.status}
                        </p>
                        <h3>${() => read().record.title}</h3>
                        <p>Opened by ${() => read().record.author}</p>
                        <p>
                          ${() => read().record.base} → ${() => read().record.head} ·
                          revision ${() => read().record.revision}
                        </p>
                      </header>
                      <dl class="facts">
                        <dt>Files</dt>
                        <dd>${() => read().record.diff.files}</dd>
                        <dt>Added</dt>
                        <dd>+${() => read().record.diff.additions}</dd>
                        <dt>Deleted</dt>
                        <dd>−${() => read().record.diff.deletions}</dd>
                        <dt>Commits</dt>
                        <dd>${() => read().record.diff.commits}</dd>
                      </dl>
                      <section class="pr-description">
                        <h4>Author's description</h4>
                        <div prop:innerHTML=${() => read().description}></div>
                      </section>
                      <table class="pr-checks">
                        <caption>
                          Observed checks
                        </caption>
                        <tbody>
                          ${For({
                get each() {
                  return read().checks;
                },
                keyed: (check) => check[0],
                children: (check) =>
                  html` <tr>
                    <th scope="row">${() => check()[0]}</th>
                    <td>${() => check()[1]}</td>
                  </tr>`,
              })}
                          ${Show({
                get when() {
                  return !read().checks.length;
                },
                children: (_visible) =>
                  html`<tr>
                    <td>No checks reported</td>
                  </tr>`,
              })}
                        </tbody>
                      </table>
                      <p class="pr-observed" title=${() => read().record.observedAt}>
                        Observed ${() => read().observed}
                      </p>
                    </article>`,
            })}`,
          props,
        );
    }

    // The drawn brief's datum and code highlighting follow each draw; the draw's claim
    // waits for the highlighting.
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
      if (record) this.drawing(highlightBlocks(this));
    }
  },
);
