/* A bound document owns one source and its source/preview readings. Optional
 * previews compose the ordinary lf-tabs switcher, so keyboard, reveal, and tab
 * memory have the same owner as authored views. Each reading has its own bounded
 * viewport, keeping the page still when switching and its scroll place independent.
 * The syntax and Markdown renderers
 * reconcile unchanged text across source updates. HTML lives in a separate frame
 * so its styles and scripts cannot access Leaf’s document. */
import {
  failSoft,
  projectData,
  synNodes,
  syntax,
  watchData,
  once,
  watchOwner,
  keepsText,
  setRenderedChildren,
  setChildren,
  loadMarkdown,
  renderMarkdown,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-text-document",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      watchOwner(this, {
        disconnect: () => {
          this.rendering = (this.rendering ?? 0) + 1;
          this.finishFrame?.();
        },
      });
      watchData(this, "document", (snapshot) => this.render(snapshot));
    }

    async render(snapshot) {
      const rendering = (this.rendering ?? 0) + 1;
      this.rendering = rendering;
      const source = snapshot?.value ?? "";
      const preview = this.getAttribute("preview");
      try {
        if (preview) await import("./lf-tabs.js");
        const language = this.getAttribute("language") ?? preview;
        const tokens = language
          ? await syntax(source, language)
          : [{ text: source, style: {} }];
        if (preview === "markdown") {
          let failure;
          if (!(await loadMarkdown((error) => (failure = error)))) throw failure;
        }
        if (rendering !== this.rendering || !this.isConnected) return;
        this.figure ??= this.build(preview);
        const label = this.getAttribute("label") ?? this.getAttribute("source");
        keepsText(this.caption, snapshot ? label : `${label} · no data`);
        if (this.code.textContent !== source)
          setRenderedChildren(this.code, synNodes(tokens));
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
              resolve();
            };
            this.finishFrame = finish;
            this.preview.addEventListener("load", finish);
          });
          if (!this.preview.hasAttribute("srcdoc") || this.preview.srcdoc !== source)
            this.preview.srcdoc = source;
        }
        setChildren(this, [this.figure]);
        if (loaded) await loaded;
        if (rendering !== this.rendering || !this.isConnected) return;
        projectData(
          this,
          preview
            ? [
                { key: "source", node: this.listing },
                { key: "preview", node: this.preview },
              ]
            : [{ key: "document", node: this.figure }],
          { snapshot },
        );
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
      this.listing = document.createElement("pre");
      this.code = document.createElement("code");
      this.listing.append(this.code);
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
