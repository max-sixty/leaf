import { LAYOUT, afterScript, cancelAnimation, cancelRender, nativeLayerHolding, nextAnimation, nextFrame, nextRender, renderedOrder, renderedUnder, sizeObserver, skipped, tabStore, under } from "./bundle-portable.js";
import { TEXT_FIELD, Z, bareReaction, closeLayer, currentLocationIn, declareRelease, drawn, focusDestination, focused, handBack, holdFocus, hostIn, html, inputCount, keeps, keepsHidden, keepsText, layerLanding, layoutPx, letGo, move, onCurrentLocation, onPressAway, onUserInput, pressLed, render, ringBox, roomPx, rove, sameAnchor, tabStops, turns, visibleFocus } from "./bundle-layer-stack.js";
import { PRESS, closeControl, coarsePointer, cycledRow, el, generatedElement, keys, notice, offer, offerAction, paintKeys, paintKeysWithin, repaint, rowArrows, setRuntimeRootAttribute } from "./bundle-layer-client.js";
import { atScrollEnd, chromeForeground, chromeRoot, effectiveScroller, exactTarget, moveScrollerBy, pageScroller, passageGeometry, placeKept, pointBand, rangeGeometry, readingRegionFor, registerReadingRegion, scrollToEnd, targetElement, targetParts, targetRange, targetSegments, targetSurface, visualAt } from "./bundle-content-layout.js";
import { ANNOTATIONS_KEY } from "./bundle-restore-state.js";
import { anchorLabel, arrivalOf, beginWalk, carryingThreadPlace, claimSeatReplies, claimed, currentLocationThreadId, declareOffFlowSurface, declareSide, keepThreadLanding, listWalkPosition, pageCommand, pageRung, pageScope, pageSelection, placeKeeper, releaseAuthoredUnder, releaseReplies, revealHeld, rowWalk, selectionAnchor, setChildLists, setChildren, showReturnTurn, threadFocusDestination, threadIdNamed, threadNamed } from "./bundle-data.js";
import { clamp, rightCover, seenRect, shownBox, shownParts, shownWindow, showsContents, slotTop, union, watchRoom } from "./bundle-geometry.js";
import { blockAt, closestAcross, elementFromPointAcross, inChrome, labelWords, pageRange, pageWords, quoteFrom, rangeOf, segmentsIn } from "./bundle-passages.js";
import { retainUserIntent } from "./bundle-copy-control.js";
import { activateContributionControl, awaitingUser, canFold, choosePrimary, clearContributionControls, clusterProjection, contributionEntry, contributionEntryRecord, contributionEntrySource, contributionSource, entryEngaged, entryHasMarginHost, focusedOfferOf, markerFace, materializeContributionControls, optionsOffered, presentContributionEntry, presentContributionReceipts, primaryReading, readingBehavior, readingChoices, readingContext, readingFace, readingKey, readingLabel, readingState, spokenContext, spokenSubject, syncContributionSelection, syncContributionUnread, threadReading, unreadIn } from "./bundle-disclosure.js";
import { SVG_NS, boxMotion, dropStand, paintGeometry, paintShape, paintStand, paintTrace, placement, standOver } from "./bundle-box-motion.js";
import { THREAD_CARD, cardMeasure, cardMinimum, commentAttachment, commentBoundary, commentPlacement, commentReference, floatingPlacement, floatingSelections, floatingUi, heldEdges, layoutMarginRows, makeRoom, marginColumn, mountMarginLayer, paintedBox, registerMarginRow, scheduleMarginEntryLabels, scheduleMarginLayout, standsFolded, syncMarginContentLayout, unregisterMarginRow } from "./bundle-comment-placement.js";

//#region runtime/annotation-overlay/surface-grip.js
const SLOP = 3;
function surfaceGrip({ surface, bounds, dropped }) {
	const grip = el("div", "lf-ui lf-surface-grip");
	grip.title = "Drag to move";
	let held = null;
	let offset = {
		x: 0,
		y: 0
	};
	const placed = () => {
		if (held) return;
		if (surface.style.translate) surface.style.removeProperty("translate");
		surface.removeAttribute("data-lf-carried");
		offset = {
			x: 0,
			y: 0
		};
	};
	function follow() {
		const { box, travel } = held;
		const boundary = bounds();
		held.moved ||= Math.hypot(travel.x, travel.y) >= SLOP;
		const now = surface.getBoundingClientRect();
		const within = (room, at, start, end, length) => clamp(at, room[start], Math.max(room[start], room[end] - length));
		const x = within(boundary, box.left + travel.x, "left", "right", now.width);
		const spot = {
			x,
			y: within(boundary.across({
				left: x,
				right: x + now.width
			}), box.top + travel.y, "top", "bottom", now.height)
		};
		const scale = {
			x: now.width / surface.offsetWidth || 1,
			y: now.height / surface.offsetHeight || 1
		};
		const placed = {
			x: now.left - offset.x * scale.x,
			y: now.top - offset.y * scale.y
		};
		offset = {
			x: (spot.x - placed.x) / scale.x,
			y: (spot.y - placed.y) / scale.y
		};
		const xShift = layoutPx(offset.x);
		const yShift = layoutPx(offset.y);
		const translate = xShift === "0px" && yShift === "0px" ? "" : `${xShift} ${yShift}`;
		if (surface.style.translate !== translate) surface.style.translate = translate;
	}
	const frame = () => {
		follow();
		held.frame = nextAnimation(frame);
	};
	grip.addEventListener("pointerdown", (event) => {
		if (held || !event.isPrimary || event.button !== 0) return;
		event.preventDefault();
		grip.setPointerCapture(event.pointerId);
		held = {
			pointerId: event.pointerId,
			start: {
				x: event.clientX,
				y: event.clientY
			},
			travel: {
				x: 0,
				y: 0
			},
			box: surface.getBoundingClientRect(),
			moved: false
		};
		surface.toggleAttribute("data-lf-carried", true);
		held.frame = nextAnimation(frame);
	});
	grip.addEventListener("pointermove", (event) => {
		if (held?.pointerId !== event.pointerId) return;
		held.travel = {
			x: event.clientX - held.start.x,
			y: event.clientY - held.start.y
		};
	});
	grip.addEventListener("mousedown", (event) => event.stopPropagation());
	const finish = (event) => {
		if (held?.pointerId !== event.pointerId) return;
		follow();
		const { moved } = held;
		cancelAnimation(held.frame);
		held = null;
		const box = surface.getBoundingClientRect();
		if (!moved || event.type !== "pointerup") placed();
		dropped(moved && event.type === "pointerup" ? box : null);
	};
	for (const ending of [
		"pointerup",
		"pointercancel",
		"lostpointercapture"
	]) grip.addEventListener(ending, finish);
	return {
		grip,
		placed
	};
}

