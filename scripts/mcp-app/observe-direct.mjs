import fs from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";

const [pageDir, results] = process.argv.slice(2);
const events = async () =>
  (await fs.readFile(path.join(pageDir, "comments.jsonl"), "utf8"))
    .trim()
    .split("\n")
    .filter(Boolean)
    .map(JSON.parse);
const startingEvents = await events();
assert.equal(
  startingEvents.filter((event) => ["action", "comment"].includes(event.kind)).length,
  0,
  "Use a fresh reader fixture",
);
const startingIds = new Set(startingEvents.map((event) => event.id));
const newEvent = async (predicate) => {
  for (let tries = 0; tries < 100; tries++) {
    const found = (await events()).find(
      (event) => !startingIds.has(event.id) && predicate(event),
    );
    if (found) return found;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("No new matching durable event");
};
const require = createRequire(import.meta.url);
const repo = path.resolve(new URL(import.meta.url).pathname, "../../..");
const playwrightPackage = execFileSync(
  path.join(repo, ".venv/bin/python"),
  [
    "-c",
    "from pathlib import Path; import playwright; print(Path(playwright.__file__).parent / 'driver' / 'package')",
  ],
  { encoding: "utf8" },
).trim();
const { chromium } = require(playwrightPackage);
const browser = await chromium.launch({
  ...(process.env.LEAF_BROWSER_EXECUTABLE
    ? { executablePath: process.env.LEAF_BROWSER_EXECUTABLE }
    : { channel: "chrome" }),
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  page.setDefaultTimeout(30_000);
  const errors = [];
  page.on("pageerror", (error) => errors.push({ text: String(error) }));
  page.on("console", (message) => {
    if (message.type() === "error")
      errors.push({ text: message.text(), url: message.location().url });
  });
  await page.goto("http://localhost:8080/?tool=leaf_direct_present");
  await page.waitForFunction(
    () => document.querySelectorAll("select")[1]?.value === "leaf_direct_present",
  );
  await page.locator("textarea").fill("{}");
  await page.getByRole("button", { name: "Call Tool" }).click();
  const app = page.frameLocator("iframe").frameLocator("iframe");
  await app.locator('body[data-lf-presented="1"]').waitFor();
  assert.equal(await app.locator("iframe").count(), 0);
  assert.equal(
    await app.getByRole("heading", { name: "Where sessions live" }).isVisible(),
    true,
  );
  assert.equal(await app.locator(".lf-banner").isVisible(), true);
  await page
    .locator("iframe")
    .screenshot({ path: path.join(results, "direct-leaf.png") });
  const choice = app.locator("#opt-redis").getByRole("checkbox");
  await choice.focus();
  await choice.press("Space");
  await app.locator("#opt-redis[chosen]").waitFor();
  const action = await newEvent(
    (event) => event.kind === "action" && event.widget === "session-options",
  );
  assert.equal(action.kind, "action");
  assert.equal(action.widget, "session-options");
  await app.locator("#decision-lede").evaluate((element) => {
    const range = document.createRange();
    range.selectNodeContents(element);
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    element.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  const commentText = `Comment delivered directly through MCP tools: ${randomUUID()}`;
  await app.locator(".lf-fab-input").fill(commentText);
  await app.locator(".lf-fab-input").press("Enter");
  const comment = await newEvent(
    (event) => event.kind === "comment" && event.text === commentText,
  );
  assert.equal(comment.kind, "comment");
  assert.ok(comment.anchor.quote);
  // Disk append precedes the submit continuation. Wait for the new inline reply
  // to receive focus before opening the overview that continuation would close.
  await app
    .locator(
      `.lf-margin-thread .lf-conversation-thread[data-thread="${comment.id}"] textarea:focus`,
    )
    .waitFor();
  const threadsToggle = app.getByRole("button", { name: /^Threads/ });
  if ((await threadsToggle.getAttribute("aria-expanded")) !== "true")
    await threadsToggle.click();
  const commentNode = app
    .locator(".lf-threads")
    .getByText(commentText, { exact: true });
  try {
    await commentNode.waitFor();
  } catch (error) {
    await fs.writeFile(
      path.join(results, "hidden-comment.json"),
      JSON.stringify(
        await commentNode.evaluate((node) => {
          const parents = [];
          for (let el = node; el; el = el.parentElement) {
            const style = getComputedStyle(el);
            parents.push({
              tag: el.tagName,
              id: el.id,
              classes: el.className,
              hidden: el.hidden,
              display: style.display,
              visibility: style.visibility,
              rect: el.getBoundingClientRect().toJSON(),
            });
          }
          return {
            parents,
            body: document.body.className,
            toggle: document.querySelector(".lf-threads-toggle")?.outerHTML,
          };
        }),
        null,
        2,
      ),
    );
    await page.screenshot({ path: path.join(results, "failure.png"), fullPage: true });
    throw error;
  }
  await page
    .locator("iframe")
    .screenshot({ path: path.join(results, "direct-comment.png") });
  await app.getByRole("button", { name: "Close threads" }).click();
  await app.getByRole("button", { name: "Test Codex follow-up" }).press("Enter");
  await app.getByRole("status").filter({ hasText: "ui/message accepted" }).waitFor();
  const csp = JSON.parse(new URL(page.frames()[1].url()).searchParams.get("csp"));
  assert.equal(csp.connectDomains?.length || 0, 0);
  assert.equal(csp.frameDomains?.length || 0, 0);
  const requests = await page
    .frames()
    .at(-1)
    .evaluate(() =>
      performance.getEntriesByType("resource").map((entry) => entry.name),
    );
  assert.deepEqual(
    requests.filter((url) => !url.startsWith("data:")),
    [],
  );
  const appErrors = errors.filter(
    (error) => error.url !== "http://localhost:8080/favicon.ico",
  );
  assert.deepEqual(appErrors, []);
  console.log(
    JSON.stringify(
      {
        presented: true,
        leafChildFrames: 0,
        csp,
        networkRequests: requests.filter((url) => !url.startsWith("data:")),
        inlineDataResources: requests.filter((url) => url.startsWith("data:")).length,
        action,
        comment,
        uiMessageAccepted: true,
        idleCodexWakeTested: false,
        errors: appErrors,
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
