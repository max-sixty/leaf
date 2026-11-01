/* Leaf's host capabilities for the portable element lifecycle. Install before
   widgets connect: page presentation, authored/bound data, widget controllers and
   command dressing belong to the page, while the element owns Lit and its failures.
   A plain host supplies properties and listens to drawn without loading this module. */
import { installElementIntegration } from "./leaf-element.js";
import {
  attachApplicationPresentation,
  attachWidgetPresentation,
  queueWidgetUpdate,
  watchPresentation,
} from "./semantic-state.js";
import { widgetDescriptor } from "./widget-descriptors.js";
import { drawsItself, widgetController, widgetMounted } from "./widget-controller.js";
import { paintKeysWithin } from "./keyboard/scopes.js";
import { ElementData } from "./element-data.js";
import { registry } from "./registry.js";

installElementIntegration({
  attachApplicationPresentation,
  attachWidgetPresentation,
  queueWidgetUpdate,
  watchPresentation,
  widgetDescriptor,
  drawsItself,
  widgetController,
  widgetMounted,
  paintKeysWithin,
  data: (element, stage) => new ElementData(element, stage),
  shadows: (element) => registry[element.localName]?.["x-shadow"],
});
