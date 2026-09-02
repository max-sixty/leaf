import {
  App,
  applyDocumentTheme,
  applyHostFonts,
  applyHostStyleVariables,
} from "@modelcontextprotocol/ext-apps/app-with-deps";

const PAGE_FORMAT = "leaf.page/v1";
const SNAPSHOT_FORMAT = "leaf.snapshot/v1";
const PAGE_READY_EVENT = "leaf:mcp-page-ready";
const PAGE_READY_TIMEOUT_MS = 5000;
const app = new App(
  { name: "Leaf presentation", version: "0.2.0" },
  { availableDisplayModes: ["inline", "fullscreen"] },
);
const shell = document.querySelector("#app");
const frame = document.querySelector("#leaf-page");
const pageLoading = document.querySelector("#page-loading");
const surface = document.querySelector("#surface");
const pageHost = document.querySelector("#page-host");
const shadow = pageHost.attachShadow({ mode: "open" });
const title = document.querySelector("#title");
const meta = document.querySelector("#meta");
const status = document.querySelector("#status");
const statusText = document.querySelector("#status-text");
const commentPage = document.querySelector("#comment-page");
const browser = document.querySelector("#browser");
const snapshotButton = document.querySelector("#snapshot");
const refresh = document.querySelector("#refresh");
const fullscreen = document.querySelector("#fullscreen");
const composer = document.querySelector("#composer");
const quote = document.querySelector("#quote");
const comment = document.querySelector("#comment");
const cancel = document.querySelector("#cancel");
const send = document.querySelector("#send");
let current = null;
let currentMode = null;
let selection = null;
let hostContext = {};
let hostCapabilities = {};
let displayMode = "inline";
let busy = false;
let fullRoute = null;
let readyUrl = null;
let readyTimer = null;

function payload(result) {
  return (
    result?._meta?.leaf ??
    result?.structuredContent ??
    result?.structured_content ??
    null
  );
}

function errorText(error) {
  return error?.message || error?.data?.message || String(error);
}

function showStatus(text, { error = false } = {}) {
  statusText.textContent = text;
  status.classList.toggle("show", Boolean(text));
  status.classList.toggle("error", error);
}

function supportsServerTools() {
  return Boolean(hostCapabilities.serverTools);
}

function syncControls() {
  const canCall = supportsServerTools();
  refresh.disabled = busy || !canCall || !current;
  commentPage.disabled = busy || !canCall || currentMode !== "snapshot";
  snapshotButton.disabled = busy || !canCall || currentMode !== "page";
  send.disabled = busy || !canCall;
  fullscreen.disabled = busy;
}

function setBusy(value) {
  busy = value;
  syncControls();
}

function safePageUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "http:" || url.hostname !== "localhost")
    throw new Error("Leaf returned an unexpected page address");
  return url.href;
}

function attemptId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function themeCss(base = "", dark = "") {
  const chosen =
    hostContext.theme === "dark"
      ? `${base}\n${dark}`
      : hostContext.theme === "light"
        ? base
        : `${base}\n@media (prefers-color-scheme: dark) {${dark}}`;
  return chosen.replaceAll(":root", ":host");
}

function pageCss(leaf) {
  return `${themeCss(leaf.theme, leaf.darkTheme)}
    ${(leaf.authoredCss || "").replaceAll(":root", ":host")}
    :host {
      display: block !important;
      position: relative !important;
      inset: auto !important;
      z-index: 0 !important;
      width: auto !important;
      min-width: 0 !important;
      max-width: 100% !important;
      height: auto !important;
      margin: 0 !important;
      overflow: clip !important;
      contain: layout paint style !important;
      isolation: isolate !important;
      transform: none !important;
      color-scheme: light dark;
    }
    main { box-sizing: border-box; min-height: 160px; padding-block: 24px 70px; }
    [data-lf-gen], .lf-ui { display: none !important; }
    a, area, form, button, input, select, textarea {
      pointer-events: none !important;
    }
  `;
}

function containSnapshotHost() {
  const properties = {
    display: "block",
    position: "relative",
    inset: "auto",
    "z-index": "0",
    width: "auto",
    "min-width": "0",
    "max-width": "100%",
    height: "auto",
    margin: "0",
    overflow: "clip",
    contain: "layout paint style",
    isolation: "isolate",
    transform: "none",
    translate: "none",
    rotate: "none",
    scale: "none",
    filter: "none",
    "backdrop-filter": "none",
    perspective: "none",
    "box-shadow": "none",
    outline: "none",
    "mix-blend-mode": "normal",
  };
  for (const [name, value] of Object.entries(properties))
    pageHost.style.setProperty(name, value, "important");
}

