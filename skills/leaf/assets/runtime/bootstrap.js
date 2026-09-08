// The server places this exact hashed script before any loadable page resource.
// It must run even when the entry module or one of its dependencies cannot load.
(() => {
  const script = document.currentScript;
  const incarnation = script.dataset.lfServer;
  const layer = script.dataset.lfLayer;
  const release = script.dataset.lfRelease;
  const entry = new URL(script.dataset.lfEntry, location.href).href;
  const theme = new URL(script.dataset.lfTheme, location.href).href;
  let recovering = false;

  // Reader-arranged workspaces are page geometry, so their saved shape must reach the
  // document before the module graph that builds their contents. The theme consumes
  // these provisional root facts; restoreArrangements replaces them with live state.
  try {
    const root = document.documentElement;
    const tray = localStorage.getItem("lf-tray-up");
    if (tray) root.dataset.lfRestoreTray = tray;
    else if (localStorage.getItem("lf-panel-open") === "1")
      root.toggleAttribute("data-lf-restore-panel", true);

    const panelWidth = parseFloat(localStorage.getItem("lf-panel-width"));
    const trayWidth = parseFloat(localStorage.getItem("lf-tray-width"));
    if (panelWidth) root.style.setProperty("--lf-panel-choice", `${panelWidth}px`);
    if (trayWidth) root.style.setProperty("--lf-tray-choice", `${trayWidth}px`);
  } catch {
    // A page that cannot remember still starts in the default arrangement.
  }

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
        if (response.status === 404) {
          if (release) location.reload();
          return;
        }
        const current = response.headers.get("Leaf-Server");
        let generation = response.headers.get("Leaf-Layer");
        const currentRelease = response.headers.get("Leaf-Release");
        if (!generation && response.ok) {
          try {
            generation = (await response.json())?.["$layer"]?.generation;
          } catch {
            // A non-registry probe can still identify itself through headers.
          }
        }
        if (
          (current && current !== incarnation) ||
          (generation && generation !== layer) ||
          (release && currentRelease && currentRelease !== release)
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
