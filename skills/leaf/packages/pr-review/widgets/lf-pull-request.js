/* A pull request is observed review evidence. The page binds one typed source; this
 * widget projects it without querying a forge or turning review state into a second
 * authority. */
import {
  ago,
  clocked,
  el,
  highlightBlocks,
  keeps,
  keepsText,
  loadMarkdown,
  projectData,
  renderMarkdown,
  watchData,
} from "/runtime/widget-api.js";

function buildCard() {
  const card = el("article", "lf-pr-card");
  const header = el("header", "lf-pr-head");
  const identity = el("p", "lf-pr-identity");
  const identityLabel = el("span", "lf-pr-identity-label");
  const status = el("span", "lf-pr-status");
  const title = el("strong", "lf-pr-title");
  const byline = el("p", "lf-pr-byline");
  const route = el("p", "lf-pr-route");
  const facts = el("ul", "lf-pr-facts");
  const description = el("section", "lf-pr-description");
  const descriptionLabel = el("h3", "lf-pr-description-label");
  const descriptionBody = el("div", "lf-pr-description-body");
  const checks = el("section", "lf-pr-checks");
  const checksTable = el("table", "lf-pr-check-table");
  const checksLabel = el("caption", "lf-pr-checks-label");
  const checksBody = document.createElement("tbody");
  const observed = el("p", "lf-pr-observed");

  keepsText(descriptionLabel, "Author's description");
  keepsText(checksLabel, "Checks");
  identity.append(identityLabel, status);
  header.append(identity, title, byline, route);
  description.append(descriptionLabel, descriptionBody);
  checksTable.append(checksLabel, checksBody);
  checks.append(checksTable);
  card.append(header, facts, description, checks, observed);
  return card;
}

function renderFacts(card, record) {
  const facts = card.querySelector(".lf-pr-facts");
  const values = [
    ["Files", record.diff.files],
    ["Added", `+${record.diff.additions}`],
    ["Deleted", `−${record.diff.deletions}`],
    ["Commits", record.diff.commits],
  ];
  while (facts.children.length < values.length) facts.append(el("li", "lf-pr-fact"));
  for (const [index, [label, value]] of values.entries()) {
    const item = facts.children[index];
    let name = item.querySelector(".lf-pr-fact-name");
    let amount = item.querySelector(".lf-pr-fact-value");
    if (!name) {
      name = el("span", "lf-pr-fact-name");
      amount = el("strong", "lf-pr-fact-value");
      item.append(name, amount);
    }
    keepsText(name, label);
    keepsText(amount, String(value));
  }
}

function renderChecks(card, checks) {
  const body = card.querySelector(".lf-pr-check-table tbody");
  const prior = new Map([...body.children].map((item) => [item.dataset.check, item]));
  const wanted = [];
  for (const [checkName, checkStatus] of Object.entries(checks).sort(([a], [b]) =>
    a.localeCompare(b),
  )) {
    const item = prior.get(checkName) ?? el("tr", "lf-pr-check");
    keeps(item, "data-check", checkName);
    keeps(item, "data-status", checkStatus);
    let name = item.querySelector(".lf-pr-check-name");
    let status = item.querySelector(".lf-pr-check-status");
    if (!name) {
      name = el("th", "lf-pr-check-name");
      name.scope = "row";
      status = el("td", "lf-pr-check-status");
      item.append(name, status);
    }
    keepsText(name, checkName);
    keepsText(status, checkStatus);
    wanted.push(item);
  }
  let cursor = body.firstElementChild;
  for (const item of wanted) {
    if (item !== cursor) body.insertBefore(item, cursor);
    cursor = item.nextElementSibling;
  }
  for (const item of [...body.children]) if (!wanted.includes(item)) item.remove();
  if (!wanted.length) {
    const empty = el("tr", "lf-pr-check lf-pr-check-empty");
    const cell = document.createElement("td");
    cell.colSpan = 2;
    empty.append(cell);
    keepsText(cell, "No checks reported");
    body.append(empty);
  }
}

