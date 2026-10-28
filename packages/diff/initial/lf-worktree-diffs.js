/* Collection totals read member scalars, never rendered labels or patch text.
 * Unavailable snapshots are excluded and counted explicitly, so zero cannot
 * silently mean missing evidence.
 * Members remain direct authored children; the header has its own Lit root. */
import { html } from "/vendor/lit.js";

document.documentElement.lfInitial.register("lf-worktree-diffs", (host, tools) => {
  const root = document.createElement("div");
  root.className = "lf-worktree-overview";
  tools.generatedElement(root, { says: true });
  host.prepend(root);
  return {
    root,
    render() {
      const members = [...host.querySelectorAll(":scope > lf-worktree")];
      const known = members.filter(
        (member) => member.getAttribute("status") !== "unavailable",
      );
      const sum = (attribute) =>
        known.reduce(
          (total, member) => total + Number(member.getAttribute(attribute)),
          0,
        );
      const binary = sum("binary-files");
      const files = sum("files");
      return html`<strong class="lf-worktree-total"
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
        >`;
    },
  };
});
