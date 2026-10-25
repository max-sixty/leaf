import { bindQueuedWork, createPresentationSchedule, observeQueuedWork } from "./bundle-browser-runtime.js";
import { WORKS, frameVisibility, onCurrentLocation, onFrameVisibility, readSampleVisibility, releaseFocus, renderedParent, renderingState, tabStops, takesLetters, upFrom } from "./bundle-dom-move.js";
import { allBindings, annotationMarkSheets, annotationSheets, chromeSharedClasses, chromeSheet, commandDeclarationsWithin, commandEntries, commandPresentations, commandRoutes, dragHeld, exceptionText, growthAfterIsSeen, landingBand, live, marksSheet, nativeLayers, recordInteraction, reveal, runtimeRootState, seenRect, shownBand, shownBox, shownRect, skipped, stackLevel, stuckBox, uiInside, userScrollport, visibleBand } from "./bundle-layer-client.js";
import { applicationPresented, presentDocument, readApplication, readApplicationPresentation, selectWidgets, watchSemantic, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented } from "./bundle-context.js";
import { effectiveScroller, reachScrollers, readingRegion, readingRegionFor, readingRegions, releaseReachStop, scrollersOf, shownRegionBounds, unconcealedReadingRegions, userReadingRegion } from "./bundle-reading-regions.js";
import { availableCommandRoutes, executeCommand, registerSampleCommand, stack } from "./bundle-dispatch.js";
import { selfComparison, servedElements, shallowSigs } from "./bundle-version.js";
import { TEXT_BLOCK, alignInlineText, closestAcross, elementById, fencePassageParts, findQuote, layoutBox, pageDocument, pageRange, pageText, quoteFrom, segmentsIn, sentenceUnits, settledAway, spanIn, verbatimBoundaryIdentity, verbatimOwnerIdentity } from "./bundle-passages.js";
import { ADDRESSABLE, aimTargetAt, aimTargets, anchorForRange, elementFrame, resolveAnchor, scrollAxes, visualPartProblems } from "./bundle-content-layout.js";
import { authoredBody } from "./bundle-initial-render.js";
import { PAGE_SCOPE, SAY_BOX, THREAD, alreadyShown, blocksOnScreen, bringBackSurfaceOf, captureDraftEditing, claimed, completeReadingReturn, draftStore, fitsWhole, heldObligation, pageScopes, placeOf, readingBlock, readingReturn, replyIsEditing, selectionAnchor, storedDraft, tabStore, userStore, walkOrigin, walkPosition, whereDraft } from "./bundle-surfaces.js";
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
export { ADDRESSABLE, PAGE_SCOPE, SAY_BOX, TEXT_BLOCK, THREAD, USER_VIEW_RESTORE_CASES, WORKS, agentArrivalDuration, aimTargetAt, aimTargets, alignInlineText, allBindings, alreadyShown, anchorForRange, annotationMarkSheets, annotationSheets, applicationPresented, authoredBody, availableCommandRoutes, bindQueuedWork, blocksOnScreen, bringBackSurfaceOf, captureDraftEditing, chromeSharedClasses, chromeSheet, claimed, closestAcross, commandDeclarationsWithin, commandEntries, commandPresentations, commandRoutes, completeReadingReturn, createPresentationSchedule, draftStore, dragHeld, effectiveScroller, elementFrame, exceptionText, executeCommand, fencePassageParts, findQuote, fitsWhole, flashDuration, frameVisibility, growthAfterIsSeen, heldObligation, landingBand, layoutBox, live, marksSheet, nativeLayers, observeQueuedWork, onCurrentLocation, onFrameVisibility, pageDocument, pageRange, pageScopes, pageText, placeOf, presentDocument, quoteFrom, reachScrollers, readApplication, readApplicationPresentation, readSampleVisibility, readingBlock, readingRegion, readingRegionFor, readingRegions, readingReturn, recordInteraction, registerSampleCommand, releaseFocus, releaseReachStop, renderedParent, renderingState, replyIsEditing, resolveAnchor, reveal, runtimeRootState, scrollAxes, scrollersOf, seenRect, segmentsIn, selectionAnchor, selfComparison, sentenceUnits, servedElements, settledAway, shallowSigs, shownBand, shownBox, shownRect, shownRegionBounds, skipped, spanIn, stack, stackLevel, storedDraft, stuckBox, tabStops, tabStore, takesLetters, uiInside, unconcealedReadingRegions, upFrom, userReadingRegion, userScrollport, userStore, validationWidgetStates, verbatimBoundaryIdentity, verbatimOwnerIdentity, visibleBand, visualPartProblems, walkOrigin, walkPosition, watchSemantic, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented, whereDraft };