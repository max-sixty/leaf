Use `--package file-editor` when the reader should edit UTF-8 files on the machine
serving the page: a config, a prompt, code or any file another tool reads as it
stands. Bind each file explicitly; the browser receives each file's label, contents
and the address of its bytes, from which a Markdown preview of it loads the pictures
and files it names beside it.

```bash
leaf page init --package reading --package file-editor PAGE
leaf file bind PAGE notes ./research-notes.md
```

```html
<lf-file-editor id="notes-file" binding="notes"></lf-file-editor>
```

Name several bindings to edit several files in one editor, one open at a time; the
first opens first. Select `file-tree` too and place a navigator whose `for` names the
editor: it lists the files and opens the one the reader picks. A link to
`#<editor-id>:<binding>` opens that file as well, and `#<editor-id>:<binding>:<line>`
puts the caret at the start of that line, so a note can point at the line it is
about. Double-clicking a word in a Markdown preview bound to the editor with `for`
puts the caret at the start of that word's line.

```bash
leaf page init --package reading --package file-editor --package file-tree PAGE
leaf file bind PAGE values deploy/values.yaml
leaf file bind PAGE alerts deploy/alerts.yaml
leaf file bind PAGE runbook docs/runbook.md
```

```html
<lf-file-tree id="files" for="config-editor" aria-label="Deploy files"></lf-file-tree>
<lf-file-editor id="config-editor" binding="values alerts runbook"></lf-file-editor>
```

Each file is labelled by its path below the deepest folder holding every file the
page binds, here `deploy/values.yaml`, `deploy/alerts.yaml` and `docs/runbook.md`;
`leaf file bind` prints the label it gives.

The editor holds the open file's name and text, as last read or saved, as its `text`
output. A reading bound to it with `for`, such as a Markdown preview, shows each save,
about half a second after the reader stops typing, and a comment on it names the file. A Markdown file beside its rendered copy, where the reader comments on passages or
suggests new wording, takes two elements, each in a pane of a workspace so both fill
the window's height:

```html
<lf-file-editor id="readme-editor" binding="readme"></lf-file-editor>
<lf-text-document
  id="readme-rendered"
  for="readme-editor"
  preview="markdown"
></lf-text-document>
```

The editor's own lines take no comments, since typing changes them under the comment;
the reader comments on the rendered copy, or on the numbered lines of its Source tab.

Tell the reader that edits save automatically. The editor saves as the reader types
and saves a file the moment the reader opens another. It shows a change written
elsewhere, by you or another program, and marks the lines it changed until the
reader edits them. It takes such a change in on other lines than the reader's unsaved
edit; where the two touch the same lines, it keeps the draft and reports the conflict
in its own status line with the choices that resolve it.

Edits change the file itself, outside Leaf's action history, and Undo in the editor is
an ordinary edit that saves too. Show a file the reader should not change with `lf-code`
instead.

`leaf file bind` records the binding in the page's directory, and only the local Leaf
server serving that page can use it. A file inside the page's directory is bound by
its path from there, so a copy of the page edits its own copy. Withdraw that page's
access when it is no longer needed:

```bash
leaf file unbind PAGE notes
```

Unbinding leaves the file and its saved edits intact. Later reads find no file and
saves are refused, including from an already-open editor. An exported page shows the
editor as unavailable, and a stamped revision is read-only. Use `lf-code` with the
exact source when the reader needs a copy that travels with the page.
