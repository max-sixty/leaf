(() => {
  // packages/diff/initial/lf-worktree.js
  document.documentElement.lfInitial.register("lf-worktree", (host, tools) => {
    const node = (tag, className, text) => {
      const result = document.createElement(tag);
      result.className = className;
      if (text !== void 0) result.textContent = text;
      return result;
    };
    const body = tools.authoredBody(node("div", "lf-worktree-body"));
    const details = node("details", "lf-worktree-disclosure");
    const key = `worktree:${host.id}`;
    const kept = tools.tabStore.get(key);
    details.open = kept === null ? host.hasAttribute("open") : kept === "open";
    details.addEventListener(
      "toggle",
      () => tools.tabStore.set(
        key,
        details.open === host.hasAttribute("open") ? null : details.open ? "open" : "closed"
      )
    );
    const summary = node("summary", "lf-worktree-summary lf-disclosure-marker");
    tools.generatedElement(summary, { says: true });
    const identity = node("span", "lf-worktree-identity");
    const label = node("strong", "lf-worktree-label", host.getAttribute("label"));
    const branch = host.getAttribute("branch");
    const head = host.getAttribute("head");
    const ref = node(
      "span",
      "lf-worktree-ref",
      [branch || (head ? "Detached HEAD" : null), head?.slice(0, 8)].filter(Boolean).join(" \xB7 ")
    );
    identity.append(label, ref);
    summary.append(identity);
    const status = host.getAttribute("status");
    const word = { clean: "Clean", unavailable: "Unavailable" }[status];
    if (word) summary.append(node("span", "lf-worktree-status", word));
    const stats = node("span", "lf-worktree-stats");
    if (status !== "unavailable") {
      const files = Number(host.getAttribute("files"));
      stats.append(node("span", "", `${files} ${files === 1 ? "file" : "files"}`));
      stats.append(
        node("span", "lf-worktree-additions", `+${host.getAttribute("additions")}`)
      );
      stats.append(
        node("span", "lf-worktree-deletions", `\u2212${host.getAttribute("deletions")}`)
      );
      const binary = Number(host.getAttribute("binary-files"));
      if (binary) stats.append(node("span", "lf-worktree-binary", `${binary} binary`));
    }
    summary.append(stats);
    const path = node("div", "lf-worktree-path");
    tools.generatedElement(path, { says: true });
    path.append(
      node("span", "", "Worktree"),
      node("code", "", host.getAttribute("path"))
    );
    details.append(summary, path, body);
    host.append(details);
    return { details };
  });
})();
