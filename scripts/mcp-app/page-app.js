import {
  App,
  applyDocumentTheme,
  applyHostFonts,
  applyHostStyleVariables,
} from "@modelcontextprotocol/ext-apps/app-with-deps";

const app = new App(
  { name: "Leaf page", version: "0.1.0" },
  { availableDisplayModes: ["inline", "fullscreen"] },
);
const shell = document.querySelector("#app");
const frame = document.querySelector("#leaf-page");
const loading = document.querySelector("#loading");
const pageTitle = document.querySelector("#page-title");
const sequence = document.querySelector("#sequence");
const sourceWarning = document.querySelector("#source-warning");
const status = document.querySelector("#status");
const refresh = document.querySelector("#refresh");
const openPage = document.querySelector("#open-page");
const displayMode = document.querySelector("#display-mode");
let current = null;
let pagePath = null;
let mode = "inline";
let busy = false;

function payload(result) {
  return result?.structuredContent ?? result?.structured_content ?? null;
}

function announce(message) {
  status.textContent = "";
  requestAnimationFrame(() => {
    status.textContent = message;
  });
}

function setBusy(value) {
  busy = value;
  refresh.disabled = value;
  displayMode.disabled = value;
}

function safePageUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "http:" || url.hostname !== "localhost")
    throw new Error("Leaf returned an unexpected page address");
  return url.href;
}

function render(state, announcement) {
  current = state;
  pagePath = state.page ?? pagePath;
  pageTitle.textContent = state.title || "Untitled page";
  sequence.textContent = `event ${state.event_seq} · ${state.active?.label ?? "no revision"}`;
  sourceWarning.hidden = !state.source_error;
  openPage.disabled = !state.url;
  if (state.mode !== "page" || !state.url) {
    frame.hidden = true;
    frame.removeAttribute("src");
    loading.hidden = false;
    loading.textContent = state.message;
  } else {
    loading.hidden = true;
    frame.hidden = false;
    frame.src = safePageUrl(state.url);
  }
  if (announcement) announce(announcement);
  else status.textContent = "";
}

async function readCurrent() {
  if (busy || !pagePath) return;
  setBusy(true);
  try {
    const result = await app.callServerTool({
      name: "leaf_read_page",
      arguments: { page: pagePath },
    });
    const answer = payload(result);
    if (!answer?.ok) throw new Error(answer?.error ?? "Leaf refused the read");
    render(answer.state, "Refreshed the Leaf page");
  } catch (error) {
    announce(`Could not refresh: ${String(error)}`);
  } finally {
    setBusy(false);
  }
}

function applyContext(context) {
  if (!context) return;
  if (context.theme) applyDocumentTheme(context.theme);
  if (context.styles?.variables) applyHostStyleVariables(context.styles.variables);
  if (context.styles?.css?.fonts) applyHostFonts(context.styles.css.fonts);
  if (context.safeAreaInsets) {
    for (const edge of ["top", "right", "bottom", "left"])
      shell.style.setProperty(`--safe-${edge}`, `${context.safeAreaInsets[edge]}px`);
  }
  mode = context.displayMode ?? mode;
  if (context.availableDisplayModes !== undefined)
    displayMode.hidden = !context.availableDisplayModes.includes("fullscreen");
  displayMode.textContent = mode === "fullscreen" ? "Return inline" : "Full screen";
}

app.ontoolresult = (result) => {
  const answer = payload(result);
  if (answer?.state) render(answer.state);
};
app.onhostcontextchanged = applyContext;
app.onerror = (error) => announce(`Host error: ${String(error)}`);
app.onteardown = async () => {
  frame.src = "about:blank";
  return {};
};

frame.addEventListener("load", () => announce("Leaf page loaded"));
refresh.addEventListener("click", readCurrent);
openPage.addEventListener("click", async () => {
  if (!current?.url) return;
  try {
    const answer = await app.openLink({ url: current.url });
    if (answer?.isError) announce("The host did not open the page");
  } catch (error) {
    announce(`Could not open the page: ${String(error)}`);
  }
});
displayMode.addEventListener("click", async () => {
  if (busy) return;
  setBusy(true);
  try {
    const next = mode === "fullscreen" ? "inline" : "fullscreen";
    const answer = await app.requestDisplayMode({ mode: next });
    mode = answer.mode;
    displayMode.textContent = mode === "fullscreen" ? "Return inline" : "Full screen";
  } catch (error) {
    announce(`Could not change the display: ${String(error)}`);
  } finally {
    setBusy(false);
  }
});

app
  .connect()
  .then(() => applyContext(app.getHostContext()))
  .catch((error) => {
    loading.textContent = `Could not connect to this host: ${String(error)}`;
    announce("Leaf could not connect to this host");
  });
