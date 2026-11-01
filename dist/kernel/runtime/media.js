import { describeFailure, foldDuration, inBaseLayer, keeps, keepsHidden, keepsText, offerAction, offered, reducedMotion } from "./bundle-portable.js";
import { closeLayer, closeNativeLayer, focusDestination, handBack, html, nativeLayers, offlineInteractive, openLayer, openerOf, pageUrl, plainPress, render, runtimeResource, showNativeLayer } from "./bundle-layer-stack.js";
import { closeControl, keys, paintKeys } from "./bundle-layer-client.js";
import { says } from "./bundle-passages.js";

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
		paths: [...suffix[0].matchAll(ATTACHED_MEDIA)].flatMap((image) => image.slice(1))
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
        <strong id="lf-media-viewer-title" class="lf-dialog-title"
          >Image preview</strong
        >
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
		run: () => inspector?.toggleZoom()
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
	if (!table) return "";
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
	return [...new Set([...columns, ...rows].map((head) => says(head)).filter(Boolean))].join(" · ");
};
const open = async (source, alt, from) => {
	const attempt = ++opening;
	inspector?.destroy();
	inspector = null;
	if (canvasUrl) URL.revokeObjectURL(canvasUrl);
	canvasUrl = null;
	const canvas = source instanceof HTMLCanvasElement;
	openLayer(mediaViewer, from);
	presentViewer(canvas ? null : {
		url: source,
		alt
	});
	render(canvas ? html`<p>Preparing image…</p>` : null, stage);
	const figureCaption = from.closest("figure")?.querySelector("figcaption");
	const description = from.getAttribute("data-lf-media-caption") || figureCaption && says(figureCaption) || cellHeads(from);
	keepsText(caption, description);
	keepsHidden(caption, !description);
	keepsText(viewerZoom, "100%");
	if (!mediaViewer.open) showNativeLayer(mediaViewer, { source: from });
	focusDestination(viewerClose, "move");
	let url;
	if (canvas) {
		let blob;
		try {
			blob = await new Promise((resolve) => source.toBlob(resolve));
			if (!blob) throw new Error("the drawing could not be encoded");
		} catch (error) {
			if (attempt !== opening || !mediaViewer.open) return;
			render(html`<p>Image preview unavailable: ${describeFailure(error)}.</p>`, stage);
			return;
		}
		if (attempt !== opening || !mediaViewer.open) return;
		canvasUrl = URL.createObjectURL(blob);
		url = canvasUrl;
		presentViewer({
			url,
			alt
		});
	} else url = source;
	render(html`<span class="lf-media-viewer-probe"><img src=${url} alt="" /></span>`, stage);
	const probe = stage.querySelector("img");
	if (!probe) throw new Error("Image inspection needs its rendered decode probe");
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
			].includes(key.key) || nativeLayers().at(-1)?.root !== mediaViewer || !(key.target instanceof Node && mediaViewer.contains(key.target))) event.preventDefault();
		});
		current.on("close", () => {
			if (mediaViewer.open) closeLayer(() => closeNativeLayer(mediaViewer));
		});
		current.on("zoomPanUpdate", ({ slide }) => {
			const enlarged = slide.currZoomLevel > slide.zoomLevels.initial + .01;
			keepsText(viewerZoom, enlarged ? "Fit" : "100%");
			keeps(viewerZoom, "aria-label", enlarged ? "Fit image" : "Zoom to actual size");
			paintKeys();
		});
		current.init();
		const root = current.element;
		if (!root) throw new Error("PhotoSwipe did not create its image inspection surface");
		root.removeAttribute("role");
		root.removeAttribute("aria-modal");
		paintKeys();
	}, (error) => {
		if (attempt !== opening || !mediaViewer.open) return;
		keepsText(caption, `Image preview unavailable: ${describeFailure(error)}. Open Original to see the file.`);
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
	const path = event.composedPath();
	const trigger = path.find((node) => node instanceof Element && node.matches(".lf-media-open[data-lf-media-url], .lf-media-open[data-lf-media-canvas]"));
	const link = path.find((node) => node instanceof HTMLAnchorElement);
	const image = link?.querySelector("img");
	const imageLink = link && image && !link.hasAttribute("download") && (link.href === image.src || link.href === image.currentSrc);
	const origin = trigger ?? (link && imageLink ? link : null);
	if (!origin) return;
	const source = (trigger?.hasAttribute("data-lf-media-canvas") ? trigger.querySelector("canvas") : null) || trigger?.getAttribute("data-lf-media-url") || (link && imageLink ? link.href : null);
	if (!source) throw new Error("Image inspection needs a canvas or image URL");
	event.preventDefault();
	open(source, trigger?.getAttribute("data-lf-media-alt") || (trigger?.querySelector("img") || image)?.alt || "Image", origin);
});

//#endregion
export { isCanonicalMediaUrl, mediaViewer, readAttachedMedia, scopedMediaUrl, writeAttachedMedia };