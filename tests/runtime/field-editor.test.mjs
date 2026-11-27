/* The field's own keys, whether its Markdown reads as a message or as the Markdown file
   a body displays: Return keeps code's indentation and native editability, keys at the
   edge of a line's shown words act on the blocks the field shows, and a seeded fuzzer
   holds every key to what the field promises over generated drafts. */
import assert from "node:assert/strict";
import process from "node:process";
import test from "node:test";

import {
  loadMarkdown,
  markdownWords,
  placedMarkdownTokens,
  renderMarkdown,
} from "/runtime/lib/markdown.js";
import { loadFieldEditor } from "/runtime/annotations/composing/field-editor.js";
import { keymap } from "/vendor/codemirror.esm.js";

import { random } from "./seeded.mjs";

/** Press Enter with the caret after `code` in `source`, returning the press's result
 * and the words after it. */
async function enterAfterCode(source, { message, readOnly = false }) {
  const { fieldState } = await loadFieldEditor();
  const caret = source.indexOf("code") + "code".length;
  const state = fieldState(
    { base: source, text: source, anchor: caret, head: caret, steps: [] },
    {
      typed: (_native, insert) => insert(),
      returned: () => true,
      oneLine: () => false,
      message: () => message,
      revealed: () => {},
      focused: () => {},
      readOnly,
      attributes: {},
    },
  );
  const enter = state
    .facet(keymap)
    .flat()
    .find(({ key }) => key === "Enter");
  assert.ok(enter?.run);
  let dispatched = 0;
  const view = {
    state,
    dispatch(transaction) {
      dispatched++;
      view.state = transaction.state;
    },
  };
  const handled = enter.run(view);
  assert.equal(dispatched, handled ? 1 : 0);
  return { handled, words: view.state.doc.toString() };
}

for (const message of [true, false]) {
  for (const readOnly of [false, true]) {
    test(`Enter ${readOnly ? "refuses a read-only" : "keeps indentation in an editable"} ${message ? "draft" : "file"} code fence`, async () => {
      const source = "```\n    code\n```";
      const { handled, words } = await enterAfterCode(source, {
        message,
        readOnly,
      });
      assert.equal(handled, !readOnly);
      assert.equal(words, readOnly ? source : "```\n    code\n    \n```");
    });
  }
}

test("Enter continues the indented code a Markdown body reads, as a file does", async () => {
  // The field reads its words as the body it edits does, where four spaces after a
  // blank line open code, so Return writes the code's next line rather than a break.
  assert.equal(await loadMarkdown(), true);
  const source = "Run:\n\n    code";
  assert.deepEqual(await enterAfterCode(source, { message: false }), {
    handled: true,
    words: "Run:\n\n    code\n    ",
  });
});

test("read-only fields keep paragraph and list words when Return is pressed", async () => {
  const { fieldState } = await loadFieldEditor();
  for (const [source, message] of [
    ["hello world", false],
    ["- hello", true],
  ]) {
    for (const key of ["Enter", "Shift-Enter"]) {
      const state = fieldState(
        {
          base: source,
          text: source,
          anchor: source.length,
          head: source.length,
          steps: [],
        },
        {
          typed: (_native, insert) => insert(),
          returned: () => true,
          oneLine: () => false,
          message: () => message,
          revealed: () => {},
          focused: () => {},
          readOnly: true,
          attributes: {},
        },
      );
      const view = {
        state,
        dispatch(transaction) {
          view.state = transaction.state ?? view.state.update(transaction).state;
        },
      };
      for (const binding of state.facet(keymap).flat())
        if (binding.key === key && binding.run?.(view)) break;
      assert.equal(view.state.doc.toString(), source, `${key} in ${source}`);
    }
  }
});

/** A draft's field, its keys pressed as the editor's bindings take them and its typing
 * and pastes as CodeMirror dispatches them, in a view that knows no layout: a vertical
 * step keeps the column on the line beside, carrying it as CodeMirror carries its goal,
 * and stays put at the draft's ends. */
async function draftField(source, caret = source.length, message = true) {
  const { fieldState } = await loadFieldEditor();
  const { EditorSelection } = await import("/vendor/codemirror.esm.js");
  const view = {
    state: fieldState(
      { base: source, text: source, anchor: caret, head: caret, steps: [] },
      {
        typed: (_native, insert) => insert(),
        returned: () => true,
        oneLine: () => false,
        message: () => message,
        revealed: () => {},
        focused: () => {},
        readOnly: false,
        attributes: {},
      },
    ),
    dispatch(...specs) {
      for (const spec of specs)
        view.state = spec.state ?? view.state.update(spec).state;
    },
    lineBlockAt(at) {
      const line = view.state.doc.lineAt(at);
      return { from: line.from, to: line.to, top: line.number, height: 1 };
    },
    moveVertically(range, forward) {
      const { doc } = view.state;
      const line = doc.lineAt(range.head);
      if (line.number === (forward ? doc.lines : 1))
        return EditorSelection.cursor(forward ? line.to : line.from);
      const goal = range.goalColumn ?? range.head - line.from;
      const next = doc.line(line.number + (forward ? 1 : -1));
      return EditorSelection.cursor(
        Math.min(next.from + goal, next.to),
        0,
        undefined,
        goal,
      );
    },
  };
  /** @param {string} key, Shift+Tab as `Shift-Tab` */
  const press = (key) => {
    const [name, shift] = key === "Shift-Tab" ? ["Tab", true] : [key, false];
    return view.state
      .facet(keymap)
      .flat()
      .filter((binding) => binding.key === name)
      .some((binding) => (shift ? binding.shift : binding.run)?.(view));
  };
  /** @param {string} text @param {string} userEvent */
  const put = (text, userEvent) => {
    const { from, to } = view.state.selection.main;
    view.dispatch({
      changes: { from, to, insert: text },
      selection: { anchor: from + text.length },
      userEvent,
    });
  };
  return {
    view,
    press,
    // Keys as the browser tests write them: Shift+Enter as `⏎`, Backspace as `⌫`,
    // Delete as `⌦`, the vertical arrows as `↑` and `↓`, and undo as `↶`.
    /** @param {string} keys */
    type(keys) {
      const named = {
        "⏎": "Shift-Enter",
        "⌫": "Backspace",
        "⌦": "Delete",
        "↑": "ArrowUp",
        "↓": "ArrowDown",
        "↶": "Mod-z",
      };
      for (const key of keys)
        if (named[key]) press(named[key]);
        else put(key, "input.type");
      return view.state.doc.toString();
    },
    /** @param {string} text */
    paste(text) {
      put(text, "input.paste");
      return view.state.doc.toString();
    },
  };
}

