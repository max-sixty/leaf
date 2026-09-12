/* The document's single semantic owner. Its compiled pure folds publish a complete
   immutable reading synchronously; renderer nodes and transport promises stay in
   their adapters. Importing this module does not mount any view or start delivery. */
import { createSemanticApplication } from "../vendor/browser-runtime.js";

export const applicationState = createSemanticApplication();
export const readApplication = applicationState.read;
export const projectView = applicationState.projectView;
export const selectWidgets = applicationState.selectWidgets;
export const watchSemantic = (callback) =>
  applicationState
    .select((root) => root.semanticEpoch)
    .subscribe(() => callback(readApplication()));
