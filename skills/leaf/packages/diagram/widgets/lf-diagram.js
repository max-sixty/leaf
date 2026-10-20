/* Pele owns Mermaid parsing, semantic models, layout and SVG generation. Leaf
 * loads it only when a diagram draws, supplies local font metrics and live palette
 * roles, and registers Comment coordinates from the parsed model's named boxes.
 * Named boxes have one authored identity across a diagram, including containers;
 * ambiguous identities cannot supply a stable node:<id> Comment coordinate.
 * Rendering is inert: source callbacks never execute, links and images are disabled,
 * and Pele escapes labels and filters styles. A refused source remains visible with
 * its diagnostic; Leaf never salvages a diagram by dropping statements. */
import {
  bodyText,
  once,
  failSoft,
  registerVisualParts,
  widgetController,
} from "/runtime/widget-api.js";

let rendererReady;
const loadRenderer = () => (rendererReady ??= import("/vendor/pele.esm.js"));

/** Named boxes from Pele's semantic model, never reconstructed from source or labels. */
function namedParts(model, drawn) {
  const parts = new Map();
  const add = (id, selector, label) => {
    if (parts.has(id))
      throw new Error(`Diagram declares comment identity ${id} more than once`);
    parts.set(id, { id, selector, label });
  };
  switch (model.type) {
    case "flowchart": {
      // An edge to a subgraph also creates a node entry for the same box.
      const groups = new Set(model.subgraphs.map((group) => group.id));
      for (const id of model.nodes.keys()) if (!groups.has(id)) add(id, ".pele-node");
      for (const group of model.subgraphs) add(group.id, ".pele-cluster");
      break;
    }
    case "class":
      for (const id of model.classes.keys()) add(id, ".pele-class", id);
      // Pele draws implicit parent namespaces only in hierarchical mode. The
      // parsed model keeps those parents in either mode; its renderer owns which
      // become boxes, so read their presence from that render rather than repeat
      // its private configuration rules.
      for (const [id, namespace] of model.namespaces)
        if (
          namespace.explicit ||
          drawn.querySelector(`g.pele-namespace[data-id="${CSS.escape(id)}"]`)
        )
          add(id, ".pele-namespace", id);
      break;
    case "er":
      for (const id of model.entities.keys()) add(id, ".pele-entity", id);
      for (const group of model.subgraphs) add(group.id, ".pele-cluster");
      break;
    case "sequence":
      for (const id of model.actors.keys())
        add(id, ".pele-actor:not(.pele-actor-footer)");
      break;
    case "state": {
      // The top-level states map omits nested states. rootDoc contains every state
      // declaration and transition endpoint, and marks synthetic start/end states.
      const states = new Map();
      const visitState = (state) => {
        if (state.start === undefined && state.type !== "divider")
          states.set(state.id, state);
        if (state.doc) visit(state.doc);
      };
      const visit = (statements) => {
        for (const statement of statements) {
          if (statement.stmt === "state") visitState(statement);
          else if (statement.stmt === "relation") {
            visitState(statement.state1);
            visitState(statement.state2);
          }
        }
      };
      visit(model.rootDoc);
      for (const id of states.keys()) add(id, ":is(.pele-node,.pele-cluster)");
      break;
    }
  }
  return parts.values();
}

let seq = 0;
customElements.define(
  "lf-diagram",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.visualParts = new Map();
      this.visualPartRegistration = registerVisualParts(this, () =>
        [...this.visualParts].map(([id, part]) => ({ id, ...part })),
      );
      widgetController(this).present(this.render());
    }

    async render() {
      const source = bodyText(this);
      const renderId = `lf-diagram-${++seq}`;
      try {
        const [{ parse, render }] = await Promise.all([
          loadRenderer(),
          document.fonts.ready,
        ]);
        const style = getComputedStyle(this);
        const model = parse(source);
        const { svg } = render(model, {
          idPrefix: renderId,
          fontFamily: style.getPropertyValue("--sans").trim(),
          fontFamilyMono: style.getPropertyValue("--mono").trim(),
          fontSize: 14,
          responsive: false,
          links: false,
          images: false,
        });
        this.innerHTML = svg;
        const drawn = this.querySelector("svg");
        const parts = [...namedParts(model, drawn)];
        const visualParts = new Map();
        for (const part of parts) {
          const elements = drawn.querySelectorAll(
            `g${part.selector}[data-id="${CSS.escape(part.id)}"]`,
          );
          if (elements.length !== 1)
            throw new Error(`Pele did not draw one named box for ${part.id}`);
          const element = elements[0];
          const label =
            part.label || element.textContent.replace(/\s+/g, " ").trim() || part.id;
          visualParts.set(`node:${encodeURIComponent(part.id)}`, {
            element,
            label,
          });
        }
        this.visualParts = visualParts;
        this.classList.add("lf-rendered");
        this.visualPartRegistration.update();
      } catch (err) {
        failSoft(this, err, source);
      }
    }
  },
);
