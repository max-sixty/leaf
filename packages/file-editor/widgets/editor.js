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
  Annotation,
  ChangeSet,
  Compartment,
  Decoration,
  EditorState,
  Prec,
  StateEffect,
  StateField,
  Transaction,
  EditorView,
  ViewPlugin,
  countColumn,
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
import { diffArrays } from "/vendor/jsdiff.esm.js";

const LeafEditorView = leafEditorView(codemirror);

const theme = EditorView.theme({
  "&": { color: "var(--lf-ink)", backgroundColor: "var(--lf-card)" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--lf-mono)", lineHeight: "24px" },
  ".cm-content": { caretColor: "var(--lf-accent)" },
  // A line's rows after the first hang two columns past its indent (`hangs`), up to the
  // 24 columns a code block's stop at, behind the mark a code block's wrapped rows wear
  // (reading.css, `[data-lf-pre-line]`), so a row a long line wraps onto reads as the
  // rest of that line. Started at the editor's edge, it read as a line of its own, and
  // in YAML as a new top-level key.
  ".cm-line": {
    padding: "0 .85rem",
    position: "relative",
    "--lf-code-hang": "calc(min(var(--lf-code-indent, 0), 22) * 1ch + 2ch)",
    textIndent: "var(--lf-code-hang) hanging",
  },
  ".cm-line::before": {
    content: '""',
    position: "absolute",
    insetBlock: "1lh 0",
    insetInlineStart: "calc(.85rem + var(--lf-code-hang) - 2ch)",
    inlineSize: "1ch",
    background: "var(--lf-code-muted)",
    mask: "var(--lf-wrap-mark) 0 0 / 1ch 1lh repeat-y",
  },
  // A line another writer changed (`written`), tinted and barred in the accent.
  ".cm-line.lf-written": {
    background:
      "linear-gradient(to right, var(--lf-accent) 3px, oklch(from var(--lf-accent) l c h / 0.1) 3px)",
  },
  // Where another writer took whole lines away, a rule in the accent across the gap.
  ".cm-line.lf-written-gap": { boxShadow: "inset 0 2px var(--lf-accent)" },
  ".cm-line.lf-written-gap-below": { boxShadow: "inset 0 -2px var(--lf-accent)" },
  ".cm-line.lf-written-gap.lf-written-gap-below": {
    boxShadow: "inset 0 2px var(--lf-accent), inset 0 -2px var(--lf-accent)",
  },
  ".cm-gutters": {
    backgroundColor: "var(--lf-paper)",
    color: "var(--lf-muted)",
    borderRight: "1px solid var(--lf-rule)",
  },
  ".cm-lineNumbers .cm-gutterElement": {
    padding: "0 .6rem 0 .8rem",
    minWidth: "2.5rem",
  },
  ".cm-activeLine, .cm-activeLineGutter": {
    backgroundColor: "color-mix(in srgb, var(--lf-accent) 6%, transparent)",
  },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--lf-accent)" },
  ".cm-placeholder": { color: "var(--lf-quiet)" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
    { backgroundColor: "color-mix(in srgb, var(--lf-accent) 24%, transparent)" },
  ".cm-matchingBracket": {
    backgroundColor: "color-mix(in srgb, var(--lf-accent) 18%, transparent)",
    outline: "1px solid color-mix(in srgb, var(--lf-accent) 40%, transparent)",
  },
  ".cm-tooltip": {
    backgroundColor: "var(--lf-card)",
    color: "var(--lf-ink)",
    border: "1px solid var(--lf-border)",
  },
  ".cm-tooltip-autocomplete > ul > li[aria-selected]": {
    backgroundColor: "var(--lf-accent)",
    color: "var(--lf-card)",
  },
  "&.cm-merge-b .cm-changedLine, .cm-inlineChangedLine": {
    backgroundColor: "color-mix(in srgb, var(--lf-ok) 9%, transparent)",
  },
  "&.cm-merge-b .cm-changedText": {
    backgroundColor: "color-mix(in srgb, var(--lf-ok) 23%, transparent)",
  },
  ".cm-deletedChunk": {
    backgroundColor: "color-mix(in srgb, var(--lf-danger) 9%, var(--lf-card))",
    padding: ".35rem .85rem",
    borderLeft: "3px solid var(--lf-danger)",
  },
  ".cm-deletedChunk .cm-deletedText": {
    backgroundColor: "color-mix(in srgb, var(--lf-danger) 19%, transparent)",
  },
  ".cm-deletedChunk .cm-deletedLine": { textDecoration: "none", opacity: ".85" },
  ".cm-deletedText": { textDecoration: "line-through" },
  ".cm-changedLineGutter": { backgroundColor: "var(--lf-ok)" },
  ".cm-deletedLineGutter": { backgroundColor: "var(--lf-danger)" },
});

