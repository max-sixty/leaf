/* Worktree evidence supplied by the host. The widget owns its typed input and
 * rendering; the page binds that input to a source, while Leaf delivers its validated
 * snapshot and keeps datum comments attached across replacement. */
import {
  DISCLOSE,
  ago,
  keys,
  projectData,
  relabel,
  selectableOffer,
  watchData,
} from "/runtime/widget-api.js";

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
    head = selectableOffer("button", "lf-worktree-head");
    head.addEventListener("click", (event) => {
      event.stopPropagation();
      tree.toggleAttribute("data-lf-open");
      tree.show(tree.snapshot);
    });
    // Which way it stands, before the scope below reads it: a button wearing
    // aria-expanded is ARIA's disclosure pattern, and that pair is what `DISCLOSE`
    // answers from. Without it `DISCLOSE` reads a control it cannot place and hands
    // back both arrows, which is what `aria-keyshortcuts` would be written with. The
    // render below sets the live value; this is the one at birth.
    head.setAttribute("aria-expanded", String(tree.hasAttribute("data-lf-open")));
    // The same press the runtime's disclosure scope owns, re-worded in this widget's
    // terms. Its keys come from `DISCLOSE` rather than from `PRESS`, which is what that
    // primitive is for: a nearer scope keeps only the keys it names, so the pair alone
    // took the arrow off the line while it went on opening the tree.
    //
    // And it keeps its own `run`, because this head is a span. `DISCLOSE` hands over
    // only the arrow that changes the state, so a press here is a direction and never a
    // second toggle; what it also answers for is where the head stands. In thread
    // markup the disclosure scope refuses to reach — its `at` asks `!inChrome` — and a
    // span has no platform half to fall back on the way `details > summary` does, so
    // without this the frozen head names ⏎ / space and nothing runs them.
    keys(head, "On worktree evidence", [
      {
        id: "worktree.toggle",
        keys: () => DISCLOSE(head),
        does: "Open or close the worktree evidence",
        line: () => (tree.hasAttribute("data-lf-open") ? "close" : "open"),
        run: () => head.click(),
      },
    ]);
    datum.prepend(head);
  }
  relabel(
    head,
    record.missing
      ? `${tree.hasAttribute("data-lf-open") ? "▾" : "▸"} No worktree snapshot`
      : `${tree.hasAttribute("data-lf-open") ? "▾" : "▸"} ${summary(record)}`,
    { says: true },
  );
  // Which way it stands now. The row's bindings answer from this attribute, and so do
  // both surfaces naming its keys: the document's disclosure watch hears this write and
  // repaints them together, so a row bound through `DISCLOSE` owes no repaint of its
  // own. Restating the same value is not a disclosure changing — the watch reads the
  // old value to tell the two apart — so every render can write it.
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
        {
          snapshot,
          originOf: () =>
            snapshot
              ? { ...snapshot.origin, ...(present ? { path: [this.id] } : {}) }
              : null,
        },
      );
    }
  },
);
