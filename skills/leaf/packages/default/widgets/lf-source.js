import {
  failSoft,
  projectData,
  settle,
  synNodes,
  syntax,
  watchData,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-source",
  class extends HTMLElement {
    connectedCallback() {
      if (this.stopWatching) return;
      let first = true;
      this.stopWatching = watchData(this, "document", (snapshot) => {
        const rendering = this.render(snapshot);
        if (first) {
          settle(rendering);
          first = false;
        }
        return rendering;
      });
    }

    disconnectedCallback() {
      this.rendering = (this.rendering ?? 0) + 1;
      this.stopWatching?.();
      this.stopWatching = null;
    }

    async render(snapshot) {
      const rendering = (this.rendering ?? 0) + 1;
      this.rendering = rendering;
      const source = snapshot?.value ?? "";
      try {
        const language = this.getAttribute("language");
        const tokens = language ? await syntax(source, language) : [{ text: source }];
        if (rendering !== this.rendering || !this.isConnected) return;
        projectData(
          this,
          [{ snapshot, tokens }],
          () => "document",
          (record, prior) => sourceNode(this, record, prior),
          { originOf: () => snapshot?.origin },
        );
        this.classList.add("lf-rendered");
      } catch (error) {
        if (rendering !== this.rendering || !this.isConnected) return;
        failSoft(this, error, source);
      }
    }
  },
);

function sourceNode(widget, { snapshot, tokens }, prior) {
  const figure = prior ?? document.createElement("figure");
  figure.className = "lf-source-document";
  let caption = figure.querySelector(":scope > figcaption");
  let pre = figure.querySelector(":scope > pre");
  if (!caption || !pre) {
    caption = document.createElement("figcaption");
    pre = document.createElement("pre");
    pre.append(document.createElement("code"));
    figure.replaceChildren(caption, pre);
  }
  const label = snapshot?.label ?? widget.getAttribute("source");
  const details = [];
  if (snapshot?.lines) details.push(`lines ${snapshot.lines.replace(":", "–")}`);
  if (snapshot?.snapshot) details.push(`snapshot ${snapshot.snapshot}`);
  if (!snapshot) details.push("no data");
  const heading = details.length ? `${label} · ${details.join(" · ")}` : label;
  if (caption.textContent !== heading) caption.textContent = heading;
  const code = pre.querySelector("code");
  const source = tokens.map(({ text }) => text).join("");
  if (code.textContent !== source) code.replaceChildren(...synNodes(tokens));
  return figure;
}
