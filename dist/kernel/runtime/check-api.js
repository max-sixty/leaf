import { bindQueuedWork, observeQueuedWork } from "./bundle-signals-core.js";
import { WORKS, frameVisibility, onCurrentLocation, onFrameVisibility, readSampleVisibility, releaseFocus, renderedParent, renderingState, tabStops, takesLetters, upFrom } from "./bundle-dom-move.js";
import { exceptionText, recordInteraction, runtimeRootState } from "./bundle-layer-client.js";
import { annotationMarkSheets, annotationSheets, chromeSharedClasses, chromeSheet, growthAfterIsSeen, landingBand, marksSheet, nativeLayers, scrollGlides, seenRect, shownBand, shownBox, shownParts, shownRect, skipped, stackLevel, stuckBox, uiInside, userScrollport, visibleBand, watchScrollEnds } from "./bundle-geometry.js";
import { TEXT_BLOCK, applicationPresented, createPresentationSchedule, presentDocument, readApplication, readApplicationPresentation, selectWidgets, threadCounts, watchSemantic, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented } from "./bundle-context.js";
import { allBindings, commandDeclarationsWithin, commandEntries, commandPresentations, commandRoutes, dragHeld, live, reveal } from "./bundle-errors.js";
import { effectiveScroller, reachScrollers, readingRegion, readingRegionFor, readingRegions, releaseReachStop, scrollersOf, shownRegionBounds, unconcealedReadingRegions, userReadingRegion } from "./bundle-reading-regions.js";
import { availableCommandRoutes, executeCommand, registerSampleCommand, stack } from "./bundle-dispatch.js";
import { observeOutputs, selfComparison, servedElements, shallowSigs } from "./bundle-data.js";
import { elementFrame, scrollAxes } from "./bundle-page-controls.js";
import { alignInlineText, closestAcross, elementById, fencePassageParts, findQuote, layoutBox, pageDocument, pageRange, pageText, quoteFrom, segmentsIn, sentenceUnits, settledAway, spanIn, textNodesUnder, verbatimBoundaryIdentity, verbatimOwnerIdentity } from "./bundle-passages.js";
import { ADDRESSABLE, aimTargetAt, aimTargets, anchorForRange, resolveAnchor, visualPartProblems } from "./bundle-content-layout.js";
import { authoredBody } from "./bundle-initial-render.js";
import { alreadyShown, fitsWhole } from "./bundle-copy-control.js";
import { PAGE_SCOPE, SAY_BOX, THREAD, blocksOnScreen, bringBackSurfaceOf, captureDraftEditing, capturePlace, claimed, completeReadingReturn, draftStore, heldObligation, pageScopes, placeNode, placeOf, readingBlock, readingReturn, replyIsEditing, selectionAnchor, storedDraft, tabStore, userStore, walkOrigin, walkPosition, whereDraft } from "./bundle-surfaces.js";
import { domValue } from "./bundle-abort.js";
import { agentArrivalDuration, flashDuration } from "./bundle-motion.js";
import { USER_VIEW_RESTORE_CASES } from "./bundle-restore-state.js";

//#region runtime/validation.js
function validationWidgetStates(eventIds = null) {
	return [...selectWidgets(eventIds)].map(([id, { state, specs }]) => ({
		id,
		get widget() {
			return elementById(id);
		},
		state,
		read: () => [...specs].filter(([, spec]) => spec.record?.kind === "body").map(([verb, spec]) => [verb, domValue(elementById(id), spec.record)])
	}));
}

//#endregion
export { ADDRESSABLE, PAGE_SCOPE, SAY_BOX, TEXT_BLOCK, THREAD, USER_VIEW_RESTORE_CASES, WORKS, agentArrivalDuration, aimTargetAt, aimTargets, alignInlineText, allBindings, alreadyShown, anchorForRange, annotationMarkSheets, annotationSheets, applicationPresented, authoredBody, availableCommandRoutes, bindQueuedWork, blocksOnScreen, bringBackSurfaceOf, captureDraftEditing, capturePlace, chromeSharedClasses, chromeSheet, claimed, closestAcross, commandDeclarationsWithin, commandEntries, commandPresentations, commandRoutes, completeReadingReturn, createPresentationSchedule, draftStore, dragHeld, effectiveScroller, elementFrame, exceptionText, executeCommand, fencePassageParts, findQuote, fitsWhole, flashDuration, frameVisibility, growthAfterIsSeen, heldObligation, landingBand, layoutBox, live, marksSheet, nativeLayers, observeOutputs, observeQueuedWork, onCurrentLocation, onFrameVisibility, pageDocument, pageRange, pageScopes, pageText, placeNode, placeOf, presentDocument, quoteFrom, reachScrollers, readApplication, readApplicationPresentation, readSampleVisibility, readingBlock, readingRegion, readingRegionFor, readingRegions, readingReturn, recordInteraction, registerSampleCommand, releaseFocus, releaseReachStop, renderedParent, renderingState, replyIsEditing, resolveAnchor, reveal, runtimeRootState, scrollAxes, scrollGlides, scrollersOf, seenRect, segmentsIn, selectionAnchor, selfComparison, sentenceUnits, servedElements, settledAway, shallowSigs, shownBand, shownBox, shownParts, shownRect, shownRegionBounds, skipped, spanIn, stack, stackLevel, storedDraft, stuckBox, tabStops, tabStore, takesLetters, textNodesUnder, threadCounts, uiInside, unconcealedReadingRegions, upFrom, userReadingRegion, userScrollport, userStore, validationWidgetStates, verbatimBoundaryIdentity, verbatimOwnerIdentity, visibleBand, visualPartProblems, walkOrigin, walkPosition, watchScrollEnds, watchSemantic, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented, whereDraft };