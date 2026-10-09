(() => {
  // skills/leaf/packages/default/initial.js
  var BADGE = /^[+-]\d+$/;
  function parseTree(text) {
    const root = { children: [] };
    const stack = [{ indent: -1, node: root }];
    for (const line of text.split("\n")) {
      if (!line.trim()) continue;
      const indent = line.length - line.trimStart().length;
      const tokens = line.trim().split(/\s+/);
      const badges = [];
      while (tokens.length > 1 && BADGE.test(tokens[tokens.length - 1]))
        badges.unshift(tokens.pop());
      const name = tokens.join(" ");
      const node = {
        name: name.replace(/\/$/, ""),
        dir: name.endsWith("/"),
        badges,
        children: []
      };
      while (stack[stack.length - 1].indent >= indent) stack.pop();
      stack[stack.length - 1].node.children.push(node);
      stack.push({ indent, node });
    }
    return root.children;
  }
  function listNode(nodes) {
    const ul = document.createElement("ul");
    for (const node of nodes) {
      const li = document.createElement("li");
      const name = document.createElement("span");
      if (node.dir || node.children.length) name.className = "lf-tree-dir";
      name.textContent = node.name + (node.dir || node.children.length ? "/" : "");
      li.append(name);
      for (const badge of node.badges)
        li.append(
          Object.assign(document.createElement("span"), {
            className: `lf-tree-badge ${badge.startsWith("+") ? "add" : "del"}`,
            textContent: badge
          })
        );
      if (node.children.length) li.append(listNode(node.children));
      ul.append(li);
    }
    return ul;
  }
  function render(host) {
    const source = host.querySelector(":scope > pre").textContent;
    const nodes = parseTree(source);
    if (!nodes.length) return { source, error: new Error("empty tree") };
    host.replaceChildren(listNode(nodes));
    host.classList.add("lf-rendered");
    return {};
  }
  document.documentElement.lfInitial.register("lf-tree", render);
})();
