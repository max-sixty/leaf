/** CodeMirror owns editing, selection, history and conflict presentation.
 * The surrounding widget alone owns file revisions and disk writes.
 */
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
} from "../vendor/extensions.esm.js";

const theme = EditorView.theme({
  "&": { color: "var(--ink)", backgroundColor: "var(--card)", fontSize: ".9rem" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "24px" },
  ".cm-content": { padding: "1rem 0", caretColor: "var(--accent)" },
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

const highlighting = HighlightStyle.define([
  { tag: tags.heading, color: "var(--accent)", fontWeight: "650" },
  { tag: tags.strong, fontWeight: "650" },
  { tag: tags.emphasis, fontStyle: "italic" },
  { tag: [tags.link, tags.url], color: "var(--accent)", textDecoration: "underline" },
  { tag: [tags.monospace, tags.string], color: "light-dark(#7b4432, #dca68f)" },
  { tag: [tags.keyword, tags.modifier], color: "light-dark(#76508b, #c7a4dd)" },
  { tag: [tags.number, tags.bool], color: "light-dark(#7d592a, #d3b77c)" },
  { tag: tags.comment, color: "var(--muted)" },
  { tag: [tags.meta, tags.processingInstruction], color: "var(--muted)" },
]);

/** Create a file editor. External text changes use CodeMirror transactions,
 * mapping selection and local undo history through the dependency's diff.
 */
export function createEditor(
  parent,
  {
    text = "",
    readOnly = false,
    label = "File contents",
    description = "Changes save automatically. If the file changes elsewhere, review both versions before saving.",
    onChange,
    onSave,
  } = {},
) {
  const editable = new Compartment(),
    language = new Compartment(),
    merge = new Compartment();
  let readonly = readOnly,
    markdown = false,
    conflict = null,
    replacing = false;
  const readonlyExtension = () => [
    EditorState.readOnly.of(readonly),
    EditorView.editable.of(!readonly),
    EditorView.contentAttributes.of({
      "aria-readonly": String(readonly),
      ...(readonly ? { tabindex: "0" } : {}),
    }),
  ];
  const mergeExtension = () =>
    conflict === null
      ? []
      : unifiedMergeView({
          original: conflict,
          mergeControls: false,
          allowInlineDiffs: true,
        });
  const state = (value) =>
    EditorState.create({
      doc: value,
      extensions: [
        history(),
        drawSelection(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        language.of([]),
        syntaxHighlighting(highlighting),
        theme,
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightActiveLine(),
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
        merge.of(mergeExtension()),
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
  let retained = state(text);
  let view = new EditorView({ state: retained, parent });
  let scroll = { top: 0, left: 0 };
  const reading = () => view?.state ?? retained;
  const dispatch = (spec) => {
    if (view) view.dispatch(spec);
    else retained = retained.update(spec).state;
  };
  const disconnect = () => {
    if (!view) return;
    retained = view.state;
    scroll = { top: view.scrollDOM.scrollTop, left: view.scrollDOM.scrollLeft };
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
          annotations: Transaction.addToHistory.of(false),
        });
      } finally {
        replacing = false;
      }
    },
    get readOnly() {
      return readonly;
    },
    set readOnly(value) {
      if (readonly === value) return;
      readonly = value;
      dispatch({ effects: editable.reconfigure(readonlyExtension()) });
    },
    get contentDOM() {
      return view.contentDOM;
    },
    setLabel(label) {
      const next = /\.(md|markdown)$/i.test(label);
      if (next === markdown) return;
      markdown = next;
      dispatch({
        effects: language.reconfigure(
          markdown ? new LanguageSupport(markdownLanguage) : [],
        ),
      });
    },
    setConflict(value) {
      if (conflict === value) return;
      const previous = conflict;
      conflict = value;
      if (previous !== null && value !== null) {
        const originalLength = getOriginalDoc(reading()).length;
        const changes = ChangeSet.of(
          { from: 0, to: originalLength, insert: value },
          originalLength,
        );
        dispatch({ effects: originalDocChangeEffect(reading(), changes) });
      } else dispatch({ effects: merge.reconfigure(mergeExtension()) });
    },
    connect() {
      if (view) return;
      view = new EditorView({ state: retained, parent });
      view.scrollDOM.scrollTop = scroll.top;
      view.scrollDOM.scrollLeft = scroll.left;
    },
    disconnect,
  };
}
