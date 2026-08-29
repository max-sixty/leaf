/* lf-toc: navigation derived from the headings the page already says.
 *
 * The generated labels are link apparatus rather than a second copy of the page's
 * words, so the nav wears .lf-ui. An authored heading keeps its own attributes. When one
 * has no id, a generated sibling supplies a native fragment target instead; that target
 * remains useful after export removes this module.
 *
 * The browser owns link activation and reveals a fragment inside a disclosure or a tab.
 * On an initial load the shared arrival pass runs after all widgets settle, so it can
 * honor a generated target that did not exist during HTML parsing. */
import { inChrome, once, relabel, wrote } from "/runtime/widget-api.js";

const HEADING_SELECTOR = "h2, h3, h4, h5, h6";

customElements.define(
  "lf-toc",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      const main = this.closest("main");
      if (!main) return;

      const headings = [...main.querySelectorAll(HEADING_SELECTOR)]
        .filter((heading) => !inChrome(heading) && !heading.closest("lf-toc"))
        .map((heading) => ({ heading, label: wrote(heading).trim() }))
        .filter(({ label }) => label);
      if (!headings.length) return;

      const nav = document.createElement("nav");
      nav.className = "lf-toc-nav lf-ui";
      nav.dataset.lfGen = "1";
      nav.setAttribute("aria-label", "On this page");

      const title = document.createElement("p");
      title.className = "lf-toc-title";
      relabel(title, "On this page", { says: true });
      const list = document.createElement("ol");
      const floor = Math.min(
        ...headings.map(({ heading }) => Number(heading.localName.slice(1))),
      );

      headings.forEach(({ heading, label }, index) => {
        const target = heading.id || this.#targetFor(heading, index + 1);
        const item = document.createElement("li");
        item.dataset.lfDepth = String(
          Math.min(Number(heading.localName.slice(1)) - floor, 4),
        );
        const link = document.createElement("a");
        link.href = `#${target}`;
        link.textContent = label;
        item.append(link);
        list.append(item);
      });

      nav.append(title, list);
      this.append(nav);
    }

    #targetFor(heading, position) {
      const stem = `lf-${this.id}-section-${position}`;
      let id = stem;
      let suffix = 2;
      while (document.getElementById(id)) id = `${stem}-${suffix++}`;

      const target = document.createElement("span");
      target.id = id;
      target.className = "lf-toc-target lf-ui";
      target.dataset.lfGen = "1";
      target.setAttribute("aria-hidden", "true");
      heading.before(target);
      return id;
    }
  },
);
