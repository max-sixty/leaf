/* The page a booted export draws, as one HTML file that runs no script
   (`exporting.py`, `static_document`). Playwright adds this before the page's own
   scripts, so it hears each shadow root the page attaches, closed ones included. Each
   step below runs once the page says it is ready, and the page is ready again before
   the next: `unfold`, until it finds no fold left, then `refold`, then `document`,
   which writes the file.

   A fold is a closed <details> or an element `hidden="until-found"`, and the file's
   reader can still open one: a <details> by its summary, the other by the browser's
   find-in-page. So the file holds what each fold draws once open, such as a collapsed
   diff file's lines or a chart in a tab not shown. Unfolding sets the fold's own state
   and fires no `beforematch`, so no widget moves its selection, as a tab set would.
   Refolding puts each fold back as it was and lets the page answer, so a control that
   shows whether folds are open, such as a diff's expand-all, says what it said.

   The file keeps what the runtime drew and leaves out what only a script can work:
   Leaf's chrome, every script and inline handler, the key shortcuts elements name, and
   noscript fallbacks, which would draw beside the page with scripts off. Every
   recording gets the browser's controls, since no script is left to play it, and a
   canvas becomes an image of the pixels a script drew on it. Each object URL becomes
   a data URL of its bytes, so images, fonts and recordings show wherever the markup
   and its CSS name them.

   Some of what the page shows lives outside its markup, and goes into the markup
   first. Serializing writes attributes, not the properties a script set, so a
   control's checked state, value and selection become attributes. A root's adopted
   sheets become style elements at its end, where adoption ranks them; a browser keeps
   no source text for them, so they are written as it parsed them, less any `@scope`
   whose root the file doesn't hold, such as the chrome's. A custom highlight's ranges
   become spans (`markHighlights`).

   An age (`lf-age`, browser/runtime/age.js) can't tick in a file that runs no script,
   so the file says when instead: the time its author wrote in it, else the clock time
   the age previews, which names its zone. The age the element drew is left out.

   `:defined` and `:state()` hold only for an element a script defined, and none runs in
   the file. So each element defined when it was drawn carries `data-lf-defined`,
   listing the custom states it held that the file's CSS names, and the file's CSS
   reads both from there, as it reads `::highlight()` from the spans. Without it a
   widget's stand-in for its loading time, such as the room `lf-tally` keeps
   (tally.css), would draw beside the widget. */
