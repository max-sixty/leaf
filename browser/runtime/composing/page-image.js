/* An image of part of this document, as its reader sees it.
 *
 * SnapDOM reconstructs the live DOM inside a document-coordinate crop; Leaf owns no
 * renderer. A live sample's frame holds an opaque-origin document this realm cannot
 * read, so SnapDOM alone draws it as a placeholder. Where the reconstruction reaches a
 * sample frame, the part of the crop inside the frame crosses its host's port, the
 * child draws that part of its viewport with this same function, and the image stands
 * in for the frame's content inside the frame's own box. Nested samples compose the
 * same way. A frame SnapDOM leaves out, or the part of a child outside the crop, is
 * never asked to draw. Other cross-origin frames keep SnapDOM's placeholder.
 *
 * A part that could not be drawn does not refuse the capture, since SnapDOM reads
 * resources a margin beyond the crop and cannot say whether a missing image fell
 * inside it. The image comes back with a warning for each such part instead: an image
 * SnapDOM could not load, or a sample that could not draw itself, whose frame keeps
 * its box and stays empty. A child's warnings join its parent's.
 *
 * What a caller excludes is hidden, not removed, so the rest of the page keeps the
 * geometry it is painted with. SnapDOM's `reconcile` stays off: it measures a copy of
 * the reconstruction inside this document, where every widget in the copy connects and
 * runs its setup, reporting page errors and registering regions that never present.
 * Without it, text in inline and table-cell boxes may wrap differently in the image.
 *
 * SnapDOM visits every sibling of every ancestor of the element it draws, measuring
 * each one outside the crop and copying its computed style onto a placeholder, so a
 * capture from the body costs time in proportion to the page: a third of a second for
 * a crop inside one of 800 cards. `captureRoot` descends from the body instead, by
 * rectangles, to the deepest element that alone paints the crop: its border box holds
 * the crop and no sibling's box meets it. Each element it passes paints only a solid
 * background beneath the next, with no background image, clipping or positioned
 * pseudo-element, and none of them draws its subtree through an effect such as
 * opacity, a filter or a transform. The image is filled with those backgrounds,
 * composited. What paints into the crop from outside the boxes it reads is lost: a
 * positioned descendant of a sibling, say, or an ancestor's inset shadow. It stops at
 * a shadow host and never descends into SVG or an element with no content of its own,
 * such as an image or a frame.
 */
const asDataUrl = async (blob) =>
  `data:${blob.type};base64,${(await blob.bytes()).toBase64()}`;

// SnapDOM and the sample host, which draws a mounted sample's frame. A caller that reads
// the crop's geometry at the moment of capture awaits the renderer first, so no download
// separates that reading from the reconstruction. The sample host loads here and with
// the first sample a widget mounts, so a page that shows none never loads it on the way
// to its first paint.
export const pageRenderer = async () => {
  const [{ snapdom }, { isSampleFrame, sampleFrameImage }] = await Promise.all([
    import("../../vendor/snapdom.esm.js"),
    import("../sample.js"),
  ]);
  return { snapdom, isSampleFrame, sampleFrameImage };
};

const meets = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
const holds = (a, b) =>
  a.left <= b.left && a.top <= b.top && a.right >= b.right && a.bottom >= b.bottom;

// Paint of a parent's own that lies over or around its children's.
const paintsOverChildren = (parent, style) =>
  style.backgroundImage !== "none" ||
  style.overflowX !== "visible" ||
  style.overflowY !== "visible" ||
  /paint|content|strict/.test(style.contain) ||
  ["::before", "::after"].some((pseudo) => {
    const own = getComputedStyle(parent, pseudo);
    return !["none", "normal"].includes(own.content) && own.position !== "static";
  });

// An element that draws its subtree through an effect, which only its own capture keeps.
const drawsThroughEffect = (style) =>
  style.opacity !== "1" ||
  style.mixBlendMode !== "normal" ||
  [
    "transform",
    "translate",
    "rotate",
    "scale",
    "filter",
    "backdropFilter",
    "clipPath",
    "maskImage",
  ].some((property) => style[property] !== "none");

