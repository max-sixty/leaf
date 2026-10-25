/* This review packet owns its forge facts and composition. Leaf supplies typed
 * source delivery, safe Markdown, the shared clock and identity-aware comments. */
import {
  ago,
  highlightBlocks,
  html,
  keeps,
  keyed,
  LeafElement,
  loadMarkdown,
  markdownReady,
  noChange,
  renderMarkdown,
  repeat,
  unsafeHTML,
} from "/runtime/widget-api.js";

// A check's state is a status, drawn as the page's other statuses are (`.tag`), toned
// where the forge's word says how it went.
const TONES = { passed: "ok", success: "ok", failed: "danger", failure: "danger" };

const identityOf = (record) =>
  record ? `${record.repository}#${record.number}` : "unavailable";

customElements.define(
  "lf-pr-brief",
  class extends LeafElement {
    // The pull request, set by whoever hosts the widget: Leaf from the bound source
    // (the registry's `x-data.request.property`), or null while that source has none.
    static properties = { value: { attribute: false } };

    // The request whose Markdown load the brief last waited on, the request it drew,
    // and the drawing that follows the update under way, which its `updateComplete`
    // waits for.
    #loading = null;
    #drawn;
    #work;

    constructor() {
      super();
      this.value = null;
    }

    // Also waits for the drawing the latest update started: a newer update's drawing
    // replaces one still pending.
    async getUpdateComplete() {
      const result = await super.getUpdateComplete();
      await this.#work;
      return result;
    }

    render() {
      this.#work = undefined;
      const record = this.value;
      // The author's description is Markdown. The brief waits for its renderer once a
      // delivery, the delivery's draw with it; a load that fails draws the escaped
      // source, and the next delivery tries again.
      if (record && !markdownReady() && this.#loading !== record) {
        this.#loading = record;
        this.#work = loadMarkdown().then(() => this.requestUpdate());
        return noChange;
      }
      this.#drawn = record;
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
                              <td>
                                <small class=${`tag ${TONES[status] ?? ""}`}
                                  >${status}</small
                                >
                              </td>
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

    // The drawn brief's datum mark and code highlighting follow each draw; the draw's
    // `updateComplete` waits for the highlighting.
    updated(changed) {
      super.updated(changed);
      const record = this.#drawn;
      if (record === undefined) return;
      this.#drawn = undefined;
      const identity = identityOf(record);
      const node = this.firstElementChild;
      keeps(node, "data-lf-datum", identity);
      keeps(node, "data-lf-identity", record ? identity : null);
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value: record } }));
      if (record) this.#work = highlightBlocks(this);
    }
  },
);