const LEFT = "```\ncode\n```\nafter";
test("a fence is left by typing its marks, or by Down from the draft's last line", async () => {
  assert.equal(await loadMarkdown(), true);
  for (const [name, keys, expected] of [
    ["marks ending the code's last line", "```⏎code```after", LEFT],
    ["marks, then Shift+Enter", "```⏎code```⏎after", LEFT],
    ["marks on their own line", "```⏎code⏎```after", LEFT],
    ["Down from the code", "```⏎code↓after", LEFT],
    ["Down from a blank line", "```⏎code⏎↓after", LEFT],
    // A vertical step carries a goal column, and CodeMirror's selections compare it, so
    // the step that only dropped it at the draft's end took Down's press.
    ["Down after moving up", "```⏎x⏎code↑↓↓after", "```\nx\ncode\n```\nafter"],
    ["Down from the closing marks", "```⏎code⏎```↓after", LEFT],
    ["marks in a quote", "> ```⏎x```after", "> ```\n> x\n> ```\n> after"],
    ["Down in a quote", "> ```⏎x↓after", "> ```\n> x\n> ```\n> after"],
    ["marks in an item", "- ```⏎x```b", "- ```\n  x\n  ```\n  b"],
    ["Down in an item", "- ```⏎x↓b", "- ```\n  x\n  ```\n  b"],
    ["a shorter run stays code", "````⏎x```", "````\nx```"],
    ["blank lines stay in the code", "```⏎a⏎⏎⏎b", "```\na\n\n\nb"],
    ["marks amid a closed fence stay code", "```⏎a⏎b⏎```↑↑```", "```\na```\nb\n```"],
    ["going back through the closing marks", "```⏎a```⌫", "```\na\n``"],
    ["one undo takes Down back", "```⏎a↓↶", "```\na"],
    ["one undo takes the closing marks back", "```⏎a```↶", "```\na``"],
  ]) {
    const field = await draftField("");
    assert.equal(field.type(keys), expected, name);
  }
});

test("Down leaves the indented code a body reads", async () => {
  assert.equal(await loadMarkdown(), true);
  for (const [source, expected] of [
    ["Run:\n\n    code", "Run:\n\n    code\n\nafter"],
    ["> Run:\n>\n>     code\n>     ", "> Run:\n>\n>     code\n> \n> after"],
    // Code of only spaces, as Shift+Enter and four spaces leave it.
    ["Run:\n\n    ", "Run:\n\nafter"],
    ["    ", "    \n\nafter"],
  ]) {
    const field = await draftField(source, undefined, false);
    assert.equal(field.type("↓after"), expected, source);
  }
});

test("a paste keeps a fence's marks and its containers", async () => {
  assert.equal(await loadMarkdown(), true);
  for (const [name, source, pasted, expected] of [
    ["after the opening marks", "```", "one\ntwo", "```\none\ntwo"],
    ["after the opening marks, one word", "```", "one", "```\none"],
    ["after a language", "```python", "x = 1", "```python\nx = 1"],
    ["after the closing marks", "```\ncode\n```", "after", "```\ncode\n```\nafter"],
    ["among the words on the opening line", "```a b ", "c", "```a b c"],
    ["in the code", "```\ncode", " more", "```\ncode more"],
    ["in a quote", "> ```", "one\ntwo", "> ```\n> one\n> two"],
    ["in an item", "- ```", "one\ntwo", "- ```\n  one\n  two"],
    ["from a line break, in a quote", "> ```\n> a", "\nb", "> ```\n> a\n> b"],
    ["a whole fence, in a quote", "> ", "```\na\n```", "> ```\n> a\n> ```"],
    ["a whole fence, in an item", "- ", "```\na\n```", "- ```\n  a\n  ```"],
    // Prose keeps its own markers, so a pasted item stays the item it was.
    ["prose, in an item", "1. x", "\n2. y", "1. x\n2. y"],
  ]) {
    const field = await draftField(source);
    assert.equal(field.paste(pasted), expected, name);
  }
  for (const [name, source, from, expected] of [
    ["over a selection, in a quote", "> ```\n> xxx", 8, "> ```\n> a\n> b"],
    // A paste that starts before a line's markers carries none of them.
    ["over a whole draft", "> ```\n> x", 0, "a\nb"],
    ["before a quote's marker", "> ```\n> x", 6, "> ```\na\nb> x"],
  ]) {
    const field = await draftField(source);
    field.view.dispatch({
      selection: {
        anchor: from,
        head: name.startsWith("over") ? source.length : from,
      },
    });
    assert.equal(field.paste("a\nb"), expected, name);
  }
});

// Every draft of one or two blocks built from these parts, written as the blocks a user
// means the message to hold: prose, or code entered by typing or a paste and left by
// each way out, in a quote, a list item or neither. Each is typed, and its sent message
// held to the blocks it meant. Each way into code meets each way out and each block
// after it, and a failure, named by its keys in the notation of the tables above, is
// small enough to join one of them.
const LEAVE = ["```", "```⏎", "⏎```⏎", "```↓", "↓", "⏎↓", "↑↓↓"];
const PROSE = { kind: "prose", text: "it says:" };
const CODE = [false, true].flatMap((pasted) =>
  ["", "py"].flatMap((lang) =>
    [["Read access to code"], ["Read access to code", "x = 1", "echo hi"]].map(
      (lines) => ({ kind: "code", lang, lines, pasted }),
    ),
  ),
);
const DRAFTS = ["", "> ", "- "].flatMap((container) => {
  const last = [PROSE, ...CODE];
  const left = CODE.flatMap((code) => LEAVE.map((leave) => ({ ...code, leave })));
  return [
    ...last.map((block) => ({ container, blocks: [block] })),
    ...[PROSE, ...left].flatMap((block) =>
      last.map((next) => ({ container, blocks: [block, next] })),
    ),
  ];
});

