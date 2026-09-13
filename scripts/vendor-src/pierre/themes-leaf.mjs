// Pierre's theme registry, cut to the token themes lf-diff maps onto Leaf's syntax roles.
import { normalizeTheme } from "@shikijs/core";

const descriptors = new Map([
  [
    "github-light",
    {
      name: "github-light",
      load: () => import("@shikijs/themes/github-light"),
    },
  ],
  [
    "github-dark",
    {
      name: "github-dark",
      load: () => import("@shikijs/themes/github-dark"),
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
