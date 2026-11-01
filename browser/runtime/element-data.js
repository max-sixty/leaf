/* Leaf's data integration for an element lifecycle. The element calls initialize
   before setup, deliver before its update gate, and connect with its presentation
   region on each arrival. The returned disconnect releases that region's data hold.
   The widget itself reads ordinary properties and reports drawn marks; this owner
   associates those drawings with the snapshots Leaf supplied, independently of Lit.

   Bound values. A module reads each x-data input through the plain property its
   declaration names (`property`): before each update that the input's delivery
   moves, this element sets `this[property]` to the delivered value, or null while the
   source has none, so the widget reads `this.value` as it would anywhere else a host
   sets it. A widget whose body is data (`x-content: data`) declares at most one input,
   and where the markup binds it to nothing, to a source or to another widget's output,
   the widget reads the text the page wrote in its `<pre>` the same way: this element
   sets the input's property to that string once, at setup, since the widget's drawing
   replaces the `<pre>`. Any other unbound input, and one a module hosts on an element
   it made without a `<pre>`, is left to the widget and whoever else hosts it.

   The widget marks the items it drew with plain attributes (projection/data.js) and
   dispatches a non-bubbling `drawn` event whose detail names one bound property and
   the value it drew from it, `{value}`. A seat's stamp carries one source and revision,
   so a widget with several bound inputs marks the items of one of them and names that
   one. This element finds the snapshot that supplied the value and stamps the marks
   with it, so a draw that finishes after a newer value arrived keeps the revision it
   drew. An object value is one delivery's copy, which names its snapshot for as long
   as the widget holds it (`suppliedSnapshot`, data.js). A primitive value has no
   identity, so this element keeps the one the widget last reported and every one set
   since, each with its snapshot: a widget draws a value it holds or one handed to it
   after, so a report retires only the values set before the one it names. Equal
   primitive values share a revision, a digest of the value. A null value, or an input
   the markup leaves unbound, names words no bound value supplied, stamped without a
   source. Off a Leaf page no one listens, and the marks mean nothing. */
import {
  awaitsData,
  bindsInput,
  dataReader,
  joinDataDelivery,
  suppliedSnapshot,
} from "./data.js";
import { dataBody, failSoft } from "./widget-upgrade.js";
import { registry } from "./registry.js";
import { projectMarked } from "./projection/data.js";

export class ElementData {
  #element;
  #stage;
  /** @type {{input: string, property: string, bound: boolean, read: ReturnType<typeof dataReader> | null}[]} */
  #inputs;
  // Each property's last supplied snapshot, and primitive values a later drawing
  // can still name. Object values carry their snapshot through suppliedSnapshot.
  /** @type {Map<string, {snapshot: import("./data.js").DataSnapshot | null, primitives: Map<unknown, import("./data.js").DataSnapshot | null>}>} */
  #sent = new Map();

  /** @param {Element} element @param {() => void} stage */
  constructor(element, stage) {
    this.#element = element;
    this.#stage = stage;
    const declaration = registry[element.localName];
    this.#inputs = Object.entries(declaration?.["x-data"] ?? {}).flatMap(
      ([input, declaration]) =>
        declaration.property
          ? [
              {
                input,
                property: declaration.property,
                bound: bindsInput(element, declaration),
                read: null,
              },
            ]
          : [],
    );
    if (this.#inputs.length)
      element.addEventListener("drawn", (event) => {
        if (event.target === element)
          this.#drawn(/** @type {CustomEvent} */ (event).detail);
      });
  }

  initialize() {
    const element = this.#element;
    const declaration = registry[element.localName];
    // Only an authored, unbound data body supplies an initial property. A host
    // creating an element without a pre owns its value itself.
    if (
      declaration?.["x-content"] === "data" &&
      element.querySelector(":scope > pre") &&
      !Object.values(declaration["x-data"] ?? {}).some((input) =>
        bindsInput(element, input),
      )
    )
      for (const { property } of this.#inputs)
        Object.assign(element, { [property]: dataBody(element) });
  }

  awaitsDelivery() {
    return awaitsData(this.#element);
  }

  /** @param {string} region */
  connect(region) {
    return registry[this.#element.localName]?.["x-data"]
      ? joinDataDelivery(region)
      : null;
  }

  // Read before shouldUpdate, so an unchanged-value gate still follows delivery.
  deliver() {
    for (const entry of this.#inputs) {
      if (!entry.bound) continue;
      entry.read ??= dataReader(this.#element, entry.input, this.#stage);
      const snapshot = entry.read();
      const sent = this.#sent.get(entry.property);
      if (sent && sent.snapshot === snapshot) continue;
      const value = snapshot ? snapshot.value : null;
      const primitives = sent?.primitives ?? new Map();
      if (value !== null && typeof value !== "object") {
        primitives.delete(value);
        primitives.set(value, snapshot);
      }
      this.#sent.set(entry.property, { snapshot, primitives });
      Object.assign(this.#element, { [entry.property]: value });
    }
  }

  /** @param {Record<string, unknown>} detail */
  #drawn(detail) {
    const element = this.#element;
    try {
      const named = this.#inputs.filter(
        ({ property }) => detail && Object.hasOwn(detail, property),
      );
      const entry = named[0];
      if (!entry || named.length !== 1 || Object.keys(detail).length !== 1)
        throw new Error(
          `<${element.localName}> drawn must name one bound property (${this.#inputs
            .map(({ property }) => property)
            .join(", ")}) with the value it drew`,
        );
      const { property, bound } = entry;
      const value = detail[property];
      const snapshot =
        !bound || value === null
          ? null
          : typeof value === "object"
            ? suppliedSnapshot(value)
            : this.#retire(property, value);
      if (snapshot === undefined)
        throw new Error(
          `<${element.localName} id=${element.id}> drew a ${property} Leaf did not set`,
        );
      projectMarked(element, snapshot);
    } catch (error) {
      failSoft(element, error);
    }
  }

  // A drawing retires only primitives supplied before the value it names: a newer
  // delivery may already have arrived while that drawing was being prepared.
  /** @param {string} property @param {unknown} value */
  #retire(property, value) {
    const primitives = this.#sent.get(property)?.primitives;
    if (!primitives?.has(value)) return undefined;
    for (const earlier of primitives.keys()) {
      if (earlier === value) break;
      primitives.delete(earlier);
    }
    return primitives.get(value);
  }
}
