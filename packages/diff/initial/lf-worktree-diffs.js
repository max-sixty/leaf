/* Collection totals read member scalars, never rendered labels or patch text.
 * Unavailable snapshots are excluded and counted explicitly, so zero cannot
 * silently mean missing evidence. Members remain direct authored children. */
document.documentElement.lfInitial.register("lf-worktree-diffs", (host, { keeps }) => {
  const node = (tag, className) => {
    const result = document.createElement(tag);
    result.className = className;
    return result;
  };
  const header = node("div", "lf-worktree-overview");
  header.dataset.lfGen = "1";
  header.dataset.lfSaid = "";
  const label = node("strong", "lf-worktree-total");
  const counts = node("span", "lf-worktree-stats");
  const files = node("span", "");
  const additions = node("span", "lf-worktree-additions");
  const deletions = node("span", "lf-worktree-deletions");
  const binary = node("span", "lf-worktree-binary");
  const unavailable = node("span", "lf-worktree-unavailable");
  counts.append(files, additions, deletions, binary);
  header.append(label, counts, unavailable);
  host.prepend(header);
  // Initial drawing writes each label once; the live module lends keepsText
  // for subsequent readings, sharing the runtime's no-restatement contract.
  const update = (
    writeText = (node, text) => {
      node.textContent = text;
    },
  ) => {
    const members = [...host.querySelectorAll(":scope > lf-worktree")];
    const known = members.filter(
      (member) => member.getAttribute("status") !== "unavailable",
    );
    const sum = (attribute) =>
      known.reduce(
        (total, member) => total + Number(member.getAttribute(attribute)),
        0,
      );
    writeText(
      label,
      members.length
        ? `${members.length} ${members.length === 1 ? "worktree" : "worktrees"}`
        : "No worktrees supplied",
    );
    writeText(files, `${sum("files")} ${sum("files") === 1 ? "file" : "files"}`);
    writeText(additions, `+${sum("additions")}`);
    writeText(deletions, `−${sum("deletions")}`);
    writeText(binary, `${sum("binary-files")} binary`);
    keeps(binary, "hidden", sum("binary-files") === 0 ? "" : null);
    keeps(counts, "hidden", known.length === 0 ? "" : null);
    writeText(unavailable, `${members.length - known.length} unavailable`);
    keeps(unavailable, "hidden", known.length === members.length ? "" : null);
  };
  update();
  return { update };
});
