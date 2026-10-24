// Pierre resolves the same Leaf token theme as ordinary code blocks.
import { leafTheme, normalizeTheme } from "shiki";

const descriptors = new Map([
  [
    "leaf",
    {
      name: "leaf",
      load: async () => normalizeTheme(leafTheme),
    },
  ],
]);

export const themes = { getTheme: (name) => descriptors.get(name) };
