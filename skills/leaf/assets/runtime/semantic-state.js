/* The document's single semantic owner. Its compiled pure folds publish a complete
   immutable reading synchronously; renderer nodes and transport promises stay in
   their adapters. Importing this module does not mount any view or start delivery. */
import {
  createPresentationCoordinator,
  createSemanticApplication,
} from "../vendor/browser-runtime.js";

const documentToken = Object.freeze({});
let reportPresentationFailure = (reason) =>
  console.error("leaf: presentation failed", reason);
const presentation = createPresentationCoordinator({
  reportFailure: (reason) => reportPresentationFailure(reason),
});

export const applicationState = createSemanticApplication({
  presentation: {
    begin: (semanticEpoch) => presentation.begin(documentToken, semanticEpoch),
    seal: (publication) => presentation.seal(publication),
  },
});
export const readApplication = applicationState.read;
export const projectView = applicationState.projectView;
export const selectWidgets = applicationState.selectWidgets;
export const attachWidgetPresentation = (widget, kind, renderer) =>
  presentation.attach(`widget:${widget}:${kind}`, renderer);
export const whenApplicationPresented = () =>
  presentation.whenPresented(documentToken, readApplication().semanticEpoch);
export const readApplicationPresentation = presentation.read;
export function setPresentationFailureReporter(report) {
  if (typeof report !== "function")
    throw new TypeError("Presentation failure reporting needs a callback");
  reportPresentationFailure = report;
}
export const watchSemantic = (callback) =>
  applicationState
    .select((root) => root.semanticEpoch)
    .subscribe(() => callback(readApplication()));
