/* Leaf's data integration for one element it drives (element-integration.js), which
   calls initialize before the element's first draw from Leaf, deliver in each pass of
   sets, and connect with the element's presentation region on each arrival. The
   returned disconnect releases that region's data hold.
   The widget itself reads ordinary properties and reports drawn marks; this owner
   associates those drawings with the snapshots Leaf supplied, independently of Lit.

   Bound values. A module reads each input (`inputs`) through the plain property its
   declaration names (`property`): as the input's delivery moves, Leaf sets that
   property on the element to the delivered value, or null while the source has none,
   so the widget reads `this.value` as it would anywhere else a host sets it, and draws
   again as any element does when a host sets a property: in its setter, or, on Lit,
   by declaring the property reactive. A widget whose body is data (`content: data`) takes its `<pre>` as its
   `value`, as a `<textarea>`'s text is: where the markup binds the input whose property
   is `value` to nothing, to a source or to another widget's output, Leaf sets
   `value` to the text the page wrote in its `<pre>` once, with its first sets, since
   the widget's drawing replaces the `<pre>`. Its other inputs, such as the lines a code block
   follows, leave the `<pre>` alone. Any other unbound input, and one a module hosts on
   an element it made without a `<pre>`, is left to the widget and whoever else hosts
   it.

   The widget marks the items it drew with plain attributes (records/projection/data.js) and
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
import { untracked } from "/vendor/signals-core.js";
import {
  awaitsData,
  bindsInput,
  dataReader,
  joinDataDelivery,
  suppliedSnapshot,
} from "./data.js";
import { dataBody } from "../lib/data-body.js";
import { failSoft } from "../lib/failure.js";
import { registry } from "../state/registry.js";
import type { InputDeclaration } from "../state/registry.js";
import { projectMarked } from "../records/projection/data.js";
import type { DataSnapshot } from "./data.js";

export class ElementData {
  #element;
  #stage;
  #inputs: {
    input: string;
    property: string;
    bound: boolean;
    read: ReturnType<typeof dataReader> | null;
  }[];
  // Each property's last supplied snapshot, undefined once its setter threw, and
  // primitive values a later drawing can still name. Object values carry their snapshot
  // through suppliedSnapshot.
  #sent: Map<
    string,
    {
      snapshot: DataSnapshot | null | undefined;
      primitives: Map<unknown, DataSnapshot | null>;
    }
  > = new Map();

  constructor(element: Element, stage: () => void) {
    this.#element = element;
    this.#stage = stage;
    const declaration = registry[element.localName];
    this.#inputs = Object.entries<InputDeclaration>(declaration?.inputs ?? {}).flatMap(
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
        // The widget's own event: one sent with no detail names no property (`#drawn`).
        if (event.target === element) this.#drawn((event as CustomEvent).detail ?? {});
      });
  }

  initialize() {
    const element = this.#element;
    const declaration = registry[element.localName];
    // Only an authored, unbound data body supplies an initial `value`. A host
    // creating an element without a pre owns its value itself.
    const body = Object.values<InputDeclaration>(declaration?.inputs ?? {}).find(
      (input) => input.property === "value",
    );
    if (
      body &&
      declaration?.content === "data" &&
      element.querySelector(":scope > pre") &&
      !bindsInput(element, body)
    )
      Object.assign(element, { value: dataBody(element) });
  }

  awaitsDelivery() {
    return awaitsData(this.#element);
  }

  connect(region: string) {
    return registry[this.#element.localName]?.inputs ? joinDataDelivery(region) : null;
  }

  // Read before shouldUpdate, so an unchanged-value gate still follows delivery. A
  // setter that throws leaves its input owed the value again at the next delivery, and
  // every other input is still read and set, so the caller follows each one's next
  // delivery; the first failure is thrown once all are set.
  deliver() {
    let failed: { error: unknown } | null = null;
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
      // Recorded before the set, since a setter may draw and report `drawn` inside it.
      this.#sent.set(entry.property, { snapshot, primitives });
      try {
        // The caller follows the delivery it read above; what the element's setter
        // reads is the element's own to follow.
        untracked(() => Object.assign(this.#element, { [entry.property]: value }));
      } catch (error) {
        this.#sent.set(entry.property, { snapshot: undefined, primitives });
        failed ??= { error };
      }
    }
    if (failed) throw failed.error;
  }

  #drawn(detail: Record<string, unknown>) {
    const element = this.#element;
    try {
      const named = this.#inputs.filter(({ property }) =>
        Object.hasOwn(detail, property),
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
  #retire(property: string, value: unknown) {
    const primitives = this.#sent.get(property)?.primitives;
    if (!primitives?.has(value)) return undefined;
    for (const earlier of primitives.keys()) {
      if (earlier === value) break;
      primitives.delete(earlier);
    }
    return primitives.get(value);
  }
}
