// @ts-check
/* A widget module's own rules join the theme's cascade layer (layer.py, CASCADE_LAYERS),
   so specificity, then order, rank their rules, below Layouts, theme packages, semantic
   state and the page's own stylesheet. Shared shadow rules use `lf-shadow` above these
   adopted defaults and below theme packages and semantic state. Chrome and apparatus
   marks stay unlayered so their paint beats page and widget alike (stylesheets.js). Any
   document can load this module, so a widget's rules take the same tier off Leaf, where
   a page's own unlayered rules still outrank them. */
/** @param {string} text */
export const inBaseLayer = (text) => `@layer lf-base {\n${text}\n}`;
