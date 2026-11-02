/* A document owns one text and its source/preview readings. The text is its `value`,
 * which Leaf sets from a bound source or widget output, or from the `<pre>` the page
 * wrote when the markup binds neither (element-data.js, "Bound values"). Optional
 * previews compose the ordinary lf-tabs switcher, so keyboard, reveal, and tab
 * memory have the same owner as authored views. Each reading has its own bounded
 * viewport, keeping the page still when switching and its scroll place independent.
 * Pierre draws numbered source using the same static renderer as diffs. Its sheets
 * are scoped to the listing; gutter glyphs are generated content, so selecting or
 * copying the source never includes line numbers. The Markdown preview renders a file,
 * whose soft line breaks are spaces, so a paragraph wraps to the preview's width. The
 * source and Markdown renderers reconcile unchanged text across source updates. HTML
 * lives in a separate frame so its styles and scripts cannot access Leaf’s document.
 * Source provenance is stamped with its text before awaiting the frame's presentation. */
import {
  failSoft,
  generatedElement,
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

// Writing the same key again would still be a mutation the page's observers see.
/** @param {HTMLElement} node @param {string} key */
const mark = (node, key) => {
  if (node.dataset.lfDatum !== key) node.dataset.lfDatum = key;
};

/** @param {string} source @param {string | null} language */
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
  // A line number is Leaf's control, drawn from `data-number`; dropping Pierre's
  // attribute keeps its sheet's rule for that span (a positioned, stacked
  // inline-block) off it.
  for (const number of rendered.querySelectorAll("span[data-line-number-content]")) {
    number.removeAttribute("data-line-number-content");
    number.setAttribute("data-number", number.textContent);
    number.textContent = "";
    number.classList.add("lf-ui");
    generatedElement(number, { says: false });
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
    const ending = endings[index];
    if (ending !== undefined) line.append(ending);
  });
  const code = rendered.querySelector("code");
  const pre = rendered.querySelector("pre");
  if (!code || !pre || code.textContent !== source)
    throw new Error("Pierre did not return the source unchanged");
  markSyntax(rendered, foreground);
  return { rendered, pre, code };
}

class TextDocument extends LeafElement {
  rendering = 0;
  /** @type {(() => void) | null} */
  finishFrame = null;
  /** @type {Promise<void> | undefined} */
  frameLoaded;
  /** @type {ReturnType<TextDocument["build"]> | undefined} */
  view;
  /** @type {{pre: HTMLPreElement, code: HTMLElement} | null} */
  sourceView = null;
  setup() {
    // A departure abandons the rendering in flight and its frame's wait.
    whileConnected(this, () => () => {
      this.rendering = this.rendering + 1;
      this.finishFrame?.();
    });
  }

  // The text, set by whoever hosts the widget: Leaf from the bound source or output
  // (the registry's `x-data.document.property`), or from the written `<pre>`; null
  // while a bound source has none.
  static properties = { value: { attribute: false } };

  constructor() {
    super();
    /** @type {string | null} */
    this.value = null;
  }

  render() {
    return nothing;
  }

  // Highlighting and the preview load after the draw; `updateComplete` waits for
  // them, as a Lit element's completion does for work its update starts.
  /** @param {import("lit").PropertyValues} changed */
  updated(changed) {
    super.updated(changed);
    this.showing = this.show(this.value);
  }

  // Also waits for the drawing the latest update started: a newer update's drawing
  // replaces one still pending.
  async getUpdateComplete() {
    const result = await super.getUpdateComplete();
    await this.showing;
    return result;
  }