/** The keys that write `draft` (`draftField`, `type`), and the pastes between them. */
function keysOf({ container, blocks }) {
  /** @type {({keys: string} | {paste: string})[]} */
  const steps = [{ keys: container }];
  blocks.forEach((block, at) => {
    const next = blocks[at + 1];
    if (block.kind === "prose") {
      steps.push({ keys: `${block.text}${next ? "⏎" : ""}` });
      return;
    }
    steps.push({ keys: `\`\`\`${block.lang}` });
    if (block.pasted) steps.push({ paste: block.lines.join("\n") });
    else steps.push({ keys: block.lines.map((line) => `⏎${line}`).join("") });
    if (!next) return;
    // Backticks typed after closing marks lengthen them, so a new block starts a line.
    const leave = block.leave === "```" && next.kind === "code" ? "```⏎" : block.leave;
    steps.push({ keys: leave });
  });
  return steps;
}

// Prose one block after another reads as lines of one: in a paragraph, or in list
// items Shift+Enter began.
/** @param {{kind: string, text: string}[]} blocks */
const joined = (blocks) =>
  blocks.reduce((out, block) => {
    const before = out.at(-1);
    if (block.kind === "prose" && before?.kind === "prose")
      before.text += `\n${block.text}`;
    else out.push({ ...block });
    return out;
  }, []);

/** The blocks the message renders `source` as, inside its quote or list items. */
function sentBlocks(source, renderMarkdown) {
  const body = document.createElement("div");
  body.innerHTML = renderMarkdown(source);
  for (const br of body.querySelectorAll("br")) br.replaceWith("\n");
  const holders = body.querySelectorAll(":scope > blockquote, :scope > ul > li");
  const blocks = [];
  for (const holder of holders.length ? holders : [body]) {
    // A tight list item holds its words with no paragraph around them.
    for (const node of holder.childNodes) {
      const code = node.nodeName === "PRE";
      const text = code ? node.textContent.replace(/\n$/, "") : node.textContent.trim();
      if (code || text) blocks.push({ kind: code ? "code" : "prose", text });
    }
  }
  return joined(blocks);
}

test("what a draft's keys meant is what its message holds", async () => {
  const { loadMarkdown, renderMarkdown } = await import("/runtime/lib/markdown.js");
  assert.equal(await loadMarkdown(), true);
  for (const draft of DRAFTS) {
    const steps = keysOf(draft);
    const keys = steps
      .map((step) =>
        "paste" in step ? `[paste ${JSON.stringify(step.paste)}]` : step.keys,
      )
      .join("");
    const field = await draftField("");
    let source = "";
    try {
      for (const step of steps)
        source = "paste" in step ? field.paste(step.paste) : field.type(step.keys);
    } catch (error) {
      assert.fail(`${keys}\nthrew ${error.stack}`);
    }
    const sent = JSON.stringify(sentBlocks(source, renderMarkdown));
    const meant = JSON.stringify(
      joined(
        draft.blocks.map((block) =>
          block.kind === "code"
            ? { kind: "code", text: block.lines.join("\n") }
            : block,
        ),
      ),
    );
    if (sent !== meant)
      assert.fail(
        `${keys}\nleft ${JSON.stringify(source)}\nsent ${sent}\nmeant ${meant}`,
      );
  }
});

/** The words a draft's field saves (`oneLinePerGap`), its Markdown read as a file. */
async function savedWords(source) {
  const { fieldState, oneLinePerGap } = await loadFieldEditor();
  return oneLinePerGap(
    fieldState(
      { base: source, text: source, anchor: 0, head: 0, steps: [] },
      {
        typed: (_native, insert) => insert(),
        returned: () => true,
        oneLine: () => false,
        message: () => false,
        revealed: () => {},
        focused: () => {},
        readOnly: false,
        attributes: {},
      },
    ),
  );
}

// What a draft's body shows.
/** @param {string} source */
const shown = (source) => renderMarkdown(source, {}, false);

test("a draft saves each run of blank lines between blocks as one", async () => {
  assert.equal(await loadMarkdown(), true);
  for (const [source, saved] of [
    ["Alpha\n\n\n\nBravo", "Alpha\n\nBravo"],
    ["# Head\n\n\nText", "# Head\n\nText"],
    ["- Alpha\n\n\n\n- Bravo", "- Alpha\n\n- Bravo"],
    ["- a\n\n\n  b", "- a\n\n  b"],
    ["> a\n>\n>\n> b", "> a\n>\n> b"],
    ["> a\n>\n\nB", "> a\n\nB"],
    ["| a |\n| - |\n| 1 |\n\n\n\nB", "| a |\n| - |\n| 1 |\n\nB"],
    ["```\none\n\n\ntwo\n```\n\n\nB", "```\none\n\n\ntwo\n```\n\nB"],
  ])
    assert.equal(await savedWords(source), saved, source);
  // A line the parser holds, as a link's definition, an empty quote, a space that
  // isn't one or code, stays, and so do the blank lines at the draft's ends.
  for (const source of [
    "Read [here][ref].\n\n[ref]: /guide\n\nAfter.",
    "    cmd\n    >\n\nGo",
    "A\n\n>\n\nB",
    "A\n\n \n\nB",
    "> ```\n> foo\n>\n>\n\nNext",
    '[ref]: /u "a\n    >\n    >\nb"\n\nUse [ref].',
    "\n\n\nA",
    "A\n\n\n\n",
  ])
    assert.equal(await savedWords(source), source, source);
});