// The boxes a parent lays out, through any child that generates none of its own.
function* laidOut(parent, skip) {
  for (const child of parent.children) {
    if (skip && child.matches(skip)) continue;
    if (child.getClientRects().length) yield child;
    else if (getComputedStyle(child).display === "contents")
      yield* laidOut(child, skip);
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
    if (
      !(holder instanceof HTMLElement) ||
      !holder.hasChildNodes() ||
      drawsThroughEffect(getComputedStyle(holder))
    )
      break;
    ground.push(style.backgroundColor);
    root = holder;
  }
  const canvas = new OffscreenCanvas(1, 1);
  const ctx = canvas.getContext("2d");
  for (const color of ground) {
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, 1, 1);
  }
  const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
  return { root, ground: `rgba(${r}, ${g}, ${b}, ${a / 255})` };
}

export async function pageImage(clip, { exclude = [] } = {}) {
  const { snapdom, isSampleFrame, sampleFrameImage } = await pageRenderer();
  const warnings = new Set();
  // The crop meets the frame's content box in this viewport's coordinates; the
  // child and the substitute's own box read it in the frame's, unscaled.
  async function sampleContent(frame) {
    // SnapDOM applies the frame's box to the returned node, border included.
    const box = document.createElement("div");
    if (!frame.checkVisibility({ visibilityProperty: true })) return box;
    const rect = frame.getBoundingClientRect();
    const scaleX = rect.width / frame.offsetWidth || 1;
    const scaleY = rect.height / frame.offsetHeight || 1;
    const left = rect.left + frame.clientLeft * scaleX;
    const top = rect.top + frame.clientTop * scaleY;
    const right = Math.min(
      left + frame.clientWidth * scaleX,
      clip.x - scrollX + clip.width,
    );
    const bottom = Math.min(
      top + frame.clientHeight * scaleY,
      clip.y - scrollY + clip.height,
    );
    const crop = {
      x: (Math.max(left, clip.x - scrollX) - left) / scaleX,
      y: (Math.max(top, clip.y - scrollY) - top) / scaleY,
    };
    crop.width = (right - left) / scaleX - crop.x;
    crop.height = (bottom - top) / scaleY - crop.y;
    if (crop.width <= 0 || crop.height <= 0) return box;
    try {
      const child = await sampleFrameImage(frame, crop);
      for (const warning of child.warnings) warnings.add(warning);
      const blob = child.blob;
      // The decoding attribute reaches the reconstruction's markup: without it WebKit
      // can rasterize that markup before decoding the image, and draws it blank.
      const img = document.createElement("img");
      img.decoding = "sync";
      img.src = await asDataUrl(blob);
      img.style.cssText = `display:block;position:relative;left:${crop.x}px;top:${crop.y}px;width:${crop.width}px;height:${crop.height}px`;
      box.append(img);
    } catch (error) {
      warnings.add(`A live sample in this area could not be drawn: ${error.message}`);
    }
    return box;
  }
  const { root, ground } = captureRoot(
    {
      left: clip.x - scrollX,
      top: clip.y - scrollY,
      right: clip.x - scrollX + clip.width,
      bottom: clip.y - scrollY + clip.height,
    },
    exclude.join(", "),
  );
  const image = await snapdom(root, {
    clip,
    backgroundColor: ground,
    dpr: window.devicePixelRatio,
    exclude,
    excludeMode: "hide",
    invalidate: true,
    reconcile: false,
    plugins: [
      {
        name: "leaf-sample-frames",
        resolveNode: (node) => (isSampleFrame(node) ? sampleContent(node) : undefined),
      },
      {
        // SnapDOM sets the root's margins and offsets aside, since the crop already
        // places it, but keeps its justify-self. Chrome aligns a block box by it, so a
        // root its grid centred, as the column Layout centres `main`, drew off its crop.
        name: "leaf-root-in-place",
        afterClone: ({ clone }) => {
          clone.style.justifySelf = "normal";
        },
      },
    ],
  });
  const blob = await image.toBlob({ format: "png" });
  if (image.warnings.some(({ code }) => code === "image-fallback"))
    warnings.add("An image near this area could not be drawn and may be missing.");
  return { blob, warnings: [...warnings] };
}
