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

Tell the reader that edits save automatically, and say nothing more about saving. The
editor saves as the reader types, keeps their draft when a save fails or another
program changes the file, and reports each problem in its own status line with the
choices that resolve it.

Edits change the file itself, outside Leaf's action history, and Undo in the editor is
an ordinary edit that saves too. Show a file the reader should not change with `lf-code`
instead.

A binding belongs to the page server that made it, so a copied or exported page can't
edit the file and shows the editor as unavailable, and a stamped revision is read-only.
Use `lf-code` with the exact source when the reader needs a copy that travels with the
page.
