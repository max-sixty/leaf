if (window.parent !== window) {
  const ready = () => {
    if (document.body?.dataset.lfPresented !== "1") return false;
    window.parent.postMessage({ type: "leaf:mcp-page-ready" }, "*");
    return true;
  };

  if (!ready()) {
    const observer = new MutationObserver(() => {
      if (ready()) observer.disconnect();
    });
    observer.observe(document.documentElement, {
      attributes: true,
      subtree: true,
      attributeFilter: ["data-lf-presented"],
    });
  }
}
