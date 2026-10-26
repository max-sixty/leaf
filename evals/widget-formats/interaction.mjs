// Operate the retained choice and form cases in their served browser page.
// Report uncertainty explicitly when an authored control cannot be identified.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

const [caseName, url, evidencePath] = process.argv.slice(2);
if (!caseName || !url || !evidencePath) {
  console.error("Usage: node interaction.mjs <choice|form> <url> <evidence-dir>");
  process.exit(2);
}
mkdirSync(evidencePath, { recursive: true });
const observations = [];
let browser;
let status = "insufficient_evidence";
let reason = "The browser probe did not complete.";

async function visible(locator) {
  for (const item of await locator.all()) if (await item.isVisible()) return item;
  return null;
}

async function option(page, name) {
  for (const role of ["checkbox", "radio", "button"]) {
    const control = await visible(page.getByRole(role, { name }));
    if (control) return { role, control };
  }
  return null;
}

async function active(control) {
  return control
    .getAttribute("aria-checked")
    .then((value) => (value === null ? control.isChecked() : value === "true"));
}

async function selectionAfter(choices, expected) {
  let current = [];
  const deadline = Date.now() + 2000;
  do {
    current = await Promise.all(choices.map(({ control }) => active(control)));
    if (current.join() === expected.join()) break;
    await new Promise((resolve) => setTimeout(resolve, 30));
  } while (Date.now() < deadline);
  return current;
}

async function receipts(page) {
  return page.evaluate(() =>
    Array.from(
      document.querySelectorAll(
        "#eval-action-receipt, main output, main [role='status'], main [aria-live]",
      ),
    )
      .filter(
        (element) =>
          !element.hidden &&
          element.checkVisibility({ checkVisibilityCSS: true }) &&
          !element.querySelector(
            "input, textarea, select, [role='radio'], [role='textbox']",
          ),
      )
      .map((element) => ({
        text: element.innerText.replace(/\s+/g, " ").trim(),
        id: element.id || element.tagName.toLowerCase(),
      })),
  );
}

async function choice(page) {
  const choices = [
    await option(page, /Resume EU now/i),
    await option(page, /Hold EU until/i),
    await option(page, /Roll back EU/i),
  ];
  if (choices.some((entry) => !entry)) {
    return [
      "insufficient_evidence",
      "Could not identify all three visible choice controls.",
    ];
  }
  observations.push({ controls: choices.map(({ role }) => role) });
  const roles = new Set(choices.map(({ role }) => role));
  if (roles.size !== 1) {
    return ["insufficient_evidence", "The three choices use mixed control roles."];
  }
  const role = choices[0].role;
  if (role === "checkbox" || role === "radio") {
    await choices[1].control.click();
    const hold = await selectionAfter(choices, [false, true, false]);
    observations.push({ afterHold: hold });
    await page.screenshot({
      path: join(evidencePath, "after-hold.png"),
      fullPage: true,
    });
    await choices[2].control.click();
    const rollback = await selectionAfter(choices, [false, false, true]);
    observations.push({ afterRollback: rollback });
    await page.screenshot({
      path: join(evidencePath, "after-rollback.png"),
      fullPage: true,
    });
    return hold.join() === "false,true,false" && rollback.join() === "false,false,true"
      ? [
          "proven",
          "Browser selection moved from Hold to Roll back, one choice at a time.",
        ]
      : [
          "defect",
          "The operated controls did not leave exactly the selected choice active.",
        ];
  }
  // Adaptive Cards submits each option through the local host action handler.
  if (!(await page.locator("#eval-action-receipt").count())) {
    return ["insufficient_evidence", "Buttons have no known current-choice reading."];
  }
  await choices[1].control.click();
  await page
    .waitForFunction(() => window.__evalActions?.length >= 1, null, { timeout: 2000 })
    .catch(() => {});
  const hold = await page.evaluate(() => ({
    actions: window.__evalActions,
    receipt: document.querySelector("#eval-action-receipt")?.innerText ?? "",
  }));
  observations.push({ afterHold: hold });
  await page.screenshot({ path: join(evidencePath, "after-hold.png"), fullPage: true });
  await choices[2].control.click();
  await page
    .waitForFunction(() => window.__evalActions?.length >= 2, null, { timeout: 2000 })
    .catch(() => {});
  const rollback = await page.evaluate(() => ({
    actions: window.__evalActions,
    receipt: document.querySelector("#eval-action-receipt")?.innerText ?? "",
  }));
  observations.push({ afterRollback: rollback });
  await page.screenshot({
    path: join(evidencePath, "after-rollback.png"),
    fullPage: true,
  });
  const chosen = (snapshot) =>
    JSON.stringify(snapshot.actions?.at(-1) ?? {}) + snapshot.receipt;
  return hold.actions?.length === 1 &&
    rollback.actions?.length === 2 &&
    /hold/i.test(chosen(hold)) &&
    /roll.?back/i.test(chosen(rollback)) &&
    !/hold/i.test(rollback.receipt)
    ? [
        "proven",
        "Both SDK actions ran, and the visible local receipt shows the latest choice.",
      ]
    : ["defect", "The operated buttons did not record and show the current choice."];
}

