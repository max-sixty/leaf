Select the `file-tree` package for a directory navigator when the folder hierarchy
helps the reader move among many files. Keep an ordinary document outline in
`lf-toc`.

Bind `lf-file-tree` to a `file-list` source with `source`, or name a widget that
publishes a compatible `files` output with `for`. Choose exactly one. For example,
select both `file-tree` and `diff`, then place this beside the patch:

```html
<lf-file-tree id="changed-files" for="patch" aria-label="Changed files"></lf-file-tree>
<lf-diff id="patch" source="changes" view="file"></lf-diff>
```

The diff's `view="file"` presents the selected file beside the navigator. Give
the patch enough width to read, keep the navigator available while reading it,
and provide an obvious route back to the file list when the regions stack on a
phone. A small flat patch usually needs only the diff's own listing.

The producer supplies the paths, optional Git status, and optional datum keys.
Its optional `current` path keeps selection aligned with the file its viewer shows.
Selecting a keyed file reveals that datum through the declared reference. A tree
bound directly to a source keeps selection local. Files are data, not actions:
expansion, search, and selection do not enter Leaf's event log.

The navigator fills a definite height allocation,
such as a workspace pane's body. In ordinary flow, `--lf-file-tree-height` chooses
its bounded height while the listing scrolls.