test("what a draft saves shows as its words did, and saves again unchanged", async () => {
  assert.equal(await loadMarkdown(), true);
  const lines = [
    ...["", "", "", " ", "\t", " ", ">", "> ", ">>", "  "],
    ...["Alpha", "Bravo **bold**", "Use [ref].", "[ref]: /x", "# Head", "---"],
    ...["Setext", "===", "> quote", "> > deep", "> - quoted item", "> ```"],
    ...["- item", "  continued", "  - nested", "1. one", "-", "    code", "```"],
    ...["~~~", "| a | b |", "| - | - |"],
  ];
  const next = random(7);
  for (let draft = 0; draft < 1500; draft++) {
    const length = 2 + Math.floor(next() * 10);
    const source = Array.from(
      { length },
      () => lines[Math.floor(next() * lines.length)],
    ).join("\n");
    const saved = await savedWords(source);
    assert.equal(shown(saved), shown(source), JSON.stringify(source));
    assert.equal(await savedWords(saved), saved, JSON.stringify(source));
  }
});

/** Press Return in `field`, as the draft's Enter binding takes it. */
const pressReturn = (field) =>
  field.view.state
    .facet(keymap)
    .flat()
    .filter((binding) => binding.key === "Enter")
    .some((binding) => binding.run?.(field.view));

test("Return beside a formatted paragraph's words keeps its markup with them", async () => {
  assert.equal(await loadMarkdown(), true);
  for (const [source, caret, typed] of [
    // Before the first word, a paragraph opens above, the caret in it.
    ["Alpha\n\n**Bravo**", 9, "Alpha\n\nX\n\n**Bravo**"],
    ["Alpha\n\n[Bravo](/b)", 8, "Alpha\n\nX\n\n[Bravo](/b)"],
    ["Alpha\n\n`Bravo`", 8, "Alpha\n\nX\n\n`Bravo`"],
    // After the last word, one opens below.
    ["**Alpha**\n\nBravo", 7, "**Alpha**\n\nX\n\nBravo"],
    // A link with no words has no side to act past.
    ["[](/url)", 0, "X\n\n[](/url)"],
  ]) {
    const field = await draftField(source, caret, false);
    assert.ok(pressReturn(field), source);
    assert.equal(field.type("X"), typed, source);
    // Undo puts the caret back where it stood, inside the markup.
    const undone = await draftField(source, caret, false);
    pressReturn(undone);
    assert.equal(undone.type("↶"), source, source);
    assert.equal(undone.view.state.selection.main.head, caret, source);
  }
  // A selection's words go, and the markup around them stays whole across the break.
  const field = await draftField("[abcdef](/x)", 7, false);
  field.view.dispatch({ selection: { anchor: 4, head: 7 } });
  assert.ok(pressReturn(field));
  assert.equal(field.type("X"), "[abc\\\nX](/x)");
});

