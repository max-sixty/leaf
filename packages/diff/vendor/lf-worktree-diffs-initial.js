(() => {
  // packages/diff/initial/lf-worktree-diffs.js
  document.documentElement.lfInitial.register("lf-worktree-diffs", (host, tools) => {
    const node = (tag, className) => {
      const result = document.createElement(tag);
      result.className = className;
      return result;
    };
    const header = node("div", "lf-worktree-overview");
    tools.generatedElement(header, { says: true });
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
    const update = (writeText = (node2, text) => {
      node2.textContent = text;
    }) => {
      const members = [...host.querySelectorAll(":scope > lf-worktree")];
      const known = members.filter(
        (member) => member.getAttribute("status") !== "unavailable"
      );
      const sum = (attribute) => known.reduce(
        (total, member) => total + Number(member.getAttribute(attribute)),
        0
      );
      writeText(
        label,
        members.length ? `${members.length} ${members.length === 1 ? "worktree" : "worktrees"}` : "No worktrees supplied"
      );
      writeText(files, `${sum("files")} ${sum("files") === 1 ? "file" : "files"}`);
      writeText(additions, `+${sum("additions")}`);
      writeText(deletions, `\u2212${sum("deletions")}`);
      writeText(binary, `${sum("binary-files")} binary`);
      tools.keeps(binary, "hidden", sum("binary-files") === 0 ? "" : null);
      tools.keeps(counts, "hidden", known.length === 0 ? "" : null);
      writeText(unavailable, `${members.length - known.length} unavailable`);
      tools.keeps(unavailable, "hidden", known.length === members.length ? "" : null);
    };
    update();
    return { update };
  });
})();
