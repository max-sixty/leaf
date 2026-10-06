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

export const createTheme = ({ name, load, ...metadata }) => ({
  name,
  ...metadata,
  load: async () => {
    const loaded = await load();
    return normalizeTheme(loaded?.default ?? loaded);
  },
});
export const pierreThemes = { getThemes: () => [] };
export const shikiThemes = { getTheme: (name) => descriptors.get(name) };
