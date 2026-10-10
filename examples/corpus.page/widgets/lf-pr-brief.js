/* This review packet owns its forge facts and composition. Leaf supplies typed
 * source delivery, safe Markdown, the shared clock and identity-aware comments. */
import {
  ago,
  clocked,
  highlightBlocks,
  html,
  keyed,
  loadMarkdown,
  once,
  projectData,
  render,
  renderMarkdown,
  repeat,
  unsafeHTML,
  watchData,
  watchOwner,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-pr-brief",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      watchOwner(this, {
        connect: () => {
          this.paint = clocked(this, (snapshot) => this.show(snapshot));
        },
        disconnect: () => {
          this.paint.stop();
          this.paint = null;
        },
      });
      watchData(this, "request", async (snapshot) => {
        const paint = this.paint;
        if (snapshot?.value) await loadMarkdown();
        if (paint !== this.paint || !this.isConnected) return;
        paint(snapshot);
        if (snapshot?.value) await highlightBlocks(this);
      });
    }

    show(snapshot) {
      const record = snapshot?.value;
      this.classList.toggle("lf-rendered", Boolean(record));
      const identity = record ? `${record.repository}#${record.number}` : "unavailable";
      render(
        keyed(
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
        ),
        this,
      );
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
    }
  },
);
