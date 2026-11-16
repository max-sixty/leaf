/** CodeMirror owns editing, selection, history and conflict presentation.
 * The surrounding widget alone owns file revisions and disk writes.
 */
import {
  setScroll,
  langForPath,
  leafEditorView,
  sizeObserver,
} from "/runtime/widget-api.js";
import * as codemirror from "/vendor/codemirror.esm.js";
import {
  ChangeSet,
  Compartment,
  EditorState,
  Prec,
  Transaction,
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLineGutter,
  highlightActiveLine,
  dropCursor,
  rectangularSelection,
  crosshairCursor,
  drawSelection,
  history,
  historyKeymap,
  defaultKeymap,
  LanguageSupport,
  markdownLanguage,
  HighlightStyle,
  syntaxHighlighting,
  indentOnInput,
  placeholder,
  bracketMatching,
  tags,
} from "/vendor/codemirror.esm.js";
import {
  diff,
  unifiedMergeView,
  getOriginalDoc,
  originalDocChangeEffect,
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
  completionKeymap,
} from "/vendor/extensions.esm.js";

const LeafEditorView = leafEditorView(codemirror);

const theme = EditorView.theme({
  "&": { color: "var(--ink)", backgroundColor: "var(--card)" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "24px" },
  ".cm-content": { caretColor: "var(--accent)" },
  ".cm-line": { padding: "0 .85rem" },
  ".cm-gutters": {
    backgroundColor: "var(--paper)",
    color: "var(--muted)",
    borderRight: "1px solid var(--rule)",
  },
  ".cm-lineNumbers .cm-gutterElement": {
    padding: "0 .6rem 0 .8rem",
    minWidth: "2.5rem",
  },
  ".cm-activeLine, .cm-activeLineGutter": {
    backgroundColor: "color-mix(in srgb, var(--accent) 6%, transparent)",
  },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--accent)" },
  ".cm-placeholder": { color: "var(--quiet)" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
    { backgroundColor: "color-mix(in srgb, var(--accent) 24%, transparent)" },
  ".cm-matchingBracket": {
    backgroundColor: "color-mix(in srgb, var(--accent) 18%, transparent)",
    outline: "1px solid color-mix(in srgb, var(--accent) 40%, transparent)",
  },
  ".cm-tooltip": {
    backgroundColor: "var(--card)",
    color: "var(--ink)",
    border: "1px solid var(--border-2)",
  },
  ".cm-tooltip-autocomplete > ul > li[aria-selected]": {
    backgroundColor: "var(--accent)",
    color: "var(--card)",
  },
  "&.cm-merge-b .cm-changedLine, .cm-inlineChangedLine": {
    backgroundColor: "color-mix(in srgb, var(--ok) 9%, transparent)",
  },
  "&.cm-merge-b .cm-changedText": {
    backgroundColor: "color-mix(in srgb, var(--ok) 23%, transparent)",
  },
  ".cm-deletedChunk": {
    backgroundColor: "color-mix(in srgb, var(--danger) 9%, var(--card))",
    padding: ".35rem .85rem",
    borderLeft: "3px solid var(--danger)",
  },
  ".cm-deletedChunk .cm-deletedText": {
    backgroundColor: "color-mix(in srgb, var(--danger) 19%, transparent)",
  },
  ".cm-deletedChunk .cm-deletedLine": { textDecoration: "none", opacity: ".85" },
  ".cm-deletedText": { textDecoration: "line-through" },
  ".cm-changedLineGutter": { backgroundColor: "var(--ok)" },
  ".cm-deletedLineGutter": { backgroundColor: "var(--danger)" },
});

// The theme's code tokens, as code blocks and diffs colour the same names (Leaf's
// token theme, build/entries/syntax/entry.mjs): a key, a type or a tag in
// `--syn-type`, a comment in italic `--syn-comment`.
const highlighting = HighlightStyle.define([
  { tag: tags.heading, color: "var(--accent)", fontWeight: "650" },
  { tag: tags.strong, fontWeight: "650" },
  { tag: tags.emphasis, fontStyle: "italic" },
  { tag: [tags.link, tags.url], color: "var(--accent)", textDecoration: "underline" },
  { tag: [tags.monospace, tags.string], color: "var(--syn-string)" },
  { tag: [tags.keyword, tags.modifier], color: "var(--syn-keyword)" },
  { tag: [tags.number, tags.bool], color: "var(--syn-number)" },
  { tag: tags.comment, color: "var(--syn-comment)", fontStyle: "italic" },
  { tag: [tags.meta, tags.processingInstruction], color: "var(--syn-comment)" },
  {
    tag: [tags.propertyName, tags.typeName, tags.labelName],
    color: "var(--syn-type)",
  },
]);

