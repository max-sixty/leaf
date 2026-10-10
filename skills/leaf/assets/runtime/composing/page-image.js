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
 * Known missing images refuse capture instead of returning a placeholder, and a sample
 * the crop reaches that cannot draw itself refuses it too.
 */
import { isSampleFrame, sampleFrameImage } from "../sample.js";

const asDataUrl = (blob) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });

export async function pageImage(clip, { exclude = [] } = {}) {
  const { snapdom } = await import("../../vendor/snapdom.esm.js");
  const failures = [];
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
      const blob = await sampleFrameImage(frame, crop);
      // The decoding attribute reaches the reconstruction's markup: without it WebKit
      // can rasterize that markup before decoding the image, and draws it blank.
      const img = document.createElement("img");
      img.decoding = "sync";
      img.src = await asDataUrl(blob);
      img.style.cssText = `display:block;position:relative;left:${crop.x}px;top:${crop.y}px;width:${crop.width}px;height:${crop.height}px`;
      box.append(img);
    } catch (error) {
      failures.push(error);
    }
    return box;
  }
  const image = await snapdom(document.body, {
    clip,
    dpr: window.devicePixelRatio,
    exclude,
    excludeMode: "remove",
    invalidate: true,
    reconcile: true,
    plugins: [
      {
        name: "leaf-sample-frames",
        resolveNode: (node) => (isSampleFrame(node) ? sampleContent(node) : undefined),
      },
    ],
  });
  if (failures.length)
    throw new Error(
      `A live sample in this area could not be captured: ${failures[0].message}`,
    );
  const blob = await image.toBlob({ format: "png" });
  if (image.warnings.some(({ code }) => code === "image-fallback"))
    throw new Error(
      "An image in this area could not be captured. Try another area or paste a screenshot.",
    );
  return blob;
}
