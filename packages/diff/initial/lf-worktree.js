/* Build the worktree's native disclosure before first paint. The author writes the
 * evidence directly in the host; it moves whole into the disclosure's authored body,
 * where a revision patches prose while retaining the nested diff reader. The host's
 * `open` sets the first state, and a reader's toggle, kept by host id, outlasts a
 * revision that rebuilds the row.
 *
 * Leaf owns the disclosure rather than decorating one the author writes: a summary
 * written into the author's `details` stood among their elements, where the page's
 * rules read its structure. A shadow root holding the disclosure around a slot was
 * rejected because initial drawings get no shadow stage, so the summary would
 * appear only at upgrade. */
document.documentElement.lfInitial.register("lf-worktree", (host, tools) => {
  const node = (tag, className, text) => {
    const result = document.createElement(tag);
    result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  };
  const body = tools.authoredBody(node("div", "lf-worktree-body"));
  const details = node("details", "lf-worktree-disclosure");
  const key = `worktree:${host.id}`;
  const kept = tools.tabStore.get(key);
  details.open = kept === null ? host.hasAttribute("open") : kept === "open";
  details.addEventListener("toggle", () =>
    tools.tabStore.set(
      key,
      details.open === host.hasAttribute("open")
        ? null
        : details.open
          ? "open"
          : "closed",
    ),
  );
  // Like lf-diff's file summary, this native disclosure names evidence. It is
  // content, not an apparatus-only offer: it must remain visible on paper.
  const summary = node("summary", "lf-worktree-summary lf-disclosure-marker");
  tools.generatedElement(summary, { says: true });
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
  summary.append(identity);
  const status = host.getAttribute("status");
  // A changed row's counts already say it changed, so a word marks only Clean and
  // Unavailable, which counts can't say. The user chose this on 2026-10-26 over
  // "Changed" beside every changed row's counts.
  const word = { clean: "Clean", unavailable: "Unavailable" }[status];
  if (word) summary.append(node("span", "lf-worktree-status", word));
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
  summary.append(stats);
  const path = node("div", "lf-worktree-path");
  tools.generatedElement(path, { says: true });
  path.append(
    node("span", "", "Worktree"),
    node("code", "", host.getAttribute("path")),
  );
  details.append(summary, path, body);
  host.append(details);
  return { details };
});
