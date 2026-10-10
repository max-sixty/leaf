(() => {
  // skills/leaf/packages/default/widgets/activity-view.js
  var ACTIVITY_VIEW = "activity-reading:";
  function refreshActivityTarget(link, row, write) {
    const doc = link.ownerDocument;
    const href = doc.readyState !== "loading" && doc.getElementById(row.widget) ? `#${encodeURIComponent(row.widget)}` : null;
    if (!href) write(link, "tabindex", "-1");
    write(link, "href", href);
    if (href) write(link, "tabindex", null);
  }
  function target(row, offer) {
    if (row.thread) {
      const button = offer("button", "lf-activity-target");
      button.textContent = row.label;
      button.dataset.lfCarry = `row-${row.id}`;
      return button;
    }
    if (!row.widget && !row.label) return null;
    const label = row.label;
    if (!row.widget) {
      const span = document.createElement("span");
      span.className = "lf-activity-target";
      span.textContent = label;
      return span;
    }
    const link = document.createElement("a");
    link.className = "lf-activity-target";
    link.dataset.lfCarry = `row-${row.id}`;
    refreshActivityTarget(link, row, (node, name, value) => {
      if (value !== null) node.setAttribute(name, value);
    });
    link.textContent = label;
    return link;
  }
  function fillActivityRow(item, row, offer) {
    const avatar = document.createElement("span");
    avatar.className = "lf-activity-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = row.actor.slice(0, 1).toUpperCase();
    const line = document.createElement("p");
    line.className = "lf-activity-line";
    const actor = document.createElement("strong");
    actor.className = "lf-activity-actor";
    actor.textContent = row.actor;
    const what = document.createElement("span");
    what.className = "lf-activity-what";
    what.textContent = row.what;
    line.append(actor, " ", what);
    const place = target(row, offer);
    if (place) line.append(" ", place);
    const time = document.createElement("time");
    time.className = "lf-activity-time";
    time.dateTime = row.ts;
    time.title = new Date(row.ts).toLocaleString();
    line.append(" ", time);
    if (row.undone) {
      const undone = document.createElement("span");
      undone.className = "lf-activity-undone";
      undone.textContent = "undone";
      line.append(" ", undone);
    }
    item.replaceChildren(avatar, line);
    const excerpt = row.excerpt;
    if (excerpt) {
      const said = document.createElement("p");
      said.className = "lf-activity-excerpt";
      said.textContent = excerpt;
      item.append(said);
    }
    item.toggleAttribute("data-lf-undone", row.undone);
  }
  function initialActivity(host, { offer, tabStore }) {
    const saved = tabStore.get(ACTIVITY_VIEW + host.id);
    const reading = saved ? JSON.parse(saved) : { open: false, shown: "[]", label: "Show activity", news: false };
    const list = document.createElement("ol");
    list.className = "lf-activity-list";
    list.dataset.lfGen = "1";
    list.hidden = !reading.open;
    const empty = document.createElement("p");
    empty.className = "lf-activity-empty";
    empty.dataset.lfGen = "1";
    empty.textContent = "Nothing shown yet.";
    const notice = offer("button", "lf-activity-news lf-thread-notice", reading.label);
    notice.dataset.lfCarry = "notice";
    notice.setAttribute("aria-expanded", String(reading.open));
    notice.toggleAttribute("data-lf-news", reading.news);
    const rows = /* @__PURE__ */ new Map();
    const drawn = JSON.parse(reading.shown);
    for (const row of drawn) {
      const item = document.createElement("li");
      item.className = "lf-activity-row";
      item.setAttribute("data-lf-activity-author", row.author);
      fillActivityRow(item, row, offer);
      list.append(item);
      rows.set(row.id, { item, key: JSON.stringify(row) });
    }
    if (document.readyState === "loading")
      document.addEventListener(
        "readystatechange",
        () => {
          for (const row of drawn) {
            const link = rows.get(row.id).item.querySelector("a.lf-activity-target");
            if (link)
              refreshActivityTarget(link, row, (node, name, value) => {
                if (node.getAttribute(name) === value) return;
                if (value === null) node.removeAttribute(name);
                else node.setAttribute(name, value);
              });
          }
        },
        { once: true }
      );
    empty.hidden = !reading.open || drawn.length > 0;
    host.replaceChildren(notice, list, empty);
    return { notice, list, empty, rows, reading, restored: saved !== null };
  }

  // skills/leaf/packages/default/initial.js
  document.documentElement.lfInitial.register("lf-activity", initialActivity);
})();