test("keys at the edge of a line's shown words act on its block, not its markup", async () => {
  assert.equal(await loadMarkdown(), true);
  const LIST = "Intro.\n\n- first item\n- second item\n- third item";
  const SECOND = LIST.indexOf(" item\n- third") + 5;
  const CODE = "Before.\n\n```py\nx = 1\n```";
  for (const [name, source, caret, keys, expected] of [
    // Return, then Backspace, gives the words back as they stood.
    [
      "Return before a space, then Backspace",
      "Alpha one two.",
      5,
      "⏎⌫",
      "Alpha one two.",
    ],
    [
      "Return after a space, then Backspace",
      "Alpha one two.",
      6,
      "⏎⌫",
      "Alpha one two.",
    ],
    ["Return at a joint, then Backspace", "Alpha\none two.", 5, "⏎⌫", "Alpha one two."],
    ["a typed line, then Backspace", "", 0, "Alpha⏎one⌫⌫⌫⌫", "Alpha"],
    // Backspace takes a block's marker, then joins it to the block before.
    ["a heading's marker", "Para.\n\n# Title", 9, "⌫", "Para.\n\nTitle"],
    ["then the gap", "Para.\n\n# Title", 9, "⌫⌫", "Para.Title"],
    ["from the line's start", "Para.\n\n# Title", 7, "⌫", "Para.\n\nTitle"],
    // An item's line stays in the item above, on a line of its own.
    [
      "an item's marker",
      LIST,
      LIST.indexOf("second"),
      "⌫",
      "Intro.\n\n- first item\\\nsecond item\n- third item",
    ],
    [
      "then the break",
      LIST,
      LIST.indexOf("second"),
      "⌫⌫",
      "Intro.\n\n- first itemsecond item\n- third item",
    ],
    [
      "a numbered item's",
      "1. one\n2. two\n3. three",
      10,
      "⌫",
      "1. one\\\ntwo\n3. three",
    ],
    ["a heading's below a paragraph", "Para.\n# Title", 8, "⌫", "Para.\n\nTitle"],
    ["then typing joins its words", "Para.\n# Title", 8, "⌫Q", "Para.\n\nQTitle"],
    ["after a backslash that shows", "- A\\\n- B", 7, "⌫", "- A\\\\\\\nB"],
    ["then joins it", "- A\\\n- B", 7, "⌫⌫", "- A\\\\B"],
    [
      "after a link's address",
      "- https://x.io/a\n- B",
      19,
      "⌫",
      "- https://x.io/a \\\nB",
    ],
    [
      "after words that read alone as a heading",
      "- [ ] # H\\\n- B",
      13,
      "⌫",
      "- [ ] # H\\\\\\\nB",
    ],
    ["not where the words would read as a rule", "- a\n- ___", 6, "⌫", "- a\n- ___"],
    ["a heading's closing marks with it", "# Title #", 2, "⌫", "Title"],
    [
      "a quote's, with its first paragraph's",
      "Before.\n\n> Quoted\n> words.\n>\n> More.",
      11,
      "⌫",
      "Before.\n\nQuoted\nwords.\n\n> More.",
    ],
    [
      "then the gap, into the paragraph above",
      "Before.\n\n> Quoted",
      11,
      "⌫⌫",
      "Before.Quoted",
    ],
    ["the innermost marker first", "> - item", 4, "⌫", "> item"],
    ["a task's box", "- [ ] task", 6, "⌫", "- task"],
    ["an item's above a paragraph", "- B\n\nC", 2, "⌫", "B\n\nC"],
    ["a paragraph in a quote joins the one before", "> a\n>\n> b", 8, "⌫", "> ab"],
    ["a blank line the field draws goes first", "a\n\n\n\nb", 5, "⌫", "a\n\n\nb"],
    ["a new item goes whole", "- second\n- ", 11, "⌫", "- second"],
    ["an empty item above goes whole", "- \n\nWords", 4, "⌫", "Words"],
    ["a draft's only, empty item goes whole", "- ", 2, "⌫", ""],
    ["Delete on an empty quote line", "> \nTitle\n===", 2, "⌦", "Title\n==="],
    ["Delete before an empty quote above a rule", "A\n>\n---", 1, "⌦", "A\n\n---"],
    [
      "a line after a hard break goes with its last letter",
      "Alpha\\\nb",
      8,
      "⌫",
      "Alpha",
    ],
    ["keeping the break after it", "A\\\nB\\\nC", 4, "⌫", "A\\\nC"],
    ["Return on the empty line after a hard break", "Alpha\\\n", 7, "⏎X", "Alpha\n\nX"],
    ["Delete after a paragraph's last hard break", "Alpha\\\n", 6, "⌦", "Alpha"],
    // Delete does the same to the block after.
    [
      "Delete takes the next item's marker",
      LIST,
      SECOND,
      "⌦",
      "Intro.\n\n- first item\n- second item\\\nthird item",
    ],
    [
      "then joins it",
      LIST,
      SECOND,
      "⌦⌦",
      "Intro.\n\n- first item\n- second itemthird item",
    ],
    [
      "Delete lifts the quote below",
      "Before.\n\n> Quoted",
      7,
      "⌦",
      "Before.\n\nQuoted",
    ],
    ["then joins it", "Before.\n\n> Quoted", 7, "⌦⌦", "Before.Quoted"],
    ["Delete at a hard break", "Alpha\\\none", 5, "⌦", "Alphaone"],
    ["Delete before a new item", "- A\n- \n- C", 3, "⌦", "- A\n- C"],
    ["Delete on a first, empty item", "- \n- B", 2, "⌦", "- B"],
    ["Delete on an empty item above a space", "- \n ", 2, "⌦", " "],
    ["not where two lists would join", "1. a\n> \n1. b", 7, "⌦", "1. a\n> \n1. b"],
    [
      "Delete joins a paragraph's first line to a heading",
      "# A\nB\nC",
      3,
      "⌦",
      "# AB\nC",
    ],
    ["Backspace at a quoted item below an item", "- A\n> - B", 8, "⌫", "- A\n> B"],
    // Code, its fence and a rule stay whole.
    ["Backspace at code's first line", CODE, CODE.indexOf("x = 1"), "⌫", CODE],
    [
      "Delete at code's last line",
      "```\nx\n```\n\nAfter.",
      5,
      "⌦",
      "```\nx\n```\n\nAfter.",
    ],
    ["Backspace after code", "```\nx\n```\n\nAfter.", 11, "⌫", "```\nx\n```\n\nAfter."],
    ["Backspace at a fence's line", "```\nx\n```", 6, "⌫", "```\nx\n```"],
    ["Delete at a rule's end", "---\nText", 3, "⌦", "---\nText"],
    // A table's rows show their source at the caret, which keys edit as characters.
    ["Delete before a row's spaces", "| a |  \n| - |", 5, "⌦", "| a | \n| - |"],
    [
      "Backspace at an indented row",
      "| a |\n| - |\n  | 1 |",
      14,
      "⌫",
      "| a |\n| - |\n| 1 |",
    ],
    // A gap goes where the blocks around it read the same without it.
    ["Backspace on a gap above a rule", "Para\n\n---", 5, "⌫", "Para\n\n---"],
    ["Delete on a gap above a heading", "Para\n\n# Title", 5, "⌦", "Para\n# Title"],
    ["Backspace on a gap above a heading", "Para\n\n# Title", 5, "⌫", "Para\n# Title"],
    ["Backspace on one of two gaps", "A\n\n\nB", 2, "⌫", "A\n\nB"],
    [
      "Backspace below a setext heading",
      "Title\n===\n\nBody",
      11,
      "⌫",
      "Title\n===\n\nBody",
    ],
    [
      "a line of code in a quote joins the one above",
      "> ```\n> a\n> b\n> ```",
      12,
      "⌫",
      "> ```\n> ab\n> ```",
    ],
    // Return.
    ["Return at a heading's first word", "# Title", 2, "⏎X", "X\n\n# Title"],
    [
      "Return at a heading's bold first word",
      "# **Title**",
      4,
      "⏎X",
      "X\n\n# **Title**",
    ],
    ["Return before a heading's bold word", "# A **Title**", 6, "⏎", "# A \n**Title**"],
    [
      "Return in an item's heading",
      "- # Abcd\n  tail",
      6,
      "⏎",
      "- # Ab\n  cd\n\n  tail",
    ],
    ["Return in a quote's heading", "> # Abcd", 6, "⏎", "> # Ab\n> cd"],
    ["Return in an underlined heading", "Ab    cd\n---", 2, "⏎", "Ab\n---\ncd"],
    [
      "Return in an item's underlined heading",
      "- A B\n  ---\n- C",
      4,
      "⏎",
      "- A \n  ---\n  B\n- C",
    ],
    [
      "Return inside a heading's bold words",
      "# A **Title**",
      9,
      "⏎",
      "# A **Title**\n",
    ],
    [
      "Return at the end of a heading's link words",
      "# A [link](/long-target) B",
      9,
      "⏎",
      "# A [link](/long-target)\nB",
    ],
    [
      "Return after a link's address",
      "See https://x.io/a text",
      18,
      "⏎",
      "See https://x.io/a \\\n text",
    ],
    ["Return before a heading's spaces", "- # Ab    cd", 6, "⏎", "- # Ab\n  cd"],
    ["Return at a quoted heading's", "> # Title", 4, "⏎X", "> X\n>\n> # Title"],
    ["Return at a rule's start", "Para.\n\n---", 7, "⏎X", "Para.\n\nX\n\n---"],
    ["Return among a rule's marks", "---", 1, "⏎X", "---\nX"],
    [
      "Return before a padded code span's first letter",
      "Use ` Alpha ` now.",
      6,
      "⏎",
      "Use \\\n` Alpha ` now.",
    ],
    ["Return inside a code span", "Use `Alpha` now.", 7, "⏎", "Use \\\n`Alpha` now."],
    [
      "Return before an escaped character",
      "Say **\\*Hi** now.",
      7,
      "⏎",
      "Say \\\n**\\*Hi** now.",
    ],
    ["Return inside an entity", "Fish &amp; chips", 7, "⏎", "Fish &amp;\\\n chips"],
    ["Return among a task's markers", "- [ ] task", 3, "⏎", "- \n- [ ] task"],
    ["Return before a heading's closing marks", "# Hello #", 7, "⏎", "# Hello #\n"],
    [
      "Return among the words of a heading that closes",
      "# Hello #",
      4,
      "⏎",
      "# He #\nllo",
    ],
    ["Return before marks the words show", "foo_bar_", 3, "⏎", "foo\\\n\\_bar_"],
    [
      "not where the heading's words would read as a table's header",
      "| xa | b |\n---",
      3,
      "⏎",
      "| xa | b |\n---",
    ],
    [
      "Return before a mark on a nested item's second line",
      "  - nested\n    q - x",
      16,
      "⏎",
      "  - nested\n    q\\\n     \\- x",
    ],
    [
      "Return before a mark on a paragraph's indented line",
      "a\n    # q - b",
      9,
      "⏎",
      "a\n    # q\\\n \\- b",
    ],
    // Words typed on a gap stand as a paragraph of their own.
    ["typing on a gap", "Alpha.\n\nBravo.", 7, "Zed", "Alpha.\n\nZed\n\nBravo."],
    ["typing on a quote's gap", "> a\n>\n> b", 5, "Z", "> a\n>\n> Z\n>\n> b"],
    ["typing an item on a gap", "A\n\nB", 2, "- item", "A\n\n- item\n\nB"],
    ["typing a heading's underline", "A\n\nB", 2, "=", "A\n\n=\n\nB"],
    ["typing an underline below the last paragraph", "A\n", 2, "=", "A\n\n="],
    [
      "typing left of indented code's indent",
      "    A\n\n    B",
      6,
      "x",
      "    A\nx\n\n    B",
    ],
    [
      "typing on a blank line in code",
      "    A\n    \n    B",
      10,
      "x",
      "    A\n    x\n    B",
    ],
    ["typing on a first, empty line", "\n", 0, "x", "x\n"],
    ["typing after a hard break at the draft's end", "A\\\n", 3, "x", "A\\\nx"],
    ["typing a heading's mark after it", "A\\\n", 3, "=", "A\\\n\\="],
    ["typing an item's marker after it", "A\\\n", 3, "1. hi", "A\\\n1\\. hi"],
    ["typing a link after it", "A\\\n", 3, "[a](u)", "A\\\n[a](u)"],
  ]) {
    const field = await draftField(source, caret, false);
    assert.equal(field.type(keys), expected, name);
    if ([...keys].length === 1)
      assert.equal(field.type("↶"), source, `${name}, undone`);
  }
  // A message shows each line, so words typed on one stay there, and Backspace or
  // Delete beside a blank line takes it, joining the paragraphs around it.
  assert.equal((await draftField("a\n\nb", 2, true)).type("Z"), "a\nZ\nb");
  assert.equal((await draftField("a\n\nb", 3, true)).type("⌫"), "a\nb");
  assert.equal((await draftField("a\n\nb", 1, true)).type("⌦"), "a\nb");
  assert.equal((await draftField("a\n    \n# H", 6, true)).type("⌦"), "a\n# H");
  // Pasted paragraphs stand apart from those beside the gap, as does a pasted heading
  // from a paragraph a hard break ends, and a pasted item after a hard break stays its
  // list's.
  assert.equal(
    (await draftField("A\n\nB", 2, false)).paste("one\n\ntwo"),
    "A\n\none\n\ntwo\n\nB",
  );
  assert.equal(
    (await draftField("A  \n", 4, false)).paste("word\n---"),
    "A  \n\nword\n---",
  );
  assert.equal(
    (await draftField("A\\\n", 3, false)).paste("B\n&copy;"),
    "A\\\nB\n&copy;",
  );
  assert.equal(
    (await draftField("- first\\\n  Next", 8, false)).paste("one\n- two"),
    "- firstone\n- two\\\n  Next",
  );
  // Return with a task's first words selected takes them, and its box stays with the
  // words after,
  const task = await draftField("- [x] Foo Bar", 6, false);
  task.view.dispatch({ selection: { anchor: 6, head: 9 } });
  assert.equal(task.type("⏎"), "- \n- [x]  Bar");
  // and with an entity selected takes the character it shows.
  const entity = await draftField("A&copy;B", 1, false);
  entity.view.dispatch({ selection: { anchor: 1, head: 7 } });
  assert.equal(entity.type("⏎"), "A\\\nB");
  // A list after a paragraph takes a blank line before the empty item opened above.
  const under = await draftField("Para\n- [x] Foo", 11, false);
  assert.equal(under.type("⏎"), "Para\n\n- \n- [x] Foo");
});

