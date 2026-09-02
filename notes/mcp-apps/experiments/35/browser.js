// Replay these steps through the browser tool, not a standalone Playwright
// process. Read that tool's current browser instructions before setup. Supply
// the preview's exact URL and reuse its existing tab as `leafTab`.

// Keyboard package action, followed by its visible selected state.
await leafTab.playwright
  .getByRole("checkbox", {
    name: "choose one: Request another pass — hold the patch for a native fix. — option 2 of 2",
    exact: true,
  })
  .press("Space");
nodeRepl.write(await leafTab.playwright.domSnapshot());

// The ordinary panel contains the fixture's frozen multi-select thread widget.
await leafTab.playwright
  .getByRole("button", {
    name: "Threads (2)",
    exact: true,
  })
  .click();
nodeRepl.write(await leafTab.playwright.domSnapshot());
await leafTab.playwright
  .getByRole("button", {
    name: "Close threads",
    exact: true,
  })
  .click();

// The first locator double-click selected whitespace at the heading's center.
// Inspect the screenshot before selecting text; these coordinates apply only
// to the observed 706 x 998 viewport and must not be reused blindly.
await leafTab.playwright
  .getByRole("heading", {
    name: "The iOS reconnect stall",
    exact: true,
  })
  .dblclick();
nodeRepl.write(
  await leafTab.playwright.evaluate(() => ({
    selection: window.getSelection()?.toString(),
    body: document.body.dataset,
  })),
);
await nodeRepl.emitImage(await leafTab.screenshot({ fullPage: false }));
await leafTab.cua.double_click({ x: 153, y: 205 });
nodeRepl.write(await leafTab.playwright.domSnapshot());

// Real anchored comment, not a direct event POST.
await leafTab.playwright
  .getByRole("textbox", {
    name: "Comment on “reconnect”",
    exact: true,
  })
  .fill(
    "Codex full-runtime smoke: please confirm this anchored comment arrived, then add a test-result note without changing the review decision.",
  );
await leafTab.playwright
  .getByRole("textbox", {
    name: "Comment on “reconnect”",
    exact: true,
  })
  .press("Enter");
// The send is asynchronous; check the final fact in a later observation.
nodeRepl.write(await leafTab.playwright.domSnapshot());
nodeRepl.write(await leafTab.dev.logs({ levels: ["error", "warn"], limit: 20 }));

// After the delivered action was carried into the source and stamped v2:
nodeRepl.write(
  await leafTab.playwright
    .getByText("Codex interaction check:", {
      exact: false,
    })
    .innerText(),
);
await leafTab.reload();
await leafTab.playwright.locator('body[data-lf-presented="1"]').waitFor({
  state: "visible",
  timeoutMs: 10000,
});
nodeRepl.write(
  await leafTab.playwright
    .getByRole("checkbox", {
      name: "selected: Request another pass — hold the patch for a native fix. — option 2 of 2",
      exact: true,
    })
    .getAttribute("aria-checked"),
);
await leafTab.playwright
  .getByRole("button", {
    name: "v2: open versions",
    exact: true,
  })
  .click();
await leafTab.playwright
  .getByRole("menuitem", {
    name: "v1 ship-review.html, as it stands in the tree",
    exact: true,
  })
  .click();
await leafTab.playwright.locator('body[data-lf-presented="1"]').waitFor({
  state: "visible",
  timeoutMs: 10000,
});
nodeRepl.write(
  await leafTab.playwright
    .getByText("Codex interaction check:", {
      exact: false,
    })
    .count(),
); // 0: v1 does not contain the later note.
await leafTab.playwright
  .getByRole("button", {
    name: "v1: open versions",
    exact: true,
  })
  .click();
await leafTab.playwright
  .getByRole("menuitem", {
    name: "v2 (latest version) Codex smoke: carry the queued keyboard choice and record its return",
    exact: true,
  })
  .click();
await leafTab.playwright.locator('body[data-lf-presented="1"]').waitFor({
  state: "visible",
  timeoutMs: 10000,
});
nodeRepl.write(
  await leafTab.playwright
    .getByText("Codex interaction check:", {
      exact: false,
    })
    .innerText(),
);
// Return to the original exact live URL, then inspect console and mark deliverable.

// After the separately queued anchored comment starts its own turn and receives
// a reply, open its ordinary thread from the heading and inspect the reply.
await leafTab.playwright
  .getByRole("heading", {
    name: "The iOS reconnect stall 1 comment",
    exact: true,
  })
  .getByRole("button", { name: "1 comment", exact: true })
  .click();
nodeRepl.write(await leafTab.playwright.domSnapshot());
await nodeRepl.emitImage(await leafTab.screenshot({ fullPage: false }));
nodeRepl.write(await leafTab.dev.logs({ levels: ["error", "warn"], limit: 20 }));
await leafTab.markDeliverable();
