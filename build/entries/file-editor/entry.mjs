export {
  Decoration,
  Direction,
  EditorView,
  ViewPlugin,
  crosshairCursor,
  drawSelection,
  dropCursor,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
  placeholder,
  rectangularSelection,
} from "@codemirror/view";
export {
  Annotation,
  ChangeSet,
  Compartment,
  EditorState,
  Prec,
  StateEffect,
  StateField,
  Transaction,
  countColumn,
} from "@codemirror/state";
export { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
export {
  HighlightStyle,
  StreamLanguage,
  bracketMatching,
  indentOnInput,
  syntaxHighlighting,
} from "@codemirror/language";
export { Tag } from "@lezer/highlight";
export {
  diff,
  unifiedMergeView,
  getOriginalDoc,
  originalDocChangeEffect,
} from "@codemirror/merge";
export {
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
  completionKeymap,
} from "@codemirror/autocomplete";
