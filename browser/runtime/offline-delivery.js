/* One offline document's resource addresses, allocated before native HTML parsing.

   The export's composed document, CSS resource bodies and runtime address table use
   the same tokens. Each captured body appears once in the file; each token becomes
   one object URL shared by native elements, stylesheets and runtimeResource. Module
   addresses and the import map share that allocator and module identity. document.write
   hands the existing composed source to the native parser, including classic scripts,
   import maps and declarative shadow trees; it creates no alternate renderer. */
/** @typedef {{mime: string, base64: string}} Resource */
window.setTimeout(() => {
  const packageScript = document.querySelector("script[data-lf-export]");
  if (!packageScript) throw new Error("Offline delivery has no resource package");
  /** @type {{prefix: string, document: string, resources: Record<string, Resource>}} */
  const exported = JSON.parse(packageScript.textContent);
  /** @type {Map<string, string>} */
  const addresses = new Map();
  const reference = new RegExp(`${exported.prefix}[a-f0-9]{64}`, "g");
  /** @param {string} source @returns {string} */
  const rebase = (source) =>
    source.replace(reference, (token) => {
      const resource = exported.resources[token];
      return resource ? address(token, resource) : token;
    });
  /** @param {string} token @param {Resource} resource @returns {string} */
  function address(token, resource) {
    const held = addresses.get(token);
    if (held !== undefined) return held;
    const bytes = Uint8Array.fromBase64(resource.base64);
    const body =
      resource.mime === "text/css"
        ? rebase(new window.TextDecoder().decode(bytes))
        : bytes;
    const url = URL.createObjectURL(new window.Blob([body], { type: resource.mime }));
    addresses.set(token, url);
    return url;
  }
  const source = rebase(exported.document);
  // Run outside the parser's script nesting: document.open() then retires the
  // readable outer document before the composed source enters the native parser.
  document.open();
  document.write(source);
  document.close();
}, 0);
