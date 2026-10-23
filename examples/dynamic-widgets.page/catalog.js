// Model output selects installed components; this compiler owns their markup and IDs.
// The generation endpoint validates the schema, and sample admission checks Leaf HTML.
const text = { type: "string" };
const array = (items) => ({ type: "array", items });
const object = (properties) => ({
  type: "object",
  properties,
  required: Object.keys(properties),
  additionalProperties: false,
});
const component = { $ref: "#/$defs/component" };
const kind = (name, properties) => object({ type: { const: name }, ...properties });

export const schema = {
  ...object({ components: array(component), limitation: { type: ["string", "null"] } }),
  $defs: {
    component: {
      anyOf: [
        kind("text", { style: { enum: ["heading", "subheading", "paragraph"] }, text }),
        kind("table", { headers: array(text), rows: array(array(text)) }),
        kind("options", { items: array(text) }),
        kind("tabs", {
          tabs: array(object({ label: text, components: array(component) })),
        }),
        kind("board", {
          columns: array(
            object({ label: text, cards: array(object({ title: text, text })) }),
          ),
        }),
        kind("draft", { text }),
        kind("chart", {
          label: text,
          xLabel: text,
          yLabel: text,
          rows: array(object({ category: text, value: { type: "number" } })),
        }),
      ],
    },
  },
};

export const instructions = `Compose a useful interface for the user's goal from this installed Leaf catalog.
Choose the organization, wording and components; preserve the user's facts.

Return \`components\` and \`limitation\` (\`null\` when the catalog meets the request).

#### Available components

- **Text:** headings, subheadings and paragraphs.
  \`text {type:"text", style: "heading" | "subheading" | "paragraph", text}\`
- **Table:** a static comparison.
  \`table {type:"table", headers:[string], rows:[[string]]}\`
- **Options:** record one mutually exclusive choice, with Undo.
  \`options {type:"options", items:[string]}\`
- **Tabs:** switch between sections.
  \`tabs {type:"tabs", tabs:[{label, components:[...]}]}\`
- **Board:** move cards between columns.
  \`board {type:"board", columns:[{label, cards:[{title, text}]}]}\`
- **Draft:** edit Markdown and save it, with Undo.
  \`draft {type:"draft", text}\`
- **Chart:** a static labeled bar chart.
  \`chart {type:"chart", label, xLabel, yLabel, rows:[{category, value}]}\`

All fields are required. Text is literal except draft text, which is Markdown.
IDs and markup are supplied by the compiler.

#### Limits

These components do not add new behavior or connect to each other: choosing an
option does not update a chart or draft. They cannot run timers, calculations,
network requests or custom controls.

When the request needs unavailable behavior, explain the missing capability in
\`limitation\` and offer only a useful partial result; use an empty \`components\`
array if none helps. Never present a text description of a control as working behavior.`;

const escape = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

export function compile(spec) {
  if (!spec.components.length && !spec.limitation?.trim())
    throw new Error("The catalog returned neither a widget nor a limitation.");
  let sequence = 0;
  const element = (tag, body, attrs = {}) => {
    const attributes = Object.entries(attrs)
      .map(([name, value]) =>
        value === true ? ` ${name}` : ` ${name}="${escape(value)}"`,
      )
      .join("");
    return `<${tag} id="generated-${++sequence}"${attributes}>${body}</${tag}>`;
  };
  const render = (node) => {
    switch (node.type) {
      case "text":
        return element(
          { heading: "h2", subheading: "h3", paragraph: "p" }[node.style],
          escape(node.text),
        );
      case "table":
        return element(
          "table",
          `<thead><tr>${node.headers.map((value) => `<th scope="col">${escape(value)}</th>`).join("")}</tr></thead><tbody>${node.rows.map((row) => `<tr>${row.map((value) => `<td>${escape(value)}</td>`).join("")}</tr>`).join("")}</tbody>`,
        );
      case "options":
        return element(
          "lf-options",
          node.items.map((value) => element("lf-option", escape(value))).join(""),
          { choose: true },
        );
      case "tabs":
        return element(
          "lf-tabs",
          node.tabs
            .map((tab) =>
              element("lf-tab", tab.components.map(render).join(""), {
                label: tab.label,
              }),
            )
            .join(""),
        );
      case "board":
        return element(
          "lf-board",
          node.columns
            .map((column) =>
              element(
                "lf-column",
                column.cards
                  .map((card) =>
                    element(
                      "lf-card",
                      `<strong>${escape(card.title)}</strong><p>${escape(card.text)}</p>`,
                    ),
                  )
                  .join(""),
                { label: column.label },
              ),
            )
            .join(""),
        );
      case "draft":
        return element("lf-draft", `<pre>\n${escape(node.text)}</pre>`);
      case "chart": {
        const rows = JSON.stringify(node.rows);
        const options = `{ariaLabel:${JSON.stringify(node.label)},x:{label:${JSON.stringify(node.xLabel)}},y:{grid:true,label:${JSON.stringify(node.yLabel)}},marks:[Plot.barY(${rows},{x:"category",y:"value",fill:"var(--series-1)"}),Plot.text(${rows},{x:"category",y:"value",text:"value",dy:-10})]}`;
        return element("lf-chart", `<pre>\n${escape(options)}</pre>`);
      }
      default:
        throw new Error(`Unknown component: ${node.type}`);
    }
  };
  const limitation = spec.limitation
    ? element("p", `<strong>Catalog limitation:</strong> ${escape(spec.limitation)}`)
    : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Generated Leaf widget</title></head><body><main>${limitation}${spec.components.map(render).join("\n")}</main></body></html>`;
}
