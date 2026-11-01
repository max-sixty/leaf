import { __exportAll } from "./bundle-rolldown-runtime.js";
import { canvas2D, describeFailure } from "./bundle-portable.js";

//#region runtime/composing/page-image.js
var page_image_exports = /* @__PURE__ */ __exportAll({
	pageImage: () => pageImage,
	pageRenderer: () => pageRenderer
});
const asDataUrl = async (blob) => `data:${blob.type};base64,${(await blob.bytes()).toBase64()}`;
const pageRenderer = async () => {
	const [{ snapdom }, { isSampleFrame, sampleFrameImage }] = await Promise.all([import("/vendor/snapdom.esm.js"), import("./bundle-sample.js")]);
	return {
		snapdom,
		isSampleFrame,
		sampleFrameImage
	};
};
const meets = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
const holds = (a, b) => a.left <= b.left && a.top <= b.top && a.right >= b.right && a.bottom >= b.bottom;
const paintsOverChildren = (parent, style) => style.backgroundImage !== "none" || style.overflowX !== "visible" || style.overflowY !== "visible" || /paint|content|strict/.test(style.contain) || ["::before", "::after"].some((pseudo) => {
	const own = getComputedStyle(parent, pseudo);
	return !["none", "normal"].includes(own.content) && own.position !== "static";
});
const drawsThroughEffect = (style) => style.opacity !== "1" || style.mixBlendMode !== "normal" || [
	"transform",
	"translate",
	"rotate",
	"scale",
	"filter",
	"backdrop-filter",
	"clip-path",
	"mask-image"
].some((property) => style.getPropertyValue(property) !== "none");
function* laidOut(parent, skip) {
	for (const child of parent.children) {
		if (skip && child.matches(skip)) continue;
		if (child.getClientRects().length) yield child;
		else if (getComputedStyle(child).display === "contents") yield* laidOut(child, skip);
	}
}
function captureRoot(region, skip) {
	let root = document.body;
	const ground = [getComputedStyle(document.documentElement).backgroundColor];
	while (!root.shadowRoot) {
		const style = getComputedStyle(root);
		if (paintsOverChildren(root, style)) break;
		let holder = null;
		for (const child of laidOut(root, skip)) {
			const box = child.getBoundingClientRect();
			if (!meets(box, region)) continue;
			if (holder || !holds(box, region)) {
				holder = null;
				break;
			}
			holder = child;
		}
		if (!(holder instanceof HTMLElement) || !holder.hasChildNodes() || drawsThroughEffect(getComputedStyle(holder))) break;
		ground.push(style.backgroundColor);
		root = holder;
	}
	const canvas = new OffscreenCanvas(1, 1);
	const ctx = canvas2D(canvas);
	for (const color of ground) {
		ctx.fillStyle = color;
		ctx.fillRect(0, 0, 1, 1);
	}
	const channels = Array.from(ctx.getImageData(0, 0, 1, 1).data, (channel, index) => index === 3 ? channel / 255 : channel);
	return {
		root,
		ground: `rgba(${channels.join(", ")})`
	};
}
async function pageImage(clip, { exclude = [] } = {}) {
	const { snapdom, isSampleFrame, sampleFrameImage } = await pageRenderer();
	const warnings = /* @__PURE__ */ new Set();
	async function sampleContent(frame) {
		const box = document.createElement("div");
		if (!frame.checkVisibility({ visibilityProperty: true })) return box;
		const rect = frame.getBoundingClientRect();
		const scaleX = rect.width / frame.offsetWidth || 1;
		const scaleY = rect.height / frame.offsetHeight || 1;
		const left = rect.left + frame.clientLeft * scaleX;
		const top = rect.top + frame.clientTop * scaleY;
		const right = Math.min(left + frame.clientWidth * scaleX, clip.x - scrollX + clip.width);
		const bottom = Math.min(top + frame.clientHeight * scaleY, clip.y - scrollY + clip.height);
		const start = {
			x: (Math.max(left, clip.x - scrollX) - left) / scaleX,
			y: (Math.max(top, clip.y - scrollY) - top) / scaleY
		};
		const crop = {
			...start,
			width: (right - left) / scaleX - start.x,
			height: (bottom - top) / scaleY - start.y
		};
		if (crop.width <= 0 || crop.height <= 0) return box;
		try {
			const child = await sampleFrameImage(frame, crop);
			for (const warning of child.warnings) warnings.add(warning);
			const blob = child.blob;
			const img = document.createElement("img");
			img.decoding = "sync";
			img.src = await asDataUrl(blob);
			img.style.cssText = `display:block;position:relative;left:${crop.x}px;top:${crop.y}px;width:${crop.width}px;height:${crop.height}px`;
			box.append(img);
		} catch (error) {
			warnings.add(`A live sample in this area could not be drawn: ${describeFailure(error)}`);
		}
		return box;
	}
	const { root, ground } = captureRoot({
		left: clip.x - scrollX,
		top: clip.y - scrollY,
		right: clip.x - scrollX + clip.width,
		bottom: clip.y - scrollY + clip.height
	}, exclude.join(", "));
	const image = await snapdom(root, {
		clip,
		backgroundColor: ground,
		dpr: window.devicePixelRatio,
		exclude,
		excludeMode: "hide",
		invalidate: true,
		reconcile: false,
		plugins: [{
			name: "leaf-sample-frames",
			resolveNode: (node) => isSampleFrame(node) ? sampleContent(node) : void 0
		}, {
			name: "leaf-root-in-place",
			afterClone: ({ clone }) => {
				if (clone) clone.style.justifySelf = "normal";
			}
		}]
	});
	const blob = await image.toBlob({ format: "png" });
	if (image.warnings.some(({ code }) => code === "image-fallback")) warnings.add("An image near this area could not be drawn and may be missing.");
	return {
		blob,
		warnings: [...warnings]
	};
}

//#endregion
export { pageImage, pageRenderer, page_image_exports };