function cleanDocument(html) {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const source = parsed.querySelector("main");
  const fragment = document.createElement("template");
  fragment.innerHTML = source ? source.innerHTML : "";
  fragment.content
    .querySelectorAll("script,style,link,iframe,object,embed,base,meta")
    .forEach((node) => node.remove());
  const safeAttribute = (node, attr) => {
    const name = attr.name.toLowerCase();
    if (
      name.startsWith("on") ||
      name === "contenteditable" ||
      name === "autofocus" ||
      name === "srcdoc" ||
      name === "target" ||
      name === "formtarget" ||
      name === "action" ||
      name === "formaction" ||
      name === "form" ||
      name === "ping" ||
      name === "download"
    ) {
      node.removeAttribute(attr.name);
      return;
    }
    if (node.matches("a,area") && ["href", "xlink:href"].includes(name)) {
      node.removeAttribute(attr.name);
      return;
    }
    if (
      ["href", "src", "xlink:href"].includes(name) &&
      /^\s*javascript:/i.test(attr.value)
    ) {
      node.removeAttribute(attr.name);
    }
  };
  fragment.content.querySelectorAll("*").forEach((node) => {
    for (const attr of [...node.attributes]) safeAttribute(node, attr);
    if (node.matches("button,input,select,textarea")) node.disabled = true;
  });
  const main = document.createElement("main");
  if (source) {
    for (const attr of [...source.attributes]) main.setAttribute(attr.name, attr.value);
    for (const attr of [...main.attributes]) safeAttribute(main, attr);
  }
  main.append(fragment.content);
  return main;
}

function resetComposer() {
  selection = null;
  comment.value = "";
  quote.textContent = "";
  composer.classList.remove("open");
  sizeComment();
}

function clearReadyTimer() {
  if (readyTimer !== null) clearTimeout(readyTimer);
  readyTimer = null;
}

function blankPageFrame() {
  clearReadyTimer();
  frame.hidden = true;
  frame.src = "about:blank";
  readyUrl = null;
}

function approvedFrameDomains() {
  const domains = hostCapabilities.sandbox?.csp?.frameDomains;
  return Array.isArray(domains) ? domains : null;
}

function frameOriginApproved(url) {
  const domains = approvedFrameDomains();
  if (domains === null) return true;
  const origin = new URL(url).origin;
  return domains.some((domain) => {
    try {
      return new URL(domain).origin === origin;
    } catch {
      return domain === origin;
    }
  });
}

async function showSnapshotFallback(state, message) {
  if (current !== state || currentMode !== "page") return;
  if (!supportsServerTools()) {
    pageLoading.textContent = "The complete page is unavailable in this host.";
    showStatus("Use Open in browser for the full interface.", { error: true });
    return;
  }
  setBusy(true);
  try {
    await callTool("leaf_snapshot_refresh", { page: state.page });
    showStatus(message);
  } catch (error) {
    pageLoading.textContent = "The complete page is unavailable in this host.";
    showStatus(`Its snapshot also failed: ${errorText(error)}`, { error: true });
  } finally {
    setBusy(false);
  }
}

function waitForPageReady(state, url) {
  clearReadyTimer();
  readyTimer = setTimeout(async () => {
    readyTimer = null;
    if (current !== state || currentMode !== "page" || readyUrl === url) return;
    await showSnapshotFallback(
      state,
      "The complete page did not become ready, so Leaf is showing its comments-only snapshot.",
    );
  }, PAGE_READY_TIMEOUT_MS);
}

