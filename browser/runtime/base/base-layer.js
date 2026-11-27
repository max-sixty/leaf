// Compiled from base-layer.ts by build/typescript.mjs; edit that file.
/* A widget module's own rules join the tier of Leaf's faces for what it draws, `lf-base`
   (layer.py, PART_LAYERS), so specificity, then order, rank their rules with every
   package's defaults, above the page's `base` layer and below Layouts, package
   overrides, semantic state and the page's other layers and unlayered rules. Shared
   shadow rules use `lf-shadow` above these adopted defaults and below theme packages and
   semantic state. Chrome and apparatus marks stay unlayered so their paint beats page
   and widget alike (stylesheets.js). Any document can load this module, so a widget's
   rules take the same tier off Leaf, where a page's own unlayered rules still outrank
   them. */
export const inBaseLayer = (text) => `@layer lf-base {\n${text}\n}`;
