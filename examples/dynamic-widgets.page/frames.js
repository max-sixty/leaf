// The generated documents keep their own styles and temporary interaction state.
// Only their content height crosses the sandbox boundary; no application state does.
import { whileConnected } from "/runtime/widget-api.js";
const host = document.querySelector("main");
whileConnected(host, (signal) => {
  window.addEventListener(
    "message",
    (event) => {
      if (event.data?.type !== "dynamic-widget-height") return;
      const frame = [...host.querySelectorAll(".generated-frame")].find(
        (node) => node.contentWindow === event.source,
      );
      const height = event.data.height;
      if (frame && Number.isFinite(height) && height > 0)
        frame.style.height = `${Math.ceil(height)}px`;
    },
    { signal },
  );
});
