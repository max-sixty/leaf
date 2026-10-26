// Render one agent-authored Adaptive Card with Microsoft's pinned JavaScript SDK.
// The output is self-contained so eval samples remain usable after the run ends.
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { Window } from "happy-dom";

const [sourcePath, outputPath] = process.argv.slice(2);
if (!sourcePath || !outputPath) {
  console.error("Usage: node adaptive-render.mjs <card.json> <index.html>");
  process.exit(2);
}

const require = createRequire(import.meta.url);
const sdkRoot = dirname(require.resolve("adaptivecards/package.json"));
const sdk = readFileSync(join(sdkRoot, "dist/adaptivecards.min.js"), "utf8");
const css = readFileSync(join(sdkRoot, "dist/adaptivecards.css"), "utf8");
const source = JSON.parse(readFileSync(sourcePath, "utf8"));
const window = new Window();
window.eval(sdk);
const AdaptiveCards = window.AdaptiveCards;
const context = new AdaptiveCards.SerializationContext();
const card = new AdaptiveCards.AdaptiveCard();
card.parse(source, context);
const events = [
  ...Array.from({ length: context.eventCount }, (_, index) =>
    context.getEventAt(index),
  ),
  ...card.validateProperties().validationEvents,
];
if (events.length > 0) {
  for (const event of events) console.error(event.message);
  process.exit(1);
}
if (!card.render()) {
  console.error("Adaptive Cards SDK did not render the card.");
  process.exit(1);
}

const json = JSON.stringify(source).replaceAll("<", "\\u003c");
const safeSdk = sdk.replaceAll(/<\/script/gi, "<\\/script");
const html = `<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Adaptive Card</title>
<style>
  body { margin: 0; padding: clamp(1rem, 4vw, 2.5rem); font-family: system-ui, sans-serif; color: #1b2533; background: #f5f7fa; }
  main { max-width: 56rem; margin-inline: auto; }
  #card { background: white; border: 1px solid #dce2e9; border-radius: .75rem; padding: clamp(1rem, 3vw, 2rem); }
  #eval-action-receipt { margin-block: 1rem; padding: 1rem; border: 1px solid #c3d8ca; border-radius: .5rem; background: #eff9f2; }
  #eval-action-receipt pre { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
<style>${css}</style>
<main>
  <div id="card"></div>
  <section id="eval-action-receipt" aria-live="polite" hidden>
    <strong>Recorded on this page</strong>
    <pre></pre>
  </section>
</main>
<script>${safeSdk}</script>
<script type="application/json" id="card-spec">${json}</script>
<script>
  const spec = JSON.parse(document.getElementById("card-spec").textContent);
  const card = new AdaptiveCards.AdaptiveCard();
  const context = new AdaptiveCards.SerializationContext();
  window.__evalActions = [];
  card.onExecuteAction = (action) => {
    const result = { type: action.getJsonTypeName(), title: action.title, data: action.data ?? {} };
    window.__evalActions.push(result);
    const receipt = document.getElementById("eval-action-receipt");
    receipt.querySelector("pre").textContent = JSON.stringify(result, null, 2);
    receipt.hidden = false;
  };
  card.parse(spec, context);
  const rendered = card.render();
  if (rendered) document.getElementById("card").appendChild(rendered);
  else document.getElementById("card").textContent = "Card rendering failed.";
</script>
</html>
`;
writeFileSync(outputPath, html);
