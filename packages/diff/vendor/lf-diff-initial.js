(() => {
  // packages/diff/widgets/diff-coordinates.js
  function findDiffFile(entries, coordinate) {
    if (!coordinate || !entries) return null;
    if (coordinate.source && coordinate.side === "old") {
      const renamed = entries.filter(
        ({ record }) => record.operation === "rename" && record.previousPath === coordinate.path
      );
      if (renamed.length) return renamed.length === 1 ? renamed[0] : null;
    }
    const matching = entries.filter(
      ({ record }) => (coordinate.source && coordinate.side === "old" ? record.previousPath ?? record.path : record.path) === coordinate.path
    );
    return matching.length === 1 ? matching[0] : null;
  }

  // packages/diff/widgets/overflow.js
  var overflowFor = (path, authored) => authored ?? (/\.(?:md|markdown|txt)$/i.test(path) ? "wrap" : "scroll");

  // packages/diff/initial/lf-diff.js
  document.documentElement.lfInitial.register("lf-diff", (host, tools) => {
    const pre = host.querySelector(":scope > pre");
    if (!pre || host.getAttribute("data-lf-height")) return null;
    const value = host.hasAttribute("source") ? tools.inputValue("document") : pre?.textContent;
    if (typeof value !== "string") return null;
    const authored = host.getAttribute("overflow");
    const lines = value.replace(/^\n+|\n+$/g, "").split("\n");
    const files = [];
    let file = null;
    let old = 0;
    let added = 0;
    for (const line of lines) {
      const hunk = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/.exec(line);
      if (hunk && old <= 0 && added <= 0) {
        const [, a, b = "1", c, d = "1"] = hunk;
        if (!file)
          files.push(file = { path: "", hunks: 0, rows: 0, largest: 0, texts: [] });
        old = Number(b);
        added = Number(d);
        file.rows += file.hunks++ || Number(a) > 1 || Number(c) > 1 ? 1 : 0;
        file.largest = Math.max(file.largest, Number(a) + old - 1, Number(c) + added - 1);
      } else if (file?.hunks && (old > 0 || added > 0 || line.startsWith("\\"))) {
        if (line[0] !== "+" && line[0] !== "\\") old--;
        if (line[0] !== "-" && line[0] !== "\\") added--;
        file.rows++;
        file.texts.push(line.slice(1));
      } else {
        if (!file || file.hunks || line.startsWith("diff --git "))
          files.push(file = { path: "", hunks: 0, rows: 0, largest: 0, texts: [] });
        const named = /^(?:\+\+\+ b\/|--- a\/|diff --git a\/\S+ b\/)(.+)$/.exec(line);
        if (named && named[1] !== "/dev/null") file.path = named[1];
        const previous = /^--- a\/(.+)$/.exec(line);
        if (previous) file.previousPath = previous[1];
        if (line.startsWith("rename from ")) file.operation = "rename";
      }
    }
    const singleFile = host.getAttribute("view") === "file";
    const shown = singleFile ? files.slice(0, 1) : files;
    if (!shown.length || shown.some((each) => !each.hunks)) return null;
    const open = singleFile || !host.hasAttribute("collapsed");
    let rows = 0;
    let style = null;
    let width = 0;
    let ch = 0;
    for (const each of open ? shown : []) {
      rows += each.rows;
      if (overflowFor(each.path, authored) !== "wrap") continue;
      if (!style) {
        style = getComputedStyle(pre);
        const context = document.createElement("canvas").getContext("2d");
        context.font = `${style.fontSize} ${style.fontFamily}`;
        ch = context.measureText("0").width;
        width = host.getBoundingClientRect().width;
      }
      const digits = String(each.largest).length;
      const cols = Math.floor((width - 2 - 8 - (digits + 5) * ch) / ch);
      if (cols > 0) for (const text of each.texts) rows += wraps(text, cols);
    }
    const notes = [...host.querySelectorAll(":scope > lf-diff-note")];
    const entries = files.map((record) => ({ record }));
    const notesHeight = notes.reduce((height, note) => {
      const entry = findDiffFile(entries, {
        path: note.getAttribute("file"),
        source: true,
        side: note.getAttribute("side")
      });
      const visible = !entry || open && shown.includes(entry.record);
      return height + (visible ? note.getBoundingClientRect().height : 0);
    }, 0);
    host.style.setProperty("--lf-diff-notes-height", `${notesHeight}px`);
    host.style.setProperty("--lf-diff-files", String(shown.length));
    host.style.setProperty("--lf-diff-rows", String(rows));
    host.style.setProperty("--lf-diff-open", open ? "1" : "0");
    return null;
  });
  function wraps(text, cols) {
    if (text.length <= cols) return 0;
    let extra = 0;
    let used = 0;
    for (const [, space, word] of text.matchAll(/( *)([^ ]*)/g)) {
      used += space.length;
      if (!word) continue;
      if (used > 0 && used + word.length > cols) {
        extra++;
        used = 0;
      }
      let rest = word.length;
      while (used + rest > cols) {
        rest -= cols - used;
        extra++;
        used = 0;
      }
      used += rest;
    }
    return extra;
  }
})();
