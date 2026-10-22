import { readFileSync } from "node:fs";

import { expect, it } from "vitest";
import * as z from "zod/mini";

import { interactionBatch } from "../src/interactions";

// Annotations say what a field means and constrain nothing either door checks.
const withoutDescriptions = (value: unknown): unknown =>
  Array.isArray(value)
    ? value.map(withoutDescriptions)
    : value && typeof value === "object"
      ? Object.fromEntries(
          Object.entries(value)
            .filter(([key]) => key !== "description")
            .map(([key, field]) => [key, withoutDescriptions(field)]),
        )
      : value;

it("admits the batches the local server admits", () => {
  const declared = JSON.parse(
    readFileSync(
      new URL("../../src/leaf/interaction-batch.schema.json", import.meta.url),
      "utf8",
    ),
  );
  expect(z.toJSONSchema(interactionBatch)).toEqual(withoutDescriptions(declared));
});
