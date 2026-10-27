/* The pending face is a native paragraph, retained by the live module. */
document.documentElement.lfInitial.register(
  "lf-trace",
  (host, { generatedElement }) => {
    const pending = host.ownerDocument.createElement("p");
    pending.className = "lf-trace-waiting";
    pending.textContent = "Waiting for a Playwright recording.";
    generatedElement(pending, { says: false });
    host.append(pending);
    return pending;
  },
);
