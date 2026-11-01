// Pierre resolves the same Leaf token theme as ordinary code blocks.
import { leafTheme, normalizeTheme } from "/vendor/syntax.esm.js";

const descriptors = new Map([
  [
    "leaf",
    {
      name: "leaf",
      load: async () => normalizeTheme(leafTheme),
    },
  ],
]);

export const themes = {
  getTheme: (/** @type {string} */ name) => descriptors.get(name),
};
