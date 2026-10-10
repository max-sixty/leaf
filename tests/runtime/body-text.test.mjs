/* A data body's text, the lines a module draws and numbers.

   `page check` counts the same lines to hold an lf-code `lines` numbering to its
   body, and `test_interact_document.py` reads these cases against that gate. The
   whitespace at the edges is where the two runtimes' own `\s` differ, so a body ending
   in one of those characters is numbered here exactly as the gate counts it. */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { bodyText } from "/runtime/widget-upgrade.js";

const { cases } = JSON.parse(
  readFileSync(new URL("../body_text_cases.json", import.meta.url)),
);

test("a data body's text drops its <pre>'s layout and the browser's whitespace alone", () => {
  for (const [body, text] of cases) {
    const widget = document.createElement("lf-code");
    const pre = document.createElement("pre");
    pre.textContent = body;
    widget.append(pre);
    assert.equal(bodyText(widget), text, JSON.stringify(body));
  }
});

test("a rendered Markdown caret keeps its exact source position in long and structured bodies", async () => {
  const { loadMarkdown, paintMarkdown, markdownSourceOffset } =
    await import("/runtime/markdown.js");
  await loadMarkdown();
  for (const source of [
    Array.from({ length: 600 }, (_, i) => `**word${i}**`).join(" "),
    "# Heading\n\n- **first**\n- `word300` and [a link](https://example.com)\n\n> final words",
    "A **bold &amp; repeated word300** and `one & two`.",
    "- [x] **word300**\n- [ ] Next",
    "https://example.com before reader@example.com and word300.",
    "<div>\n**word300**\n</div>",
    "| First | Second |\n| --- | --- |\n| other | **word300** |",
    "\\* literal, &amp; then word300 and *later*.",
    "```text\nword300\n```",
    "![word300](data:text/html,unsafe)",
    "- first\n\tcontinued **word300**",
    "1. first\n\tcontinued **word300**",
    "- first\n\t\tcontinued **word300**",
    "- &amp; first\n\tcontinued [word300](https://example.com)",
    "> first\n>\tcontinued **word300**",
    "First\r\n\r\n**word300**",
    "Intro **before**.\n\n| A | B |\n| --- | --- |\n| | **word300** |",
    "| | B |\n| --- | --- |\n| | **word300** |",
  ]) {
    const body = document.createElement("div");
    paintMarkdown(body, source);
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    let matches = 0;
    for (let node; (node = walker.nextNode());) {
      const at = node.data.indexOf("word300");
      if (at < 0) continue;
      matches++;
      assert.equal(
        markdownSourceOffset(body, node, at + 2),
        source.indexOf("word300") + 2,
        source,
      );
    }
    assert.equal(matches, 1);
  }
  for (const source of ["First\nword300", "First  \nword300"]) {
    const body = document.createElement("div");
    paintMarkdown(body, source);
    const node = body.querySelector("p").lastChild;
    for (const offset of [0, 2])
      assert.equal(
        markdownSourceOffset(body, node, offset),
        source.indexOf("word300") + offset,
        source,
      );
  }
});

