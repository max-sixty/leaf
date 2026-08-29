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

/* Which boxes an author may name, per Mermaid type: the id written in the source and
 * the id the renderer draws it under. A type belongs here when the author's id
 * reaches the drawing inside an id of Mermaid's own making, because only then is
 * `node:Queued` still the same box after a re-render, and after an edit that inserts
 * three boxes above it.
 *
 * The absences are not a shortlist. A sequence diagram gives a message — the thing
 * an author wants to point at in one — no coordinate at all, and journey, timeline,
 * mindmap and pie carry none anywhere. Gantt tasks look addressable and are not:
 * mermaid keeps one gantt db for the whole page, so a second gantt on it overwrites
 * the first's reading before the first has drawn, and it mints `task1`, `task2` for
 * the tasks an author left unnamed — a token that names the third bar today and the
 * fourth after an insertion.
 */
// A box that holds other boxes — a flowchart subgraph, a composite state — is drawn
// under the author's id itself, where a plain node is drawn under mermaid's. Its
// `domId` is null or names a box the renderer never draws, so asking by node kind is
// the whole of it. Mermaid draws the containers in a layer of their own rather than
// around what they hold, so a container is pointed at where it paints — its frame and
// its title — while the boxes inside it answer for themselves.
const graphBoxes = (db) =>
  db.getData().nodes.map((n) => [n.id, n.isGroup ? n.id : n.domId]);
const PART_SOURCES = {
  "flowchart-v2": { source: "flowchart", boxes: graphBoxes },
  stateDiagram: { source: "stateDiagram-v2", boxes: graphBoxes },
  er: {
    // The third member is a label, and only a type whose box says more than its own
    // name owes one: an entity's box is a table of attribute rows, where a node's box
    // is its label and nothing else. The source's word for a node is the label before
    // mermaid renders it, markdown, entities and all, so reading it back off the
    // drawing is what keeps the thread quoting what the reader can see.
    source: "erDiagram",
    boxes: (db) =>
      [...db.getEntities()].map(([name, e]) => [name, e.id, e.alias || name]),
  },
};
const PART_TYPES = Object.values(PART_SOURCES)
  .map((entry) => entry.source)
  .join(", ");

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
        const addressable = parsed && PART_SOURCES[parsed.type];
        const boxes = addressable ? addressable.boxes(parsed.db) : [];
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
        for (const [id, drawnId, name] of boxes) {
          const part = `node:${id}`;
          if (!declared.has(part)) continue;
          const element = drawn.querySelector(`#${CSS.escape(drawnId)}`);
          if (!element) continue;
          const says = element.textContent.replace(/\s+/g, " ").trim();
          this.visualParts.set(part, { element, label: name ?? (says || id) });
        }
        const missing = [...declared].filter((part) => !this.visualParts.has(part));
        if (missing.length)
          throw new Error(
            addressable
              ? `commentable ${addressable.source} boxes not found: ${missing.join(", ")}`
              : `a ${parsed.type} diagram draws its boxes under ids Mermaid mints, ` +
                  `so parts cannot name one. Only these types carry the ids you ` +
                  `write: ${PART_TYPES}. Drop parts to comment on the whole drawing.`,
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
