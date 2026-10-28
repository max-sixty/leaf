import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/vendor/lit.js";
import { initialRender } from "/runtime/initial-render.js";
import "../../packages/default/initial/lf-shot.js";

// Web Awesome reparents frames into its slots; those frames must still receive the
// same drawing's captions, image sources, links and evidence through each view.
test("Screenshot drawing retains controls, frames and images across adoption and comparison slots", () => {
  const host = document.createElement("lf-shot");
  host.setAttribute("alt", "Changed controls");
  document.body.append(host);
  const drawing = initialRender(host);
  const frames = [...drawing.frames];
  const viewports = [...drawing.viewports];
  const images = [...host.querySelectorAll(".lf-shotframe img")];
  const controls = [...host.querySelectorAll("button, input")];
  const clicked = [];
  const imagesOf = (suffix) =>
    ["before", "after"].map((state) => {
      const image = document.createElement("img");
      image.src = `/${state}-${suffix}.png`;
      return image;
    });
  const shown = {
    view: "flip",
    position: 100,
    actual: false,
    full: false,
    outlines: true,
    metadata: { labels: { before: "Base", after: "Candidate" }, focus: {} },
    reading: {
      width: 200,
      height: 100,
      regions: [{ side: "after", kind: "added", x: 20, y: 10, width: 40, height: 30 }],
    },
    description: "One changed region",
    geometry: { layout: "side", fitScale: 0.5 },
    images: imagesOf("first"),
    pixels: false,
    pixelUrl: null,
  };
  drawing.chooseView = (view) => clicked.push(view);
  const paint = (state = shown) => {
    Object.assign(drawing, state);
    render(drawing.render(), host);
  };
  const beforeLabel = host.querySelector('.lf-shot-toolbar [data-lf-state="before"]');
  const afterLabel = host.querySelector('.lf-shot-toolbar [data-lf-state="after"]');
  try {
    const slider = controls[0];
    slider.focus();
    paint();
    assert.equal(initialRender(host), drawing);
    assert.equal(document.activeElement, slider);
    slider.click();
    assert.deepEqual(clicked, ["flip"]);
    assert.equal(beforeLabel.textContent, "Base");
    assert.equal(afterLabel.hasAttribute("data-lf-shot-hidden"), true);
    assert.equal(beforeLabel.hasAttribute("data-lf-said"), true);
    assert.equal(images[0].src, shown.images[0].src);
    assert.equal(images[0].getAttribute("src"), "/before-first.png");
    const comparison = document.createElement("div");
    drawing.canvas.append(comparison);
    comparison.append(...frames);
    paint({ ...shown, actual: true, images: imagesOf("next") });
    assert.deepEqual([...comparison.children], frames);
    assert.equal(images[1].src, "https://leaf.test/after-next.png");
    assert.equal(
      frames[1]
        .querySelector("[data-lf-shot-mark]")
        .style.getPropertyValue("--lf-shot-w"),
      "20%",
    );
    for (const frame of frames) drawing.canvas.append(frame);
    comparison.remove();
    host.setAttribute("alt", "New capture");
    paint({
      ...shown,
      view: "compare",
      geometry: { layout: "stack", fitScale: 0.25 },
      pixels: true,
      pixelUrl: "blob:mask",
    });
    assert.equal(beforeLabel.hasAttribute("data-lf-echo"), true);
    assert.equal(
      frames[0].querySelector(".lf-shotcap").hasAttribute("data-lf-said"),
      true,
    );
    assert.equal(viewports[0].getAttribute("aria-label"), "Base — New capture");
    assert.equal(
      frames[0].querySelector("a").getAttribute("href"),
      shown.images[0].src,
    );
    assert.equal(frames[0].querySelector("a").hasAttribute("tabindex"), false);
    assert.equal(
      host.querySelector(".lf-shotpixels").getAttribute("aria-label"),
      "changed pixels: New capture",
    );
    const pixels = host.querySelector(".lf-shotpixels");
    paint({ ...shown, view: "pixels", full: true, pixels: true });
    assert.equal(host.querySelector(".lf-shotpixels"), pixels);
    assert.equal(
      pixels.querySelector("span").style.getPropertyValue("--lf-shot-pixels"),
      "",
    );
    assert.equal(host.querySelector(".lf-shot-outline").disabled, true);
    assert.equal(host.querySelector("input").checked, true);
    assert.equal(frames[0].querySelector("a").hasAttribute("href"), false);
    assert.deepEqual([...host.querySelectorAll("button, input")], controls);
    assert.deepEqual(drawing.frames, frames);
    assert.deepEqual(drawing.viewports, viewports);
    assert.deepEqual([...host.querySelectorAll(".lf-shotframe img")], images);
  } finally {
    host.remove();
  }
});