test("Markdown body readings share file dialect, safe destinations and native structure", async () => {
  const { loadMarkdown, renderMarkdown, renderInlineMarkdown, renderedWords } =
    await import("/runtime/markdown.js");
  assert.equal(await loadMarkdown(), true);
  const cases = JSON.parse(
    readFileSync(new URL("../markdown_body_cases.json", import.meta.url)),
  );
  for (const { source, words } of cases)
    assert.equal(
      renderedWords(renderMarkdown(source)).replace(/\s+/g, " ").trim(),
      words,
      source,
    );
  const body = document.createElement("div");
  body.innerHTML = renderMarkdown("<div>\n**bold**\n</div>\n\n<div>\nHeading\n---");
  assert.equal(
    body.innerHTML,
    "<p>&lt;div&gt;<br><strong>bold</strong><br>&lt;/div&gt;</p>\n<h2>&lt;div&gt;<br>Heading</h2>\n",
  );
  body.innerHTML = renderMarkdown("- [x] Done\n- [ ] Todo");
  assert.deepEqual(
    [...body.querySelectorAll("input")].map((input) => [input.disabled, input.checked]),
    [
      [true, true],
      [true, false],
    ],
  );
  body.innerHTML = renderInlineMarkdown(
    "[**bad**](javascript:alert(1)) ![alt](data:text/html,boom) [good](https://example.com)",
  );
  assert.equal(body.textContent, "bad alt good");
  assert.deepEqual(
    [...body.querySelectorAll("a")].map((node) => node.getAttribute("href")),
    ["https://example.com"],
  );
  assert.equal(body.querySelector("img"), null);
  body.innerHTML = renderInlineMarkdown(
    "![**alt** `code` &amp; more [details](https://example.com)](https://example.com/image.svg)",
  );
  assert.equal(body.querySelector("img").alt, "alt code & more details");
  body.innerHTML = renderInlineMarkdown(
    "![A ![B &amp; `code`](https://example.com/b.svg) C](https://example.com/a.svg)",
  );
  assert.equal(body.querySelector("img").alt, "A B & code C");
  assert.equal(renderInlineMarkdown("first\nsecond", false), "first\nsecond");
  // Formatting whitespace must not add a second line in space-preserving messages;
  // excerpts still read the semantic break as separation between the words.
  for (const source of ["first\nsecond", "first  \nsecond"]) {
    assert.equal(renderInlineMarkdown(source), "first<br>second");
    assert.equal(renderedWords(renderInlineMarkdown(source)), "first\nsecond");
  }
});

test("editor tokens retain native constructs and exact source syntax after parser joining", async () => {
  const { loadMarkdown, placedMarkdownTokens } = await import("/runtime/markdown.js");
  await loadMarkdown();
  const source =
    "***nested*** and `code` [**label**](https://example.com) ~~gone~~ H~2~O \\*";
  const constructs = placedMarkdownTokens(source).filter(
    ({ token }) => token.nesting === 1 && token.type !== "paragraph_open",
  );
  assert.deepEqual(
    constructs.map(({ token, from, to, contentFrom, contentTo }) => [
      token.type,
      source.slice(from, to),
      source.slice(contentFrom, contentTo),
    ]),
    [
      ["em_open", "***nested***", "**nested**"],
      ["strong_open", "**nested**", "nested"],
      ["link_open", "[**label**](https://example.com)", "**label**"],
      ["strong_open", "**label**", "label"],
      ["s_open", "~~gone~~", "gone"],
    ],
  );
  for (const automatic of [
    "reader@example.com",
    "www.example.com",
    "before reader@example.com",
    "**one** and reader@example.com",
    "**one** and www.example.com",
    "***one*** and reader@example.com",
    "*one* and reader@example.com",
    "~~one~~ and reader@example.com",
  ]) {
    const link = placedMarkdownTokens(automatic).find(
      ({ token }) => token.type === "link_open",
    );
    assert.equal(
      automatic.slice(link.contentFrom, link.contentTo),
      automatic.trim().split(" ").at(-1),
    );
    assert.equal(link.to, automatic.length);
  }
  for (const automatic of [
    "**one** and reader@example.com foo@example.com",
    "**one** www.example.com **two**",
  ]) {
    const links = placedMarkdownTokens(automatic).filter(
      ({ token }) => token.type === "link_open",
    );
    for (const link of links) {
      const words = automatic.slice(link.contentFrom, link.contentTo);
      assert.match(
        words,
        /^(?:reader@example\.com|foo@example\.com|www\.example\.com)$/,
      );
      assert.equal(link.contentFrom, automatic.indexOf(words));
      assert.equal(link.contentTo, link.contentFrom + words.length);
    }
    assert.equal(links.length, automatic.includes("foo@example.com") ? 2 : 1);
  }
  for (const [automatic, expected] of [
    ["**one** and www.xn--9ca.com", "www.xn--9ca.com"],
    ["**one** and reader@xn--9ca.com", "reader@xn--9ca.com"],
    ["**one** and http://example.com/%E2%9C%93", "http://example.com/%E2%9C%93"],
    ["- [x] reader@example.com", "reader@example.com"],
    ["- [ ] reader@example.com", "reader@example.com"],
    ["- [ ] www.example.com", "www.example.com"],
    ["https://example.com/a%20b", "https://example.com/a%20b"],
    ["&amp; www.example.com tail", "www.example.com"],
    ["\\* www.example.com tail", "www.example.com"],
    ["**one** &amp; www.xn--9ca.com tail", "www.xn--9ca.com"],
    ["- [x] **one** www.example.com", "www.example.com"],
  ]) {
    const link = placedMarkdownTokens(automatic).find(
      ({ token }) => token.type === "link_open",
    );
    assert.equal(automatic.slice(link.contentFrom, link.contentTo), expected);
    assert.equal(link.contentFrom, automatic.indexOf(expected));
    assert.equal(link.contentTo, automatic.indexOf(expected) + expected.length);
  }
  const escaped = placedMarkdownTokens(source).flatMap(({ escapes = [] }) => escapes);
  assert.deepEqual(
    escaped.map((at) => source.slice(at, at + 2)),
    ["\\*"],
  );
});