// The field redraws what an edit replaces, so Backspace and Delete on a message's
// blank lines replace only the line they take, though the edit the check weighs runs
// from the paragraph above.
test("a key taking a message's blank line replaces only that line", async () => {
  for (const [caret, key, expected] of [
    [14, "⌫", [[13, 14, ""]]],
    [11, "⌦", [[11, 12, ""]]],
  ]) {
    const field = await draftField("First line\n\n\n\n", caret, true);
    /** @type {[number, number, string][]} */
    const replaced = [];
    const { dispatch } = field.view;
    field.view.dispatch = (...specs) => {
      for (const spec of specs)
        spec.changes?.iterChanges((from, to, _a, _b, inserted) =>
          replaced.push([from, to, inserted.toString()]),
        );
      dispatch(...specs);
    };
    assert.equal(field.type(key), "First line\n\n\n", key);
    assert.deepEqual(replaced, expected, key);
  }
});

// A seeded fuzzer over generated drafts and the keys a user presses in them. Each key
// keeps what the field promises: it throws nothing, one Undo gives back the words
// before it, and a body's saved words show as the field's did and save again unchanged.
// Where the caret stands beside no markup the field shows at it, which a key edits as
// the characters it is (`revealed`), the check counts the characters the draft shows,
// whitespace and order aside: a key that types nothing adds none, Backspace or Delete
// takes at most one letter or digit, and Return and Tab take none. It can't tell a
// paragraph from words another block took in; the table of edge cases asserts those. `LEAF_FUZZ_DRAFTS` raises the drafts run and `LEAF_FUZZ_SEED` picks
// another run (`pnpm run fuzz:editor`); a failure names its seed, draft and keys.
const FUZZ_LINES = [
  ...["", "", "", "", " ", ">", "> ", "  ", "Alpha one two.", "Use [a link](/x) now."],
  ...["Bravo **bold words** and `code` here.", "[ref]: /x", "# Title here", "## Sub"],
  ...["---", "> Quoted words.", "> > Deep words.", "> - quoted item", "- first item"],
  ...["- second item", "  continued words", "  - nested item", "1. one", "2. two"],
  ...["- [ ] task", "```", "```python", "x = 1", "~~~", "    indented", "| a | b |"],
  ...[
    "| - | - |",
    "` Alpha ` span",
    "**\\*Hello**",
    "Broken line\\",
    "Tail &amp; entity",
  ],
  ...["Setext", "===", "*em* and _em_", "~~struck~~", "![alt](/p.png)", "<b>html</b>"],
];
const FUZZ_KEYS = [
  ...["Enter", "Enter", "Shift-Enter", "Backspace", "Backspace", "Backspace", "Delete"],
  ...[
    "Delete",
    "Tab",
    "Shift-Tab",
    "type:x",
    "type:x",
    "type:Q",
    "type: ",
    "paste:a\nb",
  ],
  "paste:p\n\nq",
];