// Keep the undecorated rendering separately from the live DOM. Leaf adds syntax
// spans and external-link affordances after projection, so comparing innerHTML
// would mistake those decorations for a data change and replace an unchanged
// description (destroying a user's active selection in the process).
const renderedDescriptions = new WeakMap();

function renderDescription(element, source) {
  const rendered = renderMarkdown(source);
  if (renderedDescriptions.get(element) === rendered) return false;
  const template = document.createElement("template");
  template.innerHTML = rendered;
  element.replaceChildren(template.content);
  renderedDescriptions.set(element, rendered);
  return true;
}

function renderCard(record, prior, descriptionChanged) {
  const card = prior ?? buildCard();
  const identityLabel = card.querySelector(".lf-pr-identity-label");
  const status = card.querySelector(".lf-pr-status");
  const title = card.querySelector(".lf-pr-title");
  const byline = card.querySelector(".lf-pr-byline");
  const route = card.querySelector(".lf-pr-route");
  const description = card.querySelector(".lf-pr-description-body");
  const observed = card.querySelector(".lf-pr-observed");

  keeps(
    card,
    "aria-label",
    `${record.repository} pull request ${record.number}: ${record.title}`,
  );
  keeps(status, "data-status", record.status);
  keepsText(identityLabel, `${record.repository} · PR #${record.number}`);
  keepsText(status, record.status);
  keepsText(title, record.title);
  keepsText(byline, `Opened by ${record.author}`);
  keepsText(route, `${record.base} → ${record.head} · revision ${record.revision}`);
  if (
    renderDescription(
      description,
      record.description || "No description was provided by the author.",
    )
  )
    descriptionChanged.value = true;
  keepsText(observed, `Observed ${ago(record.observedAt)}`);
  keeps(observed, "title", record.observedAt);
  renderFacts(card, record);
  renderChecks(card, record.checks);
  return card;
}

function renderMissing(prior) {
  const card = prior ?? el("article", "lf-pr-card lf-pr-missing");
  keepsText(card, "Waiting for pull request data.");
  keeps(card, "aria-label", "Pull request data unavailable");
  return card;
}

customElements.define(
  "lf-pull-request",
  class extends HTMLElement {
    connectedCallback() {
      if (this.stopWatching) return;
      // Markdown loading is asynchronous, but the card paint itself is synchronous. Keep
      // the clock dependency on that second half so an unchanged source still refreshes
      // the observed age when the shared clock crosses a display boundary.
      this.paintSnapshot = clocked(this, (snapshot) => {
        const record = snapshot?.value ?? null;
        const projected = record
          ? [{ ...record, key: `${record.repository}#${record.number}` }]
          : [{ key: "unavailable", missing: true }];
        const descriptionChanged = { value: false };
        projectData(
          this,
          projected,
          ({ key }) => key,
          (next, prior) =>
            next.missing
              ? renderMissing(prior)
              : renderCard(next, prior, descriptionChanged),
          { snapshot, identify: record ? ({ key }) => key : null },
        );
        return descriptionChanged.value;
      });
      this.stopWatching = watchData(this, "request", (snapshot) => this.show(snapshot));
    }

    disconnectedCallback() {
      this.stopWatching?.();
      this.stopWatching = null;
      this.paintSnapshot?.stop();
      this.paintSnapshot = null;
    }

    async show(snapshot) {
      const painter = this.paintSnapshot;
      const record = snapshot?.value ?? null;
      if (record)
        await loadMarkdown((error) =>
          console.error(
            `leaf: pull request Markdown failed to load: ${error?.message ?? error}`,
          ),
        );
      // The widget may leave the document while the lazy Markdown module is loading.
      // Keep the painter belonging to this mount and let a later mount own its snapshot.
      if (this.paintSnapshot !== painter || !this.isConnected) return;
      const descriptionChanged = painter(snapshot);
      if (descriptionChanged) await highlightBlocks(this);
    }
  },
);
