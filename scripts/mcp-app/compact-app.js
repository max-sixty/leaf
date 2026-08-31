import {
  App,
  applyDocumentTheme,
  applyHostFonts,
  applyHostStyleVariables,
} from "@modelcontextprotocol/ext-apps/app-with-deps";

const app = new App({ name: "Leaf compact ask", version: "0.1.0" });
const content = document.querySelector("#content");
const sequence = document.querySelector("#sequence");
const status = document.querySelector("#status");
const refresh = document.querySelector("#refresh");
const openFull = document.querySelector("#open-full");
const shell = document.querySelector("#app");
let current = null;
let pagePath = null;
let busy = false;

function payload(result) {
  return result?.structuredContent ?? result?.structured_content ?? null;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
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
  for (const button of content.querySelectorAll("button")) button.disabled = value;
}

function showMessage(state) {
  const kicker = element("p", "kicker", state.title || "Leaf page");
  const heading = element(
    "h1",
    "",
    state.mode === "empty"
      ? "Nothing waiting here"
      : state.full_page_url
        ? "Continue on the full page"
        : "Not available inline",
  );
  const message = element("p", "message", state.message);
  if (state.mode === "empty") {
    const mark = element("span", "empty-mark", "✓");
    mark.setAttribute("aria-hidden", "true");
    content.append(mark);
  }
  content.append(kicker, heading, message);
}

function choiceButton(option, ask) {
  const button = element("button", "option");
  button.type = "button";
  button.dataset.option = option.id;
  button.setAttribute("aria-label", option.label);
  button.append(element("span", "option-label", option.label));
  const summaryText = supportingText(option);
  if (summaryText) {
    const summary = element("span", "option-summary", summaryText);
    summary.id = `option-summary-${option.id}`;
    button.setAttribute("aria-describedby", summary.id);
    button.append(summary);
  }
  button.addEventListener("click", () => choose(option, ask));
  return button;
}

function supportingText(option) {
  const summary = option.summary?.trim();
  if (!summary || summary === option.label) return "";
  const labelAt = summary.indexOf(option.label);
  if (labelAt < 0) return summary;
  return `${summary.slice(0, labelAt)} ${summary.slice(labelAt + option.label.length)}`
    .trim()
    .replaceAll(/\s+/g, " ");
}

function showAsk(state) {
  const ask = state.ask;
  content.append(
    element("p", "kicker", state.title || "Leaf page"),
    element("h1", "", ask.question),
  );
  if (ask.context) content.append(element("p", "context", ask.context));
  const options = element("div", "options");
  options.setAttribute("role", "group");
  options.setAttribute("aria-label", ask.question);
  for (const option of ask.options) options.append(choiceButton(option, ask));
  content.append(options);
}

function render(state, announcement) {
  current = state;
  pagePath = state.page ?? pagePath;
  content.replaceChildren();
  sequence.textContent = `event ${state.event_seq} · ${state.active?.label ?? "no revision"}`;
  openFull.hidden = !state.full_page_url;
  state.mode === "ask" ? showAsk(state) : showMessage(state);
  if (announcement) announce(announcement);
  else status.textContent = "";
}

async function choose(option, ask) {
  if (busy || !pagePath) return;
  setBusy(true);
  announce(`Recording ${option.label}`);
  const event = {
    ...ask.submit,
    detail: { options: [option.id] },
    attempt: crypto.randomUUID().replaceAll("-", ""),
  };
  try {
    const result = await app.callServerTool({
      name: "leaf_post_event",
      arguments: { page: pagePath, event },
    });
    const answer = payload(result);
    if (!answer?.ok) throw new Error(answer?.error ?? "Leaf refused the event");
    render(answer.state, `Recorded ${option.label}`);
  } catch (error) {
    announce(`Could not record the choice: ${String(error)}`);
  } finally {
    setBusy(false);
  }
}

async function readCurrent() {
  if (busy || !pagePath) return;
  setBusy(true);
  try {
    const result = await app.callServerTool({
      name: "leaf_read_compact_ask",
      arguments: { page: pagePath },
    });
    const answer = payload(result);
    if (!answer?.ok) throw new Error(answer?.error ?? "Leaf refused the read");
    render(answer.state, "Refreshed the Leaf ask");
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
}

app.ontoolresult = (result) => {
  const answer = payload(result);
  if (answer?.state) render(answer.state);
};
app.onhostcontextchanged = applyContext;
app.onerror = (error) => announce(`Host error: ${String(error)}`);
app.onteardown = async () => ({});

refresh.addEventListener("click", readCurrent);
openFull.addEventListener("click", async () => {
  if (!current?.full_page_url) return;
  try {
    const answer = await app.openLink({ url: current.full_page_url });
    if (answer?.isError) announce("The host did not open the full page");
  } catch (error) {
    announce(`Could not open the full page: ${String(error)}`);
  }
});

app
  .connect()
  .then(() => applyContext(app.getHostContext()))
  .catch((error) => {
    content.replaceChildren(
      element("h1", "", "Could not connect to this host"),
      element("p", "message", String(error)),
    );
    announce("Leaf could not connect to this host");
  });
