/* lf-code: the author's code, numbered and coloured, with `lf-note` children standing
 * under the lines they remark on — the annotated-walkthrough shape. The body is code
 * verbatim in a <pre> (data); `hi` highlights line ranges; each note's `at` names the
 * line it is about.
 *
 * A `language-…` class colors it, on a `<code>` inside the `<pre>` as on any code
 * block (`codeLanguage`). A token can span a newline (a docstring, a block comment)
 * and a line is the unit this widget numbers, so the tokens are cut at each
 * newline (tokenLines) rather than the source being colored a line at a time —
 * coloring line by line would restart the tokenizer inside the docstring and
 * read its second line as code.
 *
 * `lines` makes the body an excerpt: the line numbers it quotes, in the grammar `hi`
 * speaks ("1505-1507,1520-1527"). A gutter number is the line's number in its source,
 * a gap between ranges draws an elided row, and every reference into the block — `hi`,
 * a note's `at`, another widget's key — names lines by those numbers. Without `lines`
 * the body is lines 1..N, so a quick snippet reads exactly as before. A line has one
 * number and nothing else to be called by: a driver that wants readable names keeps
 * them in its own vocabulary, where it uses them.
 *
 * Every number from the first shown line to the last addresses a row: its own line,
 * or the elided row standing in for the stretch it falls in. So a left-out line is
 * referenced like any other — `hi` tints the elided row, and a note whose `at` falls
 * there becomes that row's caption, saying what was left out. A note naming a line past
 * either end of the block stands at its foot.
 *
 * `lfElementsFor(key)` answers a reference into the block (`navigateToDatum`) in that
 * same grammar. A number outside the block addresses nothing.
 *
 * The reader can switch wrapping through the code block's command scope (`w`). This is
 * tab-local reading state, kept by widget id across revisions (`KeepInTab`), not a
 * decision. Until the reader chooses, authored presentation remains the default, and
 * the press reads which that is off the drawn line. Paper wraps complete lines
 * regardless of the screen choice.
 *
 * A docked note carries its line's indent (`--lf-code-indent`, as the line does), so
 * the theme stands it under the line's first character. A block with notes offers a
 * mark in its toolbar, beside Copy, and `n` in its scope: Collapse all's fold hides
 * them, named Hide notes, and Expand all's shows them again, named Show 8 notes, so a
 * reader can read the code whole. It is reading state kept as wrapping is, and paper
 * shows the notes whatever the screen's choice. A hidden note's line keeps its number
 * in the accent, so the reader sees where the notes were. The maintainer chose the
 * toolbar, which shows while the pointer or focus is on the block or after a tap,
 * over a word standing above the block, which kept a strip of room over every block
 * with notes. The mark is Leaf's control, drawn only where Leaf runs, since only
 * Leaf's register answers its press.
 *
 * `playhead` is the lines another widget is at, in `hi`'s grammar, or null: Leaf sets
 * it from the `source-lines` output of the widget `for` names (registry `inputs`), and
 * a plain host sets the property itself. The block marks the rows those numbers address
 * (`data-lf-at`). Several excerpts of one file can follow one widget, since a number
 * outside an excerpt marks nothing there.
 *
 * So that a reader watching that widget sees the marked line beside it, the block keeps
 * the first marked line in the box that scrolls it. When the line stands outside a band
 * of that box, from 15% of its height to 70%, the block sets the box's scroll at once
 * so the line stands a third of the way down, with the lines that run next below it.
 * Where that box is the page, or the page doesn't render the line, as in a closed
 * disclosure, it moves nothing. The first value a block is handed only marks its line,
 * as an arrival moves nothing, and the block follows from the next.
 *
 * The reader's hand inside the box, a press, wheel, touch or key there, stops the
 * following, so the box holds still while they read or scroll it, and their hand on
 * the widget `for` names starts it again for the blocks that name it. Rejected:
 * following again once a marked line came into the reader's view, which took the pane
 * from a reader who had scrolled up to read the lede as soon as the film lit a line
 * beside it.
 *
 * How it is drawn: a decorating widget (lf-options.js, "How it is drawn"). An Effect
 * UI component (runtime/effect-widget.js) draws the numbered lines, the elided rows and
 * the toolbar in the element's shadow root, and the theme styles them by their shadow
 * parts (code.css): `frame`, `source`, each `row` (a `line` or an `elided` row, with
 * `hi`, `at` and `folded` for the states a row is in, and `wrap` or `scroll` for the
 * reader's choice), each `note` and `caption` holding a note, and `bar`. The light DOM
 * stays the author's: the authored <pre> is the source the lines are drawn from and
 * shows nowhere, and each note stays where it was written, shown under its line
 * through a slot of its own, which a mount assigns it to (`slotAssignment: "manual"`),
 * so its words stay the author's and quotable. A comment on the code anchors on the
 * drawn lines' text, which the registry's `shadow` brings into the page's reading.
 * The tokenizer is Shiki's (`syntax`), run by a mount on the source (`Color`), whose
 * coloured lines come back as a message; until they do, the block draws its source
 * uncoloured, and it holds Leaf's presentation for them (`pending-task`), so the first
 * anchor pass reads the lines as they stand.
 *
 * It imports only the helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` draws it too: coloured, numbered by its own stylesheet where
 * the page loads it, and with nothing of Leaf's. What Leaf adds it reads from outside:
 * the wrap and notes keys as the element's `lfCommands`, the Copy control from the
 * block's `data-lf-copy`, standing in the block's toolbar (`lfBar`) where it has one,
 * and the word a listener hears on a highlighted line from its `data-lf-quiet`. */
