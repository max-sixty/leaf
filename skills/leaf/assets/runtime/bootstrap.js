// The server places this exact hashed script before any loadable page resource.
// It must run even when the entry module or one of its dependencies cannot load.
(() => {
  const script = document.currentScript;
  const incarnation = script.dataset.lfServer;
  const layer = script.dataset.lfLayer;
  const entry = new URL(script.dataset.lfEntry, location.href).href;
  const theme = new URL(script.dataset.lfTheme, location.href).href;
  let recovering = false;

  function recover() {
    if (recovering) return;
    recovering = true;
    const show = () => {
      const status = document.createElement("p");
      status.className = "lf-chrome";
      status.setAttribute("data-lf-runtime", "");
      status.setAttribute("role", "status");
      status.textContent = "Leaf couldn't start. Waiting for the server to update.";
      document.body.prepend(status);
    };
    if (document.body) show();
    else document.addEventListener("DOMContentLoaded", show, { once: true });

    const check = async () => {
      try {
        const response = await fetch(script.dataset.lfProbe, { cache: "no-store" });
        if (response.status === 404) return;
        const current = response.headers.get("Leaf-Server");
        const generation = response.headers.get("Leaf-Layer");
        if (
          (current && current !== incarnation) ||
          (generation && generation !== layer)
        ) {
          location.reload();
          return;
        }
      } catch {
        // The stopped server has not been replaced yet.
      }
      setTimeout(check, 1000);
    };
    void check();
  }

  window.addEventListener(
    "error",
    (event) => {
      const target = event.target;
      if (
        (target instanceof HTMLScriptElement && target.src === entry) ||
        (target instanceof HTMLLinkElement && target.href === theme) ||
        (target === window && !document.body?.hasAttribute("data-lf-presented"))
      )
        recover();
    },
    true,
  );
  window.addEventListener("lf-startup-failed", recover);
})();
