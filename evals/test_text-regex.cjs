const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const yaml = require("yaml");
const { assertions } = require("promptfoo");

async function check(caseName, metric, output) {
  const source = yaml.parse(
    fs.readFileSync(path.join(__dirname, caseName, "case.yaml"), "utf8"),
  );
  const assertion = source.assert.find((item) => item.metric === metric);
  if (assertion.value.startsWith("file://"))
    assertion.value = `file://${path.join(__dirname, assertion.value.slice(7))}`;
  return (
    await assertions.runAssertions({
      test: { assert: [assertion] },
      providerResponse: { output },
    })
  ).pass;
}

test("no-drawing cases reject drawings and accept words, regardless of tag case", async () => {
  for (const [caseName, metric, clean, drawing] of [
    [
      "options-stay-words-for-wording",
      "options-draw-nothing",
      "<lf-option>Words</lf-option>",
      "<lf-option><svg></svg></lf-option>",
    ],
    [
      "visual-change-uses-captures",
      "draws-nothing",
      "<lf-shot before='a' after='b'></lf-shot>",
      "<svg></svg>",
    ],
  ]) {
    for (const transform of [(text) => text, (text) => text.toUpperCase()]) {
      assert.equal(await check(caseName, metric, transform(clean)), true);
      assert.equal(await check(caseName, metric, transform(drawing)), false);
    }
  }
});

test("case-insensitive positive cases still accept upper-case HTML", async () => {
  assert.equal(
    await check(
      "options-stay-words-for-wording",
      "has-options",
      "<LF-OPTION>Words</LF-OPTION>",
    ),
    true,
  );
  assert.equal(
    await check("options-stay-words-for-wording", "has-options", "<p>Words</p>"),
    false,
  );
});

test("opening and mid-work progress reject repeating the page URL", async () => {
  for (const [caseName, url] of [
    ["page-url-opening-progress", "http://127.0.0.1:42041/"],
    ["page-url-midwork-progress", "http://127.0.0.1:8123/"],
  ]) {
    assert.equal(
      await check(caseName, "page-url", "I am checking the controls."),
      true,
    );
    assert.equal(await check(caseName, "page-url", `I am checking ${url}`), false);
  }
});
