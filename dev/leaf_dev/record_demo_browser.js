(function installRecordDemoBrowser() {
  function selectText(selector, text) {
    const walker = document.createTreeWalker(
      document.querySelector(selector),
      NodeFilter.SHOW_TEXT,
    );
    let node;
    while ((node = walker.nextNode())) {
      const at = node.data.indexOf(text);
      if (at < 0) continue;
      const range = document.createRange();
      range.setStart(node, at);
      range.setEnd(node, at + text.length);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      return selection.toString();
    }
    return null;
  }

  globalThis.__leafRecordDemo = Object.freeze({ selectText });
})();
