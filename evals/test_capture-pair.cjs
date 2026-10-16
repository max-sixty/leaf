/** Page validity cannot establish whether a pair uses the intended two captures. */
const assert = require("node:assert/strict");
const test = require("node:test");
const { pair, outlinedPair, readablePair } = require("./capture-pair.cjs");

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

test("a readable pair keeps both frames near the column's width", () => {
  const { mkdtempSync, writeFileSync } = require("node:fs");
  const { join } = require("node:path");
  const { tmpdir } = require("node:os");
  const directory = mkdtempSync(join(tmpdir(), "capture-pair-"));
  // Only the IHDR width at byte 16 is read.
  const png = (name, width) => {
    const bytes = Buffer.alloc(24);
    bytes.writeUInt32BE(width, 16);
    writeFileSync(join(directory, name), bytes);
    return join(directory, name);
  };
  const input_media = {
    "evals/case/captures/before.png": "/media/full-before.png",
    "evals/case/captures/after.png": "/media/full-after.png",
  };
  const registered = {
    "/media/full-before.png": png("full-before.png", 1440),
    "/media/full-after.png": png("full-after.png", 1440),
    "/media/crop-before.png": png("crop-before.png", 760),
    "/media/crop-after.png": png("crop-after.png", 760),
    "/media/wide-after.png": png("wide-after.png", 1440),
  };
  const shot = (before, after) =>
    `<lf-shot before="/media/${before}.png" after="/media/${after}.png"></lf-shot>`;
  const samples = [
    [shot("crop-before", "crop-after"), true],
    [shot("full-before", "full-after"), false],
    [shot("crop-before", "wide-after"), false],
    [
      `<lf-shot before="/media/crop-before.png" after="/media/gone.png"></lf-shot>`,
      false,
    ],
  ];
  for (const [output, expected] of samples) {
    const context = {
      providerResponse: {
        metadata: { input_media, capture_evidence: { media: registered } },
      },
    };
    assert.equal(readablePair(output, context), expected, output);
  }
});
