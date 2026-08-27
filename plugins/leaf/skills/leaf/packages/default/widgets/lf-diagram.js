/* lf-diagram: renders a mermaid-source body, upgraded because it parses. The body is
 * data, not prose — the theme shows it as source until the SVG replaces it, so a page
 * degrades readably if rendering fails (the source stays visible in the error box).
 * The vendored mermaid bundle loads lazily, once, and only on pages that use it. */
import { dataBody, once, failSoft, settle } from "/runtime/widget-api.js";

/* A diagram paints its own boxes, which makes it the one widget that can hold a
 * palette of its own — and it did: mermaid's stock "neutral" is a cool grey, so
 * every diagram sat on the page as a slab of a different theme. The tokens are the
 * page's answer to what a surface, a rule and a label look like, so the diagram
 * takes them too, read off the document rather than restated here. `base` is the
 * theme that accepts them; the named themes derive their own and ignore most of
 * what you pass. `darkMode` is the one thing the tokens can't say, because it tells
 * mermaid which way to derive the variables it wasn't given.
 *
 * The seeds are resolved once, at load — mermaid takes strings — and written back
 * as var() over the tokens they came from after each render (retheme), so the
 * drawn surfaces follow the tokens live: a scheme flip mid-read repaints them with
 * the rest of the page, and a copy exported in a light browser opens honestly for
 * a dark reader, where it used to stay a light slab inside a dark page. What stays
 * frozen is only what mermaid derives from the seeds itself (its lighten/darken
 * variants), which none of the principal surfaces are. */
const token = (name) => getComputedStyle(document.body).getPropertyValue(name).trim();

let mermaidReady;
let retheme = (svg) => svg;
const loadMermaid = () =>
  (mermaidReady ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "/vendor/mermaid.min.js";
    s.onload = () => {
      const seeds = {
        background: "--paper",
        mainBkg: "--card",
        primaryColor: "--card",
        primaryTextColor: "--ink",
        primaryBorderColor: "--border-2",
        secondaryColor: "--field",
        tertiaryColor: "--chip",
        lineColor: "--muted",
        textColor: "--ink",
        nodeBorder: "--border-2",
        clusterBkg: "--field",
        clusterBorder: "--rule",
        titleColor: "--ink",
        edgeLabelBackground: "--paper",
      };
      const values = Object.fromEntries(
        Object.entries(seeds).map(([key, name]) => [key, token(name)]),
      );
      globalThis.mermaid.initialize({
        startOnLoad: false,
        theme: "base",
        // A diagram's node labels are apparatus, so they take the apparatus face.
        fontFamily: token("--sans"),
        themeVariables: {
          darkMode: matchMedia("(prefers-color-scheme: dark)").matches,
          ...values,
        },
      });
      // value → its token, first declaration winning where two tokens resolve to
      // one value; matched in a single alternation pass, longest first, so a
      // substitution can never re-match inside another's written-back fallback.
      const byValue = new Map();
      for (const [key, name] of Object.entries(seeds))
        if (values[key] && !byValue.has(values[key])) byValue.set(values[key], name);
      byValue.set(token("--sans"), "--sans");
      const pattern = new RegExp(
        [...byValue.keys()]
          .sort((a, b) => b.length - a.length)
          .map((v) => v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
          .join("|"),
        "g",
      );
      // Only where the SVG states style — its <style> element and style=""
      // attributes — never its text: a node label quoting a palette value is the
      // page's words, and a blind pass rewrote one into `var(--paper, #faf9f5)`
      // on screen.
      const restate = (css) =>
        css.replace(pattern, (hit) => `var(${byValue.get(hit)}, ${hit})`);
      retheme = (svg) =>
        svg
          .replace(/<style[\s\S]*?<\/style>/g, restate)
          .replace(/style="[^"]*"/g, restate);
      resolve(globalThis.mermaid);
    };
    s.onerror = () => reject(new Error("couldn't load /vendor/mermaid.min.js"));
    document.head.append(s);
  }));

let seq = 0;
customElements.define(
  "lf-diagram",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.visualParts = new Map();
      // Registered with settle() so the runtime holds the view restore and the
      // first anchor pass until the SVG is in and the page's geometry is final.
      settle(this.render());
    }

    async render() {
      const source = dataBody(this).trim();
      const renderId = `lf-mermaid-${++seq}`;
      try {
        const mermaid = await loadMermaid();
        const declared = new Set(
          (this.getAttribute("parts") ?? "").trim().split(/\s+/).filter(Boolean),
        );
        const parsed = declared.size
          ? await mermaid.mermaidAPI.getDiagramFromText(source)
          : null;
        const { svg } = await mermaid.render(renderId, source);
        this.innerHTML = retheme(svg);
        // Mermaid sizes to fit: the svg is width 100%, capped at its natural size, so
        // a diagram wider than the column scales down whole, glyphs first — a
        // five-node flowchart arrived at 63% with its labels below legibility.
        // Legibility outranks fit: state the natural size and let the element's own
        // box scroll sideways (the theme's answer for a wide table or pre). The
        // viewBox is how every diagram type declares that size, so none is named.
        const drawn = this.querySelector("svg");
        const natural = drawn.viewBox.baseVal.width;
        if (natural) {
          drawn.setAttribute("width", natural);
          drawn.style.maxWidth = "";
        }
        this.visualParts.clear();
        if (parsed?.type === "flowchart-v2") {
          for (const node of parsed.db.getData().nodes ?? []) {
            const part = `node:${node.id}`;
            if (!declared.has(part)) continue;
            const element = drawn.querySelector(`#${CSS.escape(node.domId)}`);
            if (!element) continue;
            const label = element.textContent.replace(/\s+/g, " ").trim() || node.id;
            this.visualParts.set(part, { element, label });
          }
        }
        const missing = [...declared].filter((part) => !this.visualParts.has(part));
        if (missing.length)
          throw new Error(
            `commentable flowchart nodes not found: ${missing.join(", ")}`,
          );
        this.classList.add("lf-rendered");
      } catch (err) {
        // mermaid leaves its temp node (id "d" + renderId) in the body on failure.
        document.getElementById(`d${renderId}`)?.remove();
        failSoft(this, err, source);
      }
    }

    lfVisualPart(part) {
      return this.visualParts.get(part) ?? null;
    }

    lfVisualPartAt(target) {
      for (const [part, record] of this.visualParts)
        if (record.element === target || record.element.contains(target)) return part;
      return null;
    }
  },
);