function renderPage(state) {
  if (state.format !== PAGE_FORMAT || state.mode !== "page")
    throw new Error("Leaf returned an invalid complete-page payload");
  pageHost.removeAttribute("style");
  current = state;
  currentMode = "page";
  fullRoute = {
    inlineUrl: state.inline_url,
    browserUrl: state.browser_url,
  };
  shell.classList.add("page-mode");
  surface.classList.add("page-surface");
  title.textContent = state.title || "Untitled page";
  meta.textContent = `Complete page · ${state.active?.label ?? "no revision"} · event ${state.event_seq}`;
  commentPage.hidden = true;
  snapshotButton.hidden = false;
  browser.textContent = "Open in browser";
  browser.title = "Open the complete Leaf page outside this attachment";
  browser.disabled = !(state.browser_url || state.inline_url);
  pageHost.hidden = true;
  pageLoading.hidden = false;
  pageLoading.textContent = "Opening the complete page…";
  frame.hidden = true;
  shadow.replaceChildren();
  resetComposer();
  const next = safePageUrl(state.inline_url);
  hostCapabilities = app.getHostCapabilities() || hostCapabilities;
  if (!frameOriginApproved(next)) {
    blankPageFrame();
    showStatus(
      "This host did not approve the complete page frame. Opening the comments-only snapshot…",
    );
    void showSnapshotFallback(
      state,
      "This host did not approve the complete page frame, so Leaf is showing its comments-only snapshot.",
    );
    syncControls();
    return;
  }
  if (frame.src !== next) frame.src = next;
  if (readyUrl === next) {
    clearReadyTimer();
    pageLoading.hidden = true;
    frame.hidden = false;
    showStatus("Complete Leaf page ready.");
  } else {
    showStatus(
      state.source_error
        ? "Opening the last valid revision. If it remains unavailable, Leaf will show its snapshot."
        : "Opening the complete page. If it remains unavailable, Leaf will show its snapshot.",
    );
    waitForPageReady(state, next);
  }
  syncControls();
}

function renderSnapshot(state) {
  if (state.format !== SNAPSHOT_FORMAT || state.mode !== "snapshot")
    throw new Error("Leaf returned an invalid snapshot payload");
  const fallbackUrl =
    state.url || fullRoute?.browserUrl || fullRoute?.inlineUrl || null;
  current = { ...state, ...(fallbackUrl && { url: fallbackUrl }) };
  currentMode = "snapshot";
  shell.classList.remove("page-mode");
  surface.classList.remove("page-surface");
  title.textContent = state.title || "Leaf review";
  meta.textContent = `Authored snapshot · comments only · r${state.revision} · event ${state.eventSeq}`;
  commentPage.hidden = false;
  snapshotButton.hidden = true;
  browser.textContent = "Full page";
  browser.title = "Open the full Leaf runtime for active controls";
  browser.disabled = false;
  pageLoading.hidden = true;
  blankPageFrame();
  pageHost.hidden = false;
  const style = document.createElement("style");
  style.dataset.leafTheme = "";
  style.textContent = pageCss(state);
  shadow.replaceChildren(style, cleanDocument(state.document));
  containSnapshotHost();
  resetComposer();
  showStatus(
    supportsServerTools()
      ? ""
      : "This host shows Leaf read-only. Use Full page to leave feedback.",
  );
  syncControls();
}

function render(state) {
  if (state?.format === PAGE_FORMAT && state?.mode === "page") {
    renderPage(state);
    return;
  }
  if (state?.format === SNAPSHOT_FORMAT && state?.mode === "snapshot") {
    renderSnapshot(state);
    return;
  }
  throw new Error("Leaf returned an unknown presentation payload");
}

function acceptToolResult(result) {
  if (result?.isError) {
    const text =
      result.content?.find((item) => item.type === "text")?.text ||
      "Leaf tool call failed.";
    throw new Error(text);
  }
  const leaf = payload(result);
  if (leaf) render(leaf);
  return result;
}

async function callTool(name, args) {
  if (!supportsServerTools())
    throw new Error("This host cannot call Leaf tools; use Full page instead.");
  return acceptToolResult(await app.callServerTool({ name, arguments: args }));
}

function sizeComment() {
  comment.style.height = "auto";
  comment.style.height = `${Math.min(Math.max(comment.scrollHeight, 66), 240)}px`;
}