async function form(page) {
  const title = await visible(page.getByRole("textbox", { name: /title/i }));
  const impact = await visible(page.getByRole("textbox", { name: /customer impact/i }));
  if (!title || !impact) {
    return [
      "insufficient_evidence",
      "Could not identify labeled title and impact fields.",
    ];
  }
  const titleValue = "Atlas search review probe";
  const impactValue = "37 EU workspaces saw stale search results";
  await title.fill(titleValue);
  await impact.fill(impactValue);
  const high = await visible(page.getByRole("radio", { name: /^High$/i }));
  const severity = await visible(page.getByRole("combobox", { name: /severity/i }));
  if (high) await high.check();
  else if (severity) {
    if (await severity.evaluate((element) => element.tagName === "SELECT")) {
      await severity.selectOption({ label: "High" });
    } else {
      await severity.click();
      const highOption = await visible(page.getByRole("option", { name: /^High$/i }));
      if (!highOption)
        return ["insufficient_evidence", "Could not select High severity."];
      await highOption.click();
    }
  } else return ["insufficient_evidence", "Could not identify the severity control."];
  const submit = await visible(
    page.locator("main").getByRole("button", {
      name: /submit|record|save|finish|create/i,
    }),
  );
  if (!submit)
    return ["insufficient_evidence", "Could not identify a visible submit control."];
  observations.push({
    filled: { title: titleValue, severity: "High", impact: impactValue },
  });
  await page.screenshot({ path: join(evidencePath, "filled.png"), fullPage: true });
  const before = await receipts(page);
  await submit.click();
  let after = [];
  const deadline = Date.now() + 2000;
  do {
    after = await receipts(page);
    if (
      after.some(
        ({ text }) =>
          text.includes(titleValue) &&
          text.includes(impactValue) &&
          /\bhigh\b/i.test(text) &&
          !before.some((entry) => entry.text === text),
      )
    )
      break;
    await new Promise((resolve) => setTimeout(resolve, 30));
  } while (Date.now() < deadline);
  await page.screenshot({
    path: join(evidencePath, "after-submit.png"),
    fullPage: true,
  });
  const actions = await page.evaluate(() => window.__evalActions ?? null);
  observations.push({ beforeReceipts: before, afterReceipts: after, actions });
  if (actions && actions.length !== 1) {
    return ["defect", "The SDK did not record one submit action."];
  }
  const changed = after.filter(
    ({ text }) => !before.some((entry) => entry.text === text),
  );
  if (
    changed.some(
      ({ text }) =>
        text.includes(titleValue) &&
        text.includes(impactValue) &&
        /\bhigh\b/i.test(text),
    )
  )
    return [
      "proven",
      "A new visible receipt contains the submitted title, severity and impact.",
    ];
  return changed.length
    ? ["defect", "A visible receipt changed, but did not contain all submitted values."]
    : [
        "insufficient_evidence",
        "No distinct visible submission receipt could be identified.",
      ];
}

try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 900, height: 760 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto(url, { waitUntil: "load" });
  if (await page.locator("script[data-lf-entry]").count()) {
    await page.waitForFunction(
      () =>
        document
          .querySelector("script[data-lf-entry]")
          ?.lfReadiness?.(null, "rendering") === null,
      null,
      { timeout: 10000 },
    );
  } else if (await page.locator("#card").count()) {
    await page
      .locator("#card > *")
      .first()
      .waitFor({ state: "visible", timeout: 10000 });
  }
  await page.screenshot({ path: join(evidencePath, "before.png"), fullPage: true });
  [status, reason] = caseName.endsWith("choice")
    ? await choice(page)
    : caseName.endsWith("form")
      ? await form(page)
      : ["insufficient_evidence", `No interaction probe for ${caseName}.`];
  if (errors.length) observations.push({ pageErrors: errors });
} catch (error) {
  observations.push({ probeError: String(error) });
  reason = `Browser probe could not finish: ${error.message ?? error}`;
} finally {
  await browser?.close();
}
const result = { status, reason, observations };
writeFileSync(join(evidencePath, "interaction.json"), JSON.stringify(result, null, 2));
process.stdout.write(JSON.stringify(result) + "\n");
