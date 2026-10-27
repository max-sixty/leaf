"""Browser resource URL identity shared by source readings, capture and delivery."""

import posixpath
from pathlib import Path
from urllib.parse import quote, unquote

from pywhatwgurl import URL

from .schema import JAVASCRIPT_SUFFIXES


class ReferenceError(ValueError):
    """A URL cannot name a supported resource; admission adds its source location."""

    def __init__(self, code: str, **values):
        self.code = code
        self.values = values
        super().__init__(code)


def resource_reference(
    specifier: str, importer: str, *, module=False
) -> tuple[str, str] | None:
    """A browser URL's decoded filesystem path and its query/fragment suffix.

    The WHATWG parser resolves URL syntax; filesystem normalization and the
    caller's containment gate decide which local file it names. Decoding happens
    once, so escaped percent signs remain literal parts of filenames. A module's
    suffix is refused because the captured module graph keys execution by path.
    Capture has no deployment origin: a resource must be local on both HTTP and
    HTTPS or external on both. Scheme-dependent references are refused rather
    than silently omitting a file the browser can load locally.
    """
    base = "https://leaf.invalid"
    other_base = "http://relative.invalid"
    importer_url = quote(importer, safe="/")
    other_importer_url = importer_url + "-reference"
    try:
        url = URL(specifier, base + importer_url)
    except ValueError as error:
        raise ReferenceError("dependency-url", error=str(error)) from error
    if url.protocol == "data:":
        return None
    if not specifier or url.protocol not in {"http:", "https:"}:
        raise ReferenceError("dependency-not-local")
    # A local reference follows either base's origin. Absolute and network-path
    # references keep their own host, even when it happens to equal one base.
    try:
        other = URL(specifier, other_base + other_importer_url)
    except ValueError as error:
        raise ReferenceError("dependency-scheme-dependent") from error
    if url.origin != base or other.origin != other_base:
        # Following just one origin can mean a scheme-dependent relative URL or
        # an external URL whose host happens to match that base. A third host
        # with the matching scheme distinguishes them through the same parser.
        for resolved, origin in ((url, base), (other, other_base)):
            if resolved.origin == origin:
                same_scheme_base = resolved.protocol + "//reference.invalid"
                if (
                    URL(specifier, same_scheme_base + importer_url).origin
                    == same_scheme_base
                ):
                    raise ReferenceError("dependency-scheme-dependent")
        return None
    # Fragment-only references follow the base's filename too. An explicit
    # self-resource URL does not follow the other filename and remains captured.
    if (
        "#" in url.href
        and not url.search
        and url.pathname == importer_url
        and other.pathname == other_importer_url
    ):
        return None
    if module and ("?" in url.href or "#" in url.href):
        raise ReferenceError("dependency-not-local")
    path = unquote(url.pathname)
    if "\\" in path or any(ord(char) < 32 for char in path):
        raise ReferenceError("dependency-encoded")
    resolved = posixpath.normpath(path)
    if resolved.startswith("//") or not resolved.startswith("/"):
        raise ReferenceError("dependency-escapes")
    # A module is JavaScript, or JSON its import reads `with { type: "json" }`, as
    # the runtime reads its kernel registry; the browser refuses JSON imported
    # without it, which a page's render check reports as a console error.
    if module and Path(resolved).suffix not in {*JAVASCRIPT_SUFFIXES, ".json"}:
        raise ReferenceError("module-type")
    return resolved, url.search + url.hash