//#endregion
//#region runtime/thread/card-anchor.js
var CardAnchor = class {
	#surface;
	#sent = null;
	#press = null;
	#side = null;
	constructor(surface) {
		this.#surface = surface;
	}
	sending(attempt) {
		this.#sent = attempt;
	}
	writing() {
		this.#sent = null;
	}
	#keepsSend(joined) {
		return this.#sent !== null && (!joined?.size || joined.has(this.#sent));
	}
	presented(joined) {
		if (!this.#keepsSend(joined)) this.#sent = null;
	}
	pressed(event, input) {
		if (![
			"pointerdown",
			"touchstart",
			"keydown"
		].includes(event.type)) return;
		const path = event.composedPath();
		if (!path.includes(this.#surface)) return;
		const top = this.#surface.getBoundingClientRect().top;
		this.#press = {
			input,
			path: path.filter((node) => node instanceof Element && node !== this.#surface && this.#surface.contains(node)).map((node) => ({
				node,
				offset: node.getBoundingClientRect().top - top
			})),
			extent: this.#extent(),
			edge: null
		};
	}
	#field() {
		return this.#surface.querySelector(`.lf-thread-reply ${TEXT_FIELD}`);
	}
	#writing() {
		const field = this.#field();
		return Boolean(field?.checkVisibility() && (currentLocationIn(field.closest(".lf-thread-reply")) || field.value !== ""));
	}
	#extent() {
		const transcript = this.#surface.querySelector(".lf-thread-transcript");
		return transcript ? parseFloat(getComputedStyle(transcript).height) + transcript.scrollHeight - transcript.clientHeight : 0;
	}
	prepare(seat) {
		if (seat.fresh) this.forget();
		this.#side = seat.side;
		if (this.#field()?.value) this.writing();
		const writing = this.#writing();
		const captured = this.#press;
		let press = captured?.input === inputCount() ? captured : null;
		if (press) {
			const extent = this.#extent();
			if (Math.abs(extent - press.extent) > .5) {
				const reference = press.path.find(({ node }) => node.checkVisibility());
				if (press.edge) press = null;
				else if (reference) {
					const offset = reference.node.getBoundingClientRect().top - this.#surface.getBoundingClientRect().top;
					press = {
						...press,
						edge: seat.side === "top" || Math.abs(offset - reference.offset) > .5 ? "foot" : "top",
						extent
					};
				}
			}
		}
		const attachment = seat.side === "top" ? "foot" : "top";
		const ordinary = this.#sent || !writing && seat.side === "top" ? "foot" : "top";
		const beside = seat.side === "left" || seat.side === "right";
		return {
			edge: seat.adopted ? attachment : press?.edge ?? ordinary,
			rises: !seat.adopted && !press?.edge && writing && !this.#sent && beside,
			commit: () => {
				if (this.#press === captured) this.#press = press;
			}
		};
	}
	newsMoves(joined) {
		return this.#writing() || this.#side === "top" || this.#keepsSend(joined);
	}
	forget() {
		this.#sent = null;
		this.#press = null;
		this.#side = null;
	}
};

//#endregion
//#region runtime/annotation-overlay/thread-preview.js
const REPLY_BOX = `.lf-thread-reply ${TEXT_FIELD}`;
const CUT_EDGES = [
	"--lf-cut-top",
	"--lf-cut-right",
	"--lf-cut-bottom",
	"--lf-cut-left"
];
function createThreadPreview({ inventory, renderMarginThread, placedAt, scrollThreadIntoView, scrollToElement, openInPanel, onClose }) {
	const { targetFor, entryPoint, entryPlace, sourceItem } = inventory;
	const preview = el("aside", "lf-ui lf-margin-preview");
	preview.id = THREAD_CARD;
	preview.hidden = true;
	preview.setAttribute("role", "dialog");
	const previewOpen = () => previewSession !== null;
	const previewClose = closeControl({
		name: "Dismiss thread view",
		title: "Dismiss thread view (Esc)",
		className: "lf-margin-preview-close"
	});
	const previewNav = el("span", "lf-margin-preview-nav");
	const previewPosition = el("span", "lf-margin-preview-position");
	const previewPrevious = offerAction("symbol", "lf-margin-preview-step", "Previous thread", { action: "previous" });
	const previewNext = offerAction("symbol", "lf-margin-preview-step", "Next thread", { action: "next" });
	previewNav.append(previewPrevious, previewPosition, previewNext);
	const previewOpenInPanel = offerAction("symbol", "lf-margin-preview-expand", "Open in panel", { action: "expand" });
	const previewList = el("div", "lf-margin-preview-list");
	let dismiss = () => {};
	const carry = surfaceGrip({
		surface: preview,
		bounds: () => commentBoundary({ region: previewSession?.region }),
		dropped(box) {
			const session = previewSession;
			if (!session) return;
			if (box) {
				session.width = box.width;
				session.side.adopt({
					box,
					placement: {
						...session.side.capture(),
						moved: true
					}
				});
			}
			placeThreadPreview();
		}
	});
	const face = el("div", "lf-margin-preview-card");
	face.append(previewList);
	const followCard = () => {
		if (!preview.hasAttribute("data-lf-thread-placement")) return following.forget();
		following.follow();
	};
	const followed = sizeObserver(followCard);
	const following = boxMotion({
		root: face,
		box: face,
		surface: "lf-margin-preview-ground",
		lift: 3,
		outset: 0,
		observer: followed,
		held: () => heldEdges(preview)
	});
	preview.append(following.ground, carry.grip, face);
	followed.observe(face);
	const opener = () => previewSession?.control?.checkVisibility() ? previewSession.control : null;
	const onOpener = () => Boolean(opener()) && focused() === opener();
	const stopsBeside = (root, at, side) => tabStops(root).filter((stop) => stop !== at && !renderedUnder(at, stop) && Math.sign(renderedOrder(stop, at)) === side);
	const atCardEdge = (side) => Boolean(opener()) && stopsBeside(preview, focused(), side).length === 0;
	keys(preview, null, [{
		id: "margin.card.back",
		keys: ["Shift+Tab"],
		title: "back to the margin entry",
		repeat: true,
		runFromCommandReference: false,
		when: () => atCardEdge(-1),
		run: () => focusDestination(opener(), "step")
	}, {
		id: "margin.card.onward",
		keys: ["Tab"],
		title: "on past the margin entry",
		native: true,
		repeat: true,
		runFromCommandReference: false,
		when: () => atCardEdge(1),
		run: () => focusDestination(opener(), "return")
	}]);
	const openerKeys = [{
		id: "margin.card.enter",
		keys: ["Tab"],
		title: "into the thread card",
		repeat: true,
		runFromCommandReference: false,
		when: () => onOpener() && tabStops(preview).length > 0,
		run: () => focusDestination(tabStops(preview)[0], "step")
	}, {
		id: "margin.card.over",
		keys: ["Shift+Tab"],
		title: "back past the thread card",
		native: true,
		repeat: true,
		runFromCommandReference: false,
		when: () => onOpener() && under(stopsBeside(chromeRoot, opener(), -1).at(-1), preview),
		run: () => focusDestination(preview, "return")
	}];
	onUserInput((event) => previewSession?.anchor.pressed(event, inputCount()));
	preview.addEventListener("lf-before-edit", (event) => {
		if (event.composedPath().some((node) => node instanceof Element && node.matches(".lf-thread-reply"))) previewSession?.anchor.writing();
	});
	let previewRegionMounted = false;
	function syncPreviewTranscript() {
		const transcript = previewList.querySelector(".lf-thread-transcript");
		if (transcript === previewSession.transcript) return;
		previewSession.stopRegion?.();
		previewSession.stopRegion = null;
		previewSession.transcript = transcript;
		previewSession.place = transcript ? placeKeeper(transcript, {
			items: ".lf-msg[data-event]",
			identity: (message) => message.dataset.event
		}) : null;
		if (previewRegionMounted && transcript) previewSession.stopRegion = registerReadingRegion({
			id: THREAD_CARD,
			host: preview,
			body: transcript,
			paintContinuation: (above) => {
				let edge = 0;
				let height = above ? 12 : 0;
				const room = slotTop(transcript);
				const top = transcript.getBoundingClientRect().top + transcript.clientTop + room;
				for (const message of transcript.querySelectorAll(":scope > .lf-msg")) {
					const box = message.querySelector(":scope > .lf-msg-head")?.getBoundingClientRect();
					keeps(message, "data-lf-beside-actions", above && box && box.top < top + box.height && box.bottom > top ? "" : null);
				}
				if (above) for (const head of transcript.querySelectorAll(".lf-msg-head")) {
					const box = head.getBoundingClientRect();
					if (!box.height || box.bottom <= top) continue;
					if (box.top <= top) edge = box.bottom - top;
					else {
						height = Math.min(height, box.top - top - edge);
						break;
					}
				}
				const card = transcript.parentElement;
				card.style.setProperty("--lf-thread-fade-top", layoutPx(edge));
				card.style.setProperty("--lf-thread-fade-height", layoutPx(height));
				keeps(card, "data-lf-scrolled", above ? "" : null);
			}
		});
	}
	let previewSession = null;
	const placementDriver = floatingPlacement({
		floating: preview,
		update: () => scheduleThreadPreviewPosition()
	});
	const placedThreadPreview = () => {
		previewSession.positionResult ??= Promise.withResolvers();
		cancelRender(previewSession.positionFrame);
		previewSession.positionFrame = 0;
		placeThreadPreview();
		return previewSession.positionResult.promise;
	};
	function forgetThreadPreviewPlacement() {
		placementDriver.supersede();
		cancelRender(previewSession.positionFrame);
		previewSession.positionFrame = 0;
		previewSession.side.forget();
		previewSession.anchor.forget();
		previewSession.away = false;
	}
	function retirePreviewSession() {
		carry.placed();
		const session = previewSession;
		if (!session) return;
		keeps(preview, "data-lf-grows", null);
		session.positionResult?.resolve(false);
		cancelRender(session.positionFrame);
		placementDriver.supersede();
		session.stopRegion?.();
		preview.style.removeProperty("visibility");
		previewSession = null;
	}
	function deferThreadPreviewFocus(positioned, focus) {
		const mayFocus = retainUserIntent();
		const session = previewSession;
		const pending = { holding: focused() };
		previewSession.focusPending = pending;
		positioned?.then((placed) => {
			if (previewSession !== session || session.focusPending !== pending) return;
			previewSession.focusPending = null;
			const holdingGone = focused() === document.body && (!pending.holding?.isConnected || !pending.holding?.checkVisibility());
			if (placed && (focused() === pending.holding || holdingGone)) mayFocus.handoff(focus);
		});
	}
	function measureThreadCard(room, cap, reading) {
		preview.style.setProperty("--lf-thread-width", layoutPx(room));
		const worn = parseFloat(preview.style.getPropertyValue("--lf-thread-max-height"));
		const height = preview.offsetHeight;
		const overflow = [previewSession.transcript, ...previewList.querySelectorAll(REPLY_BOX)].some((box) => box && box.scrollHeight > box.clientHeight + .5);
		if (!(worn >= 0) || cap < height - .5 || overflow && cap > height + .5) preview.style.setProperty("--lf-thread-max-height", layoutPx(cap));
		if (reading?.latest) showArrival(previewSession);
		else if (reading?.end) scrollToEnd(previewSession.transcript);
		return preview.getBoundingClientRect().height;
	}
	function showArrival(session) {
		if (!session.sent) return showReturnTurn(session.transcript, threadCardThread(session));
		scrollToEnd(session.transcript);
		moveScrollerBy(session.transcript, -session.sent.fromEnd);
	}
	function threadCardCluster(session) {
		const row = session.control.closest("[data-lf-margin-for]") ?? session.control;
		if (row.checkVisibility()) return row;
		return entryPlace(session.entry) ?? row;
	}
	const threadCardThread = (session) => {
		const item = session.entry?.items.find((candidate) => candidate.id === session.threadItem);
		return item ? sourceItem(item)?.thread : null;
	};
	function threadCardPlace(session) {
		const target = targetFor(session.entry);
		const point = entryPoint(session.entry);
		if (!target) {
			const cluster = threadCardCluster(session);
			const box = cluster.getBoundingClientRect();
			return {
				element: cluster,
				clear: box,
				extent: box,
				row: box.top,
				margin: null,
				region: null,
				scroller: effectiveScroller(cluster)
			};
		}
		const thread = threadCardThread(session);
		const words = !point && thread?.anchor?.quote ? passageGeometry(placedAt(thread.id)) : null;
		return commentAttachment({
			target,
			point,
			passage: words
		});
	}
	const THREAD_SIDES = {
		right: "right",
		left: "left",
		bottom: "below",
		top: "above"
	};
	function placeThreadPreview() {
		const session = previewSession;
		if (!session || !session.control?.isConnected) return false;
		const placement = placementDriver.begin();
		let reading = null;
		const stillCurrent = () => previewSession === session && placementDriver.current(placement) && session.control?.isConnected;
		const place = threadCardPlace(session);
		const element = place?.element ?? targetFor(session.entry);
		const watch = (ui) => placementDriver.watch(element, {
			contextElement: element,
			getBoundingClientRect: () => threadCardPlace(session)?.clear ?? element.getBoundingClientRect()
		}, ui.autoUpdate);
		if (!place) {
			if (preview.style.visibility !== "hidden") {
				session.withheldFocus = holdFocus(preview);
				preview.style.visibility = "hidden";
			}
			session.away = true;
			floatingUi().then((ui) => stillCurrent() && watch(ui));
			return false;
		}
		const boundary = commentBoundary({ region: place.region });
		session.region = place.region;
		if (!boundary.width || !boundary.height) {
			floatingUi().then((ui) => stillCurrent() && watch(ui));
			return false;
		}
		const scroller = place.scroller;
		const seat = session.side.choose({
			clear: place.clear,
			row: place.row,
			column: place.column,
			extent: place.extent,
			boundary,
			scroller,
			coarse: coarsePointer.matches
		});
		const { side, fresh, opening } = seat;
		let anchored;
		floatingUi().then((ui) => {
			if (!stillCurrent()) return null;
			anchored = session.anchor.prepare(seat);
			const { reference, placement, middleware, plane } = session.side.options(ui, {
				clear: place.clear,
				row: place.row,
				lastRow: place.lastRow,
				column: place.column,
				margin: place.margin,
				boundary,
				fit({ width, height, stood, scale }) {
					if (!stillCurrent()) return;
					reading ??= session.transcript && {
						end: !fresh && atScrollEnd(session.transcript),
						latest: session.arriving
					};
					if (fresh) session.width = null;
					const room = Math.min(cardMeasure(), width, (session.width ?? Infinity) / scale.x);
					preview.style.setProperty("--lf-thread-min-width", layoutPx(session.width === null ? Math.min(cardMinimum(), room) : room));
					const fitted = measureThreadCard(room, Math.max(stood, height), reading);
					if (opening && (side === "top" || side === "bottom") && makeRoom(side, place.clear, place.extent, fitted, boundary, scroller)) {
						session.side.scrolled();
						placeThreadPreview();
					}
				},
				edge: anchored.edge,
				rises: anchored.rises
			});
			watch(ui);
			return placementDriver.position(ui.computePosition, commentReference(place, reference), {
				placement,
				middleware
			}, plane, place.element);
		}).then((position) => {
			if (!position || !stillCurrent()) return;
			session.arriving = false;
			const { scale } = session.side.landed(position);
			anchored.commit();
			placementDriver.stand(position);
			session.width ??= preview.getBoundingClientRect().width;
			carry.placed();
			preview.style.removeProperty("visibility");
			session.withheldFocus?.();
			session.withheldFocus = null;
			const card = placementDriver.clientBox(position);
			session.away = card.bottom <= boundary.top || card.top >= boundary.bottom;
			const region = boundary.inRegion;
			const cuts = region ? [
				(region.top - card.top) / scale.y,
				(card.right - region.right) / scale.x,
				(card.bottom - region.bottom) / scale.y,
				(region.left - card.left) / scale.x
			].map((cut) => layoutPx(Math.max(cut, -following.shadowReach()))) : [];
			CUT_EDGES.forEach((edge, i) => {
				if (region) preview.style.setProperty(edge, cuts[i]);
				else preview.style.removeProperty(edge);
			});
			keeps(preview, "data-lf-thread-placement", THREAD_SIDES[side]);
			if (!session.followed) {
				session.followed = true;
				if (session.sent) following.drawnAt(session.sent.field);
				followCard();
			}
			keepThreadLanding(previewList.querySelector(".lf-page-thread"));
			session.positionResult?.resolve(true);
			session.positionResult = null;
		}).catch((error) => {
			if (stillCurrent()) close();
			throw error;
		});
		return true;
	}
	function scheduleThreadPreviewPosition() {
		const session = previewSession;
		if (!session || session.positionFrame || preview.hasAttribute("data-lf-carried")) return;
		session.positionFrame = nextRender(() => {
			session.positionFrame = 0;
			if (previewSession === session) placeThreadPreview();
		});
	}
	function transferThreadCard(button, carry = focused() === previewSession?.control) {
		if (previewSession?.control === button) return;
		forgetThreadPreviewPlacement();
		previewSession.control = button;
		if (carry) focusDestination(button, "return");
	}
	function select({ entry, threadItem, control, origin, accompanies, forced = false, disclosed = false }) {
		retirePreviewSession();
		previewSession = {
			entry,
			threadItem,
			control,
			accompanies,
			forced,
			disclosed,
			preparing: false,
			latest: null,
			arriving: true,
			sent: origin && {
				fromEnd: origin.fromEnd,
				field: origin.field
			},
			away: false,
			positionFrame: 0,
			positionResult: null,
			focusPending: null,
			withheldFocus: null,
			transcript: null,
			place: null,
			stopRegion: null,
			side: commentPlacement(),
			anchor: new CardAnchor(preview),
			width: origin?.box.width ?? null,
			region: null,
			followed: false
		};
		if (origin) previewSession.side.adopt(origin);
		keeps(preview, "data-lf-grows", origin ? "" : null);
		return previewSession;
	}
	function buildThreadCard(entry, requestedItem = null) {
		const restoreFocus = holdFocus(preview);
		const focusedItem = restoreFocus ? focused(document)?.closest?.("[data-lf-margin-entry]")?.lfMarginItem ?? null : null;
		const threadItems = entry.items.filter((item) => item.kind === "comment");
		const wanted = requestedItem ?? previewSession.threadItem ?? focusedItem;
		const selected = threadItems.find((item) => item.id === wanted) ?? threadItems[0];
		const arriving = previewSession.threadItem !== selected.id || !previewSession.transcript;
		if (previewSession.threadItem !== selected.id) select({
			...selection(),
			entry,
			threadItem: selected.id
		});
		else previewSession.entry = entry;
		const session = previewSession;
		const latest = turns(sourceItem(selected).thread).at(-1);
		const messageSelector = ":scope > .lf-margin-thread > .lf-margin-thread-body > .lf-page-thread > .lf-thread-transcript > .lf-msg";
		const replySelector = ":scope > .lf-margin-thread > .lf-margin-thread-body > .lf-page-thread > .lf-thread-reply";
		const lastBox = [...previewList.querySelectorAll(messageSelector)].findLast((node) => showsContents(node))?.getBoundingClientRect();
		const listBox = session.transcript?.getBoundingClientRect();
		const replyBox = previewList.querySelector(replySelector)?.getBoundingClientRect();
		const follow = !arriving && session.latest && latest?.author === "agent" && (latest.id !== session.latest.id || latest.text !== session.latest.text) && lastBox && listBox && lastBox.bottom >= listBox.top && lastBox.bottom <= (replyBox?.top ?? listBox.bottom) + 80 && atScrollEnd(session.transcript);
		const present = () => {
			const targetHeading = targetFor(entry)?.querySelector(":scope > strong")?.textContent;
			const quoted = sourceItem(selected)?.thread?.anchor ? anchorLabel(sourceItem(selected).thread.anchor, sourceItem(selected).thread.root.about) : null;
			const title = labelWords(targetHeading || quoted || entry.title);
			keeps(preview, "aria-label", `Thread for ${spokenSubject(title)}`);
			keepsHidden(previewNav, threadItems.length < 2);
			const selectedIndex = Math.max(0, threadItems.indexOf(selected));
			keepsText(previewPosition, `${selectedIndex + 1}/${threadItems.length}`);
			previewPrevious.toggleAttribute("disabled", selectedIndex === 0);
			previewNext.toggleAttribute("disabled", selectedIndex === threadItems.length - 1);
			const item = selected ? previewItemNode(selected) : null;
			setChildren(previewList, item ? [item] : []);
			if (item) claimSeatReplies(item.querySelector(":scope > .lf-margin-thread-body"));
			syncPreviewTranscript();
			restoreFocus?.(focusedItem && previewList.querySelector(".lf-page-thread"), previewClose);
		};
		if (!arriving && session.place) session.place.around(present);
		else {
			present();
			session.arriving = Boolean(session.transcript);
			if (session.arriving) showArrival(session);
		}
		session.latest = latest && {
			id: latest.id,
			text: latest.text
		};
		if (follow) scrollToEnd(session.transcript);
	}
	function stepPreviewThread(step) {
		if (!previewSession) return;
		const threadItems = previewSession.entry.items.filter((item) => item.kind === "comment");
		const current = threadItems.findIndex((item) => item.id === previewSession.threadItem);
		const next = Math.max(0, Math.min(threadItems.length - 1, current + step));
		if (next === current || !threadItems[next]) return;
		focusThread(show({
			...selection(),
			threadItem: threadItems[next].id
		}));
	}
	function previewItemNode(item) {
		let node = [...previewList.children].find((candidate) => candidate.lfMarginItem === item.id);
		if (!node?.classList.contains("lf-margin-thread")) {
			node?.remove();
			node = el("section", "lf-margin-thread");
			const body = el("div", "lf-margin-thread-body");
			node.append(body);
		}
		const shownThread = sourceItem(item).thread;
		previewOpenInPanel.onclick = () => {
			dismiss();
			openInPanel(shownThread.id);
		};
		renderMarginThread(node.querySelector(":scope > .lf-margin-thread-body"), shownThread, {
			nav: previewNav.hidden ? null : previewNav,
			expand: previewOpenInPanel,
			close: previewClose,
			anchor: previewSession.anchor,
			sending: following.stream,
			prepareLanding: () => {
				const target = targetFor(previewSession?.entry);
				const mayLand = retainUserIntent({
					source: focused(),
					available: () => Boolean(target?.isConnected)
				});
				return () => {
					if (previewOpen()) return false;
					return mayLand.handoff(() => focusDestination(target, "return"));
				};
			}
		});
		keeps(node, "data-lf-margin-entry", item.id);
		node.lfMarginItem = item.id;
		return node;
	}
	function releaseLeft(items) {
		for (const node of previewList.children) if (!items.has(node.lfMarginItem)) releaseReplies(node);
	}
	function selection() {
		if (!previewSession) return null;
		const { entry, threadItem, control, accompanies, forced, disclosed } = previewSession;
		return Object.freeze({
			entry,
			threadItem,
			control,
			accompanies,
			forced,
			disclosed
		});
	}
	function show({ entry, threadItem = null, control = null, origin = null, accompanies = false, forced = false, disclosed = false, prepare = null }) {
		const items = entry.items.filter((item) => item.kind === "comment");
		const selected = items.find((item) => item.id === threadItem) ?? items[0];
		const session = previewSession?.entry.key === entry.key && previewSession.threadItem === selected.id ? previewSession : select({
			entry,
			threadItem: selected.id,
			control,
			origin,
			accompanies,
			forced,
			disclosed
		});
		Object.assign(session, {
			entry,
			accompanies,
			forced,
			disclosed,
			preparing: true
		});
		let preparedControl;
		try {
			preparedControl = prepare ? prepare() : control;
		} finally {
			session.preparing = false;
		}
		if (previewSession !== session) return null;
		transferThreadCard(preparedControl);
		if (!session.control?.isConnected) {
			close();
			return null;
		}
		keepsHidden(preview, false);
		keeps(preview, "inert", null);
		buildThreadCard(entry, selected.id);
		const positioned = placedThreadPreview();
		paintKeysWithin(preview);
		return positioned;
	}
	function refresh(entry, control, carry = focused() === previewSession?.control) {
		if (!previewSession || previewSession.preparing) return;
		transferThreadCard(control, carry);
		buildThreadCard(entry);
		placeThreadPreview();
	}
	function close() {
		if (!previewSession) return;
		const closed = selection();
		retirePreviewSession();
		placementDriver.supersede();
		delete preview.dataset.lfThreadPlacement;
		const hide = () => {
			if (previewSession) return;
			placementDriver.stop();
			for (const edge of CUT_EDGES) preview.style.removeProperty(edge);
			keepsHidden(preview, true);
			keeps(preview, "inert", null);
			paintKeysWithin(preview);
		};
		const fade = preview.hidden ? null : preview.getAnimations().find((played) => played.transitionProperty === "opacity");
		if (fade) {
			keeps(preview, "inert", "");
			fade.finished.then(hide, hide);
		} else hide();
		releaseAuthoredUnder(preview);
		onClose(closed);
	}
	function focusThread(positioned, { closeControl = false, cause = "move" } = {}) {
		if (!positioned) return;
		deferThreadPreviewFocus(positioned, () => {
			const target = closeControl ? previewClose : previewList.querySelector(".lf-page-thread");
			if (!target) return;
			focusDestination(target, cause);
			if (!closeControl) scrollThreadIntoView(target, target);
		});
	}
	function focusTarget(name, { part = null } = {}) {
		const id = threadIdNamed(name);
		const thread = [...previewList.querySelectorAll(".lf-page-thread")].find((candidate) => candidate.dataset.thread === id);
		return thread ? threadFocusDestination(thread, {
			part: part ?? "thread",
			message: name
		}) : null;
	}
	function mount(onDismiss) {
		dismiss = onDismiss;
		previewClose.onclick = onDismiss;
		previewPrevious.onclick = () => stepPreviewThread(-1);
		previewNext.onclick = () => stepPreviewThread(1);
		onCurrentLocation((node, cause, left) => {
			if (node && under(node, preview) && closestAcross(node, ".lf-thread-reply") && cause !== "return" && cause !== "drop") {
				previewSession?.anchor.writing();
				scheduleThreadPreviewPosition();
			}
			const row = left && under(left, preview) && closestAcross(left, ".lf-thread-reply");
			if (row && !(node && under(node, row)) && !row.querySelector(REPLY_BOX)?.value) scheduleThreadPreviewPosition();
		});
		declareOffFlowSurface(preview, { bringBack: (behavior) => scrollToElement(entryPlace(previewSession?.entry) ?? previewSession?.control, behavior, "nearest") });
		move(chromeRoot, preview, chromeForeground);
		previewRegionMounted = true;
		if (previewSession) syncPreviewTranscript();
	}
	return {
		element: preview,
		isOpen: previewOpen,
		selection,
		show,
		refresh,
		releaseLeft,
		close,
		focusThread,
		focusTarget,
		openerKeys,
		thread: () => previewList.querySelector(".lf-page-thread"),
		accompanied: () => previewSession && !previewSession.away ? previewList.querySelector(".lf-page-thread") : null,
		closeFocused: () => focused() === previewClose,
		replying: () => under(focused(), preview) && Boolean(closestAcross(focused(), REPLY_BOX)),
		hasPlacement: () => Boolean(previewSession && threadCardPlace(previewSession)),
		place: placeThreadPreview,
		schedulePosition: scheduleThreadPreviewPosition,
		mount
	};
}

//#endregion
//#region runtime/annotation-overlay/annotation-layer.js
const hidden = Z(false);
const watchers = /* @__PURE__ */ new Set();
const annotationsHidden = () => hidden.value;
function watchAnnotations(watcher) {
	watchers.add(watcher);
}
function mountAnnotationControls() {
	pageCommand({
		id: "annotations.toggle",
		keys: ["o"],
		title: () => hidden.value ? "show annotations" : "hide annotations",
		touch: () => hidden.value ? "Show annotations" : "Hide annotations",
		menu: "annotate",
		when: () => watchers.size > 0,
		run: () => {
			setAnnotationsHidden(!hidden.value);
			notice(!hidden.value ? "Annotations shown" : coarsePointer.matches ? "Annotations hidden" : "Annotations hidden — o shows them");
		}
	});
}
function setAnnotationsHidden(on) {
	if (on === hidden.value) return;
	hidden.value = on;
	setRuntimeRootAttribute(document.documentElement, "data-lf-annotations", on ? "hidden" : null);
	tabStore.set(ANNOTATIONS_KEY, on ? "hidden" : null);
	for (const watcher of watchers) watcher(on);
}
function restoreAnnotations() {
	if (tabStore.get("lf-annotations") === "hidden") setAnnotationsHidden(true);
}

//#endregion
//#region runtime/annotation-overlay/margin-cluster-view.js
const TAG = "leaf-margin-cluster";
var MarginClusterView = class extends HTMLElement {
	#entryKey = null;
	#marker = null;
	#more = null;
	#options = null;
	#optionsId = null;
	#owner = null;
	#toggle = null;
	#offers = Object.freeze([]);
	#surface = null;
	configure({ owner, marker = null, more = null, optionsId = null }) {
		this.#owner = owner;
		this.#marker = marker;
		this.#more = more;
		this.#optionsId = optionsId;
	}
	get marker() {
		return this.#marker;
	}
	get more() {
		return this.#more;
	}
	get options() {
		return this.querySelector(":scope > .lf-margin-options");
	}
	get primary() {
		return this.querySelector(":scope > [data-lf-margin-entry-primary]");
	}
	present(model) {
		if (!this.#owner) throw new Error("Margin presentation needs its view owner");
		const restoreFocus = holdFocus(this);
		this.lfEntry = model.entry;
		keeps(this, "data-lf-margin-for", model.target);
		keeps(this, "aria-label", model.label);
		this.#offers = model.offers;
		this.#surface = "margin";
		this.#owner.prepare(this.#offers, this.#surface);
		if (!this.#marker || !this.#more || !this.#optionsId) throw new Error("Page margin presentation needs its retained controls");
		this.#entryKey = model.options.entryKey;
		const direct = this.#owner.materialize(model.direct);
		const options = this.#owner.materializeOptions(model.options);
		for (const node of direct) node.toggleAttribute("data-lf-margin-entry-primary", model.hasPrimary && node === direct[0]);
		keepsHidden(this.#more, !model.hasOptions || model.optionsOpen && !model.folded);
		if (this.#toggle !== model.toggle) {
			this.#toggle = model.toggle;
			presentContributionEntry(this.#more, contributionEntry({
				key: "options",
				action: model.toggle.action,
				icon: model.toggle.icon,
				label: model.toggle.label,
				accessibleLabel: model.moreLabel,
				behavior: "disclosure",
				rank: "overflow"
			}), { writesRelation: false });
		}
		this.#more.lfEntry = model.entry;
		keeps(this.#more, "aria-label", model.moreLabel);
		keeps(this.#more, "aria-expanded", model.optionsOpen);
		this.toggleAttribute("data-lf-options-open", model.optionsOpen);
		this.toggleAttribute("data-lf-options-expanded", model.optionsExpanded);
		this.toggleAttribute("data-lf-folded", model.folded);
		keeps(this, "data-lf-state", model.state);
		if (!this.#options) {
			this.#options = el("div", "lf-margin-options");
			this.#options.id = this.#optionsId;
			this.#options.setAttribute("role", "group");
		}
		keeps(this.#options, "aria-label", model.options.label);
		keepsHidden(this.#options, model.options.hidden);
		this.#options.lfEntry = model.entry;
		const [marker, more, group] = [
			this.#marker,
			this.#more,
			this.#options
		];
		setChildLists([[this, model.folded ? [
			...direct,
			marker,
			group,
			more
		] : [
			...direct,
			marker,
			more,
			group
		]], [group, options]]);
		restoreFocus?.();
		return this.primary;
	}
	clear() {
		this.#owner?.clearOffers(this.#offers, this.#surface);
		if (this.#entryKey) this.#owner?.retire(this.#entryKey);
		this.#entryKey = null;
		this.#offers = Object.freeze([]);
		this.#surface = null;
		this.replaceChildren();
	}
};
if (!customElements.get(TAG)) customElements.define(TAG, MarginClusterView);
function createMarginClusterViews({ activateContribution, materializeReading, openSpill }) {
	const contributionNotices = /* @__PURE__ */ new WeakMap();
	const spills = /* @__PURE__ */ new Map();
	const controlsOf = (offered, surface) => materializeContributionControls(contributionSource(offered), surface, activateContribution);
	function materializeOne(item) {
		if (item.kind === "contribution") {
			const node = controlsOf(item.offered, "margin").get(item.record.key);
			if (item.cluster) node.lfEntry = item.cluster;
			presentContributionReceipts(node, item.receipt, false);
			return node;
		}
		if (item.kind === "reading") return materializeReading(item);
		if (item.kind === "notice") {
			let node = contributionNotices.get(contributionSource(item.offered));
			if (!node) {
				node = el("span", "lf-margin-receipt");
				contributionNotices.set(contributionSource(item.offered), node);
			}
			keeps(node, "data-lf-margin-receipt", item.notice.tone);
			render(html`${item.notice.text}`, node);
			return node;
		}
		throw new Error(`Unknown margin presentation item: ${item.kind}`);
	}
	const materialize = (items) => items.map(materializeOne);
	const prepare = (offers, surface) => {
		for (const offered of offers) controlsOf(offered, surface);
	};
	const clearOffers = (offers, surface) => {
		if (!surface) return;
		for (const offered of offers) clearContributionControls(contributionSource(offered), surface, /* @__PURE__ */ new Set());
	};
	function materializeOptions(model) {
		const all = materialize(model.items);
		const byItem = new Map(model.items.map((item, index) => [item, all[index]]));
		const visible = new Set(model.visible);
		for (const [item, node] of byItem) {
			node.removeAttribute("data-lf-margin-entry-primary");
			node.toggleAttribute("data-lf-margin-entry-overflow", !visible.has(item));
		}
		const shown = model.visible.map((item) => byItem.get(item));
		if (!model.spill) {
			spills.delete(model.entryKey);
			return shown;
		}
		let spill = spills.get(model.entryKey);
		if (!spill) {
			spill = offer("button", "lf-margin-spill");
			spill.type = "button";
			spills.set(model.entryKey, spill);
		}
		presentContributionEntry(spill, contributionEntry({
			key: "all-options",
			icon: "all",
			label: model.spill.label,
			behavior: "disclosure",
			rank: "overflow",
			state: "idle"
		}));
		keeps(spill, "data-lf-spill-count", model.spill.count);
		keeps(spill, "aria-label", model.spill.label);
		spill.lfFirstSpilledOption = model.spill.first;
		spill.onclick = () => openSpill(model.entry, spill);
		shown.push(spill);
		return shown;
	}
	const owner = {
		materialize,
		materializeOptions,
		prepare,
		clearOffers,
		retire: (entryKey) => spills.delete(entryKey)
	};
	const create = (className, options = {}) => {
		const view = document.createElement(TAG);
		view.className = className;
		generatedElement(view, { says: false });
		view.setAttribute("role", "group");
		view.configure({
			owner,
			...options
		});
		return view;
	};
	return Object.freeze({ createPage: (marker, more, optionsId) => create("lf-ui lf-margin-cluster", {
		marker,
		more,
		optionsId
	}) });
}

//#endregion
//#region runtime/annotation-overlay/margin-projection.js
function createMarginProjection({ inventory, refreshInventory, renderAnnotations, openPageThread, designModeActive, pointerModeActive, leavePageMap, openPageMap, pageMapDialogContains, scrollThreadIntoView, renderMarginThread, placedAt, marksFor, scrollToElement, openInPanel }) {
	const { targetFor, entryPoint, entryPlace, entryPassage, sourceItem, workflowReceipt, threadIdsAt, threadItem: marginThreadItem } = inventory;
	const nav = el("nav", "lf-ui lf-margin-projection");
	generatedElement(nav, { says: false });
	nav.setAttribute("aria-label", "Page Map");
	const toolbar = el("div", "lf-margin-toolbar");
	toolbar.setAttribute("role", "toolbar");
	toolbar.setAttribute("aria-label", "Changes, threads, items on me, delivery status, and activity");
	nav.append(toolbar);
	const card = createThreadPreview({
		inventory,
		renderMarginThread,
		placedAt,
		scrollThreadIntoView,
		scrollToElement,
		openInPanel,
		onClose: closedPreview
	});
	const preview = card.element;
	const previewOpen = card.isOpen;
	let selectedReadingCarriers = /* @__PURE__ */ new Set();
	const readingMarginEntries = /* @__PURE__ */ new Map();
	const hosts = /* @__PURE__ */ new Map();
	function* markerRows() {
		for (const host of hosts.values()) yield host.marker;
	}
	let optionsOrdinal = 0;
	let pageInventory = [];
	let spokenPositions = [];
	let spokenBasis = null;
	function nameMarkers(positions) {
		spokenPositions = positions;
		const walked = pageInventory.map((entry, index) => ({
			entry,
			position: positions[index]
		})).filter(({ entry }) => entryHasMarginHost(entry));
		walked.forEach(({ entry, position }, index) => {
			const marker = hosts.get(entry.key)?.marker;
			const name = markerName(entry, index, walked.length, position);
			paintMarker(marker, entry, hosts.get(entry.key).primary, {
				suppressed: Boolean(focusedOfferOf(entry, expandedOptionsKey, expandedOptionsOwner)),
				accessibleLabel: name
			});
		});
	}
	function readSpokenPositions(inventory, mainRect = marginColumn().getBoundingClientRect(), mainHeight = marginColumn().scrollHeight) {
		spokenBasis = mainRect && {
			width: mainRect.width,
			height: mainHeight
		};
		return inventory.map((entry) => targetFor(entry) && !skipped(targetFor(entry)) && !readingRegionFor(targetFor(entry)) && mainRect && mainHeight ? Math.round((entryPlace(entry).getBoundingClientRect().top - mainRect.top) / mainHeight * 100) : null);
	}
	let transferThreadFocus = false;
	const forcedInlineOptionsKey = () => {
		const selected = card.selection();
		return selected?.disclosed ? selected.entry.key : null;
	};
	let expandedOptionsKey = null;
	const folded = (entry) => standsFolded(hosts.get(entry.key));
	let refoldQueued = false;
	let expandedOptionsOwner = null;
	let hoveredHost = null;
	let highlighted = null;
	let highlightFrame = 0;
	let rovingFrame = 0;
	const inRetainedContext = (node) => node instanceof Element && (Boolean(nativeLayerHolding(node)) || under(node, preview));
	function readingMarginEntry(entry, kind) {
		const marker = hosts.get(entry.key)?.marker;
		if (marker && !marker.hidden && primaryReading(entry)?.kind === kind) return marker;
		const choice = readingChoices(entry).find((candidate) => candidate.kind === kind);
		return choice ? readingMarginEntries.get(readingKey(entry, choice)) ?? null : null;
	}
	const threadMarginEntry = (entry) => readingMarginEntry(entry, "comment");
	const readingControl = (className) => {
		const control = offer("span", className);
		keys(control, "On a margin entry", [{
			id: "margin.press",
			keys: PRESS,
			title: "open / close",
			run: () => control.click()
		}], { when: () => {
			const record = contributionEntryRecord(control);
			return record.behavior === "disclosure" && !record.disabled;
		} });
		return control;
	};
	function syncReadingRelation(control, choice) {
		if (choice?.kind === "comment") {
			keeps(control, "aria-controls", preview.id);
			keeps(control, "aria-expanded", card.selection()?.control === control);
			return;
		}
		const disclosed = choice?.items.length === 1 ? sourceItem(choice.items[0]).discloses?.() : null;
		if (!disclosed) {
			control.removeAttribute("aria-controls");
			control.removeAttribute("aria-expanded");
			return;
		}
		keeps(control, "aria-controls", disclosed.id);
		keeps(control, "aria-expanded", disclosed.open);
	}
	let widthFrame = 0;
	function scheduleWidthRender() {
		if (widthFrame) return;
		widthFrame = nextRender(() => {
			widthFrame = 0;
			renderAnnotations.refresh();
		});
	}
	function marginTargetAt(node) {
		const at = node?.nodeType === 1 ? node : node?.parentElement;
		const control = closestAcross(at, ".lf-margin-entry");
		const source = control && contributionEntrySource(control);
		if (source) return source;
		return closestAcross(at, "[data-lf-margin-for]")?.lfTarget ?? null;
	}
	function markerOptions(row, order) {
		return {
			anchor: () => targetFor(row.lfEntry),
			point: () => entryPoint(row.lfEntry),
			passage: () => entryPassage(row.lfEntry),
			order,
			fold: {
				able: () => canFold(row.lfEntry, {
					expandedKey: expandedOptionsKey,
					expandedOwner: expandedOptionsOwner
				}),
				controls: () => {
					const { options } = clusterProjection(row.lfEntry, {
						expandedKey: row.lfEntry.key,
						folded: true
					});
					return options.visible.length + (options.spill ? 1 : 0) + 1;
				},
				open: () => clusterProjection(row.lfEntry, {
					expandedKey: expandedOptionsKey,
					expandedOwner: expandedOptionsOwner,
					folded: true
				}).optionsOpen,
				changed: () => {
					if (refoldQueued) return;
					refoldQueued = true;
					queueMicrotask(() => {
						refoldQueued = false;
						renderAnnotations.refresh();
					});
				}
			}
		};
	}
	function markerName(entry, index, anchored, position) {
		const choice = primaryReading(entry);
		const face = markerFace(entry).face;
		const count = choice?.items.length ?? 0;
		const userContext = spokenContext(choice);
		const subject = count === 1 && choice.items[0].workflowFace ? choice.text : entry.title;
		const own = count === 1 ? choice.items[0].label : null;
		const said = own && !subject?.includes(own) ? `, ${own}` : "";
		return `${`${face.label}${count > 1 ? `s (${count})` : ""}${said}${userContext ? `, ${userContext}` : ""}`}, ${index + 1} of ${anchored}${position == null ? "" : `, ${Math.max(0, Math.min(100, position))} percent down`}, ${spokenSubject(subject)}`;
	}
	function availableRows() {
		return [...markerRows()].filter((row) => !row.hidden && !row.closest(".lf-withheld") && row.checkVisibility({ visibilityProperty: true }));
	}
	const markerBox = (row) => paintedBox(row, closestAcross(row, "[data-lf-margin-for]"));
	function visibleRows() {
		const clips = /* @__PURE__ */ new Map();
		return availableRows().filter((row) => seenRect(row, clips, markerBox(row)));
	}
	function clusterMarginEntries(host) {
		if (!host) return [];
		return [...host.querySelectorAll(".lf-margin-entry")].filter((button) => !button.disabled && button.getAttribute("aria-disabled") !== "true" && button.checkVisibility());
	}
	const marginEntryHost = (target) => [...hosts.values()].find((host) => host.lfTarget === target) ?? null;
	function marginEntryContextContains(target, node) {
		return Boolean(marginEntryHost(target)?.contains(node)) || pageMapDialogContains(target, node);
	}
	function stepClusterMarginEntries(binding) {
		const active = focused();
		const buttons = clusterMarginEntries(closestAcross(active, "[data-lf-margin-for]"));
		if (buttons.indexOf(active) < 0 || buttons.length < 2) return;
		const direction = binding === rowArrows(active)[1] ? 1 : -1;
		focusDestination(cycledRow(buttons, active, direction), "move");
		beginWalk("margin-entry", "Action", () => {
			const currentLocation = focused();
			const currentLocationHost = closestAcross(currentLocation, "[data-lf-margin-for]");
			return listWalkPosition(clusterMarginEntries(currentLocationHost), currentLocation);
		});
	}
	const landOnToggle = (entry) => layerLanding(() => handBack(hosts.get(entry.key)?.more));
	function setOptionsOpen(entry, open, { land = null, focusOption = null, owner = null, preservePreview = false } = {}) {
		const previousKey = expandedOptionsKey;
		const previousOwner = expandedOptionsOwner;
		const nextKey = open ? entry?.key ?? null : null;
		const nextOwner = open ? owner : null;
		if (previousKey === nextKey && expandedOptionsOwner === nextOwner) return;
		if (card.selection()?.entry && !preservePreview) closePreview();
		expandedOptionsKey = nextKey;
		expandedOptionsOwner = nextOwner;
		const paint = () => {
			if (!open) {
				closeLayer(() => renderAnnotations.refresh(), land);
				return;
			}
			renderAnnotations.refresh();
			if (focusOption && nextKey) {
				const choices = clusterMarginEntries(hosts.get(nextKey)?.options);
				const fallback = clusterMarginEntries(hosts.get(nextKey));
				const next = (focusOption === "last" ? choices.at(-1) : choices[0]) ?? (focusOption === "last" ? fallback.at(-1) : fallback[0]);
				if (next) focusDestination(next, "return");
			}
		};
		if (open) paint();
		else afterScript(paint);
		if (previousOwner === "responses") document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
	}
	function focusForNavigation(control, cause, options) {
		reveal(control);
		focusDestination(control, cause, options);
	}
	function presentedControl(control) {
		if (control?.checkVisibility()) return control;
		if (!control?.matches(".lf-margin-entry")) return null;
		const { key, owner } = contributionEntryRecord(control);
		if (!key || !owner) return null;
		return visibleMarginEntries().find((candidate) => contributionEntryRecord(candidate)?.key === key && contributionEntryRecord(candidate)?.owner === owner && candidate.checkVisibility()) ?? null;
	}
	function openMarginEntryOptions(target, owner) {
		const entry = refreshInventory().find((candidate) => targetFor(candidate) === target && candidate.offers.some((offered) => offered.key === owner));
		if (!entry || !entryHasMarginHost(entry)) return null;
		if (card.selection()?.entry) closePreview();
		const alreadyOpen = expandedOptionsKey === entry.key;
		const previousOwner = alreadyOpen ? expandedOptionsOwner : null;
		setOptionsOpen(entry, true, { owner });
		return () => {
			if (expandedOptionsKey !== entry.key || expandedOptionsOwner !== owner) return;
			setOptionsOpen(alreadyOpen ? entry : null, alreadyOpen, { owner: previousOwner });
		};
	}
	function visibleMarginEntries() {
		return pageInventory.flatMap((entry) => clusterMarginEntries(hosts.get(entry.key)));
	}
	function marginEntryKind(control) {
		const entry = closestAcross(control, "[data-lf-margin-for]")?.lfEntry;
		if (!entry) return null;
		if (control.lfChoice) return control.lfChoice.kind;
		return control === hosts.get(entry.key)?.marker ? primaryReading(entry)?.kind ?? null : null;
	}
	function activateMarginEntry(control) {
		const entry = closestAcross(control, "[data-lf-margin-for]")?.lfEntry;
		if (!targetFor(entry) || !control) return false;
		scrollToElement(entryPlace(entry), void 0, "nearest");
		focusForNavigation(control, "press");
		control.click();
		return true;
	}
	function mapControlPlaces(entry = null) {
		const visible = visibleRows();
		return [entry ? hosts.get(entry.key)?.marker : null, visible.find((row) => row.tabIndex === 0) ?? visible[0]];
	}
	function holdTabStop(next) {
		const available = availableRows();
		const acts = (row) => contributionEntryRecord(row)?.behavior !== "status";
		let stop = next;
		if (stop && !acts(stop)) {
			const at = available.indexOf(stop);
			stop = available.reduce((nearest, row, index) => {
				if (!acts(row)) return nearest;
				if (!nearest) return {
					row,
					distance: Math.abs(index - at)
				};
				const distance = Math.abs(index - at);
				return distance < nearest.distance ? {
					row,
					distance
				} : nearest;
			}, null)?.row;
		}
		rove(markerRows(), stop);
	}
	function syncRoving() {
		const available = availableRows();
		const visible = visibleRows();
		if (!available.length) {
			holdTabStop(null);
			return;
		}
		const currentLocation = available.find((row) => row === focused());
		const candidates = visible.length ? visible : available;
		const room = shownWindow();
		const place = (row) => {
			const box = markerBox(row);
			return [
				box.bottom < room.top ? room.top - box.bottom : box.top > room.bottom ? box.top - room.bottom : 0,
				box.top,
				box.left
			];
		};
		const before = (a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2];
		const nearest = () => candidates.map((row) => ({
			row,
			at: place(row)
		})).reduce((best, next) => before(next.at, best.at) < 0 ? next : best).row;
		holdTabStop(currentLocation ?? nearest());
	}
	function scheduleRoving() {
		cancelRender(rovingFrame);
		rovingFrame = nextRender(() => {
			rovingFrame = 0;
			syncRoving();
		});
	}
	let revealed = null;
	function revealHost(host) {
		const shows = annotationsHidden() && host?.dataset.lfPlace === "pin" ? host : null;
		if (shows === revealed) return;
		revealed?.removeAttribute("data-lf-revealed");
		revealed = shows;
		revealed?.setAttribute("data-lf-revealed", "");
	}
	function currentLocationHost(node) {
		const own = closestAcross(node, ".lf-margin-cluster");
		if (own) return own;
		let found = null;
		for (const host of hosts.values()) if (host.lfTarget && under(node, host.lfTarget) && (!found || under(host.lfTarget, found.lfTarget))) found = host;
		return found;
	}
	const reveal = (node) => revealHost(annotationsHidden() ? currentLocationHost(node) : null);
	onCurrentLocation((node) => {
		if (node && revealed && !revealed.contains(node) && !(revealed.lfTarget && under(node, revealed.lfTarget))) revealHost(null);
	});
	function arriveAtCluster(host, node, cause, left) {
		hoveredHost = null;
		refreshHighlight();
		const control = node.closest?.(".lf-margin-entry");
		if (!(cause === "step" || cause === "move" && !pressLed()) || !control || !host.contains(control)) return;
		const current = host.lfEntry;
		const primary = current && choosePrimary(current);
		const standsFoldedNow = Boolean(current) && folded(current) && canFold(current, {
			expandedKey: expandedOptionsKey,
			expandedOwner: expandedOptionsOwner
		});
		if (!current || !(standsFoldedNow || optionsOffered(current, primary))) return;
		if (expandedOptionsKey === current.key && expandedOptionsOwner) return;
		if (entryEngaged(current)) return;
		const from = left && hostIn(left, host.getRootNode());
		const back = Boolean(from && host.compareDocumentPosition(from) & Node.DOCUMENT_POSITION_FOLLOWING);
		setOptionsOpen(current, true, { focusOption: control === host.more ? standsFoldedNow && !back ? "first" : "last" : null });
	}
	onCurrentLocation((node, cause, left) => {
		if (!node) return;
		for (const host of hosts.values()) if (host.contains(node)) return arriveAtCluster(host, node, cause, left);
	});
	onCurrentLocation((node, cause, left) => {
		if (!left) return;
		for (const host of hosts.values()) {
			if (!under(left, host) || node && under(node, host)) continue;
			nextRender(refreshHighlight);
			const current = host.lfEntry;
			if (current && expandedOptionsKey === current.key && !inRetainedContext(node)) setOptionsOpen(current, false);
		}
	});
	let awaitingRow = null;
	watchAnnotations((hidden) => {
		if (hidden) {
			const holding = closestAcross(focused(), ".lf-margin-cluster");
			if (holding?.dataset.lfPlace === "pin" && holding.lfTarget?.isConnected) focusDestination(holding.lfTarget, "return");
			if (previewOpen()) closePreview();
			awaitingRow = null;
			expandedOptionsKey = null;
			expandedOptionsOwner = null;
		}
		revealHost(null);
		renderAnnotations.refresh();
		repaint();
	});
	let marginKeysAvailable = false;
	const marginKeys = [
		{
			id: "margin.controls",
			keys: ["ArrowLeft", "ArrowRight"],
			title: "move through margin entries",
			repeat: true,
			when: () => {
				const active = focused();
				const host = closestAcross(active, "[data-lf-margin-for]");
				return active?.matches?.(".lf-margin-entry") && clusterMarginEntries(host).length > 1;
			},
			run: stepClusterMarginEntries
		},
		...rowWalk({
			id: "margin",
			noun: "Marker",
			plural: "visible markers",
			rows: visibleRows,
			landed: holdTabStop,
			scroll: false
		}).map((row) => ({
			...row,
			when: () => focused()?.matches?.(".lf-margin-marker") && visibleRows().length > 0
		})),
		...card.openerKeys
	];
	function pressMarker(event) {
		const marker = event.currentTarget;
		const choice = primaryReading(marker.lfEntry);
		if (!choice) return;
		if (choice.kind !== "comment") {
			activate(choice.items[0], marker.lfEntry);
			return;
		}
		openThreadChoice(marker.lfEntry, marker);
	}
	function presentReading(node, entry, choice, { accessibleLabel = null, writesSeat = true } = {}) {
		const items = choice?.items ?? [];
		const face = readingFace(choice);
		const behavior = readingBehavior(face);
		node.lfEntry = entry;
		presentContributionEntry(node, contributionEntry({
			key: `reading:${choice?.key ?? "none"}`,
			icon: face.icon,
			label: readingLabel(choice),
			voice: items.length === 1 && face.voice || "agent",
			context: readingContext(choice),
			behavior,
			rank: "reading",
			state: readingState(choice),
			count: items.length,
			accessibleLabel
		}), {
			writesRelation: false,
			writesSeat
		});
		presentContributionReceipts(node, workflowReceipt(items), awaitingUser(items));
		syncReadingRelation(node, choice);
		syncContributionUnread(node, unreadIn(items));
		return behavior;
	}
	function paintMarker(row, entry, primary, { suppressed = false, accessibleLabel = null } = {}) {
		const { kinds: markerKinds } = markerFace(entry);
		const choice = primaryReading(entry);
		keepsHidden(row, suppressed || markerKinds.length === 0 || Boolean(primary));
		keeps(row, "data-lf-kinds", markerKinds.map(({ kind }) => kind).join(" "));
		row.onclick = presentReading(row, entry, choice, {
			accessibleLabel,
			writesSeat: false
		}) === "status" ? null : pressMarker;
		if (row.lfTakeFocus) {
			delete row.lfTakeFocus;
			if (!row.hidden) focusDestination(row, "return");
		}
	}
	function materializeReadingItem({ entry, choice }) {
		const key = readingKey(entry, choice);
		let node = readingMarginEntries.get(key);
		if (!node) {
			node = readingControl("lf-margin-reading-option");
			readingMarginEntries.set(key, node);
		}
		const face = readingFace(choice);
		const count = choice.items.length;
		const kind = count > 1 ? `${face.label}s` : face.label;
		const userContext = spokenContext(choice);
		const behavior = presentReading(node, entry, choice, { accessibleLabel: `${kind} for ${spokenSubject(entry.title)}${count > 1 ? `, ${count} items` : ""}${userContext ? `, ${userContext}` : ""}` });
		node.lfChoice = choice;
		keeps(node, "data-lf-kinds", choice.kind);
		node.onclick = behavior === "status" ? null : () => {
			if (node.lfChoice.kind !== "comment") {
				setOptionsOpen(node.lfEntry, false, { land: landOnToggle(node.lfEntry) });
				activate(node.lfChoice.items[0], node.lfEntry, { focusMap: false });
				return;
			}
			openThreadChoice(node.lfEntry, node);
		};
		return node;
	}
	function activateContributionControl$1({ offered, entry, control, surface, event }) {
		const consumesFocusedOwner = expandedOptionsKey && expandedOptionsOwner === offered.key;
		if (activateContributionControl({
			offered,
			entry,
			control,
			surface,
			event
		}, reveal) && consumesFocusedOwner) {
			expandedOptionsKey = null;
			expandedOptionsOwner = null;
			renderAnnotations.refresh();
		}
	}
	const clusterViews = createMarginClusterViews({
		activateContribution: activateContributionControl$1,
		materializeReading: materializeReadingItem,
		openSpill: (entry, spill) => openPageMap(entry, {
			invoker: spill,
			focusSpill: true
		})
	});
	function presentCluster(host, marker, more, entry, projection, focus) {
		const primary = host.present(projection);
		const options = host.options;
		const lostOptionFocus = focus.focusedOption && !currentLocationIn(options);
		const lostPrimaryFocus = focus.focusedPrimary && !currentLocationIn(host);
		if (!projection.hasOptions && (focused() === more || lostOptionFocus)) {
			const destination = primary ?? (primaryReading(entry) ? marker : null);
			if (destination === marker && marker.hidden) marker.lfTakeFocus = true;
			else if (destination) focusDestination(destination, "return");
		} else if (focus.focusedToggle && more.hidden) focus.restore?.(clusterMarginEntries(options)[0], primary, clusterMarginEntries(host)[0]);
		else if (lostOptionFocus || lostPrimaryFocus) focus.restore?.(primary, clusterMarginEntries(options)[0], clusterMarginEntries(host)[0]);
	}
	function unfoldOpenThreadOwner(entry) {
		const previousOwner = expandedOptionsOwner;
		expandedOptionsKey = entry.key;
		expandedOptionsOwner = null;
		renderAnnotations.refresh();
		if (previousOwner === "responses") document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
	}
	function renderNow(inventory) {
		const selected = card.selection();
		const forcedKey = selected?.forced ? selected.entry.key : null;
		const threadOwnerHeld = transferThreadFocus || focused() === selected?.control;
		transferThreadFocus = false;
		if (!nav.isConnected) move(chromeRoot, nav, chromeForeground);
		pageInventory = inventory;
		card.releaseLeft(new Set(pageInventory.flatMap((entry) => entry.items.map((item) => item.id))));
		const liveHosts = new Set(pageInventory.filter(entryHasMarginHost).map((entry) => entry.key));
		const liveReadingKeys = new Set(pageInventory.flatMap((entry) => readingChoices(entry).map((choice) => readingKey(entry, choice))));
		for (const key of readingMarginEntries.keys()) if (!liveReadingKeys.has(key)) readingMarginEntries.delete(key);
		if (expandedOptionsKey && !liveHosts.has(expandedOptionsKey)) {
			expandedOptionsKey = null;
			expandedOptionsOwner = null;
		}
		for (const [key, host] of hosts) if (!liveHosts.has(key)) {
			unregisterMarginRow(host);
			host.clear();
			host.remove();
			hosts.delete(key);
		}
		pageInventory.forEach((entry, order) => {
			if (!entryHasMarginHost(entry)) return;
			let host = hosts.get(entry.key);
			let marker = host?.marker;
			let more = host?.more;
			if (host) host.lfEntry = entry;
			if (!host) {
				marker = presentContributionEntry(readingControl("lf-margin-marker"), contributionEntry({
					key: "reading",
					icon: "dot",
					label: "Open page details",
					behavior: "disclosure",
					rank: "reading"
				}), {
					writesRelation: false,
					writesSeat: false
				});
				more = offer("button", "lf-margin-more");
				const optionsId = `lf-margin-options-${++optionsOrdinal}`;
				host = clusterViews.createPage(marker, more, optionsId);
				keys(host, "In the margin", marginKeys, () => marginKeysAvailable);
				host.lfEntry = entry;
				more.setAttribute("aria-controls", optionsId);
				more.onclick = () => {
					const open = expandedOptionsKey !== more.lfEntry.key;
					setOptionsOpen(more.lfEntry, open, { focusOption: open ? "first" : null });
				};
				const takePointerOwnership = (event) => {
					const control = document.elementFromPoint(event.clientX, event.clientY)?.closest?.(".lf-margin-entry");
					hoveredHost = control && host.contains(control) ? host : null;
					refreshHighlight();
				};
				host.addEventListener("pointermove", takePointerOwnership);
				host.addEventListener("pointerleave", () => {
					if (hoveredHost === host) hoveredHost = null;
					refreshHighlight();
				});
				host.addEventListener("click", (event) => {
					if (!expandedOptionsKey || entryEngaged(host.lfEntry)) return;
					const primary = event.target.closest?.("[data-lf-margin-entry-primary]");
					if (primary && host.contains(primary)) setOptionsOpen(host.lfEntry, false);
				}, { capture: true });
				hosts.set(entry.key, host);
			}
			registerMarginRow(host, markerOptions(host, order));
			if (!host.isConnected) move(toolbar, host, pageInventory.slice(order + 1).map((later) => hosts.get(later.key)).find((later) => later?.parentElement === toolbar) ?? null);
			host.lfEntry = entry;
			host.lfTarget = targetFor(entry);
			marker.lfEntry = entry;
			const focus = {
				focusedPrimary: Boolean(host.primary && currentLocationIn(host.primary)),
				focusedOption: Boolean(host.options && currentLocationIn(host.options)),
				focusedToggle: focused() === more,
				restore: holdFocus(host, { key: "data-lf-margin-entry-identity" })
			};
			const projection = clusterProjection(entry, {
				expandedKey: expandedOptionsKey,
				expandedOwner: expandedOptionsOwner,
				forcedInlineKey: forcedKey,
				folded: folded(entry)
			});
			if (!projection.hasOptions && expandedOptionsKey === entry.key) {
				expandedOptionsKey = null;
				expandedOptionsOwner = null;
			}
			presentCluster(host, marker, more, entry, projection, focus);
		});
		nameMarkers(readSpokenPositions(pageInventory));
		keepsHidden(nav, pageInventory.length === 0);
		keeps(nav, "aria-label", `Page Map, ${pageInventory.length} locations`);
		if (selected) {
			const fresh = pageInventory.find((entry) => entry.key === selected.entry.key);
			if (!fresh || !fresh.items.some((item) => item.kind === "comment")) closePreview();
			else {
				const owner = threadMarginEntry(fresh);
				if (owner && !owner.checkVisibility() && forcedKey !== fresh.key && expandedOptionsKey !== fresh.key && !hosts.get(fresh.key)?.more?.hidden) {
					transferThreadFocus = threadOwnerHeld;
					unfoldOpenThreadOwner(fresh);
					return;
				}
				if (!owner || !owner.checkVisibility() && forcedKey !== fresh.key) closePreview();
				else {
					card.refresh(fresh, owner, threadOwnerHeld);
					for (const row of markerRows()) syncReadingRelation(row, primaryReading(row.lfEntry));
					for (const reading of readingMarginEntries.values()) syncReadingRelation(reading, reading.lfChoice);
				}
			}
		}
		refreshHighlight();
		scheduleMarginLayout();
		scheduleRoving();
		scheduleMarginEntryLabels();
		if (marginKeysAvailable !== pageInventory.length > 0) {
			marginKeysAvailable = pageInventory.length > 0;
			paintKeys();
		}
	}
	function highlight(target) {
		if (highlighted === target) return;
		highlighted = target;
		highlightFrame ||= nextRender(() => {
			highlightFrame = 0;
			const part = highlighted ? visualAt(highlighted, { unclaimed: false })?.part : null;
			paintTrace(highlighted, part?.element === highlighted ? part.surface : highlighted);
		});
	}
	function refreshHighlight() {
		const active = focused();
		const focusedHost = closestAcross(active, "[data-lf-margin-for]");
		const pointerHost = hoveredHost?.isConnected ? hoveredHost : null;
		const onTarget = previewOpen() && active && active === targetFor(card.selection()?.entry);
		const marker = pointerHost ?? focusedHost;
		const source = marker ?? ((renderedUnder(active, preview) || previewOpen()) && !onTarget ? hosts.get(card.selection()?.entry?.key) : null);
		const entry = pageInventory.find((candidate) => candidate.key === source?.lfEntry?.key);
		const drawingOnly = entry?.items.length && entry.items.every((item) => item.kind === "comment" && Boolean(sourceItem(item).thread?.root.drawing));
		const currentLocation = currentLocationThreadId();
		const currentLocationShown = !marker && entry && marksFor(currentLocation).length > 0 && threadReading(entry)?.items.some((item) => sourceItem(item).thread.id === currentLocation);
		highlight(drawingOnly || currentLocationShown ? null : targetFor(entry) ?? null);
	}
	function previewChanged() {
		refreshHighlight();
		for (const row of markerRows()) syncReadingRelation(row, primaryReading(row.lfEntry));
		for (const button of readingMarginEntries.values()) syncReadingRelation(button, button.lfChoice);
		paintKeys();
	}
	function showPreview(entry, control, threadItem = null, { origin = null, accompanies = false, forced = false } = {}) {
		if (designModeActive()) return null;
		const previous = card.selection();
		const disclosed = previous?.disclosed && previous.entry.key === entry.key || forced && !control?.checkVisibility() && expandedOptionsKey !== entry.key;
		const positioned = card.show({
			entry,
			control,
			threadItem,
			origin,
			accompanies,
			forced,
			disclosed,
			prepare: () => {
				retirePreviewDisclosure(previous, entry);
				if (disclosed && expandedOptionsKey !== entry.key) setOptionsOpen(entry, true, { preservePreview: true });
				else if (forced && !control?.checkVisibility()) renderAnnotations.refresh();
				return accompanies ? control : threadMarginEntry(entry);
			}
		});
		previewChanged();
		return positioned;
	}
	function togglePinned(entry, button) {
		const selected = card.selection();
		if (selected?.entry.key === entry.key && selected.control === button) {
			closePreview();
			return;
		}
		card.focusThread(showPreview(entry, button));
	}
	const landOnEntry = layerLanding((button) => handBack(button, ...button?.lfEntry ? mapControlPlaces(button.lfEntry) : []));
	function closePreview(land = letGo) {
		const button = card.selection()?.control;
		const at = focused();
		const heldInside = currentLocationIn(preview) && !carryingThreadPlace(at);
		closeLayer(() => card.close(), heldInside && (() => land(button)));
		paintKeys();
	}
	function retirePreviewDisclosure(previous, next = null) {
		if (previous?.disclosed && previous.entry.key !== next?.key && expandedOptionsKey === previous.entry.key) setOptionsOpen(null, false, { preservePreview: true });
	}
	function closedPreview(selection) {
		retirePreviewDisclosure(selection);
		previewChanged();
	}
	const inlineThreadView = {
		showing: () => previewOpen(),
		dismiss: () => closePreview()
	};
	const unfoldedUnder = () => {
		const entry = card.selection()?.control?.lfEntry;
		return Boolean(entry && expandedOptionsKey === entry.key && expandedOptionsKey !== forcedInlineOptionsKey() && optionsRung());
	};
	const stepsOut = (from = focused()) => {
		const target = targetFor(card.selection()?.entry);
		return preview.contains(from) && !unfoldedUnder() && target?.isConnected && target.checkVisibility() ? target : null;
	};
	function keyboardRung({ atFocus = true } = {}) {
		const active = focused();
		const host = closestAcross(active, "[data-lf-margin-for]");
		const nowhere = !active || active === document.body;
		if (!previewOpen() || atFocus && !nowhere && !renderedUnder(active, preview) && !(card.selection()?.control && host?.contains(card.selection()?.control))) return null;
		if (stepsOut()) return {
			root: preview,
			title: "back to element",
			out: () => focusDestination(stepsOut(), "return")
		};
		return {
			root: preview,
			title: "dismiss thread",
			out: () => {
				const currentLocation = unfoldedUnder();
				const button = card.selection()?.control;
				closeLayer(() => closePreview(), currentLocation ? () => landOnEntry(button) : letGo);
			}
		};
	}
	function optionsRung() {
		const host = hosts.get(expandedOptionsKey);
		if (!host?.lfEntry || host.lfEntry.key !== expandedOptionsKey) return null;
		if (entryEngaged(host.lfEntry)) return null;
		if (expandedOptionsKey === forcedInlineOptionsKey()) return null;
		return {
			root: host,
			title: "close options",
			out: () => setOptionsOpen(host.lfEntry, false, { land: landOnToggle(host.lfEntry) })
		};
	}
	pageRung("margin options", optionsRung);
	const pageMapRung = (atFocus = true) => keyboardRung({ atFocus }) ?? null;
	pageScope("page map", {
		title: "In the margin",
		root: () => pageMapRung()?.root ?? document,
		when: () => Boolean(pageMapRung(false)),
		at: () => Boolean(pageMapRung()),
		rows: [{
			id: "margin.back",
			touch: false,
			keys: ["Escape"],
			description: () => pageMapRung(false)?.description,
			title: () => pageMapRung(false)?.title,
			commandReferenceWhen: () => Boolean(pageMapRung(false)),
			when: () => Boolean(pageMapRung()),
			run: () => pageMapRung()?.out()
		}]
	});
	function activate(item, entry, { focusMap = true } = {}) {
		if (expandedOptionsKey && expandedOptionsKey !== entry.key) setOptionsOpen(entry, false);
		const landsOnTarget = focusMap && !entryHasMarginHost(entry);
		closeLayer(() => {
			closePreview();
			leavePageMap();
		}, focusMap && (() => {
			if (!landsOnTarget) return handBack(...mapControlPlaces(entry));
			sourceItem(item).activate();
			if (targetFor(entry)?.isConnected) focusDestination(targetFor(entry), "move");
		}));
		if (!landsOnTarget) sourceItem(item).activate();
	}
	function openThreadChoice(entry, button) {
		const choice = threadReading(entry);
		if (!choice) return;
		if (expandedOptionsKey && expandedOptionsKey !== entry.key) setOptionsOpen(entry, false);
		const intent = retainUserIntent();
		const held = revealHeld(choice.items.map((item) => sourceItem(item).thread.id));
		if (held) {
			intent.handoff(closePreview);
			held.presented.then(() => openPageThread(held.id, {
				part: "thread",
				travel: false,
				intent
			}));
			return;
		}
		togglePinned(entry, button);
	}
	function openInlineThread(id, { origin = null, unfold = true } = {}) {
		const itemId = marginThreadItem(threadNamed(id));
		const entry = pageInventory.find((candidate) => candidate.items.some((item) => item.id === itemId));
		if (!entry || designModeActive()) return null;
		if (!threadReading(entry)) return null;
		const shown = (control) => control?.checkVisibility() ? control : null;
		const host = hosts.get(entry.key);
		const marker = unfold ? null : shown(threadMarginEntry(entry)) ?? shown(host?.marker);
		if (!unfold && !marker && !shown(host)) return null;
		const positioned = showPreview(entry, marker ?? threadMarginEntry(entry), itemId, {
			origin,
			accompanies: !unfold,
			forced: true
		});
		const thread = card.thread();
		return thread && positioned && {
			thread,
			presented: positioned
		};
	}
	function paintSelectedMarginEntries(selections) {
		refreshHighlight();
		const selected = /* @__PURE__ */ new Set();
		for (const selection of selections) for (const entry of pageInventory) {
			if (targetFor(entry) !== selection.target) continue;
			const control = readingMarginEntry(entry, selection.kind);
			if (control?.isConnected) selected.add(control);
		}
		for (const control of selectedReadingCarriers) if (!selected.has(control)) syncContributionSelection(control, false);
		for (const control of selected) syncContributionSelection(control, true);
		selectedReadingCarriers = selected;
	}
	const threadIdOf = (entry) => sourceItem(threadReading(entry).items[0]).thread.id;
	const entryThread = (node) => {
		if (under(node, preview) && previewOpen()) {
			const selected = card.selection();
			const item = selected && threadReading(selected.entry)?.items.find((candidate) => candidate.id === selected.threadItem);
			if (item) return sourceItem(item).thread.id;
		}
		const entry = closestAcross(node, ".lf-margin-entry")?.lfEntry;
		return entry && threadReading(entry) ? threadIdOf(entry) : null;
	};
	const pointedThread = () => {
		const entry = hoveredHost?.isConnected ? hoveredHost.lfEntry : null;
		return entry && threadReading(entry) ? threadIdOf(entry) : null;
	};
	const threadIdsOf = (entry) => threadReading(entry).items.map((item) => sourceItem(item).thread.id);
	const seatedOnPage = (id) => claimed(id) || [...document.querySelectorAll(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`)].some((seat) => closestAcross(seat, ".lf-thread-seat[data-lf-thread-seat]"));
	const threadEntryAt = (node) => {
		const ids = threadIdsAt(node);
		const here = (entry) => threadReading(entry) && threadIdsOf(entry).some((id) => ids.includes(id)) && !seatedOnPage(threadIdOf(entry));
		const shown = previewOpen() && card.selection()?.entry?.key;
		return pageInventory.find((entry) => entry.key === shown && here(entry)) ?? pageInventory.find(here) ?? null;
	};
	let currentLocationUnfolded = null;
	const byKeyboard = () => !pressLed();
	function unfoldCurrentLocation(active) {
		const host = active && closestAcross(active, "[data-lf-margin-for]");
		if (host?.lfEntry?.key === currentLocationUnfolded) {
			currentLocationUnfolded = null;
			return;
		}
		const state = {
			expandedKey: expandedOptionsKey,
			expandedOwner: expandedOptionsOwner
		};
		const place = active && !host && byKeyboard() && arrivalOf(active);
		const entry = place ? pageInventory.find((candidate) => folded(candidate) && canFold(candidate, state) && under(place, targetFor(candidate))) : null;
		if (entry?.key === currentLocationUnfolded) return;
		if (currentLocationUnfolded && expandedOptionsKey === currentLocationUnfolded) setOptionsOpen(null, false, { preservePreview: true });
		currentLocationUnfolded = null;
		if (!entry || expandedOptionsKey === entry.key) return;
		setOptionsOpen(entry, true, { preservePreview: true });
		currentLocationUnfolded = entry.key;
	}
	function accompany(node, entry) {
		awaitingRow = null;
		if (openInlineThread(threadIdOf(entry), { unfold: false })) return;
		if (previewOpen() && card.selection()?.entry?.key !== entry.key) closePreview();
		awaitingRow = node;
	}
	function accompanyShownRow() {
		const node = awaitingRow;
		awaitingRow = null;
		if (!node || focused() !== node || previewOpen() || annotationsHidden() || designModeActive()) return;
		const entry = arrivalOf(node) && threadEntryAt(node);
		if (entry) accompany(node, entry);
	}
	function followCurrentLocation() {
		awaitingRow = null;
		refreshHighlight();
		const active = focused();
		unfoldCurrentLocation(active);
		if (!active || active === document.body || renderedUnder(active, preview) || designModeActive()) return;
		const host = closestAcross(active, "[data-lf-margin-for]");
		if (host) {
			if (previewOpen() && host.lfEntry?.key !== card.selection()?.entry?.key) closePreview();
			return;
		}
		const entry = arrivalOf(active) && threadEntryAt(active);
		if (!entry) {
			if (previewOpen() && !inChrome(active)) closePreview();
			return;
		}
		if (previewOpen() && card.selection()?.entry?.key === entry.key) return;
		if (byKeyboard()) accompany(active, entry);
		else if (previewOpen()) closePreview();
	}
	declareRelease(() => {
		if (previewOpen()) closePreview();
	});
	const pressedAway = (path) => {
		if (!previewOpen()) return false;
		if ((pointerModeActive() ? [preview] : [
			preview,
			hosts.get(card.selection()?.entry?.key),
			targetFor(card.selection()?.entry)
		]).some((node) => node && path.includes(node))) return false;
		return !path.some(inRetainedContext);
	};
	const marginEntryChoices = (target) => clusterMarginEntries(marginEntryHost(target));
	const accompaniedThreadHere = () => card.accompanied();
	declareSide((node) => {
		const projected = marginTargetAt(node);
		if (projected) return projected;
		if (under(node, preview)) return targetFor(card.selection()?.entry);
		return null;
	});
	function captureCurrentLocation() {
		const active = focused();
		const host = closestAcross(active, "[data-lf-margin-for]");
		const control = active?.closest?.(".lf-margin-entry");
		const selected = card.selection();
		const entry = selected?.entry ?? host?.lfEntry;
		if (!entry) return null;
		const currentLocation = {
			entry: entry.key,
			preview: previewOpen() && !card.replying() ? {
				thread: selected.threadItem,
				accompanies: selected.accompanies
			} : null,
			focus: card.closeFocused() ? { kind: "preview-close" } : under(active, preview) ? { kind: "preview" } : control && host?.contains(control) ? {
				kind: "entry",
				key: contributionEntryRecord(control)?.key,
				owner: contributionEntryRecord(control)?.owner ?? null
			} : null
		};
		return currentLocation.preview || currentLocation.focus?.kind === "entry" ? currentLocation : null;
	}
	function restoreCurrentLocation(currentLocation) {
		if (!currentLocation || typeof currentLocation.entry !== "string") return false;
		const entry = pageInventory.find((candidate) => candidate.key === currentLocation.entry);
		if (!entry) return false;
		const shown = currentLocation.preview ? restoreCard(entry, currentLocation) : false;
		return currentLocation.focus?.kind === "entry" ? restoreEntryFocus(entry, currentLocation) : shown;
	}
	function restoreCard(entry, { preview: { thread, accompanies }, focus }) {
		const items = entry.items.filter((item) => item.kind === "comment");
		const item = items.find((candidate) => candidate.id === thread) ?? items[0];
		if (!item) return false;
		const id = sourceItem(item).thread.id;
		const selected = card.selection();
		const kept = selected?.entry.key === entry.key && selected.threadItem === item.id;
		if (kept && card.hasPlacement()) return true;
		if (kept) closePreview();
		const inCard = focus?.kind === "preview" || focus?.kind === "preview-close";
		if (accompanies && !inCard) return Boolean(openInlineThread(id, { unfold: false }));
		const intent = retainUserIntent();
		const opened = openPageThread(id, {
			part: "thread",
			focus: inCard,
			travel: false,
			scroll: false,
			intent
		});
		if (focus?.kind === "preview-close") opened.then((destination) => {
			if (destination && under(destination, preview) && intent()) card.focusThread(Promise.resolve(true), {
				closeControl: true,
				cause: "return"
			});
		});
		return true;
	}
	function restoreEntryFocus(entry, currentLocation) {
		const control = clusterMarginEntries(hosts.get(entry.key)).find((candidate) => contributionEntryRecord(candidate)?.key === currentLocation.focus.key && (contributionEntryRecord(candidate)?.owner ?? null) === currentLocation.focus.owner);
		if (!control) return false;
		if (focused() === control) return true;
		focusDestination(control, "return");
		return true;
	}
	function mount() {
		mountMarginLayer(toolbar);
		card.mount(() => closePreview(landOnEntry));
		document.addEventListener("lf-margin-layout", ({ detail: { column, height } }) => {
			accompanyShownRow();
			card.place();
			scheduleMarginEntryLabels();
			if (column.width === spokenBasis?.width && height === spokenBasis?.height) return;
			const moved = readSpokenPositions(pageInventory, column, height);
			if (moved.some((position, index) => position !== spokenPositions[index])) nameMarkers(moved);
		});
		document.addEventListener("pointerover", scheduleMarginEntryLabels, { capture: true });
		document.addEventListener("pointerout", scheduleMarginEntryLabels, { capture: true });
		onCurrentLocation((node, cause) => {
			if (cause === "drop") return;
			scheduleMarginEntryLabels();
			queueMicrotask(followCurrentLocation);
		});
		onPressAway(pressedAway, () => closePreview());
		const unfolded = () => hosts.get(expandedOptionsKey) ?? null;
		onPressAway((path) => {
			const host = unfolded();
			return Boolean(host) && !path.includes(host) && !path.some(inRetainedContext);
		}, () => setOptionsOpen(unfolded().lfEntry, false));
		watchRoom(() => scheduleRoving());
		window.addEventListener("resize", () => scheduleWidthRender());
		renderAnnotations();
		move(chromeRoot, nav, chromeForeground);
	}
	return {
		pageMapActive: () => availableRows().includes(focused()),
		releaseForMap: (entry) => {
			if (expandedOptionsKey && expandedOptionsKey !== entry.key) setOptionsOpen(entry, false);
			closePreview();
		},
		mapFocusTarget: (entry) => {
			const visible = visibleRows();
			return entry ? hosts.get(entry.key)?.marker ?? null : visible.find((row) => row.tabIndex === 0) ?? visible[0] ?? null;
		},
		targetFor,
		paint: renderNow,
		flushLayout: layoutMarginRows,
		scheduleThreadPreviewPosition: card.schedulePosition,
		marginTargetAt,
		marginEntryContextContains,
		focusForNavigation,
		presentedControl,
		openMarginEntryOptions,
		visibleMarginEntries,
		marginEntryKind,
		activateMarginEntry,
		closePreview,
		entryThread,
		pointedThread,
		inlineThreadView,
		keyboardRung,
		optionsRung,
		openInlineThread,
		threadPreview: {
			open: openInlineThread,
			focusTarget: card.focusTarget,
			accompanied: accompaniedThreadHere,
			close: closePreview
		},
		paintSelectedMarginEntries,
		marginEntryChoices,
		captureCurrentLocation,
		restoreCurrentLocation,
		mount
	};
}

//#endregion
//#region runtime/annotation-overlay/anchor-paint.js
const MARK = "lf-mark";
const PENDING = "lf-pending";
const REACT = "lf-react";
const HOVER = "lf-mark-hover";
const HERE = "lf-mark-here";
function createAnchorPaint({ targetPaint, pointer, currentLocationThreadId, currentLocationObligation, rowThread, threadRow, marginThread }) {
	const marked = /* @__PURE__ */ new Map();
	const visualTargets = /* @__PURE__ */ new Map();
	let pendingMarks = [];
	let pendingOutline = [];
	let actionOutline = [];
	let hovering = null;
	let hoverFromRow = false;
	let hoverParts = [];
	let hoveredRow = null;
	let hereParts = [];
	let hoverFrame = 0;
	let mounted = false;
	const marksFor = (id) => marked.get(id) ?? [];
	const elementMarks = (where) => [...where].flat().filter((mark) => mark instanceof Element);
	const rememberVisual = (resolved) => {
		const element = targetElement(resolved);
		const surface = targetSurface(resolved);
		if (element && surface) visualTargets.set(element, surface);
	};
	function paintVisualStates() {
		const pending = new Set(pendingOutline);
		const action = new Set(actionOutline);
		const hover = new Set(elementMarks(hoverParts));
		const here = new Set(elementMarks(hereParts));
		const elements = new Set([
			pending,
			action,
			hover,
			here
		].flatMap((states) => [...states]).filter((element) => element instanceof Element));
		const active = visibleFocus();
		const obligation = currentLocationObligation();
		const obligationRing = obligation && (active === obligation || shownParts(obligation).includes(active));
		const ownsRing = active && ringBox(active) === active && !obligationRing;
		if (ownsRing && active.getRootNode() === document && pageWords(active)) elements.add(active);
		const focus = new Set(ownsRing && elements.has(active) ? [active] : []);
		const sources = [
			["pending", pending],
			["action", action],
			["hover", hover],
			["focus", focus],
			["here", here]
		];
		targetPaint.setTargets([...elements].map((element) => ({
			element,
			surface: visualTargets.get(element) ?? element,
			states: new Set(sources.filter(([, members]) => members.has(element)).map(([state]) => state))
		})));
	}
	const outlined = () => /* @__PURE__ */ new Set([
		...elementMarks(marked.values()),
		...pendingOutline,
		...actionOutline
	]);
	function paintOutlines(before) {
		const marks = new Set(elementMarks(marked.values()));
		const pending = new Set(pendingOutline);
		const action = new Set(actionOutline);
		for (const element of /* @__PURE__ */ new Set([...before, ...outlined()])) {
			element.classList.toggle("lf-mark-el", marks.has(element) || pending.has(element));
			element.classList.toggle(PENDING, pending.has(element));
			element.classList.toggle("lf-action-target", action.has(element));
		}
	}
	function paintHover(id, fromRow, repaintVisuals = true) {
		hovering = id;
		hoverFromRow = fromRow;
		const where = marksFor(id);
		const parts = fromRow ? where.filter((mark) => mark instanceof Element) : [];
		for (const part of hoverParts) if (!parts.includes(part)) part.classList.toggle(HOVER, false);
		for (const part of parts) part.classList.toggle(HOVER, true);
		hoverParts = parts;
		CSS.highlights.set(HOVER, Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), { priority: 1 }));
		if (repaintVisuals) paintVisualStates();
	}
	function markRow(id) {
		const row = id && marksFor(id).length ? threadRow(id) : null;
		if (row === hoveredRow) return;
		hoveredRow?.classList.toggle(HOVER, false);
		row?.classList.toggle(HOVER, true);
		hoveredRow = row;
	}
	function paintCurrentLocation(repaintVisuals = true) {
		const where = marksFor(currentLocationThreadId());
		const parts = where.filter((mark) => mark instanceof Element);
		for (const part of hereParts) if (!parts.includes(part)) part.classList.toggle(HERE, false);
		for (const part of parts) part.classList.toggle(HERE, true);
		hereParts = parts;
		CSS.highlights.set(HERE, Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), { priority: 2 }));
		if (repaintVisuals) paintVisualStates();
	}
	function markAt(x, y) {
		if (annotationsHidden()) return null;
		const over = document.elementFromPoint(x, y);
		if (!pageWords(over)) return null;
		const deep = elementFromPointAcross(x, y);
		for (const [id, marks] of marked) for (const where of marks) if (where instanceof Range ? [...where.getClientRects()].some((rect) => x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) : under(deep, where)) return id;
		return null;
	}
	function refreshHover() {
		if (hoverFrame || !marked.size && !hovering && !hoveredRow) return;
		hoverFrame = nextRender(() => {
			hoverFrame = 0;
			const at = pointer();
			const onMark = markAt(at.x, at.y);
			document.body.classList.toggle("lf-over-mark", Boolean(onMark));
			const row = rowThread();
			const id = row ?? onMark;
			if (id !== hovering || Boolean(row) !== hoverFromRow) paintHover(id, Boolean(row));
			markRow(id ?? marginThread());
		});
	}
	function paint({ readings, draft, action }) {
		const before = outlined();
		marked.clear();
		pendingOutline = [];
		actionOutline = [];
		visualTargets.clear();
		const posted = [];
		const reactions = [];
		for (const { thread, placement: found } of readings) {
			if (found.status === "outdated" || thread.resolved) continue;
			if (bareReaction(thread)) {
				reactions.push(...targetSegments(found).map((segment) => rangeOf([segment])));
				continue;
			}
			if (targetElement(found)) {
				rememberVisual(found);
				if (!thread.root.drawing) marked.set(thread.id, targetParts(found));
			} else if (!thread.root.drawing) {
				const ranges = targetSegments(found).map((segment) => rangeOf([segment]));
				marked.set(thread.id, ranges);
				posted.push(...ranges);
			}
		}
		const resolvedDraft = draft.resolved;
		pendingMarks = Boolean(resolvedDraft && resolvedDraft.status !== "outdated") && !draft.drawing ? targetElement(resolvedDraft) ? targetParts(resolvedDraft) : targetSegments(resolvedDraft).map((segment) => rangeOf([segment])) : [];
		if (resolvedDraft) rememberVisual(resolvedDraft);
		const pending = [];
		if (targetElement(resolvedDraft)) pendingOutline = pendingMarks;
		if (targetSegments(resolvedDraft).length) pending.push(...pendingMarks);
		actionOutline = targetElement(action) ? targetParts(action) : [];
		if (action) rememberVisual(action);
		paintOutlines(before);
		CSS.highlights.set(MARK, new Highlight(...posted));
		CSS.highlights.set(REACT, new Highlight(...reactions));
		CSS.highlights.set(PENDING, Object.assign(new Highlight(...pending), { priority: 3 }));
		paintCurrentLocation(false);
		if (hovering) paintHover(hovering, hoverFromRow, false);
		paintVisualStates();
		refreshHover();
	}
	function mount() {
		if (mounted) return;
		mounted = true;
		document.addEventListener("pointermove", refreshHover);
	}
	function destroy() {
		if (mounted) document.removeEventListener("pointermove", refreshHover);
		mounted = false;
		if (hoverFrame) cancelRender(hoverFrame);
		hoverFrame = 0;
		const before = outlined();
		marked.clear();
		pendingOutline = [];
		actionOutline = [];
		paintOutlines(before);
		for (const element of hereParts) element.classList.toggle(HERE, false);
		for (const element of [...hoverParts, hoveredRow]) element?.classList.toggle(HOVER, false);
		for (const name of [
			MARK,
			REACT,
			PENDING,
			HOVER,
			HERE
		]) CSS.highlights.delete(name);
		targetPaint.setTargets([]);
		pendingMarks = [];
		visualTargets.clear();
		hovering = null;
		hoverFromRow = false;
		hoverParts = [];
		hoveredRow = null;
		hereParts = [];
	}
	return {
		mount,
		destroy,
		paint,
		paintCurrentLocation,
		refreshHover,
		markAt,
		marksFor
	};
}

//#endregion
//#region runtime/annotation-overlay/visual-mark-paint.js
const PROJECTED = "lf-projected-mark";
const STATE_CLASSES = {
	pending: "lf-visual-mark-pending",
	action: "lf-visual-mark-action",
	hover: "lf-visual-mark-hover",
	focus: "lf-visual-mark-focus",
	here: "lf-visual-mark-here"
};
const INSET = "lf-visual-mark-inset";
function ringRoom() {
	return parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--focus-ring-w"));
}
function cramped({ rect, levels }, room) {
	const short = (band, low, high) => rect[low] >= band[low] && rect[low] - room < band[low] || rect[high] <= band[high] && rect[high] + room > band[high];
	return levels.some(({ holder, band, axes }) => holder && (axes.x && short(band, "left", "right") || axes.y && short(band, "top", "bottom")));
}
function createVisualMarkPaint() {
	const layer = el("div", "lf-ui lf-visual-marks");
	layer.setAttribute("aria-hidden", "true");
	let targets = /* @__PURE__ */ new Map();
	const overlays = /* @__PURE__ */ new Map();
	let placementFrame = 0;
	let geometryFrame = 0;
	let geometryDirty = false;
	function syncStates() {
		for (const [element, { overlay }] of overlays) {
			const states = targets.get(element)?.states ?? /* @__PURE__ */ new Set();
			for (const [state, className] of Object.entries(STATE_CLASSES)) overlay.classList.toggle(className, states.has(state));
		}
	}
	function paintTargets(rebuildGeometry = true) {
		const room = ringRoom();
		for (const element of [...overlays.keys()]) if (!targets.has(element)) {
			element.classList.toggle(PROJECTED, false);
			dropStand(overlays.get(element).stand);
			overlays.delete(element);
		}
		for (const [element, target] of targets) {
			let record = overlays.get(element);
			const geometry = rebuildGeometry || !record ? paintGeometry(target.surface) : record.geometry;
			const placed = placement(target.surface, Boolean(geometry), inChrome(element));
			if (!placed.shown) {
				element.classList.toggle(PROJECTED, false);
				if (record) {
					record.geometry = geometry;
					record.shapeKey = "";
					record.overlay.style.display = "none";
				}
				continue;
			}
			if (!record) {
				const overlay = el("div", "lf-ui lf-visual-mark");
				const shape = document.createElementNS(SVG_NS, "svg");
				shape.classList.add("lf-visual-mark-shape");
				overlay.append(shape);
				const stand = paintStand(overlay);
				layer.append(stand.root);
				record = {
					overlay,
					shape,
					stand,
					geometry: null,
					shapeKey: ""
				};
				overlays.set(element, record);
			}
			const { overlay, shape, stand } = record;
			const { rect, shapeKey } = placed;
			element.classList.toggle(PROJECTED, true);
			keeps(overlay, "data-for", element.id || null);
			overlay.classList.toggle("lf-shaped", Boolean(geometry));
			overlay.classList.toggle(INSET, !geometry && cramped(placed, room));
			if (rebuildGeometry || record.geometry !== geometry || record.shapeKey !== shapeKey) {
				if (geometry) paintShape(shape, geometry, rect);
				else shape.replaceChildren();
				record.geometry = geometry;
				record.shapeKey = shapeKey;
			}
			keeps(stand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
			standOver(stand, placed, geometry ? "0" : getComputedStyle(target.surface).borderRadius);
		}
		syncStates();
	}
	function setTargets(next) {
		const nextTargets = new Map([...next].filter((target) => target.states?.size).map((target) => [target.element, target]));
		const identitiesChanged = nextTargets.size !== targets.size || [...nextTargets].some(([element, target]) => targets.get(element)?.surface !== target.surface);
		targets = nextTargets;
		const rebuild = identitiesChanged || geometryDirty;
		if (rebuild && geometryFrame) cancelRender(geometryFrame);
		if (rebuild && placementFrame) cancelRender(placementFrame);
		if (rebuild) geometryFrame = placementFrame = 0;
		geometryDirty = false;
		paintTargets(rebuild);
	}
	function shifted() {
		if (placementFrame || geometryFrame || !targets.size) return;
		placementFrame = nextRender(() => {
			placementFrame = 0;
			paintTargets(false);
		});
	}
	function geometryChanged() {
		geometryDirty = true;
		if (placementFrame) cancelRender(placementFrame);
		placementFrame = 0;
		if (geometryFrame || !targets.size) return;
		geometryFrame = nextRender(() => {
			geometryFrame = 0;
			if (!geometryDirty) return;
			geometryDirty = false;
			paintTargets(true);
		});
	}
	return {
		layer,
		setTargets,
		shifted,
		geometryChanged
	};
}

//#endregion
//#region runtime/annotation-overlay/composing/floating-response.js
function createFloatingResponsePlacement({ bar: fabBar, input: fabInput, response, positioned, dismiss, scrollToElement, scrollToRange }) {
	const floatBoundary = (region = null) => commentBoundary({
		region,
		right: rightCover()
	});
	const fabPlacement = commentPlacement();
	let fabPositionFrame = 0;
	let fabWithheld = false;
	let fabWithheldFocus = null;
	const fabPosition = floatingPlacement({
		floating: fabBar,
		update: () => scheduleFabPosition()
	});
	let nativeAttachment = false;
	let editingAttachment = null;
	let windowPosture = false;
	let fabRegion = null;
	const carry = surfaceGrip({
		surface: fabBar,
		bounds: () => floatBoundary(fabRegion),
		dropped(box) {
			if (!response.anchor || !response.floating) return;
			if (box && response.open) fabPlacement.adopt({
				box,
				placement: {
					...fabPlacement.capture(),
					moved: true
				}
			});
			nativeAttachment = false;
			placeFab();
		}
	});
	fabBar.append(carry.grip);
	const fabField = () => fabInput.parentElement;
	let following = null;
	const readFab = () => {
		if (!following && !response.open) return;
		if (!response.floating || !fabBar.hasAttribute("data-lf-placement")) return following?.forget();
		following ??= fabMotion();
		following.follow();
	};
	const followed = sizeObserver(() => {
		if (following && response.open && fabBar.hasAttribute("data-lf-placement")) {
			nativeAttachment = false;
			if (placeFab()) return;
		}
		readFab();
	});
	function fabMotion() {
		const box = fabField();
		const motion = boxMotion({
			root: box.parentElement,
			box,
			surface: "lf-fab-ground",
			lift: 1,
			outset: 0,
			observer: followed,
			held: () => heldEdges(fabBar)
		});
		fabBar.prepend(motion.ground);
		followed.observe(box.parentElement);
		return motion;
	}
	let selectedPassage = null;
	const fabFrameAt = () => {
		if (!response.open || !response.floating) return null;
		const bar = fabBar.getBoundingClientRect();
		const field = fabField().getBoundingClientRect();
		const style = getComputedStyle(fabBar);
		const scaleX = bar.width / parseFloat(style.width);
		const scaleY = bar.height / parseFloat(style.height);
		const left = parseFloat(style.paddingLeft);
		const top = parseFloat(style.paddingTop);
		const width = field.width / scaleX + left + parseFloat(style.paddingRight);
		const height = field.height / scaleY + top + parseFloat(style.paddingBottom);
		return {
			box: new DOMRect(field.left - left * scaleX, field.top - top * scaleY, width * scaleX, height * scaleY).toJSON(),
			placement: fabPlacement.capture(),
			field: following?.outline() ?? field.toJSON(),
			fromEnd: fabInput.scrollHeight - fabInput.clientHeight - fabInput.scrollTop
		};
	};
	const nativeRowEnd = () => {
		const style = getComputedStyle(fabBar);
		const rows = style.gridTemplateRows.split(" ").map(parseFloat);
		return Math.round(rows.reduce((height, row) => height + row, 0) + parseFloat(style.rowGap) * (rows.length - 1) + parseFloat(style.paddingTop));
	};
	const fabFits = () => {
		const boundary = floatBoundary();
		return boundary.width > 0 && Math.ceil(boundary.width) >= Math.ceil(fabBar.getBoundingClientRect().width);
	};
	function stopFabPositioning({ reset = false } = {}) {
		carry.placed();
		nativeAttachment = false;
		fabPosition.stop();
		cancelRender(fabPositionFrame);
		fabPositionFrame = 0;
		if (!reset) return;
		following?.forget();
		editingAttachment = null;
		windowPosture = false;
		fabPlacement.forget();
		fabBar.removeAttribute("data-lf-placement");
		for (const property of ["--lf-float-w", "--lf-float-h"]) fabBar.style.removeProperty(property);
	}
	function scheduleFabPosition() {
		if (fabPositionFrame || !response.anchor || !response.floating || fabBar.hasAttribute("data-lf-carried")) return;
		fabPositionFrame = nextRender(() => {
			fabPositionFrame = 0;
			placeFab();
		});
	}
	let observationModes = null;
	function watchFabPosition(target, autoUpdate, getOverflowAncestors) {
		const reference = {
			contextElement: response.pointIn(target) ?? target,
			getBoundingClientRect: () => anchorGeometry(response.anchor)?.box ?? target.getBoundingClientRect()
		};
		if (!observationModes) observationModes = {
			editing: (reference, floating, update) => {
				const invalidate = () => {
					nativeAttachment = false;
					update();
				};
				const stopSize = autoUpdate(reference, floating, invalidate, {
					ancestorScroll: false,
					layoutShift: false
				});
				let x = reference.getBoundingClientRect().left;
				const scrollers = getOverflowAncestors(reference.contextElement);
				const scrollPose = () => scrollers.map((node) => [node.scrollX ?? node.scrollLeft, node.scrollY ?? node.scrollTop]);
				let pose = scrollPose();
				const stopMotion = autoUpdate(reference, floating, () => {
					const next = reference.getBoundingClientRect().left;
					const now = scrollPose();
					const scrolled = now.some((axes, i) => axes.some((value, axis) => value !== pose[i][axis]));
					pose = now;
					if (scrolled) {
						x = next;
						return;
					}
					if (next === x) return;
					x = next;
					invalidate();
				}, {
					ancestorScroll: false,
					ancestorResize: false,
					elementResize: false,
					layoutShift: true
				});
				return () => {
					stopMotion();
					stopSize();
				};
			},
			compact: autoUpdate
		};
		const observes = observationModes;
		fabPosition.watch(target, reference, response.open ? observes.editing : observes.compact);
	}
	function selectedRange(anchor) {
		if (selectedPassage && sameAnchor(anchor, selectedPassage.anchor) && selectedPassage.start.isConnected && selectedPassage.end.isConnected && quoteFrom(segmentsIn(selectedPassage.range)) === anchor.quote) return selectedPassage.range;
		selectedPassage = null;
		return null;
	}
	function anchorGeometry(anchor) {
		if (anchor?.quote) {
			const selection = pageSelection();
			const current = selection ? selectionAnchor(selection) : null;
			if (current && sameAnchor(anchor, current)) {
				const range = pageRange(selection).cloneRange();
				selectedPassage = {
					anchor,
					range,
					start: range.startContainer,
					end: range.endContainer
				};
				return rangeGeometry(range);
			}
			if (!response.open && !response.captured) return null;
			const retained = selectedRange(anchor);
			if (retained) return rangeGeometry(retained);
		}
		const found = response.resolved;
		if (!anchor || !found) return null;
		const words = anchor.quote ? passageGeometry(found) : null;
		if (words) return words;
		const box = union(targetParts(found).map((part) => shownBox(part)).filter(Boolean));
		const point = box && response.pointIn(targetElement(found));
		const elementBox = point ? pointBand(union(targetParts(found).map((part) => shownBox(part))), point) : box;
		return elementBox ? {
			box: elementBox,
			attachment: null,
			contextNode: point ?? targetElement(found)
		} : null;
	}
	function placeFab({ reveal = false } = {}) {
		if (!response.anchor) return false;
		const geometry = anchorGeometry(response.anchor);
		if (!geometry && !response.open) return false;
		const context = geometry?.contextNode;
		const owner = response.target ?? blockAt(context) ?? (context?.nodeType === Node.ELEMENT_NODE ? context : context?.parentElement) ?? null;
		const windowBoundary = floatBoundary();
		let place = commentAttachment({
			target: owner,
			point: response.anchor.quote ? null : response.pointIn(owner),
			passage: geometry,
			boundary: windowBoundary
		});
		if (place) windowPosture = false;
		else if (response.open && (reveal || windowPosture)) {
			windowPosture = true;
			place = commentAttachment({
				target: null,
				boundary: windowBoundary
			});
		} else {
			withholdFab();
			return false;
		}
		const seatedOwner = windowPosture ? null : owner;
		const attachment = {
			owner: seatedOwner,
			passage: Boolean(geometry?.attachment)
		};
		const changedAttachment = editingAttachment && (editingAttachment.owner !== attachment.owner || editingAttachment.passage !== attachment.passage);
		if (response.open && changedAttachment && drawn(fabInput)) {
			const frame = fabFrameAt();
			if (frame) {
				fabPlacement.adopt(frame);
				nativeAttachment = false;
			}
		}
		if (response.open && nativeAttachment && geometry && !windowPosture) return true;
		const boundary = place.region ? floatBoundary(place.region) : windowBoundary;
		if (boundary.width <= 0 || boundary.height <= 0) return false;
		fabRegion = place.region;
		const setWidth = (available, scale) => {
			const room = available;
			fabBar.style.setProperty("--lf-float-w", roomPx(Math.max(0, room)));
			if (Math.ceil(fabBar.offsetWidth) > Math.ceil(room)) fabBar.style.setProperty("--lf-float-w", roomPx(Math.max(0, boundary.width / scale)));
		};
		const setHeight = (room, scale) => {
			if (!response.open) return;
			fabBar.style.setProperty("--lf-float-h", roomPx(Math.max(0, room.height / scale)));
		};
		fabPlacement.choose({
			clear: place.clear,
			row: place.row,
			column: place.column,
			extent: place.extent,
			boundary,
			scroller: place.scroller,
			coarse: coarsePointer.matches
		});
		const epoch = fabPosition.begin();
		const stillCurrent = () => fabPosition.current(epoch) && response.anchor && response.floating;
		floatingUi().then((ui) => {
			if (!stillCurrent()) return null;
			watchFabPosition(owner ?? document.documentElement, ui.autoUpdate, ui.getOverflowAncestors);
			const { reference, placement, middleware, plane } = fabPlacement.options(ui, {
				clear: place.clear,
				row: place.row,
				lastRow: place.lastRow,
				column: place.column,
				margin: place.margin,
				boundary,
				fit({ width, room, scale }) {
					if (!stillCurrent()) return;
					setWidth(width, scale.x);
					setHeight(room, scale.y);
					const frame = fabBar.getBoundingClientRect();
					if (Math.ceil(frame.width) > Math.ceil(room.width) || Math.ceil(frame.height) > Math.ceil(room.height) || response.open && nativeRowEnd() > fabBar.clientHeight) withholdFab();
				}
			});
			return fabPosition.position(ui.computePosition, commentReference(place, reference), {
				placement,
				middleware
			}, response.open && seatedOwner ? () => "page" : plane, seatedOwner ?? document.documentElement);
		}).then((position) => {
			if (!position || !stillCurrent()) return;
			fabPlacement.landed(position);
			editingAttachment = response.open ? attachment : null;
			const stand = () => {
				keeps(fabBar, "data-lf-placement", position.placement);
				fabPosition.stand(position);
			};
			if (following) following.placed(stand);
			else stand();
			carry.placed();
			nativeAttachment = response.open && fabPosition.follows();
			positioned(true);
			stoodAgain();
			readFab();
			return true;
		}).catch((error) => {
			if (!stillCurrent()) return;
			dismiss();
			throw error;
		});
		return true;
	}
	function withholdFab() {
		nativeAttachment = false;
		fabPosition.supersede();
		if (fabWithheld) return;
		fabWithheld = true;
		const held = holdFocus(fabBar);
		closeLayer(() => fabBar.toggleAttribute("data-lf-withheld", true));
		fabWithheldFocus = held;
	}
	function stoodAgain() {
		if (!fabWithheld) return;
		fabWithheld = false;
		fabBar.removeAttribute("data-lf-withheld");
		const returning = fabWithheldFocus;
		fabWithheldFocus = null;
		returning?.();
	}
	function mount() {
		let beforeInputScroll = null;
		let inputEpoch = 0;
		fabInput.addEventListener("lf-before-edit", () => {
			beforeInputScroll = response.open && response.floating ? pageScroller.scrollTop : null;
			const epoch = ++inputEpoch;
			nextFrame(() => {
				if (inputEpoch === epoch) beforeInputScroll = null;
			});
		});
		fabInput.addEventListener("input", () => {
			if (beforeInputScroll === null) return;
			if (pageScroller.scrollTop !== beforeInputScroll) {
				pageScroller.scrollTo({
					top: beforeInputScroll,
					behavior: "instant"
				});
				placeKept(pageScroller);
			}
		});
		document.addEventListener(LAYOUT, (event) => {
			const geometry = anchorGeometry(response.anchor);
			const target = response.target ?? geometry?.contextNode;
			if (!response.anchor || !under(target, event.target)) return;
			nativeAttachment = false;
			scheduleFabPosition();
		});
		declareOffFlowSurface(fabBar, {
			floats: () => Boolean(response.anchor && response.floating),
			away: () => fabWithheld,
			bringBack: (behavior) => {
				const found = response.resolved;
				const range = response.anchor.quote && (targetRange(found) ?? selectedRange(response.anchor));
				if (range) return scrollToRange(range, behavior);
				const target = response.target;
				const line = response.pointIn(target) ?? target;
				if (line) scrollToElement(line, behavior, "nearest");
			}
		});
	}
	return {
		stands: () => response.open || Boolean(anchorGeometry(response.anchor)),
		place: placeFab,
		stop: stopFabPositioning,
		frame: fabFrameAt,
		fits: fabFits,
		withhold: withholdFab,
		stoodAgain,
		withheld: () => fabWithheld,
		release: () => {
			editingAttachment = null;
			windowPosture = false;
			fabWithheld = false;
			fabBar.removeAttribute("data-lf-withheld");
			fabWithheldFocus = null;
		},
		ready: () => fabBar.hasAttribute("data-lf-placement") && !fabWithheld,
		mount
	};
}

//#endregion
//#region runtime/annotation-overlay/composing/drawing-paint.js
function postedDrawings(threads, anchors) {
	const drawings = [];
	for (const thread of threads) {
		if (thread.resolved || !thread.root.drawing) continue;
		const place = anchors.placedAt(thread.id);
		const target = exactTarget(place);
		if (!target) continue;
		drawings.push({
			drawing: thread.root.drawing,
			target,
			className: "lf-drawing-posted",
			id: thread.id
		});
	}
	return drawings;
}

//#endregion
export { annotationsHidden, createAnchorPaint, createFloatingResponsePlacement, createMarginProjection, createVisualMarkPaint, floatingSelections, mountAnnotationControls, postedDrawings, restoreAnnotations, syncMarginContentLayout };