test("preloading an arriving Markdown widget preserves its exact authored body", async () => {
  const { registry } = await import("/runtime/registry.js");
  const { preloadWidgets } = await import("/runtime/widget-loader.js");
  const { formatDeclaredMarkdown } = await import("/runtime/markdown.js");
  const { dataBody } = await import("/runtime/widget-upgrade.js");
  registry["lf-source-contract"] = { "x-text-format": "markdown" };
  try {
    const source = new DOMParser()
      .parseFromString(
        '<main><lf-source-contract id="source"><pre>    code\n\n**Words**  \n</pre></lf-source-contract></main>',
        "text/html",
      )
      .querySelector("main");
    const authored = source.innerHTML;
    await preloadWidgets(source);
    assert.equal(source.innerHTML, authored);
    assert.equal(dataBody(source.firstElementChild), "    code\n\n**Words**  \n");
    const arrival = document.importNode(source.firstElementChild, true);
    formatDeclaredMarkdown(arrival);
    assert.equal(arrival.querySelector("pre").textContent, "code\n");
    assert.equal(arrival.querySelector("strong").textContent, "Words");
    assert.equal(
      source.innerHTML,
      authored,
      "presentation must not consume revision source",
    );
  } finally {
    delete registry["lf-source-contract"];
  }
});

test("Markdown paragraphs keep reading grain while annotations retain the authored host", async () => {
  const { registry } = await import("/runtime/registry.js");
  const { prepareDeclaredMarkdown } = await import("/runtime/markdown.js");
  const { annotationAt } = await import("/runtime/anchor-resolution.js");
  const { blockAt, elementReading } = await import("/runtime/passages.js");
  registry["lf-seat-contract"] = { "x-text-format": "markdown" };
  try {
    const host = document.createElement("lf-seat-contract");
    host.id = "authored-seat";
    host.innerHTML = "<pre>First **words**.\n\n- Second words.</pre>";
    await prepareDeclaredMarkdown(host);
    const first = host.querySelector("strong").firstChild;
    const second = host.querySelector("li").firstChild;
    assert.equal(blockAt(first), host.querySelector("p"));
    assert.equal(blockAt(second), host.querySelector("li"));
    assert.equal(annotationAt(first), host);
    assert.equal(annotationAt(second), host);
    assert.equal(elementReading(host), "First words. Second words.");
    const authoredParagraph = document.createElement("p");
    authoredParagraph.textContent = "Ordinary prose.";
    assert.equal(annotationAt(authoredParagraph.firstChild), authoredParagraph);
  } finally {
    delete registry["lf-seat-contract"];
  }
});
