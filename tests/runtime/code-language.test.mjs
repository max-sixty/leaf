/* The language a block of code names (`codeLanguage`): a `language-…` class on its
   `<code>`, or for a widget whose body is data the `<code>` in its `<pre>`, else the
   widget itself. A name Leaf can't colour is told from no name at all, since only a
   block naming none takes a default, as a Markdown preview's source does. */

import assert from "node:assert/strict";
import test from "node:test";
import { codeLanguage } from "/runtime/lib/syntax-tokens.js";

/** @param {string} markup */
const element = (markup) => {
  const template = document.createElement("template");
  template.innerHTML = markup;
  return /** @type {Element} */ (template.content.firstElementChild);
};

test("a block names a grammar by its name or an alias, or one Leaf can't colour", () => {
  for (const [markup, language] of [
    ['<code class="language-python">x</code>', "python"],
    ['<code class="block language-py">x</code>', "python"],
    ['<code class="language-haskell">x</code>', null],
    ["<code>x</code>", undefined],
    ['<code class="language-">x</code>', undefined],
  ])
    assert.equal(codeLanguage(element(markup)), language, markup);
});

test("a data widget names its language on its body's code, else on itself", () => {
  for (const [markup, language] of [
    ['<lf-code><pre><code class="language-rs">x</code></pre></lf-code>', "rust"],
    ['<lf-text-document class="language-toml" source="s"></lf-text-document>', "toml"],
    // The body's own name wins, an uncolourable one included.
    [
      '<lf-code class="language-python"><pre><code class="language-haskell">x</code></pre></lf-code>',
      null,
    ],
    ["<lf-text-document><pre>x</pre></lf-text-document>", undefined],
  ])
    assert.equal(codeLanguage(element(markup)), language, markup);
});