// The passage as the document holds it, which is not the passage the host paints. A
// selection's own toString() gives back the rendering: the theme uppercases a table
// header and an eyebrow, and a <br> or a display:block span breaks a run the page's own
// words run together. An anchor written from that names a passage no reading of the
// version file can find, and the reader is told the page never said the words in front
// of them. So the characters come from the text nodes, and one space goes wherever the
// enclosing text block changes, using the tag vocabulary Python owns and sends as
// textBlocks. The collapse is JS's whitespace class, which passages.py spells out as
// COLLAPSE_CHARS. A node pageCss has taken off the page is out of the reading too, which
// is how the generated and runtime nodes it hides stay out of a quote.
//
// Which passage it is stays on the other side. The append gate reads the version under
// the lease that stores the anchor, and it is the one resolver: it writes the neighbours
// that tell two copies apart, and refuses a quote repeated without unique context rather
// than letting a client guess at document order.
function passageIn(range) {
  const root = range.commonAncestorContainer;
  const nodes = [];
  if (root.nodeType === Node.TEXT_NODE) nodes.push(root);
  else {
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walk.nextNode(); node; node = walk.nextNode()) {
      if (range.intersectsNode(node)) nodes.push(node);
    }
  }
  let text = "";
  let block = null;
  for (const node of nodes) {
    const from = node === range.startContainer ? range.startOffset : 0;
    const to = node === range.endContainer ? range.endOffset : node.data.length;
    const holder = node.parentElement;
    if (from >= to || !holder?.checkVisibility()) continue;
    const owner = holder.closest(current.textBlocks) || holder;
    if (text && owner !== block) text += " ";
    block = owner;
    text += node.data.slice(from, to);
  }
  return text.replace(/\s+/g, " ").trim();
}

function captureSelection() {
  const selected = shadow.getSelection?.() || getSelection();
  if (!selected || selected.isCollapsed) return null;
  const range = selected.getRangeAt(0);
  const quote = passageIn(range);
  if (!quote) return null;
  const common = range.commonAncestorContainer;
  const holder = common.nodeType === Node.ELEMENT_NODE ? common : common.parentElement;
  // `closest` stops at the shadow boundary, so this can only name the page's own ids.
  // Where the passage sits under none, the field is left out and the append gate names
  // the innermost element enclosing it.
  const section = holder?.closest?.("[id]")?.id;
  return { quote, ...(section && { section }) };
}

function openComposer(nextSelection) {
  selection = nextSelection;
  quote.textContent = selection?.quote
    ? `On “${selection.quote.length > 150 ? `${selection.quote.slice(0, 147)}…` : selection.quote}”`
    : selection?.section
      ? `On § ${selection.section}`
      : "On this page";
  comment.placeholder = selection?.quote
    ? "Comment on this passage"
    : selection?.section
      ? "Comment on this item"
      : "Comment on this page";
  composer.classList.add("open");
  sizeComment();
  comment.focus();
}

function applyHostContext(update) {
  if (!update) return;
  const previousTheme = hostContext.theme;
  hostContext = { ...hostContext, ...update };
  if (hostContext.theme) applyDocumentTheme(hostContext.theme);
  if (hostContext.styles?.variables)
    applyHostStyleVariables(hostContext.styles.variables);
  if (hostContext.styles?.css?.fonts) applyHostFonts(hostContext.styles.css.fonts);
  if (hostContext.safeAreaInsets) {
    for (const edge of ["top", "right", "bottom", "left"])
      shell.style.setProperty(
        `--safe-${edge}`,
        `${hostContext.safeAreaInsets[edge]}px`,
      );
  }
  displayMode = hostContext.displayMode ?? displayMode;
  const modes = hostContext.availableDisplayModes || [];
  fullscreen.hidden = !modes.includes("fullscreen") || displayMode === "fullscreen";
  fullscreen.textContent =
    displayMode === "fullscreen" ? "Return inline" : "Fullscreen";
  if (currentMode === "snapshot" && hostContext.theme !== previousTheme) {
    const style = shadow.querySelector("style[data-leaf-theme]");
    if (style) style.textContent = pageCss(current);
  }
}

app.ontoolresult = (result) => {
  try {
    acceptToolResult(result);
  } catch (error) {
    showStatus(errorText(error), { error: true });
  }
};
app.onhostcontextchanged = applyHostContext;
app.onerror = (error) => showStatus(`Host error: ${errorText(error)}`, { error: true });
app.onteardown = async () => {
  blankPageFrame();
  return {};
};

function preventSnapshotNavigation(event) {
  if (currentMode !== "snapshot") return;
  const navigationTarget = event
    .composedPath()
    .find((node) => node?.matches?.("a,area,form"));
  if (navigationTarget) event.preventDefault();
}

