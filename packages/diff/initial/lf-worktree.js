/* Decorate the authored native disclosure before first paint. Its evidence stays
 * where the author put it, so a revision can patch prose while retaining the
 * nested diff reader. Native disclosure and revision carry own the open state. */
document.documentElement.lfInitial.register("lf-worktree", (host) => {
  const node = (tag, className, text) => {
    const result = document.createElement(tag);
    result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  };
  const details = host.querySelector(":scope > details");
  details.classList.add("lf-worktree-disclosure");
  // Like lf-diff's file summary, this native disclosure names evidence. It is
  // content, not an apparatus-only offer: it must remain visible on paper.
  const summary = node("summary", "lf-worktree-summary lf-disclosure-marker");
  summary.dataset.lfGen = "1";
  summary.dataset.lfSaid = "";
  const identity = node("span", "lf-worktree-identity");
  const label = node("strong", "lf-worktree-label", host.getAttribute("label"));
  const branch = host.getAttribute("branch");
  const head = host.getAttribute("head");
  const ref = node(
    "span",
    "lf-worktree-ref",
    [branch || (head ? "Detached HEAD" : null), head?.slice(0, 8)]
      .filter(Boolean)
      .join(" · "),
  );
  identity.append(label, ref);
  const status = host.getAttribute("status");
  const state = node(
    "span",
    "lf-worktree-status",
    { changed: "Changed", clean: "Clean", unavailable: "Unavailable" }[status],
  );
  const stats = node("span", "lf-worktree-stats");
  if (status !== "unavailable") {
    const files = Number(host.getAttribute("files"));
    stats.append(node("span", "", `${files} ${files === 1 ? "file" : "files"}`));
    stats.append(
      node("span", "lf-worktree-additions", `+${host.getAttribute("additions")}`),
    );
    stats.append(
      node("span", "lf-worktree-deletions", `−${host.getAttribute("deletions")}`),
    );
    const binary = Number(host.getAttribute("binary-files"));
    if (binary) stats.append(node("span", "lf-worktree-binary", `${binary} binary`));
  }
  summary.append(identity, state, stats);
  const path = node("div", "lf-worktree-path");
  path.dataset.lfGen = "1";
  path.dataset.lfSaid = "";
  path.append(
    node("span", "", "Worktree"),
    node("code", "", host.getAttribute("path")),
  );
  details.prepend(summary, path);
  return { details };
});
