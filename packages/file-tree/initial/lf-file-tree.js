/* The pending face is a native paragraph, retained by the live module. */
document.documentElement.lfInitial.register("lf-file-tree", (host, { offer }) => {
  const pending = offer("p", "lf-file-tree-empty", "No files available.");
  host.append(pending);
  return pending;
});