(() => {
  /** @type {Map<Element, ShadowRoot>} */
  const attached = new Map();
  const attachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (/** @type {ShadowRootInit} */ init) {
    const root = attachShadow.call(this, init);
    attached.set(this, root);
    return root;
  };

  // Every tree the page shows: the document and each shadow root under it, those the
  // parser attached from authored declarative markup included.
  function trees() {
    /** @type {(Document | ShadowRoot)[]} */
    const found = [document];
    for (const tree of found)
      for (const element of tree.querySelectorAll("*")) {
        const root = element.shadowRoot ?? attached.get(element);
        if (root) found.push(root);
      }
    return found;
  }

  // A <details> fires `toggle`, and a box takes its size, at the next rendering update,
  // so the page's readiness after it covers the work a step starts.
  const nextRendering = () =>
    new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve)));

  // Each fold as it stood when first seen, which `refold` puts back. A fold is seen
  // once, so a widget that closes one again doesn't send `unfold` round for ever, and
  // the state put back is the page's, wherever opening one fold closed another, as a
  // named <details> group does.
  /** @type {Map<Element, {open: boolean, hidden: string | null}>} */
  const folds = new Map();
  async function unfold() {
    let opened = 0;
    for (const tree of trees())
      for (const fold of tree.querySelectorAll('details, [hidden="until-found"]')) {
        if (folds.has(fold)) continue;
        const open = fold instanceof HTMLDetailsElement && fold.open;
        folds.set(fold, { open, hidden: fold.getAttribute("hidden") });
        if (fold instanceof HTMLDetailsElement && !open) {
          fold.open = true;
          opened++;
        }
        if (fold.getAttribute("hidden") === "until-found") {
          fold.removeAttribute("hidden");
          opened++;
        }
      }
    await nextRendering();
    return opened;
  }
  async function refold() {
    for (const [fold, { open, hidden }] of folds) {
      if (fold instanceof HTMLDetailsElement) fold.open = open;
      if (hidden === null) fold.removeAttribute("hidden");
      else fold.setAttribute("hidden", hidden);
    }
    await nextRendering();
  }

  const OBJECT_URL = /blob:[^\s"'()<>,#]+/g;
  const STATE = /:state\(\s*([\w-]+)\s*\)/g;
  /** @param {string} css */
  const withoutScript = (css) =>
    css
      .replace(/:defined\b/g, ":is(:defined, [data-lf-defined])")
      .replace(STATE, '[data-lf-defined~="$1"]')
      .replace(/::highlight\(\s*([\w-]+)\s*\)/g, ' [data-lf-highlight~="$1"]');
  /** @param {string} value */
  const quoted = (value) =>
    `"${value.replaceAll("&", "&amp;").replaceAll('"', "&quot;")}"`;

  // A custom highlight paints ranges no markup holds, such as a suggestion's changed
  // words (lf-suggestion.js) or a text document's syntax colour. Each range's text goes
  // into a span the file's CSS selects in place of `::highlight()`; a span is phrasing
  // content, so a suggestion's slot keeps its inline form (base.css).
  function markHighlights() {
    /** @type {Map<Text, {start: number, end: number, name: string}[]>} */
    const marks = new Map();
    for (const [name, highlight] of CSS.highlights)
      for (const painted of highlight) {
        const range = document.createRange();
        range.setStart(painted.startContainer, painted.startOffset);
        range.setEnd(painted.endContainer, painted.endOffset);
        const walker = document.createTreeWalker(
          range.commonAncestorContainer,
          NodeFilter.SHOW_TEXT,
        );
        /** @type {Node | null} */
        let node = walker.currentNode;
        for (; node; node = walker.nextNode()) {
          if (!(node instanceof Text) || !range.intersectsNode(node)) continue;
          const start = node === range.startContainer ? range.startOffset : 0;
          const end = node === range.endContainer ? range.endOffset : node.length;
          if (start < end)
            marks.set(node, [...(marks.get(node) ?? []), { start, end, name }]);
        }
      }
    for (const [text, held] of marks) {
      // Cut from the end, so each offset still counts from the node's start.
      const cuts = [...new Set(held.flatMap(({ start, end }) => [start, end]))]
        .filter((cut) => cut > 0 && cut < text.length)
        .sort((a, b) => b - a);
      /** @type {[number, Text][]} */
      const pieces = cuts.map((cut) => [cut, text.splitText(cut)]);
      pieces.push([0, text]);
      for (const [start, piece] of pieces) {
        const end = start + piece.length;
        const names = held
          .filter((mark) => mark.start <= start && end <= mark.end)
          .map(({ name }) => name);
        if (!names.length) continue;
        const span = document.createElement("span");
        span.dataset.lfHighlight = [...new Set(names)].join(" ");
        piece.replaceWith(span);
        span.append(piece);
      }
    }
  }

  // A canvas shows only what a script drew on it, so the file holds an image of those
  // pixels, its fallback content as the image's text. One holding another origin's
  // pixels can't be read, and stays a canvas showing its fallback content.
  /** @param {HTMLCanvasElement} canvas */
  function pictureCanvas(canvas) {
    let pixels;
    try {
      pixels = canvas.toDataURL();
    } catch {
      return;
    }
    const image = document.createElement("img");
    for (const { name, value } of canvas.attributes) image.setAttribute(name, value);
    image.alt = canvas.textContent.trim();
    image.src = pixels;
    canvas.replaceWith(image);
  }

  /** @param {Document | ShadowRoot} tree @param {CSSStyleSheet} sheet */
  function adoptedStyle(tree, sheet) {
    const style = document.createElement("style");
    if (sheet.media.mediaText) style.media = sheet.media.mediaText;
    style.textContent = Array.from(sheet.cssRules)
      .filter(
        (rule) =>
          !(
            rule instanceof CSSScopeRule &&
            rule.start &&
            !tree.querySelector(rule.start)
          ),
      )
      .map((rule) => rule.cssText)
      .join("\n");
    return style;
  }

  async function staticDocument() {
    for (const node of document.querySelectorAll(".lf-chrome, body [data-lf-runtime]"))
      node.remove();
    markHighlights();
    const shown = trees().filter(
      (tree) => !(tree instanceof ShadowRoot && tree.host.localName === "lf-age"),
    );
    for (const tree of shown) {
      for (const age of tree.querySelectorAll("lf-age")) {
        if (age.textContent.trim()) continue;
        const said = age.lfPreview?.("pointer");
        if (said && typeof said.name === "string") age.textContent = said.name;
      }
      for (const node of tree.querySelectorAll(
        "script, noscript, link[rel~=modulepreload]",
      ))
        node.remove();
      for (const media of tree.querySelectorAll("video, audio"))
        media.setAttribute("controls", "");
      for (const canvas of tree.querySelectorAll("canvas")) pictureCanvas(canvas);
      for (const input of tree.querySelectorAll("input"))
        if (input.type === "checkbox" || input.type === "radio")
          input.toggleAttribute("checked", input.checked);
        else if (input.type !== "file") input.setAttribute("value", input.value);
      for (const area of tree.querySelectorAll("textarea"))
        area.textContent = area.value;
      for (const option of tree.querySelectorAll("option"))
        option.toggleAttribute("selected", option.selected);
      const end = tree === document ? document.body : tree;
      for (const sheet of tree.adoptedStyleSheets)
        end.append(adoptedStyle(tree, sheet));
    }
    const html = document.documentElement;
    const roots = shown.filter((tree) => tree instanceof ShadowRoot);
    const serialize = () =>
      `<!doctype html><html${Array.from(
        html.attributes,
        ({ name, value }) => ` ${name}=${quoted(value)}`,
      ).join("")}>${html.getHTML({ shadowRoots: roots })}</html>`;

    /** @type {Map<string, Promise<Blob>>} */
    const bodies = new Map();
    /** @param {string} url */
    const body = (url) => {
      let read = bodies.get(url);
      if (!read) bodies.set(url, (read = fetch(url).then((answer) => answer.blob())));
      return read;
    };
    // The stylesheets object URLs hold, which the markup or another of them imports.
    /** @type {Map<string, string>} */
    const sheets = new Map();
    /** @type {(text: string) => Promise<unknown>} */
    const findSheets = (text) =>
      Promise.all(
        [...new Set(text.match(OBJECT_URL))].map(async (url) => {
          if (sheets.has(url)) return;
          const blob = await body(url);
          if (blob.type !== "text/css" || sheets.has(url)) return;
          const css = await blob.text();
          sheets.set(url, css);
          await findSheets(css);
        }),
      );
    await findSheets(serialize());

    const styles = shown.flatMap((tree) => [...tree.querySelectorAll("style")]);
    const states = new Set(
      [...styles.map((style) => style.textContent), ...sheets.values()].flatMap((css) =>
        Array.from(css.matchAll(STATE), ([, name]) => name),
      ),
    );
    for (const tree of shown)
      for (const element of tree.querySelectorAll("*")) {
        // Only a script answers an inline handler or a shortcut.
        for (const { name } of [...element.attributes])
          if (
            (name.startsWith("on") && name in element) ||
            name === "aria-keyshortcuts"
          )
            element.removeAttribute(name);
        if (
          (element.localName.includes("-") || element.hasAttribute("is")) &&
          element.matches(":defined")
        )
          element.setAttribute(
            "data-lf-defined",
            [...states].filter((name) => element.matches(`:state(${name})`)).join(" "),
          );
      }
    for (const style of styles) style.textContent = withoutScript(style.textContent);
    for (const [url, css] of sheets) sheets.set(url, withoutScript(css));

    /** @type {Map<string, Promise<string>>} */
    const dataUrls = new Map();
    /** @param {string} url */
    const dataUrl = (url) => {
      let written = dataUrls.get(url);
      if (!written)
        dataUrls.set(
          url,
          (written = (async () => {
            const blob = await body(url);
            const css = sheets.get(url);
            const bytes =
              css === undefined
                ? new Uint8Array(await blob.arrayBuffer())
                : new window.TextEncoder().encode(await inline(css));
            return `data:${blob.type};base64,${bytes.toBase64()}`;
          })()),
        );
      return written;
    };
    /** @param {string} text @returns {Promise<string>} */
    const inline = async (text) => {
      const urls = [...new Set(text.match(OBJECT_URL))];
      const written = new Map(
        await Promise.all(
          urls.map(async (url) => /** @type {const} */ ([url, await dataUrl(url)])),
        ),
      );
      return text.replace(OBJECT_URL, (url) => written.get(url) ?? url);
    };
    return inline(serialize());
  }
  Object.defineProperty(globalThis, "__leafStaticExport", {
    value: { unfold, refold, document: staticDocument },
  });
})();
