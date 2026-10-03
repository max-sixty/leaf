/* One offline document's resource addresses, allocated before native HTML parsing.

   The export's composed document, CSS resource bodies and runtime address table use
   the same tokens. Each captured body appears once in the file; each token becomes
   one object URL shared by native elements, stylesheets and runtimeResource. Module
   data URLs and the import map keep their existing module identity. document.write
   hands the existing composed source to the native parser, including classic scripts,
   import maps and declarative shadow trees; it creates no alternate renderer. */
window.setTimeout(() => {
  const packageScript = document.querySelector("script[data-lf-export]");
  const exported = JSON.parse(packageScript.textContent);
  const addresses = new Map();
  const reference = new RegExp(`${exported.prefix}[a-f0-9]{64}`, "g");
  const rebase = (source) =>
    source.replace(reference, (token) =>
      Object.hasOwn(exported.resources, token) ? address(token) : token,
    );
  function address(token) {
    if (addresses.has(token)) return addresses.get(token);
    const resource = exported.resources[token];
    const bytes = Uint8Array.from(window.atob(resource.base64), (character) =>
      character.charCodeAt(0),
    );
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
