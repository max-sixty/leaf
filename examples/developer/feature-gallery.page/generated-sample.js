// Exercise generated Leaf source through the same disposable-page host as templates.
import { mountSample, whileConnected } from "/runtime/widget-api.js";
import { keepsText } from "/runtime/lib/keeps.js";

const section = document.getElementById("bg-generated-sample-section");
const create = section.querySelector("#bg-create-sample");
const remove = section.querySelector("#bg-remove-sample");
const status = section.querySelector("#bg-generated-sample-status");
const preview = section.querySelector("#bg-generated-sample-preview");
const source = `<!doctype html><html lang="en"><head><title>Generated delivery choice</title></head>
<body><main class="layout-column"><h1>Delivery</h1>
<lf-group id="delivery-ask" label="Which delivery?">
<h2>Which delivery?</h2>
<lf-options id="delivery">
  <lf-option id="standard">Standard delivery</lf-option>
  <lf-option id="express">Express delivery</lf-option>
</lf-options></lf-group></main></body></html>`;

whileConnected(section, (signal) => {
  let host;
  create.toggleAttribute("disabled", false);
  remove.toggleAttribute("disabled", true);
  if (section.matches("[data-lf-exhibit] *")) return;
  create.addEventListener(
    "click",
    async () => {
      create.disabled = true;
      keepsText(status, "Opening sample…");
      const frame = document.createElement("iframe");
      frame.title = "Generated delivery choice";
      frame.style.cssText = "display:block;width:100%;border:0";
      preview.append(frame);
      try {
        host = await mountSample(frame, { source });
        if (signal.aborted) {
          await host.destroy();
          return;
        }
        await host.ready;
        keepsText(status, "Choose a delivery in the sample.");
        remove.disabled = false;
      } catch (error) {
        frame.remove();
        if (!signal.aborted) {
          keepsText(status, error.message);
          create.disabled = false;
        }
      }
    },
    { signal },
  );
  remove.addEventListener(
    "click",
    async () => {
      remove.disabled = true;
      try {
        await host.destroy();
        preview.replaceChildren();
        keepsText(status, "Sample removed.");
        create.disabled = false;
      } catch (error) {
        keepsText(status, error.message);
      }
    },
    { signal },
  );
  return () => {
    void host?.destroy().catch(reportError);
    preview.replaceChildren();
  };
});
