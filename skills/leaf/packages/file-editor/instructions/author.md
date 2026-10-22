Use `--package file-editor` when the reader should edit a UTF-8 file on the machine
serving the page. Bind each file explicitly; the browser receives the file's name and
contents, never its absolute path.

```bash
leaf page init --package file-editor PAGE
leaf file bind PAGE notes ./research-notes.md
```

```html
<lf-file-editor id="notes-file" binding="notes"></lf-file-editor>
```

Tell the reader that edits save automatically, and say nothing more about saving: the
editor keeps the reader's draft when a save fails or another program changes the file,
and its own status line offers the choices that resolve it. Edits, Undo included,
change the file itself, outside Leaf's action history.

The binding lives in the page's directory, and only the local Leaf server serving the
page can use it: an exported page shows the editor as unavailable, and a stamped
revision is read-only. Show a file the reader should not change, or a copy that travels
with the page, with `lf-code` holding the exact source.
