/* A package chooses layout while Leaf retains conversations, messages and replies.
   Local selection and ordering never change the log or decide obligation membership. */
import {
  compoundReadingRegionId,
  HeldReading,
  keepsHidden,
  keeps,
  keepsText,
  offer,
  queueActions,
  queueItemKey,
  queueTitle,
  readQuestions,
  readQueues,
  readThreads,
  registerThreadPresentation,
  registerReadingRegion,
  setChildren,
  shadowStage,
  threadActions,
  threadSummary,
  threadTurns,
  watchQuestions,
  watchQueues,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-conversation-workspace",
  class extends HTMLElement {
    connectedCallback() {
      if (!this.layout) this.build();
      this.stopRegions = this.regionBodies.map(([name, body]) =>
        registerReadingRegion({
          id: compoundReadingRegionId(this, name),
          host: body,
          body,
        }),
      );
      this.presentation = registerThreadPresentation(this, {
        render: (collection, parts) => this.present(collection, parts),
        reveal: (key) => {
          this.selected = key;
          this.mode = "Conversation";
        },
      });
      this.stopQuestions = watchQuestions(this, () => this.paintObligations());
      this.stopQueues = watchQueues(this, () => this.paintObligations());
    }
    disconnectedCallback() {
      for (const stop of this.stopRegions) stop();
      this.presentation.unregister();
      this.stopQuestions();
      this.stopQueues();
      this.indexOrder.dispose();
    }
    build() {
      this.mode = "Conversation";
      this.rows = new Map();
      this.outlets = new Map();
      this.queueRows = new Map();
      const style = document.createElement("style");
      style.textContent = `
      :host { display:block; height:560px; container-type:inline-size; }
      .workspace { height:100%; display:grid; grid-template-rows:auto minmax(0,1fr) auto;
        gap:12px; padding:12px; border:1px solid var(--rule); border-radius:8px; }
      .toolbar,.compose { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
      .body { display:grid; grid-template-columns:minmax(0,12rem) minmax(0,1fr); gap:16px; min-height:0; }
      .index,.reader { min-width:0; min-height:0; overflow:auto; }
      .index { display:grid; grid-template-columns:minmax(0,1fr); grid-template-rows:minmax(0,2fr) repeat(3,minmax(0,1fr)); gap:8px; }
      .group { min-width:0; min-height:0; display:flex; flex-direction:column; }
      .group ul { overflow:auto; min-height:0; }
      .group h4 { flex:none; margin:0 0 6px; }
      .counts { flex:none; min-height:2lh; margin:0 0 6px; }
      .index button { width:100%; min-width:0; text-align:start; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

      .index ul { list-style:none; margin:0; padding:0; }
      .index li { display:flex; gap:4px; margin:4px 0; }
      .index li > button:first-child { flex:1; }
      .index li > button:last-child:not(:first-child) { width:auto; }
      .reader > div { margin-bottom:16px; }
      .compose input { flex:1; min-width:8rem; }
      .counts { color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }
      @container (width < 500px) {
        .body { grid-template-columns:minmax(0,1fr); grid-template-rows:minmax(14rem,1fr) minmax(0,1fr); gap:8px; }
        .index { grid-template-columns:repeat(2,minmax(0,1fr)); grid-template-rows:repeat(2,minmax(0,1fr)); }
        .group h4 { font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .counts { min-height:1lh; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      }
    `;
      this.layout = offer("div", "workspace");
      const toolbar = offer("div", "toolbar");
      toolbar.setAttribute("role", "group");
      toolbar.setAttribute("aria-label", "Reader layout");
      this.modes = ["Conversation", "Shelf", "Feed"].map((mode) => {
        const button = offer("button", "lf-btn", mode);
        button.addEventListener("click", () => {
          this.mode = mode;
          void this.presentation.update({ release: true });
        });
        toolbar.append(button);
        return button;
      });
      const body = offer("div", "body");
      const index = offer("aside", "index");
      const title = offer("h4", "", "Conversations");
      this.list = offer("ul");
      this.counts = offer("p", "counts");
      this.queues = Object.fromEntries(
        ["onYou", "onAgent", "done"].map((key, i) => {
          const heading = offer("h4", "", ["On you", "On agent", "Done"][i]);
          const list = offer("ul");
          const group = offer("div", "group");
          group.append(heading, list);
          index.append(group);
          return [key, list];
        }),
      );
      const conversations = offer("div", "group");
      conversations.append(title, this.counts, this.list);
      index.prepend(conversations);
      this.reader = offer("section", "reader");
      this.reader.setAttribute("aria-label", "Conversation reader");
      this.regionBodies = [
        ["reader", this.reader],
        ["index", index],
        ["conversations", this.list],
        ...Object.entries(this.queues).map(([name, body]) => [
          name.toLowerCase(),
          body,
        ]),
      ];
      body.append(index, this.reader);
      const compose = offer("form", "compose");
      this.input = offer("input");
      this.input.name = "comment";
      this.creationEdit = 0;
      this.input.addEventListener("input", () => this.creationEdit++);
      this.input.autocomplete = "off";
      this.input.setAttribute("aria-label", "New conversation");
      const create = offer("button", "lf-btn", "Start conversation");
      create.type = "submit";
      compose.append(this.input, create);
      compose.addEventListener("submit", (event) => event.preventDefault());
      create.addEventListener("click", (event) => {
        event.preventDefault();
        const text = this.input.value;
        this.indexOrder.release();
        const creation = threadActions.create({ text });
        if (!creation) return;
        this.input.value = "";
        const edit = this.creationEdit;
        void creation.delivery.then((sent) => {
          if (!sent && this.creationEdit === edit && this.input.value === "")
            this.input.value = text;
        });
        this.selected = creation.key;
        this.mode = "Conversation";
        void this.presentation.update();
      });
      this.indexOrder = new HeldReading(
        () => [this.list, ...Object.values(this.queues)],
        () => {
          void this.presentation.update();
        },
      );
      this.updateLists = offer("button", "lf-btn", "Lists current");
      this.updateLists.addEventListener("click", () => this.indexOrder.show());
      toolbar.append(this.updateLists);
      this.layout.append(toolbar, body, compose);
      shadowStage(this, [style, this.layout]);
    }
    outlet(identity) {
      if (!this.outlets.has(identity)) this.outlets.set(identity, offer("div"));
      return this.outlets.get(identity);
    }
    present(collection, parts) {
      this.collection = collection;
      this.selected ??= collection.threads[0]?.key;
      for (const button of this.modes)
        keeps(button, "aria-pressed", button.textContent === this.mode);
      const currentThreads = new Map(
        collection.threads.map((thread) => [thread.key, thread]),
      );
      const slots = this.indexLayout();
      const rows = slots.threads.map((key) => {
        const thread = currentThreads.get(key);
        let row = this.rows.get(key);
        if (!row) {
          const node = offer("li");
          const button = offer("button", "lf-btn");
          button.addEventListener("click", () => {
            void threadActions.open(key, { focus: "thread" });
          });
          node.append(button);
          row = { node, button };
          this.rows.set(key, row);
        }
        keepsHidden(row.button, !thread);
        row.node.style.minHeight = "3rem";
        if (thread) {
          keepsText(row.button, threadSummary(thread).topic);
          keeps(row.button, "aria-current", key === this.selected ? "true" : null);
        }
        return row.node;
      });
      setChildren(this.list, rows);
      const selected = collection.threads.find(
        (thread) => thread.key === this.selected,
      );
      const nominations = [];
      if (this.mode === "Feed") {
        for (const thread of collection.threads)
          for (const message of threadTurns(thread)) {
            const outlet = this.outlet(JSON.stringify([thread.key, message.key]));
            nominations.push(["message", thread.key, message.key, outlet]);
          }
        if (selected)
          nominations.push([
            "reply",
            selected.key,
            null,
            this.outlet("reply:" + selected.key),
          ]);
      } else {
        for (const thread of this.mode === "Shelf"
          ? collection.threads
          : selected
            ? [selected]
            : [])
          nominations.push([
            "thread",
            thread.key,
            null,
            this.outlet("thread:" + thread.key),
          ]);
      }
      setChildren(
        this.reader,
        nominations.map((item) => item[3]),
      );
      for (const [kind, key, message, outlet] of nominations)
        if (kind === "message") parts.message(key, message, outlet);
        else if (kind === "reply") parts.reply(key, outlet);
        else parts.thread(key, outlet);
      this.paintObligations();
    }
    indexLayout() {
      const queues = readQueues();
      const current = JSON.stringify({
        threads: readThreads().threads.map((thread) => thread.key),
        ...Object.fromEntries(
          Object.keys(this.queues).map((name) => [
            name,
            queues[name].map(queueItemKey),
          ]),
        ),
      });
      const shown = this.indexOrder.hold(current);
      keepsText(this.updateLists, "Show updated lists");
      keeps(this.updateLists, "disabled", shown === current ? "" : null);
      return JSON.parse(shown);
    }
    paintObligations() {
      const questions = readQuestions();
      const answers = questions.all.filter(
        (question) => question.status === "answered",
      );
      keepsText(
        this.counts,
        `${questions.user.length} Questions on you${answers.length ? ` · ${answers.length} answered` : ""}`,
      );
      const queues = readQueues();
      const layout = this.indexLayout();
      for (const [name, list] of Object.entries(this.queues)) {
        const current = new Map(queues[name].map((item) => [queueItemKey(item), item]));
        const rows = layout[name].map((key) => {
          const item = current.get(key);
          const identity = JSON.stringify([name, key]);
          let row = this.queueRows.get(identity);
          if (!row) {
            const node = offer("li");
            const open = offer("button", "lf-btn");
            open.addEventListener("click", () => void queueActions.open(key));
            const done = offer("button", "lf-btn", "Done");
            done.addEventListener("click", () => {
              this.indexOrder.release();
              void queueActions.done(key);
            });
            row = { node, open, done };
            this.queueRows.set(identity, row);
          }
          row.node.style.minHeight = "3rem";
          if (!item) {
            setChildren(row.node, []);
            return row.node;
          }
          keepsText(row.open, `Open ${queueTitle(item)}`);
          setChildren(row.node, item.offers.done ? [row.open, row.done] : [row.open]);
          return row.node;
        });
        setChildren(list, rows);
      }
    }
  },
);