// Whether the caret at `at` stands beside markup the field shows while the caret is
// there, as the source it is: an inline construct's, ends included, an escape's or an
// entity's, a marker it stands before or inside, and a line the field draws as its
// source, as a fence's, a rule's, a setext underline, a table's or a link's definition.
function revealed(source, message, at) {
  const lineFrom = source.lastIndexOf("\n", at - 1) + 1;
  const end = source.indexOf("\n", at);
  const text = source.slice(lineFrom, end < 0 ? source.length : end);
  // A line holding nothing past its quotes' and items' markers.
  let drawn = /^[\s>]*(?:(?:[-+*]|\d{1,9}[.)])(?:\s+\[[ xX]\])?\s*)?$/.test(text);
  for (const { token, from, to, markers, spelled } of placedMarkdownTokens(
    source,
    message,
  )) {
    if (!token.block) {
      if (token.type === "hardbreak" || token.type === "softbreak") continue;
      if ((token.nesting === 1 || token.type !== "text") && from <= at && at <= to)
        return true;
      if (spelled?.some(([a, b]) => a <= at && at <= b)) return true;
      continue;
    }
    if (markers?.some(([a, b]) => a <= at && at < b)) return true;
    if (from > lineFrom || to <= lineFrom) continue;
    // A setext heading's underline is marks the field shows as typed.
    if (token.type === "heading_open" && from < lineFrom) return true;
    if (/^(paragraph_open|heading_open|code_block)$/.test(token.type)) drawn = true;
    else if (token.type === "fence")
      drawn = !markers?.some(([a]) => a >= lineFrom && a <= lineFrom + text.length);
    else if (/^(hr|table_open|html_block)$/.test(token.type)) return true;
  }
  return !drawn;
}

