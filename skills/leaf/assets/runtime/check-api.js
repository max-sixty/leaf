/* Browser render checks share these observations with the running kernel. This
   diagnostic entry is separate from the package authoring API. */
export { validationWidgetStates } from "./validation.js";
export { unrevealedVisualParts, visualPartProblems } from "./visual-parts.js";
export {
  readApplication,
  watchSemantic,
  applicationPresented,
} from "./semantic-state.js";
