/* Authored-flow presentation of the complete page Thread collection.

   The author allocates this rail's box. Native disclosures own expansion; the
   shared Thread coordinator owns cards, source standing and the one composer.
   Other rows consume the same annotation inventory as core navigation and use
   canonical item activation and retained native contribution controls.
   Preparation only nominates retained outlets. A removed row stays connected
   while its old seat still holds native content, including across refused cohorts;
   a later pass can retire it after a successful cohort has emptied that seat. */
import {
  afterScript,
  anchorLabel,
  annotationMode,
  consumeAnnotations,
  consumePageThreads,
  contributionItemKey,
  HeldReading,
  holdFocus,
  keeps,
  keepsHidden,
  keepsText,
  layoutPx,
  once,
  offer,
  openThread,
  setChildren,
} from "/runtime/widget-api.js";

const make = (tag, className, text = "") => {
  return offer(tag, className, text);
};

customElements.define(
  "lf-annotation-rail",
  class extends HTMLElement {
    #surface = null;
    #annotations = null;
    #actionRows = new Map();
    #nextSlot = 0;
    #actionOrder;
    #actionNotice;
    #noticeCurrent = true;
    #groups = new Map();
    #rows = new Map();
    #list;
    #empty;
    #composer;
    #composerName;
    #composerOutlet;
    #actions;

    // Immediate contribution updates and their focus arrival can paint in one script.
    // The fixed notice describes that script's final held layout, not its intermediate one.
    #paintNotice = () => {
      keepsText(
        this.#actionNotice,
        this.#noticeCurrent ? "Annotations current" : "Show updated annotations",
      );
      keeps(this.#actionNotice, "disabled", this.#noticeCurrent ? "" : null);
    };

    connectedCallback() {
      if (once(this)) this.#build();
      if (annotationMode !== "page") return;
      this.#surface ??= consumePageThreads(this, (collection, surfaces) =>
        this.#present(collection, surfaces),
      );
      this.#annotations ??= consumeAnnotations(this, (entries, view) =>
        this.#presentActions(entries, view),
      );
    }

    disconnectedCallback() {
      this.#surface?.unregister();
      this.#surface = null;
      this.#annotations?.unregister();
      this.#annotations = null;
      this.#actionOrder?.dispose();
    }

    #build() {
      const region = make("section", "lf-ar-region lf-ui");
      region.dataset.lfGen = "1";
      region.dataset.lfRuntime = "";
      region.setAttribute("aria-label", "Page annotations");
      region.append(make("h2", "lf-ar-heading", "Annotations"));
      this.#empty = make("p", "lf-ar-empty", "No threads yet.");
      this.#list = make("div", "lf-ar-list");
      this.#actions = make("div", "lf-ar-actions");
      this.#actionNotice = make("button", "lf-ar-notice lf-btn", "Annotations current");
      this.#actionNotice.type = "button";
      this.#actionOrder = new HeldReading(
        () => [this.#actions],
        () => this.#annotations?.update(),
      );
      this.#actionNotice.addEventListener("click", () => this.#actionOrder.show());
      this.#composer = make("section", "lf-ar-composer");
      this.#composer.hidden = true;
      this.#composerName = make("h3", "lf-ar-source");
      this.#composerOutlet = make("div", "lf-ar-outlet");
      this.#composer.append(this.#composerName, this.#composerOutlet);
      region.append(
        this.#actionNotice,
        this.#composer,
        this.#empty,
        this.#list,
        this.#actions,
      );
      this.append(region);
    }

    #group(section) {
      let group = this.#groups.get(section);
      if (!group) {
        const node = make("section", "lf-ar-group");
        const name = make("h3", "lf-ar-source");
        const rows = make("div", "lf-ar-rows");
        node.append(name, rows);
        this.#list.append(node);
        group = { node, name, rows };
        this.#groups.set(section, group);
      }
      keepsText(group.name, anchorLabel(section ? { section } : null) || "The page");
      return group;
    }

    #row(thread) {
      const group = this.#group(thread.anchor?.section ?? null);
      let row = this.#rows.get(thread.key);
      if (!row) {
        const node = make("div", "lf-ar-entry");
        const outlet = make("div", "lf-ar-outlet");
        const button = make("button", "lf-ar-open lf-btn", "Open thread");
        button.type = "button";
        row = { node, outlet, button, id: thread.id };
        button.addEventListener("click", async () => {
          await openThread(row.id, { focus: "thread", travel: false });
        });
        node.append(button, outlet);
        group.rows.append(node);
        this.#rows.set(thread.key, row);
      }
      if (row.node.parentElement !== group.rows) {
        const restore = holdFocus(row.node);
        group.rows.append(row.node);
        restore?.();
      }
      row.id = thread.id;
      keepsText(
        row.button,
        `Open thread · ${anchorLabel(thread.anchor, thread.root.about) || "The page"}`,
      );
      return row;
    }

    #measureSlots() {
      for (const row of this.#actionRows.values()) {
        for (const { node } of row.slots.values()) {
          if (!node.isConnected || node.style.inlineSize) continue;
          const width = node.getBoundingClientRect().width;
          if (width > 0) node.style.inlineSize = layoutPx(width);
        }
      }
    }

    #presentActions(entries, view) {
      this.#measureSlots();
      const current = new Map();
      for (const entry of entries) {
        const items = view.items(entry).filter((item) => item.kind !== "comment");
        const controls = view.controls(entry);
        if (!items.length && !controls.length) continue;
        let row = this.#actionRows.get(entry.key);
        if (!row) {
          const node = make("section", "lf-ar-action-row");
          const name = make("h3", "lf-ar-source");
          const body = make("div", "lf-ar-action-controls");
          node.append(name, body);
          row = { node, name, body, items: new Map(), slots: new Map() };
          this.#actionRows.set(entry.key, row);
        }
        const nodes = new Map();
        for (const item of items) {
          const key = contributionItemKey(item);
          let button = row.items.get(key);
          if (!button) {
            const node = make("button", "lf-ar-item lf-btn");
            node.type = "button";
            button = { node, item, activate: view.activate };
            node.addEventListener("click", async () => {
              await button.activate(button.item);
            });
            row.items.set(key, button);
          }
          button.item = item;
          button.activate = view.activate;
          const words = [item.label, item.text, item.context]
            .filter(Boolean)
            .join(" · ");
          keepsText(button.node, words);
          keeps(button.node, "title", words);
          nodes.set(JSON.stringify(["item", key]), {
            node: button.node,
            kind: "item",
            owner: item.owner ?? null,
          });
        }
        for (const key of row.items.keys())
          if (!items.some((item) => contributionItemKey(item) === key))
            row.items.delete(key);
        for (const control of controls)
          nodes.set(JSON.stringify(["control", view.controlKey(control)]), {
            node: control,
            kind: "control",
            owner: view.controlRecord(control).owner,
          });
        // Semantic keys retain surviving controls first. A current action may then
        // fill a retired allocation belonging to that same owner (Edit becomes Save),
        // without making its neighbours move or holding the new action as old news.
        const assigned = new Map();
        const used = new Set();
        for (const [key, reading] of nodes) {
          const prior = [...row.slots].find(([, slot]) => slot.key === key);
          if (prior) {
            assigned.set(key, { id: prior[0], reading });
            used.add(prior[0]);
          }
        }
        for (const [key, reading] of nodes) {
          if (assigned.has(key)) continue;
          let prior = [...row.slots].find(
            ([id, slot]) =>
              !used.has(id) &&
              slot.kind === reading.kind &&
              slot.owner === reading.owner,
          );
          if (!prior) {
            const id = ++this.#nextSlot;
            const slot = {
              node: make("span", "lf-ar-slot"),
              kind: reading.kind,
              owner: reading.owner,
              key,
            };
            row.slots.set(id, slot);
            prior = [id, slot];
          }
          prior[1].key = key;
          assigned.set(key, { id: prior[0], reading });
          used.add(prior[0]);
        }
        const allocations = new Map(
          [...nodes.keys()].map((key) => {
            const { id, reading } = assigned.get(key);
            return [id, reading.node];
          }),
        );
        current.set(entry.key, { entry, row, allocations });
      }
      // Hold layout identities, never records. Live labels, actions and native controls
      // stay current; removed slots empty immediately and retain only their allocation.
      const wanted = JSON.stringify(
        [...current].map(([key, { allocations }]) => [key, [...allocations.keys()]]),
      );
      if (view.arriving) this.#actionOrder.release();
      let shown = this.#actionOrder.hold(wanted);
      // A strip owns its whole allocated width. A trailing action that fits there
      // changes no surviving slot or neighbouring row, so it is already drawable.
      // Changed ordering, new rows and overflow still wait at the notice.
      if (shown !== wanted) {
        const shape = JSON.parse(shown);
        for (const rowShape of shape) {
          const [key, keys] = rowShape;
          const reading = current.get(key);
          if (!reading) continue;
          const next = [...reading.allocations.keys()];
          if (next.length <= keys.length || keys.some((id, at) => next[at] !== id))
            continue;
          const { row } = reading;
          const previous = [...row.body.children];
          const slots = next.map((id) => {
            const slot = row.slots.get(id);
            setChildren(slot.node, [reading.allocations.get(id)]);
            return slot.node;
          });
          setChildren(row.body, slots);
          const width = row.body.clientWidth;
          if (width > 0 && row.body.scrollWidth <= width) rowShape[1] = next;
          setChildren(row.body, previous);
        }
        const fitting = JSON.stringify(shape);
        if (fitting !== shown) {
          this.#actionOrder.release();
          shown = this.#actionOrder.hold(fitting);
        }
      }
      this.#noticeCurrent = shown === wanted;
      afterScript(this.#paintNotice);
      const rows = [];
      const shape = JSON.parse(shown);
      for (const [key, keys] of shape) {
        const reading = current.get(key);
        const row = this.#actionRows.get(key);
        if (!reading) {
          row.node.style.minBlockSize = layoutPx(
            row.node.getBoundingClientRect().height,
          );
          keepsText(row.name, "");
          for (const { node } of row.slots.values()) setChildren(node, []);
          row.items.clear();
          rows.push(row.node);
          continue;
        }
        row.node.style.minBlockSize = "";
        keepsText(row.name, reading.entry.title);
        keeps(row.name, "title", reading.entry.title);
        const slots = keys.map((id) => {
          const slot = row.slots.get(id);
          setChildren(
            slot.node,
            reading.allocations.has(id) ? [reading.allocations.get(id)] : [],
          );
          return slot.node;
        });
        for (const id of row.slots.keys())
          if (!keys.includes(id) && !reading.allocations.has(id)) row.slots.delete(id);
        setChildren(row.body, slots);
        rows.push(row.node);
      }
      const live = new Set(shape.map(([key]) => key));
      for (const key of this.#actionRows.keys())
        if (!live.has(key)) this.#actionRows.delete(key);
      setChildren(this.#actions, rows);
      this.#measureSlots();
      for (const [key] of shape) {
        const reading = current.get(key);
        if (!reading) continue;
        view.place(reading.entry, reading.row.node);
      }
    }

    #present(collection, surfaces) {
      const current = new Set(collection.threads.map((thread) => thread.key));
      for (const [key, row] of this.#rows) {
        if (!current.has(key) && !row.outlet.firstElementChild) {
          row.node.remove();
          this.#rows.delete(key);
        } else row.node.toggleAttribute("data-lf-ar-retired", !current.has(key));
      }
      for (const thread of collection.threads) {
        const row = this.#row(thread);
        row.node.removeAttribute("data-lf-ar-retired");
        const target = surfaces.target(thread.key);
        if (target) surfaces.place(thread.key, row.outlet);
      }
      for (const [section, group] of this.#groups) {
        if (!group.rows.childElementCount) {
          group.node.remove();
          this.#groups.delete(section);
        }
      }
      keepsHidden(this.#empty, collection.threads.length > 0);
      keepsHidden(
        this.#composer,
        !surfaces.composition && !this.#composerOutlet.firstElementChild,
      );
      this.#composer.toggleAttribute("data-lf-ar-retired", !surfaces.composition);
      if (surfaces.composition) {
        keepsText(
          this.#composerName,
          `Comment · ${anchorLabel(surfaces.composition.anchor) || "The page"}`,
        );
        surfaces.placeComposition(this.#composerOutlet);
      }
    }
  },
);