// Each language the editor highlights, by the name a file's path selects
// (`langForPath`). Markdown comes with the editor core; every other language is a
// module of the file-editor package, loaded the first time a file of it opens
// (build/vendor.mjs, "file-editor"). A file in any other language reads as plain text.
/** @type {Record<string, () => Promise<import("@codemirror/state").Extension>>} */
const languages = {
  markdown: async () => new LanguageSupport(markdownLanguage),
  yaml: async () => {
    const { yaml } = await import("/vendor/codemirror-yaml.esm.js");
    const support = yaml();
    // Code blocks colour YAML's plain values as strings. The YAML grammar calls them
    // content, which Markdown's prose is too, so the colour is scoped to YAML.
    return [
      support,
      syntaxHighlighting(
        HighlightStyle.define([{ tag: tags.content, color: "var(--syn-string)" }], {
          scope: support.language,
        }),
      ),
    ];
  },
};
/** @type {Map<string, Promise<import("@codemirror/state").Extension>>} */
const loading = new Map();
/** @type {Map<string, import("@codemirror/state").Extension>} */
const loaded = new Map();
// The language a file's name selects among those the editor highlights, or null.
/** @param {string} filename */
const languageFor = (filename) => {
  const name = langForPath(filename);
  return name && name in languages ? name : null;
};
/** @param {string} name */
const loadLanguage = (name) => {
  let pending = loading.get(name);
  if (!pending) {
    pending = /** @type {() => Promise<import("@codemirror/state").Extension>} */ (
      languages[name]
    )();
    loading.set(name, pending);
    void pending.then((extension) => loaded.set(name, extension));
  }
  return pending;
};
/** What the editor holds of one file while another is open (`suspend`).
 * @typedef {{state: import("@codemirror/state").EditorState,
 *   scroll: {top: number, left: number}}} KeptFile */

/** The changes that fold `theirs`, a version of `base` written elsewhere, into
 * `ours`, the reader's edit of `base`, where the two changed lines apart from each
 * other; null where they changed the same or adjacent lines, which a line merge leaves
 * for the reader to compare.
 * @param {string} base @param {string} ours @param {string} theirs */
function lineMerge(base, ours, theirs) {
  const lines = EditorState.create({ doc: base }).doc;
  /** @param {string} text */
  const changes = (text) =>
    diff(base, text).map((change) => ({
      from: change.fromA,
      to: change.toA,
      insert: text.slice(change.fromB, change.toB),
      first: lines.lineAt(change.fromA).number,
      last: lines.lineAt(Math.max(change.fromA, change.toA - 1)).number,
    }));
  const mine = changes(ours),
    other = changes(theirs);
  if (
    mine.some((a) => other.some((b) => a.first <= b.last + 1 && b.first <= a.last + 1))
  )
    return null;
  const spec = (/** @type {typeof mine} */ list) =>
    ChangeSet.of(
      list.map(({ from, to, insert }) => ({ from, to, insert })),
      base.length,
    );
  return spec(other).map(spec(mine));
}

/** `lineMerge` into what the editor keeps of a file while another is open, or null.
 * @param {KeptFile} kept @param {string} base @param {string} theirs
 * @returns {KeptFile | null} */
export function mergeKept(kept, base, theirs) {
  const changes = lineMerge(base, kept.state.doc.toString(), theirs);
  return (
    changes && {
      ...kept,
      state: kept.state.update({
        changes,
        annotations: Transaction.addToHistory.of(false),
      }).state,
    }
  );
}

/** Create a file editor. External text changes use CodeMirror transactions,
 * mapping selection through the dependency's diff. Adopting changed external text
 * starts a new undo history: earlier local edits belong to the replaced version.
 * @param {HTMLElement} parent
 * @param {{text?: string, filename?: string, original?: string | null, readOnly?: boolean,
 *   label?: string, description?: string, onChange?: (text: string) => void,
 *   onSave?: () => void}} [options]
 */
