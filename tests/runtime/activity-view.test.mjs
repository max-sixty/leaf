import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/vendor/lit.js";
// A page's boot installs the mover's focus accounting before anything renders
// (leaf.js), which keeps focus on a row the reorder moves.
import "/runtime/dom/move-focus.js";
import { tabStore } from "/runtime/state/tab-store.js";
import {
  ACTIVITY_VIEW,
  createActivity,
} from "../../packages/default/widgets/activity-view.js";
const row = (id, target) => ({
  id,
  author: "user",
  actor: "Me",
  what: "commented on",
  label: id,
  ts: "2026-10-21T00:00:00Z",
  undone: false,
  excerpt: null,
  ...target,
});
const reading = (rows) => ({
  open: true,
  shown: JSON.stringify(rows),
  label: "Hide activity",
  news: false,
});

test("Activity's retained rows keep their nodes, focus and live targets through restored readings and reorder", () => {
  const host = document.createElement("lf-activity");
  host.id = "activity-template";
  const destination = document.createElement("section");
  destination.id = "activity-destination";
  const widget = row("widget-row", { widget: destination.id });
  const thread = row("thread-row", { thread: "thread-1" });
  const first = reading([widget, thread]);
  tabStore.set(ACTIVITY_VIEW + host.id, JSON.stringify(first));
  document.body.append(host, destination);
  const drawing = createActivity(host);
  render(drawing.render(), host, { host });
  const renderReading = (...args) => render(drawing.render(...args), host, { host });
  const notice = drawing.notice;
  const items = [...drawing.list.children];
  const link = items[0].querySelector("a");
  const button = items[1].querySelector("button");
  const opened = [];
  const live = {
    names: (fragment) => document.getElementById(fragment.slice(1)),
    openThread: (id) => opened.push(id),
  };
  try {
    assert.equal(drawing.restored, true);
    renderReading(first, live);
    assert.equal(drawing.notice, notice);
    assert.deepEqual([...drawing.list.children], items);
    assert.equal(items[0].querySelector("a"), link);
    assert.equal(items[1].querySelector("button"), button);
    assert.equal(
      items[0].querySelector("lf-age").getAttribute("datetime"),
      "2026-10-21T00:00:00Z",
    );
    assert.equal(link.getAttribute("href"), "#activity-destination");
    link.focus();
    const reordered = reading([thread, { ...widget, label: "Renamed", undone: true }]);
    renderReading(reordered, live);
    assert.deepEqual([...drawing.list.children], [items[1], items[0]]);
    assert.equal(document.activeElement, link);
    assert.equal(link.textContent, "Renamed");
    assert.equal(items[0].hasAttribute("data-lf-undone"), true);
    destination.remove();
    renderReading(reordered, live);
    assert.equal(items[0].querySelector("a"), link);
    assert.equal(document.activeElement, link);
    assert.equal(link.hasAttribute("href"), false);
    assert.equal(link.getAttribute("tabindex"), "-1");
    document.body.append(destination);
    renderReading(reordered, live);
    assert.equal(link.getAttribute("href"), "#activity-destination");
    assert.equal(link.hasAttribute("tabindex"), false);
    button.click();
    assert.deepEqual(opened, ["thread-1"]);
    renderReading({ ...reordered, open: false }, live);
    assert.equal(drawing.list.hidden, true);
    renderReading({ ...reordered, open: false }, { ...live, printing: true });
    assert.equal(drawing.list.hidden, false);
  } finally {
    tabStore.set(ACTIVITY_VIEW + host.id, null);
    host.remove();
    destination.remove();
  }
});