// The theme's code tokens, as code blocks and diffs colour the same names (Leaf's
// token theme, build/entries/syntax/entry.mjs): a key, a type or a tag in
// `--lf-syn-type`, a comment in italic `--lf-syn-comment`.
const highlighting = HighlightStyle.define([
  { tag: tags.heading, color: "var(--lf-accent)", fontWeight: "650" },
  { tag: tags.strong, fontWeight: "650" },
  { tag: tags.emphasis, fontStyle: "italic" },
  {
    tag: [tags.link, tags.url],
    color: "var(--lf-accent)",
    textDecoration: "underline",
  },
  { tag: [tags.monospace, tags.string], color: "var(--lf-syn-string)" },
  { tag: [tags.keyword, tags.modifier], color: "var(--lf-syn-keyword)" },
  { tag: [tags.number, tags.bool], color: "var(--lf-syn-number)" },
  { tag: tags.comment, color: "var(--lf-syn-comment)", fontStyle: "italic" },
  { tag: [tags.meta, tags.processingInstruction], color: "var(--lf-syn-comment)" },
  {
    tag: [tags.propertyName, tags.typeName, tags.labelName],
    color: "var(--lf-syn-type)",
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
        HighlightStyle.define([{ tag: tags.content, color: "var(--lf-syn-string)" }], {
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
// Each line in view states its indent (`--lf-code-indent`), which its wrapped rows hang
// from (the theme's `.cm-line`), as code-lines.js boxes a code block's lines for it:
// CSS can't read a line's leading columns. The indent is the line's leading spaces and
// tabs, in the columns CodeMirror counts for it, as a code block counts it.
/** @param {EditorView} view */
const indents = (view) => {
  const marks = [];
  for (const { from, to } of view.visibleRanges)
    for (let at = from; at <= to;) {
      const { text, from: start, to: end } = view.state.doc.lineAt(at);
      const indent = countColumn(text, view.state.tabSize, text.search(/[^ \t]|$/));
      if (indent)
        marks.push(
          Decoration.line({
            attributes: { style: `--lf-code-indent: ${indent}` },
          }).range(start),
        );
      at = end + 1;
    }
  return Decoration.set(marks);
};
const hangs = ViewPlugin.fromClass(
  class {
    /** @param {EditorView} view */
    constructor(view) {
      this.decorations = indents(view);
    }
    /** @param {import("@codemirror/view").ViewUpdate} update */
    update(update) {
      if (update.docChanged || update.viewportChanged)
        this.decorations = indents(update.view);
    }
  },
  { decorations: (plugin) => plugin.decorations },
);
// The lines the last write from elsewhere changed, such as an agent's: shown until
// the next one replaces them, and each until the reader edits that line, so a reader
// whose file changed under them sees where. A file's first reading marks nothing.
const fromElsewhere = Annotation.define();
/** @type {import("@codemirror/state").StateEffectType<import("@codemirror/view").DecorationSet>} */
const markWritten = StateEffect.define();
const writtenLine = Decoration.line({ class: "lf-written" });
// Where it took whole lines away: the line after the gap, or the last line where the
// gap ends the file.
const gapAbove = Decoration.line({ class: "lf-written-gap" });
const gapBelow = Decoration.line({ class: "lf-written-gap-below" });
const written = StateField.define({
  create: () => Decoration.none,
  update(marks, transaction) {
    for (const effect of transaction.effects)
      if (effect.is(markWritten)) return effect.value;
    if (!transaction.docChanged) return marks;
    marks = marks.map(transaction.changes);
    if (transaction.annotation(fromElsewhere)) return marks;
    // The reader's edit takes the mark off each line it touches.
    const doc = transaction.state.doc;
    /** @type {[number, number][]} */
    const touched = [];
    transaction.changes.iterChangedRanges((_fromA, _toA, from, to) =>
      touched.push([doc.lineAt(from).from, doc.lineAt(to).from]),
    );
    return marks.update({
      filter: (from) => !touched.some(([start, end]) => from >= start && from <= end),
    });
  },
  provide: (field) => EditorView.decorations.from(field),
});
// The marks for a write from elsewhere that took `before` to `after`, read from a diff
// of their lines: each line the write put in, and where a run of its changes took away
// more lines than it put in, the gap they leave, after the lines it put in. The
// changes CodeMirror applies are a diff of characters, which starts and ends wherever
// the two texts stop agreeing, so one change can join and split lines, as a rewrapped
// paragraph's do, and two can meet inside a line neither changed.
/** @param {import("@codemirror/state").Text} before
 * @param {import("@codemirror/state").Text} after */
const writtenMarks = (before, after) => {
  const marks = [];
  let line = 1,
    removed = 0,
    added = 0;
  const closeRun = () => {
    if (removed > added)
      marks.push(
        (line > after.lines ? gapBelow : gapAbove).range(
          after.line(Math.min(line, after.lines)).from,
        ),
      );
    removed = added = 0;
  };
  for (const part of diffArrays(before.toJSON(), after.toJSON())) {
    const { count } = part;
    if (part.removed) removed += count;
    else if (part.added) {
      added += count;
      for (const end = line + count; line < end; line++)
        marks.push(writtenLine.range(after.line(line).from));
    } else {
      closeRun();
      line += count;
    }
  }
  closeRun();
  return Decoration.set(marks, true);
};
// Every editor's undo history, in one compartment the module shares, so a write from
// elsewhere restarts a kept file's history as it restarts the shown one's.
const undoHistory = new Compartment();
// The transactions a write from elsewhere makes of `changes` on `state`: the change,
// not the reader's to undo, marking the lines it changed (or with `mark` false taking
// every mark away), then a new undo history. CodeMirror maps the history it keeps
// through a change it doesn't record, and an earlier edit the change overlaps then
// undoes into neither version: "one" typed over as "user" and then written "agent"
// elsewhere undid to "agonent", which autosave would write to disk. So the edits before
// a write from elsewhere belong to the version it replaced, whether the editor follows
// the write or merges it into a draft, and whether the file is shown or kept.
/** @param {EditorState} state @param {ChangeSet} changes @param {boolean} [mark]
 * @returns {import("@codemirror/state").TransactionSpec[]} */
const writeFromElsewhere = (state, changes, mark = true) => [
  {
    changes,
    effects: [
      undoHistory.reconfigure([]),
      markWritten.of(
        mark ? writtenMarks(state.doc, changes.apply(state.doc)) : Decoration.none,
      ),
    ],
    annotations: [Transaction.addToHistory.of(false), fromElsewhere.of(true)],
  },
  { effects: undoHistory.reconfigure(history()) },
];
/** @param {EditorState} state @param {import("@codemirror/state").TransactionSpec[]} specs */
const applied = (state, specs) =>
  specs.reduce((at, spec) => at.update(spec).state, state);
/** The changes that turn `from` into `to`, in CodeMirror's terms.
 * @param {string} from @param {string} to */
const changesBetween = (from, to) =>
  ChangeSet.of(
    diff(from, to).map((change) => ({
      from: change.fromA,
      to: change.toA,
      insert: to.slice(change.fromB, change.toB),
    })),
    from.length,
  );

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
      state: applied(kept.state, writeFromElsewhere(kept.state, changes)),
    }
  );
}

/** What the editor keeps of a file while another is open, taken to `text`, written
 * elsewhere, as `follow` takes the open file.
 * @param {KeptFile} kept @param {string} text @returns {KeptFile} */
export function followKept(kept, text) {
  const changes = changesBetween(kept.state.doc.toString(), text);
  return {
    ...kept,
    state: applied(kept.state, writeFromElsewhere(kept.state, changes)),
  };
}

/** Create a file editor. External text changes use CodeMirror transactions,
 * mapping selection through the dependency's diff. Taking in text written elsewhere,
 * followed or merged, starts a new undo history (`writeFromElsewhere`).
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
    hint = new Compartment();
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
        written,
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
        hangs,
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
    dispatch({ effects: languageEffect(name) });
  };
  // The effect that gives the state shown `name`'s language where it has loaded, or
  // none until then, loading it to follow.
  /** @param {string | null} name */
  const languageEffect = (name) => {
    shownLanguage = name;
    const ready = name && loaded.get(name);
    if (name && !ready)
      void loadLanguage(name).then((extension) => {
        if (shownLanguage === name)
          dispatch({ effects: language.reconfigure(extension) });
      });
    return language.reconfigure(ready || []);
  };
  // Take the text through `changes`, written elsewhere (`writeFromElsewhere`).
  /** @param {ChangeSet} changes @param {boolean} [mark] */
  const write = (changes, mark) => {
    replacing = true;
    try {
      for (const spec of writeFromElsewhere(reading(), changes, mark)) dispatch(spec);
    } finally {
      replacing = false;
    }
  };
  // Adopt `value` as the file's text; `mark` marks the lines it changed as written
  // elsewhere, and otherwise every mark goes.
  /** @param {string} value @param {boolean} mark */
  const adopt = (value, mark) => {
    if (value === reading().doc.toString()) return;
    write(changesBetween(reading().doc.toString(), value), mark);
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
      adopt(value, false);
    },
    // Take the text to `value`, a version written elsewhere, as `value` does, and mark
    // the lines it changed (`written`).
    /** @param {string} value */
    follow(value) {
      adopt(value, true);
    },
    // Fold `theirs` into the text being edited (`lineMerge`), keeping the reader's
    // selection; say whether it did.
    /** @param {string} base @param {string} theirs */
    merge(base, theirs) {
      const changes = lineMerge(base, reading().doc.toString(), theirs);
      if (!changes) return false;
      write(changes);
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
      // The state shown takes this file's language with its other settings, in the one
      // update, since it may hold another file's or none yet.
      const settings = next.update({
        effects: [
          editable.reconfigure(readonlyExtension()),
          hint.reconfigure(shownHint ? placeholder(shownHint) : []),
          languageEffect(languageFor(name)),
        ],
      }).state;
      if (!view) retained = settings;
      else {
        view.setState(settings);
        setScroll(view.scrollDOM, scroll);
      }
    },
    // Put the caret at the start of line `number`, or the last line where the file is
    // shorter, and bring that line to the middle of the editor's view.
    /** @param {number} number */
    goToLine(number) {
      const doc = reading().doc;
      const { from } = doc.line(Math.min(Math.max(1, number), doc.lines));
      dispatch({
        selection: { anchor: from },
        effects: EditorView.scrollIntoView(from, { y: "center" }),
      });
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