  /** @param {string | null} value */
  async show(value) {
    const rendering = this.rendering + 1;
    this.rendering = rendering;
    const source = value ?? "";
    const preview = this.getAttribute("preview");
    try {
      if (preview) await import("./lf-tabs.js");
      const language = this.getAttribute("language") ?? preview;
      const {
        rendered: listing,
        pre: drawnPre,
        code: drawnCode,
      } = await sourceListing(source, language);
      if (preview === "markdown") {
        let failure;
        if (!(await loadMarkdown((error) => (failure = error)))) throw failure;
      }
      if (rendering !== this.rendering || !this.isConnected) return;
      const view = (this.view ??= this.build(preview));
      const label =
        this.getAttribute("label") ??
        this.getAttribute("source") ??
        this.getAttribute("for");
      keepsText(view.caption, value == null ? `${label} · no data` : label);
      if (!this.sourceView) {
        setChildren(view.listing, [...listing.childNodes]);
        this.sourceView = { pre: drawnPre, code: drawnCode };
      } else {
        // The pre owns provenance and scroll; the code owns its native reach stop.
        // Reconcile only their source children, leaving those independent owners
        // in place while unchanged lines keep their text nodes and selection.
        setRenderedChildren(this.sourceView.code, drawnCode.childNodes);
        const width = "--diffs-min-number-column-width-default";
        const drawnWidth = drawnPre.style.getPropertyValue(width);
        if (this.sourceView.pre.style.getPropertyValue(width) !== drawnWidth)
          this.sourceView.pre.style.setProperty(width, drawnWidth);
      }
      let loaded = this.frameLoaded;
      const previewNode = view.preview;
      if (previewNode instanceof HTMLDivElement) {
        const template = document.createElement("template");
        template.innerHTML = renderMarkdown(source, false);
        setRenderedChildren(previewNode, template.content.childNodes);
      } else if (
        previewNode instanceof HTMLIFrameElement &&
        (!previewNode.isConnected ||
          !previewNode.hasAttribute("srcdoc") ||
          previewNode.srcdoc !== source)
      ) {
        this.finishFrame?.();
        loaded = this.frameLoaded = new Promise((resolve) => {
          const finish = () => {
            previewNode.removeEventListener("load", finish);
            if (this.finishFrame === finish) this.finishFrame = null;
            resolve(undefined);
          };
          this.finishFrame = finish;
          previewNode.addEventListener("load", finish);
        });
        if (!previewNode.hasAttribute("srcdoc") || previewNode.srcdoc !== source)
          previewNode.srcdoc = source;
      }
      setChildren(this, [view.figure]);
      // The drawn text's items, marked for whoever hosts the widget: on a Leaf page,
      // comments on them anchor to the document's data.
      if (previewNode) {
        mark(this.sourceView.pre, "source");
        mark(previewNode, "preview");
      } else mark(view.figure, "document");
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
      if (loaded) await loaded;
      if (rendering !== this.rendering || !this.isConnected) return;
      this.classList.toggle("lf-rendered", true);
    } catch (error) {
      if (rendering !== this.rendering || !this.isConnected) return;
      failSoft(this, error, source);
    }
  }

  /** @param {string | null} preview
   * @returns {{figure: HTMLElement, caption: HTMLElement, listing: HTMLDivElement, preview: HTMLElement | null}} */
  build(preview) {
    const figure = document.createElement("figure");
    figure.className = "lf-text-document-view";
    const caption = document.createElement("figcaption");
    const listing = document.createElement("div");
    listing.className = "lf-text-document-listing scroll";
    figure.append(caption);
    if (!preview) {
      figure.append(listing);
      return { figure, caption, listing, preview: null };
    }
    const tabs = document.createElement("lf-tabs");
    tabs.id = `${this.id}--views`;
    // Its members are this document's data readings, not authored page content.
    generatedElement(tabs, { says: false });
    const bound = this.getAttribute("data-lf-bound") ?? "start";
    const rendered = document.createElement("lf-tab");
    rendered.id = `${this.id}--preview`;
    rendered.setAttribute("label", "Preview");
    rendered.setAttribute("data-lf-bound", bound);
    const literal = document.createElement("lf-tab");
    literal.id = `${this.id}--source`;
    literal.setAttribute("label", "Source");
    literal.setAttribute("data-lf-bound", bound);
    const drawn =
      preview === "html"
        ? document.createElement("iframe")
        : document.createElement("div");
    drawn.className = "lf-text-document-preview";
    if (drawn instanceof HTMLIFrameElement) {
      drawn.title = `${this.getAttribute("label") ?? this.getAttribute("source") ?? this.getAttribute("for")} preview`;
      drawn.setAttribute("sandbox", "allow-scripts");
    }
    rendered.append(drawn);
    literal.append(listing);
    tabs.append(rendered, literal);
    figure.append(tabs);
    return { figure, caption, listing, preview: drawn };
  }
}
customElements.define("lf-text-document", TextDocument);
