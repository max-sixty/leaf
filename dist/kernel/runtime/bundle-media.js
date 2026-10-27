import { closeLayer, focusDestination, handBack, keeps, keepsHidden, keepsText, openLayer, openerOf } from "./bundle-dom-move.js";
import { closeControl, keys, offerAction, offered, pagePresented, paintKeys, plainPress } from "./bundle-layer-client.js";
import { closeNativeLayer, html, inBaseLayer, nativeLayers, offlineInteractive, pageUrl, render, runtimeResource, showNativeLayer } from "./bundle-geometry.js";
import { says } from "./bundle-passages.js";

//#region runtime/motion.js
const preference = matchMedia("(prefers-reduced-motion: reduce)");
const active = /* @__PURE__ */ new Set();
const reducedMotion = () => preference.matches;
const scrollBehavior = () => preference.matches ? "instant" : "smooth";
function onMotionPreferenceChange(listener) {
	const changed = (event) => listener(event.matches);
	preference.addEventListener("change", changed);
	return () => preference.removeEventListener("change", changed);
}
preference.addEventListener("change", (event) => {
	if (event.matches) for (const played of [...active]) played.finish();
});
const motionPlays = () => !reducedMotion() && pagePresented();
const motion = (el, keyframes, ms, pseudoElement = null) => playMotion(el, keyframes, {
	duration: ms,
	pseudoElement
});
function playMotion(el, keyframes, { duration, easing = "ease", delay = 0, pseudoElement = null }) {
	if (!motionPlays()) return null;
	const played = el.animate(keyframes, {
		duration,
		delay,
		pseudoElement,
		easing,
		fill: "both"
	});
	active.add(played);
	played.finished.then(() => queueMicrotask(() => {
		active.delete(played);
		played.cancel();
	}), () => active.delete(played));
	return played;
}
const token = (property, on) => getComputedStyle(on).getPropertyValue(property).trim();
const motionTime = (property, on = document.documentElement) => {
	const value = token(property, on);
	return parseFloat(value) * (value.endsWith("ms") ? 1 : 1e3);
};
const motionEasing = (property, on = document.documentElement) => token(property, on);
const flashDuration = () => motionTime("--lf-motion-flash");
const agentArrivalDuration = () => motionTime("--lf-motion-agent-arrival");
function backgroundFlash(el, ms) {
	return motion(el, [{
		backgroundColor: "var(--hi-tint)",
		offset: 0
	}], ms);
}
const foldDuration = () => motionTime("--lf-motion-fold");
const returnDuration = () => motionTime("--lf-motion-return");
function foldBlock(el, allocation = null) {
	const adjustment = allocation ? allocation.priorSize - allocation.container.getBoundingClientRect().height : 0;
	const native = CSS.supports("block-size", "calc-size(auto, size)");
	const frames = (blockSize) => [{
		blockSize,
		display: "block",
		overflow: "clip",
		opacity: 1
	}, {
		blockSize: "0px",
		minBlockSize: "0px",
		marginBlockStart: "0px",
		marginBlockEnd: "0px",
		paddingBlockStart: "0px",
		paddingBlockEnd: "0px",
		borderBlockStartWidth: "0px",
		borderBlockEndWidth: "0px",
		display: "block",
		overflow: "clip",
		opacity: 0
	}];
	const played = motion(el, frames(native ? `calc-size(auto, size + ${adjustment}px)` : "auto"), foldDuration());
	if (!played || native) return played;
	if (getComputedStyle(el).display === "none") {
		el.style.display = "block";
		const release = () => el.style.removeProperty("display");
		played.finished.then(release, release);
	}
	const size = parseFloat(getComputedStyle(el).blockSize) + adjustment;
	played.effect.setKeyframes(frames(`${size}px`));
	return played;
}

