/* Worktree evidence supplied by the host. The widget owns its typed input and
 * rendering; the page binds that input to a source, while Leaf delivers its validated
 * snapshot and keeps datum comments attached across replacement. */
import { ago, offer, projectData, relabel, watchData } from "/runtime/widget-api.js";

function evidence(tree, kind, label, text, prior) {
  const group = prior ?? document.createElement("section");
  group.id = `lf-${tree.id}-${kind}`;
  group.className = `lf-worktree-evidence lf-worktree-${kind}`;
  let heading = group.querySelector(":scope > strong");
  if (!heading) {
    heading = document.createElement("strong");
    group.append(heading);
  }
  if (heading.textContent !== label) heading.textContent = label;
  let pre = group.querySelector(":scope > pre");
  if (!pre) {
    pre = document.createElement("pre");
    group.append(pre);
  }
  if (pre.textContent !== text) pre.textContent = text;
  return group;
}

function summary(record) {
  return [
    record.branch,
    `${record.base}…${record.head}`,
    `↑${record.ahead} ↓${record.behind}`,
    `+${record.additions} −${record.deletions}`,
    `${record.commits} commit${record.commits === 1 ? "" : "s"}`,
    `tests ${record.tests}`,
  ].join(" · ");
}

function renderDatum(tree, record, prior) {
  const datum = prior ?? document.createElement("section");
  datum.className = "lf-worktree-snapshot";
  let head = datum.querySelector(":scope > .lf-worktree-head");
  if (!head) {
    head = offer("button", "lf-worktree-head");
    head.addEventListener("click", (event) => {
      event.stopPropagation();
      tree.toggleAttribute("data-lf-open");
      tree.show(tree.snapshot);
    });
    datum.prepend(head);
  }
  relabel(
    head,
    record.missing
      ? `${tree.hasAttribute("data-lf-open") ? "▾" : "▸"} No worktree snapshot`
      : `${tree.hasAttribute("data-lf-open") ? "▾" : "▸"} ${summary(record)}`,
    { says: true },
  );
  head.setAttribute("aria-expanded", String(tree.hasAttribute("data-lf-open")));

  let source = datum.querySelector(":scope > .lf-worktree-source");
  if (!source) {
    source = document.createElement("p");
    source.className = "lf-worktree-source";
    head.after(source);
  }
  const sourceText = record.missing
    ? "Observed evidence · waiting for the host"
    : `Observed evidence · ${ago(record.observedAt)}`;
  if (source.textContent !== sourceText) source.textContent = sourceText;

  const priorEvidence = new Map(
    [...datum.querySelectorAll(":scope > .lf-worktree-evidence")].map((node) => [
      node.classList.contains("lf-worktree-files") ? "files" : "diff",
      node,
    ]),
  );
  const wanted = [];
  if (!record.missing) {
    if (record.files) {
      wanted.push(
        evidence(tree, "files", "Files", record.files, priorEvidence.get("files")),
      );
    }
    if (record.diff) {
      wanted.push(
        evidence(tree, "diff", "Diff", record.diff, priorEvidence.get("diff")),
      );
    }
    if (!record.files && !record.diff) {
      wanted.push(
        evidence(
          tree,
          "diff",
          "Diff",
          "No diff was produced.",
          priorEvidence.get("diff"),
        ),
      );
    }
  }
  let cursor = source.nextElementSibling;
  for (const node of wanted) {
    if (node !== cursor) datum.insertBefore(node, cursor);
    cursor = node.nextElementSibling;
  }
  for (const node of priorEvidence.values()) {
    if (!wanted.includes(node)) node.remove();
  }
  return datum;
}

customElements.define(
  "lf-worktree",
  class extends HTMLElement {
    connectedCallback() {
      if (this.stopWatching) return;
      if (!this.revealWorktree) {
        this.revealWorktree = () => {
          this.setAttribute("data-lf-open", "");
          this.show(this.snapshot);
        };
        this.addEventListener("lf-reveal", this.revealWorktree);
      }
      this.stopWatching = watchData(this, "worktrees", (snapshot) =>
        this.show(snapshot),
      );
    }

    disconnectedCallback() {
      this.stopWatching?.();
      this.stopWatching = null;
    }

    show(snapshot) {
      this.snapshot = snapshot;
      const records = snapshot?.value ?? {};
      const present = Object.hasOwn(records, this.id);
      const record = present
        ? { id: this.id, ...records[this.id] }
        : { id: this.id, missing: true };
      projectData(
        this,
        [record],
        ({ id }) => id,
        (next, prior) => renderDatum(this, next, prior),
      );
    }
  },
);
