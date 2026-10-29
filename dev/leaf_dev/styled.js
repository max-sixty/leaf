/* Development-only reading of computed style, for `leaf-dev stills`: evaluated with the
 * properties to read (`STYLED`, stills.py), it returns every element's values by its
 * path of tags, ids and first two classes, sharing each distinct set of values, in the
 * document and every open shadow tree. It leaves its reader on the page as
 * `leafDevStyled`, so a later reading of the same elements, such as the face census's
 * at rest and under the pointer (faces.js), reads the same properties under the same
 * keys rather than a list of its own.
 */
(properties) => {
  const skip = new Set(["head", "script", "style", "template", "link", "meta"]);
  const keys = new Map();
  // An element's values, or its pseudo-element's where that draws.
  const values = (element, pseudo) => {
    const style = getComputedStyle(element, pseudo);
    if (
      pseudo &&
      (["none", "normal"].includes(style.content) || style.display === "none")
    )
      return null;
    return properties.map((name) => style.getPropertyValue(name));
  };
  const faces = new Map();
  const elements = {};
  const walk = (parent, prefix) => {
    const seen = {};
    for (const element of parent.children) {
      if (skip.has(element.localName)) continue;
      const label =
        element.localName +
        (element.id
          ? `#${element.id}`
          : [...element.classList]
              .slice(0, 2)
              .map((name) => `.${name}`)
              .join(""));
      seen[label] = (seen[label] ?? -1) + 1;
      const key = prefix + label + (seen[label] ? `:${seen[label]}` : "");
      keys.set(element, key);
      const face = JSON.stringify(values(element));
      if (!faces.has(face)) faces.set(face, faces.size);
      elements[key] = faces.get(face);
      walk(element, `${key} > `);
      if (element.shadowRoot) walk(element.shadowRoot, `${key} >> `);
    }
  };
  walk(document, "");
  globalThis.leafDevStyled = { properties, values, keys };
  return { faces: [...faces.keys()].map((face) => JSON.parse(face)), elements };
};
