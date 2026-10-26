/* The kernel registry's facts, as the browser reads them.

   The kernel registry beside this module holds the facts no layer changes. Python
   reads it from the serving Leaf's runtime (`leaf.registry.kernel`), and so does the
   browser: a page runs the serving Leaf's runtime (`runtime_selection`), and no layer
   can replace one of its files. A page's own `/registry.json` is its composed
   vocabulary (`registry.js`), whose copy of these facts came from the Leaf that
   vendored it, so the runtime doesn't read them there.

   Imported as a JSON module, the table is part of the module graph: it has arrived
   before any module here evaluates, so the pure folds read it synchronously. The
   compiled kernel holds this module's exports as literals rather than the whole
   table (`build/runtime-bundle.mjs`, `kernelFacts`), and records the table's hash, so
   after an edit an install serves the source modules, which read it here, until the
   kernel is rebuilt. Either way no build stands between an edit and either reader. */
import kernel from "./kernel-registry.json" with { type: "json" };

const { collapse, blocks, context } = kernel.$passages;
// How a page turns into text (`leaf/passages.py`): a run of these characters is one
// space, each of these tags is one block, and an anchor starts with this much context
// on each side of its quote. Escaped, since a character class gives `]`, `\`, `^` and
// `-` meanings of their own.
const escaped = [...collapse]
  .map((ch) => `\\u${ch.codePointAt(0).toString(16).padStart(4, "0")}`)
  .join("");
export const COLLAPSE = new RegExp(`[${escaped}]+`, "g");
export const TEXT_BLOCK = blocks.join(",");
export const CONTEXT = context;

// A widget's tag, which tells a widget declaration from an idiom selector.
export const WIDGET_NAME = new RegExp(`^${kernel.$names.widget}$`);

// The declared marks and the attribute each is painted as, which the runtime paints on
// a message it renders and reads by name.
const { description: _description, ...declaredMarks } = kernel.$marks;
/** @type {Record<string, {paint: string, message: boolean, authored?: string,
 *   authored_on?: string, presence?: boolean}>} */
export const marks = declaredMarks;

const kinds = Object.entries(kernel.$events.kinds);
// The kinds said in a thread, and each widget kind with the side that writes the
// x-state verb it carries. `contract-types.mjs` derives the matching types.
export const MESSAGE_KINDS = new Set(
  kinds.filter(([, kind]) => "message" in kind && kind.message).map(([name]) => name),
);
export const VERB_WRITERS = Object.fromEntries(
  kinds.flatMap(([name, kind]) =>
    "verb_writer" in kind ? [[name, kind.verb_writer]] : [],
  ),
);

// The schema admission holds a comment's drawing to, which bounds a draft
// (`composing/drawing-record.js`).
export const drawingSchema = kernel.$events.kinds.comment.record.properties.drawing;

// The composer draft's format, named for the protocol at which its shape last
// changed, as `state.Record` names a record's.
export const DRAFT_FORMAT = `leaf-draft/${kernel.$events.draft.since}`;
