// The two arms share one request and host inference settings. Only the output
// contract changes: component configuration or complete HTML/CSS/JavaScript.
import {
  LeafElement,
  nothing,
  generate,
  highlightBlocks,
  keepsHidden,
  keepsText,
  publishOutput,
  quoted,
  tabStore,
  whileConnected,
} from "/runtime/widget-api.js";
import { stagePreview, stageLeafPreview } from "../preview.js";
import * as catalog from "../catalog.js";

const htmlInstructions = `Build a small, polished interactive widget for the user's request.

- Return \`html\` (body fragment), \`css\`, and \`js\` as strings.
- Use plain HTML, CSS and JavaScript: no libraries, network, external assets,
  imports, storage or Leaf elements. Scripts run after the fragment is inserted.
- Use real accessible controls with working behavior.
- Keep it compact and responsive down to 300px wide. Use a white background,
  warm dark text and one accent color.
- Let the content determine its height, without inner scroll areas or
  viewport-height layouts.

Produce the complete widget in one response.`;
const htmlSchema = {
  type: "object",
  properties: {
    html: { type: "string" },
    css: { type: "string" },
    js: { type: "string" },
  },
  required: ["html", "css", "js"],
  additionalProperties: false,
};
const approaches = {
  leaf: {
    instructions: catalog.instructions,
    schema: catalog.schema,
    stage: (container, value, failed) =>
      stageLeafPreview(container, catalog.compile(value), failed),
  },
  html: { instructions: htmlInstructions, schema: htmlSchema, stage: stagePreview },
};
customElements.define(
  "lf-widget-builder",
  class extends LeafElement {
    render() {
      return nothing;
    }
    setup() {
      const host = this;
      const field = host.querySelector("#widget-request");
      const button = host.querySelector("#widget-generate");
      const overall = host.querySelector("#widget-status");
      field.value = tabStore.get("dynamic-widgets:request") ?? field.value;

      if (!quoted(host))
        whileConnected(host, (signal) => {
          let busy = false;
          const lanes = Object.entries(approaches).map(([name, approach]) => {
            const region = host.querySelector(`[data-approach="${name}"]`);
            const get = (part) => region.querySelector(`[data-part="${part}"]`);
            const status = get("status"),
              clock = get("clock"),
              errorBox = get("error");
            const preview = get("preview"),
              empty = get("empty"),
              code = get("code"),
              request = get("request");
            publishOutput(get("instructions"), "document", approach.instructions);
            publishOutput(request, "document", "No generation yet.");
            let view = null,
              ticker;
            const showError = (error) => {
              keepsHidden(errorBox, false);
              keepsText(errorBox, error.message);
            };
            const draw = async (value) => {
              const staged = approach.stage(preview, value, (error) => {
                if (signal.aborted || view !== staged) return;
                view = null;
                staged.dispose();
                keepsHidden(empty, false);
                keepsText(status, "Widget error.");
                keepsText(overall, "A preview encountered an error.");
                showError(error);
              });
              view = staged;
              await staged.ready;
              if (signal.aborted) return;
              staged.frame.removeAttribute("data-staging");
              staged.frame.inert = false;
              staged.frame.removeAttribute("aria-hidden");
              keepsHidden(empty, true);
            };
            const metrics = (result) => {
              const time = result.timing;
              keepsText(
                status,
                `${result.value.limitation ? "Limited result" : "Preview ready"} in ${(time.totalMs / 1000).toFixed(1)} s`,
              );
              keepsText(
                get("metrics"),
                `${result.usage.outputTokens ?? "Unknown"} output tokens · ${(time.generationMs / 1000).toFixed(1)} s generation · ${(time.renderMs / 1000).toFixed(1)} s rendering · ${result.model}`,
              );
            };
            const run = async (input) => {
              view?.dispose();
              view = null;
              keepsHidden(empty, false);
              keepsHidden(errorBox, true);
              publishOutput(request, "document", input);
              for (const part of ["code", "css", "js"]) {
                const listing = get(part);
                if (!listing) continue;
                keepsText(listing, "No output yet.");
                delete listing.dataset.lfSyntax;
              }
              if (get("compiled")) keepsText(get("compiled"), "No source yet.");
              keepsText(get("metrics"), "");
              const started = performance.now();
              keepsText(status, "Generating…");
              keepsText(clock, "0.0 s");
              ticker = setInterval(() => {
                keepsText(
                  clock,
                  `${((performance.now() - started) / 1000).toFixed(1)} s`,
                );
              }, 100);
              try {
                const result = await generate({
                  input,
                  instructions: approach.instructions,
                  schema: approach.schema,
                });
                if (signal.aborted) return;
                const generated = performance.now();
                keepsText(status, "Rendering…");
                const record = {
                  ...result,
                  timing: {
                    generationMs: generated - started,
                    renderMs: 0,
                    totalMs: 0,
                  },
                };
                keepsText(
                  code,
                  name === "html"
                    ? result.value.html
                    : JSON.stringify(result.value, null, 2),
                );
                for (const part of ["css", "js"])
                  if (get(part)) keepsText(get(part), result.value[part]);
                if (get("compiled")) {
                  keepsText(get("compiled"), catalog.compile(result.value));
                  delete get("compiled").dataset.lfSyntax;
                }
                void highlightBlocks(region);
                await draw(result.value);
                if (signal.aborted) return;
                record.timing.renderMs = performance.now() - generated;
                record.timing.totalMs = performance.now() - started;
                metrics(record);
              } catch (error) {
                if (!signal.aborted) {
                  keepsText(
                    status,
                    `Failed after ${((performance.now() - started) / 1000).toFixed(1)} s`,
                  );
                  const failed = view;
                  view = null;
                  failed?.dispose();
                  keepsHidden(empty, false);
                  showError(error);
                }
              } finally {
                clearInterval(ticker);
                if (!signal.aborted) keepsText(clock, "");
              }
            };
            return {
              run,
              dispose() {
                clearInterval(ticker);
                view?.dispose();
                view = null;
              },
            };
          });
          field.addEventListener(
            "input",
            () => tabStore.set("dynamic-widgets:request", field.value),
            { signal },
          );
          host.querySelector("form").addEventListener(
            "submit",
            async (event) => {
              event.preventDefault();
              if (busy || !field.value.trim()) return;
              busy = true;
              button.disabled = true;
              const input = field.value.trim();
              keepsText(overall, "Comparing the same request…");
              try {
                await Promise.all(lanes.map((lane) => lane.run(input)));
                if (!signal.aborted) keepsText(overall, "Comparison finished.");
              } finally {
                busy = false;
                if (!signal.aborted) button.disabled = false;
              }
            },
            { signal },
          );
          return () => lanes.forEach((lane) => lane.dispose());
        });
    }
  },
);
