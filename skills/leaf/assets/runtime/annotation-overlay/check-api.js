/* Native overlay diagnostics share its compiled owners without making core checks
   load the physical annotation renderer. Geometry and positioning arrangements need
   real browser layout; pure placement rules are tested at their source owner in Node. */
export { marginSpot } from "./margin-layout.js";
export { floatingPlacement, floatingUi, floatingSelections } from "./floating.js";
export {
  commentBoundary,
  COMMENT_GAP,
  cardMinimum,
  makeRoom,
} from "./comment-placement.js";
