/* The pending paragraph stays until the editor creates its stage. */
document.documentElement.lfInitial.register(
  "lf-file-editor",
  (host, { generatedElement }) => {
    const pending = host.ownerDocument.createElement("p");
    pending.className = "lf-file-editor-opening";
    pending.textContent = "Opening file…";
    generatedElement(pending, { says: false });
    host.append(pending);
    return pending;
  },
);
