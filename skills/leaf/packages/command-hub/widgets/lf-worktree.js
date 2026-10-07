/* Worktree evidence supplied by the host. The widget owns its typed input and
 * rendering; the page binds that input to a source, while Leaf delivers its validated
 * snapshot and keeps datum comments attached across replacement. */
import {
  DISCLOSE,
  ago,
  commands,
  keeps,
  projectData,
  relabel,
  selectableOffer,
  html,
  render,
  repeat,
  watchData,
  once,
} from "/runtime/widget-api.js";

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

function renderDatum(tree, record) {
  let head = tree.head;
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
    commands(head, "On worktree evidence", [
      {
        id: "worktree.toggle",
        keys: () => DISCLOSE(head),
        title: () => (tree.hasAttribute("data-lf-open") ? "close" : "open"),
        run: () => head.click(),
      },
    ]);
    tree.head = head;
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
  // own. Only a change is written.
  keeps(head, "aria-expanded", tree.hasAttribute("data-lf-open"));

  const evidence = record.missing
    ? []
    : [
        ...(record.files
          ? [{ kind: "files", label: "Files", text: record.files }]
          : []),
        ...(record.diff ? [{ kind: "diff", label: "Diff", text: record.diff }] : []),
        ...(!record.files && !record.diff
          ? [{ kind: "diff", label: "Diff", text: "No diff was produced." }]
          : []),
      ];
  render(
    html`<section class="lf-worktree-snapshot">
      ${head}
      <p class="lf-worktree-source">
        ${record.missing ? "Observed evidence · waiting for the host" : `Observed evidence · ${ago(record.observedAt)}`}
      </p>
      ${repeat(
        evidence,
        ({ kind }) => kind,
        ({ kind, label, text }) =>
          html`<section
            id=${`lf-${tree.id}-${kind}`}
            class=${`lf-worktree-evidence lf-worktree-${kind}`}
          >
            <strong>${label}</strong>
            <pre>${text}</pre>
          </section>`,
      )}
    </section>`,
    tree,
  );
  return tree.querySelector(".lf-worktree-snapshot");
}

customElements.define(
  "lf-worktree",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      if (!this.revealWorktree) {
        this.revealWorktree = () => {
          this.toggleAttribute("data-lf-open", true);
          this.show(this.snapshot);
        };
        this.addEventListener("lf-reveal", this.revealWorktree);
      }
      watchData(this, "worktrees", (snapshot) => this.show(snapshot));
    }

    show(snapshot) {
      this.snapshot = snapshot;
      const records = snapshot?.value ?? {};
      const present = Object.hasOwn(records, this.id);
      const record = present
        ? { id: this.id, ...records[this.id] }
        : { id: this.id, missing: true };
      const node = renderDatum(this, record);
      projectData(
        this,
        [
          {
            node,
            key: this.id,
            ...(present ? { identity: this.id } : {}),
            origin: snapshot
              ? { ...snapshot.origin, ...(present ? { path: [this.id] } : {}) }
              : null,
          },
        ],
        { snapshot },
      );
    }
  },
);
