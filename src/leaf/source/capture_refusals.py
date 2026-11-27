"""What a capture refuses: each problem it finds as a finding (`capture_finding`), and
the refusal carrying every one at once (`ArtifactError`).

A capture finds problems wherever it reads, in a module's imports
(`resource_urls.javascript_imports`), a stylesheet's URLs (`styles.css_dependencies`),
the files it captures and the bundle it stores (`revision_artifact`), and the readers
that delivery and export share with it refuse in the same terms."""

from leaf.base.findings import Finding, Rejected


class ArtifactError(Rejected):
    """A candidate cannot be captured as a complete local revision, refused with every
    finding that says why. A capture reports each problem in every file it reads, so
    an author repairs them all from one check (`revision_artifact._collect`)."""


def capture_finding(code: str, file=None, specifier=None, /, **values) -> Finding:
    """One capture problem: `code` names it, `file` the file it was read in,
    `specifier` the reference in that file it concerns."""
    if file is not None:
        values["file"] = str(file)
    if specifier is not None:
        values["specifier"] = specifier
    return Finding(code, values=values)


def artifact_error(code: str, file=None, specifier=None, /, **values):
    """The refusal of one capture problem (`capture_finding`)."""
    return ArtifactError([capture_finding(code, file, specifier, **values)])
