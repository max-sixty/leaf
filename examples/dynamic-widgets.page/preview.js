// Reveal each preview once it starts. This checks startup, not whether its
// behavior meets the request. Generated HTML runs in an opaque sandbox.
import { mountSample } from "/runtime/widget-api.js";

export function stageLeafPreview(container, source, onFailure) {
  const frame = document.createElement("iframe");
  frame.className = "native-frame";
  frame.title = "Generated Leaf components";
  frame.setAttribute("data-staging", "");
  frame.inert = true;
  frame.setAttribute("aria-hidden", "true");
  container.append(frame);
  let sample;
  let disposed = false;
  const fit = ({ height }) => {
    frame.style.height = `${Math.ceil(height)}px`;
  };
  const ready = (async () => {
    sample = await mountSample(frame, { source });
    if (disposed) {
      await sample.destroy();
      return;
    }
    sample.on("height", fit);
    sample.on("loading", () => {
      sample.ready.catch((error) => {
        if (!disposed) onFailure(error);
      });
    });
    fit(await sample.ready);
  })();
  return {
    frame,
    ready,
    dispose() {
      disposed = true;
      if (sample) void sample.destroy().catch(onFailure);
      frame.remove();
    },
  };
}

export function stagePreview(container, value, onFailure) {
  const frame = document.createElement("iframe");
  frame.className = "generated-frame";
  frame.title = "Generated widget";
  frame.setAttribute("sandbox", "allow-scripts allow-forms");
  frame.setAttribute("data-staging", "");
  frame.inert = true;
  frame.setAttribute("aria-hidden", "true");
  const payload = JSON.stringify(value).replaceAll("<", "\\u003c");
  frame.srcdoc = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; form-action 'none';">
<style>body{margin:0;padding:16px;box-sizing:border-box;font:16px/1.5 system-ui;color:#242424;background:#fff}*{box-sizing:border-box}button,input,select,textarea{font:inherit}</style>
<script>
const send = (type, detail = {}) => parent.postMessage({type, ...detail}, '*');
let failed = false;
function fail(message) { failed = true; send('widget-error', {message}); }
addEventListener('error', event => fail(event.message));
addEventListener('unhandledrejection', event => fail(String(event.reason)));
addEventListener('DOMContentLoaded', () => {
  const value = ${payload};
  const style = document.createElement('style'); style.textContent = value.css; document.head.append(style);
  document.body.innerHTML = value.html;
  const script = document.createElement('script'); script.textContent = value.js; document.body.append(script);
  const reportSize = () => send('dynamic-widget-height', {height: document.body.getBoundingClientRect().height});
  new ResizeObserver(reportSize).observe(document.body);
  // Offscreen frames may never receive animation frames. Startup is complete
  // after the script task and its promise errors, even before scrolling here.
  setTimeout(() => {
    reportSize();
    if (!failed && value.html.trim()) send('widget-ready');
    else if (!failed) fail('The model returned an empty preview.');
  }, 0);
});
</script></head><body></body></html>`;
  let timeout;
  let rejectReady;
  let resolveReady;
  let settled = false;
  const ready = new Promise((resolve, reject) => {
    rejectReady = reject;
    resolveReady = resolve;
    timeout = setTimeout(
      () => reject(new Error("The widget did not finish starting.")),
      10000,
    );
  });
  const receive = (event) => {
    if (event.source !== frame.contentWindow) return;
    if (event.data?.type === "dynamic-widget-height") {
      const height = event.data.height;
      if (Number.isFinite(height) && height > 0)
        frame.style.height = `${Math.ceil(height)}px`;
    }
    if (event.data?.type === "widget-ready") {
      settled = true;
      clearTimeout(timeout);
      resolveReady();
    }
    if (event.data?.type === "widget-error") {
      const error = new Error(String(event.data.message));
      clearTimeout(timeout);
      if (settled) onFailure(error);
      else rejectReady(error);
    }
  };
  window.addEventListener("message", receive);
  container.append(frame);
  return {
    frame,
    ready,
    dispose() {
      clearTimeout(timeout);
      window.removeEventListener("message", receive);
      frame.remove();
    },
  };
}
