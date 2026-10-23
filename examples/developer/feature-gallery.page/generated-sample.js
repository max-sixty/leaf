// Exercise generated Leaf source through the same disposable-page host as templates.
import { keepsText, mountSample, quoted, whileConnected } from "/runtime/widget-api.js";

const section = document.getElementById("bg-generated-sample-section");
const create = section.querySelector("#bg-create-sample");
const remove = section.querySelector("#bg-remove-sample");
const status = section.querySelector("#bg-generated-sample-status");
const preview = section.querySelector("#bg-generated-sample-preview");
const source = `<!doctype html><html lang="en"><head><title>Generated delivery choice</title></head>
<body><main class="layout-column"><h1>Delivery</h1>
<lf-options id="delivery" choose>
  <lf-option id="standard">Standard delivery</lf-option>
  <lf-option id="express">Express delivery</lf-option>
</lf-options></main></body></html>`;

whileConnected(section, (signal) => {
  let host;
  create.disabled = false;
  remove.disabled = true;
  if (quoted(section)) return;
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
        const fit = ({ height }) => {
          frame.style.height = `${height}px`;
        };
        host.on("height", fit);
        fit(await host.ready);
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
