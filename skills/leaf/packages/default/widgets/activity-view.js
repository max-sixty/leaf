/* One activity drawing, used synchronously for retained tab-local reading and by
 * the live history subscriber. Retained rows are a presentation snapshot: no event,
 * semantic fold or application fact is reconstructed from them. The next authoritative
 * history is held/revealed by the behavior module through HeldReading. */
export const ACTIVITY_VIEW = "activity-reading:";

function target(row, offer) {
  if (row.thread) {
    const button = offer("button", "lf-activity-target");
    button.textContent = row.label;
    button.dataset.lfCarry = `row-${row.id}`;
    return button;
  }
  if (!row.widget && !row.label) return null;
  const label = row.label;
  if (!row.available) {
    const span = document.createElement("span");
    span.className = "lf-activity-target";
    span.textContent = label;
    return span;
  }
  const link = document.createElement("a");
  link.className = "lf-activity-target";
  link.dataset.lfCarry = `row-${row.id}`;
  link.href = `#${encodeURIComponent(row.widget)}`;
  link.textContent = label;
  return link;
}

export function fillActivityRow(item, row, offer) {
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

export function initialActivity(host, { offer, tabStore }) {
  const saved = tabStore.get(ACTIVITY_VIEW + host.id);
  const reading = saved
    ? JSON.parse(saved)
    : { open: false, shown: "[]", label: "Show activity", news: false };
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
  const rows = new Map();
  const drawn = JSON.parse(reading.shown);
  for (const row of drawn) {
    const item = document.createElement("li");
    item.className = "lf-activity-row";
    item.setAttribute("data-lf-activity-author", row.author);
    fillActivityRow(item, row, offer);
    list.append(item);
    rows.set(row.id, { item, key: JSON.stringify(row) });
  }
  empty.hidden = !reading.open || drawn.length > 0;
  host.replaceChildren(notice, list, empty);
  return { notice, list, empty, rows, reading, restored: saved !== null };
}
