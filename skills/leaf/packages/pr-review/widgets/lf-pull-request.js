/* A pull request is observed review evidence. The page binds one typed source; this
 * widget projects it without querying a forge or turning review state into a second
 * authority. */
import {
  ago,
  html,
  render,
  repeat,
  keyed,
  unsafeHTML,
  clocked,
  highlightBlocks,
  loadMarkdown,
  projectData,
  renderMarkdown,
  watchData,
  once,
  watchOwner,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-pull-request",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      watchOwner(this, {
        connect: () => this.connectPaint(),
        disconnect: () => {
          this.paintSnapshot?.stop();
          this.paintSnapshot = null;
        },
      });
      watchData(this, "request", (snapshot) => this.show(snapshot));
    }

    connectPaint() {
      // Markdown loading is asynchronous, but the card paint itself is synchronous. Keep
      // the clock dependency on that second half so an unchanged source still refreshes
      // the observed age when the shared clock crosses a display boundary.
      this.paintSnapshot = clocked(this, (snapshot) => {
        const record = snapshot?.value ?? null;
        // Drawn from its data, which lifts the height the page reserved (x-height),
        // and held at that height again while the data is absent.
        this.classList.toggle("lf-rendered", record !== null);
        const key = record ? `${record.repository}#${record.number}` : "unavailable";
        const description = record
          ? renderMarkdown(
              record.description || "No description was provided by the author.",
            )
          : null;
        render(
          keyed(
            key,
            record
              ? html` <article
                  class="lf-pr-card"
                  aria-label=${`${record.repository} pull request ${record.number}: ${record.title}`}
                >
                  <header class="lf-pr-head">
                    <p class="lf-pr-identity">
                      <span class="lf-pr-identity-label"
                        >${record.repository} · PR #${record.number}</span
                      ><span class="lf-pr-status" data-status=${record.status}
                        >${record.status}</span
                      >
                    </p>
                    <strong class="lf-pr-title">${record.title}</strong>
                    <p class="lf-pr-byline">Opened by ${record.author}</p>
                    <p class="lf-pr-route">
                      ${record.base} → ${record.head} · revision ${record.revision}
                    </p>
                  </header>
                  <ul class="lf-pr-facts">
                    ${[
                      ["Files", record.diff.files],
                      ["Added", `+${record.diff.additions}`],
                      ["Deleted", `−${record.diff.deletions}`],
                      ["Commits", record.diff.commits],
                    ].map(
                      ([label, value]) =>
                        html`<li class="lf-pr-fact">
                          <span class="lf-pr-fact-name">${label}</span
                          ><strong class="lf-pr-fact-value">${value}</strong>
                        </li>`,
                    )}
                  </ul>
                  <section class="lf-pr-description">
                    <h3 class="lf-pr-description-label">Author's description</h3>
                    <div class="lf-pr-description-body">${unsafeHTML(description)}</div>
                  </section>
                  <section class="lf-pr-checks">
                    <table class="lf-pr-check-table">
                      <caption class="lf-pr-checks-label">
                        Checks
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
                                  html`<tr
                                    class="lf-pr-check"
                                    data-check=${name}
                                    data-status=${status}
                                  >
                                    <th class="lf-pr-check-name" scope="row">
                                      ${name}
                                    </th>
                                    <td class="lf-pr-check-status">${status}</td>
                                  </tr>`,
                              )
                            : html`<tr class="lf-pr-check lf-pr-check-empty">
                                <td colspan="2">No checks reported</td>
                              </tr>`
                        }
                      </tbody>
                    </table>
                  </section>
                  <p
                    class="lf-pr-observed"
                    title=${record.observedAt}
                    .textContent=${`Observed ${ago(record.observedAt)}`}
                  ></p>
                </article>`
              : html`<article
                  class="lf-pr-card lf-pr-missing"
                  aria-label="Pull request data unavailable"
                >
                  Waiting for pull request data.
                </article>`,
          ),
          this,
        );
        projectData(
          this,
          [
            {
              node: this.querySelector("article"),
              key,
              ...(record ? { identity: key } : {}),
            },
          ],
          { snapshot },
        );
      });
    }

    async show(snapshot) {
      const painter = this.paintSnapshot;
      const record = snapshot?.value ?? null;
      if (record)
        await loadMarkdown((error) =>
          console.error(
            `leaf: pull request Markdown failed to load: ${error?.message ?? error}`,
          ),
        );
      // The widget may leave the document while the lazy Markdown module is loading.
      // Keep the painter belonging to this mount and let a later mount own its snapshot.
      if (this.paintSnapshot !== painter || !this.isConnected) return;
      painter(snapshot);
      if (record) await highlightBlocks(this);
    }
  },
);
