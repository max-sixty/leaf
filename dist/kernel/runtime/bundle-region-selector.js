import { keeps, keepsHidden, keepsText, nextRender } from "./bundle-portable.js";
import { closeLayer, focusDestination, focused, handBack, runtime } from "./bundle-layer-stack.js";
import { el, notice, paintKeys, raiseError } from "./bundle-layer-client.js";
import { clamp, layoutWindow } from "./bundle-geometry.js";
import { pageImage } from "./bundle-page-image.js";

//#region runtime/composing/region-selector.js
const MIN_SIZE = 8;
const STEP = 10;
function createRegionSelector({ parent, visibleTargets, openComposerWithMedia, returnTo = null }) {
	const { promise: done, resolve: settled } = Promise.withResolvers();
	const currentLocation = focused();
	const origin = currentLocation === document.body ? returnTo : currentLocation;
	const overlay = el("div", "lf-ui lf-region-capture");
	overlay.setAttribute("role", "region");
	overlay.setAttribute("aria-label", "Capture area");
	overlay.tabIndex = -1;
	const selection = el("div", "lf-region-selection");
	selection.setAttribute("aria-hidden", "true");
	const status = el("p", "lf-live lf-region-status");
	status.setAttribute("role", "status");
	overlay.append(selection, status);
	let box = null;
	let drag = null;
	let busy = false;
	let attempt = 0;
	let ended = false;
	function paint() {
		keepsHidden(selection, !box);
		if (!box) {
			keepsText(status, "");
			paintKeys();
			return;
		}
		selection.style.left = `${box.x}px`;
		selection.style.top = `${box.y}px`;
		selection.style.width = `${box.width}px`;
		selection.style.height = `${box.height}px`;
		keepsText(status, `${box.width} × ${box.height} pixels`);
		paintKeys();
	}
	function fit() {
		if (ended) return;
		if (!box) return paint();
		const { right, bottom } = layoutWindow();
		box.width = clamp(box.width, MIN_SIZE, right);
		box.height = clamp(box.height, MIN_SIZE, bottom);
		box.x = clamp(box.x, 0, right - box.width);
		box.y = clamp(box.y, 0, bottom - box.height);
		paint();
	}
	function finish(land = null) {
		if (ended) return;
		ended = true;
		++attempt;
		window.removeEventListener("resize", resize);
		closeLayer(() => overlay.remove(), land ?? (() => handBack(origin)));
		paintKeys();
		settled();
	}
	function resize() {
		++attempt;
		busy = false;
		drag = null;
		keeps(overlay, "aria-busy", null);
		fit();
	}
	function move(binding) {
		if (!box) {
			const { right: width, bottom: height } = layoutWindow();
			box = {
				x: Math.round(width * .2),
				y: Math.round(height * .2),
				width: Math.round(width * .6),
				height: Math.round(height * .5)
			};
			return fit();
		}
		const resizing = binding.startsWith("Shift+");
		const key = binding.split("+").at(-1);
		const dx = key === "ArrowLeft" ? -10 : key === "ArrowRight" ? STEP : 0;
		const dy = key === "ArrowUp" ? -10 : key === "ArrowDown" ? STEP : 0;
		if (resizing) {
			const { right, bottom } = layoutWindow();
			box.width = clamp(box.width + dx, MIN_SIZE, right - box.x);
			box.height = clamp(box.height + dy, MIN_SIZE, bottom - box.y);
		} else {
			box.x += dx;
			box.y += dy;
		}
		fit();
	}
	function anchorForBox() {
		const x = box.x + box.width / 2;
		const y = box.y + box.height / 2;
		const winner = visibleTargets().filter(({ rect }) => rect && rect.width && rect.height).map((target) => ({
			...target,
			distance: Math.hypot(Math.max(target.rect.left - x, 0, x - target.rect.right), Math.max(target.rect.top - y, 0, y - target.rect.bottom))
		})).sort((a, b) => a.distance - b.distance || a.rect.width * a.rect.height - b.rect.width * b.rect.height)[0];
		return (winner?.capture ? winner.capture() : winner)?.anchor ?? null;
	}
	async function capture() {
		if (ended || busy || drag) return;
		const ticket = ++attempt;
		const revision = runtime.currentRevision;
		const anchor = anchorForBox();
		const clip = {
			...box,
			x: box.x + scrollX,
			y: box.y + scrollY
		};
		busy = true;
		keeps(overlay, "aria-busy", "true");
		keepsText(status, "Capturing…");
		paintKeys();
		try {
			const { blob, warnings } = await pageImage(clip, { exclude: [
				".lf-region-capture",
				".lf-floating-panel",
				".lf-fp-ground"
			] });
			if (ended || ticket !== attempt) return;
			if (revision !== runtime.currentRevision) throw new Error("The page changed. Select the area again.");
			let adding;
			finish(() => {
				adding = openComposerWithMedia(anchor, [blob]);
			});
			await adding;
			if (warnings.length) notice(`Captured — ${warnings.join(" ")}`);
		} catch (error) {
			if (ended || ticket !== attempt) return;
			busy = false;
			keeps(overlay, "aria-busy", null);
			const message = `Could not capture — ${error.message}`;
			keepsText(status, message);
			raiseError(message);
			paintKeys();
		}
	}
	function dragTo(event) {
		box = {
			x: Math.round(Math.min(drag.x, event.clientX)),
			y: Math.round(Math.min(drag.y, event.clientY)),
			width: Math.max(MIN_SIZE, Math.round(Math.abs(event.clientX - drag.x))),
			height: Math.max(MIN_SIZE, Math.round(Math.abs(event.clientY - drag.y)))
		};
		fit();
	}
	function pointer(event) {
		if (ended) return false;
		if (event.type === "pointerdown") {
			if (busy || drag || !event.isPrimary || event.button !== 0) return false;
			drag = {
				id: event.pointerId,
				x: event.clientX,
				y: event.clientY,
				from: box
			};
			box = {
				x: drag.x,
				y: drag.y,
				width: MIN_SIZE,
				height: MIN_SIZE
			};
			fit();
			return true;
		}
		if (!drag || drag.id !== event.pointerId) return false;
		if (event.type === "pointermove") dragTo(event);
		else if (event.type === "pointerup" || event.type === "pointercancel") {
			const drew = event.type === "pointerup" && (Math.abs(event.clientX - drag.x) >= MIN_SIZE || Math.abs(event.clientY - drag.y) >= MIN_SIZE);
			if (drew) dragTo(event);
			else box = drag.from;
			drag = null;
			if (drew) capture();
			else fit();
		} else return false;
		return true;
	}
	const cancel = ({ restore = true } = {}) => finish(restore ? null : () => {});
	const rows = [
		{
			id: "capture.region.attach",
			keys: ["Enter"],
			title: "Attach capture",
			touch: false,
			when: () => !ended && !busy && !drag && Boolean(box),
			run: capture
		},
		{
			id: "capture.region.move",
			touch: false,
			keys: [
				"ArrowLeft",
				"ArrowRight",
				"ArrowUp",
				"ArrowDown"
			],
			title: "move area",
			repeat: true,
			when: () => !ended && !busy && !drag,
			run: move
		},
		{
			id: "capture.region.resize",
			touch: false,
			keys: [
				"Shift+ArrowLeft",
				"Shift+ArrowRight",
				"Shift+ArrowUp",
				"Shift+ArrowDown"
			],
			title: "resize area",
			repeat: true,
			when: () => !ended && !busy && !drag,
			run: move
		},
		{
			id: "capture.region.cancel",
			keys: ["Escape"],
			title: "Cancel capture",
			exit: true,
			when: () => !ended,
			run: cancel
		}
	];
	parent.append(overlay);
	focusDestination(overlay, "move");
	window.addEventListener("resize", resize);
	nextRender(fit);
	return {
		rows,
		pointer,
		cancel,
		done
	};
}

//#endregion
export { createRegionSelector };