for (const name of ["click", "auxclick", "submit"])
  pageHost.addEventListener(name, preventSnapshotNavigation, { capture: true });

pageHost.addEventListener("mouseup", () => {
  if (currentMode !== "snapshot") return;
  const next = captureSelection();
  if (next) openComposer(next);
});

pageHost.addEventListener("dblclick", (event) => {
  if (currentMode !== "snapshot") return;
  // Inside the rendered page only. The composed path runs on out through this app's own
  // shell, and its ids name nothing any version of the page has got.
  const target = event.composedPath().find((node) => node?.id && shadow.contains(node));
  if (target) openComposer({ section: target.id });
});

cancel.addEventListener("click", resetComposer);
comment.addEventListener("input", sizeComment);
commentPage.addEventListener("click", () => {
  if (currentMode === "snapshot") openComposer(captureSelection());
});

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (currentMode !== "snapshot" || !current || busy) return;
  const text = comment.value.trim();
  if (!text) return;
  setBusy(true);
  try {
    const leafEvent = {
      kind: "comment",
      revision: current.revision,
      text,
      attempt: attemptId(),
      ...(selection && { anchor: selection }),
    };
    await callTool("leaf_snapshot_apply_event", {
      page: current.page,
      view_revision: current.revision,
      event: leafEvent,
    });
    resetComposer();
    showStatus("Feedback saved in the Leaf log. The Codex adapter will deliver it.");
  } catch (error) {
    showStatus(errorText(error), { error: true });
  } finally {
    setBusy(false);
  }
});

refresh.addEventListener("click", async () => {
  if (!current || busy) return;
  setBusy(true);
  try {
    const name = currentMode === "page" ? "leaf_refresh" : "leaf_snapshot_refresh";
    await callTool(name, { page: current.page });
    showStatus(
      currentMode === "page"
        ? "Refreshed the Leaf page."
        : "Refreshed the Leaf snapshot.",
    );
  } catch (error) {
    showStatus(errorText(error), { error: true });
  } finally {
    setBusy(false);
  }
});

snapshotButton.addEventListener("click", async () => {
  if (currentMode !== "page" || !current || busy) return;
  setBusy(true);
  try {
    await callTool("leaf_snapshot_refresh", { page: current.page });
    showStatus("Showing the comments-only snapshot inside this app.");
  } catch (error) {
    showStatus(errorText(error), { error: true });
  } finally {
    setBusy(false);
  }
});

window.addEventListener("message", (event) => {
  if (
    currentMode !== "page" ||
    event.source !== frame.contentWindow ||
    event.data?.type !== PAGE_READY_EVENT
  ) {
    return;
  }
  const url = safePageUrl(current.inline_url);
  if (event.origin !== new URL(url).origin) return;
  readyUrl = url;
  clearReadyTimer();
  pageLoading.hidden = true;
  frame.hidden = false;
  showStatus("Complete Leaf page ready.");
});

browser.addEventListener("click", async () => {
  if (!current) return;
  try {
    if (currentMode === "page") {
      const url = current.browser_url ?? current.inline_url;
      if (url) await app.openLink({ url });
      return;
    }
    if (current.url && hostCapabilities.openLinks) {
      await app.openLink({ url: current.url });
      return;
    }
    const url = current.url ? ` Its current URL is ${current.url}.` : "";
    await app.sendMessage({
      role: "user",
      content: [
        {
          type: "text",
          text: `Open the full Leaf browser page for ${current.page}; I need its active widget controls.${url}`,
        },
      ],
    });
    showStatus("Asked Codex to open the full Leaf page.");
  } catch (error) {
    showStatus(errorText(error), { error: true });
  }
});

fullscreen.addEventListener("click", async () => {
  if (busy) return;
  setBusy(true);
  try {
    const next = displayMode === "fullscreen" ? "inline" : "fullscreen";
    const answer = await app.requestDisplayMode({ mode: next });
    applyHostContext({ displayMode: answer.mode });
  } catch (error) {
    showStatus(errorText(error), { error: true });
  } finally {
    setBusy(false);
  }
});

app
  .connect()
  .then(() => {
    hostCapabilities = app.getHostCapabilities() || {};
    applyHostContext(app.getHostContext());
    syncControls();
  })
  .catch((error) => {
    showStatus(`This host did not initialize the Leaf app: ${errorText(error)}`, {
      error: true,
    });
  });
