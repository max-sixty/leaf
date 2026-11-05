## A patch review

`lf-diff` has its own file listing. When directory hierarchy helps the reader navigate
the patch, select the `file-tree` package too; its author instructions describe the
navigator and selected-file composition. A small flat patch can use the diff's listing
alone.

## Worktree snapshots

Use `lf-worktree-diffs` when the reader needs to inspect a supplied set of worktrees.
Give it one `lf-worktree` per snapshot, in review order. There is no limit on how many.
Write each member’s evidence directly inside it. Leaf makes each member an expandable
row and writes its summary from the member's attributes; set `open` on the first useful
snapshot.

Each member supplies `label`, `path`, `status`, and the known snapshot's `files`,
`additions`, and `deletions`. Use `branch` when attached and `head` for the full current
commit hash. The row shows a shortened hash; put the full hash in the authored
snapshot details too, where the reader can select it. Optional `binary-files` counts
binary changes within `files`, separately from text-line totals. The collection
computes its totals from these member values; never count an unavailable snapshot as
zero. `status="clean"` has zero counts; `status="unavailable"` omits counts and explains
the problem in its body. Clean describes the selected comparison, not necessarily
the worktree's uncommitted state.

Get counts from the same Git comparison as the patch (for example, its `--numstat`
output), retaining Git's distinction between binary and textual changes. Name the
comparison and its inclusion scope: comparing a merge base with HEAD differs from
comparing it with the working tree, and untracked files need explicit treatment.
Snapshots can come from different repositories. Label illustrative evidence as such.

Inside each member, use ordinary authored markup followed by the real `lf-diff`:

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
    open
  >
    <p>Preserve a composer draft while switching threads.</p>
    <details>
      <summary>Snapshot details</summary>
      <dl class="facts">
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
    <lf-diff id="draft-patch" source="draft-patch-data" data-height="360"></lf-diff>
  </lf-worktree>
</lf-worktree-diffs>
```

Use the paragraph for the commit subject and relevant working-tree state. An optional
`aside` holds the agent's commentary as normal selectable, commentable prose; omit it
when the evidence speaks for itself. Put full commit and comparison-base hashes,
repository path, scope, and capture time in the native Snapshot details disclosure.
The worktree path itself is supplied by `path` and shown above the body. Include that
path in the authored details too when the reader needs to comment on it.

`lf-diff` remains the patch reader: supply the exact Git patch inline or through its
existing source contract. Describe binary changes in the authored body when
there is no textual patch to inspect. This widget displays snapshots supplied
by the author; it does not discover directories or run Git in the browser.

## Initial height

An inline patch remains readable as authored source while its widget module loads;
leave `data-height` off it. The drawing can change its height when the module loads.
A `source` diff receives its patch through the page's data reading. Reserve its
measured `data-height` when content below must hold still; `page check --render`
reports the drawn height. This applies to textual patches and files manifests,
including `view="file"` readers.
