/* A pull request is observed review evidence. The page binds one typed source; this
 * widget projects it without querying a forge or turning review state into a second
 * authority. */
import {
  ago,
  highlightBlocks,
  loadMarkdown,
  projectData,
  renderMarkdown,
  watchData,
} from "/runtime/widget-api.js";

const setText = (element, value) => {
  if (element.textContent !== value) element.textContent = value;
};

function make(tag, className) {
  const element = document.createElement(tag);
  element.className = className;
  return element;
}

function buildCard() {
  const card = make("article", "lf-pr-card");
  const header = make("header", "lf-pr-head");
  const identity = make("p", "lf-pr-identity");
  const identityLabel = make("span", "lf-pr-identity-label");
  const status = make("span", "lf-pr-status");
  const title = make("strong", "lf-pr-title");
  const byline = make("p", "lf-pr-byline");
  const route = make("p", "lf-pr-route");
  const facts = make("ul", "lf-pr-facts");
  const description = make("section", "lf-pr-description");
  const descriptionLabel = make("h3", "lf-pr-description-label");
  const descriptionBody = make("div", "lf-pr-description-body");
  const checks = make("section", "lf-pr-checks");
  const checksTable = make("table", "lf-pr-check-table");
  const checksLabel = make("caption", "lf-pr-checks-label");
  const checksBody = document.createElement("tbody");
  const observed = make("p", "lf-pr-observed");

  setText(descriptionLabel, "Author's description");
  setText(checksLabel, "Checks");
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
  while (facts.children.length < values.length) facts.append(make("li", "lf-pr-fact"));
  for (const [index, [label, value]] of values.entries()) {
    const item = facts.children[index];
    let name = item.querySelector(".lf-pr-fact-name");
    let amount = item.querySelector(".lf-pr-fact-value");
    if (!name) {
      name = make("span", "lf-pr-fact-name");
      amount = make("strong", "lf-pr-fact-value");
      item.append(name, amount);
    }
    setText(name, label);
    setText(amount, String(value));
  }
}

function renderChecks(card, checks) {
  const body = card.querySelector(".lf-pr-check-table tbody");
  const prior = new Map([...body.children].map((item) => [item.dataset.check, item]));
  const wanted = [];
  for (const [checkName, checkStatus] of Object.entries(checks).sort(([a], [b]) =>
    a.localeCompare(b),
  )) {
    const item = prior.get(checkName) ?? make("tr", "lf-pr-check");
    item.dataset.check = checkName;
    item.dataset.status = checkStatus;
    let name = item.querySelector(".lf-pr-check-name");
    let status = item.querySelector(".lf-pr-check-status");
    if (!name) {
      name = make("th", "lf-pr-check-name");
      name.scope = "row";
      status = make("td", "lf-pr-check-status");
      item.append(name, status);
    }
    setText(name, checkName);
    setText(status, checkStatus);
    wanted.push(item);
  }
  let cursor = body.firstElementChild;
  for (const item of wanted) {
    if (item !== cursor) body.insertBefore(item, cursor);
    cursor = item.nextElementSibling;
  }
  for (const item of [...body.children]) if (!wanted.includes(item)) item.remove();
  if (!wanted.length) {
    const empty = make("tr", "lf-pr-check lf-pr-check-empty");
    const cell = document.createElement("td");
    cell.colSpan = 2;
    empty.append(cell);
    setText(cell, "No checks reported");
    body.append(empty);
  }
}

// Keep the undecorated rendering separately from the live DOM. Leaf adds syntax
// spans and external-link affordances after projection, so comparing innerHTML
// would mistake those decorations for a data change and replace an unchanged
// description (destroying a reader's active selection in the process).
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

function renderCard(record, prior, snapshot, descriptionChanged) {
  const card = prior ?? buildCard();
  const identityLabel = card.querySelector(".lf-pr-identity-label");
  const status = card.querySelector(".lf-pr-status");
  const title = card.querySelector(".lf-pr-title");
  const byline = card.querySelector(".lf-pr-byline");
  const route = card.querySelector(".lf-pr-route");
  const description = card.querySelector(".lf-pr-description-body");
  const observed = card.querySelector(".lf-pr-observed");

  card.setAttribute(
    "aria-label",
    `${record.repository} pull request ${record.number}: ${record.title}`,
  );
  status.dataset.status = record.status;
  setText(identityLabel, `${record.repository} · PR #${record.number}`);
  setText(status, record.status);
  setText(title, record.title);
  setText(byline, `Opened by ${record.author}`);
  setText(route, `${record.base} → ${record.head} · revision ${record.revision}`);
  if (
    renderDescription(
      description,
      record.description || "No description was provided by the author.",
    )
  )
    descriptionChanged.value = true;
  const capture = snapshot?.snapshot
    ? ` · ${snapshot.label || `snapshot ${snapshot.snapshot}`}`
    : "";
  setText(observed, `Observed ${ago(record.observedAt)}${capture}`);
  observed.title = record.observedAt;
  renderFacts(card, record);
  renderChecks(card, record.checks);
  return card;
}

function renderMissing(prior) {
  const card = prior ?? make("article", "lf-pr-card lf-pr-missing");
  setText(card, "Waiting for pull request data.");
  card.setAttribute("aria-label", "Pull request data unavailable");
  return card;
}

customElements.define(
  "lf-pull-request",
  class extends HTMLElement {
    connectedCallback() {
      if (this.stopWatching) return;
      this.stopWatching = watchData(this, "request", (snapshot) => this.show(snapshot));
    }

    disconnectedCallback() {
      this.stopWatching?.();
      this.stopWatching = null;
    }

    async show(snapshot) {
      const record = snapshot?.value ?? null;
      if (record)
        await loadMarkdown((error) =>
          console.error(
            `leaf: pull request Markdown failed to load: ${error?.message ?? error}`,
          ),
        );
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
            : renderCard(next, prior, snapshot, descriptionChanged),
        { snapshot },
      );
      if (descriptionChanged.value) await highlightBlocks(this);
    }
  },
);
