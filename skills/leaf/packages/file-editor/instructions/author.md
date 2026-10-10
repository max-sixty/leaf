# Edit a real file

Select `--package file-editor` when the reader should edit a UTF-8 file on the
machine serving the page. Bind each file explicitly; the browser receives a label
and contents, never its absolute path.

```bash
leaf page init --package file-editor PAGE
leaf file bind PAGE notes ./research-notes.md
```

```html
<lf-file id="notes-file" binding="notes"></lf-file>
```

Tell the reader that edits save automatically. Keep the surrounding page quiet:
the editor already saves, follows clean external updates, and preserves a draft
when a save fails or another writer changes the file. A delayed save earns a
small status; conflicts show both versions with explicit recovery actions.
Markdown filenames receive Markdown highlighting; other UTF-8 files remain
plain text. CodeMirror supplies editing, history, selection and bracket behavior.

File edits change the bound file, outside Leaf's action history. A reader's Undo
inside the editor changes its buffer and saves that change normally. Keep files
that the reader should not alter as `lf-code` evidence instead.

Bindings belong to the local page server. A copied or exported page without that
binding cannot edit the original file and explains that it is unavailable.
Stamped revisions are read only. Use `lf-code` with the exact source when a
portable snapshot is what the reader needs.