import {
  Command,
  Component,
  Effect,
  Equal,
  Html,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import { onUserInput, scrollersOf, tabStore } from "/runtime/portable-api.js";
import { bodyText } from "/runtime/lib/data-body.js";
import { nameAction, offerActionElement, offerAttributes } from "/runtime/lib/controls.js";
import {
  codeLanguage,
  synAttributes,
  syntax,
  tokenLines,
} from "/runtime/lib/syntax-tokens.js";
import { scrollMoves } from "/runtime/lib/scroll-range.js";
import { PendingTaskEvent } from "/runtime/lib/pending-task.js";
import { layoutChanged } from "/runtime/lib/widget-events.js";
import { KeepInTab } from "/runtime/widget-services.js";
import { declare, defineWidget, widgetProps } from "/runtime/effect-widget.js";

// Which of the reader's gestures last had their hand on or inside each element, counted
// from the first. A block follows in its box unless their hand was in the box after it
// was last on the widget the block follows (see the header), so a hand in the box holds
// it from the page's load, before any block there has followed a line. The hand is read
// from the document's one reading of the reader's inputs (`onUserInput`), which binds
// no key, and is one of its gestures: an `input` follows a gesture already counted, and
// a script that moves the followed widget dispatches one with no reader behind it.
const hands = new WeakMap<EventTarget, number>();
let gestures = 0;
const HAND = new Set(["pointerdown", "wheel", "touchstart", "keydown"]);
onUserInput((event: Event) => {
  if (!HAND.has(event.type)) return;
  gestures += 1;
  for (const node of event.composedPath()) hands.set(node, gestures);
});

// "3-5,8" → [[3, 5], [8, 8]].
const spans = (spec: string | null | undefined): [number, number][] =>
  (spec ? spec.split(",") : []).map((part) => {
    const [start, end] = part.split("-");
    const from = Number(start);
    return [from, end === undefined ? from : Number(end)];
  });

// Whether a range spec names any of the lines lo..hi: one line, or the stretch an
// elided row stands for. A range may run across a gap in an excerpt, and then
// addresses the lines on either side of it and the elided row between.
const within = (spec: string | null | undefined) => {
  const ranges = spans(spec);
  return (lo: number, hi = lo) => ranges.some(([from, to]) => from <= hi && lo <= to);
};

// How many columns a line's leading whitespace takes, a tab reaching the next stop of
// eight (the <pre>'s tab-size).
const indentColumns = (tokens: readonly Token[]) => {
  const leading = tokens
    .map((token) => token.text)
    .join("")
    .replace(/[^ \t][\s\S]*/, "");
  let columns = 0;
  for (const char of leading)
    columns = char === "\t" ? columns - (columns % 8) + 8 : columns + 1;
  return columns;
};

// The numbers the body's lines carry, in body order: the authored `lines` ranges, one
// number per body line, or 1 to N without them. A body longer than its ranges goes on
// counting from the last number, and ranges past the body's end number nothing.
// Each range is walked only as far as the body needs, so a range far longer than the
// body costs nothing.
function* numbering(spec: string | null): Generator<number, never> {
  let last = 0;
  for (const [from, to] of spans(spec))
    for (let n = from; n <= to; n++) {
      last = n;
      yield n;
    }
  while (true) yield ++last;
}

const Token = Schema.Struct({
  text: Schema.String,
  style: Schema.Record(Schema.String, Schema.String),
});
type Token = typeof Token.Type;
const Lines = Schema.Array(Schema.Array(Token));
type Lines = typeof Lines.Type;
// The tokens' lines, each style a record of CSS declarations, as Shiki's `TokenStyles` is.
const linesOf = (tokens: Parameters<typeof tokenLines>[0]) =>
  tokenLines(tokens) as unknown as Lines;

const Note = Schema.Struct({ at: Schema.Number, note: Schema.instanceOf(Element) });
type Note = typeof Note.Type;

type Row =
  | { kind: "line"; n: number; tokens: readonly Token[]; indent: number; notes: Element[] }
  | { kind: "elided"; from: number; to: number; captions: Element[] };

// The block's rows in order: each line with the notes that stand under it, and an
// elided row for each gap between the numbers, captioned by the notes whose `at` falls
// in it. A note naming a line past either end of the block stands at its foot.
export function rowsOf(lines: Lines, spec: string | null, notes: readonly Note[]) {
  const numbers = numbering(spec);
  const byLine = Map.groupBy(notes, ({ at }) => at);
  const rows: Row[] = [];
  const placed = new Set<Element>();
  let previous: number | null = null;
  for (const tokens of lines) {
    const n = numbers.next().value;
    if (previous !== null && n > previous + 1) {
      const [from, to] = [previous + 1, n - 1];
      const captions = [...byLine]
        .filter(([at]) => from <= at && at <= to)
        .sort(([a], [b]) => a - b)
        .flatMap(([, list]) => list.map(({ note }) => note));
      for (const note of captions) placed.add(note);
      rows.push({ kind: "elided", from, to, captions });
    }
    const docked = (byLine.get(n) ?? []).map(({ note }) => note);
    for (const note of docked) placed.add(note);
    rows.push({ kind: "line", n, tokens, indent: indentColumns(tokens), notes: docked });
    previous = n;
  }
  const foot = notes.map(({ note }) => note).filter((note) => !placed.has(note));
  return { rows, foot, last: previous };
}

// The rows a range addresses, among those drawn under `frame`: a numbered line by its
// number, an elided row by the stretch it stands for.
const rowsAt = (frame: Element, key: string | null | undefined) => {
  const addressed = within(key);
  return [...frame.querySelectorAll<HTMLElement>(".lf-code-line, .lf-code-elided")].filter(
    (row) =>
      row.classList.contains("lf-code-elided")
        ? addressed(Number(row.dataset.lfFrom), Number(row.dataset.lfTo))
        : addressed(Number(row.dataset.lfLine)),
  );
};

const CodeProps = Schema.Struct({
  ...widgetProps,
  id: Schema.String,
  source: Schema.String,
  lang: Schema.NullOr(Schema.String),
  lines: Schema.NullOr(Schema.String),
  hi: Schema.NullOr(Schema.String),
  follows: Schema.NullOr(Schema.String),
  notes: Schema.Array(Note),
  interactive: Schema.Boolean,
  savedWrap: Schema.NullOr(Schema.String),
  savedNotes: Schema.NullOr(Schema.String),
  playhead: Schema.optional(Schema.NullOr(Schema.String)),
});
// `colored` is the source's lines as the tokenizer coloured them, null until it has;
// `wrap` is the reader's choice of wrapping, null until they make one.
const CodeModel = Schema.Struct({
  colored: Schema.NullOr(Lines),
  wrap: Schema.NullOr(Schema.Boolean),
  notesShown: Schema.Boolean,
});
export const CodeMessage = UiSchema.TaggedEnum({
  Colored: { lines: Lines },
  // `wrapped` is whether the lines wrapped as the reader pressed, the authored
  // presentation's choice until they made one.
  ToggledWrap: { wrapped: Schema.Boolean },
  ToggledNotes: {},
});

const wrapKey = (id: string) => `code-wrap:${id}`;
const notesKey = (id: string) => `code-notes:${id}`;
const parts = (...names: (string | false | null | undefined)[]) =>
  names.filter(Boolean).join(" ");
const noteCount = (count: number) => `Show ${count} note${count === 1 ? "" : "s"}`;

// The source coloured by the tokenizer, sent back as the coloured lines. The block
// holds Leaf's presentation until they are drawn: their message draws in the flush it
// starts, a microtask after the body ends, so a task after that sees them drawn.
const Color = Mount.make(
  "Color",
  { args: { source: Schema.String, lang: Schema.String } },
  (pre: HTMLElement, { source, lang }) =>
    Effect.suspend(() => {
      let settle = () => {};
      const settled = new Promise<void>((resolve) => (settle = resolve));
      pre.dispatchEvent(new PendingTaskEvent(settled));
      return Effect.promise(() => syntax(source, lang)).pipe(
        Effect.map(({ tokens }) => CodeMessage.Colored({ lines: linesOf(tokens) })),
        Effect.ensuring(Effect.sync(() => setTimeout(settle))),
      );
    }),
);

// A slot shows the one note assigned to it.
const Assign = Mount.make(
  "Assign",
  { args: { note: Schema.instanceOf(Element) } },
  (slot: HTMLSlotElement, { note }) =>
    Effect.sync(() => {
      slot.assign(note);
      return Component.noop;
    }),
);

// The toolbar's notes mark, whose symbol and name follow whether the notes show.
const NotesMark = Mount.make(
  "NotesMark",
  { args: { shown: Schema.Boolean, count: Schema.Number } },
  (button: HTMLButtonElement, args, changes) => {
    const name = ({ shown, count }: typeof args) =>
      nameAction(button, shown ? "collapse-all" : "expand-all", {
        label: shown ? "Hide notes" : noteCount(count),
        className: "lf-mark-icon",
      });
    offerActionElement(button, "mark", "lf-code-notes-toggle", "Hide notes", {
      action: "collapse-all",
    });
    name(args);
    return Stream.runForEach(changes, (next) => Effect.sync(() => name(next))).pipe(
      Effect.as(Component.noop),
    );
  },
);

// What Leaf reads off the element, and the work after a draw: the block's keys and the
// rows a key into it addresses, the toolbar Copy joins, the reader's sideways scroll put
// back when they unwrap, and the marked line kept in view (see the header).
const Reading = Mount.makeStream(
  "Reading",
  {
    args: {
      follows: Schema.NullOr(Schema.String),
      playhead: Schema.NullOr(Schema.String),
      wrap: Schema.NullOr(Schema.Boolean),
      notesShown: Schema.Boolean,
    },
  },
  (frame: HTMLElement, args, changes) =>
    Stream.callback<typeof CodeMessage.Type>((queue) =>
      Effect.gen(function* () {
        const send = (message: typeof CodeMessage.Type) =>
          Queue.offerUnsafe(queue, message);
        const host = (frame.getRootNode() as ShadowRoot).host as HTMLElement;
        const pre = frame.querySelector<HTMLElement>(".lf-code-source")!;
        const toggle = frame.querySelector<HTMLElement>(".lf-code-notes-toggle");
        const bar = frame.querySelector<HTMLElement>(".lf-code-bar");
        if (bar) pre.lfBar = bar;
        let current = args;
        // The reader's sideways scroll as they wrapped the lines, put back when they
        // unwrap: wrapped, the block stood at its start.
        let horizontal = 0;
        // The drawn line says whether lines wrap, the reader's choice or the page's.
        const wrapped = () => {
          const line = pre.querySelector(".lf-code-line");
          return !!line && getComputedStyle(line).whiteSpace !== "pre";
        };
        declare(frame, {
          lfElementsFor: (key: string) => rowsAt(frame, key),
          lfCommands: {
            title: "On a code block",
            rows: [
              {
                id: "code.wrap",
                keys: ["w"],
                title: () => (wrapped() ? "unwrap lines" : "wrap lines"),
                run: () => {
                  const was = wrapped();
                  if (!was) horizontal = pre.scrollLeft;
                  send(CodeMessage.ToggledWrap({ wrapped: was }));
                },
              },
              ...(toggle
                ? [
                    {
                      id: "code.notes",
                      keys: ["n"],
                      title: () => (current.notesShown ? "hide notes" : "show notes"),
                      control: toggle,
                      touch: false as const,
                      run: () => send(CodeMessage.ToggledNotes()),
                    },
                  ]
                : []),
            ],
          },
        });
        // The first value only marks its line, as an arrival moves nothing.
        let arrived = args.playhead !== null;
        yield* Effect.forkScoped(
          Stream.runForEach(changes, (next) =>
            Effect.sync(() => {
              const was = current;
              current = next;
              if (next.wrap !== was.wrap || next.notesShown !== was.notesShown) {
                if (next.wrap === false && horizontal)
                  pre.scrollTo({ left: horizontal, behavior: "instant" });
                layoutChanged(host);
              }
              if (next.playhead !== was.playhead) {
                if (arrived) follow(frame, host, next);
                arrived ||= next.playhead !== null;
              }
            }),
          ),
        );
      }),
    ),
);

// Keep the first marked line in the band of the box that scrolls it (see the header).
function follow(
  frame: HTMLElement,
  host: HTMLElement,
  { follows, playhead }: { follows: string | null; playhead: string | null },
) {
  const [row] = rowsAt(frame, playhead);
  // A row the page doesn't render, as in a closed disclosure, has no place to bring
  // into view.
  if (!row?.checkVisibility()) return;
  const [scroller] = scrollersOf(row);
  if (!scroller || scroller === document.scrollingElement) return;
  const followed =
    follows && (host.getRootNode() as Document | ShadowRoot).getElementById(follows);
  const resumed = (followed && hands.get(followed)) || 0;
  if ((hands.get(scroller) ?? 0) > resumed) return;
  const box = scroller.getBoundingClientRect();
  const { top, bottom } = row.getBoundingClientRect();
  if (top >= box.top + box.height * 0.15 && bottom <= box.top + box.height * 0.7) return;
  const to = scroller.scrollTop + top - box.top - box.height / 3;
  if (scrollMoves(scroller, { top: to }))
    scroller.scrollTo({ top: to, behavior: "instant" });
}

export const Code = Html.component({
  name: "Code",
  props: CodeProps,
  model: CodeModel,
  message: CodeMessage,
}).make({
  init: ($) =>
    $.set({
      colored: null,
      wrap: $.props.savedWrap === null ? null : $.props.savedWrap === "true",
      notesShown: $.props.savedNotes !== "hidden",
    }),
  update: {
    Colored: ($, { lines }) => $.evolve({ colored: lines }),
    ToggledWrap: ($, { wrapped }) =>
      $.evolve({ wrap: !wrapped }).run(
        KeepInTab.make({ key: wrapKey($.props.id), value: String(!wrapped) }).pipe(
          Command.asNoop,
        ),
      ),
    ToggledNotes: ($) => {
      const shown = !$.model.notesShown;
      return $.evolve({ notesShown: shown }).run(
        KeepInTab.make({
          key: notesKey($.props.id),
          value: shown ? "shown" : "hidden",
        }).pipe(Command.asNoop),
      );
    },
  },
  view: (h, model) => {
    const { source, lang, notes, interactive, follows } = h.props;
    const playhead = h.props.playhead ?? null;
    // One representation either way: an uncolored block is the whole source as a
    // single unstyled token, so the rows have one shape to draw.
    const lines = model.colored ?? linesOf([{ text: source, style: {} }]);
    const { rows, foot, last } = rowsOf(lines, h.props.lines, notes);
    const hi = within(h.props.hi);
    const at = within(playhead);
    const folded = !model.notesShown && "folded";
    const reading = model.wrap === null ? null : model.wrap ? "wrap" : "scroll";
    const marks = (highlighted: boolean) => ({
      // The tint says "this is the line" to the eye and nothing to a user listening,
      // who is handed the whole block with no idea which of it the note beside it is
      // about. A word per highlighted line rather than one at the top saying which
      // numbers: the numbers are painted from data-lf-line, into no text node on
      // purpose — a line number in the text would be a line number in the clipboard —
      // so "lines 3 to 4" would name something the user cannot hear. Said per line, it
      // arrives where it is true. The one word rides the same clip as every other
      // quiet word, out of the selection with it, so a copied block is still the
      // source and nothing else. Leaf writes it from the declaration, since only
      // Leaf's theme keeps it off the screen.
      ...(highlighted && { "data-lf-hi": "", "data-lf-quiet": "highlighted" }),
    });
    // A note stands in a slot of its own, under its line in that line's indent, or at
    // the block's foot; it is moved nowhere, so the authored element keeps its text
    // and id.
    const noteBox = (note: Element, key: string, indent = 0) =>
      h.span
        .key(key)
        .class("lf-code-note")
        .attr("part", parts("note", folded))
        .attr("style", indent ? `--lf-code-indent: ${indent}` : undefined)
        .children(h.slot.onMount(Assign({ note })));
    const drawn = rows.flatMap((row) => {
      if (row.kind === "elided") {
        const { from, to } = row;
        const count = to - from + 1;
        const lit = hi(from, to);
        // The row standing for the lines an excerpt leaves out. Its count is painted
        // from the attribute, as the gutter's numbers are, so a copied excerpt is
        // still only source and no passage anchors on text the author never wrote. A
        // note docked in the stretch is the row's caption, shown in whole, so its
        // authored text stays quotable.
        return [
          h.span
            .key(`elided:${from}`)
            .class("lf-code-elided")
            .attr("part", parts("row elided", lit && "hi", at(from, to) && "at"))
            .attr("data-lf-from", String(from))
            .attr("data-lf-to", String(to))
            .attr("data-lf-elided", `${count} line${count === 1 ? "" : "s"}`)
            .attr("data-lf-at", at(from, to) ? "" : undefined)
            .attrs(marks(lit))
            .children(
              ...row.captions.map((note, index) =>
                h.span
                  .key(`caption:${index}`)
                  .class("lf-code-caption")
                  .attr("part", parts("caption", folded))
                  .children(h.slot.onMount(Assign({ note }))),
              ),
            ),
        ];
      }
      const { n, tokens, indent } = row;
      return [
        // A line too long for the frame wraps, and its later rows hang from its own
        // indent (the theme's `--lf-code-indent`), so a wrapped line keeps its place in
        // the code's structure.
        h.span
          .key(`line:${n}`)
          .class("lf-code-line")
          .attr(
            "part",
            parts(
              "row line",
              hi(n) && "hi",
              at(n) && "at",
              row.notes.length > 0 && folded,
              reading,
            ),
          )
          .attr("data-lf-line", String(n))
          .attr("data-lf-at", at(n) ? "" : undefined)
          .attr("style", indent ? `--lf-code-indent: ${indent}` : undefined)
          .attrs(marks(hi(n)))
          .children(
            ...tokens.map(({ text, style }) => {
              const attributes = synAttributes(style);
              return attributes ? h.span.attrs(attributes).children(text) : text;
            }),
            "\n",
          ),
        ...row.notes.map((note, index) => noteBox(note, `note:${n}:${index}`, indent)),
      ];
    });
    const toolbar = interactive && notes.length > 0;
    const pre = h.pre
      .key("source")
          .class("lf-code-source")
          .attr("part", "source")
          // Reading commands remain reachable when wrapping removes overflow.
          .attr("data-lf-carry", "source")
          .attr("tabindex", "0")
          // The gutter fits the widest number, so an excerpt from deep in a file keeps
          // its code aligned with its notes.
          .attr("style", `--lf-code-digits: ${String(last).length}`)
          // Copied as the source the lines were drawn from, never as the lines' text,
          // which carries the notes docked among them.
          .attr("data-lf-copy", "code")
          .prop("lfCopy", () => source)
          .children(
            ...drawn,
            ...foot.map((note, index) => noteBox(note, `foot:${index}`)),
          );
    return h.div
      .class("lf-code-frame")
      .attr("part", "frame")
      .children(
        lang ? pre.onMount(Color({ source, lang })) : pre,
        // Copy joins the mark here (`lfBar`), which the theme stands in the block's
        // corner and shows as it would show a lone Copy; its marks join into one
        // toolbar (controls.css, `data-lf-joined`).
        toolbar
          ? h.div
              .key("bar")
              .attrs(offerAttributes("div", "lf-code-bar lf-mark-bar"))
              .attr("part", "bar")
              .attr("data-lf-joined", "")
              .children(
                // Its press is the notes key's: the scope names the mark as that key's
                // control, and Leaf's register runs the key when it is pressed.
                h.button
                  .key("notes")
                  .onMount(
                    NotesMark({ shown: model.notesShown, count: notes.length }),
                  ),
              )
          : null,
      )
      .onMount(
        Reading({ follows, playhead, wrap: model.wrap, notesShown: model.notesShown }),
      );
  },
});

defineWidget("lf-code", Code, {
  shadow: true,
  slotAssignment: "manual",
  properties: ["playhead"],
  inputs: (element) => ({
    id: element.id,
    source: bodyText(element),
    lang: codeLanguage(element) ?? null,
    lines: element.getAttribute("lines"),
    hi: element.getAttribute("hi"),
    follows: element.getAttribute("for"),
    // The code is the <pre>'s and nothing else's; notes are its siblings and say which
    // line they are about, so a note never sits between two halves of the source and
    // there is no interrupted-line arithmetic to get right. Each note is the same
    // input only as itself (`Equal.byReferenceUnsafe`).
    notes: [...element.querySelectorAll(":scope > lf-note")].map((note) => ({
      at: Number(note.getAttribute("at")),
      note: Equal.byReferenceUnsafe(note),
    })),
    interactive: document.documentElement.hasAttribute("data-lf-interactive"),
    savedWrap: tabStore.get(wrapKey(element.id)),
    savedNotes: tabStore.get(notesKey(element.id)),
  }),
});
