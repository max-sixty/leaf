(() => {
  // packages/file-editor/initial/lf-file-editor.js
  document.documentElement.lfInitial.register(
    "lf-file-editor",
    (host, { generatedElement }) => {
      const pending = host.ownerDocument.createElement("p");
      pending.className = "lf-file-editor-opening";
      pending.textContent = "Opening file\u2026";
      generatedElement(pending, { says: false });
      host.append(pending);
      return pending;
    }
  );
})();
