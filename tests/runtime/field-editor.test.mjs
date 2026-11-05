/* The field's own Enter binding preserves code indentation and native editability,
   whether its Markdown reads as a message or as the Markdown file a body displays. */
import assert from "node:assert/strict";
import test from "node:test";

import { loadMarkdown } from "/runtime/markdown.js";
import { loadFieldEditor } from "/runtime/composing/field-editor.js";
import { keymap } from "/vendor/codemirror.esm.js";

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
      const { handled, words } = await enterAfterCode(source, { message, readOnly });
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
  /** @param {string} key */
  const press = (key) =>
    view.state
      .facet(keymap)
      .flat()
      .filter((binding) => binding.key === key)
      .some((binding) => binding.run?.(view));
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
    // Keys as the browser tests write them: Shift+Enter as `⏎`, Backspace as `⌫`, the
    // vertical arrows as `↑` and `↓`, and undo as `↶`.
    /** @param {string} keys */
    type(keys) {
      const named = {
        "⏎": "Shift-Enter",
        "⌫": "Backspace",
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
      selection: { anchor: from, head: name.startsWith("over") ? source.length : from },
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
  const { loadMarkdown, renderMarkdown } = await import("/runtime/markdown.js");
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
