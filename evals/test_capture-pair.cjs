/** Page validity cannot establish whether a pair uses the intended two captures. */
const assert = require("node:assert/strict");
const test = require("node:test");
const { pair, outlinedPair } = require("./capture-pair.cjs");

test("capture pairs use the intended distinct views and the requested outlines", () => {
  const before = "/media/original.png";
  const after = "/media/revised.png";
  const media = {
    "evals/case/captures/before.png": before,
    "evals/case/captures/after.png": after,
  };
  const valid = `<lf-shot before="${before}" after="${after}"></lf-shot>`;
  const outlined = `<lf-shot before="${before}" after="${after}" outlines></lf-shot>`;
  const samples = [
    [valid, media, [true, false]],
    [outlined, media, [true, true]],
    [
      `<LF-SHOT BEFORE=${before} AFTER=${after} OUTLINES></LF-SHOT>`,
      media,
      [true, true],
    ],
    [
      `<lf-shot before="${before}" after="${before}" outlines></lf-shot>`,
      media,
      [false, false],
    ],
    [
      `<lf-shot before="${after}" after="${before}" outlines></lf-shot>`,
      media,
      [false, false],
    ],
    [
      `<lf-shot><img src="${before}"><img src="${after}"></lf-shot>`,
      media,
      [false, false],
    ],
    [`<lf-shot before="${before}"></lf-shot>`, media, [false, false]],
    [`<!-- ${outlined} -->`, media, [false, false]],
    [
      `<lf-shot before="${before}" after="${after}" alt="with outlines"></lf-shot>`,
      media,
      [true, false],
    ],
    [outlined, { "evals/case/captures/before.png": before }, [false, false]],
    [
      outlined,
      Object.fromEntries(Object.keys(media).map((key) => [key, before])),
      [false, false],
    ],
  ];
  for (const [output, input_media, expected] of samples) {
    const context = { providerResponse: { metadata: { input_media } } };
    assert.deepEqual(
      [pair(output, context), outlinedPair(output, context)],
      expected,
      output,
    );
  }
});

test("registered derived captures reach visual grading while unregistered or duplicate images fail", () => {
  const context = {
    providerResponse: {
      metadata: {
        input_media: {
          "evals/case/captures/before.png": "/media/original-before.png",
          "evals/case/captures/after.png": "/media/original-after.png",
        },
        capture_evidence: {
          media: {
            "/media/cropped-before.png": "/shots/media/cropped-before.png",
            "/media/marked-after.png": "/shots/media/marked-after.png",
          },
        },
      },
    },
  };
  for (const [before, after, expected] of [
    ["/media/cropped-before.png", "/media/marked-after.png", true],
    ["/media/original-before.png", "/media/marked-after.png", true],
    ["/media/cropped-before.png", "/media/cropped-before.png", false],
    ["/media/unregistered.png", "/media/marked-after.png", false],
  ]) {
    const output = `<lf-shot before="${before}" after="${after}" outlines></lf-shot>`;
    assert.equal(pair(output, context), expected, output);
    assert.equal(outlinedPair(output, context), expected, output);
  }
});
