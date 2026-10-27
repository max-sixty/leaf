(() => {
  // packages/file-tree/initial/lf-file-tree.js
  document.documentElement.lfInitial.register("lf-file-tree", (host, { offer }) => {
    const pending = offer("p", "lf-file-tree-empty", "No files available.");
    host.append(pending);
    return pending;
  });
})();
