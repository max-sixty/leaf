/* A bound document owns one source and its source/preview readings. Optional
 * previews compose the ordinary lf-tabs switcher, so keyboard, reveal, and tab
 * memory have the same owner as authored views. Each reading has its own bounded
 * viewport, keeping the page still when switching and its scroll place independent.
 * Pierre draws numbered source using the same static renderer as diffs. Its sheets
 * are scoped to the listing; gutter glyphs are generated content, so selecting or
 * copying the source never includes line numbers. The source and Markdown renderers
 * reconcile unchanged text across source updates. HTML lives in a separate frame
 * so its styles and scripts cannot access Leaf’s document. Source provenance is
 * stamped with its text before awaiting the frame's presentation. */
import {
  failSoft,
  projectData,
  ensureSyntaxLanguage,
  inBaseLayer,
  LeafElement,
  nothing,
  whileConnected,
  keepsText,
  setRenderedChildren,
  setChildren,
  loadMarkdown,
  renderMarkdown,
} from "/runtime/widget-api.js";
import { pierre, markSyntax } from "./pierre.js";

async function sourceListing(source, language) {
  const [{ preloadFile }, { themeName, foreground }] = await Promise.all([
    pierre(),
    ensureSyntaxLanguage(language),
  ]);
  const { prerenderedHTML } = await preloadFile({
    file: { name: "source", contents: source, lang: language ?? "text" },
    options: { theme: themeName, disableFileHeader: true, overflow: "wrap" },
  });
  const template = document.createElement("template");
  template.innerHTML = prerenderedHTML;
  const rendered = template.content;
  rendered.querySelector("svg[data-icon-sprite]")?.remove();
  for (const style of rendered.querySelectorAll("style")) {
    // A style's implicit @scope root is its parent listing. Pierre's :host rules
    // describe that file box here, without adding a second shadow-tree owner.
    style.textContent = inBaseLayer(
      `@scope { ${style.textContent.replaceAll(":host", ":scope")} }`,
    );
  }
  for (const number of rendered.querySelectorAll("span[data-line-number-content]")) {
    number.setAttribute("data-number", number.textContent);
    number.textContent = "";
    number.classList.add("lf-ui");
    number.setAttribute("data-lf-gen", "1");
    number.setAttribute("aria-hidden", "true");
  }
  // Pierre uses block rows without source newlines. Retain the exact input in the
  // DOM as well as its drawing, including its final newline (or absence of one).
  const lines = [...rendered.querySelectorAll("[data-content] [data-line]")];
  const text = source.split(/\r\n|\r|\n/);
  const endings = source.match(/\r\n|\r|\n/g) ?? [];
  lines.forEach((line, index) => {
    // Some grammars represent an empty row with a newline placeholder.
    if (text[index] === "" && line.textContent === "\n") line.replaceChildren();
    if (index < endings.length) line.append(endings[index]);
  });
  if (rendered.querySelector("code").textContent !== source)
    throw new Error("Pierre did not return the source unchanged");
  markSyntax(rendered, foreground);
  return rendered;
}