export function createEditor(
  parent,
  {
    text = "",
    filename = "",
    original = null,
    readOnly = false,
    label = "File contents",
    description = "Changes save automatically. If the file changes elsewhere, review both versions before saving.",
    onChange,
    onSave,
  } = {},
) {
  const editable = new Compartment(),
    language = new Compartment(),
    hint = new Compartment(),
    undoHistory = new Compartment();
  let shownHint = "";
  let readonly = readOnly,
    /** @type {string | null | undefined} */
    shownLanguage = null,
    conflict = original,
    replacing = false;
  const readonlyExtension = () => [
    EditorState.readOnly.of(readonly),
    EditorView.editable.of(!readonly),
    EditorView.contentAttributes.of({
      "aria-readonly": String(readonly),
      ...(readonly ? { tabindex: "0" } : {}),
    }),
  ];
  const state = (/** @type {string} */ value) =>
    EditorState.create({
      doc: value,
      extensions: [
        undoHistory.of(history()),
        drawSelection(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        language.of([]),
        hint.of([]),
        syntaxHighlighting(highlighting),
        theme,
        // Only the primary editor needs line coordinates and an active line.
        // The read-only comparison presents both versions through text decorations.
        original === null
          ? [lineNumbers(), highlightActiveLineGutter(), highlightActiveLine()]
          : [],
        dropCursor(),
        rectangularSelection(),
        crosshairCursor(),
        EditorState.allowMultipleSelections.of(true),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        autocompletion(),
        keymap.of([...closeBracketsKeymap, ...completionKeymap]),
        EditorState.tabSize.of(4),
        EditorView.contentAttributes.of({
          role: "textbox",
          "aria-label": label,
          "aria-description": description,
          "aria-multiline": "true",
          spellcheck: "false",
          autocapitalize: "off",
          autocomplete: "off",
        }),
        editable.of(readonlyExtension()),
        EditorView.lineWrapping,
        // A comparison is created with the disk version it shows and only ever moves
        // to a later one (`setConflict`); the primary editor never shows one.
        original === null
          ? []
          : unifiedMergeView({
              original,
              mergeControls: false,
              allowInlineDiffs: true,
              gutter: false,
            }),
        Prec.highest(
          keymap.of([
            {
              key: "Mod-s",
              run: () => {
                onSave?.();
                return true;
              },
              stopPropagation: true,
            },
          ]),
        ),
        EditorView.updateListener.of((update) => {
          if (update.docChanged && !replacing) onChange?.(update.state.doc.toString());
        }),
      ],
    });
  // Highlight in `name`'s language: at once where it has loaded, else plain until it
  // has, unless the editor has moved on to another file's language by then.
  /** @param {string | null} name */
  const showLanguage = (name) => {
    if (name === shownLanguage) return;
    shownLanguage = name;
    const ready = name && loaded.get(name);
    dispatch({ effects: language.reconfigure(ready || []) });
    if (!name || ready) return;
    void loadLanguage(name).then((extension) => {
      if (shownLanguage === name)
        dispatch({ effects: language.reconfigure(extension) });
    });
  };
  let retained = state(text);
  /** @type {InstanceType<typeof LeafEditorView> | null} */
  let view = new LeafEditorView({ state: retained, parent });
  let scroll = { top: 0, left: 0 };
  const reading = () => view?.state ?? retained;
  const dispatch = (
    /** @type {import("@codemirror/state").TransactionSpec} */ spec,
  ) => {
    if (view) view.dispatch(spec);
    else retained = retained.update(spec).state;
  };
  showLanguage(languageFor(filename));
  const revealCaret = () =>
    dispatch({
      effects: EditorView.scrollIntoView(reading().selection.main.head, {
        y: "nearest",
      }),
    });
  const resize =
    original === null
      ? sizeObserver(() => {
          if (view?.hasFocus) revealCaret();
        })
      : null;
  resize?.observe(view.scrollDOM);
  const disconnect = () => {
    if (!view) return;
    retained = view.state;
    scroll = { top: view.scrollDOM.scrollTop, left: view.scrollDOM.scrollLeft };
    resize?.disconnect();
    view.destroy();
    view = null;
  };
  return {
    get value() {
      return reading().doc.toString();
    },
    set value(value) {
      if (value === reading().doc.toString()) return;
      replacing = true;
      try {
        const previous = reading().doc.toString();
        dispatch({
          changes: diff(previous, value).map((change) => ({
            from: change.fromA,
            to: change.toA,
            insert: value.slice(change.fromB, change.toB),
          })),
          effects: undoHistory.reconfigure([]),
          annotations: Transaction.addToHistory.of(false),
        });
        dispatch({ effects: undoHistory.reconfigure(history()) });
      } finally {
        replacing = false;
      }
    },
    // Fold `theirs` into the text being edited (`lineMerge`), keeping the reader's
    // selection and undo history; say whether it did.
    /** @param {string} base @param {string} theirs */
    merge(base, theirs) {
      const changes = lineMerge(base, reading().doc.toString(), theirs);
      if (!changes) return false;
      replacing = true;
      try {
        dispatch({ changes, annotations: Transaction.addToHistory.of(false) });
      } finally {
        replacing = false;
      }
      return true;
    },
    // What the editor would keep of `text` read afresh, for a file not yet shown.
    /** @param {string} text @returns {KeptFile} */
    keep(text) {
      return { state: state(text), scroll: { top: 0, left: 0 } };
    },
    get readOnly() {
      return readonly;
    },
    // Words an empty editor shows in place of the file, such as why no file is there.
    /** @param {string} text */
    set placeholder(text) {
      if (shownHint === text) return;
      shownHint = text;
      dispatch({ effects: hint.reconfigure(text ? placeholder(text) : []) });
    },
    set readOnly(value) {
      if (readonly === value) return;
      readonly = value;
      dispatch({ effects: editable.reconfigure(readonlyExtension()) });
    },
    get contentDOM() {
      if (!view) throw new Error("A detached editor has no rendered content");
      return view.contentDOM;
    },
    /** @param {string} label */
    setLabel(label) {
      showLanguage(languageFor(label));
    },
    /** @param {string} value */
    setConflict(value) {
      if (conflict === value) return;
      conflict = value;
      const originalLength = getOriginalDoc(reading()).length;
      const changes = ChangeSet.of(
        { from: 0, to: originalLength, insert: value },
        originalLength,
      );
      dispatch({ effects: originalDocChangeEffect(reading(), changes) });
    },
    // Everything the editor holds of one file, its text, selection, undo history and
    // scroll, for `resume` to put back when the reader returns to that file.
    /** @returns {KeptFile} */
    suspend() {
      const port = view?.scrollDOM;
      return {
        state: reading(),
        scroll: port ? { top: port.scrollTop, left: port.scrollLeft } : scroll,
      };
    },
    // Show another file: what `suspend` kept of it, or else `text` with a history of
    // its own, read from the top. Neither is an edit, so neither reports a change.
    /** @param {KeptFile | null} kept
     * @param {string} text @param {string} name */
    resume(kept, text, name) {
      const next = kept?.state ?? state(text);
      scroll = kept?.scroll ?? { top: 0, left: 0 };
      const settings = next.update({
        effects: [
          editable.reconfigure(readonlyExtension()),
          hint.reconfigure(shownHint ? placeholder(shownHint) : []),
        ],
      }).state;
      if (!view) retained = settings;
      else {
        view.setState(settings);
        setScroll(view.scrollDOM, scroll);
      }
      // The state shown may hold another file's language, or none yet.
      shownLanguage = undefined;
      showLanguage(languageFor(name));
    },
    // Bring the caret into the editor's view, as a landing on the editor does: its room
    // may have shrunk under the caret while the reader stood elsewhere.
    revealCaret,
    // A move by `moveBefore` collapses the native selection in the view it keeps.
    placeSelection() {
      view?.placeSelection();
    },
    connect() {
      if (view) return;
      view = new LeafEditorView({ state: retained, parent });
      setScroll(view.scrollDOM, { top: scroll.top, left: scroll.left });
      resize?.observe(view.scrollDOM);
    },
    disconnect,
  };
}
