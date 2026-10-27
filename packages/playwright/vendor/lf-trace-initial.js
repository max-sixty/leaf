(() => {
  // packages/playwright/initial/lf-trace.js
  document.documentElement.lfInitial.register(
    "lf-trace",
    (host, { generatedElement }) => {
      const pending = host.ownerDocument.createElement("p");
      pending.className = "lf-trace-waiting";
      pending.textContent = "Waiting for a Playwright recording.";
      generatedElement(pending, { says: false });
      host.append(pending);
      return pending;
    }
  );
})();
