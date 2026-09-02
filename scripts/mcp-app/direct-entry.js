import { App } from "@modelcontextprotocol/ext-apps";

async function boot() {
  const app = new App({ name: "Leaf direct transport probe", version: "36" });
  const report = (detail) =>
    app.callServerTool({ name: "leaf_probe_report", arguments: { detail } });
  const call = async (name, args = {}) => {
    const result = await app.callServerTool({ name, arguments: args });
    if (result.isError) throw new Error(result.content?.[0]?.text || `${name} failed`);
    return result.structuredContent;
  };

  // This experiment adapts transport at the browser boundary. The shipped runtime
  // still owns upgrades, projection, anchors, the outbox, and all widget gestures.
  globalThis.leafProbeImport = (url) => widgetModules[url]();
  globalThis.fetch = async (input, options = {}) => {
    const url = new URL(
      typeof input === "string" ? input : input.url,
      "https://leaf-probe.invalid/",
    );
    const headers = new Headers(options.headers);
    const view_revision = Number(headers.get("Leaf-View-Revision")) || null;
    const asset = assetFiles[url.pathname];
    if (asset)
      return new Response(asset.body, { headers: { "Content-Type": asset.type } });
    if (url.pathname === "/api/state") {
      const state = await call("leaf_probe_state", { view_revision });
      return Response.json(state);
    }
    if (url.pathname === "/api/event" && options.method === "POST") {
      const result = await call("leaf_probe_event", {
        event: JSON.parse(options.body),
        generation: headers.get("Leaf-Layer"),
        view_revision,
      });
      return Response.json(result.body, { status: result.status });
    }
    throw new Error(`Unimplemented direct-probe route: ${url.pathname}`);
  };

  // The real state-feed still compares the server reading and decides when to GET.
  // Polling this token substitutes only for HTTP's long-lived EventSource channel.
  globalThis.EventSource = class extends EventTarget {
    static CLOSED = 2;
    readyState = 0;
    constructor(url) {
      super();
      if (url !== "/api/news") throw new Error(`Unexpected stream: ${url}`);
      this.poll();
    }
    async poll() {
      try {
        const { reading } = await call("leaf_probe_reading");
        if (this.readyState === 2) return;
        if (!this.readyState) {
          this.readyState = 1;
          this.dispatchEvent(new Event("open"));
        }
        this.dispatchEvent(new MessageEvent("message", { data: reading }));
        this.timer = setTimeout(() => this.poll(), 2000);
      } catch {
        this.close();
        this.dispatchEvent(new Event("error"));
      }
    }
    close() {
      this.readyState = 2;
      clearTimeout(this.timer);
    }
  };

  app.ontoolresult = () => {};
  app.onhostcontextchanged = () => {};
  app.onteardown = async () => ({});
  await app.connect();

  const controls = document.createElement("aside");
  controls.setAttribute("aria-label", "MCP experiment controls");
  controls.style.cssText =
    "position:fixed;bottom:42px;right:12px;z-index:99999;background:Canvas;color:CanvasText;padding:8px;border:1px solid GrayText;font:13px system-ui;max-width:260px";
  const button = document.createElement("button");
  button.textContent = "Test Codex follow-up";
  button.type = "button";
  const messageStatus = document.createElement("div");
  messageStatus.setAttribute("role", "status");
  messageStatus.textContent = "Only this button tests waking the agent.";
  button.addEventListener("click", async () => {
    const marker = `leaf-direct-message-${crypto.randomUUID()}`;
    button.disabled = true;
    messageStatus.textContent = "Sending ui/message…";
    const sentAt = new Date().toISOString();
    try {
      const result = await app.sendMessage({
        role: "user",
        content: [
          {
            type: "text",
            text: `Leaf direct MCP probe: ${marker}. This message came from the ui:// app's Test Codex follow-up button, without the detached Leaf adapter. Confirm receipt; do not infer whether you were idle before it arrived.`,
          },
        ],
      });
      messageStatus.textContent = "ui/message accepted; check whether a turn starts.";
      await report({
        kind: "message-result",
        marker,
        result,
        sentAt,
        at: new Date().toISOString(),
      });
    } catch (error) {
      messageStatus.textContent = `ui/message failed: ${error.message}`;
      await report({ kind: "message-error", marker, error: error.message });
    } finally {
      button.disabled = false;
    }
  });
  controls.append(button, messageStatus);
  document.body.append(controls);
  await import("/leaf.js");
  const reportPresented = () => {
    if (document.body.dataset.lfPresented !== "1") return;
    ready.disconnect();
    void report({
      kind: "presented",
      title: document.title,
      frames: document.querySelectorAll("iframe").length,
      upgraded: document.body.dataset.lfUpgraded,
      presented: document.body.dataset.lfPresented,
      heading: document.querySelector("h1")?.textContent,
    });
  };
  const ready = new MutationObserver(reportPresented);
  ready.observe(document.body, {
    attributes: true,
    attributeFilter: ["data-lf-presented"],
  });
  reportPresented();
}

void boot().catch((error) => {
  console.error(error);
  document.body.append(`Direct Leaf failed: ${error.message}`);
});