customElements.define(
  "lf-text-document",
  class extends LeafElement {
    setup() {
      // A departure abandons the rendering in flight and its frame's wait.
      whileConnected(this, () => () => {
        this.rendering = (this.rendering ?? 0) + 1;
        this.finishFrame?.();
      });
    }

    render() {
      this.snapshot = this.data("document");
      return nothing;
    }

    // Highlighting and the preview load after the draw, and the draw's claim waits
    // for them.
    updated(changed) {
      super.updated(changed);
      this.drawing(this.show(this.snapshot));
    }

    async show(snapshot) {
      const rendering = (this.rendering ?? 0) + 1;
      this.rendering = rendering;
      const source = snapshot?.value ?? "";
      const preview = this.getAttribute("preview");
      try {
        if (preview) await import("./lf-tabs.js");
        const language = this.getAttribute("language") ?? preview;
        const listing = await sourceListing(source, language);
        if (preview === "markdown") {
          let failure;
          if (!(await loadMarkdown((error) => (failure = error)))) throw failure;
        }
        if (rendering !== this.rendering || !this.isConnected) return;
        /** @type {HTMLElement} */
        this.figure = this.figure ?? this.build(preview);
        const label = this.getAttribute("label") ?? this.getAttribute("source");
        keepsText(this.caption, snapshot ? label : `${label} · no data`);
        const drawnPre = listing.querySelector("pre");
        if (!this.pre) {
          setChildren(this.listing, [...listing.childNodes]);
          this.pre = drawnPre;
          this.code = this.pre.querySelector("code");
        } else {
          // The pre owns provenance and scroll; the code owns its native reach stop.
          // Reconcile only their source children, leaving those independent owners
          // in place while unchanged lines keep their text nodes and selection.
          setRenderedChildren(this.code, drawnPre.querySelector("code").childNodes);
          const width = "--diffs-min-number-column-width-default";
          const value = drawnPre.style.getPropertyValue(width);
          if (this.pre.style.getPropertyValue(width) !== value)
            this.pre.style.setProperty(width, value);
        }
        let loaded = this.frameLoaded;
        if (preview === "markdown") {
          const template = document.createElement("template");
          template.innerHTML = renderMarkdown(source);
          setRenderedChildren(this.preview, template.content.childNodes);
        } else if (
          preview === "html" &&
          (!this.preview.isConnected ||
            !this.preview.hasAttribute("srcdoc") ||
            this.preview.srcdoc !== source)
        ) {
          this.finishFrame?.();
          loaded = this.frameLoaded = new Promise((resolve) => {
            const finish = () => {
              this.preview.removeEventListener("load", finish);
              if (this.finishFrame === finish) this.finishFrame = null;
              resolve(undefined);
            };
            this.finishFrame = finish;
            this.preview.addEventListener("load", finish);
          });
          if (!this.preview.hasAttribute("srcdoc") || this.preview.srcdoc !== source)
            this.preview.srcdoc = source;
        }
        setChildren(this, [this.figure]);
        projectData(
          this,
          preview
            ? [
                { key: "source", node: this.pre },
                { key: "preview", node: this.preview },
              ]
            : [{ key: "document", node: this.figure }],
          { snapshot },
        );
        if (loaded) await loaded;
        if (rendering !== this.rendering || !this.isConnected) return;
        this.classList.toggle("lf-rendered", true);
      } catch (error) {
        if (rendering !== this.rendering || !this.isConnected) return;
        failSoft(this, error, source);
      }
    }

    build(preview) {
      const figure = document.createElement("figure");
      figure.className = "lf-text-document-view";
      this.caption = document.createElement("figcaption");
      this.listing = document.createElement("div");
      this.listing.className = "lf-text-document-listing";
      figure.append(this.caption);
      if (!preview) {
        figure.append(this.listing);
        return figure;
      }
      const tabs = document.createElement("lf-tabs");
      tabs.id = `${this.id}--views`;
      const bound = this.getAttribute("data-lf-bound") ?? "start";
      const rendered = document.createElement("lf-tab");
      rendered.id = `${this.id}--preview`;
      rendered.setAttribute("label", "Preview");
      rendered.setAttribute("data-lf-bound", bound);
      const literal = document.createElement("lf-tab");
      literal.id = `${this.id}--source`;
      literal.setAttribute("label", "Source");
      literal.setAttribute("data-lf-bound", bound);
      /** @type {HTMLElement & Partial<HTMLIFrameElement>} */
      this.preview = document.createElement(preview === "html" ? "iframe" : "div");
      this.preview.className = "lf-text-document-preview";
      if (preview === "html") {
        this.preview.title = `${this.getAttribute("label") ?? this.getAttribute("source")} preview`;
        this.preview.setAttribute("sandbox", "allow-scripts");
      }
      rendered.append(this.preview);
      literal.append(this.listing);
      tabs.append(rendered, literal);
      figure.append(tabs);
      return figure;
    }
  },
);
