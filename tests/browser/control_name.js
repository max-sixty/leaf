// Diagnostic names shared by layout and focus readings.
(() => {
  // What to call a control in a failure message. Its words are in it because they are
  // usually the whole of what distinguishes one button in a row from the next — and out of
  // the key it is looked up by, since a control that rewrites them (a count gaining a
  // digit) is the same control saying something new.
  function named(n) {
    return (
      n.tagName.toLowerCase() +
      (typeof n.className === "string" && n.className.trim()
        ? "." + n.className.trim().split(/\s+/).join(".")
        : "") +
      " " +
      JSON.stringify((n.textContent || "").trim().slice(0, 24))
    );
  }

  return { named };
})();
