import "@observablehq/plot";

// Plot's Mark constructor (src/mark.js) sets these layout properties; styles.js
// supplies the optional accessible name. They are omitted from its declarations.
declare module "@observablehq/plot" {
  interface Mark {
    dx: number;
    dy: number;
    marginTop: number;
    marginRight: number;
    marginBottom: number;
    marginLeft: number;
    ariaLabel?: string | null | undefined;
  }
}

import "density-clustering";

// DBSCAN._init stores each datum unchanged and _regionQuery passes it to the
// supplied metric (density-clustering/lib/DBSCAN.js). Numeric vectors are only
// required by its default Euclidean metric.
declare module "density-clustering" {
  interface DBSCAN {
    run<T>(
      dataset: T[],
      neighborhoodRadius: number,
      minPointsPerCluster: number,
      distanceFunction: (p: T, q: T) => number,
    ): number[][];
  }
}

import "diff";

// createTwoFilesPatch forwards its options to diffLines, whose equals delegates
// to Diff.equals and honors a custom comparator (diff/libcjs/diff/base.js).
declare module "diff" {
  interface CreatePatchOptionsNonabortable {
    comparator?: (oldLine: string, newLine: string) => boolean;
  }
}

import "viewerjs";

// Viewer exposes its mounted surface and current image geometry on the instance
// (src/js/viewer.js, render.js and events.js). Geometry is empty until an image
// has loaded; the view owner retains the completed reading after `viewed`.
declare global {
  namespace Viewer {
    interface ImageGeometry {
      left: number;
      top: number;
      x: number;
      y: number;
      width: number;
      height: number;
      oldRatio: number;
      ratio: number;
      aspectRatio: number;
      naturalWidth: number;
      naturalHeight: number;
      rotate?: number;
      scaleX?: number;
      scaleY?: number;
    }
  }
  interface Viewer {
    element: HTMLElement | ShadowRoot;
    viewed: boolean;
    viewer?: HTMLDivElement;
    image?: HTMLImageElement | null;
    imageData: Partial<Viewer.ImageGeometry>;
    onResize?: () => void;
    resize(): void;
  }
}

// Lit 3's production build preserves this public internal setter under its minified name.
declare module "lit-html" {
  interface ChildPart {
    _$AI?: ChildPart["_$setValue"];
  }
}