//#endregion
//#region runtime/media.js
const CANONICAL_MEDIA_ROOT = "/media/";
const ATTACHED_IMAGE = String.raw`!\[Attached image\]\((${CANONICAL_MEDIA_ROOT}[^\s)]+)\)`;
const ATTACHED_MEDIA = new RegExp(ATTACHED_IMAGE, "g");
const MEDIA_SUFFIX = new RegExp(`(?:^|\\n\\n)${ATTACHED_IMAGE}(?:\\n\\n${ATTACHED_IMAGE})*(?![\\s\\S])`);
const isCanonicalMediaUrl = (href) => href.startsWith(CANONICAL_MEDIA_ROOT);
const scopedMediaUrl = (href) => offlineInteractive ? runtimeResource(href) : new URL(pageUrl(href.slice(1))).pathname;
function readAttachedMedia(value) {
	const suffix = MEDIA_SUFFIX.exec(value);
	if (!suffix) return {
		text: value,
		paths: []
	};
	return {
		text: value.slice(0, suffix.index),
		paths: Array.from(suffix[0].matchAll(ATTACHED_MEDIA), (image) => image[1])
	};
}
function writeAttachedMedia(text, paths) {
	if (!paths.length) return text;
	const images = paths.map((path) => `![Attached image](${path})`).join("\n\n");
	if (!text) return images;
	return text + "\n\n" + images;
}
const viewerClose = closeControl({
	name: "Close image preview",
	title: "Close image preview (Esc)"
});
const viewerZoom = offerAction("word", "lf-media-viewer-zoom", "100%");
const stage = document.createElement("div");
stage.className = "lf-media-viewer-stage";
const caption = document.createElement("p");
caption.className = "lf-media-viewer-caption scroll";
let inspector = null;
let loading = null;
let opening = 0;
let canvasUrl = null;
function imageTools() {
	if (!loading) loading = import("/vendor/photoswipe.esm.js").then(({ default: PhotoSwipe, styles }) => {
		const style = document.createElement("style");
		style.textContent = inBaseLayer(styles);
		mediaViewer.append(style);
		return PhotoSwipe;
	});
	return loading;
}
function presentViewer(model) {
	render(html`
      <div class="lf-media-viewer-head">
        <strong id="lf-media-viewer-title">Image preview</strong>
        <div class="lf-media-viewer-actions">
          ${model ? html`<a
                  ${offered("lf-media-viewer-original", true)}
                  href=${model.url}
                  target="_blank"
                  rel="noopener"
                  >Original</a
                >` : null}
          ${viewerZoom}${viewerClose}
        </div>
      </div>
      ${stage}${caption}
    `, mediaViewer);
}
const mediaViewer = document.createElement("dialog");
mediaViewer.id = "lf-media-viewer";
mediaViewer.className = "lf-ui lf-media-viewer";
mediaViewer.setAttribute("closedby", "any");
mediaViewer.setAttribute("aria-modal", "true");
mediaViewer.setAttribute("aria-labelledby", "lf-media-viewer-title");
presentViewer(null);
keys(mediaViewer, "Image preview", [
	{
		id: "image.close",
		keys: ["Escape"],
		title: "close image",
		control: viewerClose,
		run: () => closeLayer(() => closeNativeLayer(mediaViewer))
	},
	{
		id: "image.zoom",
		keys: ["z"],
		title: "zoom / fit",
		control: viewerZoom,
		when: () => {
			const slide = inspector?.currSlide;
			return Boolean(slide && (slide.zoomLevels.initial < 1 || Math.abs(slide.currZoomLevel - slide.zoomLevels.initial) > .01));
		},
		run: () => inspector.toggleZoom()
	},
	{
		id: "image.pan",
		keys: [
			"ArrowLeft",
			"ArrowRight",
			"ArrowUp",
			"ArrowDown"
		],
		title: "pan image",
		repeat: true,
		when: () => Boolean(inspector)
	}
], { when: () => mediaViewer.open });
const cellHeads = (from) => {
	const cell = from.closest("td");
	if (!cell) return "";
	const table = cell.closest("table");
	const box = cell.getBoundingClientRect();
	const x = box.left + box.width / 2;
	const y = box.top + box.height / 2;
	const rtl = getComputedStyle(table).direction === "rtl";
	const columns = [];
	const rows = [];
	for (const head of table.querySelectorAll("th")) {
		if (head.closest("table") !== table) continue;
		const at = head.getBoundingClientRect();
		if (head.matches("[scope=\"row\"]")) {
			if ((rtl ? at.left >= box.right - 1 : at.right <= box.left + 1) && at.top <= y && y < at.bottom) rows.push(head);
		} else if (at.bottom <= box.top + 1 && at.left <= x && x < at.right) columns.push(head);
	}
	return [...new Set([...columns, ...rows].map(says).filter(Boolean))].join(" · ");
};
const open = async (source, alt, from) => {
	const attempt = ++opening;
	inspector?.destroy();
	inspector = null;
	if (canvasUrl) URL.revokeObjectURL(canvasUrl);
	canvasUrl = null;
	const canvas = source instanceof window.HTMLCanvasElement;
	openLayer(mediaViewer, from);
	presentViewer(canvas ? null : {
		url: source,
		alt
	});
	render(canvas ? html`<p>Preparing image…</p>` : null, stage);
	const figureCaption = from.closest("figure")?.querySelector("figcaption");
	const description = from.dataset.lfMediaCaption || figureCaption && says(figureCaption) || cellHeads(from);
	keepsText(caption, description);
	keepsHidden(caption, !description);
	keepsText(viewerZoom, "100%");
	if (!mediaViewer.open) showNativeLayer(mediaViewer, { source: from });
	focusDestination(viewerClose, "move");
	let url = source;
	if (canvas) {
		let blob;
		try {
			blob = await new Promise((resolve) => source.toBlob(resolve));
			if (!blob) throw new Error("the drawing could not be encoded");
		} catch (error) {
			if (attempt !== opening || !mediaViewer.open) return;
			render(html`<p>Image preview unavailable: ${error.message}.</p>`, stage);
			return;
		}
		if (attempt !== opening || !mediaViewer.open) return;
		canvasUrl = URL.createObjectURL(blob);
		url = canvasUrl;
		presentViewer({
			url,
			alt
		});
	}
	render(html`<span class="lf-media-viewer-probe"><img src=${url} alt="" /></span>`, stage);
	const probe = stage.querySelector(".lf-media-viewer-probe > img");
	Promise.all([imageTools(), probe.decode()]).then(([PhotoSwipe]) => {
		if (attempt !== opening || !mediaViewer.open) return;
		const { naturalWidth: width, naturalHeight: height } = probe;
		const cover = Math.max(window.screen.width, window.screen.height) / Math.min(width, height);
		const size = probe.getBoundingClientRect().width > 1 ? {
			width,
			height
		} : {
			width: width * cover,
			height: height * cover
		};
		render(null, stage);
		const current = new PhotoSwipe({
			dataSource: [{
				src: url,
				alt,
				...size
			}],
			appendToEl: mediaViewer,
			paddingFn: (viewport) => {
				const box = stage.getBoundingClientRect();
				const inset = getComputedStyle(stage);
				return {
					top: box.top + parseFloat(inset.paddingTop),
					right: viewport.x - box.right + parseFloat(inset.paddingRight),
					bottom: viewport.y - box.bottom + parseFloat(inset.paddingBottom),
					left: box.left + parseFloat(inset.paddingLeft)
				};
			},
			secondaryZoomLevel: 1,
			close: false,
			zoom: false,
			counter: false,
			arrowPrev: false,
			arrowNext: false,
			trapFocus: false,
			returnFocus: false,
			escKey: false,
			showHideAnimationType: "none",
			zoomAnimationDuration: reducedMotion() ? 0 : foldDuration(),
			clickToCloseNonZoomable: false,
			bgClickAction: "close",
			tapAction: "zoom"
		});
		inspector = current;
		current.on("keydown", (event) => {
			const key = event.originalEvent;
			if (key.defaultPrevented || ![
				"ArrowLeft",
				"ArrowRight",
				"ArrowUp",
				"ArrowDown"
			].includes(key.key) || nativeLayers().at(-1)?.root !== mediaViewer || !mediaViewer.contains(key.target)) event.preventDefault();
		});
		current.on("close", () => {
			if (mediaViewer.open) closeLayer(() => closeNativeLayer(mediaViewer));
		});
		current.on("zoomPanUpdate", () => {
			const slide = current.currSlide;
			const enlarged = slide.currZoomLevel > slide.zoomLevels.initial + .01;
			keepsText(viewerZoom, enlarged ? "Fit" : "100%");
			keeps(viewerZoom, "aria-label", enlarged ? "Fit image" : "Zoom to actual size");
			paintKeys();
		});
		current.init();
		current.element.removeAttribute("role");
		current.element.removeAttribute("aria-modal");
		paintKeys();
	}, (error) => {
		if (attempt !== opening || !mediaViewer.open) return;
		keepsText(caption, `Image preview unavailable: ${error.message}. Open Original to see the file.`);
		keepsHidden(caption, false);
	});
};
mediaViewer.addEventListener("close", () => {
	if (mediaViewer.open) return;
	++opening;
	inspector?.destroy();
	inspector = null;
	if (canvasUrl) URL.revokeObjectURL(canvasUrl);
	canvasUrl = null;
	const origin = openerOf(mediaViewer);
	openLayer(mediaViewer, null);
	closeLayer(() => {
		render(null, stage);
		presentViewer(null);
	}, origin && (() => handBack(origin)));
});
document.addEventListener("click", (event) => {
	if (event.defaultPrevented || !plainPress(event)) return;
	const trigger = event.composedPath().find((node) => node instanceof Element && node.matches(".lf-media-open[data-lf-media-url], .lf-media-open[data-lf-media-canvas]"));
	const link = event.composedPath().find((node) => node instanceof HTMLAnchorElement);
	const image = link?.querySelector("img");
	const imageLink = image && !link.hasAttribute("download") && (link.href === image.src || link.href === image.currentSrc);
	if (trigger || imageLink) {
		event.preventDefault();
		open(trigger?.hasAttribute("data-lf-media-canvas") && trigger.querySelector("canvas") || trigger?.dataset.lfMediaUrl || link.href, trigger?.dataset.lfMediaAlt || (trigger?.querySelector("img") || image)?.alt || "Image", trigger || link);
	}
});

//#endregion
export { agentArrivalDuration, backgroundFlash, flashDuration, foldBlock, foldDuration, isCanonicalMediaUrl, mediaViewer, motion, motionEasing, motionPlays, motionTime, onMotionPreferenceChange, playMotion, readAttachedMedia, reducedMotion, returnDuration, scopedMediaUrl, scrollBehavior, writeAttachedMedia };