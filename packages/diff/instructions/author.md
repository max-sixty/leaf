Use `lf-worktree-diffs` when the reader needs to inspect a supplied set of worktrees.
Give it one `lf-worktree` per snapshot, in review order, with no limit on how many.
Wrap each member's evidence in one native `details` with a stable id; Leaf supplies its
summary, and `open` on the first useful disclosure shows it initially.

Each member supplies `label`, `path`, `status`, and the known snapshot's `files`,
`additions` and `deletions`, plus `branch` when attached and `head` for the full current
commit hash. The row shows a shortened hash, so put the full hash in the authored
snapshot details too, where the reader can select it. Optional `binary-files` counts
binary changes within `files`, apart from the line totals. The collection totals the
members' values, so never count an unavailable snapshot as zero: `status="unavailable"`
omits counts and explains the problem in its body. `status="clean"` describes the
selected comparison, not necessarily the worktree's uncommitted state.

Get counts from the same Git comparison as the patch, such as its `--numstat` output,
keeping Git's distinction between binary and textual changes. Name the comparison and
its scope: comparing a merge base with HEAD differs from comparing it with the working
tree, and untracked files need explicit treatment. Snapshots can come from different
repositories. Label illustrative evidence as such.

Inside each disclosure, write ordinary markup followed by the real `lf-diff`:

```html
<lf-worktree-diffs id="worktrees">
  <lf-worktree
    id="draft-worktree"
    label="retain-drafts"
    path="/workspace/leaf.retain-drafts"
    branch="fix/retain-drafts"
    head="c8ebd603f87d4c9db1ce17bf134b76567d8a409c"
    status="changed"
    files="1"
    additions="1"
    deletions="1"
  >
    <details id="draft-worktree-body" open>
      <p>Preserve a composer draft while switching threads.</p>
      <details>
        <summary>Snapshot details</summary>
        <dl>
          <dt>Repository</dt>
          <dd><code>/workspace/leaf</code></dd>
          <dt>Current commit</dt>
          <dd><code>c8ebd603f87d4c9db1ce17bf134b76567d8a409c</code></dd>
          <dt>Comparison</dt>
          <dd>HEAD → working tree; tracked files only</dd>
          <dt>Captured</dt>
          <dd>22 Oct 2026, 10:30 PT</dd>
        </dl>
      </details>
      <aside><p>The draft is saved before the thread changes.</p></aside>
      <lf-diff id="draft-patch" source="draft-patch-data" data-height="360">
        <pre></pre>
      </lf-diff>
    </details>
  </lf-worktree>
</lf-worktree-diffs>
```

The paragraph holds the commit subject and relevant working-tree state. An optional
`aside` holds your commentary as ordinary prose the reader can select and comment on;
omit it when the evidence speaks for itself. The Snapshot details disclosure holds the
full commit and comparison-base hashes, repository path, scope and capture time, and the
worktree path too when the reader needs to comment on it.

Supply each `lf-diff` the exact Git patch inline or through its source contract, and
describe binary changes in the authored body where there is no textual patch. The widget
shows only the snapshots you supply; it discovers no directories and runs no Git.
