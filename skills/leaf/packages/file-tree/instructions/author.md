# File navigation

Select the `file-tree` package for a directory navigator. Use a file tree when the
reader needs to move among files; keep an ordinary document outline in `lf-toc`.

Bind `lf-file-tree` to a `file-list` source with `source`, or name a widget that
publishes a compatible `files` output with `for`. Choose exactly one. For example,
select both `file-tree` and `diff`, then place this beside the patch:

```html
<lf-file-tree id="changed-files" for="patch" aria-label="Changed files"></lf-file-tree>
<lf-diff id="patch" source="changes"><pre></pre></lf-diff>
```

The producer supplies the paths, optional Git status, and optional datum keys.
Selecting a keyed file reveals that datum through the declared reference. A tree
bound directly to a source keeps selection local. Files are data, not actions:
expansion, search, and selection do not enter Leaf's event log.

Arrow keys move among visible files and folders; Enter or Space selects a file or
toggles a folder. Typing searches. The navigator holds its height while its listing
scrolls; set `--lf-file-tree-height` on the widget to choose that allocation.
