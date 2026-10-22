Select the `file-tree` package for a directory navigator when the folder hierarchy helps
the reader move among many files; an ordinary document outline stays in `lf-toc`.

Bind `lf-file-tree` to a `file-list` source with `source`, or name a widget that
publishes a compatible `files` output with `for`. For example, select both `file-tree`
and `diff`, then place this beside the patch:

```html
<lf-file-tree id="changed-files" for="patch" aria-label="Changed files"></lf-file-tree>
<lf-diff id="patch" source="changes" view="file"><pre></pre></lf-diff>
```

The diff's `view="file"` shows the selected file beside the navigator. Give the patch
enough width to read, keep the navigator in reach while reading it, and give an obvious
route back to the file list when the regions stack on a phone. A small flat patch
usually needs only the diff's own listing.

The producer supplies the paths, optional Git status and optional datum keys, and an
optional `current` path that keeps the selection on the file its viewer shows. Selecting
a keyed file reveals that datum in the widget `for` names; a tree bound directly to a
source keeps selection local. Expansion, search and selection are reading state and
never enter the page's log.

The navigator fills a definite height, such as a workspace pane's body. In ordinary
flow, `--lf-file-tree-height` sets its height and the listing scrolls inside it.