// The markup opening a line: quotes' and items' markers, a task's box, a heading's `#`.
const OPENING =
  /^(?:[ \t]*(?:>|(?:[-+*]|\d{1,9}[.)]|#{1,6}|\[[ xX]\])(?=[ \t]|$)))*[ \t]*/;

/** The characters a draft shows, past its whitespace, each with how often. A last line
 * holding only markers is read holding the word the user is about to type there, as
 * the field reads it (`read` in field-editor.js), and that word isn't counted. */
const shownCharacters = (source, message) => {
  const bare = /(?:^|\n)(?:[\s>]|(?:[-+*]|\d{1,9}[.)])[ \t](?:\[[ xX]\][ \t])?)*$/;
  const word = bare.test(source) ? "\u2063" : "";
  const counts = new Map();
  for (const ch of markdownWords(source + word, message).replace(/\s|\u2063/g, ""))
    counts.set(ch, (counts.get(ch) ?? 0) + 1);
  return counts;
};
/** The characters `a` holds beyond `b`. */
const beyond = (a, b) =>
  [...a]
    .flatMap(([ch, n]) => Array(Math.max(0, n - (b.get(ch) ?? 0))).fill(ch))
    .join("");

test("the field's keys keep their promises over generated drafts", async () => {
  assert.equal(await loadMarkdown(), true);
  const { isolateHistory } = await import("/vendor/codemirror.esm.js");
  const start = Number(process.env.LEAF_FUZZ_SEED ?? 11);
  const next = random(start);
  /** @template T @param {T[]} list */
  const pick = (list) => list[Math.floor(next() * list.length)];
  const drafts = Number(process.env.LEAF_FUZZ_DRAFTS ?? 1500);
  // Where a key showed markup or took words, by what it did, each with its first case,
  // so a long run says how often each kind of case fails.
  /** @type {Map<string, {count: number, first: string}>} */
  const shownMarkup = new Map();
  /** @param {boolean} ok @param {string} kind @param {string} case_ */
  const expect = (ok, kind, case_) => {
    if (ok) return;
    const seen = shownMarkup.get(kind) ?? { count: 0, first: case_ };
    seen.count++;
    shownMarkup.set(kind, seen);
  };
  for (let n = 0; n < drafts; n++) {
    const message = next() < 0.25;
    const length = 1 + Math.floor(next() * 7);
    const source = Array.from({ length }, () => pick(FUZZ_LINES)).join("\n");
    const caret = Math.floor(next() * (source.length + 1));
    const field = await draftField(source, caret, message);
    const { view } = field;
    const keys = [`@${caret}`];
    const named = () =>
      `seed ${start} draft ${n}, ${message ? "message" : "file"} ${JSON.stringify(source)}, ` +
      `keys ${JSON.stringify(keys)}`;
    for (let step = 0, steps = 1 + Math.floor(next() * 4); step < steps; step++) {
      if (step > 0 && next() < 0.3) {
        const anchor = Math.floor(next() * (view.state.doc.length + 1));
        view.dispatch({ selection: { anchor } });
        keys.push(`@${anchor}`);
      }
      const key = pick(FUZZ_KEYS);
      keys.push(key);
      // A step apart from the one before, as a pause between keys makes it.
      view.dispatch({ annotations: isolateHistory.of("full") });
      const before = view.state;
      const was = before.doc.toString();
      try {
        if (key.startsWith("type:")) field.type(key.slice(5));
        else if (key.startsWith("paste:")) field.paste(key.slice(6));
        else field.press(key);
      } catch (error) {
        assert.fail(`${named()} threw ${error.stack}`);
      }
      const after = view.state;
      const now = after.doc.toString();
      if (now === was) continue;
      field.press("Mod-z");
      assert.equal(view.state.doc.toString(), was, `one undo, ${named()}`);
      view.state = after;
      // A paste is source the user brought, whose lines may read with the lines beside
      // them as other blocks.
      const at = before.selection.main;
      if (!at.empty || key.startsWith("paste:") || revealed(was, message, at.head))
        continue;
      // Typing among the markup opening a line edits that markup, which shows there.
      // Typing or a line break beside a mark the draft shows as words can change how
      // the mark reads, as a letter before `**` stops it opening bold, and a break
      // between two backticks makes a code span of what lies between.
      const line = before.doc.lineAt(at.head);
      const opening = OPENING.exec(line.text)?.[0].length ?? 0;
      const besideMark = /[!-/:-@[-`{-~]/.test(
        was.slice(Math.max(0, at.head - 1), at.head + 1),
      );
      if (key.includes(":") && at.head < line.from + opening) continue;
      if ((key.includes(":") || key.endsWith("Enter")) && besideMark) continue;
      // A key that leaves an empty item before the draft's last line, as Return after a
      // task or Tab on a new item does, leaves its marker and box showing as words
      // until the user writes in it: the field reads only its last line as one about to
      // be written (`read` in field-editor.js).
      if (/(^|\n)[ \t>]*(?:[-+*]|\d{1,9}[.)])(?:[ \t]+\[ \])?[ \t]*\n/.test(now))
        continue;
      if (/(^|\n)[ \t>]*(?:[-+*]|\d{1,9}[.)])[ \t]+\[ \][ \t]*$/.test(now)) continue;
      const typed = key.replace(/^(type|paste):/, "").replace(/\s/g, "");
      const old = shownCharacters(was, message);
      const fresh = shownCharacters(now, message);
      // Letters and digits a key took; marks it took may have paired up as markup, as
      // the `~~` of two lines a join puts together do.
      const lost = beyond(old, fresh).replace(/[^\p{L}\p{N}]/gu, "");
      const shows = `${named()} left ${JSON.stringify(now)}`;
      // Deleting one character other than a line break edits the words as text, and can
      // change how the markup beside it reads, as `_em_` after a deleted space stops
      // being emphasis; Backspace and Delete otherwise take markup only whole.
      let kept = 0;
      while (kept < now.length && was[kept] === now[kept]) kept++;
      const deletion = key === "Backspace" || key === "Delete";
      if (deletion && was.length - now.length === 1 && was[kept] !== "\n") continue;
      // A link's definition is source the field draws as typed, and a line a key puts
      // beside one can come to read as part of it.
      if (/^ {0,3}\[[^\]]*\]:/m.test(`${was}\n${now}`)) continue;
      // A message's Return writes the line break as typed, which may open or end a
      // block, as a fence's marks moved to a line of their own do, and a deletion that
      // takes a line break joins what it split.
      if (message && key.endsWith("Enter")) continue;
      if (
        message &&
        deletion &&
        was.slice(kept, kept + was.length - now.length).includes("\n")
      )
        continue;
      // A list numbered past 1 can't interrupt a paragraph, so words a key puts up
      // against one take in its number.
      const gained = beyond(fresh, old).replace(/[\d.)]/g, (mark) =>
        /[\d.)]/.test(typed) ? mark : "",
      );
      if (key.includes(":"))
        expect(
          [...gained].sort().join("") === [...typed].sort().join(""),
          `typing showed ${gained}`,
          shows,
        );
      else expect(gained === "", `${key} showed markup`, shows);
      if (deletion) expect([...lost].length <= 1, `${key} took words`, shows);
      else if (!key.includes(":")) expect(lost === "", `${key} took words`, shows);
    }
    if (message) continue;
    const now = view.state.doc.toString();
    const saved = await savedWords(now);
    assert.equal(shown(saved), shown(now), `saving, ${named()}`);
    assert.equal(await savedWords(saved), saved, `saving again, ${named()}`);
  }
  assert.deepEqual(
    [...shownMarkup].map(
      ([kind, { count, first }]) => `${kind}: ${count}, first ${first}`,
    ),
    [],
  );
});

test("a file's formula holds its dollars as the markers round its words", async () => {
  assert.equal(await loadMarkdown(), true);
  const source = "Cost $`c(x)`$ a request.";
  const placed = placedMarkdownTokens(source, false);
  const words = (/** @type {string} */ type) =>
    placed
      .filter(({ token }) => token.type === type)
      .map(({ from, to }) => source.slice(from, to));
  assert.deepEqual(words("code_inline"), ["$`c(x)`$"]);
  assert.deepEqual(words("text"), ["Cost ", " a request."]);
  assert.equal(
    placed.find(({ token }) => token.type === "code_inline")?.token.markup,
    "$`",
  );
});
