/* One native disclosure from delivery through live updates. Authored evidence stays
 * in the host's light DOM and the browser distributes it through the slots: the
 * <strong> the host opens with, which names the worktree, into the row's name, and the
 * rest into the body. So the name the row shows is the one the page wrote, which page
 * search finds and a comment anchors on.
 *
 * Rejected: drawing a copy of the name in the row and hiding the authored one, as a
 * tab strip copies its panels' names. A tab's name still stands in its panel; hidden
 * here, the name stood nowhere search or a comment could reach. */
import { html, nothing } from "/vendor/lit.js";
import { keeps, openingTitle } from "/runtime/widget-api.js";

/** @param {HTMLElement} host */
export function render(host) {
  const name = openingTitle(host)?.holder;
  if (name) keeps(name, "slot", "lf-worktree-name");
  const branch = host.getAttribute("branch");
  const head = host.getAttribute("head");
  const identity = [branch || (head ? "Detached HEAD" : null), head?.slice(0, 8)]
    .filter(Boolean)
    .join(" · ");
  const status = host.getAttribute("status");
  // Counts already say a row changed; only Clean/Unavailable need another word.
  const word =
    status === "clean" ? "Clean" : status === "unavailable" ? "Unavailable" : undefined;
  const files = Number(host.getAttribute("files"));
  const binary = Number(host.getAttribute("binary-files"));
  return html`<details
    class="lf-worktree-disclosure"
    ?open=${host.hasAttribute("open")}
    data-lf-open-key=${`worktree:${host.getAttribute("id")}`}
  >
    <summary
      class="lf-worktree-summary lf-disclosure-marker"
      data-lf-gen="1"
      data-lf-said
    >
      <span class="lf-worktree-identity"
        ><strong class="lf-worktree-label"
          ><slot name="lf-worktree-name"></slot
        ></strong>
        <span class="lf-worktree-ref">${identity}</span></span
      >
      ${word ? html`<span class="lf-worktree-status">${word}</span>` : nothing}
      <span class="lf-worktree-stats"
        >${
          status === "unavailable"
            ? nothing
            : html`
                <span>${files} ${files === 1 ? "file" : "files"}</span>
                <span class="lf-worktree-additions"
                  >+${host.getAttribute("additions")}</span
                >
                <span class="lf-worktree-deletions"
                  >−${host.getAttribute("deletions")}</span
                >
                ${
                  binary
                    ? html`<span class="lf-worktree-binary">${binary} binary</span>`
                    : nothing
                }
              `
        }</span
      >
    </summary>
    <div class="lf-worktree-path" data-lf-gen="1" data-lf-said>
      <span>Worktree</span> <code>${host.getAttribute("path")}</code>
    </div>
    <div class="lf-worktree-body"><slot></slot></div>
  </details>`;
}
