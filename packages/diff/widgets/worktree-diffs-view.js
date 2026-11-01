/* Collection totals read supplied member scalars, never rendered labels or patch
 * text. Unavailable snapshots remain separate from the known totals. */
import { html } from "/vendor/lit.js";

/** @param {HTMLElement} host */
export function render(host) {
  const members = [...host.querySelectorAll(":scope > lf-worktree")];
  const known = members.filter(
    (member) => member.getAttribute("status") !== "unavailable",
  );
  /** @param {string} attribute */
  const sum = (attribute) =>
    known.reduce(
      (total, member) => total + Number(member.getAttribute(attribute) ?? 0),
      0,
    );
  const files = sum("files");
  const binary = sum("binary-files");
  return html`<div class="lf-worktree-overview" data-lf-gen="1" data-lf-said>
      <strong class="lf-worktree-total"
        >${
          members.length
            ? `${members.length} ${members.length === 1 ? "worktree" : "worktrees"}`
            : "No worktrees supplied"
        }</strong
      >
      <span class="lf-worktree-stats" ?hidden=${!known.length}>
        <span>${files} ${files === 1 ? "file" : "files"}</span>
        <span class="lf-worktree-additions">+${sum("additions")}</span>
        <span class="lf-worktree-deletions">−${sum("deletions")}</span>
        <span class="lf-worktree-binary" ?hidden=${!binary}>${binary} binary</span>
      </span>
      <span class="lf-worktree-unavailable" ?hidden=${known.length === members.length}
        >${members.length - known.length} unavailable</span
      >
    </div>
    <slot></slot>`;
}
